from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_massive_overlap_v1 import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_marketdata_massive_overlap_diagnostic_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the accepted MarketData Starter Trial exact-contract EOD "
            "evidence with Massive option daily aggregates."
        )
    )
    parser.add_argument(
        "--authorize-massive-provider-reads",
        action="store_true",
        help="Required explicit authorization for four read-only Massive aggregate calls.",
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
    if not args.authorize_massive_provider_reads:
        print(
            "BLOCKED: pass --authorize-massive-provider-reads to permit the "
            "bounded read-only Massive overlap diagnostic."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")
    print("ATLAS MarketData x Massive Option EOD Overlap Diagnostic V1")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print(
        "  source MarketData evidence: "
        f"{CONTRACT['marketdata_source']['run_id']} / "
        f"{CONTRACT['marketdata_source']['evidence_fingerprint']}"
    )
    print(
        "  Massive comparison roots: "
        + ", ".join(CONTRACT["massive_source"]["comparison_roots"])
    )
    print("  Massive calls: 4 expected / exact contract / 1Day / adjusted=false")
    print("  MarketData calls: 0 / accepted local raw evidence is reused")
    print("  2021 AAPL: intentionally excluded from Massive Basic two-year REST scope")
    print("  thresholds: none; semantic calibration only")
    print("  provider writes: 0")
    print("  historical-price/PAPER/LIVE/order authority: false")

    report = run_marketdata_massive_overlap_diagnostic_v1(settings)

    print("\nMARKETDATA x MASSIVE OVERLAP: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    print(f"  total overlap sessions: {report['total_overlap_sessions']}")
    aggregate = dict(report["aggregate_summary"])
    print(
        "  aggregate exact last/close match rate: "
        f"{_fmt(aggregate.get('exact_price_match_rate'))}"
    )
    print(
        "  aggregate median/max absolute last-close diff: "
        f"{_fmt(aggregate.get('median_price_abs_diff'))} / "
        f"{_fmt(aggregate.get('max_price_abs_diff'))}"
    )
    print(
        "  MarketData last inside Massive daily range rate: "
        f"{_fmt(aggregate.get('marketdata_last_inside_massive_range_rate'))}"
    )
    print(
        "  aggregate median/max volume relative diff: "
        f"{_fmt(aggregate.get('median_volume_rel_diff'))} / "
        f"{_fmt(aggregate.get('max_volume_rel_diff'))}"
    )

    for item in report["anchors"]:
        summary = item.get("summary") or {}
        print(
            "  "
            f"{item.get('root')} {item.get('option_symbol')}: "
            f"status={item.get('status')} "
            f"md_rows={item.get('marketdata_quote_rows')} "
            f"massive_rows={item.get('massive_aggregate_rows')} "
            f"overlap={summary.get('overlap_sessions')} "
            f"exact_price={_fmt(summary.get('exact_price_match_rate'))} "
            f"median_abs={_fmt(summary.get('median_price_abs_diff'))} "
            f"inside_range={_fmt(summary.get('marketdata_last_inside_massive_range_rate'))} "
            f"median_vol_rel={_fmt(summary.get('median_volume_rel_diff'))} "
            f"error={item.get('error')}"
        )

    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: semantic calibration only; no thresholded price authority, "
        "strategy, PAPER, LIVE, broker or order authority"
    )
    return 0 if report["status"] == "DIAGNOSTIC_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
