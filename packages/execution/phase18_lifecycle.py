from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from packages.brokers.base import (
    BrokerAdapter,
    BrokerMutationUncertain,
    BrokerSubmissionUncertain,
)
from packages.control_plane.phase18_authorization import (
    Phase18MutationAuthorization,
    require_phase18_mutation_authorization,
)
from packages.execution.engine import ExecutionEngine
from packages.execution.phase21_authority import (
    authorize_phase21_paper_execution,
    build_phase18_paper_execution_challenge,
)
from packages.execution.validator import reconcile_broker
from packages.schemas.execution import (
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerReconciliationSnapshot,
    ExecutionEnvironment,
    ExecutionIntent,
)
from packages.schemas.execution_attempt import ExecutionAttemptRecord


class Phase18LifecycleError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        provider_state_uncertain: bool = False,
        reconciliation: BrokerReconciliationSnapshot | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.provider_state_uncertain = provider_state_uncertain
        self.reconciliation = reconciliation


@dataclass(frozen=True)
class Phase18LifecycleResult:
    broker: str
    client_order_id: str
    attempt: ExecutionAttemptRecord
    exact_order_after_submit: BrokerOrderSnapshot
    cancellation: BrokerOrderSnapshot | None
    reconciliation_after: BrokerReconciliationSnapshot
    provider_write_count: int
    cleanup_required: bool
    disposition: str


def _safe_reconcile_after_uncertainty(
    adapter: BrokerAdapter,
    *,
    stage: str,
    now_utc: datetime,
) -> BrokerReconciliationSnapshot | None:
    try:
        return reconcile_broker(adapter, now_utc=now_utc)
    except Exception:
        return None


def run_phase18_cancelable_paper_lifecycle(
    intent: ExecutionIntent,
    adapter: BrokerAdapter,
    *,
    authorization: Phase18MutationAuthorization,
    max_abs_correlation: float | None = None,
    now_utc: datetime | None = None,
) -> Phase18LifecycleResult:
    """Exercise one explicitly authorized paper-provider submit/reconcile/cancel lifecycle.

    Phase 18's original operator authorization remains the outer certification authority.
    After that authority is validated, a narrow Phase 21 submit authority is derived for
    the exact certification intent so the provider write also crosses the unified central
    PAPER submission gate.
    """

    auth = require_phase18_mutation_authorization(authorization)
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)

    if intent.environment != ExecutionEnvironment.PAPER:
        raise Phase18LifecycleError(
            "Phase 18 real mutation lifecycle accepts paper/sandbox intents only",
            stage="authority",
        )
    if adapter.environment != ExecutionEnvironment.PAPER:
        raise Phase18LifecycleError(
            "Phase 18 adapter must be paper/sandbox",
            stage="authority",
        )
    if auth.normalized_broker != intent.broker.value or adapter.broker != intent.broker:
        raise Phase18LifecycleError(
            "explicit authorization, intent broker, and adapter broker must match",
            stage="authority",
        )

    phase21_challenge = build_phase18_paper_execution_challenge(intent)
    phase21_authority = authorize_phase21_paper_execution(
        phase21_challenge,
        explicitly_authorized=True,
        confirmation=phase21_challenge.required_confirmation,
    )

    before = reconcile_broker(adapter, now_utc=now)
    if not before.reconciled:
        raise Phase18LifecycleError("broker did not reconcile", stage="pre_reconciliation")
    if not before.zero_open_orders or not before.zero_positions:
        raise Phase18LifecycleError(
            "first Phase 18 provider-mutation lifecycle requires a flat broker with zero open orders",
            stage="pre_reconciliation",
            reconciliation=before,
        )

    try:
        attempt = ExecutionEngine().attempt(
            intent,
            adapter,
            max_abs_correlation=max_abs_correlation,
            now_utc=now,
            execution_scope_id=phase21_challenge.execution_scope_id,
            paper_authority=phase21_authority,
        )
    except BrokerSubmissionUncertain as exc:
        after_uncertain = _safe_reconcile_after_uncertainty(
            adapter, stage="submit", now_utc=now
        )
        raise Phase18LifecycleError(
            "submission outcome is uncertain; no retry, cancellation, failover, or second mutation is allowed until exact reconciliation",
            stage="submit",
            provider_state_uncertain=True,
            reconciliation=after_uncertain,
        ) from exc

    if not attempt.provider_submission_performed or attempt.existing_order_reused:
        raise Phase18LifecycleError(
            "Phase 18 lifecycle requires one newly acknowledged paper-provider submission",
            stage="submit",
        )

    client_order_id = attempt.order_plan.client_order_id
    try:
        exact = adapter.order(client_order_id)
    except Exception as exc:
        after_uncertain = _safe_reconcile_after_uncertainty(
            adapter, stage="post_submit_reconciliation", now_utc=now
        )
        raise Phase18LifecycleError(
            "new submission cannot be reconciled by exact client order id; further mutation is blocked",
            stage="post_submit_reconciliation",
            provider_state_uncertain=True,
            reconciliation=after_uncertain,
        ) from exc

    cancellation: BrokerOrderSnapshot | None = None
    writes = int(attempt.broker_write_count)
    if exact.status in {BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.PARTIAL_FILLED}:
        try:
            cancellation = adapter.cancel(client_order_id)
            writes += 1
        except BrokerMutationUncertain as exc:
            after_uncertain = _safe_reconcile_after_uncertainty(
                adapter, stage="cancel", now_utc=now
            )
            raise Phase18LifecycleError(
                "cancellation outcome is uncertain; no retry, failover, or further mutation is allowed until exact reconciliation",
                stage="cancel",
                provider_state_uncertain=True,
                reconciliation=after_uncertain,
            ) from exc

    after = reconcile_broker(adapter, now_utc=now)

    if exact.status in {BrokerOrderStatus.FILLED, BrokerOrderStatus.PARTIAL_FILLED}:
        return Phase18LifecycleResult(
            broker=adapter.broker.value,
            client_order_id=client_order_id,
            attempt=attempt,
            exact_order_after_submit=exact,
            cancellation=cancellation,
            reconciliation_after=after,
            provider_write_count=writes,
            cleanup_required=not after.safe_to_switch_broker,
            disposition="POSITION_OR_PARTIAL_FILL_REQUIRES_SEPARATE_EXPLICIT_CLEANUP",
        )

    if cancellation is not None and cancellation.status != BrokerOrderStatus.CANCELLED:
        raise Phase18LifecycleError(
            "provider cancellation did not reconcile to CANCELLED; further mutation is blocked",
            stage="post_cancel_reconciliation",
            provider_state_uncertain=True,
            reconciliation=after,
        )

    if not after.zero_open_orders or not after.zero_positions:
        return Phase18LifecycleResult(
            broker=adapter.broker.value,
            client_order_id=client_order_id,
            attempt=attempt,
            exact_order_after_submit=exact,
            cancellation=cancellation,
            reconciliation_after=after,
            provider_write_count=writes,
            cleanup_required=True,
            disposition="BROKER_NOT_FLAT_AFTER_LIFECYCLE_REQUIRES_SEPARATE_EXPLICIT_CLEANUP",
        )

    return Phase18LifecycleResult(
        broker=adapter.broker.value,
        client_order_id=client_order_id,
        attempt=attempt,
        exact_order_after_submit=exact,
        cancellation=cancellation,
        reconciliation_after=after,
        provider_write_count=writes,
        cleanup_required=False,
        disposition="SUBMIT_RECONCILE_CANCEL_RECONCILE_COMPLETE",
    )
