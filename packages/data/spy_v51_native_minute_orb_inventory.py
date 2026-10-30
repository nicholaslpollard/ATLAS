from __future__ import annotations

"""Read-only preview of first possible SPY 0DTE ORB minutes from native V2 SIP.

A provider one-minute bar can be shown as a candidate, but neither the minute
high/low nor historical timestamp constitutes an independently known first
breakout tick, selected option strike, or executable trade.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE, IntradaySemanticsAuditError,
    _sample_rows, discover_minute_units, verify_unit_integrity,
    validate_minute_rows,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT="atlas-spy-native-minute-five-minute-orb-inventory-v51"
ET=ZoneInfo("America/New_York")


def _price(value):
    try:
        val=Decimal(str(value))
    except (TypeError,InvalidOperation,ValueError) as exc:
        raise ValueError("V51_NATIVE_SPY_BAR_PRICE_INVALID") from exc
    if not val.is_finite() or val<=0:
        raise ValueError("V51_NATIVE_SPY_BAR_PRICE_INVALID")
    return val


def preview(rows: list[dict], *, session: date, source_sha256: str,
            source_unit_id: str) -> dict:
    by_start={}
    for row in rows:
        stamp=row["timestamp_utc"]
        if isinstance(stamp,str):
            stamp=datetime.fromisoformat(stamp.replace("Z","+00:00"))
        if not isinstance(stamp,datetime) or stamp.utcoffset() is None:
            raise ValueError("V51_NATIVE_SPY_TIMESTAMP_NOT_AWARE")
        local=stamp.astimezone(ET)
        if local.date()!=session or row.get("symbol")!="SPY":
            raise ValueError("V51_NATIVE_SPY_SESSION_MISMATCH")
        if local in by_start:
            raise ValueError("V51_NATIVE_SPY_DUPLICATE_MINUTE")
        op,hi,lo,cl=(_price(row[k]) for k in ("open","high","low","close"))
        if not lo<=min(op,cl)<=max(op,cl)<=hi:
            raise ValueError("V51_NATIVE_SPY_BAD_BAR_GEOMETRY")
        by_start[local]=(op,hi,lo,cl)
    open_clock=datetime.combine(session,time(9,30),tzinfo=ET)
    opening=[by_start.get(open_clock+timedelta(minutes=i)) for i in range(5)]
    raw_available=all(x is not None for x in opening)
    first=None
    missing=0
    hi=lo=None
    if raw_available:
        hi=max(x[1] for x in opening)
        lo=min(x[2] for x in opening)
        for minute in range(5,360):
            at=open_clock+timedelta(minutes=minute)
            sample=by_start.get(at)
            if sample is None:
                missing+=1
                break  # absence before breakout censors causal first event
            above=sample[1]>hi
            below=sample[2]<lo
            if above or below:
                first={"minute_start_et":at.isoformat(),
                       "minute_close_available_no_earlier_than_et":(at+timedelta(minutes=1)).isoformat(),
                       "direction_possible":"BOTH_AMBIGUOUS" if above and below else "CALL" if above else "PUT",
                       "high":str(sample[1]),"low":str(sample[2])}
                break
    reasons=[]
    if not raw_available:
        reasons.append("FIVE_OPENING_SPY_MINUTES_NOT_ALL_IN_NATIVE_SOURCE")
    if missing:
        reasons.append("MISSING_MINUTE_BEFORE_FIRST_POSSIBLE_BREAKOUT")
    if first and first["direction_possible"]=="BOTH_AMBIGUOUS":
        reasons.append("BOTH_BREAKOUT_DIRECTIONS_IN_FIRST_CANDIDATE_MINUTE")
    if not first and not reasons:
        reasons.append("NO_BREAKOUT_IN_AVAILABLE_09_35_TO_15_30_SOURCE")
    reasons.append("FIRST_BREAKOUT_TICK_AND_PUBLICATION_CLOCK_NOT_PROVEN")
    report={
        "contract":CONTRACT,"status":"OFFLINE_SOURCE_ONLY_PREVIEW_NOT_HISTORICAL_TRADE",
        "session":session.isoformat(),"symbol":"SPY",
        "source_unit_id":source_unit_id,"canonical_original_source_sha256":source_sha256,
        "observed_native_minute_rows":len(rows),
        "opening_range_completely_observed":raw_available,
        "opening_high":str(hi) if hi is not None else None,
        "opening_low":str(lo) if lo is not None else None,
        "first_possible_breakout_minute":first,
        "source_reason_codes":reasons,
        "historical_pit_publication_proven":False,
        "historical_option_contract_selected":False,
        "broker_fills":0,"provider_calls":0,"strategy_pnl":None,
    }
    report["fingerprint"]=_fingerprint(report)
    return report


def inspect_native_spy_day(project_root: Path, *, session: date) -> dict:
    if session>B34_MAX_SAMPLE_DATE:
        raise ValueError("V51_REFUSES_UNINSPECTED_MASTER_OR_FUTURE_SOURCE_DATE")
    layout=V2Layout.beneath(project_root/"data")
    try:
        units=discover_minute_units(layout)
    except IntradaySemanticsAuditError:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"NO_COMPLETED_NATIVE_MINUTE_CHECKPOINTS",
                "source_ready":False,"provider_calls":0}
    matching=[u for u in units if (u.year,u.month)==(session.year,session.month)
              and "SPY" in u.symbols]
    if not matching:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"NO_SPY_NATIVE_MINUTE_MONTHLY_SOURCE",
                "source_ready":False,"provider_calls":0}
    if len(matching)!=1:
        raise ValueError("V51_AMBIGUOUS_SPY_MONTHLY_SOURCE_UNITS")
    unit=matching[0]
    integrity=verify_unit_integrity(unit)
    if not integrity["accepted"]:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"CANONICAL_SOURCE_SHA_OR_RAW_BUNDLE_REJECTED",
                "unit_id":unit.unit_id,"source_ready":False,
                "integrity_errors":integrity["errors"],"provider_calls":0}
    rows=_sample_rows(unit.canonical_path,symbol="SPY",session_date=session)
    if not rows:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"NO_SPY_MINUTES_ON_REQUESTED_DATE",
                "source_ready":False,"provider_calls":0}
    check=validate_minute_rows(rows,sample_class="SPY_0DTE_ORB_SOURCE_PREVIEW",
        symbol="SPY",session_date=session)
    if not check["accepted"]:
        return {"contract":CONTRACT,"session":session.isoformat(),
                "status":"SPY_CANONICAL_MINUTE_GEOMETRY_UNQUALIFIED",
                "source_ready":False,"source_row_errors":check["errors"][:15],
                "provider_calls":0}
    result=preview(rows,session=session,source_sha256=unit.canonical_sha256,
                   source_unit_id=unit.unit_id)
    result["source_ready"]=True
    result["integrity_validated"]=True
    result["minute_source_warning_codes"]=check["warnings"]
    result["fingerprint"]=_fingerprint({k:v for k,v in result.items() if k!="fingerprint"})
    return result
