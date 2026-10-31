from __future__ import annotations

"""V73: auto-acquire exact option tapes on real XNYS sessions, not weekdays.

Original V65/V69 frozen semantics and historical receipts remain unchanged.
Opt-in XNYS dates are passed to both readers. No fabricated holiday opening bars.
"""

import argparse
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v65_full_june_offline_simulator_readiness import inspect as v65
from scripts.run_spy_v69_source_first_multimonth_census import run as v69

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v73-xnys-session-calendar-source-first-exact-options-v1"


def event(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def xnys(start:date,end:date):
    if start>end:
        raise ValueError("V73_INVALID_DATE_RANGE")
    return get_market_calendar("XNYS").sessions_in_range(start,end)


def audit(first,last,output):
    return v65(first,last,output,session_calendar=xnys)


def run(start,end,output_dir,*, calendar=xnys,underlying_audit=None,
        source_runner=v69,emit=event):
    emit(f"STAGE_START V73 XNYS exchange_calendar_range={start}/{end}")
    valid_days=calendar(start,end)
    emit(f"START V73 XNYS sessions={len(valid_days)} dates={start}/{end} "
         "stock_original_sha=MANDATORY option_source=ON_MISS broker_orders=0")
    def checked_audit(first,last,output):
        if underlying_audit is not None:
            return underlying_audit(first,last,output)
        return v65(first,last,output,session_calendar=calendar)
    result=source_runner(start,end,output_dir,audit=checked_audit,
                         session_calendar=calendar,emit=emit)
    emit(f"COMPLETE V73 status={result['status']} "
         f"sessions={result['weekdays']} summary={output_dir/'summary.json'} "
         "broker_orders=0")
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start",required=True,type=date.fromisoformat)
    p.add_argument("--end",required=True,type=date.fromisoformat)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args(argv)
    try:
        result=run(a.start,a.end,a.output_dir)
        # A complete source audit with censored trades is still a successful
        # preserved run; original no-data / blocked sources are in the receipt.
        return 0
    except Exception as exc:
        event(f"STOPPED V73 reason_type={type(exc).__name__} "
              "broker_orders=0 preserve_original_source_receipts=True")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
