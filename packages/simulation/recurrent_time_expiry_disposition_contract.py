from __future__ import annotations

import hashlib
import json

from packages.simulation.recurrent_forecast_horizon_clock_contract import (
    RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
)


RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-time-expiry-disposition-v1",
    "scope": "PRODUCT_SIMULATION_DESCRIPTIVE_TIME_EXPIRY_DISPOSITION",
    "source_clock_contract_fingerprint": (
        RECURRENT_FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
    ),
    "explicit_evaluation_utc_required": True,
    "evaluation_timestamp_normalized_to_utc": True,
    "deadline_comparison": "TIME_EXPIRED_WHEN_EVALUATION_GTE_DEADLINE",
    "dispositions": ["NOT_EXPIRED", "TIME_EXPIRED"],
    "source_clock_retained": True,
    "signed_seconds_from_deadline_retained": True,
    "deterministic_fingerprint_required": True,
    "price_evidence_consumed": False,
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
        RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_TIME_EXPIRY_DISPOSITION_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
