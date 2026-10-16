from __future__ import annotations

"""Read one small existing SPY input window, without a strategy or provider run."""

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
from packages.core.settings import ConfigurationError, load_settings
from packages.data.options_native_pilot_input_packet_v1 import build_options_native_pilot_input_packet

HEARTBEAT_SECONDS = 20


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ATLAS fixed SPY pilot raw-input evidence packet")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE PILOT INPUT PACKET V1", flush=True)
    print("  One fixed 2020-01-06 prior window: 21 requested SPY closes, two bounded native daily units.", flush=True)
    print("  Full plan/inventory/unit hash checks; no minute/options scans, provider/broker requests or simulations.", flush=True)
    started = time.monotonic()
    stopped = Event()

    def progress(message):
        print(f"  [{time.monotonic() - started:.1f}s] {message}", flush=True)

    def heartbeat():
        while not stopped.wait(HEARTBEAT_SECONDS):
            progress("source verification active; bounded files, ETA unavailable")

    worker = Thread(target=heartbeat, daemon=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        worker.start()
        report = build_options_native_pilot_input_packet(settings, progress=progress)
        stopped.set()
        worker.join()
        print(f"  raw closes present / requested: {report['present_closes']} / {report['requested_closes']}", flush=True)
        rows = report["prior_close_rows"]
        print(f"  requested sessions: {rows[0]['session_date']} through {rows[-1]['session_date']}", flush=True)
        print(f"  missing sessions: {report['missing_sessions']}", flush=True)
        print(f"  native acceptance: {report['lineage']['native_acceptance_fingerprint']}", flush=True)
        print("  economic returns / forecast / historical availability: UNQUALIFIED", flush=True)
        for gap in report["qualification_gaps"]:
            print(f"    {gap}", flush=True)
        if args.save_report:
            directory = settings.resolved_path("data/research/options_native_pilot_input_packet_v1")
            target = directory / f"{report['report_fingerprint'][:16]}.json"
            encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if target.is_symlink():
                raise ValueError("packet output is a link; original path retained")
            if target.exists():
                if target.stat().st_size > 256 * 1024 or target.read_text(encoding="utf-8") != encoded:
                    raise ValueError("existing packet conflicts; original file retained")
            else:
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']}; report fingerprint: {report['report_fingerprint']}", flush=True)
        return 0
    except (ConfigurationError, OSError, ValueError, KeyError, TypeError, RuntimeError, duckdb.Error) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Source files retained; no rebuild, alternative source or provider request attempted.", flush=True)
        return 3
    finally:
        stopped.set()
        if worker.is_alive():
            worker.join()


if __name__ == "__main__":
    raise SystemExit(main())
