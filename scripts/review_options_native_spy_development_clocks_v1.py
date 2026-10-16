from __future__ import annotations

"""One bounded offline pass for all 411 frozen options-native SPY stock clocks."""

import argparse
import json
from pathlib import Path
import sys
from threading import Event, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.data.options_native_spy_development_clock_coverage_v1 import (
    review_spy_development_minute_coverage,
)

HEARTBEAT_SECONDS = 20
MAX_REPORT = 12 * 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="411 native SPY weekly input clocks, cached source only")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE SPY 2018-2025 EXACT MINUTE INPUT COVERAGE V1", flush=True)
    print("  411 frozen entry sessions; globally deduplicated prior closing-minute bars and 10:00 spot bars.", flush=True)
    print("  Accepted Alpaca SIP V2 only. 0 daily/option/corporate-action/provider/broker/outcome scans.", flush=True)
    print("  Up to 125 sequential monthly units, 256 MiB per file, SQL 2 threads / 512 MiB.", flush=True)
    print("  No PIT feature, variance forecast, simulated trade or financial authority.", flush=True)
    started, stop = time.monotonic(), Event()

    def progress(msg: str) -> None:
        print(f"  [{time.monotonic() - started:.1f}s] {msg}", flush=True)

    def heartbeat() -> None:
        while not stop.wait(HEARTBEAT_SECONDS):
            progress("exact native monthly-unit scan active; ETA unavailable")

    worker = Thread(target=heartbeat, daemon=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        worker.start()
        report = review_spy_development_minute_coverage(settings, progress=progress)
        stop.set()
        worker.join()
        print(f"  source months scanned / required: {report['scanned_monthly_units']} / {report['target_months']}", flush=True)
        print(f"  exact minute clocks observed / required: {report['observed_exact_clocks']} / "
              f"{report['unique_exact_clocks_requested']}", flush=True)
        print(f"  complete physical weekly cases / requested: {report['raw_complete_weekly_cases']} / 411", flush=True)
        print(f"  incomplete physical weekly cases: {report['raw_incomplete_weekly_cases']}", flush=True)
        print(f"  unaccepted/unavailable source months: {report['unavailable_months']}", flush=True)
        for case in report["cases"]:
            if case["missing_clocks"]:
                print(f"    missing {case['decision_date']}: {len(case['missing_clocks'])} exact clocks", flush=True)
                if sum(bool(x["missing_clocks"]) for x in report["cases"]
                       if x["decision_date"] <= case["decision_date"]) >= 12:
                    print("    Further missing case details preserved in JSON.", flush=True)
                    break
        print("  PIT publication, economic adjustments, forecast, option quotes, fills and returns: UNQUALIFIED", flush=True)
        if args.save_report:
            target = settings.resolved_path("data/research/options_native_spy_development_clock_coverage_v1") / (
                report["report_fingerprint"][:16] + ".json"
            )
            encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if len(encoded.encode("utf-8")) > MAX_REPORT:
                raise ValueError("multi-year SPY minute input report exceeds output bound")
            if target.is_symlink() or (target.exists() and (
                target.stat().st_size > MAX_REPORT or target.read_text(encoding="utf-8") != encoded
            )):
                raise ValueError("existing input report differs: preserve previous evidence")
            if not target.exists():
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, duckdb.Error) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  No alternative provider, minute clock, paid retry or source repair authorized.", flush=True)
        return 3
    finally:
        stop.set()
        if worker.is_alive():
            worker.join()


if __name__ == "__main__":
    raise SystemExit(main())
