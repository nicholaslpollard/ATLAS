from __future__ import annotations

from datetime import UTC, datetime

from packages.brokers.base import (
    BrokerAdapter,
    BrokerAdapterError,
    BrokerOrderNotFound,
    BrokerSubmissionUncertain,
)
from packages.execution.order_builder import build_broker_order_plan
from packages.execution.phase21_authority import (
    Phase21AuthorizationError,
    Phase21PaperExecutionAuthority,
    require_phase21_paper_execution_authority,
)
from packages.execution.validator import (
    reconcile_broker,
    revalidate_execution_risk,
    validate_submission_gate,
)
from packages.schemas.execution import (
    BrokerPreflightResult,
    ExecutionEnvironment,
    ExecutionIntent,
)
from packages.schemas.execution_attempt import ExecutionAttemptRecord


class ExecutionEngineError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        provider_submission_attempted: bool = False,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.provider_submission_attempted = provider_submission_attempted


class ExecutionEngine:
    """Idempotent Phase 15 entry executor.

    The engine never chooses a broker. It receives one explicit intent and one matching
    adapter. Before any new submission it asks the broker for the deterministic client
    order id; only a definitive not-found response permits a new submit attempt. Every
    new PAPER provider submission additionally requires exact Phase 21 run-scoped
    authority. Reusing an already-existing deterministic order performs no new mutation
    and therefore does not consume or require new mutation authority.
    """

    def attempt(
        self,
        intent: ExecutionIntent,
        adapter: BrokerAdapter,
        *,
        max_abs_correlation: float | None = None,
        now_utc: datetime | None = None,
        execution_scope_id: str | None = None,
        paper_authority: Phase21PaperExecutionAuthority | None = None,
    ) -> ExecutionAttemptRecord:
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        plan = build_broker_order_plan(intent)
        reconciliation = reconcile_broker(adapter, now_utc=now)

        try:
            existing = adapter.order(plan.client_order_id)
        except BrokerOrderNotFound:
            existing = None
        except BrokerAdapterError as exc:
            raise ExecutionEngineError(
                "cannot prove deterministic client order id is absent; submission blocked",
                stage="idempotency_query",
            ) from exc

        if existing is not None:
            if existing.broker != intent.broker:
                raise ExecutionEngineError(
                    "existing idempotent order belongs to a different broker",
                    stage="idempotency_query",
                )
            risk_revalidation = revalidate_execution_risk(
                intent,
                reconciliation,
                new_submission=False,
                now_utc=now,
            )
            preflight = BrokerPreflightResult(
                broker=intent.broker,
                intent_id=intent.intent_id,
                accepted=True,
                as_of_utc=now,
                provider_code="IDEMPOTENT_EXISTING_ORDER",
                provider_message="Existing deterministic client order id reused; no new submission.",
                reason_codes=("EXISTING_CLIENT_ORDER_ID_REUSED", "NO_NEW_BROKER_WRITE"),
            )
            return ExecutionAttemptRecord(
                attempted_at_utc=now,
                intent=intent,
                order_plan=plan,
                reconciliation_before=reconciliation,
                risk_revalidation=risk_revalidation,
                preflight=preflight,
                order_snapshot=existing,
                existing_order_reused=True,
                provider_submission_performed=False,
                broker_write_count=0,
                order_write_count=0,
                live_submission_performed=False,
            )

        risk_revalidation = revalidate_execution_risk(
            intent,
            reconciliation,
            max_abs_correlation=max_abs_correlation,
            new_submission=True,
            now_utc=now,
        )
        if not risk_revalidation.admissible:
            raise ExecutionEngineError(
                "current broker risk envelope rejected new submission",
                stage="risk_revalidation",
            )
        try:
            preflight = adapter.preview(plan)
        except BrokerAdapterError as exc:
            raise ExecutionEngineError(
                "broker preflight failed closed",
                stage="preflight",
            ) from exc
        validate_submission_gate(
            intent,
            plan,
            adapter=adapter,
            reconciliation=reconciliation,
            risk_revalidation=risk_revalidation,
            preflight=preflight,
        )

        if intent.environment == ExecutionEnvironment.PAPER:
            try:
                require_phase21_paper_execution_authority(
                    paper_authority,
                    expected_execution_scope_id=execution_scope_id,
                    broker=adapter.broker,
                    environment=adapter.environment,
                )
            except Phase21AuthorizationError as exc:
                raise ExecutionEngineError(
                    "Phase 21 paper execution authority rejected new provider submission",
                    stage="paper_authority",
                ) from exc

        try:
            submitted = adapter.submit(plan)
        except BrokerSubmissionUncertain:
            raise
        except BrokerAdapterError as exc:
            raise ExecutionEngineError(
                "broker submission was definitively rejected/failed",
                stage="submit",
                provider_submission_attempted=True,
            ) from exc

        if submitted.client_order_id != plan.client_order_id:
            raise BrokerSubmissionUncertain(
                "provider acknowledgement changed deterministic client order id; reconcile before retry"
            )
        if submitted.broker != intent.broker:
            raise BrokerSubmissionUncertain(
                "provider acknowledgement changed explicit broker identity; reconcile before retry"
            )

        provider_submission = intent.environment == ExecutionEnvironment.PAPER
        return ExecutionAttemptRecord(
            attempted_at_utc=now,
            intent=intent,
            order_plan=plan,
            reconciliation_before=reconciliation,
            risk_revalidation=risk_revalidation,
            preflight=preflight,
            order_snapshot=submitted,
            existing_order_reused=False,
            provider_submission_performed=provider_submission,
            broker_write_count=1 if provider_submission else 0,
            order_write_count=1 if provider_submission else 0,
            live_submission_performed=False,
        )
