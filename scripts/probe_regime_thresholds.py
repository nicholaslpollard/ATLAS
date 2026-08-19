from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.threshold_probe import RegimeThresholdProbe


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100.0:6.2f}%"


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare point-in-time-safe Phase 9 threshold memory policies"
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    report = RegimeThresholdProbe(load_settings(PROJECT_ROOT, "development")).build(
        args.start,
        args.end,
    )

    print("ATLAS Phase 9 Point-in-Time Threshold Policy Probe")
    print(f"  contract:                  {report.contract_version}")
    print(f"  persistence contract:      {report.persistence_probe_contract_version}")
    print(f"  requested range:           {report.start_date} -> {report.end_date}")
    print(f"  probe status:              {report.probe_status}")
    print(f"  selected confirmation:     {report.selected_confirmation_sessions} sessions")
    print(f"  seed/training sessions:    {report.training_sessions}")
    print(f"  policy grid:               {', '.join(report.policy_names)}")
    print(f"  evaluation sessions:       {report.evaluation_session_count:,}")
    print(f"  evaluation range:          {report.first_evaluation_date} -> {report.last_evaluation_date}")
    print(f"  sector observations:       {report.sector_evaluation_observation_count:,}")
    print(f"  wall time:                 {report.wall_seconds:.3f}s")

    for policy_name, candidate in report.market_candidates.items():
        diag = candidate["transition_diagnostics"]
        agreement = candidate["retrospective_reference_agreement"]
        end_state = candidate["end_date_state"]
        print(f"  market threshold candidate {policy_name}:")
        print(f"    transition_rate             {_pct(diag['transition_rate'])}")
        print(f"    median_run_length          {diag['median_run_length']}")
        print(f"    one_day_run_share           {_pct(diag['one_day_run_share'])}")
        print(f"    retrospective exact         {_pct(agreement['exact_agreement_rate'])}")
        print(f"    retrospective family        {_pct(agreement['direction_family_agreement_rate'])}")
        print(f"    retrospective opposite      {_pct(agreement['opposite_direction_mismatch_rate'])}")
        print(
            "    end_state                   "
            f"{end_state['composite']} | trend={end_state['structure']} momentum={end_state['momentum']} "
            f"participation={end_state['participation']} vol={end_state['volatility']} efficiency={end_state['efficiency']}"
        )
        thresholds = candidate["end_thresholds"]
        print("    end market threshold bands:")
        for metric in (
            "close_above_ema_50",
            "close_above_ema_200",
            "median_price_distance_ema_20",
            "median_ema_20_slope_1",
            "median_natr_14",
        ):
            values = thresholds[metric]
            if metric.startswith("close_above_"):
                p25 = _pct(values.get("p25"))
                p75 = _pct(values.get("p75"))
                p90 = _pct(values.get("p90")) if values.get("p90") is not None else "n/a"
            else:
                p25 = _num(values.get("p25"))
                p75 = _num(values.get("p75"))
                p90 = _num(values.get("p90")) if values.get("p90") is not None else "n/a"
            print(f"      {metric:<30} p25={p25} p75={p75} p90={p90}")

    for policy_name, candidate in report.sector_candidates.items():
        summary = candidate["transition_summary"]
        agreement = candidate["retrospective_reference_agreement"]
        print(f"  sector threshold candidate {policy_name}:")
        print(f"    mean_transition_rate        {_pct(summary['mean_transition_rate'])}")
        print(f"    median_transition_rate      {_pct(summary['median_transition_rate'])}")
        print(f"    max_transition_rate         {_pct(summary['max_transition_rate'])}")
        print(f"    median_run_length          {summary['median_of_median_run_lengths']}")
        print(f"    mean_one_day_run_share      {_pct(summary['mean_one_day_run_share'])}")
        print(f"    retrospective exact         {_pct(agreement['exact_agreement_rate'])}")
        print(f"    retrospective family        {_pct(agreement['direction_family_agreement_rate'])}")
        print(f"    retrospective opposite      {_pct(agreement['opposite_direction_mismatch_rate'])}")
        print("    end-date sector states:")
        for ticker, state in candidate["end_date_states"].items():
            print(
                f"      {ticker:<5} {state['composite']:<12} trend={state['structure']:<11} "
                f"momentum={state['momentum']:<15} vol={state['volatility']:<8} efficiency={state['efficiency']}"
            )

    print("  point-in-time rule:        STRICTLY PRIOR DATA ONLY")
    print("  threshold policy:          NOT YET LOCKED")
    print("  production regime policy:  NOT YET LOCKED")
    print(f"  report:                    {report.report_path}")
    print("  result:                    EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
