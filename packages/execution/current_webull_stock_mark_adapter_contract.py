from __future__ import annotations

import hashlib
import json

from packages.execution.current_webull_quote_bundle_contract import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
)


CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT = {
    "contract_id": "atlas-simulation-current-webull-stock-mark-adapter-v1",
    "scope": "PRODUCT_SIMULATION_WEBULL_L1_BUNDLE_TO_STOCK_MARK_EVIDENCE",
    "source_contract_fingerprint": (
        CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ),
    "market_mark_contract_required": True,
    "exact_position_identity_required": True,
    "complete_position_quote_coverage_required": True,
    "exact_case_symbol_match_required": True,
    "stock_positions_only_v1": True,
    "provider_quote_age_cap_seconds": 30,
    "market_mark_age_policy_also_required": True,
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
        CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
