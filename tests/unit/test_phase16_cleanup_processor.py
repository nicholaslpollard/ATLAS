from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.cleanup_plan_ledger import ControlPlaneCleanupPlanLedger
from packages.control_plane.cleanup_planner import Phase16CleanupPlanner
from packages.control_plane.cleanup_processor import (
    ControlPlaneCleanupProcessorBlocked,
    Phase16CleanupProcessor,
)
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneActionState,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
)
from packages.schemas.control_plane_cleanup import ControlPlaneCleanupPlanConfirmationGrant
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    ExecutionEnvironment,
)


NOW = datetime(2026, 8, 23, 0, 30, tzinfo=UTC)


class FakeProcessorBroker:
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        broker: BrokerName,
        *,
        orders: tuple[BrokerOrderSnapshot, ...] = (),
        positions: tuple[BrokerPositionSnapshot, ...] = (),
    ) -> None:
        self.broker = broker
        self.account_id = f"{broker.value}-processor-account"
        self.orders_state = orders
        self.positions_state = positions
        self.read_calls: list[str] = []
        self.write_calls: list[str] = []

    def account(self) -> BrokerAccountSnapshot:
        self.read_calls.append("account")
        return BrokerAccountSnapshot(
            broker=self.broker,
            environment=self.environment,
            account_id=self.account_id,
            as_of_utc=NOW,
            equity=25000.0,
            cash=20000.0,
            buying_power=40000.0,
            gross_market_value=sum(abs(item.market_value) for item in self.positions_state),
            trading_blocked=False,
            shorting_enabled=True,
        )

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        self.read_calls.append("open_orders")
        return self.orders_state

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        self.read_calls.append("positions")
        return self.positions_state

    def preview(self, plan):
        self.write_calls.append("preview")
        raise AssertionError("cleanup processor v1 cannot preview")

    def submit(self, plan):
        self.write_calls.append("submit")
        raise AssertionError("cleanup processor v1 cannot submit")

    def order(self, client_order_id):
        self.write_calls.append("order")
        raise AssertionError("cleanup processor v1 does not query individual orders")

    def cancel(self, client_order_id):
        self.write_calls.append("cancel")
        raise AssertionError("cleanup processor v1 cannot cancel")


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _write_phase15_acceptance(tmp_path) -> None:
    root = tmp_path / "execution" / "phase15" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    (root / "phase15_final_acceptance.json").write_text(
        json.dumps(
            {
                "contract_version": PHASE15_CLOSEOUT_CONTRACT_VERSION,
                "pass": True,
                "as_of_date": "2026-08-14",
                "phase15_policy_fingerprint": phase15_policy_fingerprint(),
                "cumulative_foundation_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
                "execution_case_count": 0,
                "final_disposition": {
                    "phase15_accepted": True,
                    "actual_broker_execution_exercised_in_acceptance": False,
                    "live_execution_promoted": False,
                    "automatic_cross_broker_failover_allowed": False,
                },
            }
        ),
        encoding="utf-8",
    )


def _credentials(broker: BrokerName) -> dict[str, str]:
    if broker == BrokerName.WEBULL:
        return {"WEBULL_APP_KEY": "wk", "WEBULL_APP_SECRET": "ws"}
    return {"ALPACA_PAPER_API_KEY": "ak", "ALPACA_PAPER_API_SECRET": "as"}


def _order(broker: BrokerName, account_id: str, client_id: str, ticker: str = "SPY"):
    return BrokerOrderSnapshot(
        broker=broker,
        account_id=account_id,
        client_order_id=client_id,
        provider_order_id=f"provider-{client_id}",
        ticker=ticker,
        side=BrokerOrderSide.BUY,
        status=BrokerOrderStatus.SUBMITTED,
        requested_quantity=2.0,
        filled_quantity=0.0,
        submitted_at_utc=NOW,
        updated_at_utc=NOW,
    )


def _position(broker: BrokerName, account_id: str, ticker: str, quantity: float):
    return BrokerPositionSnapshot(
        broker=broker,
        account_id=account_id,
        ticker=ticker,
        quantity=quantity,
        market_value=quantity * 100.0,
        average_entry_price=95.0,
        as_of_utc=NOW,
    )


def _authorized_action(
    ledger: ControlPlaneActionLedger,
    *,
    action_id: str,
    kind: ControlPlaneActionKind,
    broker: BrokerName,
):
    request = ControlPlaneActionRequest(
        action_id=action_id,
        action_kind=kind,
        requested_at_utc=NOW,
        idempotency_key=f"idem-{action_id}",
        target_broker=broker,
        environment=ExecutionEnvironment.PAPER,
        reason="cleanup processor test",
    )
    ledger.create_request(request)
    scope = (
        ControlPlaneConfirmationScope.CANCEL_OPEN_ORDERS
        if kind == ControlPlaneActionKind.CANCEL_OPEN_ORDERS
        else ControlPlaneConfirmationScope.FLATTEN_POSITIONS
    )
    return ledger.confirm(
        action_id,
        ControlPlaneConfirmationGrant(
            grant_id=f"grant-{action_id}",
            action_id=action_id,
            action_fingerprint=request.authority_fingerprint(),
            scope=scope,
            confirmed_at_utc=NOW + timedelta(seconds=1),
        ),
    )


def _build_confirmed_plan(
    tmp_path,
    fake: FakeProcessorBroker,
    *,
    action_id: str,
    kind: ControlPlaneActionKind,
):
    _write_phase15_acceptance(tmp_path)
    settings = _settings(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=5))
    action = _authorized_action(
        ledger,
        action_id=action_id,
        kind=kind,
        broker=fake.broker,
    )
    service = Phase16StatusService(
        settings,
        env=_credentials(fake.broker),
        clock=lambda: NOW + timedelta(seconds=10),
        action_ledger=ledger,
    )
    planner = Phase16CleanupPlanner(
        settings,
        status_service=service,
        ledger=ledger,
        broker_factory=lambda broker: fake,
        clock=lambda: NOW + timedelta(seconds=10),
    )
    plan = planner.build(action_id)
    plan_ledger = ControlPlaneCleanupPlanLedger(
        ledger, clock=lambda: NOW + timedelta(seconds=11)
    )
    plan_ledger.record_plan(plan)
    plan_ledger.confirm_latest(
        action_id,
        ControlPlaneCleanupPlanConfirmationGrant(
            grant_id=f"plan-grant-{action_id}",
            action_id=action_id,
            action_fingerprint=action.request_fingerprint,
            cleanup_plan_fingerprint=plan.plan_fingerprint(),
            confirmed_at_utc=NOW + timedelta(seconds=11),
        ),
    )
    return settings, ledger, service, plan_ledger, plan


def _processor(
    settings,
    ledger,
    service,
    plan_ledger,
    fake: FakeProcessorBroker,
    *,
    clock_seconds: int = 12,
):
    return Phase16CleanupProcessor(
        settings,
        status_service=service,
        action_ledger=ledger,
        cleanup_plan_ledger=plan_ledger,
        broker_factory=lambda broker: fake,
        clock=lambda: NOW + timedelta(seconds=clock_seconds),
    )


def test_confirmed_cancel_plan_with_orders_is_blocked_before_provider_write(tmp_path) -> None:
    fake = FakeProcessorBroker(BrokerName.WEBULL)
    fake.orders_state = (_order(fake.broker, fake.account_id, "cancel-order-0001"),)
    settings, ledger, service, plan_ledger, _ = _build_confirmed_plan(
        tmp_path,
        fake,
        action_id="cancel-process-1",
        kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
    )
    result = _processor(settings, ledger, service, plan_ledger, fake).process(
        "cancel-process-1"
    )
    assert result.state == ControlPlaneActionState.BLOCKED
    assert result.error_code == "CANCEL_PROVIDER_WRITES_DISABLED"
    assert result.provider_write_attempted is False
    assert fake.write_calls == []


def test_confirmed_cancel_noop_completes_locally_with_zero_provider_writes(tmp_path) -> None:
    fake = FakeProcessorBroker(BrokerName.ALPACA)
    settings, ledger, service, plan_ledger, plan = _build_confirmed_plan(
        tmp_path,
        fake,
        action_id="cancel-noop-1",
        kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
    )
    assert plan.no_op is True
    result = _processor(settings, ledger, service, plan_ledger, fake).process(
        "cancel-noop-1"
    )
    assert result.state == ControlPlaneActionState.COMPLETED
    assert result.provider_write_attempted is False
    assert result.result_reference == f"cleanup-noop:{plan.plan_fingerprint()}"
    assert fake.write_calls == []


def test_cancel_resource_drift_blocks_without_expanding_scope(tmp_path) -> None:
    fake = FakeProcessorBroker(BrokerName.WEBULL)
    fake.orders_state = (_order(fake.broker, fake.account_id, "cancel-order-0001"),)
    settings, ledger, service, plan_ledger, _ = _build_confirmed_plan(
        tmp_path,
        fake,
        action_id="cancel-drift-1",
        kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
    )
    fake.orders_state = (
        _order(fake.broker, fake.account_id, "cancel-order-0001"),
        _order(fake.broker, fake.account_id, "cancel-order-0002", "QQQ"),
    )
    result = _processor(settings, ledger, service, plan_ledger, fake).process(
        "cancel-drift-1"
    )
    assert result.state == ControlPlaneActionState.BLOCKED
    assert result.error_code == "CLEANUP_RESOURCE_SET_DRIFT"
    assert fake.write_calls == []


def test_confirmed_flatten_plan_with_position_is_blocked_before_provider_write(tmp_path) -> None:
    fake = FakeProcessorBroker(BrokerName.ALPACA)
    fake.positions_state = (_position(fake.broker, fake.account_id, "QQQ", 3.0),)
    settings, ledger, service, plan_ledger, _ = _build_confirmed_plan(
        tmp_path,
        fake,
        action_id="flatten-process-1",
        kind=ControlPlaneActionKind.FLATTEN_POSITIONS,
    )
    result = _processor(settings, ledger, service, plan_ledger, fake).process(
        "flatten-process-1"
    )
    assert result.state == ControlPlaneActionState.BLOCKED
    assert result.error_code == "FLATTEN_PROVIDER_WRITES_DISABLED"
    assert result.provider_write_attempted is False
    assert fake.write_calls == []


def test_flatten_resource_drift_blocks_without_provider_write(tmp_path) -> None:
    fake = FakeProcessorBroker(BrokerName.ALPACA)
    fake.positions_state = (_position(fake.broker, fake.account_id, "QQQ", 3.0),)
    settings, ledger, service, plan_ledger, _ = _build_confirmed_plan(
        tmp_path,
        fake,
        action_id="flatten-drift-1",
        kind=ControlPlaneActionKind.FLATTEN_POSITIONS,
    )
    fake.positions_state = (_position(fake.broker, fake.account_id, "QQQ", 2.0),)
    result = _processor(settings, ledger, service, plan_ledger, fake).process(
        "flatten-drift-1"
    )
    assert result.state == ControlPlaneActionState.BLOCKED
    assert result.error_code == "CLEANUP_RESOURCE_SET_DRIFT"
    assert fake.write_calls == []


def test_expired_confirmed_plan_blocks_before_reconciliation_or_provider_write(tmp_path) -> None:
    fake = FakeProcessorBroker(BrokerName.WEBULL)
    fake.orders_state = (_order(fake.broker, fake.account_id, "cancel-order-0001"),)
    settings, ledger, service, plan_ledger, _ = _build_confirmed_plan(
        tmp_path,
        fake,
        action_id="cancel-expired-1",
        kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
    )
    reads_after_plan = list(fake.read_calls)
    result = _processor(
        settings,
        ledger,
        service,
        plan_ledger,
        fake,
        clock_seconds=200,
    ).process("cancel-expired-1")
    assert result.state == ControlPlaneActionState.BLOCKED
    assert result.error_code == "CLEANUP_PLAN_EXPIRED"
    assert fake.read_calls == reads_after_plan
    assert fake.write_calls == []


def test_processor_requires_exact_plan_confirmation_before_reconciliation(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=5))
    fake = FakeProcessorBroker(BrokerName.WEBULL)
    fake.orders_state = (_order(fake.broker, fake.account_id, "cancel-order-0001"),)
    _authorized_action(
        ledger,
        action_id="cancel-unconfirmed-plan",
        kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
        broker=fake.broker,
    )
    service = Phase16StatusService(
        settings,
        env=_credentials(fake.broker),
        clock=lambda: NOW + timedelta(seconds=10),
        action_ledger=ledger,
    )
    planner = Phase16CleanupPlanner(
        settings,
        status_service=service,
        ledger=ledger,
        broker_factory=lambda broker: fake,
        clock=lambda: NOW + timedelta(seconds=10),
    )
    plan = planner.build("cancel-unconfirmed-plan")
    plan_ledger = ControlPlaneCleanupPlanLedger(
        ledger, clock=lambda: NOW + timedelta(seconds=11)
    )
    plan_ledger.record_plan(plan)
    reads_after_plan = list(fake.read_calls)

    processor = _processor(settings, ledger, service, plan_ledger, fake)
    with pytest.raises(ControlPlaneCleanupProcessorBlocked):
        processor.process("cancel-unconfirmed-plan")
    assert fake.read_calls == reads_after_plan
    assert fake.write_calls == []
    assert ledger.get("cancel-unconfirmed-plan").state == ControlPlaneActionState.AUTHORIZED
