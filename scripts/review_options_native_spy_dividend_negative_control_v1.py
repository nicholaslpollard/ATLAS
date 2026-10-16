from __future__ import annotations

"""Offline witness check of archived SPY dividend completeness (no PIT acceptance)."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.options_native_spy_dividend_negative_control_v1 import (
    review_spy_dividend_negative_control,
)

MAX_OUTPUT = 128 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only SPY external dividend negative control")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS SPY CORPORATE-ACTION ARCHIVE NEGATIVE CONTROL V1", flush=True)
    print("  Compares two pinned completed JSON reports against one independently witnessed 2018 distribution.", flush=True)
    print("  NO ledger or original-page reread; NO stock/options/provider/broker/outcome scans.", flush=True)
    print("  Retrospective witness does NOT prove historical publication, action coverage or eligible returns.", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        report = review_spy_dividend_negative_control(settings)
        print(f"  frozen archive candidate cash dividends: {report['archived_cash_dividends']}", flush=True)
        print(f"  archived-empty weekly decisions: {report['archive_empty_weekly_windows']}", flush=True)
        print("  missing archival event: SPY ex 2018-06-15, ~1.245568 USD/share (retrospective external witness)", flush=True)
        print(f"  directly affected frozen prior windows: {report['affected_weekly_case_count']}", flush=True)
        for affected in report["definitively_affected_archivally_empty_weekly_windows"]:
            print(f"    {affected['decision_date']}: archive shows zero; source completeness disproved", flush=True)
        print("  Historical PIT, economic returns, variance, option inputs and trades: UNQUALIFIED", flush=True)
        if args.save_report:
            target = settings.resolved_path("data/research/options_native_spy_dividend_negative_control_v1") / (
                report["report_fingerprint"][:16] + ".json"
            )
            encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if len(encoded.encode("utf-8")) > MAX_OUTPUT:
                raise ValueError("negative control output exceeds 128 KiB")
            if target.is_symlink() or (target.exists() and (
                target.stat().st_size > MAX_OUTPUT or target.read_text(encoding="utf-8") != encoded
            )):
                raise ValueError("conflicting existing report; no overwrite")
            if not target.exists():
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Existing evidence unchanged. No dividend repair, paid fallback or replay authorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
