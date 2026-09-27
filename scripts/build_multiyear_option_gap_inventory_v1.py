from __future__ import annotations

"""Inventory exact multi-year option-chain source gaps without network calls."""

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.multiyear_option_gap_inventory_v1 import (
    MultiYearOptionInventoryError, build_option_source_gap_inventory,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local 2021–2025 original option source-gap inventory"
    )
    parser.add_argument("--rolling-floor", default="2021-09-27")
    args = parser.parse_args()
    print("ATLAS Multi-Year Original Options Source Gap Census / OFFLINE", flush=True)
    print("  Reuses accepted stock+news+native files, plus the frozen 2022 quote plan.",
          flush=True)
    print("  Zero MarketData requests; no new paid query has been approved.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        report, path, status = build_option_source_gap_inventory(
            settings, rolling_floor=date.fromisoformat(args.rolling_floor),
            progress=lambda row: print("  " + " ".join(
                f"{k}={v}" for k, v in row.items()), flush=True),
        )
        print(f"  result: {status} / {path}", flush=True)
        print(f"  original stock cases: {report['case_denominator']}", flush=True)
        print(f"  matched original 2022 preferred-CALL plan cases: "
              f"{report['2022_case_overlaps_not_new_contract_selections']}", flush=True)
        print(f"  original 2022 frozen preferred cases: "
              f"{report['original_2022_preferred_representatives_in_plan']}", flush=True)
        print(f"  original 2022 frozen exact quote histories: "
              f"{report['original_2022_physical_quote_histories_in_plan']}", flush=True)
        print(f"  provisional unpaid query groups: {report['provisional_group_count']}",
              flush=True)
        for year, statuses in report["by_year"].items():
            print(f"  {year}: {statuses}", flush=True)
        print(f"  inventory fingerprint: {report['inventory_fingerprint']}", flush=True)
        print("  Preview only: reconcile exact existing 2022 chain receipts and 2025 "
              "pilot before any physical new requests.", flush=True)
        return 0
    except (MultiYearOptionInventoryError, OSError, ValueError,
            TypeError, KeyError, RuntimeError) as exc:
        print(f"MULTIYEAR OPTION GAP INVENTORY STOPPED: "
              f"{type(exc).__name__}: {exc}", flush=True)
        print("  Keep original stock, chain, quote and news files untouched.",
              flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
