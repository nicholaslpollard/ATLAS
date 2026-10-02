from __future__ import annotations

"""Read-only ThetaData qualification against the exact intraday option clock plan.

This gate is intentionally small. It reads only the outcome-blind qualification
anchors frozen by the zero-provider plan, persists raw response bytes and receipts,
and checks entitlement/schema/chronology before full acquisition can be authorized.

It does not compute option returns, historical fills, account P&L, strategy evidence,
PAPER, or LIVE decisions.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_intraday_option_plan_v1 import (
    CONTRACT as PLAN_CONTRACT,
    PROVIDER_CANDIDATE,
)
from packages.providers.thetadata.client import (
    ThetaDataError,
    ThetaDataResponse,
    option_at_time_quote,
)

CONTRACT = "atlas-thetadata-intraday-option-source-qualification-v1"
OUTPUT_REL = "data/options/provider_qualification/thetadata_intraday_v1"
EASTERN = ZoneInfo("America/New_York")
REQUIRED_FIELDS = (
    "symbol",
    "expiration",
    "strike",
    "right",
    "timestamp",
    "bid_size",
    "bid_exchange",
    "bid",
    "bid_condition",
    "ask_size",
    "ask_exchange",
    "ask",
    "ask_condition",
)


class ThetaDataIntradayQualificationError(ValueError):
    pass


def _run_root(settings: AtlasSettings, plan_fp: str, run_id: str) -> Path:
    return settings.resolved_path(
        f"{OUTPUT_REL}/{plan_fp[:16]}/{run_id}"
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _persist_raw(
    root: Path,
    *,
    label: str,
    response: ThetaDataResponse,
    query: dict[str, Any],
    plan_fingerprint: str,
) -> dict[str, Any]:
    raw_dir = root / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    body_path = raw_dir / f"{label}.json"
    if body_path.exists() or body_path.is_symlink():
        raise ThetaDataIntradayQualificationError(
            f"qualification raw path already exists: {body_path}"
        )
    body_path.write_bytes(response.raw_body)
    receipt = {
        "body_path": str(body_path),
        "body_sha256": _sha256(response.raw_body),
        "body_bytes": len(response.raw_body),
        "http_status": response.http_status,
        "elapsed_seconds": response.elapsed_seconds,
        "query": query,
        "plan_fingerprint": plan_fingerprint,
    }
    receipt_path = raw_dir / f"{label}.receipt.json"
    atomic_write_text(
        receipt_path,
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _aware_et(value: object) -> datetime:
    if not isinstance(value, str):
        raise ThetaDataIntradayQualificationError("ThetaData timestamp is not text")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThetaDataIntradayQualificationError(
            f"ThetaData timestamp is invalid: {value}"
        ) from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        stamp = stamp.replace(tzinfo=EASTERN)
    return stamp.astimezone(EASTERN)


def _finite_number(value: object, label: str, *, nonnegative: bool = True) -> float:
    if isinstance(value, bool):
        raise ThetaDataIntradayQualificationError(f"{label} cannot be boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ThetaDataIntradayQualificationError(f"{label} is not numeric") from exc
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ThetaDataIntradayQualificationError(f"{label} is invalid")
    return number


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ThetaDataIntradayQualificationError(f"{label} cannot be boolean")
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    else:
        try:
            number = int(str(value))
        except (TypeError, ValueError) as exc:
            raise ThetaDataIntradayQualificationError(f"{label} is not integer") from exc
    if number < 0:
        raise ThetaDataIntradayQualificationError(f"{label} is negative")
    return number


def _query_clock(params: dict[str, Any]) -> datetime:
    day_text = str(params["start_date"])
    if len(day_text) == 8 and day_text.isdigit():
        day = date(int(day_text[:4]), int(day_text[4:6]), int(day_text[6:]))
    else:
        day = date.fromisoformat(day_text)
    try:
        clock = datetime.strptime(str(params["time_of_day"]), "%H:%M:%S.%f").time()
    except ValueError as exc:
        raise ThetaDataIntradayQualificationError("qualification query clock invalid") from exc
    return datetime.combine(day, clock, EASTERN)


def _validate_row(
    row: dict[str, Any],
    *,
    anchor: dict[str, Any],
) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in row]
    if missing:
        raise ThetaDataIntradayQualificationError(
            f"ThetaData response missing fields: {missing}"
        )
    query = anchor["query"]["params"]
    root = str(query["symbol"])
    expected_option_symbol = str(anchor["option_symbol"])
    response_symbol = str(row["symbol"])
    if response_symbol not in {root, expected_option_symbol}:
        raise ThetaDataIntradayQualificationError(
            "ThetaData response symbol does not match requested underlying/contract"
        )

    response_expiry = date.fromisoformat(str(row["expiration"])[:10])
    query_expiry_text = str(query["expiration"])
    query_expiry = (
        date(int(query_expiry_text[:4]), int(query_expiry_text[4:6]), int(query_expiry_text[6:]))
        if len(query_expiry_text) == 8 and query_expiry_text.isdigit()
        else date.fromisoformat(query_expiry_text)
    )
    if response_expiry != query_expiry:
        raise ThetaDataIntradayQualificationError("ThetaData expiration changed")

    response_strike = _finite_number(row["strike"], "strike", nonnegative=False)
    expected_strike = _finite_number(query["strike"], "query strike", nonnegative=False)
    if response_strike <= 0 or expected_strike <= 0 or not math.isclose(
        response_strike, expected_strike, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ThetaDataIntradayQualificationError("ThetaData strike changed")
    if str(row["right"]).lower() != str(query["right"]).lower():
        raise ThetaDataIntradayQualificationError("ThetaData option right changed")

    requested = _query_clock(query)
    observed = _aware_et(row["timestamp"])
    if observed.date() != requested.date():
        raise ThetaDataIntradayQualificationError("ThetaData at-time date changed")
    if observed > requested:
        raise ThetaDataIntradayQualificationError(
            "ThetaData at-time quote is after requested clock"
        )
    staleness_seconds = (requested - observed).total_seconds()

    bid = _finite_number(row["bid"], "bid")
    ask = _finite_number(row["ask"], "ask")
    bid_size = _nonnegative_int(row["bid_size"], "bid_size")
    ask_size = _nonnegative_int(row["ask_size"], "ask_size")
    for field in ("bid_exchange", "bid_condition", "ask_exchange", "ask_condition"):
        _nonnegative_int(row[field], field)
    if bid > 0 and ask > 0 and ask < bid:
        raise ThetaDataIntradayQualificationError("ThetaData ask is below bid")

    usable = bid > 0 and ask > 0 and ask >= bid and bid_size > 0 and ask_size > 0
    return {
        "symbol": response_symbol,
        "expiration": response_expiry.isoformat(),
        "strike": response_strike,
        "right": str(row["right"]).lower(),
        "timestamp_et": observed.isoformat(),
        "requested_at_et": requested.isoformat(),
        "quote_staleness_seconds": staleness_seconds,
        "bid": bid,
        "ask": ask,
        "bid_size": bid_size,
        "ask_size": ask_size,
        "two_sided_positive_displayed_size": usable,
    }


def _validate_plan(plan: dict[str, Any]) -> None:
    _check_signature(plan, "plan_fingerprint")
    qualification = plan.get("qualification")
    provider = plan.get("provider_candidate")
    scope = plan.get("target_scope")
    if (
        plan.get("contract") != PLAN_CONTRACT
        or plan.get("status") != "PLANNED_ZERO_PROVIDER_READS"
        or provider != PROVIDER_CANDIDATE
        or not isinstance(qualification, dict)
        or qualification.get("outcome_blind") is not True
        or qualification.get("full_acquisition_authorized") is not False
        or not isinstance(qualification.get("anchors"), list)
        or not qualification["anchors"]
        or qualification.get("anchor_query_count") != len(qualification["anchors"])
        or not isinstance(scope, dict)
        or scope.get("date_min", "")[:4] != "2021"
        or scope.get("date_max", "")[:4] != "2025"
        or plan.get("provider_requests") != 0
        or plan.get("historical_fill_authority") is not False
        or plan.get("strategy_evidence_authority") is not False
    ):
        raise ThetaDataIntradayQualificationError(
            "ThetaData intraday source plan lineage/authority changed"
        )


def _probe_one(
    anchor: dict[str, Any],
    *,
    reader: Callable[..., ThetaDataResponse],
) -> tuple[dict[str, Any], ThetaDataResponse | None]:
    params = anchor["query"]["params"]
    try:
        response = reader(
            symbol=str(params["symbol"]),
            expiration=str(params["expiration"]),
            strike=str(params["strike"]),
            right=str(params["right"]),
            date_et=str(params["start_date"]),
            time_of_day_et=str(params["time_of_day"]),
        )
    except ThetaDataError as exc:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "TRANSPORT_OR_ENTITLEMENT_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }, None

    if len(response.rows) == 0:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "EXPLICIT_NO_QUOTE_AT_TIME",
            "http_status": response.http_status,
            "response_rows": 0,
        }, response
    if len(response.rows) != 1:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "AMBIGUOUS_MULTIPLE_ROWS",
            "http_status": response.http_status,
            "response_rows": len(response.rows),
            "error": "specific contract/date/time request returned multiple rows",
        }, response
    try:
        normalized = _validate_row(response.rows[0], anchor=anchor)
    except ThetaDataIntradayQualificationError as exc:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "ROW_VALIDATION_ERROR",
            "http_status": response.http_status,
            "response_rows": 1,
            "error": f"{type(exc).__name__}: {exc}",
        }, response
    return {
        "anchor_index": anchor["anchor_index"],
        "qualification_reasons": anchor["qualification_reasons"],
        "query": anchor["query"],
        "status": (
            "VALID_USABLE_NBBO"
            if normalized["two_sided_positive_displayed_size"]
            else "VALID_NONUSABLE_OR_ONE_SIDED_QUOTE"
        ),
        "http_status": response.http_status,
        "response_rows": 1,
        "normalized_row": normalized,
    }, response


def run_thetadata_intraday_option_qualification_v1(
    settings: AtlasSettings,
    plan: dict[str, Any],
    *,
    workers: int = 4,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote,
) -> dict[str, Any]:
    _validate_plan(plan)
    if workers < 1 or workers > int(PROVIDER_CANDIDATE["documented_concurrent_requests_observed"]):
        raise ThetaDataIntradayQualificationError(
            "qualification workers exceed documented target-tier concurrency"
        )
    settings.assert_external_storage_binding("options")
    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _run_root(settings, plan["plan_fingerprint"], run_id)
    root.mkdir(parents=True, exist_ok=False)

    anchors = list(plan["qualification"]["anchors"])
    results: dict[int, dict[str, Any]] = {}
    responses: dict[int, ThetaDataResponse] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_probe_one, anchor, reader=reader): anchor
            for anchor in anchors
        }
        for future in as_completed(futures):
            anchor = futures[future]
            result, response = future.result()
            index = int(anchor["anchor_index"])
            if response is not None:
                receipt = _persist_raw(
                    root,
                    label=f"anchor-{index:03d}",
                    response=response,
                    query=anchor["query"],
                    plan_fingerprint=plan["plan_fingerprint"],
                )
                result["raw_receipt"] = receipt
                responses[index] = response
            results[index] = result

    ordered = [results[index] for index in sorted(results)]
    hard_bad = {
        "TRANSPORT_OR_ENTITLEMENT_ERROR",
        "AMBIGUOUS_MULTIPLE_ROWS",
        "ROW_VALIDATION_ERROR",
    }
    hard_errors = [item for item in ordered if item["status"] in hard_bad]

    coverage: dict[str, dict[str, int]] = {
        str(year): {"ENTRY": 0, "EXIT": 0} for year in range(2021, 2026)
    }
    for item in ordered:
        if item["status"] != "VALID_USABLE_NBBO":
            continue
        params = item["query"]["params"]
        year = str(params["start_date"])[:4]
        for role in item["query"]["expected_role"]:
            if year in coverage and role in coverage[year]:
                coverage[year][role] += 1

    full_year_role_coverage = all(
        values["ENTRY"] > 0 and values["EXIT"] > 0
        for values in coverage.values()
    )
    oldest_2021_proven = (
        coverage["2021"]["ENTRY"] > 0 and coverage["2021"]["EXIT"] > 0
    )

    # Repeat one usable 2021 anchor after the concurrent probe to test historical
    # determinism without choosing based on option return or spread magnitude.
    repeat_source: dict[str, Any] | None = next(
        (
            item
            for item in ordered
            if item["status"] == "VALID_USABLE_NBBO"
            and str(item["query"]["params"]["start_date"]).startswith("2021")
        ),
        None,
    )
    repeat_result: dict[str, Any]
    provider_requests = len(anchors)
    if repeat_source is None:
        repeat_result = {
            "status": "NOT_RUN_NO_USABLE_2021_ANCHOR",
            "deterministic_normalized_row": False,
        }
    else:
        anchor = next(
            item for item in anchors
            if item["anchor_index"] == repeat_source["anchor_index"]
        )
        second, response = _probe_one(anchor, reader=reader)
        provider_requests += 1
        if response is not None:
            receipt = _persist_raw(
                root,
                label=f"repeat-anchor-{int(anchor['anchor_index']):03d}",
                response=response,
                query=anchor["query"],
                plan_fingerprint=plan["plan_fingerprint"],
            )
            second["raw_receipt"] = receipt
        deterministic = (
            second.get("status") == repeat_source.get("status")
            and second.get("normalized_row") == repeat_source.get("normalized_row")
        )
        repeat_result = {
            "status": second.get("status"),
            "anchor_index": anchor["anchor_index"],
            "deterministic_normalized_row": deterministic,
            "second_result": second,
        }

    qualified = (
        not hard_errors
        and oldest_2021_proven
        and full_year_role_coverage
        and bool(repeat_result.get("deterministic_normalized_row"))
    )
    report = {
        "contract": CONTRACT,
        "status": (
            "QUALIFIED_FOR_BOUNDED_INTRADAY_OPTION_ACQUISITION"
            if qualified
            else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
        ),
        "plan_fingerprint": plan["plan_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "generated_at_utc": generated.isoformat(),
        "run_id": run_id,
        "qualification_anchor_count": len(anchors),
        "provider_requests": provider_requests,
        "provider_writes": 0,
        "anchors": ordered,
        "status_counts": dict(
            sorted(
                __import__("collections").Counter(
                    item["status"] for item in ordered
                ).items()
            )
        ),
        "usable_year_role_coverage": coverage,
        "oldest_2021_entry_and_exit_proven": oldest_2021_proven,
        "full_2021_2025_entry_exit_coverage_proven": full_year_role_coverage,
        "repeatability_probe": repeat_result,
        "hard_validation_or_transport_errors": len(hard_errors),
        "full_acquisition_source_qualified": qualified,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "raw_root": str(root),
    }
    report["qualification_fingerprint"] = _fingerprint(report)
    report_path = root / "qualification.json"
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    report["report_path"] = str(report_path)
    return report
