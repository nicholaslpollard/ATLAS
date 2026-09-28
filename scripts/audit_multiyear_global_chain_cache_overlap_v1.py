from __future__ import annotations

"""Read original signed local chain receipts; no network or account charges."""

import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_global_chain_cache_overlap_v1 import (
    GlobalChainOverlapError,build_global_chain_cache_overlap,
)


def main()->int:
    print("ATLAS Multi-Year Global Physical Chain Cache Reuse / OFFLINE",flush=True)
    print("  Full original 2021-2025 stock cohort, 2026 protected boundary explicit.",flush=True)
    print("  Receipt metadata index once; raw body validation only for intersecting sources.",flush=True)
    print("  Zero external GETs, zero paid authorization, zero quote-body rereads.",flush=True)
    try:
        settings=load_settings(ROOT,"development")
        result,path,action=build_global_chain_cache_overlap(
            settings,progress=lambda r:print(
                "  "+" ".join(f"{k}={v}" for k,v in r.items()),flush=True,
            ),
        )
        print(f"  result: {action} / {path}",flush=True)
        print(f"  source preview physical keys: {result['unique_physical_preview_queries']}",flush=True)
        print(f"  underlying accepted stock cases: {result['accepted_case_denominator']}",flush=True)
        print(f"  candidate source-case memberships: {result['candidate_case_memberships']}",flush=True)
        print(f"  local receipt metadata: {result['source_cache_metadata_counts']}",flush=True)
        print(f"  matched source bodies independently verified: {result['source_bodies_verified_for_relevant_overlaps']}",flush=True)
        print(f"  physical source states: {result['by_status']}",flush=True)
        for year,status in result["by_year_query_status"].items():
            print(f"  {year} physical queries: {status}",flush=True)
            print(f"       original case memberships: {result['by_year_case_status'][year]}",flush=True)
        print(f"  fingerprint: {result['overlap_fingerprint']}",flush=True)
        print("  This is a source-coverage report, not an API budget, option selection or simulated trade.",flush=True)
        return 0
    except (GlobalChainOverlapError,ValueError,TypeError,KeyError,OSError,RuntimeError) as exc:
        print(f"GLOBAL CHAIN SOURCE OVERLAP STOPPED: {type(exc).__name__}: {exc}",flush=True)
        print("  Preserve evidence and unresolved attempts. Do not retry a provider request.",flush=True)
        return 3


if __name__=="__main__":
    raise SystemExit(main())
