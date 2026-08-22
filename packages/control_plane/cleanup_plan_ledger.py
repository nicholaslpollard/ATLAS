from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from packages.schemas.control_plane import ControlPlaneActionState
from packages.schemas.control_plane_cleanup import (
    ControlPlaneCleanupPlan,
    ControlPlaneCleanupPlanConfirmationGrant,
    cleanup_plan_confirmation_matches,
)
from packages.schemas.control_plane_ledger import ControlPlaneAuditEventType

from .action_ledger import (
    ControlPlaneActionConflict,
    ControlPlaneActionLedger,
    ControlPlaneActionLedgerError,
)


CONTROL_PLANE_CLEANUP_PLAN_LEDGER_CONTRACT_VERSION = (
    "control-plane-cleanup-plan-ledger-v1-shared-audit-latest-plan-one-time-confirmation"
)


class ControlPlaneCleanupPlanLedgerError(RuntimeError):
    pass


class ControlPlaneCleanupPlanConflict(ControlPlaneCleanupPlanLedgerError):
    pass


class ControlPlaneCleanupPlanNotFound(ControlPlaneCleanupPlanLedgerError):
    pass


@dataclass(frozen=True, slots=True)
class CleanupPlanAuditState:
    plans: tuple[ControlPlaneCleanupPlan, ...]
    confirmation: ControlPlaneCleanupPlanConfirmationGrant | None
    confirmed_plan_fingerprint: str | None

    @property
    def latest_plan(self) -> ControlPlaneCleanupPlan | None:
        return self.plans[-1] if self.plans else None


class ControlPlaneCleanupPlanLedger:
    """Replay cleanup plans and exact confirmations from the action ledger's hash chain."""

    def __init__(
        self,
        action_ledger: ControlPlaneActionLedger,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.action_ledger = action_ledger
        # Reuse the exact same writer/lock. Do not create another ControlPlaneAuditLog
        # object pointing at this path inside the control-plane process.
        self.audit_log = action_ledger.audit_log
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ControlPlaneCleanupPlanLedgerError("cleanup plan ledger clock must be timezone-aware")
        return value.astimezone(UTC)

    def state(self, action_id: str) -> CleanupPlanAuditState:
        try:
            action = self.action_ledger.get(action_id)
            events = self.audit_log.read_verified()
        except ControlPlaneActionLedgerError as exc:
            raise ControlPlaneCleanupPlanLedgerError("action/audit ledger verification failed") from exc

        plans: list[ControlPlaneCleanupPlan] = []
        by_fingerprint: dict[str, ControlPlaneCleanupPlan] = {}
        confirmation: ControlPlaneCleanupPlanConfirmationGrant | None = None
        confirmed_fp: str | None = None

        for event in events:
            if event.action_id != action_id:
                continue
            if event.event_type == ControlPlaneAuditEventType.CLEANUP_PLAN_CREATED:
                raw_plan = event.details.get("cleanup_plan")
                raw_fp = event.details.get("cleanup_plan_fingerprint")
                try:
                    plan = ControlPlaneCleanupPlan.model_validate(raw_plan)
                except Exception as exc:
                    raise ControlPlaneCleanupPlanLedgerError(
                        f"invalid cleanup plan in audit sequence {event.sequence}"
                    ) from exc
                fp = plan.plan_fingerprint()
                if raw_fp != fp:
                    raise ControlPlaneCleanupPlanLedgerError("cleanup plan audit fingerprint mismatch")
                if (
                    event.action_fingerprint != plan.action_fingerprint
                    or event.action_fingerprint != action.request_fingerprint
                    or plan.action_id != action_id
                    or event.action_state != ControlPlaneActionState.AUTHORIZED
                ):
                    raise ControlPlaneCleanupPlanLedgerError("cleanup plan audit action binding mismatch")
                if fp in by_fingerprint:
                    raise ControlPlaneCleanupPlanLedgerError("duplicate cleanup plan fingerprint event")
                plans.append(plan)
                by_fingerprint[fp] = plan
            elif event.event_type == ControlPlaneAuditEventType.CLEANUP_PLAN_CONFIRMATION_GRANTED:
                raw_grant = event.details.get("cleanup_plan_confirmation")
                raw_fp = event.details.get("cleanup_plan_fingerprint")
                try:
                    grant = ControlPlaneCleanupPlanConfirmationGrant.model_validate(raw_grant)
                except Exception as exc:
                    raise ControlPlaneCleanupPlanLedgerError(
                        f"invalid cleanup plan confirmation in audit sequence {event.sequence}"
                    ) from exc
                plan = by_fingerprint.get(str(raw_fp))
                if plan is None:
                    raise ControlPlaneCleanupPlanLedgerError(
                        "cleanup plan confirmation references an unknown prior plan"
                    )
                if (
                    event.action_fingerprint != action.request_fingerprint
                    or event.action_state != ControlPlaneActionState.AUTHORIZED
                    or not cleanup_plan_confirmation_matches(plan, grant)
                ):
                    raise ControlPlaneCleanupPlanLedgerError(
                        "cleanup plan confirmation audit binding mismatch"
                    )
                if confirmation is not None:
                    raise ControlPlaneCleanupPlanLedgerError(
                        "multiple cleanup plan confirmation events exist for one action"
                    )
                confirmation = grant
                confirmed_fp = plan.plan_fingerprint()

        return CleanupPlanAuditState(
            plans=tuple(plans),
            confirmation=confirmation,
            confirmed_plan_fingerprint=confirmed_fp,
        )

    def record_plan(self, plan: ControlPlaneCleanupPlan) -> ControlPlaneCleanupPlan:
        try:
            action = self.action_ledger.get(plan.action_id)
        except ControlPlaneActionLedgerError as exc:
            raise ControlPlaneCleanupPlanLedgerError("cleanup action is unavailable") from exc
        if action.state != ControlPlaneActionState.AUTHORIZED:
            raise ControlPlaneCleanupPlanConflict(
                f"cleanup plan requires an authorized action: {action.state}"
            )
        if action.request_fingerprint != plan.action_fingerprint:
            raise ControlPlaneCleanupPlanConflict("cleanup plan action fingerprint mismatch")
        if action.request.action_kind != plan.action_kind:
            raise ControlPlaneCleanupPlanConflict("cleanup plan action kind mismatch")
        if action.request.target_broker != plan.broker or action.request.environment != plan.environment:
            raise ControlPlaneCleanupPlanConflict("cleanup plan broker/environment mismatch")
        if plan.provider_write_authorized:
            raise ControlPlaneCleanupPlanConflict("review ledger cannot record provider-write authority")

        state = self.state(plan.action_id)
        fingerprint = plan.plan_fingerprint()
        for existing in state.plans:
            if existing.plan_fingerprint() == fingerprint:
                return existing
        if state.confirmation is not None:
            raise ControlPlaneCleanupPlanConflict(
                "a confirmed cleanup plan cannot be silently superseded"
            )

        self.audit_log.append(
            event_type=ControlPlaneAuditEventType.CLEANUP_PLAN_CREATED,
            actor="atlas_system",
            action_id=plan.action_id,
            action_fingerprint=plan.action_fingerprint,
            action_state=ControlPlaneActionState.AUTHORIZED,
            details={
                "cleanup_plan_fingerprint": fingerprint,
                "cleanup_plan": plan.model_dump(mode="json"),
                "provider_write_authorized": False,
            },
        )
        return plan

    def confirm_latest(
        self,
        action_id: str,
        grant: ControlPlaneCleanupPlanConfirmationGrant,
    ) -> ControlPlaneCleanupPlan:
        try:
            action = self.action_ledger.get(action_id)
        except ControlPlaneActionLedgerError as exc:
            raise ControlPlaneCleanupPlanLedgerError("cleanup action is unavailable") from exc
        if action.state != ControlPlaneActionState.AUTHORIZED:
            raise ControlPlaneCleanupPlanConflict(
                f"cleanup plan confirmation requires authorized action: {action.state}"
            )
        state = self.state(action_id)
        plan = state.latest_plan
        if plan is None:
            raise ControlPlaneCleanupPlanNotFound(action_id)
        if state.confirmation is not None:
            if (
                state.confirmation == grant
                and state.confirmed_plan_fingerprint == plan.plan_fingerprint()
            ):
                return plan
            raise ControlPlaneCleanupPlanConflict(
                "cleanup plan confirmation has already been consumed"
            )
        if not cleanup_plan_confirmation_matches(plan, grant):
            raise ControlPlaneCleanupPlanConflict(
                "cleanup confirmation does not bind the latest exact resource plan"
            )
        now = self._now()
        if now > plan.expires_at_utc or grant.confirmed_at_utc > plan.expires_at_utc:
            raise ControlPlaneCleanupPlanConflict(
                "cleanup plan expired before exact confirmation"
            )
        if grant.confirmed_at_utc < plan.generated_at_utc:
            raise ControlPlaneCleanupPlanConflict(
                "cleanup plan confirmation predates the plan"
            )

        self.audit_log.append(
            event_type=ControlPlaneAuditEventType.CLEANUP_PLAN_CONFIRMATION_GRANTED,
            actor="local_user",
            action_id=action_id,
            action_fingerprint=action.request_fingerprint,
            action_state=ControlPlaneActionState.AUTHORIZED,
            details={
                "cleanup_plan_fingerprint": plan.plan_fingerprint(),
                "cleanup_plan_confirmation": grant.model_dump(mode="json"),
                "provider_write_authorized": False,
            },
        )
        return plan

    def verify(self) -> dict[str, object]:
        try:
            records = self.action_ledger.records()
        except (ControlPlaneActionLedgerError, ControlPlaneActionConflict) as exc:
            raise ControlPlaneCleanupPlanLedgerError("action ledger verification failed") from exc
        plan_count = 0
        confirmed_count = 0
        for action_id, record in records.items():
            if record.request.action_kind.value not in {
                "CANCEL_OPEN_ORDERS",
                "FLATTEN_POSITIONS",
            }:
                continue
            state = self.state(action_id)
            plan_count += len(state.plans)
            confirmed_count += 1 if state.confirmation is not None else 0
        return {
            "plan_count": plan_count,
            "confirmed_plan_count": confirmed_count,
            "provider_write_authority_count": 0,
            "shared_audit_chain_valid": True,
            "pass": True,
        }
