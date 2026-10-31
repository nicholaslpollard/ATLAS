from __future__ import annotations

"""V82: independently causal SPY entry families and source-demand bridge.

No trades, source GET, future prices, option selection, P&L, or broker fill.
A higher-level runner can feed ONLY source-verified stock bars whose release
clock <= decision and then resolve any selected exact option source via V39.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_on_demand_source_cache_v38 import normalize_source_requirement

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v82-options-first-three-independent-entry-family-registry-v1"

REGISTRY={
    "orb_continuation_0940":{
        "decision_clock":"09:40:01",
        "setup":"09:30-09:34 opening-range breakout with 09:35-09:39 continuation",
        "required_prior_evidence":"FIRST_TEN_MINUTES_OF_SESSION",
        "version":"v82.1",
    },
    "failed_breakout_fade_0940":{
        "decision_clock":"09:40:01",
        "setup":"09:30-09:34 range breakout rejected by 09:39 close",
        "required_prior_evidence":"FIRST_TEN_MINUTES_OF_SESSION",
        "version":"v82.1",
    },
    "gap_fade_0935":{
        "decision_clock":"09:35:01",
        "setup":"prior full-session close versus 09:30 gap and first five-minute fade",
        "required_prior_evidence":"PREVIOUS_SESSION_CLOSE_AND_FIRST_FIVE_MINUTES",
        "version":"v82.1",
        "minimum_gap_pct":"0.60",
    },
}


class V82Error(ValueError):
    pass


def _decimal(x):
    try:
        d=Decimal(str(x))
    except (ValueError,InvalidOperation,TypeError) as exc:
        raise V82Error("V82_PRICE_NOT_DECIMAL") from exc
    if not d.is_finite() or d<=0:
        raise V82Error("V82_NONPOSITIVE_OR_NONFINITE_SOURCE_PRICE")
    return d


def _dt(x):
    try:
        d=datetime.fromisoformat(x) if isinstance(x,str) else x
    except (TypeError,ValueError) as exc:
        raise V82Error("V82_BAD_SOURCE_TIMESTAMP") from exc
    if not isinstance(d,datetime) or d.utcoffset() is None:
        raise V82Error("V82_NAIVE_SOURCE_TIMESTAMP")
    return d.astimezone(ET)


def _signed(data):
    return {**data,"fingerprint":_fingerprint(data)}


def _verify(data):
    return isinstance(data,dict) and data.get("fingerprint")==_fingerprint({
        k:v for k,v in data.items() if k!="fingerprint"
    })


def _bar(raw,day,decision):
    if not isinstance(raw,dict):
        raise V82Error("V82_BAR_SHAPE_INVALID")
    at=_dt(raw.get("minute_at_et"))
    available=_dt(raw.get("available_at_et"))
    if (at.date()!=day or at.second!=0 or at.microsecond!=0
            or available<at+timedelta(minutes=1)
            or available>decision):
        raise V82Error("V82_FUTURE_OR_NOT_YET_CLOSED_MINUTE")
    values={k:_decimal(raw.get(k)) for k in ("open","high","low","close")}
    if not values["low"]<=values["open"]<=values["high"] or not values["low"]<=values["close"]<=values["high"]:
        raise V82Error("V82_INVALID_OHLC_GEOMETRY")
    return at,values


def evaluate(family,*,session:str,stock_source_sha:str,bars:list[dict],
             prior_close=None,prior_close_at_et=None,prior_close_available_at_et=None,
             prior_closing_bar_publication_independently_proven:bool=False,
             market_session_verified:bool=False):
    if family not in REGISTRY:
        raise V82Error("V82_UNREGISTERED_ENTRY_FAMILY")
    if (type(market_session_verified) is not bool or not market_session_verified or
            type(stock_source_sha) is not str or len(stock_source_sha)!=64 or
            any(k not in "0123456789abcdef" for k in stock_source_sha)):
        raise V82Error("V82_STOCK_SOURCE_OR_SESSION_NOT_VERIFIED")
    try:
        day=date.fromisoformat(session)
    except (ValueError,TypeError) as exc:
        raise V82Error("V82_SESSION_DATE_INVALID") from exc
    if not isinstance(bars,list):
        raise V82Error("V82_MINUTE_BARS_REQUIRED")
    policy=REGISTRY[family]
    hh,mm,ss=map(int,policy["decision_clock"].split(":"))
    decision=datetime.combine(day,time(hh,mm,ss),ET)
    source={}
    for raw in bars:
        stamp,values=_bar(raw,day,decision)
        if stamp in source:
            raise V82Error("V82_DUPLICATE_SOURCE_BAR_CLOCK")
        source[stamp.time().strftime("%H:%M")]=values
    required=[f"09:{i:02d}" for i in range(30,40 if hh==9 and mm==40 else 35)]
    # No silent gap interpolation or substitution from later bars.
    if sorted(source)!=required:
        raise V82Error("V82_EXACT_REQUIRED_SOURCE_WINDOW_MISSING_OR_EXTRA")
    first=[source[k] for k in required[:5]]
    opening_high=max(x["high"] for x in first)
    opening_low=min(x["low"] for x in first)
    last=source[required[-1]]["close"]
    open_at_0930=first[0]["open"]
    call=put=False
    reason=None
    feature={
        "opening_range_high":str(opening_high),
        "opening_range_low":str(opening_low),
        "first_open":str(open_at_0930),
        "last_closed_bar_close":str(last),
    }
    if family=="orb_continuation_0940":
        call=last>opening_high and last>source["09:35"]["close"]
        put=last<opening_low and last<source["09:35"]["close"]
        reason="CLOSED_BAR_BREAKOUT_CONTINUATION"
    elif family=="failed_breakout_fade_0940":
        recent=[source[k] for k in required[5:]]
        crossed_high=max(x["high"] for x in recent)>opening_high
        crossed_low=min(x["low"] for x in recent)<opening_low
        # Reject ambiguous days with dual breakouts/rejections.
        call=crossed_low and not crossed_high and opening_low<last<opening_high
        put=crossed_high and not crossed_low and opening_low<last<opening_high
        reason="FAILED_BREAKOUT_REJECTED_INTO_OPENING_RANGE"
        feature["recent_crossed_high"]=crossed_high
        feature["recent_crossed_low"]=crossed_low
    else:
        if type(prior_closing_bar_publication_independently_proven) is not bool:
            raise V82Error("V82_PRIOR_CLOSE_PUBLICATION_PROOF_FLAG_INVALID")
        if prior_close is None or prior_close_at_et is None or prior_close_available_at_et is None:
            raise V82Error("V82_PRIOR_CLOSE_EVIDENCE_REQUIRED")
        prior_at=_dt(prior_close_at_et)
        prior_available=_dt(prior_close_available_at_et)
        if (prior_at.date()>=day or prior_available<prior_at or
                prior_available>decision or prior_at.hour<9 or prior_at.hour>16):
            raise V82Error("V82_PRIOR_CLOSE_FUTURE_OR_INVALID")
        prior=_decimal(prior_close)
        gap=(open_at_0930-prior)/prior*Decimal(100)
        threshold=Decimal(policy["minimum_gap_pct"])
        call=gap<=-threshold and last>open_at_0930
        put=gap>=threshold and last<open_at_0930
        reason="PREVIOUS_SESSION_GAP_WITH_FIVE_MINUTE_MEAN_REVERSION"
        feature["prior_close"]=str(prior)
        feature["opening_gap_pct"]=str(gap)
        feature["prior_close_at_et"]=prior_at.isoformat()
        feature["prior_close_available_at_et"]=prior_available.isoformat()
        feature["prior_closing_bar_publication_independently_proven"]=prior_closing_bar_publication_independently_proven
    if call and put:
        raise V82Error("V82_CONTRADICTORY_STRATEGY_DIRECTION")
    direction="CALL" if call else "PUT" if put else None
    result=_signed({
        "contract":CONTRACT,
        "strategy_id":family,"strategy_version":policy["version"],
        "strategy_registry_sha":_fingerprint(REGISTRY),
        "session":session,
        "decision_at_et":decision.isoformat(),
        "source_stock_sha256":stock_source_sha,
        "source_bar_count":len(source),
        "all_features_from_closed_bars_as_of_decision":True,
        "source_session_verified":True,
        "features":feature,
        "direction":direction,
        "status":"OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED" if direction else "NO_SIGNAL",
        "reason":reason if direction else "PREDECLARED_ENTRY_CONDITIONS_NOT_MET",
        "stock_fallback_status":"UNPRICED_AND_UNAUTHORIZED",
        "future_quote_used":False,
        "actual_orders":0,"broker_fills":0,
        "option_contract_selected":False,
        "source_acquisition_permitted_only_after_prior_qualified_selection":True,
    })
    return result


def exact_option_demand(decision:dict,*,selected_contract:dict,
                        selection_at_et:str,selection_source_sha256:str,
                        end_time_et:str="15:30:00.000"):
    """Build one new V39 source need only for a causally selected contract.

    No strike/expiry derived from later option tape. New families or contract
    choices produce their OWN exact query IDs, cache first via V39. This
    function does not open the network itself.
    """
    if not _verify(decision) or decision.get("contract")!=CONTRACT:
        raise V82Error("V82_ENTRY_DECISION_SIGNATURE_INVALID")
    if decision.get("status")!="OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED":
        raise V82Error("V82_NO_SIGNAL_CANNOT_DEMAND_OPTION_QUOTES")
    if (not isinstance(selected_contract,dict) or
            not selection_source_sha256 or
            len(selection_source_sha256)!=64 or
            any(c not in "0123456789abcdef" for c in selection_source_sha256)):
        raise V82Error("V82_OPTION_SELECTION_SOURCE_NOT_PROVEN")
    # Contract selection evidence must predate the registered signal clock.
    if _dt(selection_at_et)>=_dt(decision["decision_at_et"]):
        raise V82Error("V82_FUTURE_SELECTED_CONTRACT_FORBIDDEN")
    expected=("call" if decision["direction"]=="CALL" else "put")
    if (selected_contract.get("symbol")!="SPY" or
            selected_contract.get("date_et")!=decision["session"] or
            selected_contract.get("right")!=expected or
            not selected_contract.get("expiration") or
            not selected_contract.get("strike")):
        raise V82Error("V82_CONTRACT_NOT_ALIGNED_WITH_ENTRY_DECISION")
    # Work within the already supported exact V65/V39 option-tape provider
    # shape. Do not invent a new method/SDK permission.
    t=_dt(decision["decision_at_et"])
    req=normalize_source_requirement(
        "option_history_exact_quote_tape",{
            **selected_contract,
            "start_time_et":t.strftime("%H:%M:%S")+".000",
            "end_time_et":end_time_et,"interval":"1s",
        })
    qid=_fingerprint(req)
    return _signed({
        "contract":"atlas-v82-causal-option-exact-source-demand-v1",
        "strategy_decision_sha":decision["fingerprint"],
        "strategy_version":decision["strategy_id"]+"_"+decision["strategy_version"],
        "candidate_id":"SPY_"+decision["session"]+"_"+decision["strategy_id"]+"_"+expected,
        "purpose":"original_exact_entry_and_exit_tape",
        "method":req["method"],
        "kwargs":req["kwargs"],
        "query_id":qid,
        "selection_at_et":_dt(selection_at_et).isoformat(),
        "selection_prior_source_sha256":selection_source_sha256,
        "provider_requests":0,"broker_orders":0,
        "uses_v39_read_through_cache_only":True,
        "caller_must_revalidate_expiry_strike_deliverable_and_liquidity":True,
    })


def v39_demand(source_request):
    if (not _verify(source_request) or
            source_request.get("contract")!="atlas-v82-causal-option-exact-source-demand-v1"):
        raise V82Error("V82_UNVERIFIED_OPTION_SOURCE_REQUIREMENT")
    return {key:source_request[key]
            for key in ("candidate_id","purpose","method","kwargs")}
