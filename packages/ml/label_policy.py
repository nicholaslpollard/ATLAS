from __future__ import annotations

import math


ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION = (
    "ml-prediction-label-policy-v1-3session-0.5natr-three-class-endpoint"
)

# Gate 4 production label, selected from the accepted Gate 3 feasibility evidence
# and the Gate 4 annual-stability comparison. The target remains strategy-neutral:
# it classifies only the exact 3-session endpoint move relative to volatility known
# at the observation timestamp.
ML_PREDICTION_LABEL_POLICY_ACCEPTED = True
ML_PREDICTION_LABEL_HORIZON_SESSIONS = 3
ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER = 0.5
ML_PREDICTION_LABEL_VOLATILITY_FEATURE = "natr_14"
ML_PREDICTION_LABEL_HORIZON_SCALING = "sqrt_sessions"
ML_PREDICTION_LABEL_CLASSES = ("DOWN", "NEUTRAL", "UP")
ML_PREDICTION_LABEL_PROBABILITY_FIELDS = ("p_down", "p_neutral", "p_up")
ML_PREDICTION_LABEL_NEUTRAL_RETAINED = True
ML_PREDICTION_LABEL_NATURAL_PREVALENCE_RETAINED = True
ML_PREDICTION_LABEL_RESAMPLING = "NONE_AT_LABEL_CONTRACT"

ML_PREDICTION_LABEL_EXACT_SESSION_CONTINUITY_REQUIRED = True
ML_PREDICTION_LABEL_EXACT_PROVIDER_TICKER_REQUIRED = True
ML_PREDICTION_LABEL_TICKER_TEXT_SPLICING_ALLOWED = False
ML_PREDICTION_LABEL_SPLIT_CROSSINGS_CENSORED = True
ML_PREDICTION_LABEL_ENDPOINT_ONLY = True
ML_PREDICTION_LABEL_PATH_BARRIER_USED = False
ML_PREDICTION_LABEL_ADJACENT_OVERLAP_SESSIONS = 2
ML_PREDICTION_LABEL_THRESHOLD_USES_OBSERVATION_VOLATILITY_ONLY = True

# Accepted 2026-08-14 target-machine evidence for the locked candidate.
ML_GATE4_ACCEPTED_USABLE_ROWS = 6_553_856
ML_GATE4_ACCEPTED_UP_ROWS = 1_466_456
ML_GATE4_ACCEPTED_DOWN_ROWS = 1_329_898
ML_GATE4_ACCEPTED_NEUTRAL_ROWS = 3_757_502
ML_GATE4_ANNUAL_DIRECTIONAL_RANGE_PCT = 2.66
ML_GATE4_ANNUAL_UP_GIVEN_DIRECTIONAL_RANGE_PCT = 7.05


def prediction_label_threshold(natr_14: float) -> float:
    """Return the locked symmetric absolute-return threshold for one observation."""

    value = float(natr_14)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("natr_14 must be finite and positive")
    return (
        value
        * math.sqrt(float(ML_PREDICTION_LABEL_HORIZON_SESSIONS))
        * ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER
    )


def classify_prediction_label(*, forward_return: float, natr_14: float) -> str:
    """Classify one exact 3-session endpoint return using observation-time NATR."""

    ret = float(forward_return)
    if not math.isfinite(ret):
        raise ValueError("forward_return must be finite")
    threshold = prediction_label_threshold(natr_14)
    if ret >= threshold:
        return "UP"
    if ret <= -threshold:
        return "DOWN"
    return "NEUTRAL"
