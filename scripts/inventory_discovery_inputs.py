from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.discovery.input_inventory import (
    DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION,
    DiscoveryInputInventory,
    QuantileSummary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure Phase 8 universe/feature coverage and activity distributions."
    )
    parser.add_argument("--date", required=True, type=date.fromisoformat, dest="as_of_date")
    return parser.parse_args()


def _fmt_number(value: float | None) -> str:
    if value is None:
        return "n/a"
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{value / 1_000_000_000:.3f}b"
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:.3f}m"
    if absolute >= 1_000:
        return f"{value / 1_000:.3f}k"
    return f"{value:.6g}"


def _print_quantile(name: str, summary: QuantileSummary) -> None:
    print(
        f"    {name:<28} "
        f"n={summary.finite_count:>6,} missing={summary.missing_or_nonfinite_count:>5,} "
        f"p10={_fmt_number(summary.p10):>10} "
        f"p25={_fmt_number(summary.p25):>10} "
        f"p50={_fmt_number(summary.p50):>10} "
        f"p75={_fmt_number(summary.p75):>10} "
        f"p90={_fmt_number(summary.p90):>10} "
        f"p95={_fmt_number(summary.p95):>10}"
    )


def main() -> int:
    args = parse_args()
    settings = load_settings(PROJECT_ROOT, "development")
    report = DiscoveryInputInventory(settings).run(args.as_of_date)

    print("ATLAS Phase 8 Discovery Input Inventory")
    print(f"  contract:             {DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION}")
    print(f"  as-of date:           {report.as_of_date}")
    print(f"  discovery universe:   {report.universe_count:,}")
    print(f"  duplicate tickers:    {report.duplicate_universe_tickers:,}")
    print(f"  wall time:            {report.wall_seconds:.3f}s")

    print("\n  feature coverage")
    for timeframe in ("1d", "4h", "1h"):
        item = report.coverage[timeframe]
        print(
            f"    {timeframe:<3} rows={item.total_feature_rows:>9,} "
            f"symbols={item.distinct_feature_symbols:>6,} "
            f"matched={item.matched_universe_symbols:>6,} "
            f"missing={item.missing_universe_symbols:>5,}"
        )
        if item.regular_session_symbols is not None:
            print(
                f"        segment symbols: regular={item.regular_session_symbols:,} "
                f"premarket={item.premarket_symbols:,} after_hours={item.after_hours_symbols:,}"
            )

    print("\n  daily data quality")
    for key, value in report.daily_quality.items():
        print(f"    {key:<38} {value:>8,}")

    print("\n  daily activity distributions")
    for metric in DiscoveryInputInventory.DAILY_METRICS:
        _print_quantile(metric, report.quantiles[metric])

    print("\n  standalone threshold population")
    for metric, counts in report.threshold_counts.items():
        print(f"    {metric}")
        for label, count in counts.items():
            print(f"      {label:<12} {count:>8,}")

    print("\n  combined close + dollar-volume population")
    for label, count in report.combined_activity_counts.items():
        print(f"    {label:<36} {count:>8,}")

    print(f"\n  report:               {report.report_path}")
    print("  result:               PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
