from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.research_storage import (
    initialize_research_layout,
    inspect_research_storage,
)


PREFLIGHT_CONTRACT = "atlas-news-options-data-foundation-preflight-v1"
DOCUMENTED_SOURCE_COVERAGE_AS_OF = "2026-09-20"
DOCUMENTED_SOURCE_COVERAGE = {
    "alpaca_news": {
        "historical_start": "2015-01-01",
        "role": "BROAD_HISTORICAL_NEWS",
    },
    "alpaca_options": {
        "historical_start": "2024-02-01",
        "role": "RECENT_CANDIDATE_OPTION_DATA",
    },
    "massive_option_day_aggregates": {
        "historical_start": "2014-06-02",
        "role": "BROAD_OPTION_DAILY",
    },
    "massive_option_minute_aggregates": {
        "historical_start": "2014-06-02",
        "role": "SELECTIVE_OR_BULK_OPTION_MINUTE",
    },
    "massive_option_trades": {
        "historical_start": "2014-06-02",
        "role": "SELECTIVE_CANDIDATE_TRADES",
    },
    "massive_option_quotes": {
        "historical_start": "2022-03-07",
        "role": "SELECTIVE_CANDIDATE_TOP_OF_BOOK",
    },
}


class NewsOptionsSourcePreflightError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _redacted_http_probe(
    request: urllib.request.Request,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            payload: Any = None
            if raw:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = None
            return {
                "status": "ACCESSIBLE",
                "http_status": int(response.status),
                "response_bytes": len(raw),
                "result_count": (
                    len(payload.get("news", []))
                    if isinstance(payload, dict)
                    and isinstance(payload.get("news"), list)
                    else (
                        len(payload.get("results", []))
                        if isinstance(payload, dict)
                        and isinstance(payload.get("results"), list)
                        else None
                    )
                ),
            }
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = ""
        return {
            "status": "HTTP_ERROR",
            "http_status": int(exc.code),
            "error": body,
        }
    except urllib.error.URLError as exc:
        return {
            "status": "NETWORK_ERROR",
            "error": str(exc.reason),
        }


def _resolve_alpaca_market_data_credentials(
    settings: AtlasSettings,
) -> tuple[str, str, str] | None:
    cfg = settings.alpaca.credentials
    profiles = [cfg.preferred_profile, "paper", "live"]
    seen: set[str] = set()
    for profile in profiles:
        if profile in seen:
            continue
        seen.add(profile)
        if profile == "paper":
            key_env = cfg.paper_api_key_env
            secret_env = cfg.paper_api_secret_env
        elif profile == "live":
            key_env = cfg.live_api_key_env
            secret_env = cfg.live_api_secret_env
        else:
            continue
        key = os.getenv(key_env, "").strip()
        secret = os.getenv(secret_env, "").strip()
        if key and secret:
            return profile, key, secret
    return None


def probe_alpaca_historical_news(settings: AtlasSettings) -> dict[str, object]:
    credentials = _resolve_alpaca_market_data_credentials(settings)
    if credentials is None:
        return {
            "status": "NOT_CONFIGURED",
            "credential_secret_values_exposed": False,
        }
    profile, key, secret = credentials
    cfg = settings.data.research.news
    query = urllib.parse.urlencode(
        {
            "start": "2015-01-01",
            "end": "2015-01-07",
            "limit": 1,
            "sort": "asc",
            "include_content": "false",
        }
    )
    url = (
        settings.alpaca.market_data.base_url.rstrip("/")
        + cfg.endpoint_path
        + "?"
        + query
    )
    request = urllib.request.Request(
        url,
        headers={
            "APCA-API-KEY-ID": key,
            "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json",
            "User-Agent": "ATLAS-news-options-preflight/1",
        },
        method="GET",
    )
    result = _redacted_http_probe(
        request,
        timeout_seconds=settings.alpaca.market_data.request_timeout_seconds,
    )
    return {
        **result,
        "credential_profile": profile,
        "probe_window": ["2015-01-01", "2015-01-07"],
        "credential_secret_values_exposed": False,
    }


def probe_massive_option_reference(settings: AtlasSettings) -> dict[str, object]:
    key_env = settings.massive.credentials.api_key_env
    key = os.getenv(key_env, "").strip()
    if not key:
        return {
            "status": "NOT_CONFIGURED",
            "credential_secret_values_exposed": False,
        }
    cfg = settings.data.research.options
    query = urllib.parse.urlencode(
        {
            "underlying_ticker": "SPY",
            "expiration_date.gte": "2016-01-01",
            "expiration_date.lt": "2017-01-01",
            "limit": 1,
            "order": "asc",
            "sort": "expiration_date",
        }
    )
    url = (
        settings.massive.provider.rest_base_url.rstrip("/")
        + cfg.reference_endpoint_path
        + "?"
        + query
    )
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "ATLAS-news-options-preflight/1",
        },
        method="GET",
    )
    result = _redacted_http_probe(
        request,
        timeout_seconds=settings.massive.reference.request_timeout_seconds,
    )
    return {
        **result,
        "probe_underlying": "SPY",
        "probe_expiration_year": 2016,
        "credential_secret_values_exposed": False,
    }


def _massive_s3_probe(
    settings: AtlasSettings,
    *,
    dataset: str,
    prefix: str,
    year: int,
) -> dict[str, object]:
    creds = settings.massive.credentials
    access_key = os.getenv(creds.s3_access_key_env, "").strip()
    secret_key = os.getenv(creds.s3_secret_key_env, "").strip()
    if not access_key or not secret_key:
        return {
            "dataset": dataset,
            "year": year,
            "status": "NOT_CONFIGURED",
            "credential_secret_values_exposed": False,
        }
    client = boto3.client(
        "s3",
        endpoint_url=settings.massive.provider.flat_file_endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="us-east-1",
    )
    full_prefix = f"{prefix.rstrip('/')}/{year}/"
    try:
        response = client.list_objects_v2(
            Bucket=settings.massive.provider.flat_file_bucket,
            Prefix=full_prefix,
            MaxKeys=1,
        )
        contents = response.get("Contents") or []
        if not contents:
            return {
                "dataset": dataset,
                "year": year,
                "status": "NO_VISIBLE_OBJECT",
                "prefix": full_prefix,
                "credential_secret_values_exposed": False,
            }
        item = contents[0]
        return {
            "dataset": dataset,
            "year": year,
            "status": "ACCESSIBLE",
            "prefix": full_prefix,
            "sample_key": str(item.get("Key") or ""),
            "sample_size_bytes": int(item.get("Size") or 0),
            "credential_secret_values_exposed": False,
        }
    except ClientError as exc:
        error = exc.response.get("Error", {})
        return {
            "dataset": dataset,
            "year": year,
            "status": "S3_ERROR",
            "prefix": full_prefix,
            "error_code": str(error.get("Code") or ""),
            "error_message": str(error.get("Message") or "")[:300],
            "credential_secret_values_exposed": False,
        }
    except BotoCoreError as exc:
        return {
            "dataset": dataset,
            "year": year,
            "status": "S3_ERROR",
            "prefix": full_prefix,
            "error_code": type(exc).__name__,
            "error_message": str(exc)[:300],
            "credential_secret_values_exposed": False,
        }


def run_news_options_data_preflight(
    settings: AtlasSettings,
    *,
    initialize_layout: bool,
    probe_providers: bool,
    output_path: Path | None = None,
) -> dict[str, object]:
    if initialize_layout:
        layout = initialize_research_layout(settings)
    else:
        from packages.data.research_storage import planned_research_layout

        layout = planned_research_layout(settings)

    storage = inspect_research_storage(settings)
    provider_probes: dict[str, object] = {
        "performed": probe_providers,
    }
    if probe_providers:
        provider_probes["alpaca_historical_news"] = probe_alpaca_historical_news(
            settings
        )
        provider_probes["massive_option_reference_2016"] = (
            probe_massive_option_reference(settings)
        )
        opt = settings.data.research.options
        provider_probes["massive_s3"] = [
            _massive_s3_probe(
                settings,
                dataset="OPTION_DAY_AGGREGATES",
                prefix=opt.massive_day_prefix,
                year=year,
            )
            for year in (2016, 2025)
        ] + [
            _massive_s3_probe(
                settings,
                dataset="OPTION_MINUTE_AGGREGATES",
                prefix=opt.massive_minute_prefix,
                year=year,
            )
            for year in (2016, 2025)
        ]

    report: dict[str, object] = {
        "contract": PREFLIGHT_CONTRACT,
        "generated_utc": datetime.now(UTC).isoformat(),
        "project_root": str(settings.project_root.resolve()),
        "storage": asdict(storage),
        "planned_layout": [str(path) for path in layout],
        "layout_initialized": initialize_layout,
        "documented_source_coverage_as_of": DOCUMENTED_SOURCE_COVERAGE_AS_OF,
        "documented_source_coverage": DOCUMENTED_SOURCE_COVERAGE,
        "provider_probes": provider_probes,
        "bulk_downloads_performed": 0,
        "provider_records_persisted": 0,
        "secrets_persisted": False,
        "authority": {
            "source_probe_only": True,
            "strategy_outcome_access": False,
            "consumed_master_rows_permitted": 0,
            "future_blind_rows_permitted": 0,
            "broker_reads_permitted": 0,
            "broker_writes_permitted": 0,
            "order_actions_permitted": 0,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    report["fingerprint"] = _stable_hash(
        {
            key: value
            for key, value in report.items()
            if key != "generated_utc"
        }
    )

    final_path = (
        Path(output_path).resolve()
        if output_path is not None
        else settings.resolved_path(
            "data/manifests/news_options_source_preflight.json"
        )
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        final_path,
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        fsync=True,
    )
    return report
