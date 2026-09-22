from __future__ import annotations

import json
import os
import urllib.parse
from pathlib import Path
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
    "atlas-historical-option-reference-v4-explicit-correction-conflict-diagnostic-v1"
)
PARENT_V4_CONTRACT_FINGERPRINT = (
    "2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d"
)
TARGET_PARTITION = "expired-2014-07"
TARGET_TICKER = "O:ACT2140719C00045000"
TARGET_EXPIRATION = "2014-07-19"
TARGET_CONTRACT_TYPE = "call"
TARGET_STRIKE_PRICE = 45
CURRENT_AS_OF = "2026-09-19"
HISTORICAL_AS_OF = "2014-07-18"
REFERENCE_ENDPOINT = "/v3/reference/options/contracts"


class HistoricalOptionReferenceV4CorrectionConflictDiagnosticError(RuntimeError):
    pass


def diagnostic_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": DIAGNOSTIC_CONTRACT,
        "parent_v4_contract_fingerprint": PARENT_V4_CONTRACT_FINGERPRINT,
        "provider": "massive",
        "provider_documented_semantics_as_of": "2026-09-21",
        "provider_semantics": {
            "options_all_contracts_as_of": (
                "point-in-time contract reference using YYYY-MM-DD"
            ),
            "options_correction": (
                "provider correction number for an option contract"
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
                "EXPLICIT_SAME_HIGHEST_CORRECTION_CONFLICT_REJECTED_BY_V4_"
                "UNVERSIONED_ONLY_FALLBACK"
            ),
        },
        "requests": {
            "current_structural_list": {
                "endpoint": REFERENCE_ENDPOINT,
                "filters": {
                    "contract_type": TARGET_CONTRACT_TYPE,
                    "expiration_date": TARGET_EXPIRATION,
                    "strike_price": TARGET_STRIKE_PRICE,
                },
                "as_of": CURRENT_AS_OF,
                "expired": True,
                "repeat": 2,
                "underlying_filter_intentionally_omitted": True,
            },
            "historical_structural_list": {
                "endpoint": REFERENCE_ENDPOINT,
                "filters": {
                    "contract_type": TARGET_CONTRACT_TYPE,
                    "expiration_date": TARGET_EXPIRATION,
                    "strike_price": TARGET_STRIKE_PRICE,
                },
                "as_of": HISTORICAL_AS_OF,
                "expired": False,
                "repeat": 2,
                "underlying_filter_intentionally_omitted": True,
            },
            "current_contract_overview": {
                "endpoint": REFERENCE_ENDPOINT + "/{options_ticker}",
                "ticker": TARGET_TICKER,
                "as_of": CURRENT_AS_OF,
                "repeat": 2,
            },
            "historical_contract_overview": {
                "endpoint": REFERENCE_ENDPOINT + "/{options_ticker}",
                "ticker": TARGET_TICKER,
                "as_of": HISTORICAL_AS_OF,
                "repeat": 2,
            },
        },
        "diagnostic_questions": [
            "WHICH_EXPLICIT_CORRECTION_VALUES_APPEAR_ON_CURRENT_CONFLICTING_ROWS",
            "WHICH_FIELDS_DIFFER_BETWEEN_ROWS_SHARING_THE_HIGHEST_EXPLICIT_CORRECTION",
            "IS_THE_CURRENT_CONFLICT_STABLE_ACROSS_REPEATS",
            "DOES_THE_PREEXPIRATION_VIEW_RETURN_EXACTLY_ONE_TARGET_ROW",
            "DOES_PREEXPIRATION_CONTRACT_OVERVIEW_MATCH_THE_PREEXPIRATION_LIST_ROW",
            "DOES_THAT_HISTORICAL_PAYLOAD_MATCH_EXACTLY_ONE_CURRENT_CONFLICTING_ROW",
            "IS_ANY_SUCCESSOR_RULE_NARROW_ENOUGH_TO_REMAIN_FAIL_CLOSED",
        ],
        "authority": {
            "diagnostic_only": True,
            "bulk_acquisition": False,
            "source_mutation": False,
            "conflict_resolution_rule": False,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    payload["fingerprint"] = stable_fingerprint(payload)
    return payload


HISTORICAL_OPTION_REFERENCE_V4_CORRECTION_CONFLICT_DIAGNOSTIC_FINGERPRINT = str(
    diagnostic_manifest()["fingerprint"]
)


def _resolve_api_key(settings: AtlasSettings) -> str:
    env_name = settings.massive.credentials.api_key_env
    value = os.getenv(env_name, "").strip()
    if not value:
        raise HistoricalOptionReferenceV4CorrectionConflictDiagnosticError(
            f"Massive API key is not configured in {env_name}"
        )
    return value


def _endpoint(settings: AtlasSettings) -> str:
    return (
        settings.massive.provider.rest_base_url.rstrip("/")
        + settings.data.research.options.reference_endpoint_path
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
        raise HistoricalOptionReferenceV4CorrectionConflictDiagnosticError(
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
            raise HistoricalOptionReferenceV4CorrectionConflictDiagnosticError(
                "contract-overview response returned multiple/non-object results"
            )
        result = result[0]
    if not isinstance(result, dict):
        raise HistoricalOptionReferenceV4CorrectionConflictDiagnosticError(
            "contract-overview result is not an object"
        )
    ticker = str(result.get("ticker") or "")
    if ticker and ticker != TARGET_TICKER:
        raise HistoricalOptionReferenceV4CorrectionConflictDiagnosticError(
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


def _correction_values(rows: list[dict[str, Any]]) -> list[object]:
    encoded_to_value: dict[str, object] = {}
    for row in rows:
        value = row.get("correction")
        encoded_to_value.setdefault(stable_json(value), value)
    return [encoded_to_value[key] for key in sorted(encoded_to_value)]


def _request_list_twice(
    settings: AtlasSettings,
    *,
    api_key: str,
    as_of: str,
    expired: bool,
) -> dict[str, object]:
    url = _list_url(settings, as_of=as_of, expired=expired)
    attempts: list[dict[str, object]] = []
    for _ in range(2):
        status, payload = _request_json(settings, url=url, api_key=api_key)
        rows = _extract_list_results(payload)
        target_rows = [
            row
            for row in rows
            if str(row.get("ticker") or "") == TARGET_TICKER
        ]
        attempts.append(
            {
                "http_status": status,
                "request_id": str(payload.get("request_id") or ""),
                "safe_url": _safe_url(url),
                "candidate_row_count": len(rows),
                "candidate_tickers": sorted(
                    {
                        str(row.get("ticker") or "")
                        for row in rows
                        if str(row.get("ticker") or "")
                    }
                ),
                "candidate_set_fingerprint": _row_set_fingerprint(rows),
                "target_row_count": len(target_rows),
                "target_row_hashes": sorted(_row_hash(row) for row in target_rows),
                "target_row_set_fingerprint": _row_set_fingerprint(target_rows),
                "target_correction_values": _correction_values(target_rows),
                "target_correction_present_count": sum(
                    1 for row in target_rows if row.get("correction") is not None
                ),
                "target_rows": target_rows,
                "next_url_present": bool(payload.get("next_url")),
            }
        )
    return {
        "stable": (
            attempts[0]["candidate_set_fingerprint"]
            == attempts[1]["candidate_set_fingerprint"]
            and attempts[0]["target_row_set_fingerprint"]
            == attempts[1]["target_row_set_fingerprint"]
        ),
        "attempts": attempts,
        "field_differences": _field_differences(
            list(attempts[0]["target_rows"])  # type: ignore[arg-type]
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
    for _ in range(2):
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
            raise HistoricalOptionReferenceV4CorrectionConflictDiagnosticError(
                "contract-overview HTTP 404 did not match the frozen "
                "provider NOT_FOUND semantics"
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


def run_historical_option_reference_v4_correction_conflict_diagnostic(
    settings: AtlasSettings,
) -> dict[str, object]:
    api_key = _resolve_api_key(settings)

    current_list = _request_list_twice(
        settings,
        api_key=api_key,
        as_of=CURRENT_AS_OF,
        expired=True,
    )
    historical_list = _request_list_twice(
        settings,
        api_key=api_key,
        as_of=HISTORICAL_AS_OF,
        expired=False,
    )
    current_overview = _request_overview_twice(
        settings,
        api_key=api_key,
        as_of=CURRENT_AS_OF,
    )
    historical_overview = _request_overview_twice(
        settings,
        api_key=api_key,
        as_of=HISTORICAL_AS_OF,
    )

    current_rows = _first_target_rows(current_list)
    historical_rows = _first_target_rows(historical_list)
    current_overview_row = _first_overview_row(current_overview)
    historical_overview_row = _first_overview_row(historical_overview)

    current_hashes = {_row_hash(row) for row in current_rows}
    historical_hashes = {_row_hash(row) for row in historical_rows}
    current_overview_hash = (
        None
        if current_overview_row is None
        else _row_hash(current_overview_row)
    )
    historical_overview_hash = (
        None
        if historical_overview_row is None
        else _row_hash(historical_overview_row)
    )

    current_corrections = _correction_values(current_rows)
    historical_corrections = _correction_values(historical_rows)

    interpretation = {
        "current_list_conflict_reproduced": len(current_hashes) > 1,
        "current_target_correction_values": current_corrections,
        "historical_target_correction_values": historical_corrections,
        "all_current_target_rows_have_explicit_correction": (
            bool(current_rows)
            and all(row.get("correction") is not None for row in current_rows)
        ),
        "current_target_rows_share_one_correction_value": (
            bool(current_rows) and len(current_corrections) == 1
        ),
        "current_conflicting_fields": current_list["field_differences"],
        "historical_list_target_row_count": len(historical_rows),
        "option_requests_repeat_stable": all(
            bool(section["stable"])
            for section in (
                current_list,
                historical_list,
                current_overview,
                historical_overview,
            )
        ),
        "historical_overview_matches_historical_list_row": (
            historical_overview_hash in historical_hashes
            if historical_overview_hash is not None
            else False
        ),
        "historical_overview_matches_exactly_one_current_row": (
            sum(
                1
                for row in current_rows
                if historical_overview_hash is not None
                and _row_hash(row) == historical_overview_hash
            )
            == 1
        ),
        "current_overview_matches_current_list_row": (
            current_overview_hash in current_hashes
            if current_overview_hash is not None
            else False
        ),
        "diagnostic_only_no_resolution_rule_authorized": True,
    }

    report: dict[str, object] = {
        "status": "DIAGNOSTIC_COMPLETE",
        "contract": DIAGNOSTIC_CONTRACT,
        "contract_fingerprint": (
            HISTORICAL_OPTION_REFERENCE_V4_CORRECTION_CONFLICT_DIAGNOSTIC_FINGERPRINT
        ),
        "parent_v4_contract_fingerprint": PARENT_V4_CONTRACT_FINGERPRINT,
        "target_partition": TARGET_PARTITION,
        "target_ticker": TARGET_TICKER,
        "target_expiration": TARGET_EXPIRATION,
        "current_as_of": CURRENT_AS_OF,
        "historical_as_of": HISTORICAL_AS_OF,
        "current_structural_list": current_list,
        "historical_structural_list": historical_list,
        "current_contract_overview": current_overview,
        "historical_contract_overview": historical_overview,
        "interpretation": interpretation,
        "authority": diagnostic_manifest()["authority"],
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)

    report_path = settings.resolved_path(
        "data/options/manifests/massive/"
        "historical_option_reference_v4_correction_conflict_diagnostic.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
    )
    return report
