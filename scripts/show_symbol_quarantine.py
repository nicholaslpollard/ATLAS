from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths


def main() -> int:
    parser = argparse.ArgumentParser(description="Show ATLAS per-session provider symbol quarantine details.")
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    settings = load_settings(PROJECT_ROOT)
    path = MarketDataPaths(settings).symbol_quarantine_registry(args.date)
    if not path.exists():
        print(f"No symbol quarantine registry exists for {args.date}.")
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
