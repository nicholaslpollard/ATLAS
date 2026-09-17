from __future__ import annotations

import hashlib
import json


MARKET_MARK_EVIDENCE_CONTRACT = {
    "contract_id": "atlas-simulation-market-mark-evidence-v1",
    "scope": "PRODUCT_SIMULATION_SOURCE_BOUND_MARK_EVIDENCE_ONLY",
    "inputs": ["atlas-simulation-open-position-account-state-v1"],
    "exact_open_position_fingerprint_required": True,
    "source_id_and_sha256_required": True,
    "provider_feed_transport_provenance_required": True,
    "market_receive_valuation_timestamps_required": True,
    "timestamp_order": "market_timestamp_utc<=received_utc<=valuation_utc",
    "freshness_basis": "valuation_utc_minus_market_timestamp_utc",
    "max_mark_age_seconds": 60.0,
    "stale_marks_preserved_but_not_valuation_eligible": True,
    "current_supported_positions": "LONG_STOCK_AND_LONG_OPTION_ONLY",
    "conservative_mark_side": "BID",
    "stock_bid_must_be_positive": True,
    "option_bid_may_be_zero": True,
    "ask_must_be_greater_than_or_equal_to_bid": True,
    "midpoint_not_used_as_valuation_truth": True,
    "last_not_used_as_valuation_truth": True,
    "no_position_value_calculation": True,
    "no_mark_to_market": True,
    "no_unrealized_pnl": True,
    "no_realized_pnl": True,
    "no_exit_closeout": True,
    "account_mutation_authority": False,
    "provider_read_authority": False,
    "provider_write_authority": False,
    "broker_read_authority": False,
    "broker_write_authority": False,
    "order_creation_authority": False,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        MARKET_MARK_EVIDENCE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT = contract_fingerprint()
MAX_MARK_AGE_SECONDS = float(MARKET_MARK_EVIDENCE_CONTRACT["max_mark_age_seconds"])
