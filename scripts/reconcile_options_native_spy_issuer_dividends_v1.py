from __future__ import annotations

"""Bounded offline issuer 33-event SPY cash-date/source reconciliation."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.options_native_spy_issuer_dividend_reconciliation_v1 import (
    build_issuer_spy_reconciliation,
)

MAX_REPORT_BYTES = 192 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline exact source SPY issuer dividend reconciliation"
    )
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE SPY ISSUER 33-EVENT CASH SOURCE RECONCILIATION V1", flush=True)
    print("  3 pinned JSON reports + the original SHA-256-verified US State Street XLSX only.", flush=True)
    print("  ZERO provider, issuer-download, broker, minute, action-ledger, option or outcome calls.", flush=True)
    print("  Reconciles cash ex-dates, not 2018-2025 announcement/revision availability.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        report = build_issuer_spy_reconciliation(settings)
        print(f"  original issuer XLSX bytes / rows: {report['issuer_original_bytes']} / {report['issuer_workbook_rows']}", flush=True)
        print(f"  all-time SPY issuer rows: {report['issuer_all_time_spy_rows']}", flush=True)
        print(f"  period cash distributions matched: {report['issuer_event_count']}/33", flush=True)
        print(f"  original Alpaca archive ex-date matches: {report['archived_cash_events_matched_by_ex_date']}/33", flush=True)
        print(f"  originally omitted ex-dates: {report['missing_from_original_action_archive']}", flush=True)
        print(f"  issuer vs previous reference differences: {report['issuer_vs_reference_differences']}", flush=True)
        print(f"  issuer vs original archive differences: {report['issuer_vs_archive_differences']}", flush=True)
        print("  Historical PIT/publication/revisions, other adjustments, option IV and trading: UNQUALIFIED", flush=True)
        if args.save_report:
            directory = settings.resolved_path(
                "data/research/options_native_spy_issuer_dividend_reconciliation_v1"
            )
            output = directory / (report["report_fingerprint"][:16] + ".json")
            text = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
            if len(text.encode("utf-8")) > MAX_REPORT_BYTES:
                raise ValueError("issuer reconciliation report exceeds bounded output")
            if output.is_symlink() or (output.exists() and (
                output.stat().st_size > MAX_REPORT_BYTES
                or output.read_text(encoding="utf-8") != text
            )):
                raise ValueError("previous retained source report differs; original preserved")
            if not output.exists():
                atomic_write_text(output, text, fsync=True)
            print(f"  saved report: {output}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, KeyError, ArithmeticError, TypeError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Original issuer and historical research receipts untouched; no source fallback or trades.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
