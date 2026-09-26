from __future__ import annotations

"""Read-only source-level closeout for the frozen 2025 MarketData pilot.

This module never imports MarketData transport, resolves credentials, or requests
quote histories. Exact raw HTTP bodies remain in the original private cache.
The local closeout is a reproducible reference to those receipts, not a new
provider source, contract selector, price, trade, or strategy result.
"""

import json
import os
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError,
    _fingerprint,
    _paths,
    _valid_receipt,
    run_candidate_chain_cache,
    verify_candidate_plan,
)
from packages.providers.marketdata_app import array_rows

CONTRACT = "atlas-marketdata-accepted-2025-chain-source-closeout-v1"
FROZEN_PLAN = "a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1"
FROZEN_FSLY = "6886b1d35d7a1ea2e1a9f555cd0f778905ad1029175bec953fc52d5289a643d8"
FROZEN_FSLY_PROOF = "6d2e3d17fbcb0f39d88af9ed025d71757c84e97ac00b75d130d189c6ac0f083f"
FROZEN_FSLY_BODY = "54e3e162845e54a24f015e4faaff70531c0707baf1f492fcebd5c35922f5971a"
OUTPUT_REL = "data/options/manifests/marketdata_candidate_2025_source_closeout_v1_d6c924cf5006d295.json"

def _count_sides(rows: tuple[dict[str, Any], ...]) -> dict[str, int]:
    return {"call": sum(r["side"] == "call" for r in rows),
            "put": sum(r["side"] == "put" for r in rows)}

def build_source_closeout(
    settings: AtlasSettings,
    plan: dict[str, Any],
    *,
    source_sha256: str,
) -> dict[str, Any]:
    """Independently verify all physical original receipts; never trust a run checkpoint."""
    verified_plan = verify_candidate_plan(plan)
    if verified_plan["plan_fingerprint"] != FROZEN_PLAN or len(verified_plan["requests"]) != 12:
        raise CandidateChainCacheError("frozen cohort plan changed")
    preview = run_candidate_chain_cache(settings, verified_plan)
    if (
        preview["status"] != "PREVIEW" or preview["provider_reads"] != 0
        or preview["reused"] != 11 or preview.get("no_data_verified") != 1
        or preview["pending"] != 0 or preview["new_complete"] != 0
        or len(preview["request_results"]) != 12
    ):
        raise CandidateChainCacheError("source closeout requires 11 verified chains, one exact gap, zero pending")
    source_shas = {binding["stock_source_sha256"]
                   for binding in verified_plan["source_bindings"].values()}
    if source_shas != {source_sha256}:
        raise CandidateChainCacheError("source closeout stock artifact binding differs")

    request_rows: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    complete = 0
    gaps = 0
    reported_consumed = 0
    for index, request in enumerate(verified_plan["requests"]):
        summary = preview["request_results"][index]
        if summary["request_identity"] != request["request_identity"]:
            raise CandidateChainCacheError("preview order/identity diverges from frozen plan")
        paths = _paths(settings, request["request_identity"])
        receipt = _valid_receipt(
            paths, request, expected_plan_fingerprint=FROZEN_PLAN,
        )
        if receipt is None:
            raise CandidateChainCacheError("closeout cannot include an unattempted request")
        gap = receipt["status"] == "VERIFIED_NO_DATA"
        expected_status = "SOURCE_NO_DATA_VERIFIED" if gap else "REUSED_VERIFIED"
        if summary["status"] != expected_status:
            raise CandidateChainCacheError("preview and independently verified receipt disagree")

        row: dict[str, Any] = {
            "request_identity": request["request_identity"],
            "ticker": request["ticker"],
            "snapshot_date": request["params"]["date"],
            "expiration": request["params"]["expiration"],
            "strike_window": request["params"]["strike"],
            "opportunity_ids": list(request["opportunity_ids"]),
            "status": expected_status,
            "raw_body_sha256": receipt["body_sha256"],
            "raw_body_bytes": receipt["body_bytes"],
        }
        if gap:
            if (
                request["request_identity"] != FROZEN_FSLY
                or receipt["no_data_proof"] != FROZEN_FSLY_PROOF
                or receipt["body_sha256"] != FROZEN_FSLY_BODY
            ):
                raise CandidateChainCacheError("no-data classification is not the accepted FSLY proof")
            row.update({
                "same_side_observation": "NO_DATA_FOR_EXACT_QUERY_ONLY",
                "proof_fingerprint": receipt["no_data_proof"],
                "row_count": 0,
                "historical_absence_in_alternative_queries_proven": False,
            })
            gaps += 1
            observed_side_counts: dict[str, int] | None = None
        else:
            if receipt["status"] != "COMPLETE":
                raise CandidateChainCacheError("closeout receipt is not independently complete")
            try:
                data = json.loads(paths.body.read_bytes().decode("utf-8"))
                records = array_rows(data)
            except (OSError, ValueError, TypeError) as exc:
                raise CandidateChainCacheError("verified raw chain failed independent local decode") from exc
            if not records or len(records) != receipt["row_count"]:
                raise CandidateChainCacheError("closeout row count disagrees with signed receipt")
            observed_side_counts = _count_sides(records)
            consumed = receipt["rate_limit"]["consumed"]
            if type(consumed) is not int or consumed < 0:
                raise CandidateChainCacheError("original complete receipt has invalid credit accounting")
            reported_consumed += consumed
            row.update({
                "row_count": len(records),
                "observed_call_rows": observed_side_counts["call"],
                "observed_put_rows": observed_side_counts["put"],
                "provider_reported_credits_consumed": consumed,
                "offline_recovered_original": bool(receipt.get("offline_recovery", False)),
                "no_quote_or_contract_selection_authority": True,
            })
            complete += 1
        request_rows.append(row)
        for identifier in request["opportunity_ids"]:
            binding = verified_plan["source_bindings"][identifier]
            side = binding["side"]
            if side not in ("call", "put"):
                raise CandidateChainCacheError("accepted stock candidate has unsupported option side")
            opportunities.append({
                "opportunity_id": identifier,
                "request_identity": request["request_identity"],
                "ticker": request["ticker"],
                "decision_at_utc": binding["decision_at_utc"],
                "requested_side": side,
                "source_coverage": expected_status,
                "observed_same_side_rows": (
                    observed_side_counts[side] if observed_side_counts is not None else None
                ),
                "final_contract_selected": False,
                "deliverable_and_adjustment_validated": False,
                "historical_quote_path_acquired": False,
            })

    if (complete, gaps, len(opportunities)) != (11, 1, 12):
        raise CandidateChainCacheError("frozen pilot closeout counts diverge")
    closeout: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "COMPLETE_WITH_SOURCE_GAPS",
        "authority": "DEVELOPMENT_SOURCE_ONLY",
        "plan_fingerprint": FROZEN_PLAN,
        "accepted_stock_source_sha256": source_sha256,
        "planned_requests": 12,
        "verified_complete_chains": complete,
        "exact_query_no_data": gaps,
        "pending": 0,
        "verified_opportunities": 12,
        "provider_reads_during_closeout": 0,
        "provider_credits_during_closeout": 0,
        "provider_reported_credits_consumed_by_complete_receipts": reported_consumed,
        "raw_bodies_preserved_in_original_private_cache": True,
        "unselected_candidate_symbols_available_only_in_original_raw_bodies": True,
        "no_execution_price_quote_history_or_option_pnl_authority": True,
        "no_strategy_paper_live_or_broker_authority": True,
        "requests": request_rows,
        "opportunities": sorted(opportunities, key=lambda x: x["opportunity_id"]),
    }
    closeout["closeout_fingerprint"] = _fingerprint(closeout)
    return closeout

def write_local_closeout(
    settings: AtlasSettings,
    closeout: dict[str, Any],
    *,
    authorize_local_write: bool = False,
) -> tuple[str, Path]:
    """Read-only default. Exclusive, idempotent local write; never overwrite."""
    path = settings.resolved_path(OUTPUT_REL)
    encoded = (json.dumps(closeout, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists() or path.is_symlink():
        if not path.is_file() or path.is_symlink() or path.read_bytes() != encoded:
            raise CandidateChainCacheError("existing source closeout differs or is linked; preserve it")
        return "REUSED_EXACT_LOCAL_CLOSEOUT", path
    if not authorize_local_write:
        return "PREVIEW_NO_WRITES", path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CandidateChainCacheError("closeout appeared concurrently; inspect local file") from exc
    if path.read_bytes() != encoded:
        raise CandidateChainCacheError("local closeout read-back differs; preserve file")
    return "WRITTEN_AND_REVERIFIED", path
