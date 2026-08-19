from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_probe import (
    TICKER_REGIME_PROBE_CONTRACT_VERSION,
    TICKER_REGIME_REQUIRED_HISTORY_SESSIONS,
    TickerRegimeProbe,
)


def _fmt_quantile(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Phase 9 ticker-regime inputs and candidate states")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    report = TickerRegimeProbe(load_settings(PROJECT_ROOT, "development")).run(args.as_of)

    print("ATLAS Phase 9 Ticker Regime Evidence Probe")
    print(f"  contract:                       {TICKER_REGIME_PROBE_CONTRACT_VERSION}")
    print(f"  as-of session:                  {report.as_of_date}")
    print(f"  probe status:                   {report.probe_status}")
    print(f"  routed ticker-regime population:{report.route_population_count:>10,}")
    print(f"    Phase 8 discovery state       {report.discovery_count:>10,}")
    print(f"    POSITION route                {report.position_count:>10,}")
    print(f"    WATCHLIST route               {report.watchlist_count:>10,}")
    print(f"    CUSTOM route                  {report.custom_count:>10,}")
    print(f"  duplicate current tickers:      {report.duplicate_current_tickers:>10,}")
    print("  identity continuity inventory:")
    print(f"    single observed alias         {report.identity_single_alias_count:>10,}")
    print(f"    multiple observed aliases     {report.identity_multi_alias_count:>10,}")
    print(f"    multi-alias + auth intervals  {report.authoritative_multi_alias_count:>10,}")
    print("  current timeframe coverage:")
    print(f"    1d                            {report.current_timeframe_coverage['1d']:>10,}")
    print(f"    4h regular                    {report.current_timeframe_coverage['4h_regular']:>10,}")
    print(f"    1h regular                    {report.current_timeframe_coverage['1h_regular']:>10,}")
    print(f"    all three                     {report.all_three_timeframe_count:>10,}")
    print("  single-alias self-history:")
    print(f"    >= {TICKER_REGIME_REQUIRED_HISTORY_SESSIONS} complete 1d sessions {report.single_alias_history_252_ready_count:>10,}")
    print(f"    <  {TICKER_REGIME_REQUIRED_HISTORY_SESSIONS} complete 1d sessions {report.single_alias_history_lt252_count:>10,}")
    print(f"    multi-alias continuity pending{report.multi_alias_requires_continuity_count:>10,}")
    print(f"  candidate state observations:   {report.candidate_state_count:>10,}")
    print("  candidate ticker states:")
    for state, count in report.candidate_state_counts.items():
        pct = 0.0 if report.candidate_state_count == 0 else count / report.candidate_state_count
        print(f"    {state:<20} {count:>7,}  {pct:>7.2%}")
    print("  daily structure:")
    for state, count in report.daily_structure_counts.items():
        print(f"    {state:<20} {count:>7,}")
    print("  4h/1h short alignment:")
    for state, count in report.short_alignment_counts.items():
        print(f"    {state:<20} {count:>7,}")
    print("  daily momentum:")
    for state, count in report.momentum_counts.items():
        print(f"    {state:<20} {count:>7,}")
    print("  cross-sectional risk evidence (diagnostic only):")
    for metric, quantiles in report.risk_metric_quantiles.items():
        print(
            f"    {metric:<28} "
            f"p10={_fmt_quantile(quantiles['p10'])} "
            f"p25={_fmt_quantile(quantiles['p25'])} "
            f"p50={_fmt_quantile(quantiles['p50'])} "
            f"p75={_fmt_quantile(quantiles['p75'])} "
            f"p90={_fmt_quantile(quantiles['p90'])}"
        )
    print("  ticker regime semantics:        CANDIDATE ONLY")
    print("  per-ticker risk thresholds:     NOT YET LOCKED")
    print("  multi-alias history splice:     NOT YET LOCKED")
    print(f"  wall time:                      {report.wall_seconds:.3f}s")
    print(f"  report:                         {report.report_path}")
    print("  result:                         EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
