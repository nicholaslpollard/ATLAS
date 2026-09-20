from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from packages.core.settings import AtlasSettings
from packages.data.historical_news_v1 import _month_paths, month_windows
from packages.data.historical_news_v1_closeout import (
    _atomic_write_json,
    _parse_timestamp,
    _parquet_source,
    _rfc3339,
)


DIAGNOSTIC_CONTRACT = "atlas-historical-news-v1-chronology-diagnostic-v1"


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _chronology_fields(
    *,
    created_at: object,
    updated_at: object,
    pit_available_at: object,
) -> dict[str, object]:
    created = _parse_timestamp(created_at)
    updated = _parse_timestamp(updated_at)
    pit = _parse_timestamp(pit_available_at)
    if created is None or updated is None:
        raise ValueError("chronology diagnostic requires created_at and updated_at")
    return {
        "created_at": _iso(created_at),
        "updated_at": _iso(updated_at),
        "pit_available_at": _iso(pit_available_at),
        "updated_before_created": updated < created,
        "updated_before_created_seconds": (
            (created - updated).total_seconds() if updated < created else 0.0
        ),
        "pit_before_created": bool(pit is not None and pit < created),
        "pit_equals_updated": pit == updated,
    }


def _normalized_anomalies_for_month(
    *,
    month: str,
    normalized_path: Path,
    query_start_utc: str,
    query_end_utc: str,
) -> list[dict[str, object]]:
    if not normalized_path.is_file():
        return []
    con = duckdb.connect(database=":memory:")
    try:
        source = _parquet_source([normalized_path])
        rows = con.execute(
            f"""
            SELECT
                article_id,
                source,
                headline,
                url,
                created_at,
                updated_at,
                pit_available_at,
                symbols_json,
                provider_record_sha256,
                pit_text_policy
            FROM {source}
            WHERE
                created_at IS NOT NULL
                AND updated_at IS NOT NULL
                AND updated_at < created_at
            ORDER BY article_id
            """
        ).fetchall()
    finally:
        con.close()

    anomalies: list[dict[str, object]] = []
    for (
        article_id,
        source_name,
        headline,
        url,
        created_at,
        updated_at,
        pit_available_at,
        symbols_json,
        provider_record_sha256,
        pit_text_policy,
    ) in rows:
        item: dict[str, object] = {
            "month": month,
            "query_start_utc": query_start_utc,
            "query_end_utc": query_end_utc,
            "article_id": str(article_id),
            "source": str(source_name or ""),
            "headline": str(headline or ""),
            "url": str(url or ""),
            "symbols": json.loads(str(symbols_json or "[]")),
            "provider_record_sha256": str(provider_record_sha256 or ""),
            "pit_text_policy": str(pit_text_policy or ""),
        }
        item.update(
            _chronology_fields(
                created_at=created_at,
                updated_at=updated_at,
                pit_available_at=pit_available_at,
            )
        )
        anomalies.append(item)
    return anomalies


def _select_raw_records(
    raw_path: Path,
    article_ids: set[str],
) -> dict[str, dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    if not article_ids:
        return chosen
    with gzip.open(raw_path, "rt", encoding="utf-8", newline="") as handle:
        for line in handle:
            text = line.rstrip("\n")
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                continue
            article_id = str(value.get("id") or "").strip()
            if article_id not in article_ids:
                continue
            current = chosen.get(article_id)
            if current is None:
                chosen[article_id] = value
                continue
            candidate_key = (
                str(value.get("updated_at") or ""),
                _stable_json(value),
            )
            current_key = (
                str(current.get("updated_at") or ""),
                _stable_json(current),
            )
            if candidate_key > current_key:
                chosen[article_id] = value
    return chosen


def run_historical_news_v1_chronology_diagnostic(
    settings: AtlasSettings,
) -> dict[str, object]:
    anomalies: list[dict[str, object]] = []
    windows_by_month = {window.key: window for window in month_windows()}

    for month, window in windows_by_month.items():
        paths = _month_paths(settings, window)
        anomalies.extend(
            _normalized_anomalies_for_month(
                month=month,
                normalized_path=paths["normalized"],
                query_start_utc=_rfc3339(window.start_utc),
                query_end_utc=_rfc3339(window.end_utc),
            )
        )

    ids_by_month: dict[str, set[str]] = {}
    for anomaly in anomalies:
        ids_by_month.setdefault(str(anomaly["month"]), set()).add(
            str(anomaly["article_id"])
        )

    for month, article_ids in ids_by_month.items():
        window = windows_by_month[month]
        paths = _month_paths(settings, window)
        selected = _select_raw_records(paths["raw"], article_ids)
        for anomaly in anomalies:
            if anomaly["month"] != month:
                continue
            article_id = str(anomaly["article_id"])
            raw = selected.get(article_id)
            if raw is None:
                anomaly["raw_record_found"] = False
                anomaly["raw_normalized_hash_match"] = False
                continue

            raw_hash = _canonical_hash(raw)
            anomaly["raw_record_found"] = True
            anomaly["raw_provider_record_sha256"] = raw_hash
            anomaly["raw_normalized_hash_match"] = (
                raw_hash == anomaly["provider_record_sha256"]
            )
            anomaly["raw_created_at"] = (
                None if raw.get("created_at") is None else str(raw.get("created_at"))
            )
            anomaly["raw_updated_at"] = (
                None if raw.get("updated_at") is None else str(raw.get("updated_at"))
            )
            anomaly["raw_source"] = str(raw.get("source") or "")
            anomaly["raw_headline"] = str(raw.get("headline") or "")
            anomaly["raw_url"] = str(raw.get("url") or "")
            anomaly["raw_symbols"] = raw.get("symbols") or []

            created = _parse_timestamp(raw.get("created_at"))
            updated = _parse_timestamp(raw.get("updated_at"))
            query_start = _parse_timestamp(anomaly["query_start_utc"])
            query_end = _parse_timestamp(anomaly["query_end_utc"])
            anomaly["raw_created_inside_query_window"] = bool(
                created is not None
                and query_start is not None
                and query_end is not None
                and query_start <= created <= query_end
            )
            anomaly["raw_updated_inside_query_window"] = bool(
                updated is not None
                and query_start is not None
                and query_end is not None
                and query_start <= updated <= query_end
            )

    anomalies.sort(
        key=lambda item: (
            str(item["month"]),
            str(item["created_at"]),
            str(item["article_id"]),
        )
    )

    report: dict[str, object] = {
        "status": "ANOMALIES_FOUND" if anomalies else "NO_ANOMALIES",
        "contract": DIAGNOSTIC_CONTRACT,
        "anomaly_count": len(anomalies),
        "months": sorted(ids_by_month),
        "all_raw_records_found": all(
            bool(item.get("raw_record_found")) for item in anomalies
        ),
        "all_raw_normalized_hashes_match": all(
            bool(item.get("raw_normalized_hash_match")) for item in anomalies
        ),
        "all_pit_equals_updated": all(
            bool(item.get("pit_equals_updated")) for item in anomalies
        ),
        "all_pit_before_created": all(
            bool(item.get("pit_before_created")) for item in anomalies
        ),
        "anomalies": anomalies,
        "authority": {
            "diagnostic_only": True,
            "source_mutation": False,
            "provider_calls": False,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }

    report_path = settings.resolved_path(
        "data/news/manifests/alpaca/"
        "historical_news_v1_chronology_diagnostic.json"
    )
    _atomic_write_json(report_path, report)
    return report
