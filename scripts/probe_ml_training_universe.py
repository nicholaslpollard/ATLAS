from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.universe_probe import MLTrainingUniverseProbe


def _percent(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the historical population before ATLAS ML labels/models are designed."
    )
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = load_settings(PROJECT_ROOT, "development")
    report = MLTrainingUniverseProbe(settings).run(args.end)

    print("ATLAS Phase 10 Gate 1 Historical ML Training-Universe Probe")
    print(f"  contract:                         {report.contract_version}")
    print(f"  history:                          {report.history_start} -> {report.history_end}")
    print("  probe status:                     EVIDENCE_ONLY")
    print(f"  historical daily bars:            {report.historical_bar_rows:,}")
    print(f"  historical daily feature rows:    {report.historical_feature_rows:,}")
    print(f"  historical symbols:               {report.historical_unique_symbols:,}")
    print(f"  feature symbols:                  {report.feature_unique_symbols:,}")
    print(f"  current reference symbols:        {report.current_reference_symbols:,}")
    print(f"  current routed-universe symbols:  {report.current_universe_symbols:,}")
    print(f"  historical symbols absent ref:    {report.historical_symbols_absent_current_reference:,}")
    print(f"  historical symbols absent route:  {report.historical_symbols_absent_current_universe:,}")
    print(
        "  historical rows absent ref:      "
        f"{report.historical_rows_absent_current_reference:,} "
        f"({_percent(report.historical_rows_absent_current_reference_fraction)})"
    )
    print(f"  complete 33-feature rows:         {report.complete_feature_rows:,}")
    print(f"  complete rows >=$250k DV:         {report.liquid_complete_rows:,}")
    print(
        "  liquid complete absent ref:      "
        f"{report.liquid_complete_rows_absent_current_reference:,} "
        f"({_percent(report.liquid_complete_rows_absent_current_reference_fraction)})"
    )
    print(f"  provider adjustment states:       {report.adjustment_state_counts}")
    print(f"  symbols with >=30d history gap:   {report.symbols_with_long_gap:,}")
    print(f"  >=30d history gaps:               {report.long_gap_count:,}")
    print(f"  maximum calendar gap:             {report.maximum_calendar_gap_days:,} days")
    print(f"  adjacent close-return pairs:      {report.consecutive_return_pair_count:,}")
    print(f"  |return| >=50% pairs:             {report.abs_return_ge_50pct_count:,}")
    print(f"  |return| >=100% pairs:            {report.abs_return_ge_100pct_count:,}")
    print("  annual evidence:")
    for item in report.annual_evidence:
        print(
            f"    {item.year}: rows={item.observation_rows:,} "
            f"symbols={item.unique_symbols:,} "
            f"absent-current-ref={_percent(item.rows_absent_current_reference_fraction)} "
            f"complete={item.complete_feature_rows:,} "
            f"liquid-complete={item.liquid_complete_rows:,} "
            f"liquid-absent-ref={_percent(item.liquid_complete_rows_absent_current_reference_fraction)}"
        )
    print(f"  survivorship gap observed:        {report.survivorship_gap_observed}")
    print(
        "  current snapshot safe for train: "
        f"{report.current_snapshot_safe_as_historical_training_universe}"
    )
    print("  historical identity policy:       NOT YET LOCKED")
    print("  prediction-label policy:          NOT YET LOCKED")
    print(f"  wall time:                        {report.wall_seconds:.3f}s")
    print(f"  report:                           {report.report_path}")
    print("  result:                           EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
