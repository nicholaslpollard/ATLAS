from __future__ import annotations

"""V60 side-aware quote sanity using *independent* point-in-time BSM inputs.

A quote with wide spread is not intrinsically unusable: buying acts on ASK,
selling acts on BID. Reject suspicious action-side pricing; allow a candidate
side only when an independently derived and tight fair-value band supports it.
All assessments remain developmental; never assert a broker fill or alpha.

The underlying SPY option is American-style; Black-Scholes-Merton is a
European-equivalent benchmark, not a guaranteed SPY executable market price.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from math import isfinite

from packages.simulation.historical_option_greeks_v1 import _price_and_greeks

CONTRACT="atlas-v60-independent-valuation-quote-side-gate-v1"
MAX_QUOTE_AGE_SECONDS=1.0
MAX_SPOT_AGE_SECONDS=2.0
MAX_VOL_AGE_SECONDS=10.0
MAX_MODEL_BAND_RELATIVE_WIDTH=0.15
MAX_SPREAD_PCT=15.0
PRICE_TOLERANCE_DOLLARS=0.02


class QuoteSideError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IndependentActionEvidence:
    action: str
    option_right: str
    quote_at: datetime
    decision_at: datetime
    expiration_at: datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    contracts: int
    spot: float
    spot_at: datetime
    independent_iv_lower: float
    independent_iv_upper: float
    volatility_at: datetime
    historical_rate: float
    historical_dividend_yield: float
    strike: float
    spot_source_id: str
    iv_source_id: str
    rate_source_id: str
    dividend_source_id: str
    acted_quote_source_id: str
    standard_100_share_deliverable: bool
    raw_spot_as_traded: bool
    iv_derived_from_current_acted_quote: bool = False


def _stamp(x,tag):
    if not isinstance(x,datetime) or x.tzinfo is None or x.utcoffset() is None:
        raise QuoteSideError(f"{tag}_WITHOUT_TIMEZONE")
    return x.astimezone(timezone.utc)


def _num(value,tag):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value):
        raise QuoteSideError(f"{tag}_NOT_FINITE_NUMBER")
    return float(value)


def classify_action_side(x:IndependentActionEvidence):
    """An independent valuation audit; no model-generated bid/ask/fill.

    Outcomes: ACTION_SIDE_MODEL_CONSISTENT, REJECT_ACTION_SIDE_DEVIATION,
    ABSTAIN_MODEL_UNCERTAIN, REJECT_ACTION_SIDE_SIZE, ABSTAIN_BAD_INPUT.
    Model compatibility is a *research candidate* only, not execution proof.
    """
    if not isinstance(x,IndependentActionEvidence):
        raise QuoteSideError("MISSING_EVIDENCE")
    action=x.action.lower()
    right=x.option_right.lower()
    if action not in ("buy","sell") or right not in ("call","put"):
        raise QuoteSideError("ACTION_OR_OPTION_RIGHT_INVALID")
    quote_at=_stamp(x.quote_at,"QUOTE")
    now=_stamp(x.decision_at,"DECISION")
    spot_at=_stamp(x.spot_at,"SPOT")
    iv_at=_stamp(x.volatility_at,"VOLATILITY")
    expiry=_stamp(x.expiration_at,"EXPIRY")
    for field in ("bid","ask","spot","strike","independent_iv_lower",
                  "independent_iv_upper","historical_rate","historical_dividend_yield"):
        _num(getattr(x,field),field.upper())
    if (not (0 < x.bid<=x.ask and x.spot>0 and x.strike>0
             and 0<x.independent_iv_lower<=x.independent_iv_upper<=5
             and -0.05<=x.historical_rate<=0.30
             and 0<=x.historical_dividend_yield<=0.30)
            or type(x.contracts) is not int or x.contracts<=0
            or type(x.bid_size) is not int or x.bid_size<0
            or type(x.ask_size) is not int or x.ask_size<0):
        raise QuoteSideError("INVALID_PRICE_VOL_OR_SIZE")
    if (expiry<=now or now<quote_at or now<spot_at or now<iv_at
            or (now-quote_at).total_seconds()>MAX_QUOTE_AGE_SECONDS
            or (now-spot_at).total_seconds()>MAX_SPOT_AGE_SECONDS
            or (now-iv_at).total_seconds()>MAX_VOL_AGE_SECONDS):
        return {
            "contract":CONTRACT,"status":"ABSTAIN_STALE_OR_FUTURE_REFERENCE",
            "reason":"QUOTE_SPOT_VOL_EXPIRY_CLOCK_UNQUALIFIED",
            "action":action,"option_right":right,"action_price":x.ask if action=="buy" else x.bid,
            "historical_fills":0,
        }
    provenance=(x.spot_source_id,x.iv_source_id,x.rate_source_id,
                x.dividend_source_id,x.acted_quote_source_id)
    if (any(not isinstance(v,str) or not v.strip() for v in provenance)
            or x.iv_derived_from_current_acted_quote
            or x.iv_source_id==x.acted_quote_source_id
            or not x.standard_100_share_deliverable or not x.raw_spot_as_traded):
        return {
            "contract":CONTRACT,"status":"ABSTAIN_UNTRUSTED_REFERENCE",
            "reason":"INDEPENDENT_IV_SOURCE_OR_CONTRACT_BASIS_UNPROVEN",
            "action":action,"option_right":right,"historical_fills":0,
        }
    years=(expiry-now).total_seconds()/(365*86400)
    try:
        lower=_price_and_greeks(right,x.spot,x.strike,years,x.historical_rate,
                                x.historical_dividend_yield,x.independent_iv_lower)[0]
        upper=_price_and_greeks(right,x.spot,x.strike,years,x.historical_rate,
                                x.historical_dividend_yield,x.independent_iv_upper)[0]
    except (ValueError,ZeroDivisionError,OverflowError) as exc:
        raise QuoteSideError("BSM_REFERENCE_CALCULATION_FAILED") from exc
    if not(isfinite(lower) and isfinite(upper) and 0<=lower<=upper):
        raise QuoteSideError("BSM_REFERENCE_OUTSIDE_BOUNDS")
    wide=(x.ask-x.bid)/((x.ask+x.bid)/2)*100
    action_price=x.ask if action=="buy" else x.bid
    other=x.bid if action=="buy" else x.ask
    usable_size=x.ask_size if action=="buy" else x.bid_size
    reference_mid=(lower+upper)/2
    width=upper-lower
    lower_band=max(0,lower-PRICE_TOLERANCE_DOLLARS)
    upper_band=upper+PRICE_TOLERANCE_DOLLARS
    base={
        "contract":CONTRACT,"action":action,"option_right":right,
        "action_price":action_price,"opposite_side_price":other,
        "bid_size":x.bid_size,"ask_size":x.ask_size,
        "action_size_available":usable_size,"requested_contracts":x.contracts,
        "spread_pct":wide,"spread_over_original_15pct":wide>MAX_SPREAD_PCT,
        "bs_model_name":"EUROPEAN_EQUIVALENT_BLACK_SCHOLES_MERTON",
        "fair_value_band_before_tolerance":[lower,upper],
        "qualified_price_band_with_tolerance":[lower_band,upper_band],
        "model_width_relative_to_mid":width/max(reference_mid,0.01),
        "model_reference_mid":reference_mid,
        "quote_at":quote_at.isoformat(),"decision_at":now.isoformat(),
        "spot_source_id":x.spot_source_id,"volatility_source_id":x.iv_source_id,
        "rate_source_id":x.rate_source_id,"dividend_source_id":x.dividend_source_id,
        "acted_quote_source_id":x.acted_quote_source_id,
        "iv_derived_from_acted_quote":False,
        "quote_is_not_an_observed_fill":True,
        "black_scholes_not_american_option_price_or_guaranteed_fill":True,
        "historical_fills":0,"historical_alpha_validated":False,
    }
    def result(status,reason):
        return {**base,"status":status,"reason":reason}
    if usable_size<x.contracts:
        return result("REJECT_ACTION_SIDE_SIZE","DISPLAYED_ACTION_SIDE_SIZE_INSUFFICIENT")
    if width/max(reference_mid,0.01)>MAX_MODEL_BAND_RELATIVE_WIDTH:
        return result("ABSTAIN_MODEL_UNCERTAIN","FAIR_VALUE_INTERVAL_TOO_WIDE_TO_DIAGNOSE_SIDE")
    if action=="buy":
        if action_price>upper_band:
            return result("REJECT_ACTION_SIDE_DEVIATION","BUY_ASK_ABOVE_INDEPENDENT_FAIR_RANGE")
        if action_price<lower_band:
            return result("ABSTAIN_TOO_FAVORABLE_TO_VERIFY","BUY_ASK_IMPLAUSIBLY_BELOW_FAIR_RANGE")
        far_side_abnormal=other<lower_band
    else:
        if action_price<lower_band:
            return result("REJECT_ACTION_SIDE_DEVIATION","SELL_BID_BELOW_INDEPENDENT_FAIR_RANGE")
        if action_price>upper_band:
            return result("ABSTAIN_TOO_FAVORABLE_TO_VERIFY","SELL_BID_IMPLAUSIBLY_ABOVE_FAIR_RANGE")
        far_side_abnormal=other>upper_band
    if wide>MAX_SPREAD_PCT and not far_side_abnormal:
        return result("ABSTAIN_WIDE_SPREAD_NOT_ATTRIBUTABLE",
                      "BOTH_SIDES_OR_MODEL_NOT_SEPARABLE")
    return result("ACTION_SIDE_MODEL_CONSISTENT",
                  "ACTED_SIDE_NEAR_INDEPENDENT_FAIR_VALUE_OTHERSIDE_SUSPECT"
                  if far_side_abnormal else
                  "NORMAL_SPREAD_AND_ACTED_SIDE_MODEL_CONSISTENT")
