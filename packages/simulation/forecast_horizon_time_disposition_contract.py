from __future__ import annotations

import hashlib
import json

from packages.simulation.forecast_horizon_clock_book_contract import (
    FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
)


FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT = {
    "contract_id": (
        "atlas-simulation-forecast-horizon-time-disposition-v1"
    ),
    "scope": (
        "PRODUCT_SIMULATION_EXPLICIT_UTC_FORECAST_HORIZON_TIME_DISPOSITION"
    ),
    "source_clock_book_contract_fingerprint": (
        FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
    ),
    "full_source_clock_book_retained": True,
    "explicit_evaluation_utc_required": True,
    "evaluation_must_not_precede_position_open": True,
    "time_expired_when_evaluation_at_or_after_deadline": True,
    "not_expired_when_evaluation_before_deadline": True,
    "deadline_equality_is_expired": True,
    "exact_clock_disposition_coverage_required": True,
    "deterministic_position_order_required": True,
    "bundle_self_fingerprint_required": True,
    "atomic_fsync_persistence_required": True,
    "price_trigger_authority": False,
    "close_precedence_authority": False,
    "close_fill_authority": False,
    "account_mutation_authority": False,
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
        FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
