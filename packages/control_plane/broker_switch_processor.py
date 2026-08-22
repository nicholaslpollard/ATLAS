from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from packages.brokers.alpaca import AlpacaPaperBroker
from packages.brokers.base import BrokerAdapter, BrokerAdapterError
from packages.brokers.webull import WebullSandboxBroker
from packages.core.settings import AtlasSettings
from packages.execution.broker_switch import BrokerSwitchError, authorize_broker_switch
from packages.execution.validator import ExecutionValidationError, reconcile_broker
from packages.schemas.control_plane import ControlPlaneActionKind, ControlPlaneActionState
from packages.schemas.control_plane_ledger import ControlPlaneActionRecord
from packages.schemas.control_plane_runtime import ControlPlaneRuntimeState
from packages.schemas.execution import BrokerName, ExecutionEnvironment

from .action_ledger import (
    ControlPlaneActionConflict,
    ControlPlaneActionLedger,
)
from .runtime_state import (
    ControlPlaneRuntimeStateError,
    ControlPlaneRuntimeStateStore,
)
from .status import Phase16StatusService


BROKER_SWITCH_PROCESSOR_CONTRACT_VERSION = (
    "control-plane-broker-switch-v1-phase15-reconciled-flat-local-routing-only"
)


class ControlPlaneBrokerSwitchError(RuntimeError):
    pass


BrokerFactory = Callable[[BrokerName], BrokerAdapter]


def _default_broker_factory(broker: BrokerName) -> BrokerAdapter:
    if broker == BrokerName.WEBULL:
        return WebullSandboxBroker()
    if broker == BrokerName.ALPACA:
        return AlpacaPaperBroker()
    raise ControlPlaneBrokerSwitchError(f"unsupported broker: {broker}")


def _other_provider(broker: BrokerName) -> BrokerName:
    if broker == BrokerName.WEBULL:
        return BrokerName.ALPACA
    if broker == BrokerName.ALPACA:
        return BrokerName.WEBULL
    raise ControlPlaneBrokerSwitchError("provider switch target must be Webull or Alpaca")


class Phase16BrokerSwitchProcessor:
    """Process an authorized broker-selection action without any provider mutation.

    Both paper brokers are reconciled through Phase 15 and must be flat. The only write
    this processor performs is the local, audit-bound runtime routing state. It never
    previews/submits/cancels/closes provider orders or positions.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        status_service: Phase16StatusService | None = None,
        ledger: ControlPlaneActionLedger | None = None,
        runtime_store: ControlPlaneRuntimeStateStore | None = None,
        broker_factory: BrokerFactory | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self._clock = clock or (lambda: datetime.now(UTC))
        self.status_service = status_service or Phase16StatusService(settings)
        self.ledger = ledger or ControlPlaneActionLedger(settings, clock=self._clock)
        self.runtime_store = runtime_store or self.status_service.runtime_store
        self._broker_factory = broker_factory or _default_broker_factory

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ControlPlaneBrokerSwitchError("processor clock must be timezone-aware")
        return value.astimezone(UTC)

    def _block(
        self,
        record: ControlPlaneActionRecord,
        code: str,
        *,
        details: dict[str, object] | None = None,
    ) -> ControlPlaneActionRecord:
        if record.state == ControlPlaneActionState.AUTHORIZED:
            return self.ledger.transition(
                record.request.action_id,
                ControlPlaneActionState.BLOCKED,
                error_code=code,
                event_details=details,
            )
        if record.state == ControlPlaneActionState.EXECUTING:
            return self.ledger.transition(
                record.request.action_id,
                ControlPlaneActionState.FAILED,
                error_code=code,
                event_details=details,
            )
        raise ControlPlaneActionConflict(
            f"cannot block broker switch from state {record.state}"
        )

    def _reconcile_pair(
        self,
        *,
        current_broker: BrokerName,
        target_broker: BrokerName,
    ):
        for broker in (current_broker, target_broker):
            if not self.status_service.credentials(broker).ready:
                raise ControlPlaneBrokerSwitchError(
                    f"credentials unavailable for {broker.value}"
                )
        current_adapter = self._broker_factory(current_broker)
        target_adapter = self._broker_factory(target_broker)
        if (
            current_adapter.broker != current_broker
            or target_adapter.broker != target_broker
            or current_adapter.environment != ExecutionEnvironment.PAPER
            or target_adapter.environment != ExecutionEnvironment.PAPER
        ):
            raise ControlPlaneBrokerSwitchError("broker adapter identity/environment mismatch")
        now = self._now()
        current = reconcile_broker(current_adapter, now_utc=now)
        target = reconcile_broker(target_adapter, now_utc=now)
        authorization = authorize_broker_switch(
            current,
            target,
            explicit_request=True,
            now_utc=now,
        )
        return current, target, authorization

    def _runtime_transition_event_for(
        self,
        record: ControlPlaneActionRecord,
        *,
        current_revision: int,
        target_broker: BrokerName,
    ):
        events = self.ledger.runtime_transition_events(record.request.action_id)
        if len(events) > 1:
            raise ControlPlaneBrokerSwitchError(
                "multiple runtime transition intents exist for one broker-switch action"
            )
        if not events:
            return None
        event = events[0]
        expected = {
            "transition_kind": "BROKER_SELECTION",
            "prior_revision": current_revision,
            "next_revision": current_revision + 1,
            "selected_broker": target_broker.value,
            "selected_environment": ExecutionEnvironment.PAPER.value,
            "provider_write_attempted": False,
        }
        if event.details != expected:
            raise ControlPlaneBrokerSwitchError(
                "existing runtime transition intent does not match current routing transition"
            )
        return event

    def process(self, action_id: str) -> ControlPlaneActionRecord:
        record = self.ledger.get(action_id)
        request = record.request
        if request.action_kind != ControlPlaneActionKind.BROKER_SWITCH:
            raise ControlPlaneBrokerSwitchError("action is not a broker-switch request")
        if (
            request.environment != ExecutionEnvironment.PAPER
            or request.target_broker not in {BrokerName.WEBULL, BrokerName.ALPACA}
        ):
            raise ControlPlaneBrokerSwitchError(
                "Phase 16 provider broker switching is paper-only"
            )
        if record.state in {
            ControlPlaneActionState.BLOCKED,
            ControlPlaneActionState.COMPLETED,
            ControlPlaneActionState.FAILED,
        }:
            return record
        if record.state == ControlPlaneActionState.AWAITING_CONFIRMATION:
            raise ControlPlaneActionConflict("broker switch still awaits explicit confirmation")
        if record.state not in {
            ControlPlaneActionState.AUTHORIZED,
            ControlPlaneActionState.EXECUTING,
        }:
            raise ControlPlaneActionConflict(
                f"broker switch cannot be processed from state {record.state}"
            )
        if not self.status_service.phase15_acceptance().accepted:
            return self._block(record, "PHASE15_ACCEPTANCE_REQUIRED")

        try:
            runtime = self.runtime_store.load()
        except ControlPlaneRuntimeStateError:
            return self._block(record, "RUNTIME_STATE_INVALID")

        target_broker = request.target_broker
        if (
            runtime.selected_broker == target_broker
            and runtime.selected_environment == ExecutionEnvironment.PAPER
        ):
            if runtime.last_transition_action_id == action_id:
                events = self.ledger.runtime_transition_events(action_id)
                if len(events) != 1 or events[0].event_hash != runtime.last_transition_audit_hash:
                    return self._block(record, "RUNTIME_AUDIT_BINDING_INVALID")
                if record.state == ControlPlaneActionState.EXECUTING:
                    return self.ledger.transition(
                        action_id,
                        ControlPlaneActionState.COMPLETED,
                        result_reference=f"runtime:{runtime.authority_fingerprint()}",
                        event_details={
                            "broker_switch_recovered_after_runtime_persist": True,
                            "provider_write_attempted": False,
                        },
                    )
                return self._block(record, "TARGET_BROKER_ALREADY_SELECTED")
            return self._block(record, "TARGET_BROKER_ALREADY_SELECTED")

        current_broker = (
            runtime.selected_broker
            if runtime.selected_environment == ExecutionEnvironment.PAPER
            and runtime.selected_broker in {BrokerName.WEBULL, BrokerName.ALPACA}
            else _other_provider(target_broker)
        )
        if current_broker == target_broker:
            return self._block(record, "TARGET_BROKER_ALREADY_SELECTED")

        try:
            current, target, authorization = self._reconcile_pair(
                current_broker=current_broker,
                target_broker=target_broker,
            )
        except (
            BrokerAdapterError,
            BrokerSwitchError,
            ControlPlaneBrokerSwitchError,
            ExecutionValidationError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exc:
            return self._block(
                record,
                "BROKER_RECONCILIATION_FAILED",
                details={
                    "exception_type": type(exc).__name__,
                    "provider_write_attempted": False,
                },
            )

        reconciliation_details = {
            "current_broker": current.broker.value,
            "target_broker": target.broker.value,
            "current_zero_open_orders": current.zero_open_orders,
            "current_zero_positions": current.zero_positions,
            "target_zero_open_orders": target.zero_open_orders,
            "target_zero_positions": target.zero_positions,
            "switch_authorized": authorization.authorized,
            "reason_codes": list(authorization.reason_codes),
            "provider_write_attempted": False,
        }
        if not authorization.authorized:
            return self._block(
                record,
                "BROKER_SWITCH_NOT_AUTHORIZED",
                details=reconciliation_details,
            )

        if record.state == ControlPlaneActionState.AUTHORIZED:
            record = self.ledger.transition(
                action_id,
                ControlPlaneActionState.EXECUTING,
                event_details=reconciliation_details,
            )

        runtime = self.runtime_store.load()
        if (
            runtime.selected_broker == target_broker
            and runtime.selected_environment == ExecutionEnvironment.PAPER
            and runtime.last_transition_action_id == action_id
        ):
            events = self.ledger.runtime_transition_events(action_id)
            if len(events) == 1 and events[0].event_hash == runtime.last_transition_audit_hash:
                return self.ledger.transition(
                    action_id,
                    ControlPlaneActionState.COMPLETED,
                    result_reference=f"runtime:{runtime.authority_fingerprint()}",
                    event_details={
                        "broker_switch_recovered_after_runtime_persist": True,
                        "provider_write_attempted": False,
                    },
                )
            return self._block(record, "RUNTIME_AUDIT_BINDING_INVALID")

        try:
            transition_event = self._runtime_transition_event_for(
                record,
                current_revision=runtime.revision,
                target_broker=target_broker,
            )
        except ControlPlaneBrokerSwitchError:
            return self._block(record, "RUNTIME_TRANSITION_INTENT_INVALID")
        if transition_event is None:
            transition_event = self.ledger.append_runtime_transition_intent(
                action_id,
                prior_revision=runtime.revision,
                next_revision=runtime.revision + 1,
                selected_broker=target_broker.value,
                selected_environment=ExecutionEnvironment.PAPER.value,
            )

        next_state = ControlPlaneRuntimeState(
            revision=runtime.revision + 1,
            updated_at_utc=self._now(),
            selected_broker=target_broker,
            selected_environment=ExecutionEnvironment.PAPER,
            provider_write_uncertain=False,
            active_action_id=None,
            uncertain_action_id=None,
            last_transition_action_id=action_id,
            last_transition_audit_hash=transition_event.event_hash,
            source="persisted",
        )
        try:
            saved = self.runtime_store.persist_transition(
                next_state,
                expected_prior_revision=runtime.revision,
            )
        except ControlPlaneRuntimeStateError:
            raise

        return self.ledger.transition(
            action_id,
            ControlPlaneActionState.COMPLETED,
            result_reference=f"runtime:{saved.authority_fingerprint()}",
            event_details={
                **reconciliation_details,
                "runtime_revision": saved.revision,
                "runtime_transition_audit_hash": transition_event.event_hash,
                "provider_write_attempted": False,
            },
        )
