from __future__ import annotations

import hashlib
import json


RECURRENT_RUNTIME_STARTUP_CONTRACT = {
    "contract_id": "atlas-control-plane-recurrent-runtime-startup-v1",
    "scope": "PRODUCT_RUNTIME_RESTORE_AND_READONLY_PHASE19_BINDING",
    "runtime_contract": "atlas-simulation-persistent-recurrent-runtime-v1",
    "store_contract": "atlas-simulation-recurrent-runtime-store-v1",
    "dashboard_contract": (
        "track-a-recurrent-simulation-lifecycle-dashboard-v1-engine-owned-readonly"
    ),
    "configured_derived_store_path_required": True,
    "missing_store_returns_uninitialized_not_connected": True,
    "corrupt_store_fails_startup": True,
    "no_implicit_account_bootstrap": True,
    "no_implicit_starting_equity": True,
    "no_legacy_artifact_fallback": True,
    "restored_marks_are_absent_until_fresh_publication": True,
    "phase19_uses_explicit_recurrent_dashboard_service": True,
    "single_cycle_compatibility_code_retained": True,
    "provider_reads_on_restore": 0,
    "provider_writes_on_restore": 0,
    "broker_reads_on_restore": 0,
    "broker_writes_on_restore": 0,
    "order_writes_on_restore": 0,
    "paper_authority": False,
    "live_authority": False,
    "promotion_authority": False,
    "confluence_authority": False,
}


def contract_fingerprint() -> str:
    raw = json.dumps(
        RECURRENT_RUNTIME_STARTUP_CONTRACT,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


RECURRENT_RUNTIME_STARTUP_CONTRACT_FINGERPRINT = contract_fingerprint()
