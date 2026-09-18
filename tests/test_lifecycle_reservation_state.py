from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from packages.execution.option_economics import (
    OptionEconomicsInputs,
    build_option_economic_candidate,
)
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    InstrumentKind,
    TradeExpressionMode,
)
from packages.schemas.case_file import OptionCandidateEvidence
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.closeout_account_state import (
    apply_closeout_exit_fill_v1,
    initialize_closeout_account_v1,
)
from packages.simulation.decision_record import build_simulation_decision_record
from packages.simulation.lifecycle_reservation_contract import (
    LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_reservation_state import (
    LifecycleReservationAccountError,
    LifecycleReservationEventKind,
    apply_lifecycle_decision_reservation_v1,
    apply_lifecycle_reservation_batch_v1,
    initialize_lifecycle_reservation_account_v1,
    replay_lifecycle_reservation_account_v1,
    verify_lifecycle_reservation_account_replay_v1,
)
from packages.simulation.open_position_state import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
    OpenPositionAccountStateV1,
    SimulatedOpenPositionV1,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.option_reservation import (
    LongOptionReservationInputs,
    build_long_option_reservation_terms,
)
from packages.simulation.simulated_exit_fill import (
    SimulatedExitFillInputs,
    build_simulated_exit_fill_evidence,
)


OPENED = datetime(2026, 9, 17, 14, 30, tzinfo=UTC)
SOURCE_AS_OF = datetime(2026, 9, 17, 14, 55, tzinfo=UTC)
CLOSED_AT = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)
DECISION_BASE = datetime(2026, 9, 17, 15, 10, tzinfo=UTC)
SOURCE_FP = "a" * 64
SCENARIO_FP = "b" * 64
EVENT_FP = "c" * 64


def _fp(char: str) -> str:
    return char * 64


def _existing_stock() -> SimulatedOpenPositionV1:
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=_fp("d"),
        decision_record_fingerprint=_fp("1"),
        candidate_fingerprint=_fp("2"),
        fill_fingerprint=_fp("3"),
        funding_terms_fingerprint=_fp("4"),
        reservation_fingerprint=_fp("5"),
        option_reservation_terms_fingerprint=None,
        option_economics_result_fingerprint=None,
        instrument_kind=InstrumentKind.STOCK,
        instrument_id="AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier="existing-stock-aapl",
        option_contract_ticker=None,
        option_contract_type=None,
        opened_utc=OPENED,
        quantity=10.0,
        quantity_unit="SHARES",
        entry_price_per_unit=10.0,
        contract_multiplier=1.0,
        entry_book_value_dollars=100.0,
        entry_fees_dollars=1.0,
        all_in_cash_cost_basis_dollars=101.0,
        original_reserved_capital_dollars=80.0,
        supplemental_cash_consumed_dollars=21.0,
        unspent_reserve_returned_dollars=0.0,
        stock_gross_entry_exposure_dollars=100.0,
        option_premium_at_risk_dollars=0.0,
        option_signed_delta_equivalent_entry_reference_dollars=0.0,
        option_abs_delta_equivalent_entry_reference_dollars=0.0,
        reason_codes=("EXISTING_STOCK",),
    )


def _existing_option() -> SimulatedOpenPositionV1:
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=_fp("d"),
        decision_record_fingerprint=_fp("6"),
        candidate_fingerprint=_fp("7"),
        fill_fingerprint=_fp("8"),
        funding_terms_fingerprint=_fp("9"),
        reservation_fingerprint=_fp("e"),
        option_reservation_terms_fingerprint=_fp("f"),
        option_economics_result_fingerprint=_fp("0"),
        instrument_kind=InstrumentKind.OPTION,
        instrument_id="AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier="existing-option-aapl",
        option_contract_ticker="AAPL261016C00100000",
        option_contract_type="call",
        opened_utc=OPENED,
        quantity=1.0,
        quantity_unit="CONTRACTS",
        entry_price_per_unit=2.0,
        contract_multiplier=100.0,
        entry_book_value_dollars=200.0,
        entry_fees_dollars=1.0,
        all_in_cash_cost_basis_dollars=201.0,
        original_reserved_capital_dollars=250.0,
        supplemental_cash_consumed_dollars=0.0,
        unspent_reserve_returned_dollars=49.0,
        stock_gross_entry_exposure_dollars=0.0,
        option_premium_at_risk_dollars=200.0,
        option_signed_delta_equivalent_entry_reference_dollars=120.0,
        option_abs_delta_equivalent_entry_reference_dollars=120.0,
        reason_codes=("EXISTING_OPTION",),
    )


def _source_open_account() -> OpenPositionAccountStateV1:
    stock = _existing_stock()
    option = _existing_option()
    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=_fp("d"),
        as_of_utc=SOURCE_AS_OF,
        initial_equity=20_000.0,
        source_stock_gross_notional=100.0,
        source_option_signed_delta_equivalent_notional=120.0,
        source_option_abs_delta_equivalent_notional=120.0,
        cash=19_698.0,
        entry_book_equity=19_998.0,
        cumulative_entry_fees_dollars=2.0,
        remaining_stock_reserved_capital=0.0,
        remaining_option_reserved_capital=0.0,
        remaining_stock_gross_notional=0.0,
        remaining_option_signed_delta_equivalent_notional=0.0,
        remaining_option_abs_delta_equivalent_notional=0.0,
        open_entry_book_value_dollars=300.0,
        open_stock_gross_entry_exposure_dollars=100.0,
        open_option_entry_book_value_dollars=200.0,
        open_option_signed_delta_equivalent_entry_reference_dollars=120.0,
        open_option_abs_delta_equivalent_entry_reference_dollars=120.0,
        open_option_premium_at_risk_dollars=200.0,
        remaining_stock_reservations=(),
        remaining_option_reservations=(),
        open_positions=(stock, option),
    )


def _post_close_source():
    source = _source_open_account()
    stock = source.open_positions[0]
    fill = build_simulated_exit_fill_evidence(
        source_state=source,
        position_fingerprint=stock.position_fingerprint,
        inputs=SimulatedExitFillInputs(
            fill_source_id="existing-stock-close",
            fill_source_fingerprint=_fp("a"),
            exited_utc=CLOSED_AT,
            exit_price_per_unit=11.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )
    transition = apply_closeout_exit_fill_v1(
        initialize_closeout_account_v1(source_state=source),
        fill=fill,
    )
    return transition.account


def _threshold() -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=0.01,
        favorable_touch_probability=0.45,
        adverse_touch_probability=0.25,
        favorable_before_adverse_probability=0.34,
        adverse_before_favorable_probability=0.13,
        same_interval_collision_probability=0.04,
        median_favorable_time=10.0,
    )


def _forecast(
    *,
    ticker: str,
    instrument_id: str,
    created_utc: datetime,
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
) -> UnderlyingMoveTimeForecast:
    bearish = direction == DiscoveryDirection.BEARISH
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=instrument_id,
        ticker=ticker,
        direction=direction,
        forecast_created_utc=created_utc,
        evidence_cutoff_utc=created_utc - timedelta(minutes=1),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=390,
        method_id="lifecycle-reentry-fixture",
        source_label="lifecycle reentry fixture",
        source_fingerprint=SOURCE_FP,
        sample_size=1_000,
        reference_price=100.0,
        mean_signed_return=-0.012 if bearish else 0.008,
        median_signed_return=-0.008 if bearish else 0.005,
        p10_signed_return=-0.045 if bearish else -0.020,
        p25_signed_return=-0.022 if bearish else -0.006,
        p75_signed_return=0.006 if bearish else 0.018,
        p90_signed_return=0.018 if bearish else 0.035,
        probability_positive_return=0.34 if bearish else 0.58,
        mean_mfe=0.030 if bearish else 0.022,
        mean_mae=0.012 if bearish else 0.009,
        thresholds=(_threshold(),),
        uncertainty_score=0.30,
        reason_codes=("FIXTURE",),
    )


def _option(
    *,
    contract_type: str = "call",
    delta: float = 0.55,
) -> OptionCandidateEvidence:
    return OptionCandidateEvidence(
        contract_ticker=(
            "O:XYZ261016C00100000"
            if contract_type == "call"
            else "O:XYZ261016P00100000"
        ),
        contract_type=contract_type,
        expiration_date=date(2026, 10, 16),
        dte=29,
        strike=100.0,
        bid=4.8,
        ask=5.2,
        mid=5.0,
        spread_to_mid=0.08,
        open_interest=1_000,
        volume=200,
        delta=delta,
        implied_volatility=0.30,
        eligible=True,
        reason_codes=("FIXTURE_OPTION",),
    )


def _option_inputs(forecast: UnderlyingMoveTimeForecast) -> OptionEconomicsInputs:
    return OptionEconomicsInputs(
        contracts=2,
        contract_multiplier=100.0,
        capital_required_dollars=1_050.0,
        holding_period_calendar_days=5.0,
        expected_terminal_premium_per_share=6.2,
        favorable_terminal_premium_per_share=8.0,
        adverse_terminal_premium_per_share=2.5,
        model_probability_profit=0.58,
        scenario_model_id="fixture-option-scenario-v1",
        scenario_model_fingerprint=SCENARIO_FP,
        scenario_forecast_fingerprint=forecast_fingerprint(forecast),
        gamma=0.04,
        theta_per_calendar_day=-0.08,
        vega_per_one_iv_fraction=12.0,
        iv_percentile=0.60,
        skew_signal=-0.10,
        term_structure_signal=0.05,
        risk_free_rate=0.04,
        dividend_yield=0.01,
        event_within_horizon=False,
        event_risk_acceptable=True,
        event_context_fingerprint=EVENT_FP,
        liquidity_score=0.90,
        exit_slippage_dollars=8.0,
        round_trip_commission_dollars=2.0,
        round_trip_fees_dollars=1.0,
        executable=True,
        risk_budget_ok=True,
        model_reference_premium_per_share=5.5,
    )


def _stock_inputs(
    *,
    capital: float = 5_000.0,
    notional: float = 10_000.0,
) -> StockEconomicsInputs:
    return StockEconomicsInputs(
        position_notional_dollars=notional,
        capital_required_dollars=capital,
        entry_slippage_bps=5.0,
        exit_slippage_bps=5.0,
        round_trip_commission_dollars=1.0,
        round_trip_fees_dollars=1.0,
        horizon_borrow_cost_dollars=0.0,
        horizon_financing_cost_dollars=2.0,
        net_probability_profit=0.50,
        liquidity_score=0.90,
        executable=True,
        risk_budget_ok=True,
        shortable_if_bearish=True,
    )


def _policy() -> ActionabilityPolicy:
    return ActionabilityPolicy(
        min_expected_net_value=0.0,
        min_expected_return_on_capital=0.0,
        min_probability_profit=0.0,
        max_expected_loss_to_gain_ratio=10.0,
        max_execution_cost_to_expected_gain_ratio=10.0,
        min_liquidity_score=0.0,
        material_superiority_ratio=1.0,
    )


def _stock_record(
    *,
    created_utc: datetime = DECISION_BASE,
    capital: float = 5_000.0,
):
    forecast = _forecast(
        ticker="ABC",
        instrument_id="iid-abc",
        created_utc=created_utc,
    )
    return build_simulation_decision_record(
        decision_created_utc=created_utc + timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=_stock_inputs(
            capital=capital,
            notional=max(10_000.0, capital * 2.0),
        ),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(),
    )


def _option_case(
    *,
    created_utc: datetime = DECISION_BASE + timedelta(minutes=2),
    fee_reserve: float = 3.0,
):
    forecast = _forecast(
        ticker="XYZ",
        instrument_id="iid-xyz",
        created_utc=created_utc,
    )
    option = _option()
    economics = build_option_economic_candidate(
        forecast=forecast,
        option=option,
        inputs=_option_inputs(forecast),
    )
    assert economics.candidate is not None
    record = build_simulation_decision_record(
        decision_created_utc=created_utc + timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.OPTIONS_ONLY,
        option_candidates=(economics.candidate,),
    )
    terms = build_long_option_reservation_terms(
        record=record,
        option_economics=economics,
        option=option,
        inputs=LongOptionReservationInputs(
            cash_fee_reserve_dollars=fee_reserve
        ),
    )
    return record, terms


def test_contract_fingerprint_is_frozen() -> None:
    assert (
        LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
        == "b4b825cca77a59f2d65064c9644d513714968f4ae7b8cea03f0738411d3459bb"
    )


def test_initialization_carries_post_close_history_and_survivor_exactly() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    state = account.state

    assert state.cash == pytest.approx(19_807.0)
    assert state.account_book_equity == pytest.approx(20_007.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(1.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)
    assert state.open_entry_book_value_dollars == pytest.approx(200.0)
    assert len(state.open_positions) == 1
    assert state.open_positions[0].candidate_identifier == "existing-option-aapl"
    assert len(state.closed_trades) == 1
    assert state.closed_trades[0].candidate_identifier == "existing-stock-aapl"
    assert state.stock_reservations == ()
    assert state.option_reservations == ()
    assert account.ledger.events == ()


def test_new_stock_reservation_uses_cash_without_changing_book_or_history() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    before_open = account.state.open_positions
    before_closed = account.state.closed_trades
    before_book = account.state.account_book_equity
    before_realized = account.state.cumulative_account_realized_pnl_dollars

    record = _stock_record()
    transition = apply_lifecycle_decision_reservation_v1(account, record)
    state = transition.account.state

    assert transition.event is not None
    assert transition.event.kind == LifecycleReservationEventKind.RESERVE_STOCK
    assert state.cash == pytest.approx(14_807.0)
    assert state.stock_reserved_capital == pytest.approx(5_000.0)
    assert state.stock_reserved_gross_notional == pytest.approx(10_000.0)
    assert state.account_book_equity == pytest.approx(before_book)
    assert (
        state.cash
        + state.stock_reserved_capital
        + state.option_reserved_capital
        + state.open_entry_book_value_dollars
        == pytest.approx(state.account_book_equity)
    )
    assert state.open_positions == before_open
    assert state.closed_trades == before_closed
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(before_realized)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)


def test_new_option_reservation_stays_separate_from_existing_open_option_reference() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    record, terms = _option_case()
    transition = apply_lifecycle_decision_reservation_v1(
        account,
        record,
        option_terms=terms,
    )
    state = transition.account.state

    assert transition.event is not None
    assert transition.event.kind == LifecycleReservationEventKind.RESERVE_OPTION
    assert state.option_reserved_capital == pytest.approx(1_043.0)
    assert state.option_reserved_max_loss_cash == pytest.approx(1_043.0)
    assert state.option_reserved_premium_at_risk == pytest.approx(1_040.0)
    assert state.option_reserved_signed_delta_equivalent_notional == pytest.approx(11_000.0)
    assert state.option_reserved_abs_delta_equivalent_notional == pytest.approx(11_000.0)

    assert state.open_option_entry_book_value_dollars == pytest.approx(200.0)
    assert state.open_option_signed_delta_equivalent_entry_reference_dollars == pytest.approx(120.0)
    assert state.open_option_abs_delta_equivalent_entry_reference_dollars == pytest.approx(120.0)
    assert state.open_option_premium_at_risk_dollars == pytest.approx(200.0)
    assert len(state.open_positions) == 1
    assert len(state.closed_trades) == 1


def test_mixed_new_reservations_share_only_current_cash() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    stock = _stock_record()
    option_record, terms = _option_case()

    after_stock = apply_lifecycle_decision_reservation_v1(
        account,
        stock,
    ).account
    after_option = apply_lifecycle_decision_reservation_v1(
        after_stock,
        option_record,
        option_terms=terms,
    ).account

    assert after_option.state.stock_reserved_capital == pytest.approx(5_000.0)
    assert after_option.state.option_reserved_capital == pytest.approx(1_043.0)
    assert after_option.state.cash == pytest.approx(13_764.0)
    assert after_option.state.open_entry_book_value_dollars == pytest.approx(200.0)
    assert after_option.state.account_book_equity == pytest.approx(20_007.0)
    assert (
        after_option.state.cash
        + after_option.state.stock_reserved_capital
        + after_option.state.option_reserved_capital
        + after_option.state.open_entry_book_value_dollars
        == pytest.approx(20_007.0)
    )


def test_missing_option_terms_is_ledgered_without_mutating_money_or_history() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    record, _terms = _option_case()
    transition = apply_lifecycle_decision_reservation_v1(account, record)

    assert transition.event is not None
    assert (
        transition.event.kind
        == LifecycleReservationEventKind.REJECT_MISSING_OPTION_TERMS
    )
    assert transition.account.state.cash == pytest.approx(account.state.cash)
    assert transition.account.state.account_book_equity == pytest.approx(
        account.state.account_book_equity
    )
    assert transition.account.state.open_positions == account.state.open_positions
    assert transition.account.state.closed_trades == account.state.closed_trades


def test_insufficient_current_cash_rejects_without_using_open_book_as_cash() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    record = _stock_record(capital=25_000.0)
    transition = apply_lifecycle_decision_reservation_v1(account, record)

    assert transition.event is not None
    assert (
        transition.event.kind
        == LifecycleReservationEventKind.REJECT_INSUFFICIENT_CAPITAL
    )
    assert transition.account.state.cash == pytest.approx(19_807.0)
    assert transition.account.state.stock_reserved_capital == 0.0
    assert transition.account.state.open_entry_book_value_dollars == pytest.approx(200.0)
    assert transition.account.state.account_book_equity == pytest.approx(20_007.0)


def test_duplicate_decision_is_idempotent_and_conflicting_option_terms_fail() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    record, terms = _option_case(fee_reserve=3.0)
    same_record, conflicting_terms = _option_case(fee_reserve=4.0)
    assert same_record.record_fingerprint == record.record_fingerprint

    first = apply_lifecycle_decision_reservation_v1(
        account,
        record,
        option_terms=terms,
    )
    duplicate = apply_lifecycle_decision_reservation_v1(
        first.account,
        record,
        option_terms=terms,
    )
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account

    with pytest.raises(
        LifecycleReservationAccountError,
        match="different reservation terms",
    ):
        apply_lifecycle_decision_reservation_v1(
            first.account,
            record,
            option_terms=conflicting_terms,
        )


def test_batch_order_is_deterministic_and_replay_is_exact() -> None:
    source = _post_close_source()
    stock = _stock_record()
    option_record, terms = _option_case()

    first = replay_lifecycle_reservation_account_v1(
        source=source,
        decisions=((option_record, terms), (stock, None)),
    )
    second = replay_lifecycle_reservation_account_v1(
        source=source,
        decisions=((stock, None), (option_record, terms)),
    )

    assert first.ordered_decision_fingerprints == second.ordered_decision_fingerprints
    assert first.account.state == second.account.state
    assert first.account.ledger == second.account.ledger
    assert first.account.state.state_fingerprint == second.account.state.state_fingerprint
    assert first.account.ledger.ledger_fingerprint == second.account.ledger.ledger_fingerprint

    verify_lifecycle_reservation_account_replay_v1(
        account=first.account,
        source=source,
        decisions=((stock, None), (option_record, terms)),
    )


def test_reservation_state_grants_no_fill_position_exit_mark_or_trading_authority() -> None:
    state = initialize_lifecycle_reservation_account_v1(
        source=_post_close_source()
    ).state

    assert state.entry_fill_authority is False
    assert state.new_open_position_authority is False
    assert state.exit_closeout_authority is False
    assert state.mark_to_market_authority is False
    assert state.provider_read_authority is False
    assert state.provider_write_authority is False
    assert state.broker_read_authority is False
    assert state.broker_write_authority is False
    assert state.order_creation_authority is False
    assert state.paper_authority is False
    assert state.live_authority is False

    with pytest.raises(LifecycleReservationAccountError, match="cannot grant"):
        replace(state, entry_fill_authority=True)
    with pytest.raises(LifecycleReservationAccountError, match="cannot grant"):
        replace(state, broker_write_authority=True)
