from __future__ import annotations

"""Audit only the ten original retained option exit-source bindings."""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import ConfigurationError, load_settings
from packages.simulation.retained_option_exit_source_audit_v1 import (
    DEFAULT_BINDING, OUTPUT_REL, audit_retained_option_exit_sources,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ATLAS retained option exact-exit source audit")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS RETAINED OPTION EXACT-EXIT SOURCE AUDIT V1", flush=True)
    print("  Two pinned reports; at most ten exact cached quote histories and their receipts/attempts.", flush=True)
    print("  Zero provider/broker requests, stock scans, strategy resolution and account replays.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        print(f"  review: {DEFAULT_BINDING.review_path}", flush=True)
        print("  checking full file hashes, signatures and original exact-contract memberships", flush=True)
        report = audit_retained_option_exit_sources(settings, progress=lambda message: print(f"  {message}", flush=True))
        print(f"  positions / contracts: {report['position_count']} / {report['contract_count']}", flush=True)
        print(f"  verified / missing position sources: {report['verified_position_sources']} / {report['missing_position_sources']}", flush=True)
        print(f"  legacy failures (nonexclusive): {report['legacy_failure_counts_nonexclusive']}", flush=True)
        print(f"  quote clocks versus recorded exit: {report['snapshot_clock_relations']}", flush=True)
        print(f"  calendar-close snapshots rejected by legacy 16:00 rule: {report['calendar_close_rejected_by_legacy_1600_rule']}", flush=True)
        print(f"  reported bid size below position / unknown: {report['reported_bid_size_below_position']} / {report['reported_bid_size_unknown']}", flush=True)
        print(f"  retained classification disagreements: {report['retained_classification_disagreements']}", flush=True)
        for row in report["positions"]:
            print(f"    {row['option_symbol']} | {row['contracts']} contracts | {row['status']}", flush=True)
            if row["status"] == "CACHE_EVIDENCE_MISSING":
                print(f"      missing: {row['source_evidence']['missing_cache_members']}", flush=True)
                continue
            quote = row["quote_snapshot_not_fill"]
            print(f"      exit {row['recorded_failed_exit_at_utc']} / quote {quote['updated_at_utc']} / {row['snapshot_clock_relation']}", flush=True)
            print(f"      bid/ask {quote['bid']}/{quote['ask']}; bid size {quote['bid_size_contracts']}; "
                  f"reported volume {quote['reported_volume_contracts']}; failures {row['legacy_failure_reasons']}", flush=True)
        print("  Source snapshots are not fills or publication-time proof; stock close does not qualify option trading hours.", flush=True)
        print("  Original exits, fees, settlement and cash unchanged; equity/return remain UNKNOWN.", flush=True)
        if args.save_report:
            directory = settings.resolved_path(OUTPUT_REL)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            target = directory / f"{stamp}_{uuid.uuid4().hex[:8]}.json"
            atomic_write_text(target, json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']}; report fingerprint: {report['report_fingerprint']}", flush=True)
        return 0
    except (ConfigurationError, OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Original evidence retained. No hash replacement, source rebuild or provider fallback attempted.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
