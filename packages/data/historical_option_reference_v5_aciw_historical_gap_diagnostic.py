from __future__ import annotations

import json
import os
import urllib.parse
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.historical_option_reference_qualification import (
    _request_json,
    _safe_url,
)
from packages.data.provider_source_qualification import (
    stable_fingerprint,
    stable_json,
)


DIAGNOSTIC_CONTRACT = (
    "atlas-historical-option-reference-v5-aciw-historical-gap-diagnostic-v1"
)
PARENT_V5_CONTRACT_FINGERPRINT = (
    "4a9775c90414d8a454654d5f0928d79b68dec785b16b493e197ea34471aef1ea"
)
TARGET_PARTITION = "expired-2014-08"
TARGET_TICKER = "O:ACIW140816C00040000"
TARGET_EXPIRATION = "2014-08-16"
TARGET_CONTRACT_TYPE = "call"
TARGET_STRIKE_PRICE = 40
CURRENT_AS_OF = "2026-09-19"
REFERENCE_ENDPOINT = "/v3/reference/options/contracts"
REPEAT_COUNT = 2

# V5 failed specifically at 2014-08-15 / expired=false. The surrounding matrix is
# diagnostic-only evidence to determine whether the provider exposes a stable target
# immediately before, on, or immediately after expiration and whether expired
# filtering is part of the observed gap.
HISTORICAL_LIST_MATRIX: tuple[tuple[str, bool], ...] = (
    ("2014-08-14", False),
    ("2014-08-15", False),
    ("2014-08-15", True),
    ("2014-08-16", False),
    ("2014-08-16", True),
    ("2014-08-17", False),
    ("2014-08-17", True),
    ("2014-08-18", True),
)
HISTORICAL_OVERVIEW_DATES: tuple[str, ...] = (
    "2014-08-14",
    "2014-08-15",
    "2014-08-16",
    "2014-08-17",
    "2014-08-18",
)


class HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(RuntimeError):
    pass


def diagnostic_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": DIAGNOSTIC_CONTRACT,
        "parent_v5_contract_fingerprint": PARENT_V5_CONTRACT_FINGERPRINT,
        "provider": "massive",
        "provider_documented_semantics_as_of": "2026-09-21",
        "provider_semantics": {
            "options_all_contracts_as_of": (
                "point-in-time contract reference using YYYY-MM-DD"
            ),
            "option_contract_overview": (
                "single-contract structural reference endpoint with as_of selector"
            ),
            "adjusted_option_series": (
                "adjusted and standard series may coexist and are not merged"
            ),
        },
        "target": {
            "partition": TARGET_PARTITION,
            "ticker": TARGET_TICKER,
            "contract_type": TARGET_CONTRACT_TYPE,
            "expiration_date": TARGET_EXPIRATION,
            "strike_price": TARGET_STRIKE_PRICE,
            "observed_failure": (
                "UNVERSIONED_CONFLICT_PREEXPIRATION_STRUCTURAL_LIST_ZERO_TARGET_ROWS"
            ),
            "failed_v5_historical_as_of": "2014-08-15",
            "failed_v5_expired_filter": False,
        },
        "requests": {
            "current_structural_list": {
                "endpoint": REFERENCE_ENDPOINT,
                "as_of": CURRENT_AS_OF,
                "expired": True,
                "repeat_count": REPEAT_COUNT,
                "paginate_all_results": True,
                "underlying_filter_intentionally_omitted": True,
            },
            "historical_structural_list_matrix": [
                {
                    "as_of": as_of,
                    "expired": expired,
                    "repeat_count": REPEAT_COUNT,
                    "paginate_all_results": True,
                    "underlying_filter_intentionally_omitted": True,
                }
                for as_of, expired in HISTORICAL_LIST_MATRIX
            ],
            "contract_overview_dates": [
                {
                    "as_of": as_of,
                    "repeat_count": REPEAT_COUNT,
                }
                for as_of in (CURRENT_AS_OF,) + HISTORICAL_OVERVIEW_DATES
            ],
        },
        "diagnostic_questions": [
            "WHAT_FIELDS_DIFFER_BETWEEN_THE_CURRENT_UNVERSIONED_ROWS",
            "DOES_2014_08_15_EXPIRED_FALSE_STABLY_RETURN_ZERO_TARGET_ROWS",
            "DOES_THE_TARGET_EXIST_ON_NEIGHBORING_AS_OF_DATES",
            "DOES_EXPIRED_FILTER_CHOICE_CHANGE_TARGET_VISIBILITY",
            "DOES_EXACT_CONTRACT_OVERVIEW_EXIST_ON_ANY_NEIGHBORING_DATE",
            "DO_ANY_STABLE_HISTORICAL_LIST_AND_OVERVIEW_PAYLOADS_AGREE",
            "DOES_ANY_SUCH_PAYLOAD_MATCH_EXACTLY_ONE_CURRENT_CONFLICTING_ROW",
            "IF_NO_POINT_IN_TIME_ROW_EXISTS_SHOULD_SUCCESSOR_QUARANTINE_AMBIGUITY_INSTEAD_OF_GUESSING",
        ],
        "authority": {
            "diagnostic_only": True,
            "bulk_acquisition": False,
            "source_mutation": False,
            "conflict_resolution_rule": False,
            "quarantine_rule": False,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    payload["fingerprint"] = stable_fingerprint(payload)
    return payload


HISTORICAL_OPTION_REFERENCE_V5_ACIW_HISTORICAL_GAP_DIAGNOSTIC_FINGERPRINT = str(
    diagnostic_manifest()["fingerprint"]
)


def _resolve_api_key(settings: AtlasSettings) -> str:
    env_name = settings.massive.credentials.api_key_env
    value = os.getenv(env_name, "").strip()
    if not value:
        raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
            f"Massive API key is not configured in {env_name}"
        )
    return value


def _endpoint(settings: AtlasSettings) -> str:
    return (
        settings.massive.provider.rest_base_url.rstrip("/")
        + settings.data.research.options.reference_endpoint_path
    )


def _validate_next_url(settings: AtlasSettings, value: str) -> None:
    parsed = urllib.parse.urlsplit(value)
    base = urllib.parse.urlsplit(settings.massive.provider.rest_base_url)
    if parsed.scheme != "https" or parsed.netloc != base.netloc:
        raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
            "provider pagination next_url escaped the configured HTTPS API host"
        )


def _list_url(
    settings: AtlasSettings,
    *,
    as_of: str,
    expired: bool,
) -> str:
    query = urllib.parse.urlencode(
        {
            "contract_type": TARGET_CONTRACT_TYPE,
            "expiration_date": TARGET_EXPIRATION,
            "strike_price": TARGET_STRIKE_PRICE,
            "as_of": as_of,
            "expired": "true" if expired else "false",
            "order": "asc",
            "sort": "ticker",
            "limit": 1000,
        }
    )
    return _endpoint(settings) + "?" + query


def _overview_url(settings: AtlasSettings, *, as_of: str) -> str:
    encoded = urllib.parse.quote(TARGET_TICKER, safe="")
    query = urllib.parse.urlencode({"as_of": as_of})
    return _endpoint(settings).rstrip("/") + "/" + encoded + "?" + query


def _extract_list_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results")
    if results is None:
        return []
    if not isinstance(results, list) or any(
        not isinstance(item, dict) for item in results
    ):
        raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
            "structural-list response results is not a list of objects"
        )
    return [dict(item) for item in results]


def _extract_overview_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    result = payload.get("results")
    if result is None:
        result = payload.get("result")
    if result is None:
        return None
    if isinstance(result, list):
        if len(result) == 0:
            return None
        if len(result) != 1 or not isinstance(result[0], dict):
            raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
                "contract-overview response returned multiple/non-object results"
            )
        result = result[0]
    if not isinstance(result, dict):
        raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
            "contract-overview result is not an object"
        )
    ticker = str(result.get("ticker") or "")
    if ticker and ticker != TARGET_TICKER:
        raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
            f"contract-overview ticker mismatch: {ticker!r}"
        )
    return dict(result)


def _row_hash(row: dict[str, Any]) -> str:
    return stable_fingerprint(row)


def _row_set_fingerprint(rows: list[dict[str, Any]]) -> str:
    return stable_fingerprint(sorted(_row_hash(row) for row in rows))


def _field_differences(rows: list[dict[str, Any]]) -> dict[str, list[object]]:
    if len(rows) < 2:
        return {}
    fields = sorted({key for row in rows for key in row})
    differences: dict[str, list[object]] = {}
    for field in fields:
        encoded_to_value: dict[str, object] = {}
        for row in rows:
            value = row.get(field)
            encoded_to_value.setdefault(stable_json(value), value)
        if len(encoded_to_value) > 1:
            differences[field] = [
                encoded_to_value[key] for key in sorted(encoded_to_value)
            ]
    return differences


def _request_list_once(
    settings: AtlasSettings,
    *,
    api_key: str,
    as_of: str,
    expired: bool,
) -> dict[str, object]:
    next_url = _list_url(settings, as_of=as_of, expired=expired)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    request_ids: list[str] = []
    page_count = 0

    while next_url:
        if next_url in seen:
            raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
                "structural-list pagination loop"
            )
        seen.add(next_url)
        page_count += 1
        if page_count > 100:
            raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
                "structural-list exceeded 100-page diagnostic guard"
            )
        status, payload = _request_json(
            settings,
            url=next_url,
            api_key=api_key,
        )
        if status != 200:
            raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
                f"structural-list returned HTTP {status}"
            )
        rows.extend(_extract_list_results(payload))
        request_ids.append(str(payload.get("request_id") or ""))
        value = payload.get("next_url")
        if value in (None, ""):
            next_url = ""
        elif not isinstance(value, str):
            raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
                "structural-list next_url was not a string"
            )
        else:
            _validate_next_url(settings, value)
            next_url = value

    target_rows = [
        row
        for row in rows
        if str(row.get("ticker") or "") == TARGET_TICKER
    ]
    return {
        "as_of": as_of,
        "expired": expired,
        "candidate_row_count": len(rows),
        "candidate_set_fingerprint": _row_set_fingerprint(rows),
        "target_row_count": len(target_rows),
        "target_row_hashes": sorted(_row_hash(row) for row in target_rows),
        "target_row_set_fingerprint": _row_set_fingerprint(target_rows),
        "target_rows": target_rows,
        "page_count": page_count,
        "request_ids": request_ids,
        "safe_initial_url": _safe_url(_list_url(settings, as_of=as_of, expired=expired)),
    }


def _request_list_twice(
    settings: AtlasSettings,
    *,
    api_key: str,
    as_of: str,
    expired: bool,
) -> dict[str, object]:
    attempts = [
        _request_list_once(
            settings,
            api_key=api_key,
            as_of=as_of,
            expired=expired,
        )
        for _ in range(REPEAT_COUNT)
    ]
    first_rows = attempts[0]["target_rows"]
    return {
        "as_of": as_of,
        "expired": expired,
        "stable": (
            attempts[0]["candidate_set_fingerprint"]
            == attempts[1]["candidate_set_fingerprint"]
            and attempts[0]["target_row_set_fingerprint"]
            == attempts[1]["target_row_set_fingerprint"]
        ),
        "attempts": attempts,
        "field_differences": _field_differences(
            [dict(row) for row in first_rows if isinstance(row, dict)]
        ),
    }


def _request_overview_twice(
    settings: AtlasSettings,
    *,
    api_key: str,
    as_of: str,
) -> dict[str, object]:
    url = _overview_url(settings, as_of=as_of)
    attempts: list[dict[str, object]] = []
    for _ in range(REPEAT_COUNT):
        status, payload = _request_json(
            settings,
            url=url,
            api_key=api_key,
            accepted_http_statuses=frozenset({404}),
        )
        not_found = status == 404
        if not_found and (
            str(payload.get("status") or "") != "NOT_FOUND"
            or str(payload.get("message") or "") != "Option Ticker not found."
        ):
            raise HistoricalOptionReferenceV5AciwHistoricalGapDiagnosticError(
                "contract-overview HTTP 404 did not match provider NOT_FOUND semantics"
            )
        row = None if not_found else _extract_overview_result(payload)
        response_fingerprint = stable_fingerprint(
            {
                "http_status": status,
                "provider_status": str(payload.get("status") or ""),
                "provider_message": str(payload.get("message") or ""),
                "row_hash": None if row is None else _row_hash(row),
            }
        )
        attempts.append(
            {
                "http_status": status,
                "request_id": str(payload.get("request_id") or ""),
                "safe_url": _safe_url(url),
                "provider_status": str(payload.get("status") or ""),
                "provider_message": str(payload.get("message") or ""),
                "not_found": not_found,
                "row_present": row is not None,
                "row_hash": None if row is None else _row_hash(row),
                "row": row,
                "response_fingerprint": response_fingerprint,
            }
        )
    return {
        "as_of": as_of,
        "stable": (
            attempts[0]["response_fingerprint"]
            == attempts[1]["response_fingerprint"]
        ),
        "attempts": attempts,
    }


def _first_target_rows(section: dict[str, object]) -> list[dict[str, Any]]:
    attempts = section.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return []
    first = attempts[0]
    if not isinstance(first, dict):
        return []
    rows = first.get("target_rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _first_overview_row(section: dict[str, object]) -> dict[str, Any] | None:
    attempts = section.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        return None
    first = attempts[0]
    if not isinstance(first, dict):
        return None
    row = first.get("row")
    return dict(row) if isinstance(row, dict) else None


def run_historical_option_reference_v5_aciw_historical_gap_diagnostic(
    settings: AtlasSettings,
) -> dict[str, object]:
    api_key = _resolve_api_key(settings)

    current_list = _request_list_twice(
        settings,
        api_key=api_key,
        as_of=CURRENT_AS_OF,
        expired=True,
    )
    list_matrix: list[dict[str, object]] = []
    for as_of, expired in HISTORICAL_LIST_MATRIX:
        list_matrix.append(
            _request_list_twice(
                settings,
                api_key=api_key,
                as_of=as_of,
                expired=expired,
            )
        )

    overview_by_date: dict[str, dict[str, object]] = {}
    for as_of in (CURRENT_AS_OF,) + HISTORICAL_OVERVIEW_DATES:
        overview_by_date[as_of] = _request_overview_twice(
            settings,
            api_key=api_key,
            as_of=as_of,
        )

    current_rows = _first_target_rows(current_list)
    current_hashes = {_row_hash(row) for row in current_rows}
    current_underlyings = sorted(
        {str(row.get("underlying_ticker") or "") for row in current_rows}
    )
    current_exchanges = sorted(
        {str(row.get("primary_exchange") or "") for row in current_rows}
    )
    current_corrections = sorted(
        {stable_json(row.get("correction")) for row in current_rows}
    )

    matrix_summary: list[dict[str, object]] = []
    exact_historical_matches: list[dict[str, object]] = []
    for section in list_matrix:
        as_of = str(section["as_of"])
        expired = bool(section["expired"])
        rows = _first_target_rows(section)
        row_hashes = {_row_hash(row) for row in rows}
        overview = overview_by_date[as_of]
        overview_row = _first_overview_row(overview)
        overview_hash = None if overview_row is None else _row_hash(overview_row)
        list_overview_match = (
            overview_hash is not None
            and len(row_hashes) == 1
            and overview_hash in row_hashes
        )
        matches_current = (
            sum(
                1
                for row in current_rows
                if overview_hash is not None and _row_hash(row) == overview_hash
            )
            if list_overview_match
            else 0
        )
        item = {
            "as_of": as_of,
            "expired": expired,
            "list_stable": bool(section["stable"]),
            "target_row_count": len(rows),
            "target_row_hashes": sorted(row_hashes),
            "overview_stable": bool(overview["stable"]),
            "overview_present": overview_row is not None,
            "list_overview_exact_match": list_overview_match,
            "historical_payload_current_exact_match_count": matches_current,
        }
        matrix_summary.append(item)
        if list_overview_match and matches_current == 1:
            exact_historical_matches.append(item)

    failed_cell = next(
        item
        for item in matrix_summary
        if item["as_of"] == "2014-08-15" and item["expired"] is False
    )

    interpretation = {
        "current_list_conflict_reproduced": len(current_hashes) > 1,
        "current_target_row_count": len(current_rows),
        "current_conflicting_fields": current_list["field_differences"],
        "current_underlying_tickers": current_underlyings,
        "current_primary_exchanges": current_exchanges,
        "current_correction_values_json": current_corrections,
        "v5_preexpiration_zero_target_failure_reproduced": (
            bool(failed_cell["list_stable"])
            and int(failed_cell["target_row_count"]) == 0
        ),
        "all_list_matrix_cells_repeat_stable": all(
            bool(item["list_stable"]) for item in matrix_summary
        ),
        "all_overview_dates_repeat_stable": all(
            bool(section["stable"]) for section in overview_by_date.values()
        ),
        "historical_matrix": matrix_summary,
        "historical_exact_list_overview_current_matches": exact_historical_matches,
        "any_historical_exact_match": bool(exact_historical_matches),
        "diagnostic_only_no_resolution_or_quarantine_rule_authorized": True,
    }

    report: dict[str, object] = {
        "status": "DIAGNOSTIC_COMPLETE",
        "contract": DIAGNOSTIC_CONTRACT,
        "contract_fingerprint": (
            HISTORICAL_OPTION_REFERENCE_V5_ACIW_HISTORICAL_GAP_DIAGNOSTIC_FINGERPRINT
        ),
        "parent_v5_contract_fingerprint": PARENT_V5_CONTRACT_FINGERPRINT,
        "target_partition": TARGET_PARTITION,
        "target_ticker": TARGET_TICKER,
        "target_expiration": TARGET_EXPIRATION,
        "current_as_of": CURRENT_AS_OF,
        "current_structural_list": current_list,
        "historical_structural_list_matrix": list_matrix,
        "contract_overview_by_date": overview_by_date,
        "interpretation": interpretation,
        "authority": diagnostic_manifest()["authority"],
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)

    report_path = settings.resolved_path(
        "data/options/manifests/massive/"
        "historical_option_reference_v5_aciw_historical_gap_diagnostic.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
    )
    return report
