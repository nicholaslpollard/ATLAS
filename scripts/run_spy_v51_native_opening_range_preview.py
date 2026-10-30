from __future__ import annotations

"""Read-only native SPY minute source preview for published 0DTE ORB candidate."""

import argparse
from datetime import date, datetime
from zoneinfo import ZoneInfo
import time
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__" and not __package__:
    sys.path.insert(0,str(ROOT))

from packages.data.spy_v51_native_minute_orb_inventory import inspect_native_spy_day


def _progress(message: str) -> None:
    stamp=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
    print(f"[{stamp}] {message}",flush=True)


def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--date",default="2025-06-09")
    cli.add_argument("--output",type=Path,required=True)
    a=cli.parse_args(argv)
    started=time.monotonic()
    _progress("START V51 offline SPY 0DTE opening-range original source inspection"
              f" date={a.date} instrument=SPY provider_requests=0 broker_requests=0")
    _progress("STAGE_START validate_original_source_and_SHA full_monthly_parquet_plus_raw_bundle")
    try:
        if a.output.exists() or a.output.is_symlink():
            raise ValueError("V51_OUTPUT_ALREADY_EXISTS")
        result=inspect_native_spy_day(ROOT,session=date.fromisoformat(a.date),progress=_progress)
        _progress(f"STAGE_START save_source_preview status={result['status']}")
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open("x",encoding="utf-8") as f:
            json.dump(result,f,sort_keys=True,indent=2)
            f.write("\n")
        _progress(f"STAGE_PASS source_status={result['status']}"
                  f" native_minute_count={result.get('observed_native_minute_rows')}")
        if result.get("first_possible_breakout_minute"):
            _progress(f"possible_breakout_minute={result['first_possible_breakout_minute']}")
        _progress(f"opening_high={result.get('opening_high')} opening_low={result.get('opening_low')}")
        _progress("genuine_tick_first_breakout_verified=False historical_option_pnl=None")
        _progress(f"COMPLETE source_ready={result.get('source_ready',False)}"
                  f" elapsed={time.monotonic()-started:.1f}s saved={a.output}")
        return 0 if result.get("source_ready") else 2
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        _progress(f"STOPPED elapsed={time.monotonic()-started:.1f}s"
                  f" error={type(exc).__name__}: {str(exc)[:160]}")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
