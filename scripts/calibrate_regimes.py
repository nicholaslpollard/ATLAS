from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.regimes.calibration import RegimeCalibration


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100.0:6.2f}%"


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.6f}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure historical Phase 9 regime distributions before thresholds are locked"
    )
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    args = parser.parse_args()

    report = RegimeCalibration(load_settings(PROJECT_ROOT, "development")).build(
        args.start,
        args.end,
    )

    print("ATLAS Phase 9 Regime Calibration Evidence")
    print(f"  contract:                  {report.contract_version}")
    print(f"  requested range:           {report.start_date} -> {report.end_date}")
    print(f"  XNYS sessions:             {report.requested_session_count:,}")
    print(f"  1d feature manifests:      {report.feature_manifest_count:,}")
    print(f"  usable breadth sessions:   {report.usable_breadth_session_count:,}")
    print(f"  usable breadth range:      {report.first_usable_breadth_date} -> {report.last_usable_breadth_date}")
    print(f"  activity floor:            ${report.minimum_dollar_volume:,.0f} daily dollar volume")
    print(f"  wall time:                 {report.wall_seconds:.3f}s")

    print("  historical breadth quantiles (p10 / p50 / p90):")
    for metric, values in report.breadth_metric_quantiles.items():
        print(
            f"    {metric:<28} {_pct(values['p10'])} / {_pct(values['p50'])} / {_pct(values['p90'])}"
        )

    print("  end-date calibration breadth:")
    print(f"    trading_date               {report.end_date_breadth['trading_date']}")
    print(f"    participant_count          {report.end_date_breadth['participant_count']}")
    for metric in (
        "close_above_ema_20",
        "close_above_ema_50",
        "close_above_ema_200",
        "positive_return_1",
        "rsi_above_50",
        "macd_hist_positive",
    ):
        print(f"    {metric:<28} {_pct(report.end_date_breadth[metric])}")

    print("  market proxy observations:")
    for ticker, count in report.market_proxy_observation_counts.items():
        print(f"    {ticker:<5} {count:>5,}")

    print("  market-basket historical quantiles (p10 / p50 / p90):")
    for metric in (
        "fraction_above_ema_50",
        "fraction_above_ema_200",
        "fraction_positive_return_1",
        "fraction_rsi_above_50",
        "fraction_macd_hist_positive",
        "median_natr_14",
    ):
        values = report.market_basket_metric_quantiles[metric]
        formatter = _pct if metric.startswith("fraction_") else _num
        print(
            f"    {metric:<34} {formatter(values['p10'])} / {formatter(values['p50'])} / {formatter(values['p90'])}"
        )

    print("  sector proxy observations:")
    for ticker, count in report.sector_proxy_observation_counts.items():
        print(f"    {ticker:<5} {count:>5,}")

    print("  sector-basket historical quantiles (p10 / p50 / p90):")
    for metric in (
        "fraction_above_ema_50",
        "fraction_above_ema_200",
        "fraction_positive_return_1",
        "fraction_rsi_above_50",
        "fraction_macd_hist_positive",
        "median_natr_14",
    ):
        values = report.sector_basket_metric_quantiles[metric]
        formatter = _pct if metric.startswith("fraction_") else _num
        print(
            f"    {metric:<34} {formatter(values['p10'])} / {formatter(values['p50'])} / {formatter(values['p90'])}"
        )

    print("  regime thresholds:         NOT YET LOCKED")
    print(f"  report:                    {report.report_path}")
    print("  result:                    EVIDENCE CAPTURED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
