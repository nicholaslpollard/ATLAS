from __future__ import annotations

import hashlib
import json

from packages.simulation.recurrent_forecast_horizon_clock_book_contract import (
    RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT,
)


RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT = {
    "contract_id": (
        "atlas-simulation-recurrent-time-expiry-disposition-bundle-v1"
    ),
    "scope": (
        "PRODUCT_SIMULATION_DURABLE_CLOCK_BOOK_TO_TIME_EXPIRY_DISPOSITION"
    ),
    "source_clock_book_contract_fingerprint": (
        RECURRENT_FORECAST_HORIZON_CLOCK_BOOK_CONTRACT_FINGERPRINT
    ),
    "full_clock_book_retained": True,
    "explicit_evaluation_utc_required": True,
    "evaluation_not_before_clock_book_required": True,
    "exact_clock_disposition_coverage_required": True,
    "deadline_comparison": (
        "TIME_EXPIRED_WHEN_EVALUATION_GTE_DEADLINE"
    ),
    "dispositions": ["NOT_EXPIRED", "TIME_EXPIRED"],
    "signed_seconds_from_deadline_retained": True,
    "deterministic_order_required": True,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
    "price_evidence_consumed": False,
    "stop_target_precedence_authority": False,
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
        RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
