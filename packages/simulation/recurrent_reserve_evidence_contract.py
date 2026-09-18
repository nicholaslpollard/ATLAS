from __future__ import annotations

import hashlib
import json


RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT = {
    "contract_id": "atlas-simulation-recurrent-reserve-evidence-bundle-v1",
    "scope": "PRODUCT_SIMULATION_DURABLE_RESERVE_STAGE_DECISION_EVIDENCE",
    "source_decision_contract_required": True,
    "cycle_identity_binding_required": True,
    "deterministic_decision_order_required": True,
    "duplicate_decision_fingerprint_forbidden": True,
    "future_decision_relative_to_bundle_forbidden": True,
    "abstention_preserved": True,
    "stock_selection_forbids_option_terms": True,
    "option_selection_requires_exact_option_terms": True,
    "option_terms_decision_fingerprint_binding_required": True,
    "option_terms_candidate_fingerprint_binding_required": True,
    "option_terms_forecast_fingerprint_binding_required": True,
    "typed_json_roundtrip_required": True,
    "atomic_fsync_persistence_required": True,
    "bundle_self_fingerprint_required": True,
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
        RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT = (
    contract_fingerprint()
)
