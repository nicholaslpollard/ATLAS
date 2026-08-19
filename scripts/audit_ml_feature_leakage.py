from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.feature_leakage_audit import MLFeatureLeakageAudit


def _pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Phase 10 Gate 5 point-in-time ML features and context availability"
    )
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings(PROJECT_ROOT, "development")
    report = MLFeatureLeakageAudit(settings).run(args.end)
    core = report.core_features
    regime = report.regime_context

    print("ATLAS Phase 10 Gate 5 Point-in-Time Feature / Leakage Audit")
    print(f"  contract:                          {report.contract_version}")
    print(f"  history:                           {report.history_start} -> {report.history_end}")
    print(f"  audit status:                      {report.audit_status}")
    print(f"  feature Parquet read mode:         {report.parquet_read_mode}")
    print(f"  observation availability:          {report.observation_availability_rule}")
    print("  core feature integrity:")
    print(f"    feature count:                    {core.feature_count}")
    print(
        f"    candidate rows/symbols/keys:      "
        f"{core.candidate_rows:,} / {core.candidate_symbols:,} / {core.candidate_distinct_keys:,}"
    )
    print(
        f"    feature join rows/symbols/keys:   "
        f"{core.feature_join_rows:,} / {core.feature_join_symbols:,} / {core.feature_join_distinct_keys:,}"
    )
    print(f"    non-numeric feature columns:      {core.non_numeric_feature_names}")
    print(f"    rows with null/non-finite input:  {core.rows_with_any_bad_feature:,}")
    print(f"    full population reconciled:       {core.full_population_reconciled}")
    print(f"    all features numeric:             {core.all_features_numeric}")
    print(f"    all joined features finite:       {core.all_joined_features_finite}")
    print(
        f"    registry raw dependencies safe:   "
        f"{core.registry_dependencies_point_in_time_safe}"
    )
    print("  Phase 9 context availability:")
    print(
        f"    market regime history:            {regime.market_history_rows:,} rows "
        f"({regime.market_history_first_date} -> {regime.market_history_last_date})"
    )
    print(
        f"    candidate rows with market state: {regime.candidate_rows_with_market_context:,} "
        f"({_pct(regime.candidate_market_context_fraction)})"
    )
    print(
        f"    market replayable point-in-time:  "
        f"{regime.market_context_point_in_time_replayable}"
    )
    print(f"    market candidate fields:          {regime.market_context_candidate_fields}")
    print(
        f"    sector regime history:            {regime.sector_history_rows:,} rows / "
        f"{regime.sector_history_symbols:,} proxies"
    )
    print(f"    sector history replayable:        {regime.sector_history_replayable}")
    print(
        f"    sector stock attachment accepted: {regime.sector_instrument_attachment_accepted}"
    )
    print(
        f"    ticker historical attachment:     {regime.ticker_historical_attachment_accepted}"
    )
    print(f"    sector exclusion reason:          {regime.sector_exclusion_reason}")
    print(f"    ticker exclusion reason:          {regime.ticker_exclusion_reason}")
    print(f"  prohibited model-input fields:     {report.prohibited_input_fields}")
    print("  production feature policy:         NOT YET LOCKED")
    print(f"  wall time:                          {report.wall_seconds:.3f}s")
    print(f"  report:                             {report.report_path}")
    print("  result:                             EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
