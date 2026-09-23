from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_massive_disjoint_validation_v1 import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_marketdata_massive_disjoint_validation_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preregistered disjoint MarketData x Massive EOD option "
            "last/volume validation."
        )
    )
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help=(
            "Required explicit authorization for bounded MarketData and Massive "
            "read-only validation calls."
        ),
    )
    return parser


def _fmt(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, float):
        return f"{value:.8f}"
    return str(value)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit the bounded "
            "read-only disjoint validation."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")
    print("ATLAS MarketData x Massive Disjoint EOD Validation V1")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print(
        "  calibration evidence: "
        f"{CONTRACT['calibration_evidence']['run_id']} / "
        f"{CONTRACT['calibration_evidence']['evidence_fingerprint']}"
    )
    print(
        "  disjoint anchors: "
        + ", ".join(
            f"{item['root']}@{item['date']}"
            for item in CONTRACT["validation_anchors"]
        )
    )
    print("  MarketData expected reads: 8 / 4 chains + 4 quote series")
    print("  Massive expected reads: 4 / exact contract / 1Day / adjusted=false")
    print("  calibration contracts reused: 0")
    print("  thresholds: preregistered and binding")
    print("  provider writes: 0")
    print("  bid/ask/intraday/execution/PAPER/LIVE/order authority: false")

    thresholds = CONTRACT["preregistered_thresholds"]
    for key, value in thresholds.items():
        print(f"    {key}: {value}")

    report = run_marketdata_massive_disjoint_validation_v1(settings)

    print("\nMARKETDATA x MASSIVE VALIDATION: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(f"  anchor pass count: {report['anchor_pass_count']}/4")
    aggregate = dict(report["aggregate_summary"])
    print(
        "  aggregate exact last/close match rate (descriptive): "
        f"{_fmt(aggregate.get('exact_price_match_rate'))}"
    )
    print(
        "  aggregate median/max relative last-close diff: "
        f"{_fmt(aggregate.get('median_price_rel_diff'))} / "
        f"{_fmt(aggregate.get('max_price_rel_diff'))}"
    )
    print(
        "  aggregate last-inside-range rate: "
        f"{_fmt(aggregate.get('marketdata_last_inside_massive_range_rate'))}"
    )
    print(
        "  aggregate median/max volume relative diff: "
        f"{_fmt(aggregate.get('median_volume_rel_diff'))} / "
        f"{_fmt(aggregate.get('max_volume_rel_diff'))}"
    )
    print("  aggregate checks:")
    for key, value in report["aggregate_checks"].items():
        print(f"    {key}: {value}")
    print(
        "  observed MarketData API credits consumed: "
        f"{report['observed_marketdata_api_credits_consumed']}"
    )
    print(
        "  last observed MarketData API credits remaining: "
        f"{report['last_observed_marketdata_api_credits_remaining']}"
    )

    for item in report["anchors"]:
        summary = item.get("summary") or {}
        print(
            "  "
            f"{item.get('root')} {item.get('option_symbol')}: "
            f"passed={item.get('passed')} "
            f"md_rows={item.get('marketdata_quote_rows')} "
            f"massive_rows={item.get('massive_aggregate_rows')} "
            f"overlap={item.get('overlap_sessions')} "
            f"coverage={_fmt(item.get('overlap_coverage_rate'))} "
            f"inside_range={_fmt(summary.get('marketdata_last_inside_massive_range_rate'))} "
            f"median_price_rel={_fmt(summary.get('median_price_rel_diff'))} "
            f"median_volume_rel={_fmt(summary.get('median_volume_rel_diff'))} "
            f"error={item.get('error')}"
        )
        for key, value in (item.get("checks") or {}).items():
            print(f"      {key}: {value}")

    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: EOD last/volume semantic validation only if PASS; "
        "bid/ask, intraday, execution, simulator, strategy, PAPER and LIVE remain closed"
    )
    return 0 if report["validation_passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
