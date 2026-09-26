from __future__ import annotations

"""Provisional structural CALL ranking using already-acquired 2025 source only."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.data.marketdata_candidate_2025_structural_call_shortlist_v1 import (
    build_structural_call_shortlist, read_frozen_source_closeout, write_local_shortlist,
)
from scripts.run_marketdata_candidate_2025_pilot import preflight


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute new point-in-time structural CALL shortlist; zero provider calls."
    )
    parser.add_argument(
        "--write-local-shortlist", action="store_true",
        help="Explicitly create a new private D:-bound structural metadata manifest.",
    )
    args = parser.parse_args(argv)
    try:
        settings = load_settings(ROOT, "development")
        plan, _source = preflight(settings)
        closeout = read_frozen_source_closeout(settings)
        result = build_structural_call_shortlist(settings, plan, closeout)
        action, output = write_local_shortlist(
            settings, result, authorize_local_write=args.write_local_shortlist,
        )
    except (OSError, ValueError, TypeError, KeyError, CandidateChainCacheError) as exc:
        print(f"STRUCTURAL SHORTLIST STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  no provider retry; preserve private source and closeout unchanged", flush=True)
        return 3
    print("ATLAS 2025 MarketData Point-in-Time Structural CALL Shortlist V1")
    print(f"  source closeout fingerprint: {result['source_closeout_fingerprint']}")
    print(f"  policy: {result['ranking_policy']}")
    print(f"  structural CALL rows examined: {result['source_call_rows_examined']}")
    print(f"  provisional preferred CALL symbols: {result['provisional_structural_symbols']}/12")
    for decision in result["opportunities"]:
        print(
            f"  {decision['ticker']:<5} call_rows={decision['structural_call_count']:<3} "
            f"provisional={decision['provisional_nearest_atm_call'] or 'ABSTAIN'} "
            f"raw_open={decision['accepted_raw_stock_open']}"
        )
    print(f"  shortlist fingerprint: {result['shortlist_fingerprint']}")
    print(f"  local action: {action}")
    print(f"  local output path: {output}")
    print("  provider reads: 0; credits: 0; deliverables UNVERIFIED; no executable option/P&L authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
