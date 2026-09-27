from __future__ import annotations

"""Zero-provider, read-only inventory and exact-symbol EOD history inspection."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.offline_option_history_v1 import (
    OfflineOptionHistoryError,
    OfflineOptionHistoryStore,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect accepted offline 2022 CALL EOD library")
    parser.add_argument("--symbol", help="Exact frozen OCC CALL symbol, without provider fallback")
    parser.add_argument("--decision-utc", help="ISO-8601 timezone-aware cutoff; requires --symbol")
    args = parser.parse_args()
    if args.decision_utc and not args.symbol:
        parser.error("--decision-utc requires --symbol")
    print("ATLAS Offline Option History V1 / ZERO provider requests", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        project_options, physical_options = settings.external_storage_binding_paths("options")
        store = OfflineOptionHistoryStore(settings)
        print(f"  physical external options root: {physical_options}", flush=True)
        print(f"  logical options alias: {project_options}", flush=True)
        print(f"  accepted frozen quote plan: {store.plan_fingerprint}", flush=True)
        print(f"  indexed exact CALL histories: {store.available_symbols:,}", flush=True)
        print("  raw quote bodies are checked only when requested; no full-corpus re-audit.", flush=True)
        if args.symbol:
            if args.decision_utc:
                result = store.predecision_history(
                    args.symbol, decision_utc=datetime.fromisoformat(args.decision_utc)
                )
            else:
                result = store.inspect_retrospective_history(args.symbol)
            print(f"  option symbol: {result['option_symbol']}", flush=True)
            print(f"  scope: {result['scope']}", flush=True)
            print(f"  observation count: {result['observation_count']}", flush=True)
            if result["observations"]:
                print(f"  first observation: {result['observations'][0]['session_et']}", flush=True)
                print(f"  last observation: {result['observations'][-1]['session_et']}", flush=True)
            print("  original provider updated timestamp is NOT proof of publication or fill time.", flush=True)
        print("  provider requests: 0; PAPER/LIVE/strategy-promotion authority: none.", flush=True)
        return 0
    except (OfflineOptionHistoryError, OSError, ValueError, KeyError) as exc:
        print(f"OFFLINE OPTION SOURCE STOPPED: {type(exc).__name__}: {exc}", flush=True)
        print("  No paid retry or alternate-source fallback. Preserve existing evidence.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
