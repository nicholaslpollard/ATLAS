from __future__ import annotations

import hashlib
import json


CURRENT_LIVE_EVIDENCE_CONTRACT = {
    "contract_id": "atlas-simulation-current-live-evidence-v1",
    "scope": "PRODUCT_SIMULATION_LOCAL_CURRENT_MARKET_ARTIFACT_ADAPTER",
    "source": "data/live/market_state/current.json",
    "source_raw_sha256_required": True,
    "source_size_bounded": True,
    "pydantic_live_state_validation_required": True,
    "snapshot_not_from_future_required": True,
    "exact_symbol_identity_required": True,
    "event_feed_mode_binding_required": True,
    "event_expected_delay_binding_required": True,
    "event_symbol_binding_required": True,
    "minute_to_quote_fabrication_forbidden": True,
    "network_provider_calls_performed": 0,
    "network_broker_calls_performed": 0,
    "descriptive_only": True,
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
        CURRENT_LIVE_EVIDENCE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT = contract_fingerprint()
