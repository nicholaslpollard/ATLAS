from __future__ import annotations

"""Index SPY archival corporate-action candidates for all 411 frozen pilot decisions."""

import argparse
import json
from pathlib import Path
import sys
from threading import Event, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.options_native_spy_archival_action_timeline_v1 import (
    build_spy_archival_action_timeline,
)

MAX_REPORT_BYTES = 4 * 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline multi-year SPY archival action candidates")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE SPY ARCHIVAL ACTION TIMELINE V1", flush=True)
    print("  411 fixed SPY pilot decisions; one hash-pinned 378362-record corporate-action ledger.", flush=True)
    print("  Reuses proven 379-page original source reconciliation without reopening those pages.", flush=True)
    print("  No stock scans, options, broker/provider requests, outcomes or simulations.", flush=True)
    print("  Archival ex/process/effective dates do NOT establish historical publication or complete coverage.", flush=True)
    start, stop = time.monotonic(), Event()

    def progress(message: str) -> None:
        print(f"  [{time.monotonic() - start:.1f}s] {message}", flush=True)

    def heartbeat() -> None:
        while not stop.wait(20):
            progress("bounded original native-action ledger scan active; ETA unavailable")

    worker = Thread(target=heartbeat, daemon=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        worker.start()
        report = build_spy_archival_action_timeline(settings, progress=progress)
        stop.set()
        worker.join()
        print(f"  ledger action records checked: {report['native_ledger_records_reconciled']}", flush=True)
        print(f"  bounded SPY archive candidates: {len(report['action_candidates'])}", flush=True)
        print(f"  source action types: {report['action_candidates_by_type']}", flush=True)
        print(f"  SPY candidates with unknown event date: {report['archival_candidates_with_unknown_effective_date']}", flush=True)
        print(f"  price-complete frozen weeks: {report['physical_input_complete_weekly_decisions']}/411", flush=True)
        for row in report["weekly_case_action_index"]:
            if row["archived_dated_action_candidate_indices"]:
                print(f"  {row['decision_date']}: {len(row['archived_dated_action_candidate_indices'])} dated archival event candidate(s)", flush=True)
        print("  No-action coverage, historical disclosure/revisions, adjusted returns and trading: UNQUALIFIED", flush=True)
        if args.save_report:
            target = settings.resolved_path("data/research/options_native_spy_archival_action_timeline_v1") / (
                report["report_fingerprint"][:16] + ".json"
            )
            encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if len(encoded.encode("utf-8")) > MAX_REPORT_BYTES:
                raise ValueError("SPY archival candidate report exceeds 4 MiB")
            if target.is_symlink() or (target.exists() and (
                target.stat().st_size > MAX_REPORT_BYTES or target.read_text(encoding="utf-8") != encoded
            )):
                raise ValueError("existing candidate timeline conflicts; original preserved")
            if not target.exists():
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Raw evidence unchanged. No missing-date substitute, paid retry or backtest authorized.", flush=True)
        return 3
    finally:
        stop.set()
        if worker.is_alive():
            worker.join()


if __name__ == "__main__":
    raise SystemExit(main())
