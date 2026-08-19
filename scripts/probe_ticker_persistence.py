from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_persistence_probe import TickerPersistenceProbe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure Gate-9-safe ticker-regime chatter and candidate persistence policies."
    )
    parser.add_argument("--as-of", required=True, help="Finalized/as-of session YYYY-MM-DD")
    return parser


def _pct(value: float | int | None) -> str:
    return "n/a" if value is None else f"{float(value) * 100.0:,.2f}%"


def main(argv: list[str] | None = None) -> int:
    from datetime import date

    args = build_parser().parse_args(argv)
    as_of = date.fromisoformat(args.as_of)
    report = TickerPersistenceProbe(load_settings(PROJECT_ROOT, "development")).run(as_of)

    print("ATLAS Phase 9 Gate 10 Ticker Persistence Probe")
    print(f"  contract:                       {report.contract_version}")
    print(f"  as-of session:                  {report.as_of_date}")
    print(f"  probe status:                   {report.probe_status}")
    print(f"  routed population:              {report.route_population_count:,}")
    print(f"  identity-safe history:          {report.identity_safe_history_instrument_count:,}")
    print(f"  identity-blocked history:       {report.identity_blocked_history_instrument_count:,}")
    print(f"  analyzable history (>=2):       {report.analyzable_history_instrument_count:,}")
    print(f"  identity-safe but <2 depth:     {report.insufficient_depth_instrument_count:,}")
    print(f"  state instruments:              {report.state_instrument_count:,}")
    print(f"  state observations:             {report.state_observation_count:,}")
    print(f"  max history/instrument:         {report.max_history_sessions:,}")
    print("  state depth:")
    for key, value in report.state_depth_counts.items():
        print(f"    {key:<6} {value:>8,}")

    raw = report.raw_state_diagnostics
    print("  raw ticker-state stability:")
    print(f"    transition rate:              {_pct(raw['transition_rate'])}")
    print(f"    median sequence transition:   {_pct(raw['median_sequence_transition_rate'])}")
    print(f"    median run length:            {raw['median_run_length']}")
    print(f"    one-session run share:        {_pct(raw['one_session_run_share'])}")
    print(f"    A->B->A flipbacks:            {int(raw['aba_flipback_count'] or 0):,}")
    print(f"    flipbacks / transitions:      {_pct(raw['aba_flipback_per_transition'])}")

    print("  raw dimension transition rates:")
    for dimension, diagnostics in report.raw_dimension_diagnostics.items():
        print(
            f"    {dimension:<18} transition={_pct(diagnostics['transition_rate'])} "
            f"one-session={_pct(diagnostics['one_session_run_share'])} "
            f"median-run={diagnostics['median_run_length']}"
        )

    print("  candidate persistence policies:")
    for name, diagnostics in report.candidate_policies.items():
        print(f"    {name}")
        print(
            f"      transition={_pct(diagnostics['transition_rate'])} "
            f"reduction={_pct(diagnostics['transition_reduction_rate'])} "
            f"one-session={_pct(diagnostics['one_session_run_share'])}"
        )
        print(
            f"      exact agreement={_pct(diagnostics['exact_agreement_rate'])} "
            f"family agreement={_pct(diagnostics['direction_family_agreement_rate'])} "
            f"opposite mismatch={_pct(diagnostics['opposite_direction_mismatch_rate'])}"
        )
        print(
            f"      median-run={diagnostics['median_run_length']} "
            f"flipbacks={int(diagnostics['aba_flipback_count'] or 0):,}"
        )

    print("  top raw transitions:")
    for item in report.top_raw_transitions[:12]:
        print(f"    {item['from']:<20} -> {item['to']:<20} {int(item['count']):,}")

    print("  history safety:                 GATE-9 OPERATIONAL CURRENT-ALIAS ONLY")
    print("  missing-session handling:       RESET CONFIRMATION / NO FABRICATED STREAK")
    print("  ticker-text splice:             NONE")
    print("  persistence policy:             NOT YET LOCKED")
    print(f"  wall time:                      {report.wall_seconds:,.3f}s")
    print(f"  report:                         {Path(report.report_path).resolve()}")
    print("  result:                         EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
