from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.cleanup_planner import (
    ControlPlaneCleanupPlannerBlocked,
    Phase16CleanupPlanner,
)
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneConfirmationGrant,
    ControlPlaneConfirmationScope,
)
from packages.schemas.control_plane_cleanup import (
    ControlPlaneCleanupPlan,
    ControlPlaneCleanupPlanConfirmationGrant,
    cleanup_plan_confirmation_matches,
)
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    ExecutionEnvironment,
)


NOW = datetime(2026, 8, 22, 23, 30, tzinfo=UTC)


class FakeCleanupBroker:
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        broker: BrokerName,
        *,
        open_orders: tuple[BrokerOrderSnapshot, ...] = (),
        positions: tuple[BrokerPositionSnapshot, ...] = (),
    ) -> None:
        self.broker = broker
        self.account_id = f"{broker.value}-cleanup-secret-account"
        self._orders = open_orders
        self._positions = positions
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
            gross_market_value=sum(abs(item.market_value) for item in self._positions),
            trading_blocked=False,
            shorting_enabled=True,
        )

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        self.read_calls.append("open_orders")
        return self._orders

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        self.read_calls.append("positions")
        return self._positions

    def preview(self, plan):
        self.write_calls.append("preview")
        raise AssertionError("cleanup planning cannot preview provider writes")

    def submit(self, plan):
        self.write_calls.append("submit")
        raise AssertionError("cleanup planning cannot submit")

    def order(self, client_order_id):
        self.write_calls.append("order")
        raise AssertionError("cleanup planning does not query individual orders")

    def cancel(self, client_order_id):
        self.write_calls.append("cancel")
        raise AssertionError("cleanup planning cannot cancel")


def _settings_with_derived(tmp_path):
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


def _action(
    ledger: ControlPlaneActionLedger,
    *,
    action_id: str,
    kind: ControlPlaneActionKind,
    broker: BrokerName,
    confirm: bool = True,
):
    request = ControlPlaneActionRequest(
        action_id=action_id,
        action_kind=kind,
        requested_at_utc=NOW,
        idempotency_key=f"idem-{action_id}",
        target_broker=broker,
        environment=ExecutionEnvironment.PAPER,
        reason="cleanup planner test",
    )
    record = ledger.create_request(request)
    if not confirm:
        return record
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


def _order(broker: BrokerName, account_id: str, client_id: str, ticker: str):
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


def _position(
    broker: BrokerName,
    account_id: str,
    ticker: str,
    quantity: float,
):
    return BrokerPositionSnapshot(
        broker=broker,
        account_id=account_id,
        ticker=ticker,
        quantity=quantity,
        market_value=quantity * 100.0,
        average_entry_price=95.0,
        as_of_utc=NOW,
    )


def _planner(tmp_path, fake: FakeCleanupBroker, ledger: ControlPlaneActionLedger):
    settings = _settings_with_derived(tmp_path)
    service = Phase16StatusService(
        settings,
        env=(
            {"WEBULL_APP_KEY": "wk", "WEBULL_APP_SECRET": "ws"}
            if fake.broker == BrokerName.WEBULL
            else {
                "ALPACA_PAPER_API_KEY": "ak",
                "ALPACA_PAPER_API_SECRET": "as",
            }
        ),
        clock=lambda: NOW + timedelta(seconds=10),
        action_ledger=ledger,
    )
    return Phase16CleanupPlanner(
        settings,
        status_service=service,
        ledger=ledger,
        broker_factory=lambda broker: fake,
        clock=lambda: NOW + timedelta(seconds=10),
    )


def test_cancel_plan_binds_exact_open_orders_and_contains_no_provider_authority(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=5))
    fake = FakeCleanupBroker(BrokerName.WEBULL)
    fake._orders = (
        _order(fake.broker, fake.account_id, "cancel-order-bbbbb", "QQQ"),
        _order(fake.broker, fake.account_id, "cancel-order-aaaaa", "SPY"),
    )
    record = _action(
        ledger,
        action_id="cancel-plan-1",
        kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
        broker=BrokerName.WEBULL,
    )
    plan = _planner(tmp_path, fake, ledger).build(record.request.action_id)

    assert [item.client_order_id for item in plan.cancel_targets] == [
        "cancel-order-bbbbb",
        "cancel-order-aaaaa",
    ]
    assert plan.zero_open_orders is False
    assert plan.no_op is False
    assert plan.provider_write_authorized is False
    assert plan.exact_plan_confirmation_required is True
    assert plan.scope_expansion_allowed is False
    assert len(plan.plan_fingerprint()) == 64
    assert fake.read_calls == ["account", "open_orders", "positions"]
    assert fake.write_calls == []
    encoded = plan.model_dump_json()
    assert fake.account_id not in encoded
    assert "provider-cancel" not in encoded

    grant = ControlPlaneCleanupPlanConfirmationGrant(
        grant_id="cleanup-plan-grant-1",
        action_id=plan.action_id,
        action_fingerprint=plan.action_fingerprint,
        cleanup_plan_fingerprint=plan.plan_fingerprint(),
        confirmed_at_utc=NOW + timedelta(seconds=20),
    )
    assert cleanup_plan_confirmation_matches(plan, grant) is True

    changed = plan.model_copy(
        update={
            "cancel_targets": plan.cancel_targets[:1],
            "zero_open_orders": False,
            "no_op": False,
        }
    )
    changed = ControlPlaneCleanupPlan.model_validate(changed.model_dump(mode="python"))
    assert cleanup_plan_confirmation_matches(changed, grant) is False


def test_flatten_planning_requires_separate_cancel_resolution_first(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=5))
    fake = FakeCleanupBroker(BrokerName.ALPACA)
    fake._orders = (
        _order(fake.broker, fake.account_id, "flatten-open-order", "SPY"),
    )
    fake._positions = (
        _position(fake.broker, fake.account_id, "SPY", 2.0),
    )
    record = _action(
        ledger,
        action_id="flatten-plan-blocked",
        kind=ControlPlaneActionKind.FLATTEN_POSITIONS,
        broker=BrokerName.ALPACA,
    )
    with pytest.raises(ControlPlaneCleanupPlannerBlocked, match="separate confirmed cancel"):
        _planner(tmp_path, fake, ledger).build(record.request.action_id)
    assert fake.read_calls == ["account", "open_orders", "positions"]
    assert fake.write_calls == []


def test_flatten_plan_captures_signed_positions_but_close_method_remains_unaccepted(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW + timedelta(seconds=5))
    fake = FakeCleanupBroker(BrokerName.ALPACA)
    fake._positions = (
        _position(fake.broker, fake.account_id, "TSLA", -3.0),
        _position(fake.broker, fake.account_id, "AAPL", 4.0),
    )
    record = _action(
        ledger,
        action_id="flatten-plan-review",
        kind=ControlPlaneActionKind.FLATTEN_POSITIONS,
        broker=BrokerName.ALPACA,
    )
    plan = _planner(tmp_path, fake, ledger).build(record.request.action_id)
    assert plan.zero_open_orders is True
    assert plan.zero_positions is False
    assert plan.no_op is False
    assert plan.provider_write_authorized is False
    assert plan.flatten_close_order_method_accepted is False
    assert [(item.ticker, item.quantity, item.required_close_side) for item in plan.flatten_targets] == [
        ("AAPL", 4.0, BrokerOrderSide.SELL),
        ("TSLA", -3.0, BrokerOrderSide.BUY_TO_COVER),
    ]
    assert fake.write_calls == []


def test_cleanup_plan_requires_original_action_confirmation_before_any_broker_read(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    ledger = ControlPlaneActionLedger(settings, clock=lambda: NOW)
    fake = FakeCleanupBroker(BrokerName.WEBULL)
    record = _action(
        ledger,
        action_id="cleanup-unconfirmed",
        kind=ControlPlaneActionKind.CANCEL_OPEN_ORDERS,
        broker=BrokerName.WEBULL,
        confirm=False,
    )
    with pytest.raises(ControlPlaneCleanupPlannerBlocked, match="explicitly confirmed"):
        _planner(tmp_path, fake, ledger).build(record.request.action_id)
    assert fake.read_calls == []
    assert fake.write_calls == []
