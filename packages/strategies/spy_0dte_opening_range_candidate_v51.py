from __future__ import annotations

"""V51 SPY 0DTE opening-range breakout source-only detection and exact demands.

One-minute OHLC bars identify the first minute containing a possible breakout.
They NEVER establish which tick crossed first, the ATM price at the crossing,
an actual decision-time fill, or option stop/target execution. Those require a
separately source-proven tick and actionable option quote tape.
"""

from datetime import datetime, timedelta, time
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-spy-0dte-opening-range-causal-candidate-v51"
DEMAND_CONTRACT = "atlas-spy-0dte-orb-exact-option-source-demands-v51"
EASTERN = ZoneInfo("America/New_York")
BASE = "external-spy-0dte-opening-range-breakout-published-v1"
ALL_DAYS = "atlas-spy-0dte-opening-range-all-weekdays-preregistered-v1"
MWF = frozenset((0, 2, 4))
ALL = frozenset(range(5))


class OrbError(ValueError):
    pass


def _when(value):
    try:
        dt=datetime.fromisoformat(value)
    except (TypeError,ValueError) as exc:
        raise OrbError("V51_TIMESTAMP_INVALID") from exc
    if dt.utcoffset() is None:
        raise OrbError("V51_TIMESTAMP_NOT_TIMEZONE_AWARE")
    return dt.astimezone(EASTERN)


def _value(raw):
    try:
        val=Decimal(str(raw))
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise OrbError("V51_SPY_BAR_PRICE_INVALID") from exc
    if not val.is_finite() or val<=0:
        raise OrbError("V51_SPY_BAR_PRICE_INVALID")
    return val


def _snapshot(bar: dict) -> dict:
    if bar.get("symbol")!="SPY":
        raise OrbError("V51_WRONG_UNDERLYING")
    start=_when(bar["bar_start_et"])
    if start.second!=0 or start.microsecond!=0:
        raise OrbError("V51_EXPECTED_MINUTE_START")
    end=start+timedelta(minutes=1)
    if not isinstance(bar.get("source_query_id"),str) or not bar["source_query_id"] or not isinstance(bar.get("source_sha256"),str) or re.fullmatch(r"[0-9a-f]{64}",bar["source_sha256"]) is None:
        raise OrbError("V51_UNVERIFIED_SOURCE_REF")
    # A bar's OHLC is not known at the beginning of the minute.
    known=_when(bar["available_at_et"])
    if known<end:
        raise OrbError("V51_FUTURE_MINUTE_BAR_LEAKAGE")
    op,hi,lo,cl=(_value(bar[k]) for k in ("open","high","low","close"))
    if lo>min(op,cl) or hi<max(op,cl) or hi<lo:
        raise OrbError("V51_INVALID_OHLC_STRUCTURE")
    return {
        "bar_start_et":start.isoformat(),
        "bar_end_et":end.isoformat(),
        "bar_available_et":known.isoformat(),
        "open":str(op),"high":str(hi),"low":str(lo),"close":str(cl),
        "source_query_id":bar["source_query_id"],
        "source_sha256":bar["source_sha256"],
        "first_publication_proven":bar.get("first_publication_proven") is True,
    }


def first_breakout_candidate(
    minute_bars: list[dict], *,
    policy: str=BASE,
) -> dict:
    """Source-only first-containing-minute candidate. No option trading."""
    if policy not in (BASE,ALL_DAYS):
        raise OrbError("V51_UNREGISTERED_WEEKDAY_POLICY")
    if not isinstance(minute_bars,list) or not 1<=len(minute_bars)<=400:
        raise OrbError("V51_BAR_POPULATION_INVALID")
    rows=[_snapshot(b) for b in minute_bars]
    rows.sort(key=lambda r:r["bar_start_et"])
    if len({r["bar_start_et"] for r in rows})!=len(rows):
        raise OrbError("V51_DUPLICATE_MINUTE_BAR")
    dates={_when(r["bar_start_et"]).date().isoformat() for r in rows}
    if len(dates)!=1:
        raise OrbError("V51_MULTIPLE_SESSIONS_MIXED")
    day=next(iter(dates))
    session=_when(rows[0]["bar_start_et"]).date()
    open_start=datetime.combine(session,time(9,30),tzinfo=EASTERN)
    session_end=datetime.combine(session,time(15,30),tzinfo=EASTERN)
    series={_when(r["bar_start_et"]):r for r in rows}
    opening=[series.get(open_start+timedelta(minutes=i)) for i in range(5)]
    base={
        "contract":CONTRACT,
        "strategy_version":policy,
        "date_et":day,
        "source_authority":"SOURCE_ONLY_MINUTE_BAR_NOT_TICK_DECISION",
        "published_mwf_filter":policy==BASE,
        "original_0dte_option_trades_executed":0,
        "qualified_historical_broker_fills":0,
        "requires_exact_tick_first_breakout_and_option_quotes":True,
        "opening_interval_et":"09:30_TO_09:35",
        "opening_source_bars":opening,
        "opening_high":None,"opening_low":None,
        "first_possible_breakout_bar":None,
        "status":None,"reason_codes":[],
    }
    if any(r is None for r in opening):
        base["status"]="OPENING_RANGE_INCOMPLETE"
        base["reason_codes"]=["MISSING_ONE_OR_MORE_09:30_TO_09:34_BARS"]
    elif any(not r["first_publication_proven"] for r in opening):
        base["status"]="SOURCE_PUBLICATION_UNQUALIFIED"
        base["reason_codes"]=["ONE_OR_MORE_OPENING_BARS_LACK_HISTORICAL_AVAILABILITY_PROOF"]
    else:
        high=max(_value(x["high"]) for x in opening)
        low=min(_value(x["low"]) for x in opening)
        base["opening_high"],base["opening_low"]=str(high),str(low)
        if session.weekday() not in (MWF if policy==BASE else ALL):
            base["status"]="WEEKDAY_EXCLUDED_BY_FROZEN_STRATEGY"
            base["reason_codes"]=["SOURCE_PUBLISHED_MWF_FILTER"]
        else:
            first=None
            missing_before_first=False
            expected_next=open_start+timedelta(minutes=5)
            for r in rows:
                start=_when(r["bar_start_et"])
                if start<open_start+timedelta(minutes=5) or start>=session_end:
                    continue
                if start!=expected_next:
                    missing_before_first=True
                    break
                expected_next=start+timedelta(minutes=1)
                above=_value(r["high"])>high
                below=_value(r["low"])<low
                if above or below:
                    first={**r, "possible_breakout_direction":(
                        "AMBIGUOUS_BOTH" if above and below else "CALL" if above else "PUT"
                    )}
                    break
            base["first_possible_breakout_bar"]=first
            if missing_before_first:
                base["status"]="BREAKOUT_MINUTE_SEQUENCE_INCOMPLETE"
                base["reason_codes"]=["MISSING_MINUTE_BEFORE_FIRST_POSSIBLE_BREAKOUT"]
            elif first is None:
                base["status"]="NO_BREAKOUT_WITHIN_OBSERVED_MINUTE_BARS"
                base["reason_codes"]=["NO_BREAKOUT_SOURCE_OBSERVED"]
            elif not first["first_publication_proven"]:
                base["status"]="SOURCE_PUBLICATION_UNQUALIFIED"
                base["reason_codes"]=["BREAKOUT_BAR_HISTORICAL_AVAILABILITY_UNPROVEN"]
            elif first["possible_breakout_direction"]=="AMBIGUOUS_BOTH":
                base["status"]="AMBIGUOUS_INTRAMINUTE_BREAKOUT"
                base["reason_codes"]=["BOTH_OPENING_RANGE_BOUNDARIES_BREACHED_IN_SAME_MINUTE"]
            else:
                base["status"]="POSSIBLE_FIRST_BREAKOUT_NEEDS_TICK_CONFIRMATION"
                base["reason_codes"]=["ONE_MINUTE_HIGH_LOW_CANNOT_PROVE_FIRST_BREAKOUT_TICK_TIME",
                                      "OPTION_ATM_STRIKE_AND_FILL_NOT_YET_DETERMINABLE"]
    base["fingerprint"]=_fingerprint(base)
    return base


def exact_entry_demands(
    candidate: dict, verified_first_breakout_tick: dict,
    *, action_lag_seconds: tuple[int,...]=(1,3),
) -> dict:
    """Construct V39 exact quote requests only after independently proved tick.

    This does NOT resolve source requests or validate resulting historical
    quote publication. It does not preselect future profitable exit periods.
    """
    if (candidate.get("contract")!=CONTRACT
            or candidate.get("fingerprint")!=_fingerprint({k:v for k,v in candidate.items() if k!="fingerprint"})
            or candidate.get("status")!="POSSIBLE_FIRST_BREAKOUT_NEEDS_TICK_CONFIRMATION"):
        raise OrbError("V51_CANDIDATE_NOT_SIGNED_OR_NOT_ELIGIBLE")
    if (not isinstance(verified_first_breakout_tick,dict)
            or verified_first_breakout_tick.get("first_breakout_tick_verified") is not True
            or verified_first_breakout_tick.get("same_day_first_breakout_certified") is not True
            or not verified_first_breakout_tick.get("source_query_id")
            or re.fullmatch(r"[0-9a-f]{64}", str(verified_first_breakout_tick.get("source_sha256",""))) is None):
        raise OrbError("V51_BREAKOUT_TICK_PROVENANCE_UNVERIFIED")
    ts=_when(verified_first_breakout_tick["timestamp_et"])
    known=_when(verified_first_breakout_tick["available_at_et"])
    if known<ts or ts.date().isoformat()!=candidate["date_et"]:
        raise OrbError("V51_TICK_TIME_OR_SESSION_INVALID")
    if (known-ts).total_seconds()>3:
        raise OrbError("V51_TICK_PUBLICATION_LAG_UNQUALIFIED_FOR_ONE_TO_THREE_SECOND_ACTION")
    opening_finish=datetime.combine(ts.date(),time(9,35),tzinfo=EASTERN)
    if not opening_finish<=ts<datetime.combine(ts.date(),time(15,30),tzinfo=EASTERN):
        raise OrbError("V51_TICK_OUTSIDE_ALLOWED_BREAKOUT_HOURS")
    containing=candidate["first_possible_breakout_bar"]
    start=_when(containing["bar_start_et"])
    if not start<=ts<start+timedelta(minutes=1):
        raise OrbError("V51_BREAKOUT_TICK_NOT_IN_FIRST_CANDIDATE_MINUTE")
    spot=_value(verified_first_breakout_tick["underlying_spot"])
    high,low=_value(candidate["opening_high"]),_value(candidate["opening_low"])
    direction="CALL" if spot>high else "PUT" if spot<low else None
    if direction!=containing["possible_breakout_direction"]:
        raise OrbError("V51_BREAKOUT_DIRECTION_OR_LEVEL_NOT_CONFIRMED")
    if tuple(action_lag_seconds) not in ((1,),(3,),(1,3)):
        raise OrbError("V51_UNREGISTERED_QUOTE_LATENCY_PLAN")
    strike=spot.quantize(Decimal("1"),rounding=ROUND_HALF_UP)
    # Source-only exact quotes at the first *known* tick or a later action clock:
    # an observation date alone is never an executable order or first-pub proof.
    reference=max(ts,known)
    if reference+timedelta(seconds=max(action_lag_seconds))>=datetime.combine(ts.date(),time(15,30),tzinfo=EASTERN):
        raise OrbError("V51_ACTION_CLOCK_NOT_BEFORE_PUBLISHED_TIME_EXIT")
    expiry=candidate["date_et"]
    right="call" if direction=="CALL" else "put"
    qs=[]
    for label,at in [("order_reference",reference),*[
        (f"independent_action_plus_{s}s",reference+timedelta(seconds=s))
        for s in action_lag_seconds]]:
        qs.append({
            "candidate_id":f"ORB:{candidate['date_et']}:{direction}:{str(strike)}",
            "purpose":label,
            "method":"option_at_time_quote",
            "kwargs":{
                "symbol":"SPY","expiration":expiry,"strike":str(strike),
                "right":right,"date_et":expiry,
                "time_of_day_et":at.strftime("%H:%M:%S.%f")[:12],
            },
            "requested_observation_as_of_et":at.isoformat(),
            "source_acquisition_is_not_fill_authority":True,
        })
    result={
        "contract":DEMAND_CONTRACT,
        "strategy_version":candidate["strategy_version"],
        "candidate_fingerprint":candidate["fingerprint"],
        "tick_source_query_id":verified_first_breakout_tick["source_query_id"],
        "tick_source_sha256":verified_first_breakout_tick["source_sha256"],
        "first_verified_tick_et":ts.isoformat(),
        "first_known_tick_et":known.isoformat(),
        "selected_original_contract":{"underlying":"SPY","expiry":expiry,
                                      "strike":str(strike),"right":right},
        "query_count":len(qs),
        "demands":qs,
        "historical_quote_availability_qualified":False,
        "historical_trade_executed":False,
        "exit_watches_must_be_generated_on_each_future_source_observation":True,
    }
    result["fingerprint"]=_fingerprint(result)
    return result
