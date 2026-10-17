from __future__ import annotations

"""Read-only ThetaData qualification for provider-agnostic 09:35 CALL surfaces.

Only the deterministic outcome-blind anchors frozen by the zero-provider source plan
are requested. Raw response bytes and request receipts are preserved. This gate proves
transport, entitlement, schema, chronology, surface identity, and repeatability only.

It does not select an option contract, compute option returns, read exit outcomes,
create historical fills/account P&L, or grant strategy/PAPER/LIVE authority.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Sequence
from zoneinfo import ZoneInfo

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as PLAN_CONTRACT,
    EXPECTED_MAX_DTE,
    PROVIDER_CANDIDATE,
)
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING,
    TARGET_LIBRARY_VERSION,
    TRANSPORT,
    ThetaDataError,
    ThetaDataResponse,
    option_at_time_quote_surface,
)

CONTRACT = "atlas-thetadata-candidate-surface-source-qualification-v1"
OUTPUT_REL = "data/options/provider_qualification/thetadata_candidate_surface_v1"
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


class ThetaDataCandidateSurfaceQualificationError(ValueError):
    pass


def _symbol_matches_underlying(response_symbol: str, expected_symbol: str) -> bool:
    if response_symbol == expected_symbol:
        return True
    compact = response_symbol.replace(" ", "")
    if not compact.startswith(expected_symbol):
        return False
    suffix = compact[len(expected_symbol):]
    return (
        len(suffix) == 15
        and suffix[:6].isdigit()
        and suffix[6] in {"C", "P"}
        and suffix[7:].isdigit()
    )


def _validate_provider_provenance(response: ThetaDataResponse) -> None:
    if (
        response.transport != TRANSPORT
        or response.library_version != TARGET_LIBRARY_VERSION
        or not isinstance(response.provider_environment_fingerprint, str)
        or len(response.provider_environment_fingerprint) != 64
        or any(
            char not in "0123456789abcdef"
            for char in response.provider_environment_fingerprint
        )
        or response.evidence_encoding != EVIDENCE_ENCODING
    ):
        raise ThetaDataCandidateSurfaceQualificationError(
            "ThetaData provider transport/library provenance changed"
        )


def _run_root(settings: AtlasSettings, plan_fp: str, run_id: str) -> Path:
    return settings.resolved_path(f"{OUTPUT_REL}/{plan_fp[:16]}/{run_id}")


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
        raise ThetaDataCandidateSurfaceQualificationError(
            f"qualification raw path already exists: {body_path}"
        )
    body_path.write_bytes(response.raw_body)
    receipt = {
        "body_path": str(body_path),
        "body_sha256": _sha256(response.raw_body),
        "body_bytes": len(response.raw_body),
        "http_status": response.http_status,
        "elapsed_seconds": response.elapsed_seconds,
        "provider_transport": response.transport,
        "provider_library_version": response.library_version,
        "provider_environment_fingerprint": response.provider_environment_fingerprint,
        "evidence_encoding": response.evidence_encoding,
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
        raise ThetaDataCandidateSurfaceQualificationError(
            "ThetaData timestamp is not text"
        )
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThetaDataCandidateSurfaceQualificationError(
            f"ThetaData timestamp is invalid: {value}"
        ) from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        stamp = stamp.replace(tzinfo=EASTERN)
    return stamp.astimezone(EASTERN)


def _finite_number(value: object, label: str, *, nonnegative: bool = True) -> float:
    if isinstance(value, bool):
        raise ThetaDataCandidateSurfaceQualificationError(
            f"{label} cannot be boolean"
        )
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ThetaDataCandidateSurfaceQualificationError(
            f"{label} is not numeric"
        ) from exc
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ThetaDataCandidateSurfaceQualificationError(f"{label} is invalid")
    return number


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ThetaDataCandidateSurfaceQualificationError(
            f"{label} cannot be boolean"
        )
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    else:
        try:
            number = int(str(value))
        except (TypeError, ValueError) as exc:
            raise ThetaDataCandidateSurfaceQualificationError(
                f"{label} is not integer"
            ) from exc
    if number < 0:
        raise ThetaDataCandidateSurfaceQualificationError(f"{label} is negative")
    return number


def _query_day(params: dict[str, Any]) -> date:
    text = str(params["start_date"])
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    return date.fromisoformat(text)


def _query_clock(params: dict[str, Any]) -> datetime:
    day = _query_day(params)
    try:
        clock = datetime.strptime(
            str(params["time_of_day"]), "%H:%M:%S.%f"
        ).time()
    except ValueError as exc:
        raise ThetaDataCandidateSurfaceQualificationError(
            "qualification query clock invalid"
        ) from exc
    return datetime.combine(day, clock, EASTERN)


def _normalize_rows(
    rows: Sequence[dict[str, Any]],
    *,
    anchor: dict[str, Any],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    params = anchor["query"]["params"]
    expected_symbol = str(params["symbol"])
    expected_right = str(params["right"]).lower()
    requested = _query_clock(params)
    requested_day = requested.date()
    max_expiry = requested_day + timedelta(days=int(params["max_dte"]))

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, float, str]] = set()
    two_sided = 0
    eligible_dte_rows = 0
    stale_seconds: list[float] = []

    for row in rows:
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            raise ThetaDataCandidateSurfaceQualificationError(
                f"ThetaData response missing fields: {missing}"
            )
        response_symbol = str(row["symbol"])
        if not _symbol_matches_underlying(response_symbol, expected_symbol):
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData candidate-surface response changed underlying symbol"
            )
        try:
            expiration = date.fromisoformat(str(row["expiration"])[:10])
        except ValueError as exc:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData expiration is invalid"
            ) from exc
        if expiration < requested_day or expiration > max_expiry:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData surface returned expiration outside requested max_dte"
            )
        strike = _finite_number(row["strike"], "strike", nonnegative=False)
        if strike <= 0:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData strike must be positive"
            )
        right = str(row["right"]).lower()
        if right != expected_right:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData surface returned wrong option right"
            )
        identity = (expiration.isoformat(), strike, right)
        if identity in seen:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData surface contains duplicate contract identity"
            )
        seen.add(identity)

        observed = _aware_et(row["timestamp"])
        if observed.date() != requested_day:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData at-time quote date changed"
            )
        if observed > requested:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData at-time quote is after requested clock"
            )
        staleness = (requested - observed).total_seconds()
        stale_seconds.append(staleness)

        bid = _finite_number(row["bid"], "bid")
        ask = _finite_number(row["ask"], "ask")
        bid_size = _nonnegative_int(row["bid_size"], "bid_size")
        ask_size = _nonnegative_int(row["ask_size"], "ask_size")
        for field in (
            "bid_exchange",
            "bid_condition",
            "ask_exchange",
            "ask_condition",
        ):
            _nonnegative_int(row[field], field)
        if bid > 0 and ask > 0 and ask < bid:
            raise ThetaDataCandidateSurfaceQualificationError(
                "ThetaData ask is below bid"
            )
        usable = bid > 0 and ask > 0 and bid_size > 0 and ask_size > 0
        if usable:
            two_sided += 1
        dte = (expiration - requested_day).days
        if 14 <= dte <= 45:
            eligible_dte_rows += 1
        normalized.append({
            "symbol": response_symbol,
            "expiration": expiration.isoformat(),
            "strike": strike,
            "right": right,
            "timestamp_et": observed.isoformat(),
            "quote_staleness_seconds": staleness,
            "bid": bid,
            "ask": ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "two_sided_positive_displayed_size": usable,
            "dte_calendar_days": dte,
        })

    ordered = tuple(sorted(
        normalized,
        key=lambda item: (
            item["expiration"],
            float(item["strike"]),
            item["right"],
        ),
    ))
    surface_fp = _fingerprint(list(ordered))
    summary = {
        "row_count": len(ordered),
        "two_sided_positive_displayed_size_rows": two_sided,
        "phase13_dte_14_45_rows": eligible_dte_rows,
        "min_quote_staleness_seconds": min(stale_seconds) if stale_seconds else None,
        "max_quote_staleness_seconds": max(stale_seconds) if stale_seconds else None,
        "normalized_surface_fingerprint": surface_fp,
    }
    return ordered, summary


def _validate_plan(plan: dict[str, Any]) -> None:
    _check_signature(plan, "plan_fingerprint")
    qualification = plan.get("qualification")
    provider = plan.get("provider_candidate")
    scope = plan.get("target_scope")
    request_contract = plan.get("provider_request_contract")
    if (
        plan.get("contract") != PLAN_CONTRACT
        or plan.get("status") != "PLANNED_ZERO_PROVIDER_READS"
        or provider != PROVIDER_CANDIDATE
        or not isinstance(scope, dict)
        or scope.get("date_min", "")[:4] != "2021"
        or scope.get("date_max", "")[:4] != "2025"
        or scope.get("decision_clock_et") != "09:35:00.000"
        or scope.get("max_dte_calendar_days") != EXPECTED_MAX_DTE
        or not isinstance(request_contract, dict)
        or request_contract.get("expiration") != "*"
        or request_contract.get("strike") != "*"
        or request_contract.get("right") != "call"
        or request_contract.get("strike_range") is not None
        or not isinstance(qualification, dict)
        or qualification.get("outcome_blind") is not True
        or qualification.get("full_acquisition_authorized") is not False
        or not isinstance(qualification.get("anchors"), list)
        or not qualification["anchors"]
        or qualification.get("anchor_query_count") != len(qualification["anchors"])
        or plan.get("provider_requests") != 0
        or plan.get("historical_fill_authority") is not False
        or plan.get("strategy_evidence_authority") is not False
    ):
        raise ThetaDataCandidateSurfaceQualificationError(
            "ThetaData candidate-surface plan lineage/authority changed"
        )


def _probe_one(
    anchor: dict[str, Any],
    *,
    reader: Callable[..., ThetaDataResponse],
) -> tuple[dict[str, Any], ThetaDataResponse | None, tuple[dict[str, Any], ...] | None]:
    params = anchor["query"]["params"]
    try:
        response = reader(
            symbol=str(params["symbol"]),
            date_et=str(params["start_date"]),
            time_of_day_et=str(params["time_of_day"]),
            right=str(params["right"]),
            max_dte=int(params["max_dte"]),
            strike_range=params.get("strike_range"),
        )
    except ThetaDataError as exc:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "TRANSPORT_OR_ENTITLEMENT_ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "http_status": exc.http_status,
        }, None, None

    try:
        _validate_provider_provenance(response)
    except ThetaDataCandidateSurfaceQualificationError as exc:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "SURFACE_VALIDATION_ERROR",
            "http_status": response.http_status,
            "response_rows": len(response.rows),
            "error": f"{type(exc).__name__}: {exc}",
        }, response, None

    if len(response.rows) == 0:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "EXPLICIT_NO_DATA",
            "http_status": response.http_status,
            "response_rows": 0,
        }, response, ()

    try:
        normalized, summary = _normalize_rows(response.rows, anchor=anchor)
    except ThetaDataCandidateSurfaceQualificationError as exc:
        return {
            "anchor_index": anchor["anchor_index"],
            "qualification_reasons": anchor["qualification_reasons"],
            "query": anchor["query"],
            "status": "SURFACE_VALIDATION_ERROR",
            "http_status": response.http_status,
            "response_rows": len(response.rows),
            "error": f"{type(exc).__name__}: {exc}",
        }, response, None

    return {
        "anchor_index": anchor["anchor_index"],
        "qualification_reasons": anchor["qualification_reasons"],
        "query": anchor["query"],
        "status": "VALID_CANDIDATE_SURFACE",
        "http_status": response.http_status,
        "response_rows": len(response.rows),
        "surface_summary": summary,
    }, response, normalized


def run_thetadata_candidate_surface_qualification_v1(
    settings: AtlasSettings,
    plan: dict[str, Any],
    *,
    workers: int = 4,
    reader: Callable[..., ThetaDataResponse] = option_at_time_quote_surface,
) -> dict[str, Any]:
    _validate_plan(plan)
    concurrency = int(PROVIDER_CANDIDATE["documented_concurrent_requests_observed"])
    if workers < 1 or workers > concurrency:
        raise ThetaDataCandidateSurfaceQualificationError(
            "qualification workers exceed documented target-tier concurrency"
        )
    settings.assert_external_storage_binding("options")

    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _run_root(settings, plan["plan_fingerprint"], run_id)
    root.mkdir(parents=True, exist_ok=False)

    anchors = list(plan["qualification"]["anchors"])
    results: dict[int, dict[str, Any]] = {}
    normalized_by_index: dict[int, tuple[dict[str, Any], ...]] = {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_probe_one, anchor, reader=reader): anchor
            for anchor in anchors
        }
        for future in as_completed(futures):
            anchor = futures[future]
            result, response, normalized = future.result()
            index = int(anchor["anchor_index"])
            if response is not None:
                result["raw_receipt"] = _persist_raw(
                    root,
                    label=f"anchor-{index:03d}",
                    response=response,
                    query=anchor["query"],
                    plan_fingerprint=plan["plan_fingerprint"],
                )
            if normalized is not None:
                normalized_by_index[index] = normalized
            results[index] = result

    ordered = [results[index] for index in sorted(results)]
    hard_bad = {"TRANSPORT_OR_ENTITLEMENT_ERROR", "SURFACE_VALIDATION_ERROR"}
    hard_errors = [item for item in ordered if item["status"] in hard_bad]

    coverage: dict[str, int] = {str(year): 0 for year in range(2021, 2026)}
    usable_rows: dict[str, int] = {str(year): 0 for year in range(2021, 2026)}
    for item in ordered:
        if item["status"] != "VALID_CANDIDATE_SURFACE":
            continue
        year = str(item["query"]["params"]["start_date"])[:4]
        if year in coverage:
            coverage[year] += 1
            usable_rows[year] += int(
                item["surface_summary"]["two_sided_positive_displayed_size_rows"]
            )

    full_year_coverage = all(value > 0 for value in coverage.values())
    oldest_2021_proven = coverage["2021"] > 0

    repeat_source = next(
        (
            item for item in ordered
            if item["status"] == "VALID_CANDIDATE_SURFACE"
            and str(item["query"]["params"]["start_date"]).startswith("2021")
        ),
        None,
    )
    provider_requests = len(anchors)
    if repeat_source is None:
        repeat_result: dict[str, Any] = {
            "status": "NOT_RUN_NO_VALID_2021_SURFACE",
            "deterministic_normalized_surface": False,
        }
    else:
        anchor = next(
            item for item in anchors
            if int(item["anchor_index"]) == int(repeat_source["anchor_index"])
        )
        second, response, normalized = _probe_one(anchor, reader=reader)
        provider_requests += 1
        if response is not None:
            second["raw_receipt"] = _persist_raw(
                root,
                label=f"repeat-anchor-{int(anchor['anchor_index']):03d}",
                response=response,
                query=anchor["query"],
                plan_fingerprint=plan["plan_fingerprint"],
            )
        first_normalized = normalized_by_index.get(int(anchor["anchor_index"]))
        deterministic = (
            second.get("status") == "VALID_CANDIDATE_SURFACE"
            and normalized is not None
            and first_normalized == normalized
        )
        repeat_result = {
            "status": second.get("status"),
            "anchor_index": anchor["anchor_index"],
            "deterministic_normalized_surface": deterministic,
            "first_surface_fingerprint": repeat_source.get(
                "surface_summary", {}
            ).get("normalized_surface_fingerprint"),
            "second_surface_fingerprint": second.get(
                "surface_summary", {}
            ).get("normalized_surface_fingerprint"),
            "second_result": second,
        }

    qualified = (
        not hard_errors
        and oldest_2021_proven
        and full_year_coverage
        and bool(repeat_result.get("deterministic_normalized_surface"))
    )

    report = {
        "contract": CONTRACT,
        "status": (
            "QUALIFIED_FOR_BOUNDED_CANDIDATE_SURFACE_ACQUISITION"
            if qualified
            else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
        ),
        "plan_fingerprint": plan["plan_fingerprint"],
        "decision_spot_fingerprint": plan["decision_spot_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "generated_at_utc": generated.isoformat(),
        "run_id": run_id,
        "qualification_anchor_count": len(anchors),
        "provider_requests": provider_requests,
        "provider_writes": 0,
        "anchors": ordered,
        "status_counts": dict(
            sorted(Counter(item["status"] for item in ordered).items())
        ),
        "valid_surface_coverage_by_year": coverage,
        "two_sided_rows_by_year": usable_rows,
        "oldest_2021_surface_proven": oldest_2021_proven,
        "full_2021_2025_surface_coverage_proven": full_year_coverage,
        "repeatability_probe": repeat_result,
        "hard_validation_or_transport_errors": len(hard_errors),
        "full_acquisition_source_qualified": qualified,
        "single_contract_selected": False,
        "option_exit_prices_read": 0,
        "historical_fill_authority": False,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "raw_root": str(root),
        "report_path": str(root / "qualification.json"),
    }
    report["qualification_fingerprint"] = _fingerprint(report)
    atomic_write_text(
        root / "qualification.json",
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    return report
