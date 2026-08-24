from __future__ import annotations

import hashlib
import json

from packages.control_plane.phase19_policy import (
    PHASE19_POLICY_CONTRACT_VERSION,
    phase19_policy_fingerprint,
)


PHASE20_POLICY_CONTRACT_VERSION = (
    "phase20-policy-v1-phase19-stabilized-deterministic-run-orchestration-shadow-no-provider-calls"
)
PHASE20_ACCEPTED_BASELINE_MERGE = "121503590d3c0b18fa9cc19e4c8210b04e2f8d47"
PHASE20_LOCAL_ARTIFACT_READS_ALLOWED = True
PHASE20_LOCAL_STATE_WRITES_ALLOWED = True
PHASE20_PROVIDER_READS_ALLOWED = False
PHASE20_PROVIDER_WRITES_ALLOWED = False
PHASE20_BROKER_WRITES_ALLOWED = False
PHASE20_LIVE_EXECUTION_PROMOTION_ALLOWED = False
PHASE20_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED = False
PHASE20_AUTOMATIC_BROKER_SWITCHING_ALLOWED = False
PHASE20_AI_EXECUTION_AUTHORITY_ALLOWED = False
PHASE20_SHADOW_REHEARSAL_ALLOWED = True
PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED = False
PHASE20_BLIND_RETRY_OF_EXTERNAL_MUTATION_ALLOWED = False
PHASE20_SCHEDULER_DAEMON_AUTHORITY_ALLOWED = False
PHASE20_POSTGRES_OPERATIONAL_STATE_REQUIRED = False
PHASE20_UNKNOWN_STATE_FAILS_CLOSED = True


def phase20_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE20_POLICY_CONTRACT_VERSION,
        "accepted_baseline": {
            "merge": PHASE20_ACCEPTED_BASELINE_MERGE,
            "phase19_policy_contract_version": PHASE19_POLICY_CONTRACT_VERSION,
            "phase19_policy_fingerprint": phase19_policy_fingerprint(),
        },
        "local_orchestration": {
            "local_artifact_reads_allowed": PHASE20_LOCAL_ARTIFACT_READS_ALLOWED,
            "local_state_writes_allowed": PHASE20_LOCAL_STATE_WRITES_ALLOWED,
            "shadow_rehearsal_allowed": PHASE20_SHADOW_REHEARSAL_ALLOWED,
            "unknown_state_fails_closed": PHASE20_UNKNOWN_STATE_FAILS_CLOSED,
            "scheduler_daemon_authority_allowed": PHASE20_SCHEDULER_DAEMON_AUTHORITY_ALLOWED,
            "postgres_operational_state_required": PHASE20_POSTGRES_OPERATIONAL_STATE_REQUIRED,
        },
        "provider_broker_authority": {
            "provider_reads_allowed": PHASE20_PROVIDER_READS_ALLOWED,
            "provider_writes_allowed": PHASE20_PROVIDER_WRITES_ALLOWED,
            "broker_writes_allowed": PHASE20_BROKER_WRITES_ALLOWED,
            "external_mutation_stage_registration_allowed": (
                PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED
            ),
            "blind_retry_of_external_mutation_allowed": (
                PHASE20_BLIND_RETRY_OF_EXTERNAL_MUTATION_ALLOWED
            ),
        },
        "execution_authority": {
            "live_execution_promotion_allowed": PHASE20_LIVE_EXECUTION_PROMOTION_ALLOWED,
            "automatic_cross_broker_failover_allowed": (
                PHASE20_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED
            ),
            "automatic_broker_switching_allowed": PHASE20_AUTOMATIC_BROKER_SWITCHING_ALLOWED,
            "ai_execution_authority_allowed": PHASE20_AI_EXECUTION_AUTHORITY_ALLOWED,
        },
    }


def phase20_policy_fingerprint() -> str:
    raw = json.dumps(
        phase20_policy_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_phase20_policy() -> None:
    assert PHASE20_ACCEPTED_BASELINE_MERGE
    assert PHASE20_LOCAL_ARTIFACT_READS_ALLOWED is True
    assert PHASE20_LOCAL_STATE_WRITES_ALLOWED is True
    assert PHASE20_PROVIDER_READS_ALLOWED is False
    assert PHASE20_PROVIDER_WRITES_ALLOWED is False
    assert PHASE20_BROKER_WRITES_ALLOWED is False
    assert PHASE20_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE20_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False
    assert PHASE20_AUTOMATIC_BROKER_SWITCHING_ALLOWED is False
    assert PHASE20_AI_EXECUTION_AUTHORITY_ALLOWED is False
    assert PHASE20_SHADOW_REHEARSAL_ALLOWED is True
    assert PHASE20_EXTERNAL_MUTATION_STAGE_REGISTRATION_ALLOWED is False
    assert PHASE20_BLIND_RETRY_OF_EXTERNAL_MUTATION_ALLOWED is False
    assert PHASE20_SCHEDULER_DAEMON_AUTHORITY_ALLOWED is False
    assert PHASE20_POSTGRES_OPERATIONAL_STATE_REQUIRED is False
    assert PHASE20_UNKNOWN_STATE_FAILS_CLOSED is True
