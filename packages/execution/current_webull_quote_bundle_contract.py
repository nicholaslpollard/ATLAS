from __future__ import annotations

import hashlib
import json


CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT = {
    "contract_id": "atlas-execution-current-webull-stock-quote-bundle-v1",
    "scope": "PRODUCT_READONLY_EXECUTION_QUALITY_STOCK_L1_QUOTE_BUNDLE",
    "source": "webull_openapi_l1",
    "environment": "sandbox",
    "asset_class": "US_STOCK",
    "requested_symbols_explicit_required": True,
    "exact_case_symbol_identity_required": True,
    "requested_symbols_sorted_unique_required": True,
    "complete_requested_symbol_coverage_required": True,
    "one_provider_read_per_symbol_required": True,
    "realtime_feed_required": True,
    "zero_expected_delay_required": True,
    "regular_session_required": True,
    "positive_uncrossed_bid_ask_required": True,
    "provider_timestamp_required": True,
    "bounded_quote_age_required": True,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
    "partial_bundle_persistence_forbidden": True,
    "capture_attempt_invalidates_prior_current_artifact": True,
    "capture_provider_reads_allowed": True,
    "artifact_provider_read_authority": False,
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
        CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
