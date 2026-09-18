from __future__ import annotations

import hashlib
import json


CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT = {
    "contract_id": "atlas-simulation-current-market-snapshot-source-v1",
    "scope": "PRODUCT_SIMULATION_IMMUTABLE_PROVISIONAL_LIVE_MARKET_SNAPSHOT_SOURCE",
    "source_schema": "LiveStateSnapshot",
    "source_current_path_required": True,
    "source_raw_sha256_required": True,
    "source_semantic_fingerprint_required": True,
    "archive_content_addressed_by_raw_sha256": True,
    "archive_exact_bytes_required": True,
    "archive_atomic_fsync_required": True,
    "archive_reuse_requires_exact_bytes": True,
    "snapshot_schema_validation_required": True,
    "feed_mode_preserved": True,
    "connection_state_preserved": True,
    "session_state_preserved": True,
    "freshness_state_preserved": True,
    "no_freshness_reclassification": True,
    "no_quote_or_bar_synthesis": True,
    "no_strategy_decision_authority": True,
    "provider_acquisition_outside_source": True,
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
        CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_FINGERPRINT = contract_fingerprint()
