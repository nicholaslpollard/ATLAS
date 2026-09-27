from __future__ import annotations

"""Prepare full-denominator 2021–2026 option-chain source demand, offline only."""

import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_physical_chain_source_demand_v1 import (
    PhysicalSourceDemandError,build_physical_chain_source_demand,
)


def main()->int:
    print("ATLAS Multi-Year Physical Option-Chain Source Demand / OFFLINE",flush=True)
    print("  2021-2026 research horizon; original case cohort through 2025.",flush=True)
    print("  Zero provider requests; zero new paid request authority.",flush=True)
    try:
        settings=load_settings(ROOT,"development")
        result,path,action=build_physical_chain_source_demand(
            settings,progress=lambda row:print(
                "  "+" ".join(f"{k}={v}" for k,v in row.items()),flush=True,
            ),
        )
        print(f"  result: {action} / {path}",flush=True)
        print(f"  original stock cases: {result['case_denominator']}",flush=True)
        print(f"  candidate source cases requiring local cache reconciliation: {result['new_stock_source_case_denominator_needing_preview']}",flush=True)
        print(f"  deduplicated physical-key previews (NOT approved GETs): {result['unique_unreconciled_physical_preview_queries']}",flush=True)
        print(f"  2022 original full CALL quote-series pointers: {result['original_2022_exact_quote_histories_reused_by_pointer_only']}",flush=True)
        print(f"  2022 exact original source-key gaps: {result['original_2022_old_source_key_absence_count']}",flush=True)
        print(f"  2021 before frozen provider floor: {result['2021_before_five_year_floor_cases']}",flush=True)
        print(f"  2025 signals with deferred 2026 native entry: {result['2026_deferred_2025_signal_native_entry_cases']}",flush=True)
        print("  No accepted 2026 new-stock cohort or protected outcomes are read.",flush=True)
        for year,states in result["by_year"].items():
            print(f"  {year}: {states}",flush=True)
        print(f"  per-year source preview memberships: {result['by_year_preview_case_memberships']}",flush=True)
        print(f"  fingerprint: {result['demand_fingerprint']}",flush=True)
        print("  Acquisition remains BLOCKED pending global local-receipt overlap and an independent budget gate.",flush=True)
        return 0
    except (PhysicalSourceDemandError,ValueError,TypeError,KeyError,OSError,RuntimeError) as exc:
        print(f"MULTIYEAR PHYSICAL SOURCE DEMAND STOPPED: {type(exc).__name__}: {exc}",flush=True)
        print("  Preserve original source and receipts. No paid retry.",flush=True)
        return 3


if __name__=="__main__":
    raise SystemExit(main())
