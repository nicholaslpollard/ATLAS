from __future__ import annotations

import hashlib
import json

from .phase18_policy import PHASE18_POLICY_CONTRACT_VERSION, phase18_policy_fingerprint


PHASE19_POLICY_CONTRACT_VERSION = (
    "phase19-policy-v1-phase18-stacked-readonly-operations-observability-no-provider-writes"
)
PHASE19_STACKED_UPSTREAM_PHASE = "phase18-paper-provider-mutation-lifecycle-validation"
PHASE19_PROVIDER_READS_ALLOWED = False
PHASE19_PROVIDER_WRITES_ALLOWED = False
PHASE19_LIVE_EXECUTION_PROMOTION_ALLOWED = False
PHASE19_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED = False
PHASE19_BROWSER_EXECUTION_AUTHORITY_ALLOWED = False
PHASE19_CREDENTIAL_VALUES_EXPOSED = False
PHASE19_RAW_ACCOUNT_IDS_EXPOSED = False
PHASE19_LOCAL_ARTIFACT_READS_ALLOWED = True
PHASE19_MISSING_ARTIFACTS_FAIL_DISPLAY_ONLY = True
PHASE19_STACKED_MERGE_BLOCKED_UNTIL_PHASE18_MERGED = True


def phase19_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE19_POLICY_CONTRACT_VERSION,
        "stacked_upstream": {
            "phase": PHASE19_STACKED_UPSTREAM_PHASE,
            "phase18_policy_contract_version": PHASE18_POLICY_CONTRACT_VERSION,
            "phase18_policy_fingerprint": phase18_policy_fingerprint(),
            "merge_blocked_until_phase18_merged": PHASE19_STACKED_MERGE_BLOCKED_UNTIL_PHASE18_MERGED,
        },
        "observability": {
            "local_artifact_reads_allowed": PHASE19_LOCAL_ARTIFACT_READS_ALLOWED,
            "provider_reads_allowed": PHASE19_PROVIDER_READS_ALLOWED,
            "provider_writes_allowed": PHASE19_PROVIDER_WRITES_ALLOWED,
            "missing_artifacts_fail_display_only": PHASE19_MISSING_ARTIFACTS_FAIL_DISPLAY_ONLY,
        },
        "authority": {
            "live_execution_promotion_allowed": PHASE19_LIVE_EXECUTION_PROMOTION_ALLOWED,
            "automatic_cross_broker_failover_allowed": PHASE19_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
            "browser_execution_authority_allowed": PHASE19_BROWSER_EXECUTION_AUTHORITY_ALLOWED,
            "credential_values_exposed": PHASE19_CREDENTIAL_VALUES_EXPOSED,
            "raw_account_ids_exposed": PHASE19_RAW_ACCOUNT_IDS_EXPOSED,
        },
    }


def phase19_policy_fingerprint() -> str:
    raw = json.dumps(
        phase19_policy_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_phase19_policy() -> None:
    assert PHASE19_PROVIDER_READS_ALLOWED is False
    assert PHASE19_PROVIDER_WRITES_ALLOWED is False
    assert PHASE19_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE19_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False
    assert PHASE19_BROWSER_EXECUTION_AUTHORITY_ALLOWED is False
    assert PHASE19_CREDENTIAL_VALUES_EXPOSED is False
    assert PHASE19_RAW_ACCOUNT_IDS_EXPOSED is False
    assert PHASE19_LOCAL_ARTIFACT_READS_ALLOWED is True
    assert PHASE19_MISSING_ARTIFACTS_FAIL_DISPLAY_ONLY is True
    assert PHASE19_STACKED_MERGE_BLOCKED_UNTIL_PHASE18_MERGED is True
