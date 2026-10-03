from __future__ import annotations

"""Read-only qualification for ThetaData historical option open-interest surfaces.

The quote source must already be qualified for the same frozen source plan. This gate
then probes only the deterministic open-interest anchors derived from those quote
anchors, persists raw source bytes/receipts, verifies causal timestamp and contract
identity, and repeats a 2021 surface for historical determinism.

No contract selection, Greeks, exit quote, return, P&L, strategy, PAPER or LIVE
authority is created.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
    EXPECTED_MAX_DTE,
    PROVIDER_CANDIDATE,
)
from packages.data.thetadata_candidate_surface_qualification_v1 import (
    CONTRACT as QUOTE_QUALIFICATION_CONTRACT,
    _aware_et,
    _finite_number,
    _nonnegative_int,
    _symbol_matches_underlying,
)
from packages.providers.thetadata.client import (
    ThetaDataError,
    ThetaDataResponse,
    option_history_open_interest_surface,
)

CONTRACT = "atlas-thetadata-open-interest-surface-qualification-v1"
OUTPUT_REL = "data/options/provider_qualification/thetadata_open_interest_surface_v1"
DECISION_CLOCK_ET = "09:35:00.000"
MAX_WORKERS = 4
EXPECTED_QUALIFICATION_ANCHORS = 15


class ThetaDataOpenInterestQualificationError(ValueError):
    pass


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _run_root(settings: AtlasSettings, plan_fp: str, run_id: str) -> Path:
    return settings.resolved_path(f"{OUTPUT_REL}/{plan_fp[:16]}/{run_id}")


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
    receipt_path = raw_dir / f"{label}.receipt.json"
    if body_path.exists() or receipt_path.exists() or body_path.is_symlink() or receipt_path.is_symlink():
        raise ThetaDataOpenInterestQualificationError(
            f"qualification evidence path already exists: {body_path}"
        )
    body_path.write_bytes(response.raw_body)
    receipt = {
        "body_path": str(body_path),
        "body_sha256": _sha256(response.raw_body),
        "body_bytes": len(response.raw_body),
        "http_status": response.http_status,
        "elapsed_seconds": response.elapsed_seconds,
        "query": query,
        "enrichment_plan_fingerprint": plan_fingerprint,
    }
    atomic_write_text(
        receipt_path,
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    receipt["receipt_path"] = str(receipt_path)
    return receipt


def _query_day(params: dict[str, Any]) -> date:
    text = str(params["date"])
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    return date.fromisoformat(text)


def _normalize_rows(
    rows: tuple[dict[str, Any], ...],
    *,
    anchor: dict[str, Any],
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    params = anchor["query"]["params"]
    expected_symbol = str(params["symbol"])
    requested_day = _query_day(params)
    max_expiry = requested_day + timedelta(days=int(params["max_dte"]))
    decision_clock = datetime.combine(
        requested_day,
        datetime.strptime(DECISION_CLOCK_ET, "%H:%M:%S.%f").time(),
        _aware_et(f"{requested_day.isoformat()}T{DECISION_CLOCK_ET}").tzinfo,
    )

    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, float, str]] = set()
    phase13_rows = 0
    positive_rows = 0
    timestamps: list[str] = []

    for row in rows:
        required = {
            "symbol", "expiration", "strike", "right", "timestamp", "open_interest",
        }
        missing = sorted(required.difference(row))
        if missing:
            raise ThetaDataOpenInterestQualificationError(
                f"ThetaData OI response missing fields: {missing}"
            )
        response_symbol = str(row["symbol"])
        if not _symbol_matches_underlying(response_symbol, expected_symbol):
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI response changed underlying symbol"
            )
        try:
            expiry = date.fromisoformat(str(row["expiration"])[:10])
        except ValueError as exc:
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI expiration invalid"
            ) from exc
        if expiry < requested_day or expiry > max_expiry:
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI expiration outside requested max_dte"
            )
        strike = _finite_number(row["strike"], "strike", nonnegative=False)
        if strike <= 0:
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI strike must be positive"
            )
        right = str(row["right"]).lower()
        if right != "call":
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI returned wrong option right"
            )
        identity = (expiry.isoformat(), strike, right)
        if identity in seen:
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI contains duplicate contract identity"
            )
        seen.add(identity)

        observed = _aware_et(row["timestamp"])
        if observed.date() != requested_day:
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI report date changed"
            )
        if observed > decision_clock:
            raise ThetaDataOpenInterestQualificationError(
                "ThetaData OI timestamp is after 09:35 decision clock"
            )
        oi = _nonnegative_int(row["open_interest"], "open_interest")
        if oi > 0:
            positive_rows += 1
        if oi >= 100:
            phase13_rows += 1
        timestamps.append(observed.isoformat())
        normalized.append({
            "symbol": response_symbol,
            "expiration": expiry.isoformat(),
            "strike": strike,
            "right": right,
            "timestamp_et": observed.isoformat(),
            "open_interest": oi,
        })

    ordered = tuple(sorted(
        normalized,
        key=lambda item: (
            item["expiration"],
            float(item["strike"]),
            item["right"],
        ),
    ))
    summary = {
        "row_count": len(ordered),
        "positive_open_interest_rows": positive_rows,
        "phase13_open_interest_gte_100_rows": phase13_rows,
        "earliest_timestamp_et": min(timestamps) if timestamps else None,
        "latest_timestamp_et": max(timestamps) if timestamps else None,
        "normalized_surface_fingerprint": _fingerprint(list(ordered)),
    }
    return ordered, summary


def _validate_inputs(
    enrichment_plan: dict[str, Any],
    quote_qualification: dict[str, Any],
) -> list[dict[str, Any]]:
    _check_signature(enrichment_plan, "enrichment_plan_fingerprint")
    _check_signature(quote_qualification, "qualification_fingerprint")
    oi = enrichment_plan.get("open_interest_stage")
    if (
        enrichment_plan.get("contract") != ENRICHMENT_PLAN_CONTRACT
        or enrichment_plan.get("status") != "PLANNED_ZERO_PROVIDER_READS"
        or enrichment_plan.get("provider_candidate") != PROVIDER_CANDIDATE
        or not isinstance(oi, dict)
        or not isinstance(oi.get("qualification_anchors"), list)
        or oi.get("qualification_anchor_count") != len(oi["qualification_anchors"])
        or oi.get("qualification_anchor_count") != EXPECTED_QUALIFICATION_ANCHORS
        or enrichment_plan.get("provider_requests") != 0
        or enrichment_plan.get("historical_fill_authority") is not False
        or enrichment_plan.get("strategy_evidence_authority") is not False
    ):
        raise ThetaDataOpenInterestQualificationError(
            "ThetaData OI enrichment plan lineage/authority changed"
        )
    if (
        quote_qualification.get("contract") != QUOTE_QUALIFICATION_CONTRACT
        or quote_qualification.get("plan_fingerprint")
            != enrichment_plan.get("source_plan_fingerprint")
        or quote_qualification.get("decision_spot_fingerprint")
            != enrichment_plan.get("decision_spot_fingerprint")
        or quote_qualification.get("provider_candidate") != PROVIDER_CANDIDATE
        or quote_qualification.get("full_acquisition_source_qualified") is not True
        or quote_qualification.get("hard_validation_or_transport_errors") != 0
        or quote_qualification.get("repeatability_probe", {}).get(
            "deterministic_normalized_surface"
        ) is not True
    ):
        raise ThetaDataOpenInterestQualificationError(
            "successful quote-surface qualification is required before OI qualification"
        )
    return list(oi["qualification_anchors"])


def _probe_one(
    anchor: dict[str, Any],
    *,
    reader: Callable[..., ThetaDataResponse],
) -> tuple[dict[str, Any], ThetaDataResponse | None, tuple[dict[str, Any], ...] | None]:
    params = anchor["query"]["params"]
    try:
        response = reader(
            symbol=str(params["symbol"]),
            date_et=str(params["date"]),
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
            "http_status": exc.http_status,
            "error": f"{type(exc).__name__}: {exc}",
        }, None, None

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
    except (ThetaDataOpenInterestQualificationError, ValueError) as exc:
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
        "status": "VALID_OPEN_INTEREST_SURFACE",
        "http_status": response.http_status,
        "response_rows": len(response.rows),
        "surface_summary": summary,
    }, response, normalized


def run_thetadata_open_interest_qualification_v1(
    settings: AtlasSettings,
    enrichment_plan: dict[str, Any],
    quote_qualification: dict[str, Any],
    *,
    workers: int = 4,
    reader: Callable[..., ThetaDataResponse] = option_history_open_interest_surface,
) -> dict[str, Any]:
    anchors = _validate_inputs(enrichment_plan, quote_qualification)
    if workers < 1 or workers > MAX_WORKERS:
        raise ThetaDataOpenInterestQualificationError(
            "OI qualification workers exceed Options Standard concurrency"
        )
    settings.assert_external_storage_binding("options")
    generated = datetime.now(UTC)
    run_id = generated.strftime("%Y%m%dT%H%M%SZ")
    root = _run_root(
        settings,
        enrichment_plan["enrichment_plan_fingerprint"],
        run_id,
    )
    root.mkdir(parents=True, exist_ok=False)

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
                    plan_fingerprint=enrichment_plan["enrichment_plan_fingerprint"],
                )
            if normalized is not None:
                normalized_by_index[index] = normalized
            results[index] = result

    ordered = [results[index] for index in sorted(results)]
    hard_bad = {"TRANSPORT_OR_ENTITLEMENT_ERROR", "SURFACE_VALIDATION_ERROR"}
    hard_errors = [item for item in ordered if item["status"] in hard_bad]
    coverage = {str(year): 0 for year in range(2021, 2026)}
    phase13_rows = {str(year): 0 for year in range(2021, 2026)}
    for item in ordered:
        if item["status"] != "VALID_OPEN_INTEREST_SURFACE":
            continue
        year = str(item["query"]["params"]["date"])[:4]
        if year in coverage:
            coverage[year] += 1
            phase13_rows[year] += int(
                item["surface_summary"]["phase13_open_interest_gte_100_rows"]
            )

    repeat_source = next(
        (
            item for item in ordered
            if item["status"] == "VALID_OPEN_INTEREST_SURFACE"
            and str(item["query"]["params"]["date"]).startswith("2021")
        ),
        None,
    )
    provider_requests = len(anchors)
    if repeat_source is None:
        repeat_result: dict[str, Any] = {
            "status": "NOT_RUN_NO_VALID_2021_OI_SURFACE",
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
                plan_fingerprint=enrichment_plan["enrichment_plan_fingerprint"],
            )
        first_normalized = normalized_by_index.get(int(anchor["anchor_index"]))
        repeat_result = {
            "status": second.get("status"),
            "anchor_index": anchor["anchor_index"],
            "deterministic_normalized_surface": (
                second.get("status") == "VALID_OPEN_INTEREST_SURFACE"
                and normalized is not None
                and first_normalized == normalized
            ),
            "first_surface_fingerprint": repeat_source.get(
                "surface_summary", {}
            ).get("normalized_surface_fingerprint"),
            "second_surface_fingerprint": second.get(
                "surface_summary", {}
            ).get("normalized_surface_fingerprint"),
            "second_result": second,
        }

    oldest_2021 = coverage["2021"] > 0
    full_years = all(value > 0 for value in coverage.values())
    qualified = (
        not hard_errors
        and oldest_2021
        and full_years
        and bool(repeat_result.get("deterministic_normalized_surface"))
    )
    report = {
        "contract": CONTRACT,
        "status": (
            "QUALIFIED_FOR_BOUNDED_OPEN_INTEREST_SURFACE_ACQUISITION"
            if qualified
            else "DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS"
        ),
        "enrichment_plan_fingerprint": enrichment_plan["enrichment_plan_fingerprint"],
        "source_plan_fingerprint": enrichment_plan["source_plan_fingerprint"],
        "quote_qualification_fingerprint": quote_qualification["qualification_fingerprint"],
        "decision_spot_fingerprint": enrichment_plan["decision_spot_fingerprint"],
        "provider_candidate": PROVIDER_CANDIDATE,
        "generated_at_utc": generated.isoformat(),
        "run_id": run_id,
        "qualification_anchor_count": len(anchors),
        "provider_requests": provider_requests,
        "provider_writes": 0,
        "anchors": ordered,
        "status_counts": dict(sorted(Counter(item["status"] for item in ordered).items())),
        "valid_surface_coverage_by_year": coverage,
        "phase13_oi_rows_by_year": phase13_rows,
        "oldest_2021_surface_proven": oldest_2021,
        "full_2021_2025_surface_coverage_proven": full_years,
        "repeatability_probe": repeat_result,
        "hard_validation_or_transport_errors": len(hard_errors),
        "full_open_interest_acquisition_source_qualified": qualified,
        "greeks_authority": False,
        "single_contract_selected": False,
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
