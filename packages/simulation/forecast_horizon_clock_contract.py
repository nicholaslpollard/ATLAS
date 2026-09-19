from __future__ import annotations

import hashlib
import json


FORECAST_HORIZON_CLOCK_CONTRACT = {
    "contract_id": "atlas-simulation-forecast-horizon-clock-v1",
    "scope": "PRODUCT_SIMULATION_FORECAST_HORIZON_TO_DETERMINISTIC_EXCHANGE_CLOCK",
    "source_exit_plan_contract_required": True,
    "official_exchange_calendar_required": True,
    "minutes_are_regular_session_elapsed_minutes": True,
    "closed_premarket_afterhours_weekend_holiday_minutes_count": False,
    "early_close_sessions_respected": True,
    "session_horizon_requires_explicit_counting_policy": True,
    "session_counting_policies": [
        "ENTRY_SESSION_INCLUDED",
        "FULL_SESSIONS_AFTER_ENTRY",
    ],
    "entry_session_included_semantics": (
        "horizon=1 expires at official close of entry session"
    ),
    "full_sessions_after_entry_semantics": (
        "horizon=1 expires at official close of first session after entry session"
    ),
    "minutes_horizon_rejects_session_counting_policy": True,
    "evaluation_must_not_predate_position_open": True,
    "expiry_is_deterministic_from_plan_and_calendar": True,
    "clock_expired_at_or_after_expiry_timestamp": True,
    "price_trigger_authority": False,
    "close_fill_authority": False,
    "provider_reads": 0,
    "provider_writes": 0,
    "broker_reads": 0,
    "broker_writes": 0,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        FORECAST_HORIZON_CLOCK_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT = contract_fingerprint()
