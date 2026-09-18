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
from packages.simulation.lifecycle_closeout_contract import (
    LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_closeout_state import (
    LifecycleCloseoutAccountError,
    apply_lifecycle_closeout_batch_v1,
    apply_lifecycle_closeout_v1,
    initialize_lifecycle_closeout_account_v1,
    replay_lifecycle_closeout_account_v1,
    verify_lifecycle_closeout_account_replay_v1,
)
from packages.simulation.lifecycle_entry_evidence import (
    LifecycleEntryEvidenceError,
    LifecycleFundingModel,
    build_lifecycle_entry_fill_evidence,
    build_lifecycle_funding_terms,
)
from packages.simulation.lifecycle_entry_evidence_contract import (
    LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT,
    LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_exit_fill import (
    LifecycleExitFillError,
    LifecycleExitFillInputsV1,
    build_lifecycle_exit_fill_evidence,
)
from packages.simulation.lifecycle_exit_fill_contract import (
    LIFECYCLE_EXIT_FILL_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_position_contract import (
    LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_position_marked_contract import (
    LIFECYCLE_POSITION_MARKED_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_position_marked_state import (
    LifecyclePositionMarkedAccountError,
    build_lifecycle_position_marked_account_state,
)
from packages.simulation.lifecycle_position_state import (
    LifecyclePositionAccountError,
    apply_lifecycle_entry_batch_v1,
    apply_lifecycle_entry_v1,
    initialize_lifecycle_position_account_v1,
    replay_lifecycle_position_account_v1,
    verify_lifecycle_position_account_replay_v1,
)
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
from packages.simulation.market_mark_evidence import (
    MarketMarkInputs,
    MarketMarkTransport,
    build_simulated_market_mark_evidence,
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
from packages.simulation.recurrent_close_position import (
    RecurrentClosePositionError,
    apply_recurrent_close_position_batch_v1,
    apply_recurrent_close_position_v1,
    verify_recurrent_close_position_replay_v1,
)
from packages.simulation.recurrent_close_position_contract import (
    RECURRENT_CLOSE_POSITION_TRANSITION_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_coordinator_contract import (
    RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_engine import (
    RecurrentLifecycleCoordinatorError,
    RecurrentLifecycleCoordinatorV1,
)
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryEvidenceError,
    RecurrentFundingModel,
    build_recurrent_entry_fill_evidence,
    build_recurrent_funding_terms,
)
from packages.simulation.recurrent_entry_evidence_contract import (
    RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT,
    RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillError,
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_exit_fill_contract import (
    RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_position_contract import (
    RECURRENT_POSITION_TRANSITION_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_positions import (
    RecurrentPositionTransitionError,
    apply_recurrent_entry_batch_v1,
    apply_recurrent_entry_v1,
    verify_recurrent_entry_replay_v1,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentClosedTradeOrigin,
    RecurrentLifecycleAccountError,
    RecurrentLifecycleEventKind,
    initialize_recurrent_lifecycle_account_v1,
)
from packages.simulation.recurrent_marked_contract import (
    RECURRENT_MARKED_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_marked_state import (
    RecurrentMarkedAccountError,
    build_recurrent_marked_account_state,
)
from packages.simulation.recurrent_reservation_contract import (
    RECURRENT_RESERVATION_TRANSITION_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_reservations import (
    RecurrentReservationError,
    apply_recurrent_decision_reservation_v1,
    apply_recurrent_reservation_batch_v1,
    verify_recurrent_reservation_replay_v1,
)
from packages.simulation.simulated_fill import (
    SimulatedEntryFillError,
    SimulatedEntryFillInputs,
    build_simulated_entry_fill_evidence,
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


def test_lifecycle_entry_and_funding_contract_fingerprints_are_frozen() -> None:
    assert (
        LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT
        == "a2bcaddbfba19370af070217cd2c4b911b121797abb76348747e575e17aa3b3c"
    )
    assert (
        LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT
        == "26266be782240511baadeb73d11aef393aaa6a52f12883b30cd3aab025f54870"
    )


def test_lifecycle_stock_fill_and_funding_bind_exact_reentry_reservation() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record = _stock_record()
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
    ).account

    fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="lifecycle-stock-fill",
            fill_source_fingerprint=_fp("9"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=fill,
    )

    assert fill.lifecycle_reservation_state_fingerprint == reserved.state.state_fingerprint
    assert fill.instrument_kind == InstrumentKind.STOCK
    assert fill.quantity == pytest.approx(100.0)
    assert fill.gross_fill_notional_dollars == pytest.approx(10_000.0)
    assert fill.reserved_capital_dollars == pytest.approx(5_000.0)
    assert fill.funding_semantics_resolved is False
    assert fill.account_mutation_authority is False
    assert fill.open_position_authority is False

    assert funding.funding_model == LifecycleFundingModel.CASH_ONLY_STOCK_LONG
    assert funding.required_cash_dollars == pytest.approx(10_002.0)
    assert funding.reserved_capital_dollars == pytest.approx(5_000.0)
    assert (
        funding.supplemental_unreserved_cash_required_dollars
        == pytest.approx(5_002.0)
    )
    assert funding.unspent_reserved_capital_dollars == 0.0
    assert (
        funding.projected_unreserved_cash_after_entry_dollars
        == pytest.approx(9_805.0)
    )
    assert reserved.state.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert reserved.state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)


def test_lifecycle_option_fill_reuses_reserved_debit_and_unspent_cash() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record, terms = _option_case()
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
        option_terms=terms,
    ).account

    fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=record,
        option_terms=terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="lifecycle-option-fill",
            fill_source_fingerprint=_fp("8"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=5.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=fill,
    )

    assert fill.instrument_kind == InstrumentKind.OPTION
    assert fill.quantity == pytest.approx(2.0)
    assert fill.contract_multiplier == pytest.approx(100.0)
    assert fill.gross_fill_notional_dollars == pytest.approx(1_000.0)
    assert fill.cash_debit_dollars == pytest.approx(1_002.0)
    assert fill.unspent_reserved_capital_dollars == pytest.approx(41.0)
    assert fill.funding_semantics_resolved is True

    assert (
        funding.funding_model
        == LifecycleFundingModel.RESERVED_LONG_OPTION_DEBIT
    )
    assert funding.required_cash_dollars == pytest.approx(1_002.0)
    assert funding.supplemental_unreserved_cash_required_dollars == 0.0
    assert funding.unspent_reserved_capital_dollars == pytest.approx(41.0)
    assert (
        funding.projected_unreserved_cash_after_entry_dollars
        == pytest.approx(18_805.0)
    )


def test_legacy_entry_fill_builder_rejects_lifecycle_reservation_state() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record = _stock_record()
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
    ).account

    with pytest.raises(
        SimulatedEntryFillError,
        match="simulation account-state v2 fingerprint mismatch",
    ):
        build_simulated_entry_fill_evidence(
            account=reserved,  # type: ignore[arg-type]
            record=record,
            inputs=SimulatedEntryFillInputs(
                fill_source_id="must-not-use-legacy-builder",
                fill_source_fingerprint=_fp("7"),
                filled_utc=record.decision_created_utc + timedelta(minutes=1),
                fill_price_per_unit=100.0,
                explicit_entry_fees_dollars=0.0,
            ),
        )


def test_lifecycle_fill_and_funding_fail_on_state_or_reservation_drift() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record = _stock_record()
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
    ).account
    fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="lifecycle-stock-fill",
            fill_source_fingerprint=_fp("6"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )

    with pytest.raises(
        LifecycleEntryEvidenceError,
        match="does not bind the current lifecycle reservation state",
    ):
        build_lifecycle_funding_terms(
            account=base,
            fill=fill,
        )

    tampered = replace(
        fill,
        active_reservation_fingerprint=_fp("0"),
    )
    with pytest.raises(
        LifecycleEntryEvidenceError,
        match="active reservation fingerprint mismatch",
    ):
        build_lifecycle_funding_terms(
            account=reserved,
            fill=tampered,
        )


def test_option_fill_cannot_spend_beyond_reserved_fee_bucket() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record, terms = _option_case(fee_reserve=3.0)
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
        option_terms=terms,
    ).account

    with pytest.raises(
        LifecycleEntryEvidenceError,
        match="entry fees exceed explicit fee reserve",
    ):
        build_lifecycle_entry_fill_evidence(
            account=reserved,
            record=record,
            option_terms=terms,
            inputs=SimulatedEntryFillInputs(
                fill_source_id="bad-option-fee",
                fill_source_fingerprint=_fp("5"),
                filled_utc=record.decision_created_utc + timedelta(minutes=1),
                fill_price_per_unit=5.0,
                explicit_entry_fees_dollars=4.0,
            ),
        )


def test_lifecycle_entry_evidence_grants_no_mutation_or_trading_authority() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record = _stock_record()
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
    ).account
    fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="authority-test",
            fill_source_fingerprint=_fp("4"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=fill,
    )

    with pytest.raises(LifecycleEntryEvidenceError, match="cannot grant"):
        replace(fill, account_mutation_authority=True)
    with pytest.raises(LifecycleEntryEvidenceError, match="cannot grant"):
        replace(fill, broker_fill_authority=True)
    with pytest.raises(LifecycleEntryEvidenceError, match="cannot grant"):
        replace(funding, open_position_authority=True)
    with pytest.raises(LifecycleEntryEvidenceError, match="cannot grant"):
        replace(funding, paper_authority=True)


def _reserved_stock_entry_case(
    *,
    created_utc: datetime = DECISION_BASE,
    source_char: str = "3",
):
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record = _stock_record(created_utc=created_utc)
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
    ).account
    fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id=f"position-stock-{source_char}",
            fill_source_fingerprint=_fp(source_char),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=fill,
    )
    return reserved, record, fill, funding


def test_lifecycle_position_contract_fingerprint_is_frozen() -> None:
    assert (
        LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT
        == "7c5f2a82a8583b9f7b2e90f994f7d6ca4c682888448b97ad287e79e6dad82f29"
    )


def test_lifecycle_stock_entry_consumes_only_reservation_and_expenses_fee_once() -> None:
    reserved, _record, fill, funding = _reserved_stock_entry_case()
    before_open = reserved.state.open_positions
    before_closed = reserved.state.closed_trades

    transition = apply_lifecycle_entry_v1(
        initialize_lifecycle_position_account_v1(source=reserved),
        fill=fill,
        funding=funding,
    )
    state = transition.account.state

    assert transition.idempotent_reuse is False
    assert state.cash == pytest.approx(9_805.0)
    assert state.stock_reserved_capital == 0.0
    assert state.option_reserved_capital == 0.0
    assert state.open_entry_book_value_dollars == pytest.approx(10_200.0)
    assert state.open_stock_gross_entry_exposure_dollars == pytest.approx(10_000.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(4.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(1.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)
    assert state.account_book_equity == pytest.approx(20_005.0)
    assert (
        state.cash
        + state.stock_reserved_capital
        + state.option_reserved_capital
        + state.open_entry_book_value_dollars
        == pytest.approx(state.account_book_equity)
    )
    assert len(state.open_positions) == len(before_open) + 1
    assert state.closed_trades == before_closed
    assert transition.position.entry_fees_dollars == pytest.approx(2.0)
    assert transition.position.all_in_cash_cost_basis_dollars == pytest.approx(
        10_002.0
    )
    assert transition.event is not None
    assert transition.event.entry_fee_delta_dollars == pytest.approx(2.0)
    assert transition.event.cash_delta_dollars == pytest.approx(-5_002.0)


def test_lifecycle_option_entry_returns_unspent_reserve_and_preserves_history() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    record, terms = _option_case()
    reserved = apply_lifecycle_decision_reservation_v1(
        base,
        record,
        option_terms=terms,
    ).account
    fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=record,
        option_terms=terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="position-option",
            fill_source_fingerprint=_fp("2"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=5.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=fill,
    )
    transition = apply_lifecycle_entry_v1(
        initialize_lifecycle_position_account_v1(source=reserved),
        fill=fill,
        funding=funding,
    )
    state = transition.account.state

    assert state.cash == pytest.approx(18_805.0)
    assert state.option_reserved_capital == 0.0
    assert state.open_entry_book_value_dollars == pytest.approx(1_200.0)
    assert state.open_option_entry_book_value_dollars == pytest.approx(1_200.0)
    assert (
        state.open_option_signed_delta_equivalent_entry_reference_dollars
        == pytest.approx(11_120.0)
    )
    assert (
        state.open_option_abs_delta_equivalent_entry_reference_dollars
        == pytest.approx(11_120.0)
    )
    assert state.open_option_premium_at_risk_dollars == pytest.approx(1_200.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(4.0)
    assert state.account_book_equity == pytest.approx(20_005.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)
    assert len(state.closed_trades) == 1


def test_identical_lifecycle_entry_is_idempotent_and_conflict_fails_closed() -> None:
    reserved, record, fill, funding = _reserved_stock_entry_case()
    account = initialize_lifecycle_position_account_v1(source=reserved)
    first = apply_lifecycle_entry_v1(
        account,
        fill=fill,
        funding=funding,
    )
    duplicate = apply_lifecycle_entry_v1(
        first.account,
        fill=fill,
        funding=funding,
    )
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account

    conflicting_fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="conflicting-stock-fill",
            fill_source_fingerprint=_fp("1"),
            filled_utc=fill.filled_utc + timedelta(seconds=1),
            fill_price_per_unit=101.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    conflicting_funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=conflicting_fill,
    )
    with pytest.raises(
        LifecyclePositionAccountError,
        match="conflicting fill",
    ):
        apply_lifecycle_entry_v1(
            first.account,
            fill=conflicting_fill,
            funding=conflicting_funding,
        )


def test_competing_stock_entries_enforce_current_cash_not_isolated_projection() -> None:
    source = _post_close_source()
    account = initialize_lifecycle_reservation_account_v1(source=source)
    first_record = _stock_record(created_utc=DECISION_BASE)
    second_record = _stock_record(
        created_utc=DECISION_BASE + timedelta(minutes=2)
    )
    after_first_reserve = apply_lifecycle_decision_reservation_v1(
        account,
        first_record,
    ).account
    reserved = apply_lifecycle_decision_reservation_v1(
        after_first_reserve,
        second_record,
    ).account
    assert reserved.state.cash == pytest.approx(9_807.0)
    assert reserved.state.stock_reserved_capital == pytest.approx(10_000.0)

    first_fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=first_record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="competition-first",
            fill_source_fingerprint=_fp("a"),
            filled_utc=second_record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    second_fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=second_record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="competition-second",
            fill_source_fingerprint=_fp("b"),
            filled_utc=second_record.decision_created_utc + timedelta(minutes=2),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    first_funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=first_fill,
    )
    second_funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=second_fill,
    )
    assert (
        first_funding.supplemental_unreserved_cash_required_dollars
        == pytest.approx(5_002.0)
    )
    assert (
        second_funding.supplemental_unreserved_cash_required_dollars
        == pytest.approx(5_002.0)
    )

    position_account = initialize_lifecycle_position_account_v1(
        source=reserved
    )
    first = apply_lifecycle_entry_v1(
        position_account,
        fill=first_fill,
        funding=first_funding,
    )
    assert first.account.state.cash == pytest.approx(4_805.0)

    with pytest.raises(
        LifecyclePositionAccountError,
        match="insufficient current cash after competing lifecycle entries",
    ):
        apply_lifecycle_entry_v1(
            first.account,
            fill=second_fill,
            funding=second_funding,
        )


def test_mixed_entry_batch_is_deterministic_and_replays_exactly() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    stock_record = _stock_record()
    option_record, terms = _option_case()
    after_stock = apply_lifecycle_decision_reservation_v1(
        base,
        stock_record,
    ).account
    reserved = apply_lifecycle_decision_reservation_v1(
        after_stock,
        option_record,
        option_terms=terms,
    ).account

    fill_time = option_record.decision_created_utc + timedelta(minutes=1)
    stock_fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=stock_record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="batch-stock",
            fill_source_fingerprint=_fp("c"),
            filled_utc=fill_time,
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    option_fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=option_record,
        option_terms=terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="batch-option",
            fill_source_fingerprint=_fp("d"),
            filled_utc=fill_time + timedelta(seconds=1),
            fill_price_per_unit=5.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    stock_funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=stock_fill,
    )
    option_funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=option_fill,
    )
    entries = (
        (option_fill, option_funding),
        (stock_fill, stock_funding),
    )
    first = replay_lifecycle_position_account_v1(
        source=reserved,
        entries=entries,
    )
    second = replay_lifecycle_position_account_v1(
        source=reserved,
        entries=tuple(reversed(entries)),
    )

    assert first.ordered_fill_fingerprints == (
        stock_fill.fill_fingerprint,
        option_fill.fill_fingerprint,
    )
    assert first.account.state == second.account.state
    assert first.account.ledger == second.account.ledger
    assert first.account.state.cash == pytest.approx(8_803.0)
    assert first.account.state.open_entry_book_value_dollars == pytest.approx(
        11_200.0
    )
    assert first.account.state.cumulative_entry_fees_dollars == pytest.approx(
        6.0
    )
    assert first.account.state.account_book_equity == pytest.approx(20_003.0)
    assert first.account.state.stock_reserved_capital == 0.0
    assert first.account.state.option_reserved_capital == 0.0
    assert len(first.account.state.open_positions) == 3
    assert len(first.account.state.closed_trades) == 1

    verify_lifecycle_position_account_replay_v1(
        account=first.account,
        source=reserved,
        entries=entries,
    )


def test_lifecycle_position_state_grants_no_reservation_exit_mark_or_trading_authority() -> None:
    reserved, _record, fill, funding = _reserved_stock_entry_case()
    transition = apply_lifecycle_entry_v1(
        initialize_lifecycle_position_account_v1(source=reserved),
        fill=fill,
        funding=funding,
    )
    state = transition.account.state

    assert state.reservation_mutation_authority is False
    assert state.exit_closeout_authority is False
    assert state.mark_to_market_authority is False
    assert state.provider_read_authority is False
    assert state.broker_write_authority is False
    assert state.order_creation_authority is False
    assert state.paper_authority is False
    assert state.live_authority is False

    with pytest.raises(LifecyclePositionAccountError, match="cannot grant"):
        replace(state, reservation_mutation_authority=True)
    with pytest.raises(LifecyclePositionAccountError, match="cannot grant"):
        replace(state, exit_closeout_authority=True)
    with pytest.raises(LifecyclePositionAccountError, match="cannot grant"):
        replace(state, paper_authority=True)


def _market_mark(
    position: SimulatedOpenPositionV1,
    *,
    valuation_utc: datetime,
    bid: float,
    ask: float,
    source_char: str,
    age_seconds: float = 5.0,
):
    market_utc = valuation_utc - timedelta(seconds=age_seconds)
    return build_simulated_market_mark_evidence(
        position=position,
        inputs=MarketMarkInputs(
            source_id=f"lifecycle-mark-{position.decision_record_fingerprint[:6]}",
            source_fingerprint=_fp(source_char),
            provider="ALPACA",
            feed=(
                "IEX"
                if position.instrument_kind == InstrumentKind.STOCK
                else "INDICATIVE_OPTIONS"
            ),
            transport=MarketMarkTransport.STREAM,
            feed_quality="REALTIME",
            market_timestamp_utc=market_utc,
            received_utc=market_utc + timedelta(seconds=1),
            valuation_utc=valuation_utc,
            bid_price_per_unit=bid,
            ask_price_per_unit=ask,
            last_price_per_unit=(bid + ask) / 2.0,
        ),
    )


def _post_reentry_stock_position_account():
    reserved, _record, fill, funding = _reserved_stock_entry_case()
    transition = apply_lifecycle_entry_v1(
        initialize_lifecycle_position_account_v1(source=reserved),
        fill=fill,
        funding=funding,
    )
    return transition.account


def test_lifecycle_post_reentry_marked_contract_fingerprint_is_frozen() -> None:
    assert (
        LIFECYCLE_POSITION_MARKED_ACCOUNT_CONTRACT_FINGERPRINT
        == "ba944922450d570ac15b6b28794cfe0cb2c7894cba0e62d09e0957df35c92863"
    )


def test_post_reentry_marks_include_new_and_preexisting_open_positions() -> None:
    account = _post_reentry_stock_position_account()
    existing_option = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    new_stock = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    valuation = account.state.as_of_utc + timedelta(minutes=1)
    state = build_lifecycle_position_marked_account_state(
        source_state=account.state,
        marks=(
            _market_mark(
                existing_option,
                valuation_utc=valuation,
                bid=1.5,
                ask=1.6,
                source_char="e",
            ),
            _market_mark(
                new_stock,
                valuation_utc=valuation,
                bid=101.0,
                ask=101.1,
                source_char="f",
            ),
        ),
        valuation_utc=valuation,
    )

    assert len(state.marked_positions) == 2
    assert state.open_entry_book_value_dollars == pytest.approx(10_200.0)
    assert state.marked_open_position_value_dollars == pytest.approx(10_250.0)
    assert state.aggregate_unrealized_pnl_dollars == pytest.approx(50.0)
    assert state.account_book_equity == pytest.approx(20_005.0)
    assert state.marked_equity == pytest.approx(20_055.0)
    assert (
        state.cash
        + state.stock_reserved_capital
        + state.option_reserved_capital
        + state.marked_open_position_value_dollars
        == pytest.approx(state.marked_equity)
    )
    assert state.cumulative_entry_fees_dollars == pytest.approx(4.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(1.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)
    assert state.closed_trade_count == 1


def test_post_reentry_mark_coverage_rejects_missing_or_extra_positions() -> None:
    account = _post_reentry_stock_position_account()
    option = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    stock = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    valuation = account.state.as_of_utc + timedelta(minutes=1)
    option_mark = _market_mark(
        option,
        valuation_utc=valuation,
        bid=1.5,
        ask=1.6,
        source_char="e",
    )
    stock_mark = _market_mark(
        stock,
        valuation_utc=valuation,
        bid=101.0,
        ask=101.1,
        source_char="f",
    )

    with pytest.raises(
        LifecyclePositionMarkedAccountError,
        match="complete lifecycle open-position mark coverage",
    ):
        build_lifecycle_position_marked_account_state(
            source_state=account.state,
            marks=(option_mark,),
            valuation_utc=valuation,
        )

    with pytest.raises(
        LifecyclePositionMarkedAccountError,
        match="multiple marks",
    ):
        build_lifecycle_position_marked_account_state(
            source_state=account.state,
            marks=(option_mark, stock_mark, stock_mark),
            valuation_utc=valuation,
        )


def test_post_reentry_stale_mark_fails_closed() -> None:
    account = _post_reentry_stock_position_account()
    option = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    stock = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    valuation = account.state.as_of_utc + timedelta(minutes=2)
    stale_stock = _market_mark(
        stock,
        valuation_utc=valuation,
        bid=101.0,
        ask=101.1,
        source_char="f",
        age_seconds=61.0,
    )
    option_mark = _market_mark(
        option,
        valuation_utc=valuation,
        bid=1.5,
        ask=1.6,
        source_char="e",
    )
    with pytest.raises(
        LifecyclePositionMarkedAccountError,
        match="stale or ineligible",
    ):
        build_lifecycle_position_marked_account_state(
            source_state=account.state,
            marks=(option_mark, stale_stock),
            valuation_utc=valuation,
        )


def test_post_reentry_valuation_is_order_independent_and_read_only() -> None:
    account = _post_reentry_stock_position_account()
    positions = tuple(account.state.open_positions)
    valuation = account.state.as_of_utc + timedelta(minutes=1)
    marks = tuple(
        _market_mark(
            position,
            valuation_utc=valuation,
            bid=(
                101.0
                if position.instrument_kind == InstrumentKind.STOCK
                else 1.5
            ),
            ask=(
                101.1
                if position.instrument_kind == InstrumentKind.STOCK
                else 1.6
            ),
            source_char=(
                "f"
                if position.instrument_kind == InstrumentKind.STOCK
                else "e"
            ),
        )
        for position in positions
    )
    first = build_lifecycle_position_marked_account_state(
        source_state=account.state,
        marks=marks,
        valuation_utc=valuation,
    )
    second = build_lifecycle_position_marked_account_state(
        source_state=account.state,
        marks=tuple(reversed(marks)),
        valuation_utc=valuation,
    )

    assert first == second
    assert first.state_fingerprint == second.state_fingerprint
    assert first.account_mutation_authority is False
    assert first.new_realized_pnl_authority is False
    assert first.exit_closeout_authority is False
    assert first.provider_read_authority is False
    assert first.broker_write_authority is False
    assert first.paper_authority is False
    assert first.live_authority is False

    with pytest.raises(
        LifecyclePositionMarkedAccountError,
        match="cannot grant",
    ):
        replace(first, account_mutation_authority=True)


def test_lifecycle_exit_fill_contract_fingerprint_is_frozen() -> None:
    assert (
        LIFECYCLE_EXIT_FILL_CONTRACT_FINGERPRINT
        == "f3a952f971d693dbc0ca098d9eb5ff912d54443b9dcf2580409bb5558285df74"
    )


def test_lifecycle_exit_fill_binds_new_reentry_stock_exactly() -> None:
    account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    exited = account.state.as_of_utc + timedelta(minutes=5)
    fill = build_lifecycle_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=stock.position_fingerprint,
        inputs=LifecycleExitFillInputsV1(
            fill_source_id="lifecycle-reentry-stock-exit",
            fill_source_fingerprint=_fp("1"),
            exited_utc=exited,
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )

    assert fill.source_position_state_fingerprint == account.state.state_fingerprint
    assert fill.position_fingerprint == stock.position_fingerprint
    assert fill.entry_fill_fingerprint == stock.fill_fingerprint
    assert fill.funding_terms_fingerprint == stock.funding_terms_fingerprint
    assert fill.quantity == pytest.approx(stock.quantity)
    assert fill.gross_exit_proceeds_dollars == pytest.approx(10_200.0)
    assert fill.net_exit_proceeds_dollars == pytest.approx(10_199.0)
    assert fill.full_close is True
    assert fill.realized_pnl_authority is False
    assert fill.account_mutation_authority is False


def test_lifecycle_exit_fill_can_close_inherited_option_at_zero() -> None:
    account = _post_reentry_stock_position_account()
    option = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    fill = build_lifecycle_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=option.position_fingerprint,
        inputs=LifecycleExitFillInputsV1(
            fill_source_id="inherited-option-zero-exit",
            fill_source_fingerprint=_fp("2"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=5),
            exit_price_per_unit=0.0,
            explicit_exit_fees_dollars=0.0,
        ),
    )

    assert fill.instrument_kind == InstrumentKind.OPTION
    assert fill.quantity == pytest.approx(1.0)
    assert fill.contract_multiplier == pytest.approx(100.0)
    assert fill.gross_exit_proceeds_dollars == 0.0
    assert fill.net_exit_proceeds_dollars == 0.0
    assert fill.option_contract_ticker == option.option_contract_ticker


def test_lifecycle_exit_fill_rejects_unknown_position_and_backward_time() -> None:
    account = _post_reentry_stock_position_account()

    with pytest.raises(
        LifecycleExitFillError,
        match="exact active lifecycle open position",
    ):
        build_lifecycle_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=_fp("0"),
            inputs=LifecycleExitFillInputsV1(
                fill_source_id="unknown",
                fill_source_fingerprint=_fp("3"),
                exited_utc=account.state.as_of_utc + timedelta(minutes=1),
                exit_price_per_unit=1.0,
            ),
        )

    stock = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    with pytest.raises(
        LifecycleExitFillError,
        match="cannot precede lifecycle position state",
    ):
        build_lifecycle_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=stock.position_fingerprint,
            inputs=LifecycleExitFillInputsV1(
                fill_source_id="too-early",
                fill_source_fingerprint=_fp("4"),
                exited_utc=account.state.as_of_utc - timedelta(seconds=1),
                exit_price_per_unit=102.0,
            ),
        )


def test_lifecycle_exit_fees_cannot_exceed_gross_proceeds() -> None:
    account = _post_reentry_stock_position_account()
    option = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    with pytest.raises(
        LifecycleExitFillError,
        match="exit fees cannot exceed gross exit proceeds",
    ):
        build_lifecycle_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=option.position_fingerprint,
            inputs=LifecycleExitFillInputsV1(
                fill_source_id="bad-fees",
                fill_source_fingerprint=_fp("5"),
                exited_utc=account.state.as_of_utc + timedelta(minutes=1),
                exit_price_per_unit=0.01,
                explicit_exit_fees_dollars=2.0,
            ),
        )


def test_lifecycle_exit_fill_fingerprint_is_deterministic_and_source_bound() -> None:
    account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    kwargs = dict(
        source_state=account.state,
        position_fingerprint=stock.position_fingerprint,
    )
    first = build_lifecycle_exit_fill_evidence(
        **kwargs,
        inputs=LifecycleExitFillInputsV1(
            fill_source_id="deterministic-exit",
            fill_source_fingerprint=_fp("6"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )
    second = build_lifecycle_exit_fill_evidence(
        **kwargs,
        inputs=LifecycleExitFillInputsV1(
            fill_source_id="deterministic-exit",
            fill_source_fingerprint=_fp("6"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )
    changed_source = build_lifecycle_exit_fill_evidence(
        **kwargs,
        inputs=LifecycleExitFillInputsV1(
            fill_source_id="deterministic-exit",
            fill_source_fingerprint=_fp("7"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )

    assert first == second
    assert first.exit_fill_fingerprint == second.exit_fill_fingerprint
    assert first.exit_fill_fingerprint != changed_source.exit_fill_fingerprint


def test_lifecycle_exit_fill_authority_escalation_fails_closed() -> None:
    account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    fill = build_lifecycle_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=stock.position_fingerprint,
        inputs=LifecycleExitFillInputsV1(
            fill_source_id="authority-exit",
            fill_source_fingerprint=_fp("8"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )

    with pytest.raises(LifecycleExitFillError, match="cannot grant"):
        replace(fill, realized_pnl_authority=True)
    with pytest.raises(LifecycleExitFillError, match="cannot grant"):
        replace(fill, broker_fill_authority=True)
    with pytest.raises(LifecycleExitFillError, match="cannot grant"):
        replace(fill, paper_authority=True)


def _lifecycle_exit(
    account,
    position,
    *,
    exited_utc: datetime,
    price: float,
    fees: float,
    source_char: str,
):
    return build_lifecycle_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=position.position_fingerprint,
        inputs=LifecycleExitFillInputsV1(
            fill_source_id=f"lifecycle-close-{source_char}",
            fill_source_fingerprint=_fp(source_char),
            exited_utc=exited_utc,
            exit_price_per_unit=price,
            explicit_exit_fees_dollars=fees,
        ),
    )


def test_lifecycle_closeout_contract_fingerprint_is_frozen() -> None:
    assert (
        LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT
        == "9588c3ac326a78103803371071655f0133608beaf0fb10ee7932b3cf0cbace1b"
    )


def test_lifecycle_closeout_preserves_prior_closed_history_and_fee_semantics() -> None:
    position_account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in position_account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    fill = _lifecycle_exit(
        position_account,
        stock,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="1",
    )
    transition = apply_lifecycle_closeout_v1(
        initialize_lifecycle_closeout_account_v1(source=position_account),
        fill=fill,
    )
    state = transition.account.state
    trade = transition.closed_trade

    assert len(state.prior_closed_trades) == 1
    assert len(state.lifecycle_closed_trades) == 1
    assert len(state.open_positions) == 1
    assert state.open_positions[0].instrument_kind == InstrumentKind.OPTION
    assert state.cash == pytest.approx(20_004.0)
    assert state.open_entry_book_value_dollars == pytest.approx(200.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(4.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(208.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(205.0)
    assert state.account_book_equity == pytest.approx(20_204.0)
    assert trade.account_realized_pnl_delta_dollars == pytest.approx(199.0)
    assert trade.lifetime_trade_net_pnl_dollars == pytest.approx(197.0)
    assert trade.entry_fees_dollars == pytest.approx(2.0)
    assert trade.exit_fees_dollars == pytest.approx(1.0)
    assert (
        state.cash
        + state.stock_reserved_capital
        + state.option_reserved_capital
        + state.open_entry_book_value_dollars
        == pytest.approx(state.account_book_equity)
    )


def test_lifecycle_closeout_can_finish_inherited_option_without_rewriting_prior_trade() -> None:
    position_account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in position_account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    option = next(
        x
        for x in position_account.state.open_positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    stock_fill = _lifecycle_exit(
        position_account,
        stock,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="1",
    )
    option_fill = _lifecycle_exit(
        position_account,
        option,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=6),
        price=0.0,
        fees=0.0,
        source_char="2",
    )

    result = apply_lifecycle_closeout_batch_v1(
        initialize_lifecycle_closeout_account_v1(source=position_account),
        (option_fill, stock_fill),
    )
    state = result.account.state

    assert result.ordered_exit_fill_fingerprints == (
        stock_fill.exit_fill_fingerprint,
        option_fill.exit_fill_fingerprint,
    )
    assert state.open_positions == ()
    assert state.open_entry_book_value_dollars == 0.0
    assert len(state.prior_closed_trades) == 1
    assert len(state.lifecycle_closed_trades) == 2
    assert state.cash == pytest.approx(20_004.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(4.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(8.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(4.0)
    assert state.account_book_equity == pytest.approx(20_004.0)
    assert state.account_book_equity == pytest.approx(state.cash)


def test_lifecycle_closeout_duplicate_is_idempotent_and_conflict_fails_closed() -> None:
    position_account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in position_account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    first_fill = _lifecycle_exit(
        position_account,
        stock,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="3",
    )
    account = initialize_lifecycle_closeout_account_v1(
        source=position_account
    )
    first = apply_lifecycle_closeout_v1(account, fill=first_fill)
    duplicate = apply_lifecycle_closeout_v1(
        first.account,
        fill=first_fill,
    )
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account

    conflicting_fill = _lifecycle_exit(
        position_account,
        stock,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=6),
        price=103.0,
        fees=1.0,
        source_char="4",
    )
    with pytest.raises(
        LifecycleCloseoutAccountError,
        match="conflicting second lifecycle close",
    ):
        apply_lifecycle_closeout_v1(
            first.account,
            fill=conflicting_fill,
        )


def test_lifecycle_closeout_batch_is_order_independent_and_replay_exact() -> None:
    position_account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in position_account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    option = next(
        x
        for x in position_account.state.open_positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    stock_fill = _lifecycle_exit(
        position_account,
        stock,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="5",
    )
    option_fill = _lifecycle_exit(
        position_account,
        option,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=6),
        price=1.5,
        fees=1.0,
        source_char="6",
    )

    first = replay_lifecycle_closeout_account_v1(
        source=position_account,
        fills=(option_fill, stock_fill),
    )
    second = replay_lifecycle_closeout_account_v1(
        source=position_account,
        fills=(stock_fill, option_fill),
    )
    assert first.account.state == second.account.state
    assert first.account.ledger == second.account.ledger
    assert first.account.state.state_fingerprint == second.account.state.state_fingerprint
    assert first.account.ledger.ledger_fingerprint == second.account.ledger.ledger_fingerprint

    verify_lifecycle_closeout_account_replay_v1(
        account=first.account,
        source=position_account,
        fills=(stock_fill, option_fill),
    )


def test_lifecycle_closeout_state_grants_no_external_or_trading_authority() -> None:
    position_account = _post_reentry_stock_position_account()
    state = initialize_lifecycle_closeout_account_v1(
        source=position_account
    ).state

    assert state.provider_read_authority is False
    assert state.provider_write_authority is False
    assert state.broker_read_authority is False
    assert state.broker_write_authority is False
    assert state.order_creation_authority is False
    assert state.paper_authority is False
    assert state.live_authority is False

    with pytest.raises(LifecycleCloseoutAccountError, match="cannot grant"):
        replace(state, broker_write_authority=True)
    with pytest.raises(LifecycleCloseoutAccountError, match="cannot grant"):
        replace(state, paper_authority=True)


def test_lifecycle_closeout_preserves_unrelated_pending_reservation() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    stock_record = _stock_record()
    option_record, terms = _option_case()
    after_stock_reserve = apply_lifecycle_decision_reservation_v1(
        base,
        stock_record,
    ).account
    reserved = apply_lifecycle_decision_reservation_v1(
        after_stock_reserve,
        option_record,
        option_terms=terms,
    ).account

    stock_fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=stock_record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="preserve-reservation-entry",
            fill_source_fingerprint=_fp("9"),
            filled_utc=option_record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    stock_funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=stock_fill,
    )
    position_account = apply_lifecycle_entry_v1(
        initialize_lifecycle_position_account_v1(source=reserved),
        fill=stock_fill,
        funding=stock_funding,
    ).account
    assert len(position_account.state.option_reservations) == 1
    pending = position_account.state.option_reservations[0]
    pending_fp = pending.decision_record_fingerprint

    stock_position = next(
        x
        for x in position_account.state.open_positions
        if x.decision_record_fingerprint == stock_record.record_fingerprint
    )
    exit_fill = _lifecycle_exit(
        position_account,
        stock_position,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="a",
    )
    closed = apply_lifecycle_closeout_v1(
        initialize_lifecycle_closeout_account_v1(
            source=position_account
        ),
        fill=exit_fill,
    ).account.state

    assert len(closed.option_reservations) == 1
    assert closed.option_reservations[0] == pending
    assert (
        closed.option_reservations[0].decision_record_fingerprint
        == pending_fp
    )
    assert closed.option_reserved_capital == pytest.approx(
        pending.reserved_capital
    )
    assert closed.option_reserved_max_loss_cash == pytest.approx(
        pending.max_loss_cash
    )
    assert (
        closed.option_reserved_abs_delta_equivalent_notional
        == pytest.approx(pending.abs_delta_equivalent_notional)
    )


def _recurrent_bootstrap_source():
    position_account = _post_reentry_stock_position_account()
    stock = next(
        x
        for x in position_account.state.open_positions
        if x.instrument_kind == InstrumentKind.STOCK
    )
    fill = _lifecycle_exit(
        position_account,
        stock,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="b",
    )
    return apply_lifecycle_closeout_v1(
        initialize_lifecycle_closeout_account_v1(
            source=position_account
        ),
        fill=fill,
    ).account


def test_recurrent_lifecycle_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
        == "9a22ebdb75a85c7d602851f48ae19a4262b0ab5a28441fc80f26b22a96781299"
    )


def test_recurrent_bootstrap_canonicalizes_both_closed_trade_generations() -> None:
    source = _recurrent_bootstrap_source()
    account = initialize_recurrent_lifecycle_account_v1(source=source)
    state = account.state

    assert state.stable_repeated_cycle_contract is True
    assert state.bootstrap_state_fingerprint == source.state.state_fingerprint
    assert state.bootstrap_ledger_fingerprint == source.ledger.ledger_fingerprint
    assert len(state.closed_trades) == 2
    assert tuple(x.origin for x in state.closed_trades) == (
        RecurrentClosedTradeOrigin.ORIGINAL_CLOSEOUT_V1,
        RecurrentClosedTradeOrigin.LIFECYCLE_CLOSEOUT_V1,
    )
    assert all(
        len(x.source_record_fingerprint) == 64
        for x in state.closed_trades
    )
    assert len(state.open_positions) == 1
    assert state.open_positions[0].instrument_kind == InstrumentKind.OPTION
    assert state.cash == pytest.approx(20_004.0)
    assert state.open_entry_book_value_dollars == pytest.approx(200.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(4.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(208.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(205.0)
    assert state.account_book_equity == pytest.approx(20_204.0)
    assert (
        state.cash
        + state.stock_reserved_capital
        + state.option_reserved_capital
        + state.open_entry_book_value_dollars
        == pytest.approx(state.account_book_equity)
    )
    assert account.ledger.events == ()
    assert account.ledger.initial_state_fingerprint == state.state_fingerprint


def test_recurrent_bootstrap_preserves_pending_reservations_and_open_positions() -> None:
    source = _post_close_source()
    base = initialize_lifecycle_reservation_account_v1(source=source)
    stock_record = _stock_record()
    option_record, terms = _option_case()
    after_stock = apply_lifecycle_decision_reservation_v1(
        base,
        stock_record,
    ).account
    reserved = apply_lifecycle_decision_reservation_v1(
        after_stock,
        option_record,
        option_terms=terms,
    ).account
    stock_fill = build_lifecycle_entry_fill_evidence(
        account=reserved,
        record=stock_record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-pending-entry",
            fill_source_fingerprint=_fp("c"),
            filled_utc=option_record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    stock_funding = build_lifecycle_funding_terms(
        account=reserved,
        fill=stock_fill,
    )
    position_account = apply_lifecycle_entry_v1(
        initialize_lifecycle_position_account_v1(source=reserved),
        fill=stock_fill,
        funding=stock_funding,
    ).account
    stock_position = next(
        x
        for x in position_account.state.open_positions
        if x.decision_record_fingerprint == stock_record.record_fingerprint
    )
    close_fill = _lifecycle_exit(
        position_account,
        stock_position,
        exited_utc=position_account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="d",
    )
    lifecycle_closeout = apply_lifecycle_closeout_v1(
        initialize_lifecycle_closeout_account_v1(
            source=position_account
        ),
        fill=close_fill,
    ).account
    recurrent = initialize_recurrent_lifecycle_account_v1(
        source=lifecycle_closeout
    ).state

    assert recurrent.option_reservations == lifecycle_closeout.state.option_reservations
    assert recurrent.option_reserved_capital == pytest.approx(
        lifecycle_closeout.state.option_reserved_capital
    )
    assert recurrent.open_positions == lifecycle_closeout.state.open_positions
    assert recurrent.closed_trades[-1].origin == (
        RecurrentClosedTradeOrigin.LIFECYCLE_CLOSEOUT_V1
    )


def test_recurrent_canonical_history_preserves_economic_totals_exactly() -> None:
    source = _recurrent_bootstrap_source()
    state = initialize_recurrent_lifecycle_account_v1(source=source).state

    assert sum(x.entry_fees_dollars for x in state.closed_trades) + sum(
        x.entry_fees_dollars for x in state.open_positions
    ) == pytest.approx(state.cumulative_entry_fees_dollars)
    assert sum(
        x.exit_fees_dollars for x in state.closed_trades
    ) == pytest.approx(state.cumulative_exit_fees_dollars)
    assert sum(
        x.account_realized_pnl_delta_dollars for x in state.closed_trades
    ) == pytest.approx(state.cumulative_account_realized_pnl_dollars)
    assert sum(
        x.lifetime_trade_net_pnl_dollars for x in state.closed_trades
    ) == pytest.approx(state.cumulative_lifetime_trade_net_pnl_dollars)


def test_recurrent_account_grants_no_external_or_trading_authority() -> None:
    state = initialize_recurrent_lifecycle_account_v1(
        source=_recurrent_bootstrap_source()
    ).state

    assert state.provider_read_authority is False
    assert state.provider_write_authority is False
    assert state.broker_read_authority is False
    assert state.broker_write_authority is False
    assert state.order_creation_authority is False
    assert state.paper_authority is False
    assert state.live_authority is False

    with pytest.raises(RecurrentLifecycleAccountError, match="cannot grant"):
        replace(state, broker_write_authority=True)
    with pytest.raises(RecurrentLifecycleAccountError, match="cannot grant"):
        replace(state, paper_authority=True)


def _recurrent_account():
    return initialize_recurrent_lifecycle_account_v1(
        source=_recurrent_bootstrap_source()
    )


def test_recurrent_reservation_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_RESERVATION_TRANSITION_CONTRACT_FINGERPRINT
        == "8e7cb6b4cf3d64bcafc8f0af9443bde8022df92c5b200aec67f4611fbedae796"
    )


def test_recurrent_stock_reservation_mutates_same_stable_account_contract() -> None:
    account = _recurrent_account()
    record = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1)
    )
    before_closed = account.state.closed_trades
    before_open = account.state.open_positions
    transition = apply_recurrent_decision_reservation_v1(
        account,
        record,
    )
    state = transition.account.state

    assert state.contract_fingerprint == account.state.contract_fingerprint
    assert state.cash == pytest.approx(15_004.0)
    assert state.stock_reserved_capital == pytest.approx(5_000.0)
    assert state.stock_reserved_gross_notional == pytest.approx(10_000.0)
    assert state.open_positions == before_open
    assert state.closed_trades == before_closed
    assert state.cumulative_entry_fees_dollars == pytest.approx(4.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(208.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(205.0)
    assert state.account_book_equity == pytest.approx(20_204.0)
    assert transition.event is not None
    assert transition.event.kind == RecurrentLifecycleEventKind.RESERVE_STOCK
    assert transition.event.cash_delta_dollars == pytest.approx(-5_000.0)
    assert transition.event.stock_reserved_capital_delta_dollars == pytest.approx(5_000.0)


def test_recurrent_option_reservation_preserves_canonical_history() -> None:
    account = _recurrent_account()
    record, terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2)
    )
    transition = apply_recurrent_decision_reservation_v1(
        account,
        record,
        option_terms=terms,
    )
    state = transition.account.state

    assert state.option_reserved_capital == pytest.approx(1_043.0)
    assert state.option_reserved_max_loss_cash == pytest.approx(1_043.0)
    assert state.option_reserved_premium_at_risk == pytest.approx(1_040.0)
    assert (
        state.option_reserved_signed_delta_equivalent_notional
        == pytest.approx(11_000.0)
    )
    assert len(state.closed_trades) == 2
    assert tuple(x.origin for x in state.closed_trades) == (
        RecurrentClosedTradeOrigin.ORIGINAL_CLOSEOUT_V1,
        RecurrentClosedTradeOrigin.LIFECYCLE_CLOSEOUT_V1,
    )
    assert transition.event is not None
    assert transition.event.reservation_terms_fingerprint is not None
    assert transition.event.option_economics_result_fingerprint is not None


def test_recurrent_duplicate_decision_is_idempotent() -> None:
    account = _recurrent_account()
    record = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1)
    )
    first = apply_recurrent_decision_reservation_v1(account, record)
    duplicate = apply_recurrent_decision_reservation_v1(
        first.account,
        record,
    )
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account


def test_recurrent_reservation_batch_is_order_independent_and_replay_exact() -> None:
    account = _recurrent_account()
    stock = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1)
    )
    option_record, terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2)
    )
    decisions = ((option_record, terms), (stock, None))

    first = apply_recurrent_reservation_batch_v1(
        account,
        decisions,
    )
    second = apply_recurrent_reservation_batch_v1(
        account,
        tuple(reversed(decisions)),
    )
    assert first.ordered_decision_fingerprints == (
        stock.record_fingerprint,
        option_record.record_fingerprint,
    )
    assert first.account.state == second.account.state
    assert first.account.ledger == second.account.ledger
    assert first.account.state.cash == pytest.approx(13_961.0)
    assert first.account.state.stock_reserved_capital == pytest.approx(5_000.0)
    assert first.account.state.option_reserved_capital == pytest.approx(1_043.0)
    assert len(first.account.state.closed_trades) == 2

    verify_recurrent_reservation_replay_v1(
        initial_account=account,
        expected_account=first.account,
        decisions=decisions,
    )


def test_recurrent_reservation_rejects_insufficient_cash_without_spending_open_book() -> None:
    account = _recurrent_account()
    record = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1),
        capital=25_000.0,
    )
    transition = apply_recurrent_decision_reservation_v1(
        account,
        record,
    )

    assert transition.event is not None
    assert (
        transition.event.kind
        == RecurrentLifecycleEventKind.REJECT_INSUFFICIENT_CAPITAL
    )
    assert transition.account.state.cash == pytest.approx(account.state.cash)
    assert transition.account.state.stock_reserved_capital == 0.0
    assert transition.account.state.open_entry_book_value_dollars == pytest.approx(
        account.state.open_entry_book_value_dollars
    )


def test_recurrent_duplicate_option_terms_conflict_fails_closed() -> None:
    account = _recurrent_account()
    record, terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2)
    )
    first = apply_recurrent_decision_reservation_v1(
        account,
        record,
        option_terms=terms,
    )
    repeated_record, changed_terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2),
        fee_reserve=4.0,
    )
    assert repeated_record.record_fingerprint == record.record_fingerprint
    with pytest.raises(
        RecurrentReservationError,
        match="different reservation terms",
    ):
        apply_recurrent_decision_reservation_v1(
            first.account,
            record,
            option_terms=changed_terms,
        )


def _recurrent_stock_reservation_case():
    account = _recurrent_account()
    record = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1)
    )
    reserved = apply_recurrent_decision_reservation_v1(
        account,
        record,
    ).account
    return reserved, record


def _recurrent_option_reservation_case():
    account = _recurrent_account()
    record, terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2)
    )
    reserved = apply_recurrent_decision_reservation_v1(
        account,
        record,
        option_terms=terms,
    ).account
    return reserved, record, terms


def test_recurrent_entry_and_funding_contract_fingerprints_are_frozen() -> None:
    assert (
        RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT
        == "6802682c78dac10921afd49a023bab774dded6d5c8415e53f17ac92f852bf15a"
    )
    assert (
        RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT
        == "4340cbe3d39b1026663db416094093814dab691ef611e7fca8a8a93e5023b6fc"
    )


def test_recurrent_stock_fill_and_funding_bind_current_recurrent_state() -> None:
    reserved, record = _recurrent_stock_reservation_case()
    fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-stock-fill",
            fill_source_fingerprint=_fp("e"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_recurrent_funding_terms(
        account=reserved,
        fill=fill,
    )

    assert fill.recurrent_state_fingerprint == reserved.state.state_fingerprint
    assert fill.instrument_kind == InstrumentKind.STOCK
    assert fill.quantity == pytest.approx(100.0)
    assert fill.gross_fill_notional_dollars == pytest.approx(10_000.0)
    assert fill.reserved_capital_dollars == pytest.approx(5_000.0)
    assert fill.funding_semantics_resolved is False
    assert fill.descriptive_only is True

    assert funding.funding_model == RecurrentFundingModel.CASH_ONLY_STOCK_LONG
    assert funding.required_cash_dollars == pytest.approx(10_002.0)
    assert funding.supplemental_unreserved_cash_required_dollars == pytest.approx(
        5_002.0
    )
    assert funding.projected_unreserved_cash_after_entry_dollars == pytest.approx(
        10_002.0
    )
    assert reserved.state.cumulative_account_realized_pnl_dollars == pytest.approx(
        208.0
    )
    assert reserved.state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(
        205.0
    )


def test_recurrent_option_fill_reuses_exact_reserved_debit() -> None:
    reserved, record, terms = _recurrent_option_reservation_case()
    fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        option_terms=terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-option-fill",
            fill_source_fingerprint=_fp("f"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=5.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_recurrent_funding_terms(
        account=reserved,
        fill=fill,
    )

    assert fill.instrument_kind == InstrumentKind.OPTION
    assert fill.quantity == pytest.approx(2.0)
    assert fill.contract_multiplier == pytest.approx(100.0)
    assert fill.gross_fill_notional_dollars == pytest.approx(1_000.0)
    assert fill.cash_debit_dollars == pytest.approx(1_002.0)
    assert fill.unspent_reserved_capital_dollars == pytest.approx(41.0)
    assert fill.funding_semantics_resolved is True
    assert funding.funding_model == RecurrentFundingModel.RESERVED_LONG_OPTION_DEBIT
    assert funding.required_cash_dollars == pytest.approx(1_002.0)
    assert funding.supplemental_unreserved_cash_required_dollars == 0.0
    assert funding.unspent_reserved_capital_dollars == pytest.approx(41.0)
    assert funding.projected_unreserved_cash_after_entry_dollars == pytest.approx(
        19_002.0
    )


def test_recurrent_funding_rejects_fill_from_stale_account_snapshot() -> None:
    reserved, record = _recurrent_stock_reservation_case()
    fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="stale-recurrent-fill",
            fill_source_fingerprint=_fp("1"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    with pytest.raises(
        RecurrentEntryEvidenceError,
        match="does not bind current recurrent account state",
    ):
        build_recurrent_funding_terms(
            account=_recurrent_account(),
            fill=fill,
        )


def test_recurrent_option_fill_rejects_fee_above_reserved_bucket() -> None:
    account = _recurrent_account()
    record, terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2),
        fee_reserve=3.0,
    )
    reserved = apply_recurrent_decision_reservation_v1(
        account,
        record,
        option_terms=terms,
    ).account
    with pytest.raises(
        RecurrentEntryEvidenceError,
        match="entry fees exceed reserved fee bucket",
    ):
        build_recurrent_entry_fill_evidence(
            account=reserved,
            record=record,
            option_terms=terms,
            inputs=SimulatedEntryFillInputs(
                fill_source_id="bad-recurrent-option-fee",
                fill_source_fingerprint=_fp("2"),
                filled_utc=record.decision_created_utc + timedelta(minutes=1),
                fill_price_per_unit=5.0,
                explicit_entry_fees_dollars=4.0,
            ),
        )


def test_recurrent_entry_and_funding_evidence_grant_no_mutation_authority() -> None:
    reserved, record = _recurrent_stock_reservation_case()
    fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-authority-test",
            fill_source_fingerprint=_fp("3"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_recurrent_funding_terms(
        account=reserved,
        fill=fill,
    )

    with pytest.raises(RecurrentEntryEvidenceError, match="cannot grant"):
        replace(fill, account_mutation_authority=True)
    with pytest.raises(RecurrentEntryEvidenceError, match="cannot grant"):
        replace(fill, broker_fill_authority=True)
    with pytest.raises(RecurrentEntryEvidenceError, match="cannot grant"):
        replace(funding, open_position_authority=True)
    with pytest.raises(RecurrentEntryEvidenceError, match="cannot grant"):
        replace(funding, paper_authority=True)


def _recurrent_stock_entry_case():
    reserved, record = _recurrent_stock_reservation_case()
    fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-position-stock",
            fill_source_fingerprint=_fp("4"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_recurrent_funding_terms(
        account=reserved,
        fill=fill,
    )
    return reserved, record, fill, funding


def _recurrent_option_entry_case():
    reserved, record, terms = _recurrent_option_reservation_case()
    fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        option_terms=terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-position-option",
            fill_source_fingerprint=_fp("5"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=5.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_recurrent_funding_terms(
        account=reserved,
        fill=fill,
    )
    return reserved, record, terms, fill, funding


def test_recurrent_position_transition_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_POSITION_TRANSITION_CONTRACT_FINGERPRINT
        == "998b3c505aaabd429b5009cb1c9cfebe864810f2d6e871d60450f4ccc2d7e084"
    )


def test_recurrent_stock_entry_mutates_same_account_and_expenses_fee_once() -> None:
    reserved, record, fill, funding = _recurrent_stock_entry_case()
    before_closed = reserved.state.closed_trades
    before_open = reserved.state.open_positions

    transition = apply_recurrent_entry_v1(
        reserved,
        fill=fill,
        funding=funding,
    )
    state = transition.account.state

    assert state.contract_fingerprint == reserved.state.contract_fingerprint
    assert transition.idempotent_reuse is False
    assert transition.event is not None
    assert transition.event.kind == RecurrentLifecycleEventKind.OPEN_POSITION
    assert transition.event.decision_record_fingerprint == record.record_fingerprint
    assert transition.event.fill_fingerprint == fill.fill_fingerprint
    assert transition.event.funding_terms_fingerprint == funding.terms_fingerprint
    assert state.cash == pytest.approx(10_002.0)
    assert state.stock_reserved_capital == 0.0
    assert state.open_entry_book_value_dollars == pytest.approx(10_200.0)
    assert state.open_stock_gross_entry_exposure_dollars == pytest.approx(10_000.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(6.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(208.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(205.0)
    assert state.account_book_equity == pytest.approx(20_202.0)
    assert state.closed_trades == before_closed
    assert len(state.open_positions) == len(before_open) + 1
    assert transition.position is not None
    assert transition.position.entry_fees_dollars == pytest.approx(2.0)
    assert transition.position.all_in_cash_cost_basis_dollars == pytest.approx(
        10_002.0
    )
    assert (
        state.cash
        + state.stock_reserved_capital
        + state.option_reserved_capital
        + state.open_entry_book_value_dollars
        == pytest.approx(state.account_book_equity)
    )


def test_recurrent_option_entry_returns_unspent_reserve_on_same_account() -> None:
    reserved, _record, _terms, fill, funding = _recurrent_option_entry_case()
    transition = apply_recurrent_entry_v1(
        reserved,
        fill=fill,
        funding=funding,
    )
    state = transition.account.state

    assert state.contract_fingerprint == reserved.state.contract_fingerprint
    assert state.cash == pytest.approx(19_002.0)
    assert state.option_reserved_capital == 0.0
    assert state.open_entry_book_value_dollars == pytest.approx(1_200.0)
    assert state.open_option_entry_book_value_dollars == pytest.approx(1_200.0)
    assert (
        state.open_option_signed_delta_equivalent_entry_reference_dollars
        == pytest.approx(11_120.0)
    )
    assert (
        state.open_option_abs_delta_equivalent_entry_reference_dollars
        == pytest.approx(11_120.0)
    )
    assert state.open_option_premium_at_risk_dollars == pytest.approx(1_200.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(6.0)
    assert state.account_book_equity == pytest.approx(20_202.0)
    assert len(state.closed_trades) == 2
    assert transition.event is not None
    assert transition.event.option_reserved_capital_delta_dollars == pytest.approx(
        -1_043.0
    )
    assert transition.event.cash_delta_dollars == pytest.approx(41.0)


def test_recurrent_entry_duplicate_is_idempotent_and_conflict_fails_closed() -> None:
    reserved, record, fill, funding = _recurrent_stock_entry_case()
    first = apply_recurrent_entry_v1(
        reserved,
        fill=fill,
        funding=funding,
    )
    duplicate = apply_recurrent_entry_v1(
        first.account,
        fill=fill,
        funding=funding,
    )
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account
    assert duplicate.position_fingerprint == first.position_fingerprint

    conflicting_fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-position-conflict",
            fill_source_fingerprint=_fp("6"),
            filled_utc=fill.filled_utc + timedelta(seconds=1),
            fill_price_per_unit=101.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    conflicting_funding = build_recurrent_funding_terms(
        account=reserved,
        fill=conflicting_fill,
    )
    with pytest.raises(
        RecurrentPositionTransitionError,
        match="conflicting recurrent fill",
    ):
        apply_recurrent_entry_v1(
            first.account,
            fill=conflicting_fill,
            funding=conflicting_funding,
        )


def test_recurrent_single_entry_rejects_evidence_after_unrelated_state_change() -> None:
    reserved, _record, fill, funding = _recurrent_stock_entry_case()
    option_record, option_terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=4)
    )
    changed = apply_recurrent_decision_reservation_v1(
        reserved,
        option_record,
        option_terms=option_terms,
    ).account

    with pytest.raises(
        RecurrentPositionTransitionError,
        match="fill/funding must bind the recurrent evidence source state",
    ):
        apply_recurrent_entry_v1(
            changed,
            fill=fill,
            funding=funding,
        )


def test_recurrent_mixed_entry_batch_uses_common_snapshot_and_replays_exactly() -> None:
    account = _recurrent_account()
    stock_record = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1)
    )
    option_record, option_terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2)
    )
    reserved = apply_recurrent_reservation_batch_v1(
        account,
        ((option_record, option_terms), (stock_record, None)),
    ).account

    stock_fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=stock_record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-batch-stock",
            fill_source_fingerprint=_fp("7"),
            filled_utc=option_record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    option_fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=option_record,
        option_terms=option_terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="recurrent-batch-option",
            fill_source_fingerprint=_fp("8"),
            filled_utc=option_record.decision_created_utc + timedelta(minutes=1, seconds=1),
            fill_price_per_unit=5.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    stock_funding = build_recurrent_funding_terms(
        account=reserved,
        fill=stock_fill,
    )
    option_funding = build_recurrent_funding_terms(
        account=reserved,
        fill=option_fill,
    )
    entries = (
        (option_fill, option_funding),
        (stock_fill, stock_funding),
    )

    first = apply_recurrent_entry_batch_v1(
        reserved,
        entries,
    )
    second = apply_recurrent_entry_batch_v1(
        reserved,
        tuple(reversed(entries)),
    )

    assert first.source_state_fingerprint == reserved.state.state_fingerprint
    assert first.ordered_fill_fingerprints == (
        stock_fill.fill_fingerprint,
        option_fill.fill_fingerprint,
    )
    assert first.account.state == second.account.state
    assert first.account.ledger == second.account.ledger
    assert first.account.state.cash == pytest.approx(9_000.0)
    assert first.account.state.stock_reserved_capital == 0.0
    assert first.account.state.option_reserved_capital == 0.0
    assert first.account.state.open_entry_book_value_dollars == pytest.approx(
        11_200.0
    )
    assert first.account.state.cumulative_entry_fees_dollars == pytest.approx(
        8.0
    )
    assert first.account.state.account_book_equity == pytest.approx(20_200.0)
    assert len(first.account.state.open_positions) == 3
    assert len(first.account.state.closed_trades) == 2
    assert [event.kind for event in first.account.ledger.events[-2:]] == [
        RecurrentLifecycleEventKind.OPEN_POSITION,
        RecurrentLifecycleEventKind.OPEN_POSITION,
    ]

    verify_recurrent_entry_replay_v1(
        initial_account=reserved,
        expected_account=first.account,
        entries=entries,
    )


def test_recurrent_entry_batch_rechecks_current_cash_competition() -> None:
    account = _recurrent_account()
    records = tuple(
        _stock_record(
            created_utc=DECISION_BASE + timedelta(hours=1, minutes=index * 2)
        )
        for index in range(3)
    )
    reserved = apply_recurrent_reservation_batch_v1(
        account,
        tuple((record, None) for record in records),
    ).account
    assert reserved.state.cash == pytest.approx(5_004.0)
    assert reserved.state.stock_reserved_capital == pytest.approx(15_000.0)

    entries = []
    for index, record in enumerate(records):
        fill = build_recurrent_entry_fill_evidence(
            account=reserved,
            record=record,
            inputs=SimulatedEntryFillInputs(
                fill_source_id=f"recurrent-competition-{index}",
                fill_source_fingerprint=_fp(str(index + 1)),
                filled_utc=records[-1].decision_created_utc
                + timedelta(minutes=index + 1),
                fill_price_per_unit=100.0,
                explicit_entry_fees_dollars=2.0,
            ),
        )
        funding = build_recurrent_funding_terms(
            account=reserved,
            fill=fill,
        )
        entries.append((fill, funding))

    with pytest.raises(
        RecurrentPositionTransitionError,
        match="insufficient current recurrent cash after competing entries",
    ):
        apply_recurrent_entry_batch_v1(
            reserved,
            tuple(entries),
        )


def test_recurrent_position_transition_keeps_external_authority_false() -> None:
    reserved, _record, fill, funding = _recurrent_stock_entry_case()
    transition = apply_recurrent_entry_v1(
        reserved,
        fill=fill,
        funding=funding,
    )
    state = transition.account.state

    assert state.provider_read_authority is False
    assert state.provider_write_authority is False
    assert state.broker_read_authority is False
    assert state.broker_write_authority is False
    assert state.order_creation_authority is False
    assert state.paper_authority is False
    assert state.live_authority is False


def _recurrent_positioned_account():
    reserved, _record, fill, funding = _recurrent_stock_entry_case()
    return apply_recurrent_entry_v1(
        reserved,
        fill=fill,
        funding=funding,
    ).account


def test_recurrent_marked_account_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_MARKED_ACCOUNT_CONTRACT_FINGERPRINT
        == "6f473d2480167efa77e7826c994661d12141621122e99b644cb58cc39bbf5532"
    )


def test_recurrent_marked_account_values_inherited_and_new_positions() -> None:
    account = _recurrent_positioned_account()
    option = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.OPTION
    )
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    valuation = account.state.as_of_utc + timedelta(minutes=1)
    option_mark = _market_mark(
        option,
        valuation_utc=valuation,
        bid=1.5,
        ask=1.6,
        source_char="a",
    )
    stock_mark = _market_mark(
        stock,
        valuation_utc=valuation,
        bid=101.0,
        ask=101.1,
        source_char="b",
    )

    marked = build_recurrent_marked_account_state(
        source_state=account.state,
        marks=(stock_mark, option_mark),
        valuation_utc=valuation,
    )

    assert marked.source_account_state_fingerprint == account.state.state_fingerprint
    assert len(marked.marked_positions) == 2
    assert marked.open_entry_book_value_dollars == pytest.approx(10_200.0)
    assert marked.marked_open_position_value_dollars == pytest.approx(10_250.0)
    assert marked.aggregate_unrealized_pnl_dollars == pytest.approx(50.0)
    assert marked.account_book_equity == pytest.approx(20_202.0)
    assert marked.marked_equity == pytest.approx(20_252.0)
    assert marked.cash == pytest.approx(10_002.0)
    assert marked.cumulative_entry_fees_dollars == pytest.approx(6.0)
    assert marked.cumulative_exit_fees_dollars == pytest.approx(2.0)
    assert marked.cumulative_account_realized_pnl_dollars == pytest.approx(208.0)
    assert marked.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(205.0)
    assert marked.closed_trade_count == 2
    assert marked.recurrent_ledger_mutation is False
    assert (
        marked.cash
        + marked.stock_reserved_capital
        + marked.option_reserved_capital
        + marked.marked_open_position_value_dollars
        == pytest.approx(marked.marked_equity)
    )


def test_recurrent_marked_account_requires_complete_current_coverage() -> None:
    account = _recurrent_positioned_account()
    option = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.OPTION
    )
    valuation = account.state.as_of_utc + timedelta(minutes=1)
    option_mark = _market_mark(
        option,
        valuation_utc=valuation,
        bid=1.5,
        ask=1.6,
        source_char="c",
    )

    with pytest.raises(
        RecurrentMarkedAccountError,
        match="complete recurrent open-position mark coverage",
    ):
        build_recurrent_marked_account_state(
            source_state=account.state,
            marks=(option_mark,),
            valuation_utc=valuation,
        )


def test_recurrent_marked_account_rejects_duplicate_and_stale_marks() -> None:
    account = _recurrent_positioned_account()
    option = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.OPTION
    )
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    valuation = account.state.as_of_utc + timedelta(minutes=2)
    option_mark = _market_mark(
        option,
        valuation_utc=valuation,
        bid=1.5,
        ask=1.6,
        source_char="d",
    )
    stock_mark = _market_mark(
        stock,
        valuation_utc=valuation,
        bid=101.0,
        ask=101.1,
        source_char="e",
    )
    stale_stock = _market_mark(
        stock,
        valuation_utc=valuation,
        bid=101.0,
        ask=101.1,
        source_char="f",
        age_seconds=61.0,
    )

    with pytest.raises(
        RecurrentMarkedAccountError,
        match="multiple marks",
    ):
        build_recurrent_marked_account_state(
            source_state=account.state,
            marks=(option_mark, stock_mark, stock_mark),
            valuation_utc=valuation,
        )

    with pytest.raises(
        RecurrentMarkedAccountError,
        match="stale or ineligible",
    ):
        build_recurrent_marked_account_state(
            source_state=account.state,
            marks=(option_mark, stale_stock),
            valuation_utc=valuation,
        )


def test_recurrent_marked_account_is_order_independent_and_read_only() -> None:
    account = _recurrent_positioned_account()
    valuation = account.state.as_of_utc + timedelta(minutes=1)
    marks = tuple(
        _market_mark(
            item,
            valuation_utc=valuation,
            bid=(
                101.0
                if item.instrument_kind == InstrumentKind.STOCK
                else 1.5
            ),
            ask=(
                101.1
                if item.instrument_kind == InstrumentKind.STOCK
                else 1.6
            ),
            source_char=(
                "1"
                if item.instrument_kind == InstrumentKind.STOCK
                else "2"
            ),
        )
        for item in account.state.open_positions
    )
    ledger_before = account.ledger

    first = build_recurrent_marked_account_state(
        source_state=account.state,
        marks=marks,
        valuation_utc=valuation,
    )
    second = build_recurrent_marked_account_state(
        source_state=account.state,
        marks=tuple(reversed(marks)),
        valuation_utc=valuation,
    )

    assert first == second
    assert first.state_fingerprint == second.state_fingerprint
    assert account.ledger == ledger_before
    assert first.account_mutation_authority is False
    assert first.new_realized_pnl_authority is False
    assert first.exit_closeout_authority is False
    assert first.provider_read_authority is False
    assert first.broker_write_authority is False
    assert first.paper_authority is False
    assert first.live_authority is False

    with pytest.raises(RecurrentMarkedAccountError, match="cannot grant"):
        replace(first, account_mutation_authority=True)


def test_recurrent_exit_fill_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT
        == "61135bbede1416c852d7c84fa2914876c056508be9fdad1a87b834cb71f659ad"
    )


def test_recurrent_exit_fill_binds_current_stock_position_and_source_state() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    fill = build_recurrent_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=stock.position_fingerprint,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="recurrent-stock-exit",
            fill_source_fingerprint=_fp("3"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=5),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )

    assert fill.source_recurrent_state_fingerprint == account.state.state_fingerprint
    assert (
        fill.source_account_contract_fingerprint
        == RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    )
    assert fill.position_fingerprint == stock.position_fingerprint
    assert (
        fill.position_source_account_state_fingerprint
        == stock.source_account_state_fingerprint
    )
    assert fill.entry_fill_fingerprint == stock.fill_fingerprint
    assert fill.funding_terms_fingerprint == stock.funding_terms_fingerprint
    assert fill.reservation_fingerprint == stock.reservation_fingerprint
    assert fill.quantity == pytest.approx(100.0)
    assert fill.gross_exit_proceeds_dollars == pytest.approx(10_200.0)
    assert fill.net_exit_proceeds_dollars == pytest.approx(10_199.0)
    assert fill.full_close is True
    assert fill.realized_pnl_authority is False
    assert fill.account_mutation_authority is False


def test_recurrent_exit_fill_supports_zero_price_complete_option_loss() -> None:
    account = _recurrent_positioned_account()
    option = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.OPTION
    )
    fill = build_recurrent_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=option.position_fingerprint,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="recurrent-option-zero-exit",
            fill_source_fingerprint=_fp("4"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=5),
            exit_price_per_unit=0.0,
            explicit_exit_fees_dollars=0.0,
        ),
    )

    assert fill.instrument_kind == InstrumentKind.OPTION
    assert fill.gross_exit_proceeds_dollars == 0.0
    assert fill.net_exit_proceeds_dollars == 0.0
    assert fill.option_contract_ticker == option.option_contract_ticker
    assert fill.option_reservation_terms_fingerprint is not None
    assert fill.option_economics_result_fingerprint is not None


def test_recurrent_exit_fill_rejects_unknown_position_or_backward_time() -> None:
    account = _recurrent_positioned_account()

    with pytest.raises(
        RecurrentExitFillError,
        match="exact active recurrent open position",
    ):
        build_recurrent_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=_fp("0"),
            inputs=RecurrentExitFillInputsV1(
                fill_source_id="unknown-recurrent-exit",
                fill_source_fingerprint=_fp("5"),
                exited_utc=account.state.as_of_utc + timedelta(minutes=1),
                exit_price_per_unit=1.0,
            ),
        )

    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    with pytest.raises(
        RecurrentExitFillError,
        match="cannot precede recurrent lifecycle account state",
    ):
        build_recurrent_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=stock.position_fingerprint,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id="backward-recurrent-exit",
                fill_source_fingerprint=_fp("6"),
                exited_utc=account.state.as_of_utc - timedelta(seconds=1),
                exit_price_per_unit=102.0,
            ),
        )


def test_recurrent_exit_fill_rejects_fees_above_gross_proceeds() -> None:
    account = _recurrent_positioned_account()
    option = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.OPTION
    )
    with pytest.raises(
        RecurrentExitFillError,
        match="exit fees cannot exceed gross exit proceeds",
    ):
        build_recurrent_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=option.position_fingerprint,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id="bad-recurrent-exit-fees",
                fill_source_fingerprint=_fp("7"),
                exited_utc=account.state.as_of_utc + timedelta(minutes=1),
                exit_price_per_unit=0.01,
                explicit_exit_fees_dollars=2.0,
            ),
        )


def test_recurrent_exit_fill_is_deterministic_and_source_bound() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    kwargs = dict(
        source_state=account.state,
        position_fingerprint=stock.position_fingerprint,
    )
    first = build_recurrent_exit_fill_evidence(
        **kwargs,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="deterministic-recurrent-exit",
            fill_source_fingerprint=_fp("8"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )
    second = build_recurrent_exit_fill_evidence(
        **kwargs,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="deterministic-recurrent-exit",
            fill_source_fingerprint=_fp("8"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )
    changed = build_recurrent_exit_fill_evidence(
        **kwargs,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="deterministic-recurrent-exit",
            fill_source_fingerprint=_fp("9"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )

    assert first == second
    assert first.exit_fill_fingerprint == second.exit_fill_fingerprint
    assert first.exit_fill_fingerprint != changed.exit_fill_fingerprint


def test_recurrent_exit_fill_authority_escalation_fails_closed() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    fill = build_recurrent_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=stock.position_fingerprint,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="recurrent-exit-authority",
            fill_source_fingerprint=_fp("a"),
            exited_utc=account.state.as_of_utc + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )

    with pytest.raises(RecurrentExitFillError, match="cannot grant"):
        replace(fill, realized_pnl_authority=True)
    with pytest.raises(RecurrentExitFillError, match="cannot grant"):
        replace(fill, broker_fill_authority=True)
    with pytest.raises(RecurrentExitFillError, match="cannot grant"):
        replace(fill, paper_authority=True)


def _recurrent_exit(
    account,
    position,
    *,
    exited_utc: datetime,
    price: float,
    fees: float,
    source_char: str,
):
    return build_recurrent_exit_fill_evidence(
        source_state=account.state,
        position_fingerprint=position.position_fingerprint,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id=f"recurrent-close-{source_char}",
            fill_source_fingerprint=_fp(source_char),
            exited_utc=exited_utc,
            exit_price_per_unit=price,
            explicit_exit_fees_dollars=fees,
        ),
    )


def test_recurrent_close_position_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_CLOSE_POSITION_TRANSITION_CONTRACT_FINGERPRINT
        == "9f2f32d8905c19bfb377184abd1fa3f9842eb979829ce5ca03c3a44068e17e39"
    )


def test_recurrent_close_stock_appends_native_canonical_history() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    fill = _recurrent_exit(
        account,
        stock,
        exited_utc=account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="b",
    )
    transition = apply_recurrent_close_position_v1(
        account,
        fill=fill,
    )
    state = transition.account.state
    trade = transition.closed_trade

    assert transition.idempotent_reuse is False
    assert transition.event is not None
    assert transition.event.kind == RecurrentLifecycleEventKind.CLOSE_POSITION
    assert transition.event.entry_fee_delta_dollars == 0.0
    assert transition.event.exit_fee_delta_dollars == pytest.approx(1.0)
    assert transition.event.account_realized_pnl_delta_dollars == pytest.approx(
        199.0
    )
    assert transition.event.lifetime_trade_net_pnl_delta_dollars == pytest.approx(
        197.0
    )

    assert trade.origin == RecurrentClosedTradeOrigin.RECURRENT_ACCOUNT_V1
    assert (
        trade.source_state_contract_fingerprint
        == RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    )
    assert trade.source_state_fingerprint == account.state.state_fingerprint
    assert trade.source_record_fingerprint == fill.exit_fill_fingerprint
    assert trade.position_fingerprint == stock.position_fingerprint
    assert trade.account_realized_pnl_delta_dollars == pytest.approx(199.0)
    assert trade.lifetime_trade_net_pnl_dollars == pytest.approx(197.0)

    assert state.cash == pytest.approx(20_201.0)
    assert state.open_entry_book_value_dollars == pytest.approx(200.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(6.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(3.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(407.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(402.0)
    assert state.account_book_equity == pytest.approx(20_401.0)
    assert len(state.closed_trades) == 3
    assert state.closed_trades[-1].origin == (
        RecurrentClosedTradeOrigin.RECURRENT_ACCOUNT_V1
    )
    assert len(state.open_positions) == 1
    assert state.open_positions[0].instrument_kind == InstrumentKind.OPTION
    assert (
        state.cash
        + state.stock_reserved_capital
        + state.option_reserved_capital
        + state.open_entry_book_value_dollars
        == pytest.approx(state.account_book_equity)
    )


def test_recurrent_close_can_finish_inherited_option_without_rewriting_history() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    option = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.OPTION
    )
    stock_fill = _recurrent_exit(
        account,
        stock,
        exited_utc=account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="c",
    )
    option_fill = _recurrent_exit(
        account,
        option,
        exited_utc=account.state.as_of_utc + timedelta(minutes=6),
        price=0.0,
        fees=0.0,
        source_char="d",
    )

    result = apply_recurrent_close_position_batch_v1(
        account,
        (option_fill, stock_fill),
    )
    state = result.account.state

    assert result.source_state_fingerprint == account.state.state_fingerprint
    assert result.ordered_exit_fill_fingerprints == (
        stock_fill.exit_fill_fingerprint,
        option_fill.exit_fill_fingerprint,
    )
    assert state.open_positions == ()
    assert state.open_entry_book_value_dollars == 0.0
    assert state.cash == pytest.approx(20_201.0)
    assert state.account_book_equity == pytest.approx(20_201.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(6.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(3.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(207.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(201.0)
    assert len(state.closed_trades) == 4
    assert tuple(item.origin for item in state.closed_trades[:2]) == (
        RecurrentClosedTradeOrigin.ORIGINAL_CLOSEOUT_V1,
        RecurrentClosedTradeOrigin.LIFECYCLE_CLOSEOUT_V1,
    )
    assert all(
        item.origin == RecurrentClosedTradeOrigin.RECURRENT_ACCOUNT_V1
        for item in state.closed_trades[2:]
    )


def test_recurrent_close_duplicate_is_idempotent_and_conflict_fails_closed() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    fill = _recurrent_exit(
        account,
        stock,
        exited_utc=account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="e",
    )
    first = apply_recurrent_close_position_v1(
        account,
        fill=fill,
    )
    duplicate = apply_recurrent_close_position_v1(
        first.account,
        fill=fill,
    )
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account
    assert duplicate.closed_trade == first.closed_trade

    conflicting = _recurrent_exit(
        account,
        stock,
        exited_utc=account.state.as_of_utc + timedelta(minutes=6),
        price=103.0,
        fees=1.0,
        source_char="f",
    )
    with pytest.raises(
        RecurrentClosePositionError,
        match="conflicting recurrent close",
    ):
        apply_recurrent_close_position_v1(
            first.account,
            fill=conflicting,
        )


def test_recurrent_close_single_rejects_exit_evidence_after_unrelated_mutation() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    fill = _recurrent_exit(
        account,
        stock,
        exited_utc=account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="1",
    )
    record = _stock_record(
        created_utc=account.state.as_of_utc + timedelta(minutes=1)
    )
    changed = apply_recurrent_decision_reservation_v1(
        account,
        record,
    ).account

    with pytest.raises(
        RecurrentClosePositionError,
        match="exit fill must bind the recurrent evidence source state",
    ):
        apply_recurrent_close_position_v1(
            changed,
            fill=fill,
        )


def test_recurrent_close_batch_is_order_independent_and_replay_exact() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    option = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.OPTION
    )
    stock_fill = _recurrent_exit(
        account,
        stock,
        exited_utc=account.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="2",
    )
    option_fill = _recurrent_exit(
        account,
        option,
        exited_utc=account.state.as_of_utc + timedelta(minutes=6),
        price=1.5,
        fees=1.0,
        source_char="3",
    )
    fills = (option_fill, stock_fill)

    first = apply_recurrent_close_position_batch_v1(
        account,
        fills,
    )
    second = apply_recurrent_close_position_batch_v1(
        account,
        tuple(reversed(fills)),
    )

    assert first.account.state == second.account.state
    assert first.account.ledger == second.account.ledger
    assert first.account.state.cash == pytest.approx(20_350.0)
    assert first.account.state.open_positions == ()
    assert first.account.state.cumulative_exit_fees_dollars == pytest.approx(4.0)
    assert first.account.state.cumulative_account_realized_pnl_dollars == pytest.approx(
        356.0
    )
    assert first.account.state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(
        350.0
    )
    assert first.account.state.account_book_equity == pytest.approx(20_350.0)

    verify_recurrent_close_position_replay_v1(
        initial_account=account,
        expected_account=first.account,
        fills=fills,
    )


def test_recurrent_close_preserves_unrelated_pending_reservation() -> None:
    account = _recurrent_account()
    stock_record = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1)
    )
    option_record, option_terms = _option_case(
        created_utc=DECISION_BASE + timedelta(hours=1, minutes=2)
    )
    reserved = apply_recurrent_reservation_batch_v1(
        account,
        ((option_record, option_terms), (stock_record, None)),
    ).account
    stock_fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=stock_record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="pending-preserve-stock-entry",
            fill_source_fingerprint=_fp("4"),
            filled_utc=option_record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    stock_funding = build_recurrent_funding_terms(
        account=reserved,
        fill=stock_fill,
    )
    positioned = apply_recurrent_entry_v1(
        reserved,
        fill=stock_fill,
        funding=stock_funding,
    ).account
    pending = positioned.state.option_reservations[0]
    stock = next(
        item
        for item in positioned.state.open_positions
        if item.decision_record_fingerprint == stock_record.record_fingerprint
    )
    exit_fill = _recurrent_exit(
        positioned,
        stock,
        exited_utc=positioned.state.as_of_utc + timedelta(minutes=5),
        price=102.0,
        fees=1.0,
        source_char="5",
    )
    closed = apply_recurrent_close_position_v1(
        positioned,
        fill=exit_fill,
    ).account.state

    assert closed.option_reservations == (pending,)
    assert closed.option_reserved_capital == pytest.approx(pending.reserved_capital)
    assert closed.option_reserved_max_loss_cash == pytest.approx(
        pending.max_loss_cash
    )
    assert (
        closed.option_reserved_abs_delta_equivalent_notional
        == pytest.approx(pending.abs_delta_equivalent_notional)
    )


def test_recurrent_close_keeps_external_and_trading_authority_false() -> None:
    account = _recurrent_positioned_account()
    stock = next(
        item
        for item in account.state.open_positions
        if item.instrument_kind == InstrumentKind.STOCK
    )
    fill = _recurrent_exit(
        account,
        stock,
        exited_utc=account.state.as_of_utc + timedelta(minutes=1),
        price=102.0,
        fees=1.0,
        source_char="6",
    )
    state = apply_recurrent_close_position_v1(
        account,
        fill=fill,
    ).account.state

    assert state.provider_read_authority is False
    assert state.provider_write_authority is False
    assert state.broker_read_authority is False
    assert state.broker_write_authority is False
    assert state.order_creation_authority is False
    assert state.paper_authority is False
    assert state.live_authority is False


def test_recurrent_coordinator_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT
        == "0cadfd2c89c09c26731b8895ca70893dde3855c3eded4773c4455bce94b8e882"
    )


def test_recurrent_coordinator_owns_repeated_cycle_and_invalidates_stale_marks() -> None:
    coordinator = RecurrentLifecycleCoordinatorV1(
        account=_recurrent_account()
    )
    assert coordinator.revision == 0
    assert coordinator.current_dashboard_pair() is None

    record = _stock_record(
        created_utc=DECISION_BASE + timedelta(hours=1)
    )
    reservation, mutation = coordinator.apply_reservation(
        record=record,
    )
    assert reservation.event is not None
    assert mutation.new_ledger_event_count == 1
    assert mutation.revision == 1
    assert mutation.valuation_invalidated is False

    reserved = coordinator.current_account()
    fill = build_recurrent_entry_fill_evidence(
        account=reserved,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="coordinator-stock-entry",
            fill_source_fingerprint=_fp("7"),
            filled_utc=record.decision_created_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    funding = build_recurrent_funding_terms(
        account=reserved,
        fill=fill,
    )
    entry, mutation = coordinator.apply_entry(
        fill=fill,
        funding=funding,
    )
    assert entry.position is not None
    assert mutation.new_ledger_event_count == 1
    assert mutation.revision == 2
    assert coordinator.current_dashboard_pair() is None

    current = coordinator.current_account()
    valuation = current.state.as_of_utc + timedelta(minutes=1)
    marks = tuple(
        _market_mark(
            position,
            valuation_utc=valuation,
            bid=(
                101.0
                if position.instrument_kind == InstrumentKind.STOCK
                else 1.5
            ),
            ask=(
                101.1
                if position.instrument_kind == InstrumentKind.STOCK
                else 1.6
            ),
            source_char=(
                "8"
                if position.instrument_kind == InstrumentKind.STOCK
                else "9"
            ),
        )
        for position in current.state.open_positions
    )
    publication = coordinator.publish_marks(
        marks=marks,
        valuation_utc=valuation,
    )
    assert publication.revision == 3
    assert publication.idempotent_reuse is False
    assert coordinator.current_dashboard_pair() is not None

    duplicate_entry, duplicate_mutation = coordinator.apply_entry(
        fill=fill,
        funding=funding,
    )
    assert duplicate_entry.idempotent_reuse is True
    assert duplicate_mutation.idempotent_reuse is True
    assert duplicate_mutation.new_ledger_event_count == 0
    assert duplicate_mutation.revision == 3
    assert duplicate_mutation.valuation_invalidated is False
    assert coordinator.current_dashboard_pair() is not None

    current = coordinator.current_account()
    stock = next(
        item
        for item in current.state.open_positions
        if item.decision_record_fingerprint == record.record_fingerprint
    )
    exit_fill = build_recurrent_exit_fill_evidence(
        source_state=current.state,
        position_fingerprint=stock.position_fingerprint,
        inputs=RecurrentExitFillInputsV1(
            fill_source_id="coordinator-stock-exit",
            fill_source_fingerprint=_fp("a"),
            exited_utc=valuation + timedelta(minutes=1),
            exit_price_per_unit=102.0,
            explicit_exit_fees_dollars=1.0,
        ),
    )
    close, mutation = coordinator.apply_close(
        fill=exit_fill,
    )
    assert close.idempotent_reuse is False
    assert mutation.new_ledger_event_count == 1
    assert mutation.revision == 4
    assert mutation.valuation_invalidated is True
    assert coordinator.current_dashboard_pair() is None
    assert len(coordinator.current_account().state.closed_trades) == 3

    survivor_account = coordinator.current_account()
    survivor_valuation = (
        survivor_account.state.as_of_utc + timedelta(minutes=1)
    )
    survivor_marks = tuple(
        _market_mark(
            position,
            valuation_utc=survivor_valuation,
            bid=1.5,
            ask=1.6,
            source_char="b",
        )
        for position in survivor_account.state.open_positions
    )
    publication = coordinator.publish_marks(
        marks=survivor_marks,
        valuation_utc=survivor_valuation,
    )
    assert publication.revision == 5
    assert coordinator.current_dashboard_pair() is not None

    next_record = _stock_record(
        created_utc=survivor_valuation + timedelta(minutes=1)
    )
    _reservation, mutation = coordinator.apply_reservation(
        record=next_record,
    )
    assert mutation.new_ledger_event_count == 1
    assert mutation.revision == 6
    assert mutation.valuation_invalidated is True
    assert coordinator.current_dashboard_pair() is None
    assert (
        coordinator.current_account().state.contract_fingerprint
        == RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    )


def test_recurrent_coordinator_zero_money_event_invalidates_marked_snapshot() -> None:
    coordinator = RecurrentLifecycleCoordinatorV1(
        account=_recurrent_account()
    )
    current = coordinator.current_account()
    valuation = current.state.as_of_utc + timedelta(minutes=1)
    marks = tuple(
        _market_mark(
            position,
            valuation_utc=valuation,
            bid=1.5,
            ask=1.6,
            source_char="c",
        )
        for position in current.state.open_positions
    )
    coordinator.publish_marks(
        marks=marks,
        valuation_utc=valuation,
    )
    assert coordinator.current_dashboard_pair() is not None
    revision_before = coordinator.revision

    too_large = _stock_record(
        created_utc=valuation + timedelta(minutes=1),
        capital=25_000.0,
    )
    transition, mutation = coordinator.apply_reservation(
        record=too_large,
    )

    assert transition.event is not None
    assert transition.event.kind == (
        RecurrentLifecycleEventKind.REJECT_INSUFFICIENT_CAPITAL
    )
    assert mutation.new_ledger_event_count == 1
    assert mutation.revision == revision_before + 1
    assert mutation.valuation_invalidated is True
    assert coordinator.current_dashboard_pair() is None


def test_recurrent_coordinator_identical_mark_republication_is_idempotent() -> None:
    coordinator = RecurrentLifecycleCoordinatorV1(
        account=_recurrent_account()
    )
    current = coordinator.current_account()
    valuation = current.state.as_of_utc + timedelta(minutes=1)
    marks = tuple(
        _market_mark(
            position,
            valuation_utc=valuation,
            bid=1.5,
            ask=1.6,
            source_char="d",
        )
        for position in current.state.open_positions
    )
    first = coordinator.publish_marks(
        marks=marks,
        valuation_utc=valuation,
    )
    second = coordinator.publish_marks(
        marks=tuple(reversed(marks)),
        valuation_utc=valuation,
    )

    assert first.idempotent_reuse is False
    assert second.idempotent_reuse is True
    assert second.revision == first.revision
    assert (
        second.marked_state.state_fingerprint
        == first.marked_state.state_fingerprint
    )
