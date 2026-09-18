from __future__ import annotations

import hashlib
import json

from packages.execution.current_webull_quote_bundle_contract import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
)


CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT = {
    "contract_id": "atlas-simulation-current-webull-stock-fill-adapter-v1",
    "scope": "PRODUCT_SIMULATION_WEBULL_L1_TO_STOCK_ENTRY_AND_EXIT_EVIDENCE",
    "source_contract_fingerprint": (
        CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ),
    "entry_contract_required": True,
    "funding_contract_required": True,
    "exit_contract_required": True,
    "stock_positions_only_v1": True,
    "bullish_cash_funded_entry_only_v1": True,
    "entry_price_semantics": "ASK",
    "exit_price_semantics": "BID",
    "explicit_entry_fees_required": True,
    "explicit_exit_fees_required": True,
    "provider_quote_age_cap_seconds": 30,
    "exact_case_symbol_match_required": True,
    "quote_postdates_decision_or_position_required": True,
    "provider_calls_performed": 0,
    "broker_calls_performed": 0,
    "broker_fill_claimed": False,
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
        CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
