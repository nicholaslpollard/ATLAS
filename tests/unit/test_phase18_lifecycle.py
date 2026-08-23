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
from packages.execution.phase18_lifecycle import (
    Phase18LifecycleError,
    run_phase18_cancelable_paper_lifecycle,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderPlan,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    BrokerPreflightResult,
    ExecutionEnvironment,
    ExecutionIntent,
)


NOW = datetime(2026, 8, 23, 15, 0, tzinfo=UTC)


class FakePendingPaperBroker(BrokerAdapter):
    broker = BrokerName.WEBULL
    environment = ExecutionEnvironment.PAPER

    def __init__(
        self,
        *,
        submit_status: BrokerOrderStatus = BrokerOrderStatus.SUBMITTED,
        uncertain_submit: bool = False,
        uncertain_cancel: bool = False,
        existing_position: bool = False,
    ) -> None:
        self.account_id = "fake-webull-paper"
        self.submit_status = submit_status
        self.uncertain_submit = uncertain_submit
        self.uncertain_cancel = uncertain_cancel
        self.submit_calls = 0
        self.cancel_calls = 0
        self._orders: dict[str, BrokerOrderSnapshot] = {}
        self._positions: dict[str, BrokerPositionSnapshot] = {}
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
        return BrokerPreflightResult(
            broker=self.broker,
            intent_id=plan.intent_id,
            accepted=True,
            as_of_utc=NOW,
            estimated_cost=plan.limit_price * plan.quantity,
            estimated_fees=0.0,
            provider_code="FAKE_ACCEPT",
            provider_message="fake paper preflight",
            reason_codes=("FAKE_PREFLIGHT_ACCEPTED",),
        )

    def submit(self, plan: BrokerOrderPlan) -> BrokerOrderSnapshot:
        self.submit_calls += 1
        if self.uncertain_submit:
            raise BrokerSubmissionUncertain("fake uncertain submit")
        filled = 0.0
        average = None
        if self.submit_status == BrokerOrderStatus.FILLED:
            filled = float(plan.quantity)
            average = plan.limit_price
        elif self.submit_status == BrokerOrderStatus.PARTIAL_FILLED:
            filled = 0.5
            average = plan.limit_price
        row = BrokerOrderSnapshot(
            broker=self.broker,
            account_id=self.account_id,
            client_order_id=plan.client_order_id,
            provider_order_id="provider-" + plan.client_order_id,
            ticker=plan.ticker,
            side=plan.side,
            status=self.submit_status,
            requested_quantity=float(plan.quantity),
            filled_quantity=filled,
            average_fill_price=average,
            submitted_at_utc=NOW,
            updated_at_utc=NOW,
            raw_status=self.submit_status.value,
        )
        self._orders[plan.client_order_id] = row
        if filled > 0:
            self._positions[plan.ticker] = BrokerPositionSnapshot(
                broker=self.broker,
                account_id=self.account_id,
                ticker=plan.ticker,
                quantity=filled if plan.side == BrokerOrderSide.BUY else -filled,
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
            raise BrokerMutationUncertain("fake uncertain cancel")
        current = self.order(client_order_id)
        cancelled = current.model_copy(
            update={"status": BrokerOrderStatus.CANCELLED, "updated_at_utc": NOW}
        )
        self._orders[client_order_id] = cancelled
        return cancelled


def _intent() -> ExecutionIntent:
    return ExecutionIntent(
        intent_id="phase18-test-intent-0001",
        instrument_id="ins-test-aapl",
        ticker="AAPL",
        as_of_date=date(2026, 8, 23),
        direction=DiscoveryDirection.BULLISH,
        environment=ExecutionEnvironment.PAPER,
        broker=BrokerName.WEBULL,
        phase13_case_sha256="1" * 64,
        phase14_acceptance_sha256="2" * 64,
        reference_entry=100.0,
        entry_limit=100.0,
        stop=95.0,
        target=110.0,
        original_risk_per_share=5.0,
        executable_risk_per_share=5.0,
        executable_reward_per_share=10.0,
        adverse_entry_drift_r=0.0,
        executable_reward_to_risk=2.0,
        accepted_risk_budget=500.0,
        accepted_proposed_quantity=1,
        executable_quantity=1,
        quote_bid=99.9,
        quote_ask=100.0,
        quote_provider_timestamp_utc=NOW,
        quote_received_at_utc=NOW,
        quote_feed_mode="TEST",
        quote_expected_delay_seconds=0,
        quote_age_seconds=0.0,
        session_segment="regular",
        order_type="LIMIT",
        time_in_force="DAY",
        extended_hours=False,
        protective_stop_required=True,
        profit_target_required=True,
        broker_preflight_required=True,
        reconciliation_required=True,
        live_execution_enabled=False,
        reason_codes=("PHASE18_TEST",),
    )


def _authorization() -> Phase18MutationAuthorization:
    return Phase18MutationAuthorization(
        broker="webull",
        authorize_provider_mutation=True,
        confirmation_text=PHASE18_CONFIRMATION_TEXT,
    )


def test_phase18_pending_order_is_submitted_reconciled_cancelled_and_flat() -> None:
    adapter = FakePendingPaperBroker()
    result = run_phase18_cancelable_paper_lifecycle(
        _intent(), adapter, authorization=_authorization(), now_utc=NOW
    )
    assert result.disposition == "SUBMIT_RECONCILE_CANCEL_RECONCILE_COMPLETE"
    assert result.provider_write_count == 2
    assert result.cleanup_required is False
    assert result.cancellation is not None
    assert result.cancellation.status == BrokerOrderStatus.CANCELLED
    assert result.reconciliation_after.zero_open_orders is True
    assert result.reconciliation_after.zero_positions is True
    assert adapter.submit_calls == 1
    assert adapter.cancel_calls == 1


def test_phase18_filled_order_stops_without_automatic_flatten() -> None:
    adapter = FakePendingPaperBroker(submit_status=BrokerOrderStatus.FILLED)
    result = run_phase18_cancelable_paper_lifecycle(
        _intent(), adapter, authorization=_authorization(), now_utc=NOW
    )
    assert result.provider_write_count == 1
    assert result.cleanup_required is True
    assert result.cancellation is None
    assert result.disposition == "POSITION_OR_PARTIAL_FILL_REQUIRES_SEPARATE_EXPLICIT_CLEANUP"
    assert result.reconciliation_after.zero_positions is False
    assert adapter.cancel_calls == 0


def test_phase18_uncertain_submit_never_attempts_second_mutation() -> None:
    adapter = FakePendingPaperBroker(uncertain_submit=True)
    with pytest.raises(Phase18LifecycleError) as exc_info:
        run_phase18_cancelable_paper_lifecycle(
            _intent(), adapter, authorization=_authorization(), now_utc=NOW
        )
    exc = exc_info.value
    assert exc.stage == "submit"
    assert exc.provider_state_uncertain is True
    assert adapter.submit_calls == 1
    assert adapter.cancel_calls == 0


def test_phase18_uncertain_cancel_never_retries() -> None:
    adapter = FakePendingPaperBroker(uncertain_cancel=True)
    with pytest.raises(Phase18LifecycleError) as exc_info:
        run_phase18_cancelable_paper_lifecycle(
            _intent(), adapter, authorization=_authorization(), now_utc=NOW
        )
    exc = exc_info.value
    assert exc.stage == "cancel"
    assert exc.provider_state_uncertain is True
    assert adapter.submit_calls == 1
    assert adapter.cancel_calls == 1


def test_phase18_existing_exposure_blocks_first_mutation() -> None:
    adapter = FakePendingPaperBroker(existing_position=True)
    with pytest.raises(Phase18LifecycleError, match="requires a flat broker") as exc_info:
        run_phase18_cancelable_paper_lifecycle(
            _intent(), adapter, authorization=_authorization(), now_utc=NOW
        )
    assert exc_info.value.stage == "pre_reconciliation"
    assert adapter.submit_calls == 0
    assert adapter.cancel_calls == 0


def test_phase18_broker_authorization_must_match_intent_and_adapter() -> None:
    adapter = FakePendingPaperBroker()
    alpaca_auth = Phase18MutationAuthorization(
        broker="alpaca",
        authorize_provider_mutation=True,
        confirmation_text=PHASE18_CONFIRMATION_TEXT,
    )
    with pytest.raises(Phase18LifecycleError, match="must match"):
        run_phase18_cancelable_paper_lifecycle(
            _intent(), adapter, authorization=alpaca_auth, now_utc=NOW
        )
    assert adapter.submit_calls == 0
