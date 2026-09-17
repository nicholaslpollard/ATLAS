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
from packages.simulation.funding_terms import (
    SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_VERSION,
    SimulationFundingModel,
    SimulationFundingTermsError,
    build_simulation_funding_collateral_terms,
    simulation_funding_terms_fingerprint,
)
from packages.simulation.funding_terms_contract import (
    SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT,
    SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT,
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
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
    created_utc: datetime = CREATED,
) -> UnderlyingMoveTimeForecast:
    bearish = direction == DiscoveryDirection.BEARISH
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-xyz",
        ticker="XYZ",
        direction=direction,
        forecast_created_utc=created_utc,
        evidence_cutoff_utc=created_utc - timedelta(minutes=1),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=390,
        method_id="funding-terms-fixture-v1",
        source_label="funding terms fixture",
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


def _stock_fill(
    *,
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
    equity: float = 20_000.0,
    fees: float = 1.25,
):
    forecast = _forecast(direction=direction)
    record = build_simulation_decision_record(
        decision_created_utc=CREATED + timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(),
    )
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=equity)
    account = apply_simulation_decision_v2(account, record).account
    fill = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="funding-terms-fixture-fill-source-v1",
            fill_source_fingerprint=FILL_SOURCE_FP,
            filled_utc=account.state.as_of_utc + timedelta(minutes=1),
            fill_price_per_unit=100.0,
            explicit_entry_fees_dollars=fees,
        ),
    )
    return account, fill


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
        scenario_model_id="funding-terms-option-scenario-v1",
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


def _option_fill():
    forecast = _forecast()
    option = _option()
    economics = build_option_economic_candidate(
        forecast=forecast,
        option=option,
        inputs=_option_inputs(forecast),
    )
    assert economics.candidate is not None
    record = build_simulation_decision_record(
        decision_created_utc=CREATED + timedelta(minutes=1),
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
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    account = apply_simulation_decision_v2(account, record, option_terms=terms).account
    fill = build_simulated_entry_fill_evidence(
        account=account,
        record=record,
        option_terms=terms,
        inputs=SimulatedEntryFillInputs(
            fill_source_id="funding-terms-fixture-fill-source-v1",
            fill_source_fingerprint=FILL_SOURCE_FP,
            filled_utc=account.state.as_of_utc + timedelta(minutes=1),
            fill_price_per_unit=5.0,
            explicit_entry_fees_dollars=2.0,
        ),
    )
    return account, fill


def test_contract_identity_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT == (
        "f76d77ebbf138924a22813773ad27276b0fa71691ddff1d21040171c7b6d3821"
    )
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_VERSION == (
        "atlas-simulation-funding-collateral-terms-v1"
    )
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT["stock_long_funding_model"] == (
        "CASH_ONLY_NO_BORROWING"
    )
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT["stock_short_supported"] is False
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT["stock_short_proceeds_inferred"] is False
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT["account_mutation_authority"] is False
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT["paper_authority"] is False
    assert SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT["live_authority"] is False


def test_stock_long_is_fully_cash_funded_using_reservation_plus_unreserved_cash() -> None:
    account, fill = _stock_fill()
    terms = build_simulation_funding_collateral_terms(account=account, fill=fill)
    assert terms.instrument_kind == InstrumentKind.STOCK
    assert terms.funding_model == SimulationFundingModel.CASH_ONLY_STOCK_LONG
    assert terms.required_cash_dollars == pytest.approx(10_001.25)
    assert terms.reserved_capital_dollars == pytest.approx(5_000.0)
    assert terms.supplemental_unreserved_cash_required_dollars == pytest.approx(5_001.25)
    assert terms.unspent_reserved_capital_dollars == pytest.approx(0.0)
    assert terms.borrowing_dollars == pytest.approx(0.0)
    assert terms.short_sale_proceeds_dollars == pytest.approx(0.0)
    assert terms.collateral_dollars == pytest.approx(0.0)
    assert account.state.cash == pytest.approx(15_000.0)
    assert terms.projected_unreserved_cash_after_transition_dollars == pytest.approx(9_998.75)
    assert terms.fully_funded is True
    assert terms.account_mutation_authority is False


def test_stock_long_fails_closed_when_supplemental_cash_is_not_available() -> None:
    account, fill = _stock_fill(equity=7_000.0)
    assert account.state.cash == pytest.approx(2_000.0)
    with pytest.raises(SimulationFundingTermsError, match="insufficient unreserved cash"):
        build_simulation_funding_collateral_terms(account=account, fill=fill)


def test_stock_short_fails_closed_without_short_proceeds_or_collateral_model() -> None:
    account, fill = _stock_fill(direction=DiscoveryDirection.BEARISH)
    with pytest.raises(SimulationFundingTermsError, match="stock short funding/collateral semantics"):
        build_simulation_funding_collateral_terms(account=account, fill=fill)


def test_long_option_reuses_exact_reserved_debit_and_unspent_reserve() -> None:
    account, fill = _option_fill()
    terms = build_simulation_funding_collateral_terms(account=account, fill=fill)
    assert terms.instrument_kind == InstrumentKind.OPTION
    assert terms.funding_model == SimulationFundingModel.RESERVED_LONG_OPTION_DEBIT
    assert terms.required_cash_dollars == pytest.approx(1_002.0)
    assert terms.reserved_capital_dollars == pytest.approx(1_043.0)
    assert terms.supplemental_unreserved_cash_required_dollars == pytest.approx(0.0)
    assert terms.unspent_reserved_capital_dollars == pytest.approx(41.0)
    assert account.state.cash == pytest.approx(18_957.0)
    assert terms.projected_unreserved_cash_after_transition_dollars == pytest.approx(18_998.0)
    assert terms.borrowing_dollars == pytest.approx(0.0)
    assert terms.collateral_dollars == pytest.approx(0.0)


def test_funding_terms_require_exact_account_state_and_active_reservation_lineage() -> None:
    account, fill = _stock_fill()
    stale_fill = replace(fill, account_state_fingerprint="e" * 64)
    with pytest.raises(SimulationFundingTermsError, match="account-state fingerprint"):
        build_simulation_funding_collateral_terms(account=account, fill=stale_fill)

    bad_reservation = replace(fill, active_reservation_fingerprint="f" * 64)
    with pytest.raises(SimulationFundingTermsError, match="reservation fingerprint lineage"):
        build_simulation_funding_collateral_terms(account=account, fill=bad_reservation)


def test_funding_terms_are_deterministic_and_descriptive_only() -> None:
    account, fill = _option_fill()
    first = build_simulation_funding_collateral_terms(account=account, fill=fill)
    second = build_simulation_funding_collateral_terms(account=account, fill=fill)
    assert first == second
    assert first.terms_fingerprint == second.terms_fingerprint
    assert first.terms_fingerprint == simulation_funding_terms_fingerprint(first)
    assert first.descriptive_only is True
    assert first.borrowing_authority is False
    assert first.reservation_release_authority is False
    assert first.open_position_authority is False
    assert first.mark_to_market_authority is False
    assert first.realized_pnl_authority is False
    assert first.broker_read_authority is False
    assert first.broker_write_authority is False
    assert first.order_creation_authority is False
    assert first.paper_authority is False
    assert first.live_authority is False
