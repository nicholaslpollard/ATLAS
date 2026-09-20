from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.provider_source_qualification import (
    QualificationDimension,
    qualification_dimensions,
    qualification_status,
    stable_fingerprint,
    stable_json,
)


QUALIFICATION_CONTRACT = (
    "atlas-historical-option-reference-source-qualification-v1"
)
DOCUMENTED_PROVIDER_SEMANTICS_AS_OF = "2026-09-20"
DOCUMENTED_HISTORY_START = "2014-06-02"
REFERENCE_ENDPOINT = "/v3/reference/options/contracts"
MAX_PROBE_RECORDS_PER_PAGE = 25
MAX_PAGINATION_PAGES = 2

REQUIRED_RECORD_FIELDS: tuple[str, ...] = (
    "ticker",
    "underlying_ticker",
    "contract_type",
    "expiration_date",
    "strike_price",
    "exercise_style",
    "shares_per_contract",
)
KNOWN_OPTIONAL_RECORD_FIELDS: tuple[str, ...] = (
    "additional_underlyings",
    "cfi",
    "correction",
    "primary_exchange",
)

PROBE_CASES: tuple[dict[str, object], ...] = (
    {
        "name": "earliest_documented_history_spy",
        "params": {
            "underlying_ticker": "SPY",
            "expiration_date.gte": "2014-06-02",
            "expiration_date.lt": "2014-07-01",
            "as_of": "2014-06-02",
            "expired": "false",
            "order": "asc",
            "sort": "ticker",
            "limit": MAX_PROBE_RECORDS_PER_PAGE,
        },
    },
    {
        "name": "historical_2016_spy_point_in_time",
        "params": {
            "underlying_ticker": "SPY",
            "expiration_date.gte": "2016-01-01",
            "expiration_date.lt": "2016-02-01",
            "as_of": "2015-12-15",
            "expired": "false",
            "order": "asc",
            "sort": "ticker",
            "limit": MAX_PROBE_RECORDS_PER_PAGE,
        },
    },
    {
        "name": "historical_2016_spy_expired_current_view",
        "params": {
            "underlying_ticker": "SPY",
            "expiration_date.gte": "2016-01-01",
            "expiration_date.lt": "2016-02-01",
            "as_of": "2026-09-19",
            "expired": "true",
            "order": "asc",
            "sort": "ticker",
            "limit": MAX_PROBE_RECORDS_PER_PAGE,
        },
    },
    {
        "name": "recent_2026_spy_point_in_time",
        "params": {
            "underlying_ticker": "SPY",
            "expiration_date.gte": "2026-09-01",
            "expiration_date.lt": "2026-10-01",
            "as_of": "2026-09-19",
            "expired": "false",
            "order": "asc",
            "sort": "ticker",
            "limit": MAX_PROBE_RECORDS_PER_PAGE,
        },
    },
    {
        "name": "broad_pagination_2025_standard_expiry",
        "params": {
            "expiration_date": "2025-01-17",
            "as_of": "2025-01-17",
            "expired": "false",
            "order": "asc",
            "sort": "ticker",
            "limit": MAX_PROBE_RECORDS_PER_PAGE,
        },
    },
)


class HistoricalOptionReferenceQualificationError(RuntimeError):
    pass


def qualification_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": QUALIFICATION_CONTRACT,
        "provider": "massive",
        "endpoint": REFERENCE_ENDPOINT,
        "documented_provider_semantics_as_of": DOCUMENTED_PROVIDER_SEMANTICS_AS_OF,
        "documented_history_start": DOCUMENTED_HISTORY_START,
        "documented_semantics": {
            "all_contracts_includes_active_and_expired_listings": True,
            "as_of_is_point_in_time_date": True,
            "as_of_default": "TODAY",
            "expired_default": False,
            "page_limit_max": 1000,
            "pagination_field": "next_url",
            "reference_updates": "DAILY",
        },
        "probe_cases": list(PROBE_CASES),
        "required_record_fields": list(REQUIRED_RECORD_FIELDS),
        "known_optional_record_fields": list(KNOWN_OPTIONAL_RECORD_FIELDS),
        "qualification_dimensions": [
            "IDENTITY_AND_CARDINALITY",
            "TIMESTAMP_AND_CHRONOLOGY",
            "DUPLICATE_AND_VERSION_SEMANTICS",
            "PAGINATION_COMPLETENESS",
            "PROVIDER_METADATA_VS_OBSERVED_DATA",
            "POINT_IN_TIME_AVAILABILITY",
            "SCHEMA_TYPES_AND_NULLABILITY",
            "ENTITLEMENT_AND_COVERAGE_BOUNDARIES",
            "RAW_TO_NORMALIZED_RECONCILIATION",
            "CORRUPTION_HASH_AND_RECEIPT_INTEGRITY",
            "UNKNOWN_ANOMALIES_FAIL_CLOSED",
        ],
        "source_role_limits": {
            "reference_identity_and_structure": True,
            "historical_candidate_availability_authority": False,
            "historical_dynamic_deliverable_authority": False,
            "historical_market_price_authority": False,
            "reason": (
                "REFERENCE_ROWS_DO_NOT_EXPOSE_A_FIRST_LISTED_TIMESTAMP_AND_CURRENT_"
                "REFERENCE_STATE_MAY_REFLECT_LATER_CORRECTIONS"
            ),
        },
        "authority": {
            "qualification_only": True,
            "bulk_acquisition": False,
            "provider_writes": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    payload["fingerprint"] = stable_fingerprint(payload)
    return payload


HISTORICAL_OPTION_REFERENCE_QUALIFICATION_FINGERPRINT = str(
    qualification_manifest()["fingerprint"]
)


def _safe_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [
        (key, value)
        for key, value in query
        if key.lower() not in {"apikey", "api_key", "token"}
    ]
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(filtered),
            parsed.fragment,
        )
    )


def _request_json(
    settings: AtlasSettings,
    *,
    url: str,
    api_key: str,
) -> tuple[int, dict[str, Any]]:
    cfg = settings.massive.reference
    delay = float(cfg.initial_retry_seconds)
    for attempt in range(1, int(cfg.max_attempts) + 1):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "ATLAS-option-reference-qualification/1",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=float(cfg.request_timeout_seconds),
            ) as response:
                raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise HistoricalOptionReferenceQualificationError(
                        "Massive option-reference response root is not an object"
                    )
                return int(response.status), payload
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt >= int(cfg.max_attempts):
                body = exc.read().decode("utf-8", errors="replace")[:500]
                raise HistoricalOptionReferenceQualificationError(
                    f"Massive option-reference request failed HTTP {exc.code}: {body}"
                ) from exc
            retry_after = exc.headers.get("Retry-After")
            try:
                wait_seconds = float(retry_after) if retry_after else delay
            except ValueError:
                wait_seconds = delay
            time.sleep(max(0.0, wait_seconds))
            delay = min(float(cfg.max_retry_seconds), max(delay * 2.0, 0.1))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt >= int(cfg.max_attempts):
                raise HistoricalOptionReferenceQualificationError(
                    f"Massive option-reference request failed after {attempt} attempts: {exc}"
                ) from exc
            time.sleep(delay)
            delay = min(float(cfg.max_retry_seconds), max(delay * 2.0, 0.1))
    raise AssertionError("unreachable")


def _canonical_result_hash(results: list[dict[str, Any]]) -> str:
    return stable_fingerprint(
        sorted(
            results,
            key=lambda item: (
                str(item.get("ticker") or ""),
                stable_json(item),
            ),
        )
    )


def _summarize_results(results: list[dict[str, Any]]) -> dict[str, object]:
    tickers = [str(item.get("ticker") or "").strip() for item in results]
    nonempty_tickers = [ticker for ticker in tickers if ticker]
    field_union = sorted(
        {
            str(key)
            for item in results
            for key in item
        }
    )
    missing_required = {
        field: sum(
            1
            for item in results
            if item.get(field) in (None, "")
        )
        for field in REQUIRED_RECORD_FIELDS
    }
    missing_required = {
        field: count for field, count in missing_required.items() if count
    }
    unknown_fields = sorted(
        set(field_union)
        - set(REQUIRED_RECORD_FIELDS)
        - set(KNOWN_OPTIONAL_RECORD_FIELDS)
    )
    contract_types = sorted(
        {
            str(item.get("contract_type"))
            for item in results
            if item.get("contract_type") not in (None, "")
        }
    )
    exercise_styles = sorted(
        {
            str(item.get("exercise_style"))
            for item in results
            if item.get("exercise_style") not in (None, "")
        }
    )
    corrections = [
        item.get("correction")
        for item in results
        if item.get("correction") is not None
    ]
    additional_underlyings_count = sum(
        1
        for item in results
        if item.get("additional_underlyings") not in (None, [], "")
    )
    return {
        "result_count": len(results),
        "distinct_nonempty_tickers": len(set(nonempty_tickers)),
        "empty_ticker_count": len(results) - len(nonempty_tickers),
        "duplicate_ticker_rows": max(
            0, len(nonempty_tickers) - len(set(nonempty_tickers))
        ),
        "field_union": field_union,
        "missing_required_fields": missing_required,
        "unknown_fields": unknown_fields,
        "contract_types": contract_types,
        "exercise_styles": exercise_styles,
        "correction_field_present_count": len(corrections),
        "correction_values": sorted({str(value) for value in corrections}),
        "additional_underlyings_present_count": additional_underlyings_count,
        "sample_tickers": sorted(nonempty_tickers)[:5],
        "results_fingerprint": _canonical_result_hash(results),
    }


def _probe_case(
    settings: AtlasSettings,
    *,
    api_key: str,
    case: dict[str, object],
    follow_next_page: bool,
    repeat_first_page: bool,
) -> dict[str, object]:
    endpoint = (
        settings.massive.provider.rest_base_url.rstrip("/")
        + settings.data.research.options.reference_endpoint_path
    )
    params = dict(case["params"])
    first_url = endpoint + "?" + urllib.parse.urlencode(params)
    http_status, payload = _request_json(
        settings,
        url=first_url,
        api_key=api_key,
    )
    raw_results = payload.get("results") or []
    if not isinstance(raw_results, list) or any(
        not isinstance(item, dict) for item in raw_results
    ):
        raise HistoricalOptionReferenceQualificationError(
            f"{case['name']}: results is not a list of objects"
        )
    results: list[dict[str, Any]] = [dict(item) for item in raw_results]
    summary = _summarize_results(results)
    next_url = payload.get("next_url")
    output: dict[str, object] = {
        "name": str(case["name"]),
        "request_url": _safe_url(first_url),
        "http_status": http_status,
        "provider_status": payload.get("status"),
        "request_id_present": bool(payload.get("request_id")),
        "top_level_keys": sorted(str(key) for key in payload),
        "first_page": summary,
        "next_url_present": isinstance(next_url, str) and bool(next_url),
        "pages_fetched": 1,
    }

    if repeat_first_page:
        repeat_status, repeat_payload = _request_json(
            settings,
            url=first_url,
            api_key=api_key,
        )
        repeat_results = repeat_payload.get("results") or []
        if not isinstance(repeat_results, list) or any(
            not isinstance(item, dict) for item in repeat_results
        ):
            raise HistoricalOptionReferenceQualificationError(
                f"{case['name']}: repeated results is not a list of objects"
            )
        repeat_typed = [dict(item) for item in repeat_results]
        output["repeat_first_page"] = {
            "http_status": repeat_status,
            "result_count": len(repeat_typed),
            "results_fingerprint": _canonical_result_hash(repeat_typed),
            "stable": (
                _canonical_result_hash(repeat_typed)
                == summary["results_fingerprint"]
            ),
        }

    if follow_next_page and isinstance(next_url, str) and next_url:
        parsed_next = urllib.parse.urlsplit(next_url)
        parsed_base = urllib.parse.urlsplit(
            settings.massive.provider.rest_base_url
        )
        if parsed_next.scheme != "https" or parsed_next.netloc != parsed_base.netloc:
            raise HistoricalOptionReferenceQualificationError(
                f"{case['name']}: provider next_url escaped the configured HTTPS host"
            )
        second_status, second_payload = _request_json(
            settings,
            url=next_url,
            api_key=api_key,
        )
        second_raw = second_payload.get("results") or []
        if not isinstance(second_raw, list) or any(
            not isinstance(item, dict) for item in second_raw
        ):
            raise HistoricalOptionReferenceQualificationError(
                f"{case['name']}: second-page results is not a list of objects"
            )
        second_results = [dict(item) for item in second_raw]
        second_summary = _summarize_results(second_results)
        first_tickers = {
            str(item.get("ticker") or "")
            for item in results
            if item.get("ticker")
        }
        second_tickers = {
            str(item.get("ticker") or "")
            for item in second_results
            if item.get("ticker")
        }
        output["second_page"] = {
            **second_summary,
            "http_status": second_status,
            "request_url": _safe_url(next_url),
            "ticker_overlap_with_first_page": len(
                first_tickers & second_tickers
            ),
            "next_url_present": bool(second_payload.get("next_url")),
        }
        output["pages_fetched"] = 2

    return output


def _case_by_name(
    probes: list[dict[str, object]],
    name: str,
) -> dict[str, object]:
    for probe in probes:
        if probe.get("name") == name:
            return probe
    raise KeyError(name)


def _dimensions(
    probes: list[dict[str, object]],
) -> list[dict[str, str]]:
    result_pages: list[dict[str, object]] = []
    for probe in probes:
        first = probe.get("first_page")
        if isinstance(first, dict):
            result_pages.append(first)
        second = probe.get("second_page")
        if isinstance(second, dict):
            result_pages.append(second)

    duplicate_rows = sum(
        int(page.get("duplicate_ticker_rows", 0))
        for page in result_pages
    )
    missing_required = sum(
        sum(int(value) for value in dict(page.get("missing_required_fields", {})).values())
        for page in result_pages
    )
    recent = _case_by_name(probes, "recent_2026_spy_point_in_time")
    hist = _case_by_name(probes, "historical_2016_spy_point_in_time")
    earliest = _case_by_name(probes, "earliest_documented_history_spy")
    pagination = _case_by_name(
        probes, "broad_pagination_2025_standard_expiry"
    )
    repeat = hist.get("repeat_first_page")
    second = pagination.get("second_page")

    items = [
        QualificationDimension(
            "IDENTITY_AND_CARDINALITY",
            "PASS" if duplicate_rows == 0 else "FAIL",
            (
                "Sampled pages use option ticker as the provider identity; "
                f"duplicate sampled ticker rows={duplicate_rows}."
            ),
        ),
        QualificationDimension(
            "TIMESTAMP_AND_CHRONOLOGY",
            "LIMITATION",
            (
                "Reference rows expose expiration/as_of semantics but no provider "
                "created/listed timestamp; chronology of first listing cannot be "
                "proven from this source alone."
            ),
        ),
        QualificationDimension(
            "DUPLICATE_AND_VERSION_SEMANTICS",
            "LIMITATION",
            (
                "Provider exposes an optional correction field and adjusted "
                "deliverables; current-reference values are not granted historical "
                "dynamic-deliverable authority."
            ),
        ),
        QualificationDimension(
            "PAGINATION_COMPLETENESS",
            (
                "PASS"
                if not pagination.get("next_url_present")
                or (
                    isinstance(second, dict)
                    and int(second.get("ticker_overlap_with_first_page", -1)) == 0
                )
                else "FAIL"
            ),
            (
                "Pagination uses provider next_url. The bounded qualification follows "
                "at most one next page and requires zero ticker overlap between "
                "sampled consecutive pages."
            ),
        ),
        QualificationDimension(
            "PROVIDER_METADATA_VS_OBSERVED_DATA",
            "LIMITATION",
            (
                "Reference metadata is kept separate from later observed options "
                "bars/trades/quotes; reference alone is not market-activity proof."
            ),
        ),
        QualificationDimension(
            "POINT_IN_TIME_AVAILABILITY",
            "LIMITATION",
            (
                "The endpoint supports as_of, but absence of an explicit first-listed "
                "timestamp means reference rows alone cannot authorize historical "
                "candidate availability."
            ),
        ),
        QualificationDimension(
            "SCHEMA_TYPES_AND_NULLABILITY",
            "PASS" if missing_required == 0 else "FAIL",
            (
                f"Sampled missing required structural fields={missing_required}; "
                "unknown additive fields are recorded rather than silently rejected."
            ),
        ),
        QualificationDimension(
            "ENTITLEMENT_AND_COVERAGE_BOUNDARIES",
            (
                "PASS"
                if int(recent["first_page"].get("result_count", 0)) > 0
                and int(hist["first_page"].get("result_count", 0)) > 0
                else "FAIL"
            ),
            (
                "Qualification requires both recent 2026 and historical 2016 SPY "
                "reference visibility. The documented 2014-06-02 boundary is probed "
                f"separately; sampled earliest count="
                f"{int(earliest['first_page'].get('result_count', 0))}."
            ),
        ),
        QualificationDimension(
            "RAW_TO_NORMALIZED_RECONCILIATION",
            "NOT_APPLICABLE",
            (
                "No bulk raw/normalized corpus is created by qualification; the "
                "future acquisition contract must enforce exact raw-to-normalized "
                "counts and hashes."
            ),
        ),
        QualificationDimension(
            "CORRUPTION_HASH_AND_RECEIPT_INTEGRITY",
            (
                "PASS"
                if isinstance(repeat, dict) and repeat.get("stable") is True
                else "FAIL"
            ),
            (
                "The historical 2016 first-page result set is requested twice and "
                "must have an identical canonical results fingerprint."
            ),
        ),
        QualificationDimension(
            "UNKNOWN_ANOMALIES_FAIL_CLOSED",
            "PASS",
            (
                "Qualification persists observed schema additions and limitations; "
                "future acquisition is not authorized by this probe and unknown "
                "source anomalies remain fail-closed."
            ),
        ),
    ]
    return qualification_dimensions(items)


def run_historical_option_reference_qualification(
    settings: AtlasSettings,
    *,
    output_path: Path | None = None,
) -> dict[str, object]:
    key_env = settings.massive.credentials.api_key_env
    api_key = os.getenv(key_env, "").strip()
    if not api_key:
        raise HistoricalOptionReferenceQualificationError(
            f"Massive API key is not configured in {key_env}"
        )

    probes: list[dict[str, object]] = []
    for case in PROBE_CASES:
        name = str(case["name"])
        probes.append(
            _probe_case(
                settings,
                api_key=api_key,
                case=case,
                follow_next_page=(
                    name == "broad_pagination_2025_standard_expiry"
                ),
                repeat_first_page=(
                    name == "historical_2016_spy_point_in_time"
                ),
            )
        )

    dimensions = _dimensions(probes)
    status = qualification_status(dimensions)
    report: dict[str, object] = {
        "status": status,
        "contract": QUALIFICATION_CONTRACT,
        "contract_fingerprint": (
            HISTORICAL_OPTION_REFERENCE_QUALIFICATION_FINGERPRINT
        ),
        "generated_utc": datetime.now(UTC).isoformat(),
        "provider": "massive",
        "endpoint": settings.data.research.options.reference_endpoint_path,
        "documented_history_start": DOCUMENTED_HISTORY_START,
        "probes": probes,
        "dimensions": dimensions,
        "bulk_downloads_performed": 0,
        "provider_records_persisted": 0,
        "credential_secret_values_exposed": False,
        "source_role_limits": qualification_manifest()["source_role_limits"],
        "authority": qualification_manifest()["authority"],
    }
    report["evidence_fingerprint"] = stable_fingerprint(
        {
            key: value
            for key, value in report.items()
            if key != "generated_utc"
        }
    )

    final_path = output_path or settings.resolved_path(
        "data/options/manifests/"
        "historical_option_reference_qualification_v1.json"
    )
    final_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        final_path,
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        fsync=True,
    )
    return report
