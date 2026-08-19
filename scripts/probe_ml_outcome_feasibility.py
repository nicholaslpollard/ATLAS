from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.outcome_probe import MLOutcomeFeasibilityProbe


def _pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Phase 10 ML outcome-label feasibility")
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings(PROJECT_ROOT, "development")
    report = MLOutcomeFeasibilityProbe(settings).run(args.end)

    print("ATLAS Phase 10 Gate 3 Outcome-Label Feasibility Probe")
    print(f"  contract:                          {report.contract_version}")
    print(f"  history:                           {report.history_start} -> {report.history_end}")
    print("  probe status:                      EVIDENCE_ONLY")
    print(f"  accepted Gate 2 candidate rows:    {report.candidate_rows:,}")
    print(f"  accepted Gate 2 candidate symbols: {report.candidate_symbols:,}")
    print("  forward-horizon evidence:")
    for item in report.horizons:
        q = item.return_quantiles
        print(
            f"    {item.horizon_sessions:>2} sessions: "
            f"labelable={item.labelable_rows:,} ({_pct(item.labelable_fraction)}) "
            f"censored={item.censored_rows:,} split-cross={item.split_crossing_rows:,} "
            f"abs>=50%={item.abs_return_ge_50pct_rows:,} "
            f"non-split abs>=50%={item.non_split_abs_return_ge_50pct_rows:,}"
        )
        print(
            "       returns: "
            f"p01={q['p01']!s} p05={q['p05']!s} p25={q['p25']!s} "
            f"p50={q['p50']!s} p75={q['p75']!s} p95={q['p95']!s} p99={q['p99']!s}"
        )
        print(
            f"       sign: positive={item.positive_rows:,} negative={item.negative_rows:,} "
            f"near-zero={item.near_zero_rows:,} abs>=25%={item.abs_return_ge_25pct_rows:,} "
            f"abs>=100%={item.abs_return_ge_100pct_rows:,}"
        )
    split = report.split_adjustment
    print("  split-adjustment evidence:")
    print(f"    fetched split events:             {split.fetched_split_events:,}")
    print(f"    fetched split symbols:            {split.fetched_split_symbols:,}")
    print(f"    material split events:            {split.material_split_events:,}")
    print(f"    diagnostic material events:       {split.diagnostic_material_split_events:,}")
    print(f"    unadjusted-like events:            {split.unadjusted_like_events:,}")
    print(f"    adjusted-like events:              {split.adjusted_like_events:,}")
    print(f"    ambiguous events:                  {split.ambiguous_events:,}")
    print(f"    median abs raw return:             {split.median_abs_raw_return}")
    print(f"    median abs expected-ratio residual:{split.median_abs_expected_ratio_residual}")
    print(f"  exact session continuity required:  {report.exact_session_continuity_required}")
    print(f"  same provider ticker required:      {report.same_provider_ticker_required}")
    print(f"  ticker-text splicing used:          {report.ticker_text_splicing_used}")
    print(f"  corporate-action evidence source:   {report.corporate_action_evidence_source}")
    print("  prediction-label policy:            NOT YET LOCKED")
    print(f"  split evidence SHA-256:             {report.split_evidence_sha256}")
    print(f"  split evidence:                     {report.split_evidence_path}")
    print(f"  wall time:                          {report.wall_seconds:.3f}s")
    print(f"  report:                             {report.report_path}")
    print("  result:                             EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
