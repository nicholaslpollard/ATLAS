from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from packages.execution.option_economics import OptionEconomicsInputs, build_option_economic_candidate
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import ActionabilityPolicy, InstrumentKind, TradeExpressionMode
from packages.schemas.case_file import OptionCandidateEvidence
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)
from packages.simulation.account_state_v2 import (
    apply_simulation_decision_v2,
    initialize_simulation_account_v2,
)
from packages.simulation.decision_record import build_simulation_decision_record
from packages.simulation.funding_terms import build_simulation_funding_collateral_terms
from packages.simulation.open_position_state import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
    OpenPositionAccountStateError,
    apply_open_position_batch_v1,
    apply_open_position_fill_v1,
    initialize_open_position_account_v1,
    replay_open_position_account_v1,
    verify_open_position_account_replay_v1,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT,
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)
from packages.simulation.option_reservation import (
    LongOptionReservationInputs,
    build_long_option_reservation_terms,
)
from packages.simulation.simulated_fill import (
    SimulatedEntryFillInputs,
    build_simulated_entry_fill_evidence,
)


CREATED = datetime(2026, 9, 16, 6, 0, tzinfo=UTC)
SOURCE_FP = "a" * 64
SCENARIO_FP = "b" * 64
EVENT_FP = "c" * 64
FILL_SOURCE_FP = "d" * 64
ALT_FILL_SOURCE_FP = "e" * 64


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
    ticker: str = "XYZ",
    instrument_id: str = "iid-xyz",
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
    created_utc: datetime = CREATED,
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
        method_id="open-position-state-fixture-v1",
        source_label="open position fixture",
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


def _stock_inputs(*, position_notional: float = 10_000.0, capital_required: float = 5_000.0) -> StockEconomicsInputs:
    return StockEconomicsInputs(
        position_notional_dollars=position_notional,
        capital_required_dollars=capital_required,
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


def _stock_record(*, ticker: str, instrument_id: str, created_utc: datetime):
    forecast = _forecast(ticker=ticker, instrument_id=instrument_id, created_utc=created_utc)
    return build_simulation_decision_record(
        decision_created_utc=created_utc + timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(),
    )


def _option() -> OptionCandidateEvidence:
    return OptionCandidateEvidence(
        contract_ticker="O:XYZ261016C00100000",
        contract_type="call",
        expiration_date=date(2026, 10, 16),
        dte=30,
        strike=100.0,
        bid=4.8,
        ask=5.2,
        mid=5.0,
        spread_to_mid=0.08,
        open_interest=1_000,
        volume=200,
        delta=0.55,
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
        scenario_model_id="open-position-option-scenario-v1",
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


def _option_record_and_terms():
    forecast = _forecast(created_utc=CREATED + timedelta(minutes=10))
    option = _option()
    economics = build_option_economic_candidate(
        forecast=forecast,
        option=option,
        inputs=_option_inputs(forecast),
    )
    assert economics.candidate is not None
    record = build_simulation_decision_record(
        decision_created_utc=CREATED + timedelta(minutes=11),
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
        inputs=LongOptionReservationInputs(cash_fee_reserve_dollars=3.0),
    )
    return record, terms


def _fill_and_funding(
    *,
    source_account,
    record,
    filled_utc: datetime,
    price: float = 100.0,
    fees: float = 1.25,
    source_fp: str = FILL_SOURCE_FP,
    option_terms=None,
):
    fill = build_simulated_entry_fill_evidence(
        account=source_account,
        record=record,
        option_terms=option_terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="open-position-fixture-fill-source-v1",
            fill_source_fingerprint=source_fp,
            filled_utc=filled_utc,
            fill_price_per_unit=price,
            explicit_entry_fees_dollars=fees,
        ),
    )
    funding = build_simulation_funding_collateral_terms(account=source_account, fill=fill)
    return fill, funding


def _one_stock_source(*, equity: float = 20_000.0):
    record = _stock_record(ticker="XYZ", instrument_id="iid-xyz", created_utc=CREATED)
    source = initialize_simulation_account_v2(as_of_utc=CREATED, equity=equity)
    source = apply_simulation_decision_v2(source, record).account
    fill, funding = _fill_and_funding(
        source_account=source,
        record=record,
        filled_utc=source.state.as_of_utc + timedelta(minutes=1),
    )
    return source, record, fill, funding


def _one_option_source(*, equity: float = 20_000.0):
    record, option_terms = _option_record_and_terms()
    source = initialize_simulation_account_v2(as_of_utc=CREATED, equity=equity)
    source = apply_simulation_decision_v2(source, record, option_terms=option_terms).account
    fill, funding = _fill_and_funding(
        source_account=source,
        record=record,
        option_terms=option_terms,
        filled_utc=source.state.as_of_utc + timedelta(minutes=1),
        price=5.0,
        fees=2.0,
    )
    return source, record, option_terms, fill, funding


def test_contract_identity_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
    assert OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT == (
        "c15c03400d61bf9e025f836118bf431178caadbdfc7c9a62826ec03796a0ee37"
    )
    assert OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION == "atlas-simulation-open-position-account-state-v1"
    assert OPEN_POSITION_ACCOUNT_STATE_CONTRACT["cash_rechecked_at_transition_time"] is True
    assert OPEN_POSITION_ACCOUNT_STATE_CONTRACT["stock_short_supported"] is False
    assert OPEN_POSITION_ACCOUNT_STATE_CONTRACT["no_mark_to_market"] is True
    assert OPEN_POSITION_ACCOUNT_STATE_CONTRACT["paper_authority"] is False
    assert OPEN_POSITION_ACCOUNT_STATE_CONTRACT["live_authority"] is False


def test_initialize_copies_exact_reservation_batch_without_mutating_source() -> None:
    source, _, _, _ = _one_stock_source()
    account = initialize_open_position_account_v1(source_account=source)
    assert account.state.source_account_state_fingerprint == source.state.state_fingerprint
    assert account.state.cash == pytest.approx(15_000.0)
    assert account.state.remaining_stock_reserved_capital == pytest.approx(5_000.0)
    assert account.state.remaining_stock_gross_notional == pytest.approx(10_000.0)
    assert account.state.open_positions == ()
    assert account.state.entry_book_equity == pytest.approx(20_000.0)
    assert source.state.stock_reserved_capital == pytest.approx(5_000.0)


def test_stock_long_transition_releases_reservation_and_books_entry_fee() -> None:
    source, _, fill, funding = _one_stock_source()
    account = initialize_open_position_account_v1(source_account=source)
    result = apply_open_position_fill_v1(account, fill=fill, funding=funding)
    state = result.account.state
    position = result.position
    assert result.idempotent_reuse is False
    assert state.cash == pytest.approx(9_998.75)
    assert state.remaining_stock_reserved_capital == pytest.approx(0.0)
    assert state.open_entry_book_value_dollars == pytest.approx(10_000.0)
    assert state.open_stock_gross_entry_exposure_dollars == pytest.approx(10_000.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(1.25)
    assert state.entry_book_equity == pytest.approx(19_998.75)
    assert position.entry_book_value_dollars == pytest.approx(10_000.0)
    assert position.all_in_cash_cost_basis_dollars == pytest.approx(10_001.25)
    assert position.supplemental_cash_consumed_dollars == pytest.approx(5_001.25)
    assert position.unspent_reserve_returned_dollars == pytest.approx(0.0)
    assert result.event is not None
    assert result.event.stock_reserved_capital_delta_dollars == pytest.approx(-5_000.0)


def test_long_option_transition_returns_unspent_reserve_and_keeps_delta_as_entry_reference() -> None:
    source, _, _, fill, funding = _one_option_source()
    account = initialize_open_position_account_v1(source_account=source)
    result = apply_open_position_fill_v1(account, fill=fill, funding=funding)
    state = result.account.state
    position = result.position
    assert state.cash == pytest.approx(18_998.0)
    assert state.remaining_option_reserved_capital == pytest.approx(0.0)
    assert state.open_option_entry_book_value_dollars == pytest.approx(1_000.0)
    assert state.open_option_premium_at_risk_dollars == pytest.approx(1_000.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(2.0)
    assert state.entry_book_equity == pytest.approx(19_998.0)
    assert position.all_in_cash_cost_basis_dollars == pytest.approx(1_002.0)
    assert position.unspent_reserve_returned_dollars == pytest.approx(41.0)
    assert position.option_signed_delta_equivalent_entry_reference_dollars == pytest.approx(
        source.state.option_signed_delta_equivalent_notional
    )
    assert position.option_abs_delta_equivalent_entry_reference_dollars == pytest.approx(
        source.state.option_abs_delta_equivalent_notional
    )
    assert state.mark_to_market_authority is False
    assert state.unrealized_pnl_authority is False
    assert state.realized_pnl_authority is False


def test_duplicate_same_fill_is_idempotent_and_conflicting_fill_fails_closed() -> None:
    source, record, fill, funding = _one_stock_source()
    account = initialize_open_position_account_v1(source_account=source)
    first = apply_open_position_fill_v1(account, fill=fill, funding=funding)
    duplicate = apply_open_position_fill_v1(first.account, fill=fill, funding=funding)
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account

    other_fill, other_funding = _fill_and_funding(
        source_account=source,
        record=record,
        filled_utc=fill.filled_utc + timedelta(seconds=1),
        price=101.0,
        fees=1.25,
        source_fp=ALT_FILL_SOURCE_FP,
    )
    with pytest.raises(OpenPositionAccountStateError, match="conflicting fill"):
        apply_open_position_fill_v1(first.account, fill=other_fill, funding=other_funding)


def test_two_individually_funded_stock_fills_cannot_spend_same_unreserved_cash() -> None:
    first_record = _stock_record(ticker="AAA", instrument_id="iid-aaa", created_utc=CREATED)
    second_record = _stock_record(
        ticker="BBB",
        instrument_id="iid-bbb",
        created_utc=CREATED + timedelta(minutes=2),
    )
    source = initialize_simulation_account_v2(as_of_utc=CREATED, equity=15_000.0)
    source = apply_simulation_decision_v2(source, first_record).account
    source = apply_simulation_decision_v2(source, second_record).account
    assert source.state.cash == pytest.approx(5_000.0)

    fill1, funding1 = _fill_and_funding(
        source_account=source,
        record=first_record,
        filled_utc=source.state.as_of_utc + timedelta(minutes=1),
        fees=0.0,
    )
    fill2, funding2 = _fill_and_funding(
        source_account=source,
        record=second_record,
        filled_utc=source.state.as_of_utc + timedelta(minutes=2),
        fees=0.0,
        source_fp=ALT_FILL_SOURCE_FP,
    )
    account = initialize_open_position_account_v1(source_account=source)
    first = apply_open_position_fill_v1(account, fill=fill1, funding=funding1)
    assert first.account.state.cash == pytest.approx(0.0)
    with pytest.raises(OpenPositionAccountStateError, match="insufficient current cash"):
        apply_open_position_fill_v1(first.account, fill=fill2, funding=funding2)


def test_mixed_stock_option_batch_reconciles_cash_book_value_and_fees() -> None:
    stock_record = _stock_record(ticker="XYZ", instrument_id="iid-xyz", created_utc=CREATED)
    option_record, option_terms = _option_record_and_terms()
    source = initialize_simulation_account_v2(as_of_utc=CREATED, equity=30_000.0)
    source = apply_simulation_decision_v2(source, stock_record).account
    source = apply_simulation_decision_v2(source, option_record, option_terms=option_terms).account
    stock_fill, stock_funding = _fill_and_funding(
        source_account=source,
        record=stock_record,
        filled_utc=source.state.as_of_utc + timedelta(minutes=1),
    )
    option_fill, option_funding = _fill_and_funding(
        source_account=source,
        record=option_record,
        option_terms=option_terms,
        filled_utc=source.state.as_of_utc + timedelta(minutes=2),
        price=5.0,
        fees=2.0,
        source_fp=ALT_FILL_SOURCE_FP,
    )
    account = initialize_open_position_account_v1(source_account=source)
    result = apply_open_position_batch_v1(
        account,
        ((option_fill, option_funding), (stock_fill, stock_funding)),
    )
    state = result.account.state
    assert result.ordered_fill_fingerprints == (stock_fill.fill_fingerprint, option_fill.fill_fingerprint)
    assert len(state.open_positions) == 2
    assert state.remaining_stock_reserved_capital == pytest.approx(0.0)
    assert state.remaining_option_reserved_capital == pytest.approx(0.0)
    assert state.cash == pytest.approx(18_996.75)
    assert state.open_entry_book_value_dollars == pytest.approx(11_000.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(3.25)
    assert state.entry_book_equity == pytest.approx(29_996.75)
    assert state.cash + state.open_entry_book_value_dollars == pytest.approx(state.entry_book_equity)


def test_batch_order_is_deterministic_and_replay_is_exact() -> None:
    stock_record = _stock_record(ticker="XYZ", instrument_id="iid-xyz", created_utc=CREATED)
    option_record, option_terms = _option_record_and_terms()
    source = initialize_simulation_account_v2(as_of_utc=CREATED, equity=30_000.0)
    source = apply_simulation_decision_v2(source, stock_record).account
    source = apply_simulation_decision_v2(source, option_record, option_terms=option_terms).account
    stock_fill, stock_funding = _fill_and_funding(
        source_account=source,
        record=stock_record,
        filled_utc=source.state.as_of_utc + timedelta(minutes=1),
    )
    option_fill, option_funding = _fill_and_funding(
        source_account=source,
        record=option_record,
        option_terms=option_terms,
        filled_utc=source.state.as_of_utc + timedelta(minutes=2),
        price=5.0,
        fees=2.0,
        source_fp=ALT_FILL_SOURCE_FP,
    )
    entries = ((option_fill, option_funding), (stock_fill, stock_funding))
    forward = replay_open_position_account_v1(source_account=source, entries=entries)
    reverse = replay_open_position_account_v1(source_account=source, entries=tuple(reversed(entries)))
    assert forward.account.state.state_fingerprint == reverse.account.state.state_fingerprint
    assert forward.account.ledger.ledger_fingerprint == reverse.account.ledger.ledger_fingerprint
    verify_open_position_account_replay_v1(
        account=forward.account,
        source_account=source,
        entries=entries,
    )


def test_replay_detects_missing_or_tampered_transition_history() -> None:
    source, _, fill, funding = _one_stock_source()
    complete = replay_open_position_account_v1(
        source_account=source,
        entries=((fill, funding),),
    )
    empty = initialize_open_position_account_v1(source_account=source)
    with pytest.raises(OpenPositionAccountStateError, match="replayed open-position state fingerprint mismatch"):
        verify_open_position_account_replay_v1(
            account=empty,
            source_account=source,
            entries=((fill, funding),),
        )
    verify_open_position_account_replay_v1(
        account=complete.account,
        source_account=source,
        entries=((fill, funding),),
    )


def test_fill_and_funding_must_bind_same_immutable_source_account() -> None:
    source, _, fill, funding = _one_stock_source()
    account = initialize_open_position_account_v1(source_account=source)
    bad_funding = replace(funding, account_state_fingerprint="f" * 64)
    with pytest.raises(OpenPositionAccountStateError, match="immutable source reservation account state"):
        apply_open_position_fill_v1(account, fill=fill, funding=bad_funding)
