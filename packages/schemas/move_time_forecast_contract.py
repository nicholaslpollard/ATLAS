from __future__ import annotations

import hashlib
import json


MOVE_TIME_FORECAST_CONTRACT = {
    "contract_id": "atlas-underlying-move-time-forecast-v1",
    "scope": "BROKER_NEUTRAL_PRODUCT_EVIDENCE",
    "forecast_target": "UNDERLYING_PRICE_PATH_BEFORE_INSTRUMENT_SELECTION",
    "availability_states": ["AVAILABLE", "UNAVAILABLE"],
    "horizon_units": ["MINUTES", "SESSIONS"],
    "directions": ["bullish", "bearish", "neutral"],
    "required_available_distribution_fields": [
        "reference_price",
        "mean_signed_return",
        "median_signed_return",
        "p10_signed_return",
        "p25_signed_return",
        "p75_signed_return",
        "p90_signed_return",
        "probability_positive_return",
        "mean_mfe",
        "mean_mae",
    ],
    "threshold_fields": [
        "threshold_fraction",
        "favorable_touch_probability",
        "adverse_touch_probability",
        "favorable_before_adverse_probability",
        "adverse_before_favorable_probability",
        "same_interval_collision_probability",
        "median_favorable_time",
    ],
    "threshold_probabilities_are_underlying_only": True,
    "historical_option_pnl_claimed": False,
    "instrument_selection_authority": False,
    "broker_reads": 0,
    "broker_writes": 0,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
}


def contract_payload() -> dict[str, object]:
    return json.loads(json.dumps(MOVE_TIME_FORECAST_CONTRACT))


def contract_fingerprint() -> str:
    raw = json.dumps(
        MOVE_TIME_FORECAST_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT = (
    "93525886fb2f0e8af3821caba8c87854ab1d732d5619dc02838df0ef98d931e1"
)
