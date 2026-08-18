from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.ticker_history_probe import (
    TICKER_HISTORY_DEPTH_GRID,
    TICKER_HISTORY_PROBE_CONTRACT_VERSION,
    TickerHistoryProbe,
)


def _depth_line(values: dict[str, int]) -> str:
    return ", ".join(
        f"{key}={values[key]:,}"
        for key in (f">={n}" for n in TICKER_HISTORY_DEPTH_GRID)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe operational current-alias and authoritative current-interval "
            "history depth for Phase 9 ticker regimes"
        )
    )
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    report = TickerHistoryProbe(load_settings(PROJECT_ROOT, "development")).run(args.as_of)

    print("ATLAS Phase 9 Ticker History Depth Probe v2")
    print(f"  contract:                         {TICKER_HISTORY_PROBE_CONTRACT_VERSION}")
    print(f"  as-of session:                    {report.as_of_date}")
    print(f"  probe status:                     {report.probe_status}")
    print(f"  routed ticker-regime population:  {report.route_population_count:>8,}")
    print(f"    Phase 8 discovery state          {report.discovery_count:>8,}")
    print(f"    POSITION route                   {report.position_count:>8,}")
    print(f"    WATCHLIST route                  {report.watchlist_count:>8,}")
    print(f"    CUSTOM route                     {report.custom_count:>8,}")
    print("  identity inventory:")
    print(f"    single observed alias            {report.identity_single_alias_count:>8,}")
    print(f"    multiple observed aliases        {report.identity_multi_alias_count:>8,}")
    print(f"    exact current alias observation  {report.current_alias_observation_count:>8,}")
    print(f"    current ticker reused by IDs     {report.current_ticker_reuse_count:>8,}")
    print(f"    exact current auth interval      {report.authoritative_current_interval_count:>8,}")
    print(f"    ambiguous current auth interval  {report.ambiguous_authoritative_current_interval_count:>8,}")
    print("  history status:")
    for status, count in report.history_status_counts.items():
        print(f"    {status:<32} {count:>8,}")
    print("  raw current-alias complete-history depth (diagnostic only):")
    print(f"    {_depth_line(report.raw_current_alias_depth_counts)}")
    print("  operational current-alias depth:")
    print(f"    {_depth_line(report.operational_current_alias_depth_counts)}")
    print("  authoritative current-interval depth:")
    print(f"    {_depth_line(report.authoritative_interval_depth_counts)}")
    print("  depth by history status:")
    for status, values in report.depth_by_status.items():
        operational = values["operational"]
        authoritative = values["authoritative"]
        print(
            f"    {status:<32} n={values['instrument_count']:>6,} "
            f"oper>=2={operational['>=2']:>6,} oper>=20={operational['>=20']:>6,} "
            f"oper>=252={operational['>=252']:>6,} auth>=20={authoritative['>=20']:>6,} "
            f"auth>=252={authoritative['>=252']:>6,}"
        )
    if report.unresolved_multi_alias_examples:
        print("  unresolved multi-alias examples:")
        for item in report.unresolved_multi_alias_examples[:10]:
            print(
                f"    {item['ticker']:<12} aliases={item['alias_count']} "
                f"raw_depth={item['raw_current_alias_depth']} id={item['instrument_id']}"
            )
    if report.unresolved_ticker_reuse_examples:
        print("  unresolved ticker-reuse examples:")
        for item in report.unresolved_ticker_reuse_examples[:10]:
            print(
                f"    {item['ticker']:<12} identities={item['reuse_identity_count']} "
                f"raw_depth={item['raw_current_alias_depth']} id={item['instrument_id']}"
            )
    print("  sparse reference date bound:      RETIRED")
    print("  authority precedence:             EXACT CURRENT INTERVAL WINS")
    print("  history rule:                     NO TICKER-TEXT SPLICE")
    print("  ticker persistence policy:        NOT YET LOCKED")
    print("  per-ticker risk calibration:      NOT YET LOCKED")
    print(f"  wall time:                        {report.wall_seconds:.3f}s")
    print(f"  report:                           {report.report_path}")
    print("  result:                           EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
