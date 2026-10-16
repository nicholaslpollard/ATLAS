from __future__ import annotations

"""Bounded original action-page audit for the frozen SPY options-native pilot."""

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
from packages.data.options_native_spy_action_source_proof_v1 import build_spy_action_source_proof

HEARTBEAT_SECONDS = 20


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate original SPY corporate-action source pages")
    parser.add_argument("--save-report", action="store_true")
    args = parser.parse_args(argv)
    print("ATLAS OPTIONS-NATIVE SPY ACTION SOURCE PROOF V1", flush=True)
    print("  Reuse pinned stock-input review; original gzip pages and native ledger only.", flush=True)
    print("  No daily/minute price scans, outcomes, option requests, provider/broker calls or simulations.", flush=True)
    started = time.monotonic()
    stop = Event()

    def progress(message: str) -> None:
        print(f"  [{time.monotonic() - started:.1f}s] {message}", flush=True)

    def heartbeat() -> None:
        while not stop.wait(HEARTBEAT_SECONDS):
            progress("bounded original source reconciliation active; ETA unavailable")

    worker = Thread(target=heartbeat, daemon=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.save_report:
            settings.assert_external_storage_binding("research_evidence")
        worker.start()
        report = build_spy_action_source_proof(settings, progress=progress)
        stop.set()
        worker.join()
        print(f"  original pages verified: {report['scanned_page_count']}", flush=True)
        print(f"  source records reconciled: {report['reconciled_action_records']}", flush=True)
        print(f"  bounded SPY action candidates: {len(report['spy_action_candidates'])}", flush=True)
        for item in report["spy_action_candidates"][:30]:
            print(f"    {item['action_type']}: {json.dumps(item['payload'], sort_keys=True)}", flush=True)
        print("  historical publication / economic returns / option forecast / pilot acceptance: UNQUALIFIED", flush=True)
        if args.save_report:
            folder = settings.resolved_path("data/research/options_native_spy_action_source_proof_v1")
            target = folder / (report["report_fingerprint"][:16] + ".json")
            encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
            if len(encoded.encode("utf-8")) > 512 * 1024:
                raise ValueError("source proof exceeds the fixed 512 KiB output bound")
            if target.is_symlink() or (target.exists() and (
                target.stat().st_size > 512 * 1024 or target.read_text(encoding="utf-8") != encoded
            )):
                raise ValueError("existing source proof conflicts; original preserved")
            if not target.exists():
                atomic_write_text(target, encoded, fsync=True)
            print(f"  saved report: {target}", flush=True)
        print(f"  COMPLETE: {report['status']} fingerprint={report['report_fingerprint']}", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"  BLOCKED: {exc}", flush=True)
        print("  Original data preserved; no alternative source, paid retry or historical result substituted.", flush=True)
        return 3
    finally:
        stop.set()
        if worker.is_alive():
            worker.join()


if __name__ == "__main__":
    raise SystemExit(main())
