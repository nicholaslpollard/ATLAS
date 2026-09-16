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
    release_option_reservation_v2,
    release_stock_reservation_v2,
)
from packages.simulation.decision_record import build_simulation_decision_record
from packages.simulation.option_reservation import (
    LongOptionReservationInputs,
    build_long_option_reservation_terms,
)
from packages.simulation.simulated_fill import (
    SIMULATED_ENTRY_FILL_CONTRACT_VERSION,
    SimulatedEntryFillError,
    SimulatedEntryFillInputs,
    build_simulated_entry_fill_evidence,
    simulated_entry_fill_fingerprint,
)
from packages.simulation.simulated_fill_contract import (
    SIMULATED_ENTRY_FILL_CONTRACT,
    SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)


CREATED = datetime(2026, 9, 16, 6, 0, tzinfo=UTC)
SOURCE_FP = "a" * 64
SCENARIO_FP = "b" * 64
EVENT_FP = "c" * 64
FILL_SOURCE_FP = "d" * 64


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
        method_id="sim-fill-fixture-v1",
        source_label="simulated fill fixture",
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


def _stock_inputs() -> StockEconomicsInputs:
    return StockEconomicsInputs(
        position_notional_dollars=10_000.0,
        capital_required_dollars=5_000.0,
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


def _stock_case(*, direction: DiscoveryDirection = DiscoveryDirection.BULLISH):
    forecast = _forecast(direction=direction)
    record = build_simulation_decision_record(
        decision_created_utc=CREATED + timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(),
    )
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    account = apply_simulation_decision_v2(account, record).account
    return record, account


def _option(
    *,
    contract_type: str = "call",
    delta: float = 0.55,
) -> OptionCandidateEvidence:
    return OptionCandidateEvidence(
        contract_ticker=(
            "O:XYZ261016C00100000" if contract_type == "call" else "O:XYZ261016P00100000"
        ),
        contract_type=contract_type,
        expiration_date=date(2026, 10, 16),
        dte=30,
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
        scenario_model_id="sim-fill-option-scenario-v1",
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


def _option_case(
    *,
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
    created_utc: datetime = CREATED,
):
    forecast = _forecast(direction=direction, created_utc=created_utc)
    option = _option(
        contract_type="put" if direction == DiscoveryDirection.BEARISH else "call",
        delta=-0.45 if direction == DiscoveryDirection.BEARISH else 0.55,
    )
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
        inputs=LongOptionReservationInputs(cash_fee_reserve_dollars=3.0),
    )
    account = initialize_simulation_account_v2(as_of_utc=created_utc, equity=20_000.0)
    account = apply_simulation_decision_v2(account, record, option_terms=terms).account
    return record, terms, account


def _fill_inputs(
    account,
    *,
    price: float,
    fees: float = 0.0,
    source_fp: str = FILL_SOURCE_FP,
) -> SimulatedEntryFillInputs:
    return SimulatedEntryFillInputs(
        fill_source_id="deterministic-fixture-fill-source-v1",
        fill_source_fingerprint=source_fp,
        filled_utc=account.state.as_of_utc + timedelta(minutes=1),
        fill_price_per_unit=price,
        explicit_entry_fees_dollars=fees,
    )


def test_contract_identity_and_no_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT
    assert SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT == (
        "e271ba5c66fe9bc41b7f81945a1ef8152a2eeae091b27f6efd4859bacd2d8668"
    )
    assert SIMULATED_ENTRY_FILL_CONTRACT_VERSION == "atlas-simulated-entry-fill-evidence-v1"
    assert SIMULATED_ENTRY_FILL_CONTRACT["partial_fill_support"] is False
    assert SIMULATED_ENTRY_FILL_CONTRACT["stock_funding_semantics_inferred"] is False
    assert SIMULATED_ENTRY_FILL_CONTRACT["option_premium_debit_cannot_exceed_reserved_ask_debit"] is True
    assert SIMULATED_ENTRY_FILL_CONTRACT["option_entry_fees_cannot_exceed_cash_fee_reserve"] is True
    assert SIMULATED_ENTRY_FILL_CONTRACT["account_mutation_authority"] is False
    assert SIMULATED_ENTRY_FILL_CONTRACT["broker_fill_authority"] is False
    assert SIMULATED_ENTRY_FILL_CONTRACT["paper_authority"] is False
    assert SIMULATED_ENTRY_FILL_CONTRACT["live_authority"] is False


def test_stock_fill_materializes_exact_reserved_notional_without_funding_inference() -> None:
    record, account = _stock_case()
    fill = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        inputs=_fill_inputs(account, price=101.0, fees=1.25),
    )
    assert fill.instrument_kind == InstrumentKind.STOCK
    assert fill.quantity == pytest.approx(10_000.0 / 101.0)
    assert fill.gross_fill_notional_dollars == pytest.approx(10_000.0)
    assert fill.reserved_capital_dollars == pytest.approx(5_000.0)
    assert fill.entry_fees_dollars == pytest.approx(1.25)
    assert fill.cash_debit_dollars is None
    assert fill.unspent_reserved_capital_dollars is None
    assert fill.funding_semantics_resolved is False
    assert fill.account_mutation_authority is False


def test_bearish_stock_fill_keeps_direction_but_does_not_infer_short_proceeds() -> None:
    record, account = _stock_case(direction=DiscoveryDirection.BEARISH)
    fill = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        inputs=_fill_inputs(account, price=99.0),
    )
    assert fill.direction == DiscoveryDirection.BEARISH
    assert fill.quantity == pytest.approx(10_000.0 / 99.0)
    assert fill.cash_debit_dollars is None
    assert "STOCK_FUNDING_AND_SHORT_PROCEEDS_SEMANTICS_UNRESOLVED" in fill.reason_codes


def test_option_fill_uses_exact_contract_count_and_separate_reserve_buckets() -> None:
    record, terms, account = _option_case()
    fill = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        option_terms=terms,
        inputs=_fill_inputs(account, price=5.0, fees=2.0),
    )
    assert fill.instrument_kind == InstrumentKind.OPTION
    assert fill.quantity == pytest.approx(2.0)
    assert fill.quantity_unit == "CONTRACTS"
    assert fill.contract_multiplier == pytest.approx(100.0)
    assert fill.gross_fill_notional_dollars == pytest.approx(1_000.0)
    assert fill.cash_debit_dollars == pytest.approx(1_002.0)
    assert fill.reserved_capital_dollars == pytest.approx(1_043.0)
    assert fill.unspent_reserved_capital_dollars == pytest.approx(41.0)
    assert fill.funding_semantics_resolved is True


def test_bearish_put_fill_preserves_exact_option_identity() -> None:
    record, terms, account = _option_case(direction=DiscoveryDirection.BEARISH)
    fill = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        option_terms=terms,
        inputs=_fill_inputs(account, price=5.1, fees=1.0),
    )
    assert fill.direction == DiscoveryDirection.BEARISH
    assert fill.option_contract_type == "put"
    assert fill.option_contract_ticker == terms.option_contract_ticker


def test_option_fill_cannot_spend_fee_reserve_on_worse_premium() -> None:
    record, terms, account = _option_case()
    with pytest.raises(SimulatedEntryFillError, match="premium debit exceeds reserved ask debit"):
        build_simulated_entry_fill_evidence(
            account=account,
            record=record,
            option_terms=terms,
            inputs=_fill_inputs(account, price=5.21, fees=0.0),
        )


def test_option_fill_fees_cannot_exceed_explicit_fee_reserve() -> None:
    record, terms, account = _option_case()
    with pytest.raises(SimulatedEntryFillError, match="fees exceed explicit fee reserve"):
        build_simulated_entry_fill_evidence(
            account=account,
            record=record,
            option_terms=terms,
            inputs=_fill_inputs(account, price=5.0, fees=3.01),
        )


def test_fill_requires_active_unreleased_reservation() -> None:
    stock_record, stock_account = _stock_case()
    stock_account = release_stock_reservation_v2(
        stock_account,
        decision_record_fingerprint=stock_record.record_fingerprint,
        released_utc=stock_account.state.as_of_utc + timedelta(minutes=1),
    ).account
    with pytest.raises(SimulatedEntryFillError, match="active stock reservation"):
        build_simulated_entry_fill_evidence(
            account=stock_account,
            record=stock_record,
            inputs=_fill_inputs(stock_account, price=100.0),
        )

    option_record, terms, option_account = _option_case(created_utc=CREATED + timedelta(minutes=10))
    option_account = release_option_reservation_v2(
        option_account,
        decision_record_fingerprint=option_record.record_fingerprint,
        released_utc=option_account.state.as_of_utc + timedelta(minutes=1),
    ).account
    with pytest.raises(SimulatedEntryFillError, match="active option reservation"):
        build_simulated_entry_fill_evidence(
            account=option_account,
            record=option_record,
            option_terms=terms,
            inputs=_fill_inputs(option_account, price=5.0),
        )


def test_option_terms_must_match_exact_active_reservation_lineage() -> None:
    record_a, _, account_a = _option_case()
    _, terms_b, _ = _option_case(created_utc=CREATED + timedelta(minutes=10))
    with pytest.raises(SimulatedEntryFillError, match="terms decision lineage"):
        build_simulated_entry_fill_evidence(
            account=account_a,
            record=record_a,
            option_terms=terms_b,
            inputs=_fill_inputs(account_a, price=5.0),
        )


def test_fill_timestamp_and_source_fingerprint_fail_closed() -> None:
    record, account = _stock_case()
    with pytest.raises(SimulatedEntryFillError, match="cannot precede account state"):
        build_simulated_entry_fill_evidence(
            account=account,
            record=record,
            inputs=SimulatedEntryFillInputs(
                fill_source_id="fixture",
                fill_source_fingerprint=FILL_SOURCE_FP,
                filled_utc=account.state.as_of_utc - timedelta(seconds=1),
                fill_price_per_unit=100.0,
            ),
        )
    with pytest.raises(SimulatedEntryFillError, match="SHA-256"):
        _fill_inputs(account, price=100.0, source_fp="bad")


def test_fill_evidence_and_fingerprint_are_deterministic() -> None:
    record, terms, account = _option_case()
    inputs = _fill_inputs(account, price=5.0, fees=2.0)
    first = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        option_terms=terms,
        inputs=inputs,
    )
    second = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        option_terms=terms,
        inputs=inputs,
    )
    assert first == second
    assert first.fill_fingerprint == second.fill_fingerprint
    assert first.fill_fingerprint == simulated_entry_fill_fingerprint(first)


def test_evidence_authority_escalation_fails_closed() -> None:
    record, account = _stock_case()
    fill = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        inputs=_fill_inputs(account, price=100.0),
    )
    with pytest.raises(SimulatedEntryFillError, match="cannot grant"):
        replace(fill, account_mutation_authority=True)
    with pytest.raises(SimulatedEntryFillError, match="cannot grant"):
        replace(fill, broker_fill_authority=True)
