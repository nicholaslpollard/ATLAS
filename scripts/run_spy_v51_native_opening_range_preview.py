from __future__ import annotations

"""Read-only native SPY minute source preview for published 0DTE ORB candidate."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if __name__=="__main__" and not __package__:
    sys.path.insert(0,str(ROOT))

from packages.data.spy_v51_native_minute_orb_inventory import inspect_native_spy_day


def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--date",default="2025-06-09")
    cli.add_argument("--output",type=Path,required=True)
    a=cli.parse_args(argv)
    print("ATLAS V51 SPY 0DTE FIVE-MINUTE OPENING RANGE EXISTING SOURCE PREVIEW")
    print("  OFFLINE; SHA-verified existing Alpaca V2 SIP 1-minute source; NO provider calls")
    try:
        if a.output.exists() or a.output.is_symlink():
            raise ValueError("V51_OUTPUT_ALREADY_EXISTS")
        result=inspect_native_spy_day(ROOT,session=date.fromisoformat(a.date))
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open("x",encoding="utf-8") as f:
            json.dump(result,f,sort_keys=True,indent=2)
            f.write("\n")
        print(f"  source_status={result['status']}"
              f" native_minute_count={result.get('observed_native_minute_rows')}",flush=True)
        if result.get("first_possible_breakout_minute"):
            print(f"  possible_breakout_minute={result['first_possible_breakout_minute']}",flush=True)
        print(f"  opening_high={result.get('opening_high')} opening_low={result.get('opening_low')}",flush=True)
        print(f"  genuine_tick_first_breakout_verified=False historical_option_pnl=None",flush=True)
        print(f"  saved={a.output}",flush=True)
        return 0 if result.get("source_ready") else 2
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(f"  STOPPED: {type(exc).__name__}: {str(exc)[:160]}",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
