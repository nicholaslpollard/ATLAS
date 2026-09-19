from __future__ import annotations

import hashlib
import json

from packages.execution.current_webull_quote_bundle_contract import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_time_expiry_disposition_contract import (
    RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT,
)


RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-price-time-exit-resolution-v1",
    "scope": (
        "PRODUCT_SIMULATION_PRICE_AND_TIME_TRIGGER_RESOLUTION_WITHOUT_FILL"
    ),
    "source_quote_bundle_contract_fingerprint": (
        CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ),
    "source_time_expiry_contract_fingerprint": (
        RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT
    ),
    "bullish_stock_long_only_v1": True,
    "exact_position_quote_coverage_required": True,
    "quote_regular_session_required": True,
    "quote_fresh_at_evaluation_required": True,
    "bid_used_for_price_trigger": True,
    "time_reason_requires_quote_received_at_or_after_deadline": True,
    "price_conditions": ["NO_PRICE_TRIGGER", "STOP", "TARGET"],
    "time_conditions": ["NOT_EXPIRED", "TIME_EXPIRED"],
    "selected_dispositions": ["HOLD", "STOP", "TARGET", "TIME"],
    "precedence_policy_required": True,
    "precedence_modes": ["PRICE_THEN_TIME", "TIME_THEN_PRICE"],
    "all_true_exit_reasons_retained": True,
    "fee_evidence_consumed": False,
    "close_fill_authority": False,
    "account_mutation_authority": False,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
    "provider_calls_performed": 0,
    "broker_calls_performed": 0,
    "provider_write_authority": False,
    "broker_write_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
