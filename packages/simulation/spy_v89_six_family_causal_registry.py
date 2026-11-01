from __future__ import annotations

"""V89: six NEW, preregistered SPY stock-only entry hypotheses.

All source features are 1-minute original OHLC bars *closed* before 09:35:01
or 09:40:01. This module NEVER reads future option quotes, calculates P&L or
places orders. Every decision, including NO_SIGNAL, is SHA-signed.
These thresholds are exploratory hypotheses, NOT proven predictive rules.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

ET=ZoneInfo("America/New_York")
CONTRACT="atlas-v89-six-new-causal-stock-entry-hypotheses-v1"

FAMILIES={
    "impulse_0935": {
        "decision":"09:35:01",
        "thesis":"directional first-five-minute move continues",
        "threshold_pct":"0.16",
    },
    "acceleration_0940": {
        "decision":"09:40:01",
        "thesis":"two positive or negative five-minute legs with acceleration",
        "first_leg_pct":"0.08", "second_leg_pct":"0.09",
    },
    "early_reversal_0940": {
        "decision":"09:40:01",
        "thesis":"second five-minute leg reverses an early opening impulse",
        "first_leg_pct":"0.18", "reverse_pct":"0.13",
    },
    "pullback_resume_0940": {
        "decision":"09:40:01",
        "thesis":"directional early impulse then partial retracement and final candle resumption",
        "first_leg_pct":"0.20", "min_retrace_pct":"0.25", "max_retrace_pct":"0.70",
    },
    "gap_followthrough_0940": {
        "decision":"09:40:01",
        "thesis":"opening gap persists and first ten-minute prices advance in gap direction",
        "minimum_gap_pct":"0.45", "followthrough_pct":"0.08",
    },
    "compression_release_0940": {
        "decision":"09:40:01",
        "thesis":"second five-minute range contracts and close favors one side",
        "max_range_ratio":"0.55", "close_extreme_fraction":"0.20",
    },
}


class V89Error(ValueError):
    pass


def signed(document):
    return {**document,"fingerprint":_fingerprint(document)}


def verified(document):
    return isinstance(document,dict) and document.get("fingerprint")==_fingerprint({
        k:v for k,v in document.items() if k!="fingerprint"
    })


def decimal(value):
    try:
        d=Decimal(str(value))
    except (ValueError,TypeError,InvalidOperation) as exc:
        raise V89Error("V89_INVALID_DECIMAL_BAR") from exc
    if not d.is_finite() or d<=0:
        raise V89Error("V89_NONPOSITIVE_OR_NONFINITE_BAR")
    return d


def percent(new,old):
    return (new/old-Decimal("1"))*Decimal("100")


def evaluate(family,*,session,stock_source_sha,bars,
             prior_close=None,prior_close_at_et=None,
             prior_close_available_at_et=None,
             market_session_verified=False):
    if family not in FAMILIES:
        raise V89Error("V89_UNREGISTERED_STRATEGY")
    if (market_session_verified is not True or not isinstance(stock_source_sha,str)
            or len(stock_source_sha)!=64 or
            any(c not in "0123456789abcdef" for c in stock_source_sha)):
        raise V89Error("V89_ORIGINAL_STOCK_SOURCE_NOT_VERIFIED")
    day=date.fromisoformat(session)
    spec=FAMILIES[family]
    hh,mm,ss=map(int,spec["decision"].split(":"))
    decision=datetime.combine(day,time(hh,mm,ss),ET)
    if len(bars)!=(5 if mm==35 else 10):
        raise V89Error("V89_EXACT_CLOSED_MINUTES_REQUIRED")
    ordered={}
    for bar in bars:
        source_at=datetime.fromisoformat(bar["minute_at_et"])
        source_available=datetime.fromisoformat(bar["available_at_et"])
        if source_at.utcoffset() is None or source_available.utcoffset() is None:
            raise V89Error("V89_NAIVE_ORIGINAL_SOURCE_CLOCK")
        at=source_at.astimezone(ET)
        available=source_available.astimezone(ET)
        if (available.utcoffset() is None
                or available<at+timedelta(minutes=1) or available>decision
                or at.date()!=day or at.second!=0):
            raise V89Error("V89_FUTURE_OR_NOT_YET_PUBLISHED_MINUTE")
        clock=at.strftime("%H:%M")
        if clock in ordered:
            raise V89Error("V89_DUPLICATE_ORIGINAL_MINUTE")
        p={k:decimal(bar[k]) for k in ("open","high","low","close")}
        if not (p["low"]<=p["open"]<=p["high"]
                and p["low"]<=p["close"]<=p["high"]):
            raise V89Error("V89_ORIGINAL_OHLC_INVALID")
        ordered[clock]=p
    required=[f"09:{m:02d}" for m in range(30,mm)]
    if sorted(ordered)!=required:
        raise V89Error("V89_MISSING_OR_EXTRA_ORIGINAL_MINUTE")
    candles=[ordered[c] for c in required]
    first=candles[:5]
    second=candles[5:]
    o=first[0]["open"]
    first_end=first[-1]["close"]
    last=candles[-1]["close"]
    high1=max(c["high"] for c in first)
    low1=min(c["low"] for c in first)
    fleg=percent(first_end,o)
    features={
        "opening_price":str(o),
        "first_five_close":str(first_end),
        "last_completed_close":str(last),
        "first_leg_pct":str(fleg),
        "first_range_high":str(high1),
        "first_range_low":str(low1),
        "original_minute_count":len(candles),
    }
    direction=None
    if family=="impulse_0935":
        t=Decimal(spec["threshold_pct"])
        direction="CALL" if fleg>=t else "PUT" if fleg<=-t else None
    else:
        second_leg=percent(last,first_end)
        features["second_leg_pct"]=str(second_leg)
        if family=="acceleration_0940":
            a=Decimal(spec["first_leg_pct"])
            b=Decimal(spec["second_leg_pct"])
            direction=("CALL" if fleg>=a and second_leg>=b and second_leg>=fleg else
                       "PUT" if fleg<=-a and second_leg<=-b and second_leg<=fleg else None)
        elif family=="early_reversal_0940":
            a=Decimal(spec["first_leg_pct"])
            b=Decimal(spec["reverse_pct"])
            direction=("PUT" if fleg>=a and second_leg<=-b else
                       "CALL" if fleg<=-a and second_leg>=b else None)
        elif family=="pullback_resume_0940":
            a=Decimal(spec["first_leg_pct"])
            minr=Decimal(spec["min_retrace_pct"])
            maxr=Decimal(spec["max_retrace_pct"])
            fraction=abs((first_end-last)/(first_end-o)) if first_end!=o else Decimal("0")
            features["retracement_fraction"]=str(fraction)
            final=candles[-1]
            bullish=final["close"]>final["open"]
            bearish=final["close"]<final["open"]
            direction=("CALL" if fleg>=a and minr<=fraction<=maxr and bullish else
                       "PUT" if fleg<=-a and minr<=fraction<=maxr and bearish else None)
        elif family=="gap_followthrough_0940":
            if (prior_close is None or prior_close_at_et is None
                    or prior_close_available_at_et is None):
                raise V89Error("V89_GAP_PRIOR_SESSION_CLOSE_REQUIRED")
            original_pat=datetime.fromisoformat(prior_close_at_et)
            original_pav=datetime.fromisoformat(prior_close_available_at_et)
            if original_pat.utcoffset() is None or original_pav.utcoffset() is None:
                raise V89Error("V89_NAIVE_PRIOR_STOCK_CLOSE_CLOCK")
            pat=original_pat.astimezone(ET)
            pav=original_pav.astimezone(ET)
            if pat.date()>=day or pav<pat or pav>decision:
                raise V89Error("V89_PRIOR_CLOSE_NOT_CAUSALLY_AVAILABLE")
            gap=percent(o,decimal(prior_close))
            following=percent(last,o)
            features.update({"original_prior_close":str(prior_close),
                             "prior_at_et":pat.isoformat(),
                             "prior_available_at_et":pav.isoformat(),
                             "gap_pct":str(gap),
                             "followthrough_pct":str(following),
                             "prior_close_publication_independently_proven":False})
            a=Decimal(spec["minimum_gap_pct"])
            b=Decimal(spec["followthrough_pct"])
            direction=("CALL" if gap>=a and following>=b else
                       "PUT" if gap<=-a and following<=-b else None)
        elif family=="compression_release_0940":
            high2=max(c["high"] for c in second)
            low2=min(c["low"] for c in second)
            span1=high1-low1
            span2=high2-low2
            allhi=max(high1,high2)
            alllo=min(low1,low2)
            if span1<=0 or allhi<=alllo:
                raise V89Error("V89_ZERO_ORIGINAL_RANGE")
            ratio=span2/span1
            location=(last-alllo)/(allhi-alllo)
            features.update({"second_range_high":str(high2),
                             "second_range_low":str(low2),
                             "compression_ratio":str(ratio),
                             "close_location_fraction":str(location)})
            cap=Decimal(spec["max_range_ratio"])
            side=Decimal(spec["close_extreme_fraction"])
            direction=("CALL" if ratio<=cap and location>=1-side and last>o else
                       "PUT" if ratio<=cap and location<=side and last<o else None)
    return signed({
        "contract":CONTRACT,
        "strategy_id":family,
        "strategy_registry_sha":_fingerprint(FAMILIES),
        "session":session,"decision_at_et":decision.isoformat(),
        "direction":direction,
        "status":"OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED" if direction else "NO_SIGNAL",
        "reason":"FROZEN_NEW_HYPOTHESIS_MATCH" if direction else "FROZEN_HYPOTHESIS_NOT_MET",
        "features":features,
        "source_stock_sha256":stock_source_sha,
        "source_session_verified":True,
        "source_bar_count":len(candles),
        "all_features_from_closed_bars_as_of_decision":True,
        "actual_orders":0,"broker_fills":0,
        "option_contract_selected":False,
        "future_quote_used":False,
        "hypothesis_is_exploratory_not_evidence_of_profit":True,
    })
