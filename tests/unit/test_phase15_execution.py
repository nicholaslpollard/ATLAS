from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from packages.brokers.paper.broker import ShadowBroker
from packages.brokers.webull.broker import WebullSandboxBroker
from packages.core.enums import DataProvider, LiveFeedMode, SessionSegment
from packages.execution.broker_switch import authorize_broker_switch
from packages.execution.engine import ExecutionEngine
from packages.execution.fills import build_execution_outcome
from packages.execution.order_builder import (
    ExecutionIntentError,
    build_broker_order_plan,
    build_execution_intent,
)
from packages.execution.phase15_policy import (
    PHASE15_AUTOMATIC_BROKER_FAILOVER,
    PHASE15_LIVE_EXECUTION_ENABLED,
    PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R,
    PHASE15_MAX_QUOTE_AGE_SECONDS,
    PHASE15_PRIMARY_BROKER,
    PHASE15_SECONDARY_BROKER,
    phase15_policy_fingerprint,
)
from packages.execution.validator import reconcile_broker, revalidate_execution_risk
from packages.schemas.broker_switch import BrokerSwitchAuthorization
from packages.schemas.case_file import (
    EvidenceAvailability,
    GeometryStatus,
    InstrumentKind,
    InstrumentSelection,
    NewsContextSummary,
    Phase13CaseFile,
    PortfolioRiskAssessment,
    PortfolioRiskStatus,
    TradeGeometry,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.execution import (
    BrokerAccountSnapshot,
    BrokerName,
    BrokerOrderSide,
    BrokerOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    BrokerReconciliationSnapshot,
    ExecutionEnvironment,
    ExecutionExitReason,
)
from packages.schemas.execution_run import (
    ExecutionCaseDisposition,
    ExecutionCaseDispositionRecord,
)
from packages.schemas.live_market import LiveQuote


NOW = datetime(2026, 8, 24, 15, 0, 0, tzinfo=UTC)


def _case(direction: DiscoveryDirection = DiscoveryDirection.BULLISH) -> Phase13CaseFile:
    if direction == DiscoveryDirection.BULLISH:
        stop, target = 95.0, 110.0
    else:
        stop, target = 105.0, 90.0
    return Phase13CaseFile(
        instrument_id="figi-xyz",
        ticker="XYZ",
        as_of_date=date(2026, 8, 24),
        direction=direction,
        phase12_case_sha256="a" * 64,
        phase12_research_complete=True,
        market_state="BULL" if direction == DiscoveryDirection.BULLISH else "BEAR",
        ticker_state="UPTREND" if direction == DiscoveryDirection.BULLISH else "DOWNTREND",
        news_context=NewsContextSummary(
            availability=EvidenceAvailability.UNAVAILABLE,
            cutoff_utc=NOW,
            lookback_calendar_days=7,
            article_count=0,
            positive_count=0,
            neutral_count=0,
            negative_count=0,
            sentiment_score=None,
            reason_codes=("UNAVAILABLE_TEST_CONTEXT",),
        ),
        instrument_selection=InstrumentSelection(
            primary_kind=InstrumentKind.EQUITY,
            primary_ticker="XYZ",
            option_chain_availability=EvidenceAvailability.UNAVAILABLE,
            reason_codes=("EQUITY_PRIMARY",),
        ),
        geometry=TradeGeometry(
            status=GeometryStatus.AVAILABLE,
            direction=direction,
            horizon_sessions=3,
            reference_entry=100.0,
            stop=stop,
            target=target,
            risk_fraction=0.05,
            reward_fraction=0.10,
            reward_to_risk=2.0,
            natr_14=0.04,
            empirical_mae_p10=-0.04,
            empirical_mfe_p75=0.10,
            reference_only_not_fill=True,
            reason_codes=("EVIDENCE_BOUNDED_GEOMETRY",),
        ),
        portfolio_risk=PortfolioRiskAssessment(
            status=PortfolioRiskStatus.ADMISSIBLE,
            proposed_risk_budget=500.0,
            proposed_quantity=10,
            proposed_notional=1000.0,
            projected_single_name_fraction=0.01,
            projected_gross_fraction=0.01,
            max_abs_correlation=None,
            open_positions_before=0,
            proposed_quantity_is_order=False,
            reason_codes=("PORTFOLIO_RISK_ADMISSIBLE",),
        ),
        phase14_review_ready=True,
        reason_codes=("PHASE14_REVIEW_READY",),
    )


def _quote(
    *,
    ticker: str = "XYZ",
    bid: float = 99.95,
    ask: float = 100.05,
    age_seconds: float = 1.0,
    feed_mode: LiveFeedMode = LiveFeedMode.REALTIME,
    expected_delay_seconds: int = 0,
    session_segment: SessionSegment = SessionSegment.REGULAR,
) -> LiveQuote:
    stamp = NOW - timedelta(seconds=age_seconds)
    return LiveQuote(
        symbol=ticker,
        provider_timestamp_utc=stamp,
        session_date=NOW.date(),
        session_segment=session_segment,
        bid_price=bid,
        bid_size=10,
        ask_price=ask,
        ask_size=10,
        sequence=123,
        provider=DataProvider.MASSIVE,
        feed_mode=feed_mode,
        expected_delay_seconds=expected_delay_seconds,
        received_at_utc=stamp + timedelta(milliseconds=20),
    )


def _intent(
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
    *,
    quote: LiveQuote | None = None,
    environment: ExecutionEnvironment = ExecutionEnvironment.SHADOW,
    broker: BrokerName = BrokerName.SHADOW,
):
    return build_execution_intent(
        _case(direction),
        phase13_case_sha256="b" * 64,
        phase14_acceptance_sha256="c" * 64,
        quote=quote or _quote(),
        environment=environment,
        broker=broker,
        now_utc=NOW,
    )


def _reconciliation(
    broker: BrokerName,
    *,
    positions: tuple[BrokerPositionSnapshot, ...] = (),
    open_orders: tuple[BrokerOrderSnapshot, ...] = (),
) -> BrokerReconciliationSnapshot:
    environment = ExecutionEnvironment.PAPER if broker != BrokerName.SHADOW else ExecutionEnvironment.SHADOW
    account = BrokerAccountSnapshot(
        broker=broker,
        environment=environment,
        account_id=f"acct-{broker.value}",
        as_of_utc=NOW,
        equity=100_000.0,
        cash=100_000.0,
        buying_power=100_000.0,
        gross_market_value=sum(abs(item.market_value) for item in positions),
        trading_blocked=False,
        shorting_enabled=True,
    )
    return BrokerReconciliationSnapshot(
        broker=broker,
        environment=environment,
        account=account,
        open_orders=open_orders,
        positions=positions,
        as_of_utc=NOW,
        reconciled=True,
        zero_open_orders=not open_orders,
        zero_positions=not positions,
        safe_to_switch_broker=not open_orders and not positions,
        reason_codes=("TEST_RECONCILIATION",),
    )


def _filled(
    intent,
    *,
    side: BrokerOrderSide,
    price: float,
    client_id: str,
    when: datetime,
) -> BrokerOrderSnapshot:
    return BrokerOrderSnapshot(
        broker=intent.broker,
        account_id="acct",
        client_order_id=client_id,
        provider_order_id="provider-" + client_id,
        ticker=intent.ticker,
        side=side,
        status=BrokerOrderStatus.FILLED,
        requested_quantity=float(intent.executable_quantity),
        filled_quantity=float(intent.executable_quantity),
        average_fill_price=price,
        submitted_at_utc=when,
        updated_at_utc=when,
        raw_status="FILLED",
    )


def test_phase15_policy_freezes_paper_only_primary_secondary_and_no_failover() -> None:
    assert PHASE15_PRIMARY_BROKER == "webull"
    assert PHASE15_SECONDARY_BROKER == "alpaca"
    assert PHASE15_LIVE_EXECUTION_ENABLED is False
    assert PHASE15_AUTOMATIC_BROKER_FAILOVER is False
    assert PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R == 0.25
    assert PHASE15_MAX_QUOTE_AGE_SECONDS == 30
    assert len(phase15_policy_fingerprint()) == 64


def test_long_execution_intent_uses_ask_and_preserves_stop_target() -> None:
    intent = _intent()
    assert intent.entry_limit == pytest.approx(100.05)
    assert intent.stop == 95.0
    assert intent.target == 110.0
    assert intent.executable_quantity == 10
    assert intent.executable_quantity <= intent.accepted_proposed_quantity
    assert intent.adverse_entry_drift_r == pytest.approx(0.01)
    assert intent.live_execution_enabled is False


def test_short_execution_intent_uses_bid_and_preserves_geometry() -> None:
    intent = _intent(
        DiscoveryDirection.BEARISH,
        quote=_quote(bid=99.95, ask=100.05),
    )
    assert intent.entry_limit == pytest.approx(99.95)
    assert intent.stop == 105.0
    assert intent.target == 90.0
    assert intent.executable_quantity == 10


def test_quarter_r_adverse_entry_boundary_is_allowed_but_more_is_blocked() -> None:
    boundary = _intent(quote=_quote(bid=101.20, ask=101.25))
    assert boundary.adverse_entry_drift_r == pytest.approx(0.25)
    with pytest.raises(ExecutionIntentError):
        _intent(quote=_quote(bid=101.21, ask=101.26))


def test_stale_delayed_wrong_symbol_and_nonregular_quotes_fail_closed() -> None:
    with pytest.raises(ExecutionIntentError):
        _intent(quote=_quote(age_seconds=31.0))
    with pytest.raises(ExecutionIntentError):
        _intent(quote=_quote(feed_mode=LiveFeedMode.DELAYED, expected_delay_seconds=900))
    with pytest.raises(ExecutionIntentError):
        _intent(quote=_quote(ticker="xyz"))
    with pytest.raises(ExecutionIntentError):
        _intent(quote=_quote(session_segment=SessionSegment.PREMARKET))


def test_live_environment_cannot_be_constructed() -> None:
    with pytest.raises(ExecutionIntentError):
        _intent(environment=ExecutionEnvironment.LIVE, broker=BrokerName.WEBULL)


def test_order_plan_has_cross_broker_32_character_id_and_protective_bracket() -> None:
    plan = build_broker_order_plan(_intent())
    assert len(plan.client_order_id) == 32
    assert plan.side == BrokerOrderSide.BUY
    assert plan.limit_price == pytest.approx(100.05)
    assert plan.stop_price == 95.0
    assert plan.target_price == 110.0
    assert plan.bracket_required is True


def test_shadow_execution_is_external_write_free_and_idempotent() -> None:
    broker = ShadowBroker()
    intent = _intent()
    first = ExecutionEngine().attempt(intent, broker, now_utc=NOW)
    assert first.order_snapshot.status == BrokerOrderStatus.SHADOW_FILLED
    assert first.provider_submission_performed is False
    assert first.broker_write_count == 0
    assert first.order_write_count == 0
    second = ExecutionEngine().attempt(intent, broker, now_utc=NOW + timedelta(seconds=1))
    assert second.existing_order_reused is True
    assert second.provider_submission_performed is False
    assert second.risk_revalidation.new_submission_evaluated is False
    assert second.broker_write_count == 0


def test_current_positions_require_fresh_correlation_for_a_new_submission() -> None:
    intent = _intent()
    position = BrokerPositionSnapshot(
        broker=BrokerName.SHADOW,
        account_id="acct-shadow",
        ticker="ABC",
        quantity=5,
        market_value=500.0,
        average_entry_price=100.0,
        as_of_utc=NOW,
    )
    rec = _reconciliation(BrokerName.SHADOW, positions=(position,))
    with pytest.raises(Exception):
        revalidate_execution_risk(intent, rec, now_utc=NOW)
    accepted = revalidate_execution_risk(
        intent, rec, max_abs_correlation=0.30, now_utc=NOW
    )
    assert accepted.admissible is True


def test_existing_same_ticker_blocks_new_add_or_flip_entry() -> None:
    intent = _intent()
    position = BrokerPositionSnapshot(
        broker=BrokerName.SHADOW,
        account_id="acct-shadow",
        ticker="XYZ",
        quantity=5,
        market_value=500.0,
        average_entry_price=100.0,
        as_of_utc=NOW,
    )
    rec = _reconciliation(BrokerName.SHADOW, positions=(position,))
    result = revalidate_execution_risk(
        intent, rec, max_abs_correlation=0.20, now_utc=NOW
    )
    assert result.admissible is False
    assert "SAME_TICKER_FAIL" in result.reason_codes


def test_broker_switch_requires_explicit_request_and_both_brokers_flat() -> None:
    current = _reconciliation(BrokerName.WEBULL)
    target = _reconciliation(BrokerName.ALPACA)
    denied = authorize_broker_switch(current, target, explicit_request=False, now_utc=NOW)
    assert denied.authorized is False
    allowed = authorize_broker_switch(current, target, explicit_request=True, now_utc=NOW)
    assert isinstance(allowed, BrokerSwitchAuthorization)
    assert allowed.authorized is True


def test_broker_switch_is_blocked_when_current_or_target_has_exposure() -> None:
    position = BrokerPositionSnapshot(
        broker=BrokerName.WEBULL,
        account_id="acct-webull",
        ticker="ABC",
        quantity=1,
        market_value=100.0,
        average_entry_price=100.0,
        as_of_utc=NOW,
    )
    current = _reconciliation(BrokerName.WEBULL, positions=(position,))
    target = _reconciliation(BrokerName.ALPACA)
    result = authorize_broker_switch(current, target, explicit_request=True, now_utc=NOW)
    assert result.authorized is False


def test_long_and_short_outcomes_are_direction_adjusted_and_descriptive_only() -> None:
    long_intent = _intent()
    long_entry = _filled(long_intent, side=BrokerOrderSide.BUY, price=100.0, client_id="entrylong", when=NOW)
    long_exit = _filled(long_intent, side=BrokerOrderSide.SELL, price=105.0, client_id="exitlong1", when=NOW + timedelta(days=1))
    long_outcome = build_execution_outcome(
        long_intent,
        entry_order=long_entry,
        exit_order=long_exit,
        exit_reason=ExecutionExitReason.TARGET,
    )
    assert long_outcome.gross_pnl == pytest.approx(50.0)
    assert long_outcome.realized_r > 0
    assert long_outcome.descriptive_only is True
    assert long_outcome.can_promote_model is False

    short_intent = _intent(DiscoveryDirection.BEARISH)
    short_entry = _filled(short_intent, side=BrokerOrderSide.SHORT, price=100.0, client_id="entryshr", when=NOW)
    short_exit = _filled(short_intent, side=BrokerOrderSide.BUY_TO_COVER, price=95.0, client_id="exitshrt", when=NOW + timedelta(days=1))
    short_outcome = build_execution_outcome(
        short_intent,
        entry_order=short_entry,
        exit_order=short_exit,
        exit_reason=ExecutionExitReason.TARGET,
    )
    assert short_outcome.gross_pnl == pytest.approx(50.0)
    assert short_outcome.gross_return == pytest.approx(0.05)
    assert short_outcome.can_change_strategy_support is False


def test_provider_uncertain_disposition_cannot_guess_write_count() -> None:
    with pytest.raises(ValidationError):
        ExecutionCaseDispositionRecord(
            instrument_id="figi-xyz",
            ticker="XYZ",
            as_of_date=NOW.date(),
            phase13_case_sha256="a" * 64,
            environment=ExecutionEnvironment.PAPER,
            broker=BrokerName.WEBULL,
            disposition=ExecutionCaseDisposition.PROVIDER_UNCERTAIN,
            intent_path="intent.json",
            intent_sha256="b" * 64,
            quote_read=True,
            broker_initialized=True,
            provider_submission_attempted=True,
            provider_submission_uncertain=True,
            broker_write_count=0,
            order_write_count=0,
            live_write_count=0,
            reason_codes=("UNCERTAIN",),
        )
    valid = ExecutionCaseDispositionRecord(
        instrument_id="figi-xyz",
        ticker="XYZ",
        as_of_date=NOW.date(),
        phase13_case_sha256="a" * 64,
        environment=ExecutionEnvironment.PAPER,
        broker=BrokerName.WEBULL,
        disposition=ExecutionCaseDisposition.PROVIDER_UNCERTAIN,
        intent_path="intent.json",
        intent_sha256="b" * 64,
        quote_read=True,
        broker_initialized=True,
        provider_submission_attempted=True,
        provider_submission_uncertain=True,
        broker_write_count=None,
        order_write_count=None,
        live_write_count=0,
        reason_codes=("UNCERTAIN",),
    )
    assert valid.broker_write_count is None


def test_webull_combo_ids_fit_provider_limit_and_include_protective_legs() -> None:
    broker = WebullSandboxBroker(account_id="sandbox-account", trade_client=object())
    orders = broker._provider_orders(build_broker_order_plan(_intent()))
    assert [item["combo_type"] for item in orders] == ["MASTER", "STOP_PROFIT", "STOP_LOSS"]
    assert all(len(item["client_order_id"]) <= 32 for item in orders)
    assert orders[0]["side"] == "BUY"
    assert orders[1]["side"] == "SELL"
    assert orders[2]["side"] == "SELL"


def test_reconciliation_marks_broker_switch_safe_only_when_flat() -> None:
    broker = ShadowBroker()
    flat = reconcile_broker(broker, now_utc=NOW)
    assert flat.safe_to_switch_broker is True
    ExecutionEngine().attempt(_intent(), broker, now_utc=NOW)
    exposed = reconcile_broker(broker, now_utc=NOW + timedelta(seconds=1))
    assert exposed.safe_to_switch_broker is False
