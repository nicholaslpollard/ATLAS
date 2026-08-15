from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.instruments.registry import InstrumentRegistryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve a ticker against an ATLAS point-in-time reference snapshot.")
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = InstrumentRegistryStore(load_settings(PROJECT_ROOT))
    rows = store.resolve_ticker(args.ticker, args.date)
    if not rows:
        print(f"No ATLAS reference observation for {args.ticker.upper()} on {args.date}.")
        return 1
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
