from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_massive_sparse_activity_v2 import (
    CONTRACT,
    CONTRACT_FINGERPRINT,
    run_sparse_activity_confirmation_v2,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize-provider-reads", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_provider_reads:
        print("BLOCKED: pass --authorize-provider-reads")
        return 2

    print("ATLAS MarketData x Massive Sparse-Activity Confirmation V2")
    print(f"  contract fingerprint: {CONTRACT_FINGERPRINT}")
    print(
        "  V1 sparse failed evidence: "
        f"{CONTRACT['evidence_basis']['v1_sparse_confirmation']['run_id']} / "
        f"{CONTRACT['evidence_basis']['v1_sparse_confirmation']['evidence_fingerprint']}"
    )
    print("  V1 sparse verdict: SPARSE_ACTIVITY_CONFIRMATION_FAILED / immutable")
    print("  V1 sparse evidence: 87 zero / 18 positive / 105 total / 100% concordance")
    print("  selector: third-farthest OTM call from frozen restricted chain")
    print("  quote-series volume is not used to select contracts")
    print("  expected MarketData reads: 24 / 12 chains + 12 quote series")
    print("  expected Massive reads: 12 / exact-contract unadjusted 1Day")
    print("  provider writes: 0")
    print("  binding thresholds:")
    for key, value in CONTRACT["preregistered_thresholds"].items():
        print(f"    {key}: {value}")

    report = run_sparse_activity_confirmation_v2(load_settings(PROJECT_ROOT, "development"))
    print("\nSPARSE-ACTIVITY V2 CONFIRMATION: " + str(report["status"]))
    print(f"  evidence fingerprint: {report['evidence_fingerprint']}")
    s = report["summary"]
    for key in [
        "total_marketdata_sessions",
        "zero_volume_sessions",
        "zero_volume_anchor_count",
        "positive_volume_sessions",
        "positive_volume_anchor_count",
        "activity_concordance_rate",
        "zero_volume_with_massive_bar",
        "positive_volume_missing_massive_bar",
        "invalid_volume_sessions",
        "extra_massive_dates",
    ]:
        print(f"  {key}: {s[key]}")
    print("  checks:")
    for key, value in report["checks"].items():
        print(f"    {key}: {value}")
    print(f"  observed MarketData API credits consumed: {report['observed_marketdata_api_credits_consumed']}")
    print(f"  last observed MarketData API credits remaining: {report['last_observed_marketdata_api_credits_remaining']}")
    for item in report["anchors"]:
        print(
            f"  {item.get('root')} {item.get('option_symbol')}: "
            f"status={item.get('status')} md_rows={item.get('marketdata_quote_rows')} "
            f"zero={item.get('zero_volume_sessions')} positive={item.get('positive_volume_sessions')} "
            f"massive_rows={item.get('massive_aggregate_rows')} "
            f"mismatches={item.get('activity_mismatches')} extra={item.get('extra_massive_dates')} "
            f"error={item.get('error')}"
        )
    print(f"  terminal error: {report['terminal_error']}")
    print(f"  report: {report['report_path']}")
    print("  authority: activity semantics only if PASS; no zero-volume-last, price, execution, simulator, PAPER or LIVE authority")
    return 0 if report["passed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
