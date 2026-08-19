from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.outcome_family_audit import MLOutcomeFamilyAudit


def _pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Phase 10 Gate 3 volatility-scaled endpoint outcome families"
    )
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings(PROJECT_ROOT, "development")
    report = MLOutcomeFamilyAudit(settings).run(args.end)

    print("ATLAS Phase 10 Gate 3 Volatility-Scaled Outcome Family Audit")
    print(f"  contract:                          {report.contract_version}")
    print(f"  history:                           {report.history_start} -> {report.history_end}")
    print("  audit status:                      EVIDENCE_ONLY")
    print(f"  accepted Gate 2 candidate rows:    {report.candidate_rows:,}")
    print(f"  accepted Gate 2 candidate symbols: {report.candidate_symbols:,}")
    print(f"  volatility-eligible rows:          {report.volatility_eligible_rows:,}")
    print(f"  volatility-eligible symbols:       {report.volatility_eligible_symbols:,}")
    integrity = report.feature_integrity
    print("  volatility-feature integrity:")
    print(f"    Parquet read mode:                {integrity.parquet_read_mode}")
    print(
        f"    base/join rows:                   {integrity.base_candidate_rows:,} / "
        f"{integrity.feature_join_rows:,}"
    )
    print(
        f"    base/join symbols:                {integrity.base_candidate_symbols:,} / "
        f"{integrity.feature_join_symbols:,}"
    )
    print(f"    stored natr finite rows:          {integrity.stored_natr_finite_rows:,}")
    print(f"    stored natr positive rows:        {integrity.stored_natr_positive_rows:,}")
    print(f"    stored natr zero rows:            {integrity.stored_natr_zero_rows:,}")
    print(f"    stored natr negative rows:        {integrity.stored_natr_negative_rows:,}")
    print(f"    derived natr positive rows:       {integrity.derived_natr_positive_rows:,}")
    print(f"    stored/derived comparable rows:   {integrity.comparable_rows:,}")
    print(
        f"    stored/derived mismatched rows:   {integrity.mismatched_rows:,} "
        f"({_pct(integrity.mismatch_fraction)})"
    )
    print(f"    median stored natr14:             {integrity.median_stored_natr}")
    print(f"    median derived atr14/close:       {integrity.median_derived_natr}")
    print(f"    max abs natr difference:          {integrity.max_abs_difference}")
    print(f"    full population reconciled:       {integrity.full_population_reconciled}")
    print(f"    stored vs derived reconciled:     {integrity.stored_vs_derived_reconciled}")
    print(f"  volatility feature:                {report.volatility_feature}")
    print(f"  horizon scaling:                   {report.volatility_horizon_scaling}")
    print(f"  threshold grid:                    {report.threshold_grid}")
    print("  horizon evidence:")
    for horizon in report.horizons:
        print(
            f"    {horizon.horizon_sessions:>2} sessions: "
            f"labelable={horizon.labelable_rows:,} "
            f"split-censored={horizon.split_censored_rows:,} "
            f"usable={horizon.usable_rows:,} ({_pct(horizon.usable_fraction)}) "
            f"adjacent-overlap={horizon.adjacent_label_overlap_sessions} sessions"
        )
        print(
            f"       median natr14={horizon.median_start_natr} "
            f"median scaled move={horizon.median_scaled_move}"
        )
        for item in horizon.thresholds:
            print(
                f"       {item.multiplier:.1f}x: "
                f"UP={item.up_rows:,} ({_pct(item.up_fraction)}) "
                f"DOWN={item.down_rows:,} ({_pct(item.down_fraction)}) "
                f"NEUTRAL={item.neutral_rows:,} ({_pct(item.neutral_fraction)}) "
                f"directional={_pct(item.directional_fraction)} "
                f"UP|directional={_pct(item.up_fraction_of_directional)}"
            )
    print(f"  split-crossing windows censored:   {report.split_crossing_windows_censored}")
    print(f"  exact session continuity required: {report.exact_session_continuity_required}")
    print(f"  same provider ticker required:     {report.same_provider_ticker_required}")
    print(f"  endpoint outcome only:             {report.endpoint_outcome_only}")
    print(f"  path barrier selected:             {report.path_barrier_selected}")
    print(f"  path barrier reason:               {report.path_barrier_reason}")
    print("  prediction-label policy:           NOT YET LOCKED")
    print(f"  source split evidence:             {report.source_split_evidence_path}")
    print(f"  wall time:                         {report.wall_seconds:.3f}s")
    print(f"  report:                            {report.report_path}")
    print("  result:                            EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
