from __future__ import annotations

"""Reuse the named pilot packet and inspect bounded cached stock input facts."""

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
from packages.data.options_native_stock_input_review_v1 import (
    DEFAULT_BINDING, review_options_native_stock_inputs,
)

HEARTBEAT_SECONDS = 20


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ATLAS fixed pilot cached corporate-action and stock-clock review")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE CACHED STOCK INPUT REVIEW V1", flush=True)
    print("  Reuses the inspected daily packet; zero daily-unit rereads, providers, brokers, option histories or simulations.", flush=True)
    print("  Two exact SPY minute units: 21 final regular-session bars plus the bar ending at the fixed 10:00 decision.", flush=True)
    print("  One accepted corporate-action snapshot; recorded dates do not establish publication or complete coverage.", flush=True)
    print("  Resource profile: two SQL threads, 512 MiB query memory, 256 MiB per minute file; bounded gzip streams.", flush=True)
    started, stopped = time.monotonic(), Event()

    def progress(message):
        print(f"  [{time.monotonic() - started:.1f}s] {message}", flush=True)

    def heartbeat():
        while not stopped.wait(HEARTBEAT_SECONDS):
            progress("bounded source checks active; ETA unavailable")

    worker = Thread(target=heartbeat, daemon=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        print(f"  retained packet: {DEFAULT_BINDING.relative_path}", flush=True)
        worker.start()
        report = review_options_native_stock_inputs(settings, progress=progress)
        stopped.set()
        worker.join()
        observations = report["observations"]
        prior = [r for r in observations if r["role"] == "PRIOR_REGULAR_CLOSE"]
        print(f"  exact prior closing-minute observations: {sum(r['raw_close'] is not None for r in prior)} / 21", flush=True)
        spot = next(r for r in observations if r["role"] == "DECISION_SPOT")
        print(f"  10:00 spot candidate: {spot['raw_close']} / {spot['state']}; historical availability UNKNOWN", flush=True)
        different = sum(r["minute_minus_daily"] is not None and float(r["minute_minus_daily"]) != 0 for r in prior)
        print(f"  daily/minute price differences: {different}; diagnostic only, no source replacement", flush=True)
        print(f"  missing exact minute clocks: {report['missing_minute_clocks']}", flush=True)
        actions = report["corporate_actions"]["selected_spy_records"]
        print(f"  SPY action candidates: {len(actions)}; coverage/publication qualification remains OPEN", flush=True)
        for row in actions[:10]:
            print(f"    {row['action_type']} | {row['effective_date_state']} | {json.dumps(row['payload'], sort_keys=True)}", flush=True)
        print("  economic returns / forecast / pilot acceptance: UNQUALIFIED", flush=True)
        if args.save_report:
            target = settings.resolved_path("data/research/options_native_stock_input_review_v1") / f"{report['report_fingerprint'][:16]}.json"
            encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if len(encoded.encode()) > 512 * 1024:
                raise ValueError("output packet exceeds 512 KiB bound")
            if target.is_symlink() or (target.exists() and (target.stat().st_size > 512 * 1024 or target.read_text(encoding="utf-8") != encoded)):
                raise ValueError("existing output conflicts; original retained")
            if not target.exists():
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']}; report fingerprint: {report['report_fingerprint']}", flush=True)
        return 0
    except (ConfigurationError, OSError, ValueError, KeyError, TypeError, RuntimeError, duckdb.Error) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Original sources retained; no rebuild, alternate clock/source, paid request or simulation attempted.", flush=True)
        return 3
    finally:
        stopped.set()
        if worker.is_alive():
            worker.join()


if __name__ == "__main__":
    raise SystemExit(main())
