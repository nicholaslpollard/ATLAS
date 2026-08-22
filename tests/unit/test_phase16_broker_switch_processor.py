from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.broker_switch_processor import Phase16BrokerSwitchProcessor
from packages.control_plane.runtime_state import ControlPlaneRuntimeStateStore
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
from packages.schemas.control_plane_runtime import ControlPlaneRuntimeState
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    ExecutionEnvironment,
)


NOW = datetime(2026, 8, 22, 22, 0, tzinfo=UTC)


class FakeSwitchBroker:
    environment = ExecutionEnvironment.PAPER

    def __init__(self, broker: BrokerName, *, orders: bool = False, positions: bool = False) -> None:
        self.broker = broker
        self.has_orders = orders
        self.has_positions = positions
        self.account_id = f"{broker.value}-acct-secret"
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
            cash=25000.0,
            buying_power=50000.0,
            gross_market_value=1000.0 if self.has_positions else 0.0,
            trading_blocked=False,
            shorting_enabled=True,
        )

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        self.read_calls.append("open_orders")
        if not self.has_orders:
            return ()
        return (
            BrokerOrderSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                client_order_id=f"{self.broker.value}-order-1",
                provider_order_id=f"{self.broker.value}-provider-secret",
                ticker="SPY",
                side=BrokerOrderSide.BUY,
                status=BrokerOrderStatus.SUBMITTED,
                requested_quantity=1.0,
                filled_quantity=0.0,
                submitted_at_utc=NOW,
                updated_at_utc=NOW,
            ),
        )

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        self.read_calls.append("positions")
        if not self.has_positions:
            return ()
        return (
            BrokerPositionSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                ticker="QQQ",
                quantity=1.0,
                market_value=1000.0,
                average_entry_price=500.0,
                as_of_utc=NOW,
            ),
        )

    def preview(self, plan):
        self.write_calls.append("preview")
        raise AssertionError("broker switch must never preview")

    def submit(self, plan):
        self.write_calls.append("submit")
        raise AssertionError("broker switch must never submit")

    def order(self, client_order_id):
        self.write_calls.append("order")
        raise AssertionError("broker switch must never query an individual order")

    def cancel(self, client_order_id):
        self.write_calls.append("cancel")
        raise AssertionError("broker switch must never cancel")


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


def _authorized_switch(ledger: ControlPlaneActionLedger, target: BrokerName, *, suffix: str = "1"):
    request = ControlPlaneActionRequest(
        action_id=f"switch-{suffix}",
        action_kind=ControlPlaneActionKind.BROKER_SWITCH,
        requested_at_utc=NOW,
        idempotency_key=f"switch-idem-{suffix}",
        target_broker=target,
        environment=ExecutionEnvironment.PAPER,
        reason="manual provider selection",
    )
    ledger.create_request(request)
    grant = ControlPlaneConfirmationGrant(
        grant_id=f"grant-{suffix}",
        action_id=request.action_id,
        action_fingerprint=request.authority_fingerprint(),
        scope=ControlPlaneConfirmationScope.BROKER_SWITCH,
        confirmed_at_utc=NOW + timedelta(seconds=1),
    )
    return ledger.confirm(request.action_id, grant)


def _processor(tmp_path, brokers, *, env=None):
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    clock = lambda: NOW + timedelta(seconds=10)
    ledger = ControlPlaneActionLedger(settings, clock=clock)
    runtime = ControlPlaneRuntimeStateStore(settings, clock=clock)
    status = Phase16StatusService(
        settings,
        env=env
        or {
            "WEBULL_APP_KEY": "wk",
            "WEBULL_APP_SECRET": "ws",
            "ALPACA_PAPER_API_KEY": "ak",
            "ALPACA_PAPER_API_SECRET": "as",
        },
        clock=clock,
        runtime_store=runtime,
    )
    processor = Phase16BrokerSwitchProcessor(
        settings,
        status_service=status,
        ledger=ledger,
        runtime_store=runtime,
        broker_factory=lambda broker: brokers[broker],
        clock=clock,
    )
    return processor, ledger, runtime


def test_initial_provider_selection_requires_both_brokers_flat_and_writes_only_runtime(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeSwitchBroker(BrokerName.WEBULL),
        BrokerName.ALPACA: FakeSwitchBroker(BrokerName.ALPACA),
    }
    processor, ledger, runtime = _processor(tmp_path, brokers)
    authorized = _authorized_switch(ledger, BrokerName.ALPACA)
    assert authorized.state == ControlPlaneActionState.AUTHORIZED

    completed = processor.process(authorized.request.action_id)
    assert completed.state == ControlPlaneActionState.COMPLETED
    assert completed.provider_write_attempted is False
    assert completed.provider_write_uncertain is False
    state = runtime.load()
    assert state.revision == 1
    assert state.selected_broker == BrokerName.ALPACA
    assert state.selected_environment == ExecutionEnvironment.PAPER
    assert state.last_transition_action_id == authorized.request.action_id
    assert state.last_transition_audit_hash is not None
    assert all(broker.write_calls == [] for broker in brokers.values())
    assert brokers[BrokerName.WEBULL].read_calls == ["account", "open_orders", "positions"]
    assert brokers[BrokerName.ALPACA].read_calls == ["account", "open_orders", "positions"]
    verification = ledger.verify()
    assert verification["active_action_count"] == 0
    assert verification["uncertain_action_count"] == 0


def test_exposure_on_either_broker_blocks_switch_without_cleanup_or_runtime_write(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeSwitchBroker(BrokerName.WEBULL, positions=True),
        BrokerName.ALPACA: FakeSwitchBroker(BrokerName.ALPACA),
    }
    processor, ledger, runtime = _processor(tmp_path, brokers)
    authorized = _authorized_switch(ledger, BrokerName.ALPACA)
    blocked = processor.process(authorized.request.action_id)
    assert blocked.state == ControlPlaneActionState.BLOCKED
    assert blocked.error_code == "BROKER_SWITCH_NOT_AUTHORIZED"
    assert blocked.provider_write_attempted is False
    assert runtime.load().source == "synthetic_default"
    assert not runtime.state_path.exists()
    assert all(broker.write_calls == [] for broker in brokers.values())


def test_missing_other_broker_credentials_blocks_before_adapter_creation(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeSwitchBroker(BrokerName.WEBULL),
        BrokerName.ALPACA: FakeSwitchBroker(BrokerName.ALPACA),
    }
    processor, ledger, runtime = _processor(
        tmp_path,
        brokers,
        env={"ALPACA_PAPER_API_KEY": "ak", "ALPACA_PAPER_API_SECRET": "as"},
    )
    authorized = _authorized_switch(ledger, BrokerName.ALPACA)
    blocked = processor.process(authorized.request.action_id)
    assert blocked.state == ControlPlaneActionState.BLOCKED
    assert blocked.error_code == "BROKER_RECONCILIATION_FAILED"
    assert all(broker.read_calls == [] for broker in brokers.values())
    assert all(broker.write_calls == [] for broker in brokers.values())
    assert not runtime.state_path.exists()


def test_restart_after_runtime_persist_completes_without_repeating_broker_reads(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeSwitchBroker(BrokerName.WEBULL),
        BrokerName.ALPACA: FakeSwitchBroker(BrokerName.ALPACA),
    }
    processor, ledger, runtime = _processor(tmp_path, brokers)
    authorized = _authorized_switch(ledger, BrokerName.WEBULL)
    executing = ledger.transition(
        authorized.request.action_id,
        ControlPlaneActionState.EXECUTING,
        event_details={"test_recovery_setup": True},
    )
    event = ledger.append_runtime_transition_intent(
        executing.request.action_id,
        prior_revision=0,
        next_revision=1,
        selected_broker=BrokerName.WEBULL.value,
        selected_environment=ExecutionEnvironment.PAPER.value,
    )
    saved = ControlPlaneRuntimeState(
        revision=1,
        updated_at_utc=NOW + timedelta(seconds=10),
        selected_broker=BrokerName.WEBULL,
        selected_environment=ExecutionEnvironment.PAPER,
        provider_write_uncertain=False,
        last_transition_action_id=executing.request.action_id,
        last_transition_audit_hash=event.event_hash,
        source="persisted",
    )
    runtime.persist_transition(saved, expected_prior_revision=0)

    completed = processor.process(executing.request.action_id)
    assert completed.state == ControlPlaneActionState.COMPLETED
    assert completed.provider_write_attempted is False
    assert all(broker.read_calls == [] for broker in brokers.values())
    assert all(broker.write_calls == [] for broker in brokers.values())


def test_new_request_to_already_selected_target_is_blocked(tmp_path) -> None:
    brokers = {
        BrokerName.WEBULL: FakeSwitchBroker(BrokerName.WEBULL),
        BrokerName.ALPACA: FakeSwitchBroker(BrokerName.ALPACA),
    }
    processor, ledger, runtime = _processor(tmp_path, brokers)
    first = _authorized_switch(ledger, BrokerName.ALPACA, suffix="first")
    assert processor.process(first.request.action_id).state == ControlPlaneActionState.COMPLETED

    second = _authorized_switch(ledger, BrokerName.ALPACA, suffix="second")
    blocked = processor.process(second.request.action_id)
    assert blocked.state == ControlPlaneActionState.BLOCKED
    assert blocked.error_code == "TARGET_BROKER_ALREADY_SELECTED"
    assert runtime.load().revision == 1
    assert all(broker.write_calls == [] for broker in brokers.values())
