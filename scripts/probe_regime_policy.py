from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.policy_probe import RegimePolicyProbe


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100.0:6.2f}%"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe the first Phase 9 candidate regime policy before hysteresis/thresholds are locked"
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    report = RegimePolicyProbe(load_settings(PROJECT_ROOT, "development")).build(
        args.start,
        args.end,
    )

    print("ATLAS Phase 9 Candidate Regime Policy Probe")
    print(f"  contract:                  {report.contract_version}")
    print(f"  calibration contract:      {report.calibration_contract_version}")
    print(f"  requested range:           {report.start_date} -> {report.end_date}")
    print(f"  policy status:             {report.policy_status}")
    print(f"  market sessions:           {report.market_session_count:,}")
    print(f"  wall time:                 {report.wall_seconds:.3f}s")

    print("  market composite states:")
    for state, count in report.market_state_counts.items():
        print(
            f"    {state:<14} {count:>5,}  {_pct(report.market_state_percentages[state])}"
        )

    print("  market dimensions:")
    for dimension, counts in report.market_dimension_counts.items():
        rendered = ", ".join(f"{state}={count:,}" for state, count in counts.items())
        print(f"    {dimension:<14} {rendered}")

    market_diag = report.market_transition_diagnostics
    print("  market raw transition diagnostics:")
    print(f"    transitions                {market_diag['transition_count']:,}")
    print(f"    transition_rate            {_pct(market_diag['transition_rate'])}")
    print(f"    runs                       {market_diag['run_count']:,}")
    print(f"    median_run_length          {market_diag['median_run_length']}")
    print(f"    one_day_runs               {market_diag['one_day_run_count']:,}")
    print(f"    one_day_run_share          {_pct(market_diag['one_day_run_share'])}")

    end_market = report.end_date_market_state
    print("  end-date market state:")
    print(f"    trading_date               {end_market['trading_date']}")
    print(f"    composite                  {end_market['composite']}")
    print(
        f"    structure                  {end_market['structure']} (score {end_market['structure_score']})"
    )
    print(
        f"    momentum                   {end_market['momentum']} (score {end_market['momentum_score']})"
    )
    print(f"    participation              {end_market['participation']}")
    print(f"    volatility                 {end_market['volatility']}")
    print(f"    efficiency                 {end_market['efficiency']}")

    print(f"  sector observations:       {report.sector_observation_count:,}")
    print("  sector aggregate composite states:")
    for state, count in report.sector_state_counts.items():
        print(
            f"    {state:<14} {count:>6,}  {_pct(report.sector_state_percentages[state])}"
        )

    print("  end-date sector proxy states:")
    for ticker, state in report.end_date_sector_states.items():
        transition = report.sector_transition_diagnostics[ticker]
        print(
            f"    {ticker:<5} {state['composite']:<12} "
            f"trend={state['structure']:<11} momentum={state['momentum']:<15} "
            f"vol={state['volatility']:<8} transitions={transition['transition_count']:,} "
            f"rate={_pct(transition['transition_rate'])} median_run={transition['median_run_length']}"
        )

    print("  threshold basis:          retrospective p25/p75 diagnostic bands")
    print("  hysteresis:               NONE; raw stability baseline")
    print("  production regime policy: NOT YET LOCKED")
    print(f"  report:                   {report.report_path}")
    print("  result:                   EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
