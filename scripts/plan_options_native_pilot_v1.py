from __future__ import annotations

"""Print a frozen options-native specification/data plan; never download data."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.data.options_native_pilot_plan_v1 import build_options_native_pilot_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the complete deterministic plan")
    parser.add_argument("--output", type=Path, help="Optionally save this plan; conflicting files are never overwritten")
    args = parser.parse_args(argv)
    plan = build_options_native_pilot_plan()
    encoded = json.dumps(plan, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        target = args.output
        if (target.is_symlink() or (target.exists() and (
                not target.is_file() or target.stat().st_size > 4 * 1024 * 1024
                or target.read_text(encoding="utf-8") != encoded))):
            print("BLOCKED: output is linked or differs from the frozen plan; existing file retained.", file=sys.stderr)
            return 2
        if not target.exists():
            atomic_write_text(target, encoded)
    if args.json:
        print(encoded, end="")
    else:
        print("ATLAS OPTIONS-NATIVE PILOT V1 — SPECIFICATION AND DATA PLAN")
        print("  Zero provider/broker requests, source scans, outcomes and account simulations.")
        print("  Pilot: SPY long ATM straddle; both CALL and PUT; one strategy variant.")
        print(f"  Weekly clocks / planned surfaces / scope-buffer exclusions: "
              f"{plan['planned_weekly_clocks']} / {plan['entry_quote_surface_count']} / {plan['scope_buffer_exclusions']}")
        print(f"  By year: {plan['by_year']}")
        print(f"  Specification fingerprint: {plan['specification_fingerprint']}")
        print(f"  Plan fingerprint: {plan['plan_fingerprint']}")
        print("  BLOCKED FOR HISTORICAL PERFORMANCE: source, fees and multi-leg execution qualification required.")
        print("  Existing 9,455 CALL surfaces unchanged; no subscription activation or acquisition authorized.")
        if args.output is not None:
            print(f"  Saved/reused: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
