from __future__ import annotations

import hashlib
import json


PHASE13_POLICY_CONTRACT_VERSION = (
    "phase13-policy-v1-context-equity-primary-evidence-bounded-geometry-broker-neutral-risk"
)

# Phase 13 is a deterministic planning/admission layer. None of these values are
# executable broker instructions and none may be tuned after viewing Phase 13 cases.
PHASE13_HORIZON_SESSIONS = 3

# Context is strictly supplemental. Provider sentiment never manufactures or promotes
# a candidate and does not receive veto authority in v1.
PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS = 7
PHASE13_NEWS_MAX_ARTICLES = 50
PHASE13_NEWS_CONTEXT_ONLY = True

# Equity is the only primary instrument in v1. Options can be collected/ranked for
# finalists but cannot become the selected primary instrument until a separately
# accepted relative-value model exists.
PHASE13_PRIMARY_INSTRUMENT = "EQUITY"
PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED = False
PHASE13_OPTION_MIN_DTE = 14
PHASE13_OPTION_MAX_DTE = 45
PHASE13_OPTION_MIN_ABS_DELTA = 0.35
PHASE13_OPTION_MAX_ABS_DELTA = 0.65
PHASE13_OPTION_MIN_OPEN_INTEREST = 100
PHASE13_OPTION_MAX_SPREAD_TO_MID = 0.15
PHASE13_OPTION_TARGET_ABS_DELTA = 0.50
PHASE13_OPTION_TARGET_DTE = 30
PHASE13_OPTION_MAX_ALTERNATIVES = 5

# Geometry uses the current canonical close as a reference entry, not as an assumed
# fill. Risk distance is the larger of current NATR and empirical p10 adverse-path
# magnitude. Reward distance is empirical p75 favorable-path magnitude. Geometry is
# available only when both are finite/positive and empirical reward exceeds risk.
PHASE13_GEOMETRY_ENTRY_SOURCE = "ACCEPTED_CURRENT_CANONICAL_1D_CLOSE_REFERENCE_ONLY"
PHASE13_GEOMETRY_RISK_RULE = "MAX_NATR14_AND_ABS_EMPIRICAL_MAE_P10"
PHASE13_GEOMETRY_REWARD_RULE = "EMPIRICAL_MFE_P75"
PHASE13_GEOMETRY_REQUIRES_REWARD_GT_RISK = True

# Portfolio risk is broker-neutral and evaluated from an explicit snapshot supplied to
# the planning layer. Missing portfolio evidence means UNAVAILABLE, never guessed.
PHASE13_RISK_PER_TRADE_FRACTION = 0.005
PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION = 0.10
PHASE13_MAX_GROSS_NOTIONAL_FRACTION = 1.00
PHASE13_MAX_OPEN_POSITIONS = 10
PHASE13_MAX_ABS_CORRELATION = 0.80
PHASE13_CORRELATION_LOOKBACK_SESSIONS = 60
PHASE13_CORRELATION_MIN_OVERLAP_SESSIONS = 20
PHASE13_SECTOR_CONCENTRATION_POLICY = "UNAVAILABLE_NO_AUTHORITATIVE_TICKER_TO_SECTOR_MAPPING"

PHASE13_PRODUCTION_ML_WRITES = 0
PHASE13_BROKER_WRITES = 0
PHASE13_ORDER_WRITES = 0


def phase13_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE13_POLICY_CONTRACT_VERSION,
        "horizon_sessions": PHASE13_HORIZON_SESSIONS,
        "news": {
            "lookback_calendar_days": PHASE13_NEWS_LOOKBACK_CALENDAR_DAYS,
            "max_articles": PHASE13_NEWS_MAX_ARTICLES,
            "context_only": PHASE13_NEWS_CONTEXT_ONLY,
        },
        "instrument": {
            "primary_instrument": PHASE13_PRIMARY_INSTRUMENT,
            "option_relative_value_model_accepted": PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED,
            "option_min_dte": PHASE13_OPTION_MIN_DTE,
            "option_max_dte": PHASE13_OPTION_MAX_DTE,
            "option_min_abs_delta": PHASE13_OPTION_MIN_ABS_DELTA,
            "option_max_abs_delta": PHASE13_OPTION_MAX_ABS_DELTA,
            "option_min_open_interest": PHASE13_OPTION_MIN_OPEN_INTEREST,
            "option_max_spread_to_mid": PHASE13_OPTION_MAX_SPREAD_TO_MID,
            "option_target_abs_delta": PHASE13_OPTION_TARGET_ABS_DELTA,
            "option_target_dte": PHASE13_OPTION_TARGET_DTE,
            "option_max_alternatives": PHASE13_OPTION_MAX_ALTERNATIVES,
        },
        "geometry": {
            "entry_source": PHASE13_GEOMETRY_ENTRY_SOURCE,
            "risk_rule": PHASE13_GEOMETRY_RISK_RULE,
            "reward_rule": PHASE13_GEOMETRY_REWARD_RULE,
            "requires_reward_gt_risk": PHASE13_GEOMETRY_REQUIRES_REWARD_GT_RISK,
        },
        "portfolio_risk": {
            "risk_per_trade_fraction": PHASE13_RISK_PER_TRADE_FRACTION,
            "max_single_name_notional_fraction": PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION,
            "max_gross_notional_fraction": PHASE13_MAX_GROSS_NOTIONAL_FRACTION,
            "max_open_positions": PHASE13_MAX_OPEN_POSITIONS,
            "max_abs_correlation": PHASE13_MAX_ABS_CORRELATION,
            "correlation_lookback_sessions": PHASE13_CORRELATION_LOOKBACK_SESSIONS,
            "correlation_min_overlap_sessions": PHASE13_CORRELATION_MIN_OVERLAP_SESSIONS,
            "sector_concentration_policy": PHASE13_SECTOR_CONCENTRATION_POLICY,
        },
        "authority": {
            "production_ml_writes": PHASE13_PRODUCTION_ML_WRITES,
            "broker_writes": PHASE13_BROKER_WRITES,
            "order_writes": PHASE13_ORDER_WRITES,
        },
    }


def phase13_policy_fingerprint() -> str:
    raw = json.dumps(phase13_policy_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
