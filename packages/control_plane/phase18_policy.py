from __future__ import annotations

import hashlib
import json


PHASE18_POLICY_CONTRACT_VERSION = (
    "phase18-policy-v1-phase17-bound-explicit-paper-mutation-no-live"
)
PHASE18_ACCEPTED_PHASE17_MERGE_SHA = "65d5a7b58c6894eba27722465741c92db9a33aaf"
PHASE18_ACCEPTED_PHASE17_POLICY_FINGERPRINT = (
    "693113bbb09458ed2939e486f9f6e0a0bda44e331c6419065760586047b93ff8"
)
PHASE18_ACCEPTED_PHASE17_READINESS_CONTRACT = (
    "phase17-readiness-v1-phase16-artifact-preserving-dual-broker-readonly-reconciliation"
)

PHASE18_REQUIRED_BROKERS = ("webull", "alpaca")
PHASE18_PROVIDER_READS_ALLOWED = True
PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT = False
PHASE18_EXPLICIT_TARGET_MACHINE_AUTHORIZATION_REQUIRED = True
PHASE18_SINGLE_BROKER_PER_RUN_REQUIRED = True
PHASE18_PRE_RECONCILIATION_REQUIRED = True
PHASE18_POST_RECONCILIATION_REQUIRED = True
PHASE18_FRESH_QUOTE_REQUIRED = True
PHASE18_CURRENT_RISK_REVALIDATION_REQUIRED = True
PHASE18_PROTECTIVE_GEOMETRY_REQUIRED = True
PHASE18_DETERMINISTIC_CLIENT_ORDER_ID_REQUIRED = True
PHASE18_UNCERTAIN_WRITE_BLOCKS_FURTHER_MUTATION = True
PHASE18_DESTRUCTIVE_CLEANUP_REQUIRES_EXPLICIT_AUTHORIZATION = True
PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED = False
PHASE18_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED = False
PHASE18_CREDENTIAL_VALUES_EXPOSED = False

PHASE18_CONFIRMATION_TEXT = "AUTHORIZE_PAPER_PROVIDER_MUTATION"


def phase18_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE18_POLICY_CONTRACT_VERSION,
        "accepted_phase17": {
            "merge_sha": PHASE18_ACCEPTED_PHASE17_MERGE_SHA,
            "policy_fingerprint": PHASE18_ACCEPTED_PHASE17_POLICY_FINGERPRINT,
            "readiness_contract_version": PHASE18_ACCEPTED_PHASE17_READINESS_CONTRACT,
        },
        "paper_mutation": {
            "required_brokers": PHASE18_REQUIRED_BROKERS,
            "provider_reads_allowed": PHASE18_PROVIDER_READS_ALLOWED,
            "provider_mutations_allowed_by_default": PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT,
            "explicit_target_machine_authorization_required": PHASE18_EXPLICIT_TARGET_MACHINE_AUTHORIZATION_REQUIRED,
            "single_broker_per_run_required": PHASE18_SINGLE_BROKER_PER_RUN_REQUIRED,
            "pre_reconciliation_required": PHASE18_PRE_RECONCILIATION_REQUIRED,
            "post_reconciliation_required": PHASE18_POST_RECONCILIATION_REQUIRED,
            "fresh_quote_required": PHASE18_FRESH_QUOTE_REQUIRED,
            "current_risk_revalidation_required": PHASE18_CURRENT_RISK_REVALIDATION_REQUIRED,
            "protective_geometry_required": PHASE18_PROTECTIVE_GEOMETRY_REQUIRED,
            "deterministic_client_order_id_required": PHASE18_DETERMINISTIC_CLIENT_ORDER_ID_REQUIRED,
            "uncertain_write_blocks_further_mutation": PHASE18_UNCERTAIN_WRITE_BLOCKS_FURTHER_MUTATION,
            "destructive_cleanup_requires_explicit_authorization": PHASE18_DESTRUCTIVE_CLEANUP_REQUIRES_EXPLICIT_AUTHORIZATION,
        },
        "authority": {
            "live_execution_promotion_allowed": PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED,
            "automatic_cross_broker_failover_allowed": PHASE18_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
            "credential_values_exposed": PHASE18_CREDENTIAL_VALUES_EXPOSED,
        },
    }


def phase18_policy_fingerprint() -> str:
    raw = json.dumps(
        phase18_policy_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_phase18_policy() -> None:
    assert len(PHASE18_ACCEPTED_PHASE17_MERGE_SHA) == 40
    assert len(PHASE18_ACCEPTED_PHASE17_POLICY_FINGERPRINT) == 64
    assert PHASE18_REQUIRED_BROKERS == ("webull", "alpaca")
    assert PHASE18_PROVIDER_READS_ALLOWED is True
    assert PHASE18_PROVIDER_MUTATIONS_ALLOWED_BY_DEFAULT is False
    assert PHASE18_EXPLICIT_TARGET_MACHINE_AUTHORIZATION_REQUIRED is True
    assert PHASE18_SINGLE_BROKER_PER_RUN_REQUIRED is True
    assert PHASE18_PRE_RECONCILIATION_REQUIRED is True
    assert PHASE18_POST_RECONCILIATION_REQUIRED is True
    assert PHASE18_FRESH_QUOTE_REQUIRED is True
    assert PHASE18_CURRENT_RISK_REVALIDATION_REQUIRED is True
    assert PHASE18_PROTECTIVE_GEOMETRY_REQUIRED is True
    assert PHASE18_DETERMINISTIC_CLIENT_ORDER_ID_REQUIRED is True
    assert PHASE18_UNCERTAIN_WRITE_BLOCKS_FURTHER_MUTATION is True
    assert PHASE18_DESTRUCTIVE_CLEANUP_REQUIRES_EXPLICIT_AUTHORIZATION is True
    assert PHASE18_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE18_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False
    assert PHASE18_CREDENTIAL_VALUES_EXPOSED is False
    assert PHASE18_CONFIRMATION_TEXT == "AUTHORIZE_PAPER_PROVIDER_MUTATION"
