from __future__ import annotations

"""V46 scenario-only 101-step American IV economics; never a historical replay."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.simulation.spy_v46_provisional_signal import evaluate


def _load(path: Path, limit: int) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError(f"V46_MISSING_OR_OVERSIZED:{path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("V46_EXPECTED_OBJECT")
    return obj


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v45", type=Path, required=True)
    p.add_argument("--v37", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    start = time.monotonic()
    last = -1

    def progress(done: int, total: int, day: str, state: str) -> None:
        nonlocal last
        step = min(10, 10 * done // total)
        if step == last:
            return
        last = step
        duration = time.monotonic() - start
        eta = round((total - done) / (done / duration)) if duration > 0 else None
        stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
        print(f"[{stamp}] PROGRESS_{step*10}PCT completed={done}/{total}"
              f" ({done/total:.1%}) elapsed={duration:.1f}s"
              f" eta_rough={eta}s last_day={day} state={state}", flush=True)

    print("ATLAS V46 EXPLORATORY SPY VARIANCE ECONOMICS", flush=True)
    print("  EXACT_SOURCE_0959=V45 RETROSPECTIVE_PRIOR_VOL=V37"
          " RATE_DIVIDEND=HYPOTHETICAL_ONLY REAL_SIGNAL=BLOCKED", flush=True)
    try:
        if args.output.is_symlink() or args.output.exists():
            raise ValueError("V46_OUTPUT_EXISTS")
        report = evaluate(_load(args.v45, 8 * 1024 * 1024),
                          _load(args.v37, 8 * 1024 * 1024), progress=progress)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True, allow_nan=False)
            f.write("\n")
        for k, v in report["status_counts"].items():
            print(f"  {k}={v}", flush=True)
        print(f"  fingerprint={report['fingerprint']} saved={args.output}", flush=True)
        print("  COMPLETE: SCENARIO_SENSITIVITY_ONLY; REAL_TRADES_AND_PROFITABILITY_NOT_TESTED", flush=True)
        return 0
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        print(f"  STOPPED: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
