from __future__ import annotations

import hashlib
import json


PHASE17_POLICY_CONTRACT_VERSION = (
    "phase17-policy-v1-phase16-bound-provider-readonly-reconciliation-no-mutation"
)
PHASE17_ACCEPTED_PHASE16_MERGE_SHA = "b474a64bf05e149f14ad668e9c715b87b3354bd5"
PHASE17_ACCEPTED_PHASE16_FROZEN_HEAD_SHA = "2d739c4bc58acd9eae53443bc30e043436a09f13"
PHASE17_ACCEPTED_PHASE16_POLICY_FINGERPRINT = (
    "dbce22bdfd4ac6dfb1a476d3fd5d4717918ca2163f93c9245135892242020b55"
)
PHASE17_ACCEPTED_PHASE16_IMPLEMENTATION_FINGERPRINT = (
    "c4f762aa1e7ac923a0fb4d50d0bd66fc259d46e6e941255ca2f8b2cc96e383ba"
)
PHASE17_ACCEPTED_PHASE16_SOURCE_FINGERPRINT = (
    "dbb8ac63008616a5511d8005ad42caf20da4590b660904df3286bf2d3ffefbf0"
)

PHASE17_REQUIRED_BROKERS = ("webull", "alpaca")
PHASE17_PROVIDER_READS_ALLOWED = True
PHASE17_PROVIDER_MUTATIONS_ALLOWED = False
PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED = False
PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED = False
PHASE17_REQUIRE_BOTH_BROKERS_RECONCILED = True
PHASE17_REQUIRE_FLAT_BROKERS_FOR_READINESS = False
PHASE17_CREDENTIAL_VALUES_EXPOSED = False
PHASE17_ACCEPTED_PHASE16_ARTIFACTS_IMMUTABLE = True
PHASE17_READONLY_REPORT_MUST_BE_SEPARATE = True


def phase17_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE17_POLICY_CONTRACT_VERSION,
        "accepted_phase16": {
            "merge_sha": PHASE17_ACCEPTED_PHASE16_MERGE_SHA,
            "frozen_head_sha": PHASE17_ACCEPTED_PHASE16_FROZEN_HEAD_SHA,
            "policy_fingerprint": PHASE17_ACCEPTED_PHASE16_POLICY_FINGERPRINT,
            "implementation_fingerprint": PHASE17_ACCEPTED_PHASE16_IMPLEMENTATION_FINGERPRINT,
            "source_fingerprint": PHASE17_ACCEPTED_PHASE16_SOURCE_FINGERPRINT,
            "artifacts_immutable": PHASE17_ACCEPTED_PHASE16_ARTIFACTS_IMMUTABLE,
        },
        "provider_readiness": {
            "required_brokers": PHASE17_REQUIRED_BROKERS,
            "provider_reads_allowed": PHASE17_PROVIDER_READS_ALLOWED,
            "provider_mutations_allowed": PHASE17_PROVIDER_MUTATIONS_ALLOWED,
            "both_brokers_reconciled_required": PHASE17_REQUIRE_BOTH_BROKERS_RECONCILED,
            "flat_brokers_required_for_readiness": PHASE17_REQUIRE_FLAT_BROKERS_FOR_READINESS,
            "readonly_report_must_be_separate": PHASE17_READONLY_REPORT_MUST_BE_SEPARATE,
        },
        "authority": {
            "live_execution_promotion_allowed": PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED,
            "automatic_cross_broker_failover_allowed": PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
            "credential_values_exposed": PHASE17_CREDENTIAL_VALUES_EXPOSED,
        },
    }


def phase17_policy_fingerprint() -> str:
    raw = json.dumps(
        phase17_policy_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_phase17_policy() -> None:
    assert len(PHASE17_ACCEPTED_PHASE16_MERGE_SHA) == 40
    assert len(PHASE17_ACCEPTED_PHASE16_FROZEN_HEAD_SHA) == 40
    assert len(PHASE17_ACCEPTED_PHASE16_POLICY_FINGERPRINT) == 64
    assert len(PHASE17_ACCEPTED_PHASE16_IMPLEMENTATION_FINGERPRINT) == 64
    assert len(PHASE17_ACCEPTED_PHASE16_SOURCE_FINGERPRINT) == 64
    assert PHASE17_REQUIRED_BROKERS == ("webull", "alpaca")
    assert PHASE17_PROVIDER_READS_ALLOWED is True
    assert PHASE17_PROVIDER_MUTATIONS_ALLOWED is False
    assert PHASE17_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE17_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False
    assert PHASE17_REQUIRE_BOTH_BROKERS_RECONCILED is True
    assert PHASE17_REQUIRE_FLAT_BROKERS_FOR_READINESS is False
    assert PHASE17_CREDENTIAL_VALUES_EXPOSED is False
    assert PHASE17_ACCEPTED_PHASE16_ARTIFACTS_IMMUTABLE is True
    assert PHASE17_READONLY_REPORT_MUST_BE_SEPARATE is True
