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
    "atlas-historical-option-reference-v2-unversioned-conflict-diagnostic-v1"
)
PARENT_V2_CONTRACT_FINGERPRINT = (
    "6d0af0b58a66b77c445d7e561d759dfd947e348e994045a1f7cfc16aeb9ccb41"
)
QUALIFICATION_EVIDENCE_FINGERPRINT = (
    "120f141089420dcfaf86e1d30203a1517f27815bf1e6b3587976ccb74f4025e3"
)
TARGET_PARTITION = "expired-2014-06"
TARGET_TICKER = "O:AAL140621C00020000"
TARGET_EXPIRATION = "2014-06-21"
CURRENT_AS_OF = "2026-09-19"
HISTORICAL_AS_OF = "2014-06-20"
REFERENCE_ENDPOINT = "/v3/reference/options/contracts"


class HistoricalOptionReferenceConflictDiagnosticError(RuntimeError):
    pass


def diagnostic_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": DIAGNOSTIC_CONTRACT,
        "parent_v2_contract_fingerprint": PARENT_V2_CONTRACT_FINGERPRINT,
        "qualification_evidence_fingerprint": QUALIFICATION_EVIDENCE_FINGERPRINT,
        "provider": "massive",
        "target": {
            "partition": TARGET_PARTITION,
            "ticker": TARGET_TICKER,
            "underlying_ticker": "AAL",
            "contract_type": "call",
            "expiration_date": TARGET_EXPIRATION,
            "strike_price": 20,
            "observed_failure": (
                "CONFLICTING_PROVIDER_ROWS_SHARE_HIGHEST_CORRECTION_RANK_MINUS_ONE"
            ),
        },
        "requests": {
            "current_structural_list": {
                "endpoint": REFERENCE_ENDPOINT,
                "filters": {
                    "underlying_ticker": "AAL",
                    "contract_type": "call",
                    "expiration_date": TARGET_EXPIRATION,
                    "strike_price": 20,
                },
                "as_of": CURRENT_AS_OF,
                "expired": True,
                "repeat": 2,
            },
            "historical_structural_list": {
                "endpoint": REFERENCE_ENDPOINT,
                "filters": {
                    "underlying_ticker": "AAL",
                    "contract_type": "call",
                    "expiration_date": TARGET_EXPIRATION,
                    "strike_price": 20,
                },
                "as_of": HISTORICAL_AS_OF,
                "expired": False,
                "repeat": 2,
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
            "ARE_STRUCTURAL_LIST_CONFLICT_ROWS_STABLE_ACROSS_REPEATS",
            "WHICH_FIELDS_DIFFER_BETWEEN_SAME_TICKER_UNVERSIONED_ROWS",
            "ARE_RELATED_ADJUSTED_SERIES_VISIBLE_FOR_THE_SAME_STRUCTURE",
            "DOES_CONTRACT_OVERVIEW_RETURN_ONE_CANONICAL_ROW",
            "DOES_CONTRACT_OVERVIEW_MATCH_ANY_TARGET_LIST_ROW_BY_CANONICAL_HASH",
            "DOES_HISTORICAL_AS_OF_CHANGE_THE_VISIBLE_STRUCTURAL_ROW_SET",
        ],
        "authority": {
            "diagnostic_only": True,
            "bulk_acquisition": False,
            "source_mutation": False,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    payload["fingerprint"] = stable_fingerprint(payload)
    return payload


HISTORICAL_OPTION_REFERENCE_V2_CONFLICT_DIAGNOSTIC_FINGERPRINT = str(
    diagnostic_manifest()["fingerprint"]
)


def _resolve_api_key(settings: AtlasSettings) -> str:
    env_name = settings.massive.credentials.api_key_env
    value = os.getenv(env_name, "").strip()
    if not value:
        raise HistoricalOptionReferenceConflictDiagnosticError(
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
            "underlying_ticker": "AAL",
            "contract_type": "call",
            "expiration_date": TARGET_EXPIRATION,
            "strike_price": 20,
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
        raise HistoricalOptionReferenceConflictDiagnosticError(
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
            raise HistoricalOptionReferenceConflictDiagnosticError(
                "contract-overview response returned multiple/non-object results"
            )
        result = result[0]
    if not isinstance(result, dict):
        raise HistoricalOptionReferenceConflictDiagnosticError(
            "contract-overview result is not an object"
        )
    ticker = str(result.get("ticker") or "")
    if ticker and ticker != TARGET_TICKER:
        raise HistoricalOptionReferenceConflictDiagnosticError(
            f"contract-overview ticker mismatch: {ticker!r}"
        )
    return dict(result)


def _row_hash(row: dict[str, Any]) -> str:
    return stable_fingerprint(row)


def _row_set_fingerprint(rows: list[dict[str, Any]]) -> str:
    return stable_fingerprint(
        sorted(
            (_row_hash(row) for row in rows),
        )
    )


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
                "candidate_row_hashes": sorted(_row_hash(row) for row in rows),
                "candidate_set_fingerprint": _row_set_fingerprint(rows),
                "candidate_rows": rows,
                "target_row_count": len(target_rows),
                "target_row_hashes": sorted(
                    _row_hash(row) for row in target_rows
                ),
                "target_row_set_fingerprint": _row_set_fingerprint(target_rows),
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
        status, payload = _request_json(settings, url=url, api_key=api_key)
        row = _extract_overview_result(payload)
        attempts.append(
            {
                "http_status": status,
                "request_id": str(payload.get("request_id") or ""),
                "safe_url": _safe_url(url),
                "row_present": row is not None,
                "row_hash": None if row is None else _row_hash(row),
                "row": row,
            }
        )
    return {
        "stable": attempts[0]["row_hash"] == attempts[1]["row_hash"],
        "attempts": attempts,
    }


def _first_list_rows(section: dict[str, object]) -> list[dict[str, Any]]:
    attempts = section["attempts"]
    if not isinstance(attempts, list) or not attempts:
        return []
    rows = attempts[0].get("target_rows")
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _first_overview_row(
    section: dict[str, object],
) -> dict[str, Any] | None:
    attempts = section["attempts"]
    if not isinstance(attempts, list) or not attempts:
        return None
    row = attempts[0].get("row")
    return dict(row) if isinstance(row, dict) else None


def run_historical_option_reference_v2_conflict_diagnostic(
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

    current_list_rows = _first_list_rows(current_list)
    historical_list_rows = _first_list_rows(historical_list)
    current_overview_row = _first_overview_row(current_overview)
    historical_overview_row = _first_overview_row(historical_overview)

    current_list_hashes = {_row_hash(row) for row in current_list_rows}
    historical_list_hashes = {_row_hash(row) for row in historical_list_rows}
    current_overview_hash = (
        None if current_overview_row is None else _row_hash(current_overview_row)
    )
    historical_overview_hash = (
        None
        if historical_overview_row is None
        else _row_hash(historical_overview_row)
    )

    interpretation = {
        "current_list_conflict_reproduced": len(current_list_hashes) > 1,
        "historical_list_conflict_reproduced": len(historical_list_hashes) > 1,
        "all_requests_repeat_stable": all(
            bool(section["stable"])
            for section in (
                current_list,
                historical_list,
                current_overview,
                historical_overview,
            )
        ),
        "current_overview_matches_current_list_row": (
            current_overview_hash in current_list_hashes
            if current_overview_hash is not None
            else False
        ),
        "historical_overview_matches_historical_list_row": (
            historical_overview_hash in historical_list_hashes
            if historical_overview_hash is not None
            else False
        ),
        "current_vs_historical_list_fingerprint_equal": (
            _row_set_fingerprint(current_list_rows)
            == _row_set_fingerprint(historical_list_rows)
        ),
        "current_vs_historical_overview_hash_equal": (
            current_overview_hash == historical_overview_hash
        ),
        "diagnostic_only_no_resolution_rule_authorized": True,
    }

    report: dict[str, object] = {
        "status": "DIAGNOSTIC_COMPLETE",
        "contract": DIAGNOSTIC_CONTRACT,
        "contract_fingerprint": (
            HISTORICAL_OPTION_REFERENCE_V2_CONFLICT_DIAGNOSTIC_FINGERPRINT
        ),
        "parent_v2_contract_fingerprint": PARENT_V2_CONTRACT_FINGERPRINT,
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
        "historical_option_reference_v2_conflict_diagnostic.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
    )
    return report
