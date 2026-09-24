from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_massive_sparse_activity_v1 import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_sparse_activity_confirmation_v1,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preregistered targeted sparse-activity confirmation for "
            "MarketData EOD volume vs Massive daily aggregate presence."
        )
    )
    parser.add_argument(
        "--authorize-provider-reads",
        action="store_true",
        help="Required explicit authorization for bounded read-only provider calls.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_provider_reads:
        print(
            "BLOCKED: pass --authorize-provider-reads to permit the bounded "
            "sparse-activity confirmation."
        )
        return 2

    settings = load_settings(PROJECT_ROOT, "development")
    print("ATLAS MarketData x Massive Sparse-Activity Confirmation V1")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print(
        "  V2 failed evidence: "
        f"{CONTRACT['evidence_basis']['v2_validation']['run_id']} / "
        f"{CONTRACT['evidence_basis']['v2_validation']['evidence_fingerprint']}"
    )
    print("  V2 verdict: VALIDATION_FAILED / immutable")
    print("  V2 positive-volume anchors: 6/6 passed / 53 comparisons")
    print("  V2 only failed gate: sparse_case_observed")
    print(
        "  target anchors: "
        + ", ".join(
            f"{item['root']}@{item['date']}" for item in CONTRACT["anchors"]
        )
    )
    print("  prior cross-provider root/date reuse: 0")
    print("  sparse selector: farthest OTM call from frozen restricted chain")
    print("  selector uses strike/underlying only; quote-series volume is not used to select")
    print("  expected MarketData reads: 24 / 12 chains + 12 quote series")
    print("  expected Massive reads: 12 / exact-contract unadjusted 1Day")
    print("  provider writes: 0")
    print("  price/bid-ask/intraday/execution/simulator/PAPER/LIVE authority: false")
    print("  binding thresholds:")
    for key, value in CONTRACT["preregistered_thresholds"].items():
        print(f"    {key}: {value}")

    report = run_sparse_activity_confirmation_v1(settings)

    print("\nSPARSE-ACTIVITY CONFIRMATION: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    summary = report["summary"]
    print(f"  total MarketData sessions: {summary['total_marketdata_sessions']}")
    print(f"  zero-volume sessions: {summary['zero_volume_sessions']}")
    print(f"  zero-volume anchors: {summary['zero_volume_anchor_count']}")
    print(f"  positive-volume sessions: {summary['positive_volume_sessions']}")
    print(f"  positive-volume anchors: {summary['positive_volume_anchor_count']}")
    print(f"  activity concordance: {summary['activity_concordance_rate']}")
    print(f"  zero-volume with Massive bar: {summary['zero_volume_with_massive_bar']}")
    print(f"  positive-volume missing Massive bar: {summary['positive_volume_missing_massive_bar']}")
    print(f"  invalid-volume sessions: {summary['invalid_volume_sessions']}")
    print(f"  extra Massive dates: {summary['extra_massive_dates']}")
    print("  checks:")
    for key, value in report["checks"].items():
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
        print(
            "  "
            f"{item.get('root')} {item.get('option_symbol')}: "
            f"status={item.get('status')} "
            f"md_rows={item.get('marketdata_quote_rows')} "
            f"zero={item.get('zero_volume_sessions')} "
            f"positive={item.get('positive_volume_sessions')} "
            f"massive_rows={item.get('massive_aggregate_rows')} "
            f"mismatches={item.get('activity_mismatches')} "
            f"extra={item.get('extra_massive_dates')} "
            f"error={item.get('error')}"
        )
    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print(
        "  authority: sparse activity semantics only if PASS; zero-volume last, "
        "positive-volume price authority, bid/ask, intraday, execution, simulator, "
        "strategy, PAPER and LIVE remain closed in this gate"
    )
    return 0 if report["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
