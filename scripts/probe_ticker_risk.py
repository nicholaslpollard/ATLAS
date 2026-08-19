from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_risk_probe import TickerRiskProbe


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 9 Gate 11 self-relative ticker diagnostics.")
    parser.add_argument("--as-of", required=True, help="Finalized/as-of session YYYY-MM-DD")
    return parser


def _pct(value: float | int | None) -> str:
    return "n/a" if value is None else f"{float(value) * 100.0:,.2f}%"


def main(argv: list[str] | None = None) -> int:
    from datetime import date

    args = build_parser().parse_args(argv)
    as_of = date.fromisoformat(args.as_of)
    report = TickerRiskProbe(load_settings(PROJECT_ROOT, "development")).run(as_of)

    print("ATLAS Phase 9 Gate 11 Ticker Self-Relative Risk Probe")
    print(f"  contract:                       {report.contract_version}")
    print(f"  as-of session:                  {report.as_of_date}")
    print(f"  probe status:                   {report.probe_status}")
    print(f"  routed population:              {report.route_population_count:,}")
    print(f"  identity-safe history:          {report.identity_safe_history_instrument_count:,}")
    print(f"  identity-blocked history:       {report.identity_blocked_history_instrument_count:,}")
    print(f"  exact as-of risk metrics:       {report.current_metric_instrument_count:,}")
    print(f"  missing exact as-of metrics:    {report.missing_current_metric_instrument_count:,}")
    print("  prior-only lookback coverage:")
    for window in report.lookback_windows:
        print(f"    {window:>3} sessions:                {report.coverage_by_window[str(window)]:,}")
    print(
        f"  current metrics but <{report.lookback_windows[0]} prior: "
        f"{report.insufficient_for_shortest_window_count:,}"
    )

    print("  candidate self-relative windows:")
    for window in report.lookback_windows:
        candidate = report.candidate_windows[str(window)]
        print(f"    {window} prior sessions")
        print(f"      eligible:                   {int(candidate['eligible_instrument_count']):,}")
        print(f"      risk states:                {candidate['risk_state_counts']}")
        print(f"      efficiency states:          {candidate['efficiency_state_counts']}")
        if window != 252:
            risk = candidate["risk_agreement_vs_252"]
            efficiency = candidate["efficiency_agreement_vs_252"]
            print(
                f"      risk vs 252:                n={int(risk['comparison_count']):,} "
                f"exact={_pct(risk['exact_agreement_rate'])} "
                f"within1={_pct(risk['within_one_level_rate'])} "
                f"distance>=2={_pct(risk['two_or_more_level_mismatch_rate'])}"
            )
            print(
                f"      efficiency vs 252:          n={int(efficiency['comparison_count']):,} "
                f"exact={_pct(efficiency['exact_agreement_rate'])} "
                f"within1={_pct(efficiency['within_one_level_rate'])} "
                f"distance>=2={_pct(efficiency['two_or_more_level_mismatch_rate'])}"
            )
            print(f"      combined exact vs 252:      {_pct(candidate['combined_exact_agreement_vs_252'])}")

    print("  threshold basis:                TICKER-SELF-RELATIVE / PRIOR-ONLY")
    print("  current observation in window:  EXCLUDED")
    print("  history safety:                 GATE-9 OPERATIONAL CURRENT-ALIAS ONLY")
    print("  ticker-text splice:             NONE")
    print("  risk/volatility policy:         NOT YET LOCKED")
    print(f"  wall time:                      {report.wall_seconds:,.3f}s")
    print(f"  report:                         {Path(report.report_path).resolve()}")
    print("  result:                         EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
