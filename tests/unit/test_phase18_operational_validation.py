from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from packages.brokers.base import (
    BrokerAdapter,
    BrokerMutationUncertain,
    BrokerOrderNotFound,
    BrokerSubmissionUncertain,
)
from packages.control_plane.phase18_authorization import Phase18MutationAuthorization
from packages.control_plane.phase18_policy import PHASE18_CONFIRMATION_TEXT
from packages.core.enums import DataProvider, LiveFeedMode, SessionSegment
from packages.execution.phase18_operational_validation import (
    PHASE18_MAX_VALIDATION_NOTIONAL,
    PHASE18_VALIDATION_QUANTITY,
    Phase18OperationalValidationError,
    build_phase18_operational_validation_plan,
    run_phase18_operational_validation_lifecycle,
)
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    BrokerPreflightResult,
    ExecutionEnvironment,
)
from packages.schemas.live_market import LiveQuote


NOW = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)


def _quote(*, bid: float = 100.0, ask: float = 100.1, delay: int = 0) -> LiveQuote:
    return LiveQuote(
        symbol="AAPL",
        provider_timestamp_utc=NOW,
        session_date=date(2026, 8, 24),
        session_segment=SessionSegment.REGULAR,
        bid_price=bid,
        bid_size=100,
        ask_price=ask,
        ask_size=100,
        sequence=1,
        provider=DataProvider.MASSIVE,
        feed_mode=LiveFeedMode.REALTIME,
        expected_delay_seconds=delay,
        received_at_utc=NOW,
    )


def _authorization(broker: str = "webull") -> Phase18MutationAuthorization:
    return Phase18MutationAuthorization(
        broker=broker,
        authorize_provider_mutation=True,
        confirmation_text=PHASE18_CONFIRMATION_TEXT,
    )


class FakeOperationalBroker(BrokerAdapter):
    broker = BrokerName.WEBULL
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        *,
        preflight_accepted: bool = True,
        submit_status: BrokerOrderStatus = BrokerOrderStatus.SUBMITTED,
        uncertain_submit: bool = False,
        uncertain_cancel: bool = False,
        existing_client_order_id: str | None = None,
        existing_position: bool = False,
    ) -> None:
        self.account_id = "fake-phase18-operational"
        self.preflight_accepted = preflight_accepted
        self.submit_status = submit_status
        self.uncertain_submit = uncertain_submit
        self.uncertain_cancel = uncertain_cancel
        self.preview_calls = 0
        self.submit_calls = 0
        self.cancel_calls = 0
        self._orders: dict[str, BrokerOrderSnapshot] = {}
        self._positions: dict[str, BrokerPositionSnapshot] = {}
        if existing_client_order_id is not None:
            self._orders[existing_client_order_id] = self._order(
                existing_client_order_id,
                status=BrokerOrderStatus.CANCELLED,
                quantity=1.0,
                filled=0.0,
                price=None,
            )
        if existing_position:
            self._positions["MSFT"] = BrokerPositionSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                ticker="MSFT",
                quantity=1.0,
                market_value=400.0,
                average_entry_price=400.0,
                as_of_utc=NOW,
            )

    def _order(
        self,
        client_order_id: str,
        *,
        status: BrokerOrderStatus,
        quantity: float,
        filled: float,
        price: float | None,
        ticker: str = "AAPL",
    ) -> BrokerOrderSnapshot:
        return BrokerOrderSnapshot(
            broker=self.broker,
            account_id=self.account_id,
            client_order_id=client_order_id,
            provider_order_id="fake-provider-" + client_order_id,
            ticker=ticker,
            side=build_phase18_operational_validation_plan(
                _quote(), broker=self.broker
            ).side,
            status=status,
            requested_quantity=quantity,
            filled_quantity=filled,
            average_fill_price=price,
            submitted_at_utc=NOW,
            updated_at_utc=NOW,
            raw_status=status.value,
        )

    def account(self) -> BrokerAccountSnapshot:
        gross = sum(abs(row.market_value) for row in self._positions.values())
        return BrokerAccountSnapshot(
            broker=self.broker,
            environment=self.environment,
            account_id=self.account_id,
            as_of_utc=NOW,
            equity=100_000.0,
            cash=100_000.0,
            buying_power=200_000.0,
            gross_market_value=gross,
            trading_blocked=False,
            shorting_enabled=True,
        )

    def positions(self) -> tuple[BrokerPositionSnapshot, ...]:
        return tuple(self._positions.values())

    def open_orders(self) -> tuple[BrokerOrderSnapshot, ...]:
        return tuple(
            row
            for row in self._orders.values()
            if row.status in {BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.PARTIAL_FILLED}
        )

    def preview(self, plan: BrokerOrderPlan) -> BrokerPreflightResult:
        self.preview_calls += 1
        return BrokerPreflightResult(
            broker=self.broker,
            intent_id=plan.intent_id,
            accepted=self.preflight_accepted,
            as_of_utc=NOW,
            estimated_cost=plan.limit_price * plan.quantity,
            estimated_fees=0.0,
            provider_code="FAKE_ACCEPT" if self.preflight_accepted else "FAKE_REJECT",
            provider_message="fake operational validation preflight",
            reason_codes=("FAKE_OPERATIONAL_PREFLIGHT",),
        )

    def submit(self, plan: BrokerOrderPlan) -> BrokerOrderSnapshot:
        self.submit_calls += 1
        if self.uncertain_submit:
            raise BrokerSubmissionUncertain("fake uncertain operational submit")
        filled = 0.0
        fill_price = None
        if self.submit_status == BrokerOrderStatus.FILLED:
            filled = float(plan.quantity)
            fill_price = float(plan.limit_price)
        elif self.submit_status == BrokerOrderStatus.PARTIAL_FILLED:
            filled = 0.5
            fill_price = float(plan.limit_price)
        row = self._order(
            plan.client_order_id,
            status=self.submit_status,
            quantity=float(plan.quantity),
            filled=filled,
            price=fill_price,
            ticker=plan.ticker,
        )
        self._orders[plan.client_order_id] = row
        if filled > 0.0:
            self._positions[plan.ticker] = BrokerPositionSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                ticker=plan.ticker,
                quantity=filled,
                market_value=filled * plan.limit_price,
                average_entry_price=plan.limit_price,
                as_of_utc=NOW,
            )
        return row

    def order(self, client_order_id: str) -> BrokerOrderSnapshot:
        try:
            return self._orders[client_order_id]
        except KeyError as exc:
            raise BrokerOrderNotFound(client_order_id) from exc

    def cancel(self, client_order_id: str) -> BrokerOrderSnapshot:
        self.cancel_calls += 1
        if self.uncertain_cancel:
            raise BrokerMutationUncertain("fake uncertain operational cancel")
        current = self.order(client_order_id)
        cancelled = current.model_copy(
            update={"status": BrokerOrderStatus.CANCELLED, "updated_at_utc": NOW}
        )
        self._orders[client_order_id] = cancelled
        return cancelled


def test_operational_plan_is_one_share_nonmarketable_buy_with_valid_geometry() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    assert plan.quantity == PHASE18_VALIDATION_QUANTITY == 1
    assert plan.side.value == "BUY"
    assert plan.limit_price == 95.0
    assert plan.stop_price < plan.limit_price < plan.target_price
    assert plan.limit_price * plan.quantity <= PHASE18_MAX_VALIDATION_NOTIONAL
    assert plan.extended_hours is False
    assert plan.bracket_required is True


def test_operational_plan_identity_is_deterministic_for_exact_same_quote() -> None:
    first = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    second = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    assert first.intent_id == second.intent_id
    assert first.client_order_id == second.client_order_id


def test_operational_plan_identity_changes_by_broker() -> None:
    webull = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    alpaca = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.ALPACA)
    assert webull.client_order_id != alpaca.client_order_id


def test_operational_plan_rejects_delayed_quote() -> None:
    with pytest.raises(Phase18OperationalValidationError, match="undelayed quote"):
        build_phase18_operational_validation_plan(
            _quote(delay=900), broker=BrokerName.WEBULL
        )


def test_operational_plan_rejects_notional_over_safety_cap() -> None:
    with pytest.raises(Phase18OperationalValidationError, match="notional exceeds"):
        build_phase18_operational_validation_plan(
            _quote(bid=2_000.0, ask=2_001.0), broker=BrokerName.WEBULL
        )


def test_operational_lifecycle_submits_reconciles_cancels_and_returns_flat() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker()
    result = run_phase18_operational_validation_lifecycle(
        plan,
        adapter,
        authorization=_authorization(),
        now_utc=NOW,
    )
    assert result.disposition == "VALIDATION_SUBMIT_RECONCILE_CANCEL_RECONCILE_COMPLETE"
    assert result.provider_write_count == 2
    assert result.cleanup_required is False
    assert result.cancellation is not None
    assert result.cancellation.status == BrokerOrderStatus.CANCELLED
    assert result.reconciliation_after.zero_open_orders is True
    assert result.reconciliation_after.zero_positions is True
    assert adapter.preview_calls == 1
    assert adapter.submit_calls == 1
    assert adapter.cancel_calls == 1


def test_operational_lifecycle_preflight_rejection_performs_no_submit() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker(preflight_accepted=False)
    with pytest.raises(Phase18OperationalValidationError, match="preflight rejected") as exc_info:
        run_phase18_operational_validation_lifecycle(
            plan,
            adapter,
            authorization=_authorization(),
            now_utc=NOW,
        )
    assert exc_info.value.stage == "preflight"
    assert adapter.preview_calls == 1
    assert adapter.submit_calls == 0
    assert adapter.cancel_calls == 0


def test_operational_lifecycle_existing_client_id_blocks_new_write() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker(existing_client_order_id=plan.client_order_id)
    with pytest.raises(Phase18OperationalValidationError, match="already exists") as exc_info:
        run_phase18_operational_validation_lifecycle(
            plan,
            adapter,
            authorization=_authorization(),
            now_utc=NOW,
        )
    assert exc_info.value.stage == "idempotency_query"
    assert adapter.preview_calls == 0
    assert adapter.submit_calls == 0


def test_operational_lifecycle_filled_order_never_auto_flattens() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker(submit_status=BrokerOrderStatus.FILLED)
    result = run_phase18_operational_validation_lifecycle(
        plan,
        adapter,
        authorization=_authorization(),
        now_utc=NOW,
    )
    assert result.disposition == "VALIDATION_FILL_REQUIRES_SEPARATE_EXPLICIT_CLEANUP"
    assert result.provider_write_count == 1
    assert result.cleanup_required is True
    assert result.cancellation is None
    assert result.reconciliation_after.zero_positions is False
    assert adapter.cancel_calls == 0


def test_operational_lifecycle_uncertain_submit_never_attempts_cancel() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker(uncertain_submit=True)
    with pytest.raises(Phase18OperationalValidationError) as exc_info:
        run_phase18_operational_validation_lifecycle(
            plan,
            adapter,
            authorization=_authorization(),
            now_utc=NOW,
        )
    assert exc_info.value.stage == "submit"
    assert exc_info.value.provider_state_uncertain is True
    assert adapter.submit_calls == 1
    assert adapter.cancel_calls == 0


def test_operational_lifecycle_uncertain_cancel_never_retries() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker(uncertain_cancel=True)
    with pytest.raises(Phase18OperationalValidationError) as exc_info:
        run_phase18_operational_validation_lifecycle(
            plan,
            adapter,
            authorization=_authorization(),
            now_utc=NOW,
        )
    assert exc_info.value.stage == "cancel"
    assert exc_info.value.provider_state_uncertain is True
    assert adapter.submit_calls == 1
    assert adapter.cancel_calls == 1


def test_operational_lifecycle_existing_position_blocks_before_preflight() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker(existing_position=True)
    with pytest.raises(Phase18OperationalValidationError, match="requires a reconciled flat broker"):
        run_phase18_operational_validation_lifecycle(
            plan,
            adapter,
            authorization=_authorization(),
            now_utc=NOW,
        )
    assert adapter.preview_calls == 0
    assert adapter.submit_calls == 0


def test_operational_lifecycle_authorization_must_match_adapter() -> None:
    plan = build_phase18_operational_validation_plan(_quote(), broker=BrokerName.WEBULL)
    adapter = FakeOperationalBroker()
    with pytest.raises(Phase18OperationalValidationError, match="does not match adapter broker"):
        run_phase18_operational_validation_lifecycle(
            plan,
            adapter,
            authorization=_authorization("alpaca"),
            now_utc=NOW,
        )
    assert adapter.preview_calls == 0
    assert adapter.submit_calls == 0
