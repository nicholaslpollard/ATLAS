from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.input_inventory import (
    MARKET_PROXY_TICKERS,
    SECTOR_PROXY_TICKERS,
    RegimeInputInventory,
    complete_proxy_count,
)


def _pct(value: float) -> str:
    return f"{value * 100.0:6.2f}%"


def _number(value: float | None, digits: int = 4) -> str:
    return "missing" if value is None else f"{value:.{digits}f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory Phase 9 regime-engine inputs")
    parser.add_argument("--date", dest="as_of_date", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    report = RegimeInputInventory(load_settings(PROJECT_ROOT, "development")).build(args.as_of_date)
    breadth = report.breadth

    print("ATLAS Phase 9 Regime Input Inventory")
    print(f"  contract:                  {report.contract_version}")
    print(f"  as-of date:                {report.as_of_date}")
    print(f"  discovery state records:   {report.state_record_count:,}")
    print(f"  wall time:                 {report.wall_seconds:.3f}s")
    print("  raw discovery states:")
    for key, value in sorted(report.raw_state_counts.items()):
        print(f"    {key:<12} {value:>8,}")
    print("  effective discovery states:")
    for key, value in sorted(report.effective_state_counts.items()):
        print(f"    {key:<12} {value:>8,}")
    print("  discovery directions:")
    for key, value in sorted(report.direction_counts.items()):
        print(f"    {key:<12} {value:>8,}")

    print("  broad-market daily breadth:")
    print(f"    exact daily joins:       {breadth.daily_join_count:,}/{breadth.population_count:,}")
    for label in (
        "close_above_ema_20",
        "close_above_ema_50",
        "close_above_ema_200",
        "ema_20_above_ema_50",
        "ema_50_above_ema_200",
        "positive_return_1",
        "negative_return_1",
        "rsi_above_50",
        "rsi_below_50",
        "macd_hist_positive",
        "macd_hist_negative",
    ):
        count = getattr(breadth, label)
        print(f"    {label:<24} {count:>8,}  {_pct(breadth.percentages[label])}")

    print("  market proxy coverage/evidence:")
    for ticker in MARKET_PROXY_TICKERS:
        proxy = report.market_proxies[ticker]
        coverage = (
            f"1d-bar={'Y' if proxy.has_daily_bar else 'N'} "
            f"1d-feat={'Y' if proxy.has_daily_feature else 'N'} "
            f"4h-reg={'Y' if proxy.has_regular_4h_feature else 'N'} "
            f"1h-reg={'Y' if proxy.has_regular_1h_feature else 'N'}"
        )
        print(
            f"    {ticker:<5} {coverage} close={_number(proxy.close, 2):>10} "
            f"ret1={_number(proxy.return_1):>10} rsi14={_number(proxy.rsi_14, 2):>8} "
            f"natr14={_number(proxy.natr_14):>10}"
        )
    print(
        f"    complete market proxies: {complete_proxy_count(report.market_proxies)}/{len(MARKET_PROXY_TICKERS)}"
    )

    print("  sector proxy coverage/evidence:")
    for ticker in SECTOR_PROXY_TICKERS:
        proxy = report.sector_proxies[ticker]
        coverage = (
            f"1d-bar={'Y' if proxy.has_daily_bar else 'N'} "
            f"1d-feat={'Y' if proxy.has_daily_feature else 'N'} "
            f"4h-reg={'Y' if proxy.has_regular_4h_feature else 'N'} "
            f"1h-reg={'Y' if proxy.has_regular_1h_feature else 'N'}"
        )
        print(
            f"    {ticker:<5} {coverage} close={_number(proxy.close, 2):>10} "
            f"ret1={_number(proxy.return_1):>10} rsi14={_number(proxy.rsi_14, 2):>8} "
            f"natr14={_number(proxy.natr_14):>10}"
        )
    print(
        f"    complete sector proxies: {complete_proxy_count(report.sector_proxies)}/{len(SECTOR_PROXY_TICKERS)}"
    )

    print("  local sector/industry classification fields:")
    for source, columns in report.classification_columns.items():
        rendered = ", ".join(columns) if columns else "none"
        print(f"    {source:<10} {rendered}")
    print(f"    mapping ready:            {report.local_sector_mapping_ready}")
    print(f"  report:                    {report.report_path}")
    print("  result:                    PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
