from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.persistence_probe import RegimePersistenceProbe


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100.0:6.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare Phase 9 2-session and 3-session dimensional persistence candidates"
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    report = RegimePersistenceProbe(load_settings(PROJECT_ROOT, "development")).build(
        args.start,
        args.end,
    )

    print("ATLAS Phase 9 Regime Persistence Probe")
    print(f"  contract:                  {report.contract_version}")
    print(f"  raw policy contract:       {report.policy_probe_contract_version}")
    print(f"  requested range:           {report.start_date} -> {report.end_date}")
    print(f"  probe status:              {report.probe_status}")
    print(f"  confirmation windows:      {', '.join(str(v) for v in report.confirmation_windows)} sessions")
    print(f"  market sessions:           {report.market_session_count:,}")
    print(f"  sector observations:       {report.sector_observation_count:,}")
    print(f"  wall time:                 {report.wall_seconds:.3f}s")

    raw_market = report.raw_market_transition_diagnostics
    print("  raw market baseline:")
    print(f"    transition_rate            {_pct(raw_market['transition_rate'])}")
    print(f"    median_run_length          {raw_market['median_run_length']}")
    print(f"    one_day_run_share          {_pct(raw_market['one_day_run_share'])}")

    raw_sector = report.raw_sector_transition_summary
    print("  raw sector baseline:")
    print(f"    mean_transition_rate       {_pct(raw_sector['mean_transition_rate'])}")
    print(f"    median_transition_rate     {_pct(raw_sector['median_transition_rate'])}")
    print(f"    max_transition_rate        {_pct(raw_sector['max_transition_rate'])}")
    print(f"    median_run_length          {raw_sector['median_of_median_run_lengths']}")
    print(f"    mean_one_day_run_share     {_pct(raw_sector['mean_one_day_run_share'])}")

    for key, candidate in report.market_candidates.items():
        diag = candidate["transition_diagnostics"]
        agreement = candidate["agreement"]
        end_state = candidate["end_date_state"]
        print(f"  market candidate {key}:")
        print(f"    max_confirmation_lag       {candidate['maximum_confirmation_lag_sessions']} session(s)")
        print(f"    transition_rate            {_pct(diag['transition_rate'])}")
        print(f"    transition_rate_reduction  {_pct(candidate['transition_rate_reduction'])}")
        print(f"    median_run_length          {diag['median_run_length']}")
        print(f"    one_day_run_share          {_pct(diag['one_day_run_share'])}")
        print(f"    exact_raw_agreement        {_pct(agreement['exact_agreement_rate'])}")
        print(f"    family_raw_agreement       {_pct(agreement['direction_family_agreement_rate'])}")
        print(f"    opposite_direction_lag     {_pct(agreement['opposite_direction_mismatch_rate'])}")
        print(
            "    end_state                   "
            f"{end_state['composite']} | trend={end_state['structure']} "
            f"momentum={end_state['momentum']} participation={end_state['participation']} "
            f"vol={end_state['volatility']} efficiency={end_state['efficiency']}"
        )

    for key, candidate in report.sector_candidates.items():
        summary = candidate["transition_summary"]
        agreement = candidate["agreement"]
        print(f"  sector candidate {key}:")
        print(f"    max_confirmation_lag       {candidate['maximum_confirmation_lag_sessions']} session(s)")
        print(f"    mean_transition_rate       {_pct(summary['mean_transition_rate'])}")
        print(f"    transition_rate_reduction  {_pct(candidate['mean_transition_rate_reduction'])}")
        print(f"    median_transition_rate     {_pct(summary['median_transition_rate'])}")
        print(f"    max_transition_rate        {_pct(summary['max_transition_rate'])}")
        print(f"    median_run_length          {summary['median_of_median_run_lengths']}")
        print(f"    mean_one_day_run_share     {_pct(summary['mean_one_day_run_share'])}")
        print(f"    exact_raw_agreement        {_pct(agreement['exact_agreement_rate'])}")
        print(f"    family_raw_agreement       {_pct(agreement['direction_family_agreement_rate'])}")
        print(f"    opposite_direction_lag     {_pct(agreement['opposite_direction_mismatch_rate'])}")
        print("    end-date sector states:")
        for ticker, state in candidate["end_date_states"].items():
            transition = candidate["per_sector_transition_diagnostics"][ticker]
            print(
                f"      {ticker:<5} {state['composite']:<12} trend={state['structure']:<11} "
                f"momentum={state['momentum']:<15} vol={state['volatility']:<8} "
                f"rate={_pct(transition['transition_rate'])} median_run={transition['median_run_length']}"
            )

    print("  persistence policy:       NOT YET LOCKED")
    print("  point-in-time thresholds: STILL REQUIRED AFTER PERSISTENCE SELECTION")
    print(f"  report:                   {report.report_path}")
    print("  result:                   EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
