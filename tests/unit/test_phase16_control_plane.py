from __future__ import annotations

from packages.control_plane.phase16_policy import (
    PHASE16_ACCEPTED_PHASE15_MERGE_SHA,
    PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
    PHASE16_ALLOWED_EXECUTION_ENVIRONMENTS,
    PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY,
    PHASE16_CANCEL_OPEN_ORDERS_REQUIRES_EXPLICIT_CONFIRMATION,
    PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER,
    PHASE16_DEFAULT_BIND_HOST,
    PHASE16_FLATTEN_REQUIRES_SEPARATE_EXPLICIT_CONFIRMATION,
    PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE16_OPERATIONAL_ACTIONS_ARE_AUDITED,
    PHASE16_OPERATIONAL_ACTIONS_ARE_IDEMPOTENT,
    PHASE16_PHASE15_GATES_MAY_BE_BYPASSED,
    PHASE16_PRIMARY_BROKER,
    PHASE16_REMOTE_BIND_ENABLED_BY_DEFAULT,
    PHASE16_SECONDARY_BROKER,
    phase16_policy_fingerprint,
    phase16_policy_payload,
    validate_phase16_policy,
)


def test_phase16_policy_is_bound_to_accepted_phase15() -> None:
    validate_phase16_policy()
    assert PHASE16_ACCEPTED_PHASE15_MERGE_SHA == "7b2c50047f761653c7abb992cebc286577801453"
    assert PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT == (
        "a5227d764e8d32a88eefe42f1982a4da27853c0d2b35f584eeb455a2426480c5"
    )
    assert len(phase16_policy_fingerprint()) == 64


def test_phase16_browser_cannot_promote_or_bypass_execution_authority() -> None:
    assert PHASE16_ALLOWED_EXECUTION_ENVIRONMENTS == ("shadow", "paper")
    assert PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY is False
    assert PHASE16_PHASE15_GATES_MAY_BE_BYPASSED is False


def test_phase16_broker_switch_is_manual_and_flat_only() -> None:
    assert PHASE16_PRIMARY_BROKER == "webull"
    assert PHASE16_SECONDARY_BROKER == "alpaca"
    assert PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False
    assert PHASE16_FLATTEN_REQUIRES_SEPARATE_EXPLICIT_CONFIRMATION is True
    assert PHASE16_CANCEL_OPEN_ORDERS_REQUIRES_EXPLICIT_CONFIRMATION is True


def test_phase16_operations_are_local_audited_and_secret_safe_by_default() -> None:
    assert PHASE16_OPERATIONAL_ACTIONS_ARE_IDEMPOTENT is True
    assert PHASE16_OPERATIONAL_ACTIONS_ARE_AUDITED is True
    assert PHASE16_CREDENTIAL_VALUES_EXPOSED_TO_BROWSER is False
    assert PHASE16_DEFAULT_BIND_HOST == "127.0.0.1"
    assert PHASE16_REMOTE_BIND_ENABLED_BY_DEFAULT is False
    payload = phase16_policy_payload()
    assert payload["network"]["default_bind_host"] == "127.0.0.1"
    assert payload["operations"]["credential_values_exposed_to_browser"] is False
