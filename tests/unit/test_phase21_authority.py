from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from packages.brokers.paper.broker import ShadowBroker
from packages.execution.engine import ExecutionEngine, ExecutionEngineError
from packages.execution.phase21_authority import (
    PHASE21_AUTOMATIC_BROKER_FAILOVER,
    PHASE21_LIVE_EXECUTION_ENABLED,
    PHASE21_PAPER_PROVIDER_SUBMIT_ENABLED_BY_DEFAULT,
    Phase21PaperExecutionAuthority,
    authorize_phase21_paper_execution,
    build_phase15_paper_execution_challenge,
    phase21_policy_fingerprint,
)
from packages.execution.validator import ExecutionValidationError
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.execution import BrokerName, ExecutionEnvironment, ExecutionIntent


NOW = datetime(2026, 8, 24, 20, 0, 0, tzinfo=UTC)
INPUT_FP = "a" * 64
PHASE15_POLICY_FP = "b" * 64


class CountingPaperBroker(ShadowBroker):
    environment = ExecutionEnvironment.PAPER

    def __init__(self, broker: BrokerName) -> None:
        self.broker = broker
        self.submit_calls = 0
        super().__init__(account_id=f"test-{broker.value}")

    def submit(self, plan):
        self.submit_calls += 1
        return super().submit(plan)


class CountingLiveBroker(CountingPaperBroker):
    environment = ExecutionEnvironment.LIVE


def _intent(
    broker: BrokerName,
    *,
    environment: ExecutionEnvironment = ExecutionEnvironment.PAPER,
) -> ExecutionIntent:
    return ExecutionIntent(
        intent_id=f"phase21-intent-{broker.value}-0001",
        instrument_id="figi-phase21",
        ticker="XYZ",
        as_of_date=date(2026, 8, 24),
        direction=DiscoveryDirection.BULLISH,
        environment=environment,
        broker=broker,
        phase13_case_sha256="c" * 64,
        phase14_acceptance_sha256="d" * 64,
        reference_entry=100.0,
        entry_limit=100.0,
        stop=95.0,
        target=110.0,
        original_risk_per_share=5.0,
        executable_risk_per_share=5.0,
        executable_reward_per_share=10.0,
        adverse_entry_drift_r=0.0,
        executable_reward_to_risk=2.0,
        accepted_risk_budget=500.0,
        accepted_proposed_quantity=10,
        executable_quantity=10,
        quote_bid=99.95,
        quote_ask=100.0,
        quote_provider_timestamp_utc=NOW,
        quote_received_at_utc=NOW,
        quote_feed_mode="REALTIME",
        quote_expected_delay_seconds=0,
        quote_age_seconds=0.0,
        session_segment="REGULAR",
        order_type="LIMIT",
        time_in_force="DAY",
        extended_hours=False,
        protective_stop_required=True,
        profit_target_required=True,
        broker_preflight_required=True,
        reconciliation_required=True,
        live_execution_enabled=environment == ExecutionEnvironment.LIVE,
        reason_codes=("PHASE21_TEST_INTENT",),
    )


def _challenge(broker: BrokerName):
    return build_phase15_paper_execution_challenge(
        as_of_date=NOW.date(),
        phase15_input_fingerprint=INPUT_FP,
        phase15_policy_fingerprint=PHASE15_POLICY_FP,
        broker=broker,
    )


def _authority(
    broker: BrokerName,
    *,
    explicitly_authorized: bool = True,
) -> tuple[str, Phase21PaperExecutionAuthority]:
    challenge = _challenge(broker)
    authority = authorize_phase21_paper_execution(
        challenge,
        explicitly_authorized=explicitly_authorized,
        confirmation=challenge.required_confirmation,
    )
    return challenge.execution_scope_id, authority


def test_phase21_policy_is_default_deny_and_keeps_live_and_failover_disabled() -> None:
    assert PHASE21_PAPER_PROVIDER_SUBMIT_ENABLED_BY_DEFAULT is False
    assert PHASE21_LIVE_EXECUTION_ENABLED is False
    assert PHASE21_AUTOMATIC_BROKER_FAILOVER is False
    assert len(phase21_policy_fingerprint()) == 64
    assert phase21_policy_fingerprint() == phase21_policy_fingerprint()


def test_phase21_scope_is_deterministic_and_broker_bound() -> None:
    webull_first = _challenge(BrokerName.WEBULL)
    webull_second = _challenge(BrokerName.WEBULL)
    alpaca = _challenge(BrokerName.ALPACA)
    assert webull_first.execution_scope_id == webull_second.execution_scope_id
    assert webull_first.execution_scope_id != alpaca.execution_scope_id
    assert webull_first.required_confirmation != alpaca.required_confirmation


@pytest.mark.parametrize("broker", [BrokerName.WEBULL, BrokerName.ALPACA])
def test_exact_authorized_paper_submission_occurs_once(broker: BrokerName) -> None:
    adapter = CountingPaperBroker(broker)
    intent = _intent(broker)
    scope, authority = _authority(broker)
    result = ExecutionEngine().attempt(
        intent,
        adapter,
        now_utc=NOW,
        execution_scope_id=scope,
        paper_authority=authority,
    )
    assert adapter.submit_calls == 1
    assert result.provider_submission_performed is True
    assert result.broker_write_count == 1


def test_missing_authority_fails_before_submit() -> None:
    adapter = CountingPaperBroker(BrokerName.WEBULL)
    with pytest.raises(ExecutionEngineError) as excinfo:
        ExecutionEngine().attempt(
            _intent(BrokerName.WEBULL),
            adapter,
            now_utc=NOW,
            execution_scope_id=_challenge(BrokerName.WEBULL).execution_scope_id,
        )
    assert excinfo.value.stage == "paper_authority"
    assert excinfo.value.provider_submission_attempted is False
    assert adapter.submit_calls == 0


def test_explicit_false_authority_fails_before_submit() -> None:
    adapter = CountingPaperBroker(BrokerName.WEBULL)
    scope, authority = _authority(BrokerName.WEBULL, explicitly_authorized=False)
    with pytest.raises(ExecutionEngineError) as excinfo:
        ExecutionEngine().attempt(
            _intent(BrokerName.WEBULL),
            adapter,
            now_utc=NOW,
            execution_scope_id=scope,
            paper_authority=authority,
        )
    assert excinfo.value.stage == "paper_authority"
    assert adapter.submit_calls == 0


@pytest.mark.parametrize(
    "mutator",
    [
        lambda authority: replace(authority, broker=BrokerName.ALPACA),
        lambda authority: replace(authority, environment=ExecutionEnvironment.SHADOW),
        lambda authority: replace(authority, execution_scope_id="p21-" + "f" * 32),
        lambda authority: replace(authority, confirmation="WRONG_CONFIRMATION"),
        lambda authority: replace(authority, policy_fingerprint="0" * 64),
        lambda authority: replace(authority, contract_version="wrong-contract"),
        lambda authority: replace(authority, operation="CANCEL"),
    ],
)
def test_malformed_or_mismatched_authority_fails_before_submit(mutator) -> None:
    adapter = CountingPaperBroker(BrokerName.WEBULL)
    scope, authority = _authority(BrokerName.WEBULL)
    bad = mutator(authority)
    with pytest.raises(ExecutionEngineError) as excinfo:
        ExecutionEngine().attempt(
            _intent(BrokerName.WEBULL),
            adapter,
            now_utc=NOW,
            execution_scope_id=scope,
            paper_authority=bad,
        )
    assert excinfo.value.stage == "paper_authority"
    assert adapter.submit_calls == 0


def test_existing_idempotent_order_needs_no_second_mutation_authority() -> None:
    adapter = CountingPaperBroker(BrokerName.WEBULL)
    intent = _intent(BrokerName.WEBULL)
    scope, authority = _authority(BrokerName.WEBULL)
    first = ExecutionEngine().attempt(
        intent,
        adapter,
        now_utc=NOW,
        execution_scope_id=scope,
        paper_authority=authority,
    )
    assert first.existing_order_reused is False
    assert adapter.submit_calls == 1

    second = ExecutionEngine().attempt(
        intent,
        adapter,
        now_utc=NOW,
        execution_scope_id=None,
        paper_authority=None,
    )
    assert second.existing_order_reused is True
    assert second.provider_submission_performed is False
    assert adapter.submit_calls == 1


def test_shadow_execution_remains_authority_free() -> None:
    adapter = ShadowBroker()
    intent = _intent(BrokerName.SHADOW, environment=ExecutionEnvironment.SHADOW)
    result = ExecutionEngine().attempt(intent, adapter, now_utc=NOW)
    assert result.provider_submission_performed is False
    assert result.broker_write_count == 0


def test_live_execution_remains_blocked() -> None:
    adapter = CountingLiveBroker(BrokerName.WEBULL)
    intent = _intent(BrokerName.WEBULL, environment=ExecutionEnvironment.LIVE)
    with pytest.raises(ExecutionValidationError):
        ExecutionEngine().attempt(intent, adapter, now_utc=NOW)
    assert adapter.submit_calls == 0


def test_public_authority_metadata_omits_confirmation_text() -> None:
    _, authority = _authority(BrokerName.WEBULL)
    public = authority.public_dict()
    assert public["explicitly_authorized"] is True
    assert public["confirmation_validated"] is True
    assert "confirmation" not in public
    assert "AUTHORIZE_ATLAS_PAPER_SUBMIT" not in repr(public)
