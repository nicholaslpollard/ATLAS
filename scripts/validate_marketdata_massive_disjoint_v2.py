from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_massive_disjoint_validation_v2 import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_marketdata_massive_disjoint_validation_v2,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preregistered activity-aware disjoint MarketData x Massive "
            "EOD option validation V2."
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
            "read-only V2 validation."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")
    print("ATLAS MarketData x Massive Activity-Aware Disjoint EOD Validation V2")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print(
        "  validation anchors: "
        + ", ".join(
            f"{item['root']}@{item['date']}"
            for item in CONTRACT["validation_anchors"]
        )
    )
    print("  prior cross-provider roots reused: 0")
    print("  prior cross-provider dates reused: 0")
    print("  MarketData expected reads: 12 / 6 chains + 6 quote series")
    print("  Massive expected reads: 6 / exact contract / 1Day / adjusted=false")
    print("  activity rule: volume>0 => Massive bar required; volume=0 => Massive bar absent")
    print("  zero-volume MarketData last: excluded from price validation")
    print("  thresholds: preregistered and binding")
    print("  provider writes: 0")
    print("  bid/ask/intraday/execution/PAPER/LIVE/order authority: false")
    for key, value in CONTRACT["preregistered_thresholds"].items():
        print(f"    {key}: {value}")

    report = run_marketdata_massive_disjoint_validation_v2(settings)

    print("\nMARKETDATA x MASSIVE V2 VALIDATION: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(
        f"  anchor pass count: {report['anchor_pass_count']}/"
        f"{CONTRACT['preregistered_thresholds']['required_anchor_count']}"
    )
    print(f"  total zero-volume sessions: {report['total_zero_volume_sessions']}")
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
        activity = item.get("activity") or {}
        summary = item.get("summary") or {}
        print(
            "  "
            f"{item.get('root')} {item.get('option_symbol')}: "
            f"passed={item.get('passed')} "
            f"md_rows={item.get('marketdata_quote_rows')} "
            f"positive={activity.get('positive_volume_session_count')} "
            f"zero={activity.get('zero_volume_session_count')} "
            f"massive_rows={item.get('massive_aggregate_rows')} "
            f"activity={_fmt(activity.get('activity_concordance_rate'))} "
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
        "  authority: positive-volume EOD last/volume semantics only if PASS; "
        "zero-volume last, bid/ask, intraday, execution, simulator, strategy, "
        "PAPER and LIVE remain closed"
    )
    return 0 if report["validation_passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
