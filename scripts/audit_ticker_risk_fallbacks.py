from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_risk_fallback_audit import TickerRiskFallbackAudit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit Gate 11 shorter-window risk severity errors and history cohorts."
    )
    parser.add_argument("--as-of", required=True, help="Finalized/as-of session YYYY-MM-DD")
    return parser


def _pct(value: float | int | None) -> str:
    return "n/a" if value is None else f"{float(value) * 100.0:,.2f}%"


def _print_diag(label: str, diag: dict[str, float | int | None]) -> None:
    print(f"    {label}")
    print(
        f"      n={int(diag['comparison_count'] or 0):,} "
        f"exact={_pct(diag['exact_rate'])} "
        f"under1={_pct(diag['under_one_rate'])} "
        f"under>=2={_pct(diag['under_two_plus_rate'])} "
        f"over1={_pct(diag['over_one_rate'])} "
        f"over>=2={_pct(diag['over_two_plus_rate'])}"
    )
    print(
        f"      stressed->CALM/NORMAL: "
        f"{int(diag['stressed_as_calm_or_normal_count'] or 0):,} / "
        f"{int(diag.get('stressed_reference_count') or 0):,} "
        f"({_pct(diag['stressed_as_calm_or_normal_rate'])})"
    )


def main(argv: list[str] | None = None) -> int:
    from datetime import date

    args = build_parser().parse_args(argv)
    as_of = date.fromisoformat(args.as_of)
    report = TickerRiskFallbackAudit(load_settings(PROJECT_ROOT, "development")).run(as_of)

    print("ATLAS Phase 9 Gate 11 Ticker Risk Fallback Audit")
    print(f"  contract:                       {report.contract_version}")
    print(f"  as-of session:                  {report.as_of_date}")
    print(f"  audit status:                   {report.audit_status}")
    print(f"  routed population:              {report.route_population_count:,}")
    print(f"  identity-safe history:          {report.identity_safe_history_instrument_count:,}")
    print(f"  identity-blocked history:       {report.identity_blocked_history_instrument_count:,}")
    print(f"  exact current metrics:          {report.exact_current_metric_count:,}")
    print(f"  missing exact current metrics:  {report.missing_exact_current_metric_count:,}")
    print("  current-metric history cohorts:")
    for label, count in report.history_cohort_counts.items():
        print(f"    {label:<8} {count:>8,}")

    print("  directional risk mismatch vs 252-session reference:")
    for window in (20, 60, 126):
        _print_diag(f"{window} vs 252", report.risk_direction_vs_252[str(window)])

    print("  shorter-window mismatch vs 126-session candidate:")
    for window in (20, 60):
        _print_diag(f"{window} vs 126", report.risk_direction_vs_126[str(window)])

    print("  threshold basis:                TICKER-SELF-RELATIVE / PRIOR-ONLY")
    print("  current observation in window:  EXCLUDED")
    print("  history safety:                 GATE-9 OPERATIONAL CURRENT-ALIAS ONLY")
    print("  ticker-text splice:             NONE")
    print("  Gate 11 policy:                 NOT YET LOCKED")
    print(f"  wall time:                      {report.wall_seconds:,.3f}s")
    print(f"  report:                         {Path(report.report_path).resolve()}")
    print("  result:                         EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
