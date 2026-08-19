from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.ml.label_policy_probe import MLLabelPolicyProbe


def _pct(value: float) -> str:
    return f"{100.0 * value:.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Phase 10 Gate 4 prediction-label annual stability"
    )
    parser.add_argument("--end", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    report = MLLabelPolicyProbe(load_settings(PROJECT_ROOT, "development")).run(args.end)

    print("ATLAS Phase 10 Gate 4 Prediction-Label Stability Probe")
    print(f"  contract:                     {report.contract_version}")
    print(f"  history:                      {report.history_start} -> {report.history_end}")
    print("  probe status:                 EVIDENCE_ONLY")
    print(f"  candidate horizons:           {report.candidate_horizons}")
    print(f"  candidate multipliers:        {report.candidate_multipliers}")
    print(f"  primary threshold candidate:  {report.primary_candidate_multiplier}x NATR")
    print("  candidate evidence:")
    for candidate in report.candidates:
        print(
            f"    {candidate.horizon_sessions:>2} sessions / {candidate.multiplier:.1f}x: "
            f"usable={candidate.usable_rows:,} "
            f"UP={candidate.up_rows:,} DOWN={candidate.down_rows:,} "
            f"NEUTRAL={candidate.neutral_rows:,} "
            f"directional={_pct(candidate.directional_fraction)} "
            f"UP|directional={_pct(candidate.up_fraction_of_directional)}"
        )
        print(
            f"       annual directional range={_pct(candidate.annual_directional_fraction_range)} "
            f"annual UP|directional range={_pct(candidate.annual_up_fraction_of_directional_range)}"
        )
        for annual in candidate.annual_evidence:
            print(
                f"       {annual.year}: usable={annual.usable_rows:,} "
                f"UP={_pct(annual.up_fraction)} DOWN={_pct(annual.down_fraction)} "
                f"NEUTRAL={_pct(annual.neutral_fraction)} "
                f"directional={_pct(annual.directional_fraction)} "
                f"UP|directional={_pct(annual.up_fraction_of_directional)}"
            )
    print(f"  split crossings censored:     {report.split_crossing_windows_censored}")
    print(f"  exact session continuity:     {report.exact_session_continuity_required}")
    print(f"  same provider ticker:         {report.same_provider_ticker_required}")
    print(f"  endpoint outcomes only:       {report.endpoint_outcome_only}")
    print("  prediction-label policy:      NOT YET LOCKED")
    print(f"  wall time:                    {report.wall_seconds:.3f}s")
    print(f"  report:                       {report.report_path}")
    print("  result:                       EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
