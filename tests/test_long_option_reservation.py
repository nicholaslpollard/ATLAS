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
from packages.simulation.decision_record import build_simulation_decision_record
from packages.simulation.option_reservation import (
    LONG_OPTION_RESERVATION_CONTRACT_VERSION,
    LongOptionReservationError,
    LongOptionReservationInputs,
    build_long_option_reservation_terms,
    long_option_reservation_terms_fingerprint,
    option_economics_result_fingerprint,
    option_evidence_fingerprint,
)
from packages.simulation.option_reservation_contract import (
    LONG_OPTION_RESERVATION_CONTRACT,
    LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)


CREATED = datetime(2026, 9, 16, 5, 0, tzinfo=UTC)
DECIDED = CREATED + timedelta(minutes=1)
CUTOFF = CREATED - timedelta(minutes=1)
SOURCE_FP = "5" * 64
SCENARIO_FP = "6" * 64
EVENT_FP = "7" * 64


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
    instrument_id: str = "iid-xyz",
    ticker: str = "XYZ",
) -> UnderlyingMoveTimeForecast:
    bearish = direction == DiscoveryDirection.BEARISH
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=instrument_id,
        ticker=ticker,
        direction=direction,
        forecast_created_utc=CREATED,
        evidence_cutoff_utc=CUTOFF,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=390,
        method_id="long-option-reservation-fixture-v1",
        source_label="long option reservation fixture",
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
    delta: float | None = 0.55,
    ticker: str | None = None,
    eligible: bool = True,
    ask: float = 5.2,
    mid: float = 5.0,
) -> OptionCandidateEvidence:
    bid = max(0.0, 2.0 * mid - ask)
    return OptionCandidateEvidence(
        contract_ticker=ticker
        or (
            "O:XYZ261016C00100000"
            if contract_type == "call"
            else "O:XYZ261016P00100000"
        ),
        contract_type=contract_type,
        expiration_date=date(2026, 10, 16),
        dte=30,
        strike=100.0,
        bid=bid,
        ask=ask,
        mid=mid,
        spread_to_mid=(ask - bid) / mid,
        open_interest=1_000,
        volume=200,
        delta=delta,
        implied_volatility=0.30,
        eligible=eligible,
        reason_codes=("FIXTURE_OPTION",),
    )


def _option_inputs(
    forecast: UnderlyingMoveTimeForecast,
    *,
    capital_required_dollars: float = 1_050.0,
) -> OptionEconomicsInputs:
    return OptionEconomicsInputs(
        contracts=2,
        contract_multiplier=100.0,
        capital_required_dollars=capital_required_dollars,
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
        liquidity_score=0.85,
        executable=True,
        risk_budget_ok=True,
        shortable_if_bearish=True,
    )


def _policy() -> ActionabilityPolicy:
    return ActionabilityPolicy(
        min_expected_net_value=100.0,
        min_expected_return_on_capital=0.10,
        min_probability_profit=0.55,
        max_expected_loss_to_gain_ratio=0.90,
        max_execution_cost_to_expected_gain_ratio=0.10,
        min_liquidity_score=0.85,
        material_superiority_ratio=1.25,
    )


def _option_economics(
    forecast: UnderlyingMoveTimeForecast,
    option: OptionCandidateEvidence,
    *,
    capital_required_dollars: float = 1_050.0,
):
    return build_option_economic_candidate(
        forecast=forecast,
        option=option,
        inputs=_option_inputs(
            forecast,
            capital_required_dollars=capital_required_dollars,
        ),
    )


def _option_record(
    forecast: UnderlyingMoveTimeForecast,
    option_economics,
):
    assert option_economics.candidate is not None
    return build_simulation_decision_record(
        decision_created_utc=DECIDED,
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.OPTIONS_ONLY,
        option_candidates=(option_economics.candidate,),
    )


def test_contract_identity_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT
    assert LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT == (
        "26835cbab3e551f0f7514e8537d823cb23d5db1f440362d20b1ba7493ff6aa64"
    )
    assert LONG_OPTION_RESERVATION_CONTRACT_VERSION == (
        "atlas-long-option-capital-risk-reservation-v1"
    )
    assert LONG_OPTION_RESERVATION_CONTRACT["stock_gross_exposure_mutation"] == 0
    assert LONG_OPTION_RESERVATION_CONTRACT["account_mutation_authority"] is False
    assert LONG_OPTION_RESERVATION_CONTRACT["fill_simulation_authority"] is False
    assert LONG_OPTION_RESERVATION_CONTRACT["broker_reads"] == 0
    assert LONG_OPTION_RESERVATION_CONTRACT["broker_writes"] == 0
    assert LONG_OPTION_RESERVATION_CONTRACT["paper_authority"] is False
    assert LONG_OPTION_RESERVATION_CONTRACT["live_authority"] is False


def test_bullish_call_terms_reserve_debit_and_explicit_fee_cash() -> None:
    forecast = _forecast()
    option = _option()
    economics = _option_economics(forecast, option)
    record = _option_record(forecast, economics)

    terms = build_long_option_reservation_terms(
        record=record,
        option_economics=economics,
        option=option,
        inputs=LongOptionReservationInputs(cash_fee_reserve_dollars=3.0),
    )

    assert terms.decision_record_fingerprint == record.record_fingerprint
    assert terms.option_economics_result_fingerprint == (
        option_economics_result_fingerprint(economics)
    )
    assert terms.option_evidence_fingerprint == option_evidence_fingerprint(option)
    assert terms.entry_cash_debit_dollars == pytest.approx(1_040.0)
    assert terms.cash_fee_reserve_dollars == pytest.approx(3.0)
    assert terms.reserved_capital_dollars == pytest.approx(1_043.0)
    assert terms.max_loss_cash_dollars == pytest.approx(1_043.0)
    assert terms.premium_at_risk_dollars == pytest.approx(1_040.0)
    assert terms.signed_delta_equivalent_notional_dollars == pytest.approx(11_000.0)
    assert terms.abs_delta_equivalent_notional_dollars == pytest.approx(11_000.0)
    assert terms.account_mutation_authority is False
    assert terms.fill_simulation_authority is False


def test_terms_and_fingerprint_are_deterministic() -> None:
    forecast = _forecast()
    option = _option()
    economics = _option_economics(forecast, option)
    record = _option_record(forecast, economics)
    inputs = LongOptionReservationInputs(cash_fee_reserve_dollars=3.0)

    first = build_long_option_reservation_terms(
        record=record,
        option_economics=economics,
        option=option,
        inputs=inputs,
    )
    second = build_long_option_reservation_terms(
        record=record,
        option_economics=economics,
        option=option,
        inputs=inputs,
    )
    assert first == second
    assert first.terms_fingerprint == second.terms_fingerprint
    assert first.terms_fingerprint == long_option_reservation_terms_fingerprint(first)


def test_bearish_put_records_negative_signed_delta_exposure() -> None:
    forecast = _forecast(direction=DiscoveryDirection.BEARISH)
    option = _option(contract_type="put", delta=-0.45)
    economics = _option_economics(forecast, option)
    record = _option_record(forecast, economics)

    terms = build_long_option_reservation_terms(
        record=record,
        option_economics=economics,
        option=option,
    )
    assert terms.option_contract_type == "put"
    assert terms.signed_delta_equivalent_notional_dollars == pytest.approx(-9_000.0)
    assert terms.abs_delta_equivalent_notional_dollars == pytest.approx(9_000.0)


def test_non_option_decision_fails_closed() -> None:
    forecast = _forecast()
    option = _option()
    economics = _option_economics(forecast, option)
    stock_record = build_simulation_decision_record(
        decision_created_utc=DECIDED,
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(economics.candidate,),
    )
    with pytest.raises(LongOptionReservationError, match="did not select an option"):
        build_long_option_reservation_terms(
            record=stock_record,
            option_economics=economics,
            option=option,
        )


def test_selected_candidate_and_option_economics_lineage_must_match() -> None:
    forecast = _forecast()
    option_a = _option()
    economics_a = _option_economics(forecast, option_a)
    record = _option_record(forecast, economics_a)

    option_b = _option(
        ticker="O:XYZ261016C00105000",
        ask=4.2,
        mid=4.0,
    )
    economics_b = _option_economics(forecast, option_b)
    with pytest.raises(LongOptionReservationError, match="identifiers differ"):
        build_long_option_reservation_terms(
            record=record,
            option_economics=economics_b,
            option=option_b,
        )


def test_forecast_and_quote_lineage_fail_closed() -> None:
    forecast = _forecast()
    option = _option()
    economics = _option_economics(forecast, option)
    record = _option_record(forecast, economics)

    other_forecast = _forecast(instrument_id="iid-other", ticker="OTHER")
    other_economics = _option_economics(other_forecast, option)
    with pytest.raises(LongOptionReservationError, match="identifiers differ|forecast lineage"):
        build_long_option_reservation_terms(
            record=record,
            option_economics=other_economics,
            option=option,
        )

    changed_quote = _option(ask=5.3, mid=5.1)
    with pytest.raises(LongOptionReservationError, match="evidence fingerprint lineage"):
        build_long_option_reservation_terms(
            record=record,
            option_economics=economics,
            option=changed_quote,
        )


def test_full_option_evidence_fingerprint_lineage_fails_closed() -> None:
    forecast = _forecast()
    option = _option()
    economics = _option_economics(forecast, option)
    record = _option_record(forecast, economics)

    changed_evidence = option.model_copy(update={"open_interest": 999})
    assert changed_evidence.contract_ticker == option.contract_ticker
    assert changed_evidence.ask == option.ask
    assert changed_evidence.mid == option.mid
    assert changed_evidence.delta == option.delta

    with pytest.raises(LongOptionReservationError, match="evidence fingerprint lineage"):
        build_long_option_reservation_terms(
            record=record,
            option_economics=economics,
            option=changed_evidence,
        )


def test_missing_or_wrong_sign_delta_fails_closed() -> None:
    forecast = _forecast()
    option = _option()
    economics = _option_economics(forecast, option)
    record = _option_record(forecast, economics)

    missing_delta = _option(delta=None)
    with pytest.raises(LongOptionReservationError, match="evidence fingerprint lineage"):
        build_long_option_reservation_terms(
            record=record,
            option_economics=economics,
            option=missing_delta,
        )

    wrong_sign = _option(delta=-0.55)
    with pytest.raises(LongOptionReservationError, match="evidence fingerprint lineage"):
        build_long_option_reservation_terms(
            record=record,
            option_economics=economics,
            option=wrong_sign,
        )


def test_economic_capital_must_cover_debit_plus_fee_reserve() -> None:
    forecast = _forecast()
    option = _option()
    economics = _option_economics(
        forecast,
        option,
        capital_required_dollars=1_040.0,
    )
    record = _option_record(forecast, economics)
    with pytest.raises(LongOptionReservationError, match="does not cover reservation"):
        build_long_option_reservation_terms(
            record=record,
            option_economics=economics,
            option=option,
            inputs=LongOptionReservationInputs(cash_fee_reserve_dollars=1.0),
        )


def test_negative_fee_reserve_and_tampered_terms_fail_closed() -> None:
    with pytest.raises(LongOptionReservationError, match="cannot be negative"):
        LongOptionReservationInputs(cash_fee_reserve_dollars=-0.01)

    forecast = _forecast()
    option = _option()
    economics = _option_economics(forecast, option)
    record = _option_record(forecast, economics)
    terms = build_long_option_reservation_terms(
        record=record,
        option_economics=economics,
        option=option,
        inputs=LongOptionReservationInputs(cash_fee_reserve_dollars=3.0),
    )
    with pytest.raises(LongOptionReservationError, match="reserved capital"):
        replace(terms, reserved_capital_dollars=1_042.0)
    with pytest.raises(LongOptionReservationError, match="cannot grant"):
        replace(terms, account_mutation_authority=True)
