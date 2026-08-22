from __future__ import annotations

from datetime import UTC, datetime

from packages.brokers.base import (
    BrokerAdapter,
    BrokerAdapterError,
    BrokerOrderNotFound,
    BrokerSubmissionUncertain,
)
from packages.execution.order_builder import build_broker_order_plan
from packages.execution.validator import reconcile_broker, validate_submission_gate
from packages.schemas.execution import (
    BrokerPreflightResult,
    ExecutionEnvironment,
    ExecutionIntent,
)
from packages.schemas.execution_attempt import ExecutionAttemptRecord


class ExecutionEngineError(RuntimeError):
    pass


class ExecutionEngine:
    """Idempotent Phase 15 entry executor.

    The engine never chooses a broker. It receives one explicit intent and one matching
    adapter. Before any new submission it asks the broker for the deterministic client
    order id; only a definitive not-found response permits a new submit attempt.
    """

    def attempt(
        self,
        intent: ExecutionIntent,
        adapter: BrokerAdapter,
        *,
        now_utc: datetime | None = None,
    ) -> ExecutionAttemptRecord:
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        plan = build_broker_order_plan(intent)
        reconciliation = reconcile_broker(adapter, now_utc=now)

        try:
            existing = adapter.order(plan.client_order_id)
        except BrokerOrderNotFound:
            existing = None
        except BrokerAdapterError as exc:
            # If ATLAS cannot prove the deterministic id is absent, submitting a new
            # order could duplicate exposure. Fail closed before preview/submission.
            raise ExecutionEngineError(
                "cannot prove deterministic client order id is absent; submission blocked"
            ) from exc

        if existing is not None:
            if existing.broker != intent.broker:
                raise ExecutionEngineError("existing idempotent order belongs to a different broker")
            preflight = BrokerPreflightResult(
                broker=intent.broker,
                intent_id=intent.intent_id,
                accepted=True,
                as_of_utc=now,
                provider_code="IDEMPOTENT_EXISTING_ORDER",
                provider_message="Existing deterministic client order id reused; no new submission.",
                reason_codes=("EXISTING_CLIENT_ORDER_ID_REUSED", "NO_NEW_BROKER_WRITE"),
            )
            validate_submission_gate(
                intent,
                plan,
                adapter=adapter,
                reconciliation=reconciliation,
                preflight=preflight,
            )
            return ExecutionAttemptRecord(
                attempted_at_utc=now,
                intent=intent,
                order_plan=plan,
                reconciliation_before=reconciliation,
                preflight=preflight,
                order_snapshot=existing,
                existing_order_reused=True,
                provider_submission_performed=False,
                broker_write_count=0,
                order_write_count=0,
                live_submission_performed=False,
            )

        try:
            preflight = adapter.preview(plan)
        except BrokerAdapterError as exc:
            raise ExecutionEngineError("broker preflight failed closed") from exc
        validate_submission_gate(
            intent,
            plan,
            adapter=adapter,
            reconciliation=reconciliation,
            preflight=preflight,
        )

        try:
            submitted = adapter.submit(plan)
        except BrokerSubmissionUncertain:
            # The provider may already hold the order. The only safe next action is
            # reconciliation by deterministic client id; never call submit again here.
            raise
        except BrokerAdapterError as exc:
            raise ExecutionEngineError("broker submission failed") from exc

        if submitted.client_order_id != plan.client_order_id:
            raise ExecutionEngineError("broker acknowledgement changed deterministic client order id")
        if submitted.broker != intent.broker:
            raise ExecutionEngineError("broker acknowledgement changed explicit broker identity")

        provider_submission = intent.environment == ExecutionEnvironment.PAPER
        return ExecutionAttemptRecord(
            attempted_at_utc=now,
            intent=intent,
            order_plan=plan,
            reconciliation_before=reconciliation,
            preflight=preflight,
            order_snapshot=submitted,
            existing_order_reused=False,
            provider_submission_performed=provider_submission,
            broker_write_count=1 if provider_submission else 0,
            order_write_count=1 if provider_submission else 0,
            live_submission_performed=False,
        )
