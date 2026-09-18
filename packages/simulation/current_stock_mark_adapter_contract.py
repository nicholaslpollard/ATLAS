from __future__ import annotations

import hashlib
import json

from packages.simulation.current_live_evidence_contract import (
    CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT,
)


CURRENT_STOCK_MARK_ADAPTER_CONTRACT = {
    "contract_id": "atlas-simulation-current-stock-mark-adapter-v1",
    "scope": "PRODUCT_SIMULATION_REALTIME_STOCK_QUOTE_TO_MARK_EVIDENCE",
    "source_contract_fingerprint": (
        CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT
    ),
    "market_mark_contract_required": True,
    "exact_position_identity_required": True,
    "realtime_feed_required": True,
    "zero_expected_delay_required": True,
    "subscribed_connection_required": True,
    "no_open_transport_gap_required": True,
    "fresh_quote_state_required": True,
    "exact_case_symbol_match_required": True,
    "complete_stock_position_coverage_required": True,
    "option_positions_unsupported_v1": True,
    "minute_bar_quote_fabrication_forbidden": True,
    "stale_mark_rejected": True,
    "provider_calls_performed": 0,
    "broker_calls_performed": 0,
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
        CURRENT_STOCK_MARK_ADAPTER_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT = contract_fingerprint()
