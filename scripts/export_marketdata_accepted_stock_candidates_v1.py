from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_accepted_stock_candidate_export_v1 import (
    CandidateStockExportError,
    export_candidate_stock_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export PIT stock-opportunity and chain-batch plans from accepted "
            "DEVELOPMENT lineage. Zero provider calls, no option outcome selection."
        )
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--per-month", type=int, default=1)
    parser.add_argument("--duckdb-threads", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        settings = load_settings(PROJECT_ROOT, "development")
        report = export_candidate_stock_manifest(
            settings,
            year=args.year,
            per_month=args.per_month,
            duckdb_threads=args.duckdb_threads,
        )
    except (OSError, ValueError, CandidateStockExportError) as exc:
        print(f"STOCK CANDIDATE EXPORT BLOCKED: {type(exc).__name__}: {exc}", flush=True)
        return 3

    print("ATLAS Accepted Stock Candidate Export V1")
    print(f"  status: {report['status']}")
    print(f"  cohort identity: {report['cohort_identity']}")
    print(f"  selected opportunities: {report['selected_opportunities']}")
    print(f"  shared chains: {report['shared_chain_requests']}")
    print(f"  duplicate requests eliminated: {report['selected_opportunities'] - report['shared_chain_requests']}")
    print(f"  SHA-verified native raw source units: {report['verified_native_raw_units']}")
    for item in report["sample"]:
        print(
            f"    {item['signal_session']} {item['ticker']} "
            f"entry_open={item['entry_price']} "
            f"candidate_expiry={item['candidate_expiration']}",
            flush=True,
        )
    print(f"  accepted-source bundle SHA256: {report['stock_source_sha256']}")
    print(f"  plan fingerprint: {report['plan_fingerprint']}")
    print(f"  stock source file: {report['stock_source_file']}")
    print(f"  opportunity manifest: {report['opportunities_file']}")
    print(f"  chain plan: {report['plan_file']}")
    print(f"  run ID: {report['source_only_run_id']}")
    print(f"  stages recorded: {report['stages_completed']}")
    print(f"  elapsed seconds: {report['elapsed_seconds']:.1f}")
    print(f"  durable run report: {report['run_report_path']}")
    print("  provider reads: 0")
    print("  broker reads/writes: 0")
    print("  option P&L or strategy promotion authority: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
