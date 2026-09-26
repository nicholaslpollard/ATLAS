from __future__ import annotations

"""Junction-safe, bounded operator entry point for the accepted 2025 pilot.

The scientific inputs are workstation-local. This script never traverses data/
to discover evidence: it uses the same logical source path emitted by the
accepted exporter and verifies the exact file/plan bytes before any provider read.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import AtlasSettings, load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError,
    MAX_NEW_REQUESTS,
    run_candidate_chain_cache,
    verify_candidate_plan,
)

COHORT = "d6c924cf5006d295"
PLAN_REL = f"data/options/manifests/marketdata_candidate_batch_plan_v1_{COHORT}.json"
SOURCE_REL = f"data/research/evidence/marketdata_candidate_stock_v1/{COHORT}.json"
PLAN_FILE_SHA256 = "fe7b85272212d9ba5584b4e964d7e46e3ac128cf449604786bdee7e9441e149e"
SOURCE_SHA256 = "e7d90ce3162475ecbfc442d35e0ffbca18fca38434e658b0ee8bd7633021362e"
PLAN_FINGERPRINT = "a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1"
AGIO_REQUEST_ID = "85fafd7c2ac2ddd61a1436a791c1bee5a654a279ce1f714fdc919b3bbb1d84ce"
TOTAL_REQUESTS = 12
MAX_PILOT_NEW_REQUESTS = 11


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def preflight(settings: AtlasSettings) -> tuple[dict[str, Any], Path]:
    """Fail without provider calls if any physical input or lineage differs."""
    plan_path = settings.resolved_path(PLAN_REL)
    source_path = settings.resolved_path(SOURCE_REL)
    if not plan_path.is_file():
        raise CandidateChainCacheError(f"expected saved plan missing: {plan_path}")
    if _digest(plan_path) != PLAN_FILE_SHA256:
        raise CandidateChainCacheError(f"saved plan file SHA mismatch: {plan_path}")

    plan = verify_candidate_plan(json.loads(plan_path.read_text(encoding="utf-8")))
    if plan["plan_fingerprint"] != PLAN_FINGERPRINT or len(plan["requests"]) != TOTAL_REQUESTS:
        raise CandidateChainCacheError("saved plan fingerprint/count differs from frozen pilot")
    if {x["stock_source_sha256"] for x in plan["source_bindings"].values()} != {SOURCE_SHA256}:
        raise CandidateChainCacheError("saved plan source bindings differ from accepted export")
    if plan["requests"][0]["request_identity"] != AGIO_REQUEST_ID:
        raise CandidateChainCacheError("saved plan no longer begins with the AGIO canary")

    # Direct path, not a recursive Get-ChildItem scan: data/research/evidence is
    # a Windows junction to the secondary SSD on the operator workstation.
    if not source_path.is_file() or source_path.is_symlink():
        raise CandidateChainCacheError(
            "accepted stock bundle not present at its exporter path: "
            f"{source_path}; do not rerun the paid request or re-export automatically"
        )
    if _digest(source_path) != SOURCE_SHA256:
        raise CandidateChainCacheError(f"accepted stock bundle SHA mismatch: {source_path}")
    bundle = json.loads(source_path.read_text(encoding="utf-8"))
    if (
        not isinstance(bundle, dict)
        or bundle.get("contract") != "atlas-marketdata-accepted-stock-candidate-export-v1"
        or not isinstance(bundle.get("rows"), list)
        or {row.get("opportunity_id") for row in bundle["rows"] if isinstance(row, dict)}
           != set(plan["source_bindings"])
        or len(bundle["rows"]) != len(plan["source_bindings"])
    ):
        raise CandidateChainCacheError("source bundle is not the accepted planned cohort")
    return plan, source_path


def _assert_preview(preview: dict[str, Any]) -> None:
    if (
        preview["status"] != "PREVIEW"
        or preview["provider_reads"] != 0
        or preview["new_complete"] != 0
        or preview["quarantined"] != 0
        or preview["planned_chain_requests"] != TOTAL_REQUESTS
        or preview["pending"] + preview["reused"] != TOTAL_REQUESTS
        or preview["request_results"][0]["request_identity"] != AGIO_REQUEST_ID
        or preview["request_results"][0]["status"] != "REUSED_VERIFIED"
    ):
        raise CandidateChainCacheError("unexpected pilot cache preview; no paid reads authorized")


def run_pilot(
    settings: AtlasSettings,
    *,
    authorize_provider_reads: bool = False,
    confirm_paid_starter: bool = False,
    confirm_private_internal_use: bool = False,
    max_total_new_requests: int = MAX_PILOT_NEW_REQUESTS,
    provider_read: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if not 1 <= max_total_new_requests <= MAX_PILOT_NEW_REQUESTS:
        raise CandidateChainCacheError("pilot max-total-new-requests must be 1..11")
    authorized = authorize_provider_reads and confirm_paid_starter and confirm_private_internal_use
    if any((authorize_provider_reads, confirm_paid_starter, confirm_private_internal_use)) and not authorized:
        raise CandidateChainCacheError("all three explicit acquisition confirmations are required")
    plan, source = preflight(settings)
    print(f"  exact accepted stock source: {source}", flush=True)
    preview = run_candidate_chain_cache(settings, plan, provider_read=provider_read)
    _assert_preview(preview)
    print(
        f"  zero-credit preflight: verified={preview['reused']} pending={preview['pending']} "
        "provider_reads=0",
        flush=True,
    )
    if not authorized or preview["pending"] == 0:
        return preview

    budget = max_total_new_requests
    while budget > 0 and preview["pending"] > 0:
        batch_size = min(MAX_NEW_REQUESTS, budget, preview["pending"])
        print(f"  authorized bounded batch: maximum {batch_size} new requests", flush=True)
        report = run_candidate_chain_cache(
            settings,
            plan,
            authorize_provider_reads=True,
            confirm_paid_starter=True,
            confirm_private_internal_use=True,
            max_new_requests=batch_size,
            provider_read=provider_read,
            stock_source_files=(source,),
        )
        # A failed/quarantined/ambiguous or credit/storage-blocked run never
        # automatically proceeds to a second batch. Return receipts for review.
        if (
            report["status"] not in {"COMPLETE", "PARTIAL_RESUMABLE"}
            or report["new_complete"] != batch_size
            or report["provider_reads"] != batch_size
            or report["credits_unknown_after_failed_request"]
            or report["quarantined"] != 0
        ):
            raise CandidateChainCacheError(
                "batch did not satisfy exact continuation conditions; inspect archived run and attempt receipts"
            )
        budget -= report["new_complete"]
        next_preview = run_candidate_chain_cache(settings, plan, provider_read=provider_read)
        _assert_preview(next_preview)
        if next_preview["reused"] != preview["reused"] + report["new_complete"]:
            raise CandidateChainCacheError("post-batch zero-credit receipt reconciliation failed")
        preview = next_preview
        print(
            f"  independently verified: {preview['reused']}/{TOTAL_REQUESTS}; "
            f"pending={preview['pending']}",
            flush=True,
        )
    return preview


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only by default; junction-safe accepted 2025 MarketData pilot, with guarded 10+1 acquisition."
    )
    parser.add_argument("--authorize-provider-reads", action="store_true")
    parser.add_argument("--confirm-paid-starter", action="store_true")
    parser.add_argument("--confirm-private-internal-use", action="store_true")
    parser.add_argument("--max-total-new-requests", type=int, default=MAX_PILOT_NEW_REQUESTS)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        report = run_pilot(
            settings,
            authorize_provider_reads=args.authorize_provider_reads,
            confirm_paid_starter=args.confirm_paid_starter,
            confirm_private_internal_use=args.confirm_private_internal_use,
            max_total_new_requests=args.max_total_new_requests,
        )
    except (OSError, ValueError, CandidateChainCacheError) as exc:
        print(f"PILOT STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  No automatic retry; preserve exact raw bodies, receipts and attempt markers.", flush=True)
        return 3
    print(
        f"ATLAS pilot: verified={report['reused']}/{TOTAL_REQUESTS} pending={report['pending']} "
        f"status={report['status']} provider_reads_in_final_preview=0",
        flush=True,
    )
    print("  Source-only EOD chains; no quote histories, fill/P&L, PAPER or LIVE authority.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
