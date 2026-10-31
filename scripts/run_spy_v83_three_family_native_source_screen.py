from __future__ import annotations

"""V83 native SPY first-5/10-minute three-entry-family source screen.

All source months pass original canonical/raw SHA integrity before decisions.
Option requests are plans only by default. Explicit --acquire-options uses V39
cache-first read-through: NEW exact original requests are automatically saved,
no request cap, no duplicate ambiguous-provider retries. No broker orders.
"""

import argparse
from collections import Counter
from datetime import date,datetime,timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE,_sample_rows,discover_minute_units,validate_minute_rows,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.spy_v51_native_minute_orb_inventory import _verify_monthly_unit_with_progress
from packages.simulation.spy_v82_causal_entry_family_registry import (
    REGISTRY,evaluate,exact_option_demand,v39_demand,V82Error,
)
from packages.simulation.strategy_options_source_runtime_v39 import (
    resolve_strategy_source_demands,
)

ROOT=Path(__file__).resolve().parents[1]
ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v83-original-native-three-entry-family-source-screen-v1"


def info(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",flush=True)


def signed(doc):
    return {**doc,"fingerprint":_fingerprint(doc)}


def write_once(path,doc):
    row=signed(doc)
    with path.open("x",encoding="utf8") as fh:
        json.dump(row,fh,sort_keys=True,indent=2,allow_nan=False)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return row


def source_bars(rows,day,*,before="09:40:00"):
    minute_end=datetime.fromisoformat(day.isoformat()+"T"+before).replace(tzinfo=ET)
    result=[]
    for row in rows:
        stamp=row["timestamp_utc"]
        if not isinstance(stamp,datetime) or stamp.utcoffset() is None:
            raise V82Error("V83_ORIGINAL_STOCK_CLOCK_MISSING")
        local=stamp.astimezone(ET)
        if (local.date()!=day or local.hour!=9 or local.minute<30 or
                local.minute>39 or local>=minute_end):
            continue
        result.append({
            "minute_at_et":local.isoformat(),
            # 1-minute original aggregate is known only AFTER this minute.
            # This is a causal assumption, not provider publication proof.
            "available_at_et":(local+timedelta(minutes=1)).isoformat(),
            "open":str(row["open"]),"high":str(row["high"]),
            "low":str(row["low"]),"close":str(row["close"]),
        })
    return result


def previous_session_close(rows,prev,market):
    if not rows:
        return None
    _,close=market.regular_open_close(prev)
    t=close.astimezone(ET)-timedelta(minutes=1)
    end=close.astimezone(ET)
    for row in rows:
        ts=row["timestamp_utc"]
        if not isinstance(ts,datetime) or ts.utcoffset() is None:
            raise V82Error("V83_ORIGINAL_PRIOR_CLOSE_TIMESTAMP_INVALID")
        if ts.astimezone(ET)==t:
            return {
                "prior_close":str(row["close"]),
                "prior_close_at_et":t.isoformat(),
                "prior_close_available_at_et":end.isoformat(),
                "prior_closing_bar_publication_independently_proven":False,
            }
    return None


def run(start,end,output,*,acquire_options=False,
        discover=discover_minute_units,
        verify=_verify_monthly_unit_with_progress,
        sample=_sample_rows,validate=validate_minute_rows,
        resolve=resolve_strategy_source_demands,
        settings_factory=load_settings,
        calendar=None,emit=info):
    if (type(acquire_options) is not bool or start>end or
            end>B34_MAX_SAMPLE_DATE or output.exists() or output.is_symlink()):
        raise ValueError("V83_RANGE_OR_OUTPUT_INVALID")
    market=calendar or get_market_calendar("XNYS")
    sessions=market.sessions_in_range(start,end)
    if not sessions:
        raise ValueError("V83_NO_REAL_XNYS_SESSIONS")
    layout=V2Layout.beneath(ROOT/"data")
    units={}
    rows_by_session={}
    deficits=[]
    def month_unit(day):
        ym=(day.year,day.month)
        if ym not in units:
            emit(f"STAGE_START V83 original stock SHA check year={day.year} month={day.month}")
            found=discover(layout,target_year=day.year,target_month=day.month,progress=emit)
            matching=[u for u in found if (u.year,u.month)==ym and "SPY" in u.symbols]
            if len(matching)!=1:
                raise V82Error("V83_NO_SINGLE_ORIGINAL_SPY_MONTH")
            unit=matching[0]
            proof=verify(unit,emit)
            if not proof["accepted"]:
                raise V82Error("V83_ORIGINAL_MONTH_SHA_UNQUALIFIED")
            units[ym]=unit
        return units[ym]

    def day_rows(day):
        if day not in rows_by_session:
            unit=month_unit(day)
            bars=sample(unit.canonical_path,symbol="SPY",session_date=day)
            if not bars:
                rows_by_session[day]=[]
            else:
                result=validate(bars,sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
                                symbol="SPY",session_date=day)
                if not result["accepted"]:
                    raise V82Error("V83_ORIGINAL_SESSION_SEMANTICS_UNQUALIFIED")
                rows_by_session[day]=bars
        return rows_by_session[day]

    emit(f"STAGE_START V83 exchange sessions={len(sessions)} date_range={start}/{end} "
         f"strategy_families={len(REGISTRY)} provider_calls_on_missing={acquire_options} "
         "broker_orders=0")
    output.mkdir(parents=True,exist_ok=False)
    records=[]
    demands=[]
    milestone=10
    for idx,day in enumerate(sessions,1):
        prior=market.sessions_in_range(day-timedelta(days=10),day-timedelta(days=1))
        previous=prior[-1] if prior else None
        current=day_rows(day)
        curr_unit=month_unit(day)
        previous_close=None
        if previous is not None:
            try:
                old=day_rows(previous)
                previous_close=previous_session_close(old,previous,market)
            except V82Error as exc:
                deficits.append({"session":day.isoformat(),
                                 "reason":"PREVIOUS_SESSION_SOURCE_UNVERIFIED",
                                 "error":str(exc)})
        for family in REGISTRY:
            try:
                if not current:
                    raise V82Error("V83_NO_ORIGINAL_SPY_SESSION_BARS")
                scope="09:35:00" if family=="gap_fade_0935" else "09:40:00"
                first_bars=source_bars(current,day,before=scope)
                kwargs=previous_close if family=="gap_fade_0935" else {}
                if kwargs is None:
                    raise V82Error("V83_PREVIOUS_SESSION_LAST_BAR_NOT_AVAILABLE")
                candidate=evaluate(
                    family,session=day.isoformat(),
                    stock_source_sha=curr_unit.canonical_sha256,
                    bars=first_bars,market_session_verified=True,**kwargs)
                if candidate["status"]=="OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED":
                    # This ATM strike proxy is driven solely by ORIGINAL stock
                    # bar close known before decision. It is NOT yet proof the
                    # option strike/expiry was listed or liquid at that clock.
                    underlying=Decimal(candidate["features"]["last_closed_bar_close"])
                    strike=str(underlying.quantize(Decimal("1"),rounding=ROUND_HALF_UP))
                    contract={
                        "symbol":"SPY","date_et":day.isoformat(),
                        "expiration":day.isoformat(),"strike":strike,
                        "right":candidate["direction"].lower(),
                    }
                    required=exact_option_demand(
                        candidate,selected_contract=contract,
                        # Latest completed minute is eligible one second before
                        # the decision clock. Never backdate option quotes.
                        selection_at_et=(datetime.fromisoformat(
                            candidate["decision_at_et"])-timedelta(seconds=1)).isoformat(),
                        selection_source_sha256=curr_unit.canonical_sha256)
                    demands.append(required)
                    status="OPTIONS_EXACT_SOURCE_DEMAND_PREPARED"
                    source_sha=required["fingerprint"]
                else:
                    status="NO_SIGNAL"
                    source_sha=None
                record={
                    "session":day.isoformat(),"strategy":family,
                    "status":status,
                    "reason":candidate["reason"],
                    "causal_decision":candidate,
                    "source_demand_sha":source_sha,
                    "selected_option_listing_historically_verified":False,
                    "option_contract_liquidity_verified":False,
                    "broker_orders":0,
                }
            except V82Error as exc:
                record={
                    "session":day.isoformat(),"strategy":family,
                    "status":"SOURCE_UNQUALIFIED_NO_TRADE",
                    "reason":str(exc),"causal_decision":None,
                    "source_demand_sha":None,"broker_orders":0,
                }
            records.append(record)
        while milestone<=100 and idx*100>=milestone*len(sessions):
            emit(f"PROGRESS_{milestone}PCT V83 sessions={idx}/{len(sessions)} "
                 f"last_day={day} source_demands_planned={len(demands)}")
            milestone+=10
    emit(f"STAGE_START V83 write causal entry decisions and exact source plans "
         f"sessions={len(sessions)} requirements={len(demands)} broker_orders=0")
    decision_report=write_once(output/"entry_screen.json",{
        "contract":CONTRACT,"start":start.isoformat(),"end":end.isoformat(),
        "source_months":[
            {"year":year,"month":month,"unit_id":unit.unit_id,
             "original_stock_sha256":unit.canonical_sha256}
            for (year,month),unit in sorted(units.items())],
        "families":REGISTRY,"registry_sha":_fingerprint(REGISTRY),
        "xnys_sessions":len(sessions),"cases":records,
        "original_stock_source_failures":deficits,
        "option_source_requirements_prepared":len(demands),
        "all_candidate_listing_and_spread_still_require_original_option_checks":True,
        "actual_broker_orders":0,"provider_requests":0,
        "date_range_is_not_heldout_if_previously_inspected":True,
    })
    option_report=write_once(output/"option_source_plan.json",{
        "contract":CONTRACT+"-exact-source-plan-v1",
        "entry_screen_sha":decision_report["fingerprint"],
        "demands":demands,
        "provider_requests":0,"broker_orders":0,
        "exact_provider_calls_automatic_only_if_acquire_options":acquire_options,
    })
    acquired=None
    if acquire_options and demands:
        emit(f"STAGE_START V83 cache-first paid exact options data source "
             f"requirements={len(demands)} V39=ENABLED "
             "no_request_quota=True safe_ambiguous_retry=False broker_orders=0")
        settings=settings_factory(ROOT,"development")
        original_source_resolution=resolve(
            settings,"spy_v82_three_family_registry_20261031",
            (v39_demand(item) for item in demands),
            continue_on_error=True,
            on_progress=lambda k,v:emit(
                f"V83_PROVIDER_{k.upper()} date={v.get('date_et')} "
                f"query={v.get('query_id')} status={v.get('status')}")
        )
        # V39 returns a typed but unsigned runtime summary, while original
        # per-query provider receipts are persisted in its SQLite cache.
        # Bind the returned exact status/counts to this immutable V83 report
        # instead of assuming V39 itself produces a signed fingerprint.
        if (not isinstance(original_source_resolution,dict) or
                original_source_resolution.get("source_uses_requested")!=len(demands)
                or original_source_resolution.get("contract")!=
                "atlas-strategy-options-data-demand-runtime-v39"):
            raise V82Error("V83_SOURCE_RESOLUTION_COUNTS_OR_CONTRACT_INVALID")
        acquired=signed(original_source_resolution)
    output_report=write_once(output/"summary.json",{
        "contract":CONTRACT+"-summary-v1",
        "entry_screen_sha":decision_report["fingerprint"],
        "option_source_plan_sha":option_report["fingerprint"],
        "source_resolution":acquired,
        "sessions":len(sessions),"family_cases":len(records),
        "entry_dispositions":dict(sorted(Counter(x["status"] for x in records).items())),
        "planned_exact_option_demands":len(demands),
        "new_provider_request_counts":"USE_EXACT_V39_SOURCE_RECEIPT_IF_ENABLED",
        "broker_orders":0,"actual_fills":0,"cash_returns_proven":False,
        "option_selection_and_trade_execution_not_qualified":True,
    })
    emit(f"COMPLETE V83 days={len(sessions)} family_decisions={len(records)} "
         f"source_plans={len(demands)} output={output/'summary.json'} "
         "broker_orders=0")
    return output_report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start",required=True,type=date.fromisoformat)
    p.add_argument("--end",required=True,type=date.fromisoformat)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--acquire-options",action="store_true")
    args=p.parse_args(argv)
    try:
        run(args.start,args.end,args.output_dir,
            acquire_options=args.acquire_options)
        return 0
    except Exception as exc:
        info(f"STOPPED V83 error_type={type(exc).__name__} "
             "preserve_source_receipts=True broker_orders=0")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
