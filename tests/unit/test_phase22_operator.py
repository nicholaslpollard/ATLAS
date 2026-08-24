from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from packages.execution.phase21_authority import build_phase15_paper_execution_challenge
from packages.execution.phase22_operator import (
    PHASE22_ARBITRARY_CASE_INPUT_ALLOWED,
    PHASE22_AUTOMATIC_BROKER_FAILOVER,
    PHASE22_BROWSER_EXECUTION_ENABLED,
    PHASE22_DEFAULT_BROKER,
    PHASE22_LIVE_EXECUTION_ENABLED,
    PHASE22_SCHEDULER_EXECUTION_ENABLED,
    Phase22OperatorError,
    Phase22PaperOperator,
    phase22_policy_fingerprint,
)
from packages.schemas.execution import BrokerName, ExecutionEnvironment


AS_OF = date(2026, 8, 24)
INPUT_FP = "a" * 64
POLICY_FP = "b" * 64


@dataclass(frozen=True)
class FakeExecutionInput:
    as_of_date: date
    execution_case_count: int


class FakeInputResolver:
    def __init__(self, count: int) -> None:
        self.count = count
        self.resolve_calls = 0

    def resolve(self, as_of_date=None):
        self.resolve_calls += 1
        return FakeExecutionInput(as_of_date=as_of_date or AS_OF, execution_case_count=self.count)


class FakeRunEngine:
    def __init__(self, count: int) -> None:
        self.input_resolver = FakeInputResolver(count)
        self.run_calls = 0
        self.last_run_kwargs = None

    def prepare_paper_execution_challenge(self, *, as_of_date=None, broker):
        return build_phase15_paper_execution_challenge(
            as_of_date=as_of_date or AS_OF,
            phase15_input_fingerprint=INPUT_FP,
            phase15_policy_fingerprint=POLICY_FP,
            broker=broker,
        )

    def run(self, **kwargs):
        self.run_calls += 1
        self.last_run_kwargs = kwargs
        count = self.input_resolver.count
        return {
            "as_of_date": (kwargs.get("as_of_date") or AS_OF).isoformat(),
            "execution_case_count": count,
            "record_count": count,
            "blocked_count": 0,
            "paper_submitted_count": count,
            "existing_reconciled_count": 0,
            "provider_uncertain_count": 0,
            "provider_submission_attempts": count,
            "known_broker_writes": count,
            "known_order_writes": count,
            "unknown_write_record_count": 0,
            "requires_reconciliation": False,
            "pass": True,
            "manifest_path": "/tmp/phase15-manifest.json",
            "source_fingerprint": "c" * 64,
        }


def _operator(count: int) -> tuple[Phase22PaperOperator, FakeRunEngine]:
    engine = FakeRunEngine(count)
    return Phase22PaperOperator(object(), run_engine=engine), engine


def test_phase22_policy_keeps_operational_authority_narrow() -> None:
    assert PHASE22_DEFAULT_BROKER == BrokerName.WEBULL
    assert PHASE22_LIVE_EXECUTION_ENABLED is False
    assert PHASE22_AUTOMATIC_BROKER_FAILOVER is False
    assert PHASE22_BROWSER_EXECUTION_ENABLED is False
    assert PHASE22_SCHEDULER_EXECUTION_ENABLED is False
    assert PHASE22_ARBITRARY_CASE_INPUT_ALLOWED is False
    assert len(phase22_policy_fingerprint()) == 64
    assert phase22_policy_fingerprint() == phase22_policy_fingerprint()


def test_prepare_nonzero_case_is_provider_free_and_returns_exact_phase21_challenge() -> None:
    operator, engine = _operator(2)
    preparation = operator.prepare(broker=BrokerName.WEBULL)
    assert preparation.as_of_date == AS_OF
    assert preparation.execution_case_count == 2
    assert preparation.authority_required is True
    assert preparation.challenge is not None
    assert preparation.challenge.broker == BrokerName.WEBULL
    assert preparation.challenge.environment == ExecutionEnvironment.PAPER
    assert preparation.challenge.required_confirmation.startswith(
        "AUTHORIZE_ATLAS_PAPER_SUBMIT:webull:p21-"
    )
    assert engine.run_calls == 0


def test_prepare_zero_case_needs_no_authority() -> None:
    operator, engine = _operator(0)
    preparation = operator.prepare(broker=BrokerName.WEBULL)
    assert preparation.execution_case_count == 0
    assert preparation.authority_required is False
    assert preparation.challenge is None
    assert engine.run_calls == 0


def test_wrong_confirmation_fails_before_delegated_run() -> None:
    operator, engine = _operator(1)
    preparation = operator.prepare(broker=BrokerName.WEBULL)
    with pytest.raises(Phase22OperatorError, match="confirmation"):
        operator.execute(preparation, confirmation="WRONG")
    assert engine.run_calls == 0


@pytest.mark.parametrize("broker", [BrokerName.WEBULL, BrokerName.ALPACA])
def test_exact_confirmation_delegates_only_to_phase15_paper_run(broker: BrokerName) -> None:
    operator, engine = _operator(1)
    preparation = operator.prepare(broker=broker)
    assert preparation.challenge is not None
    result = operator.execute(
        preparation,
        confirmation=preparation.challenge.required_confirmation,
    )
    assert engine.run_calls == 1
    assert engine.last_run_kwargs["environment"] == ExecutionEnvironment.PAPER
    assert engine.last_run_kwargs["broker"] == broker
    authority = engine.last_run_kwargs["paper_authority"]
    assert authority is not None
    assert authority.broker == broker
    assert authority.execution_scope_id == preparation.challenge.execution_scope_id
    assert result.paper_submitted_count == 1
    assert result.provider_submission_attempts == 1


def test_zero_case_execution_delegates_without_mutation_authority() -> None:
    operator, engine = _operator(0)
    preparation = operator.prepare(broker=BrokerName.WEBULL)
    result = operator.execute(preparation)
    assert engine.run_calls == 1
    assert engine.last_run_kwargs["paper_authority"] is None
    assert result.execution_case_count == 0


def test_zero_case_rejects_unneeded_confirmation() -> None:
    operator, engine = _operator(0)
    preparation = operator.prepare(broker=BrokerName.WEBULL)
    with pytest.raises(Phase22OperatorError, match="zero-case"):
        operator.execute(preparation, confirmation="SHOULD_NOT_BE_ACCEPTED")
    assert engine.run_calls == 0


def test_provider_uncertainty_stops_without_retry_or_failover() -> None:
    operator, engine = _operator(1)
    preparation = operator.prepare(broker=BrokerName.WEBULL)
    assert preparation.challenge is not None

    def uncertain_run(**kwargs):
        engine.run_calls += 1
        return {
            "as_of_date": AS_OF.isoformat(),
            "execution_case_count": 1,
            "record_count": 1,
            "blocked_count": 0,
            "paper_submitted_count": 0,
            "existing_reconciled_count": 0,
            "provider_uncertain_count": 1,
            "provider_submission_attempts": 1,
            "known_broker_writes": 0,
            "known_order_writes": 0,
            "unknown_write_record_count": 1,
            "requires_reconciliation": True,
            "pass": False,
            "manifest_path": "/tmp/uncertain.json",
            "source_fingerprint": "d" * 64,
        }

    engine.run = uncertain_run
    with pytest.raises(Phase22OperatorError, match="uncertain"):
        operator.execute(
            preparation,
            confirmation=preparation.challenge.required_confirmation,
        )
    assert engine.run_calls == 1


def test_public_preparation_and_result_do_not_expose_confirmation() -> None:
    operator, engine = _operator(1)
    preparation = operator.prepare(broker=BrokerName.WEBULL)
    public_preparation = preparation.public_dict()
    assert "required_confirmation" not in repr(public_preparation)
    assert "AUTHORIZE_ATLAS_PAPER_SUBMIT" not in repr(public_preparation)

    assert preparation.challenge is not None
    result = operator.execute(
        preparation,
        confirmation=preparation.challenge.required_confirmation,
    )
    assert "confirmation" not in repr(result.public_dict()).lower()
