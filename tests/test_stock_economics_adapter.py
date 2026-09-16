from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.execution.stock_economics import (
    STOCK_ECONOMICS_CONTRACT_VERSION,
    StockEconomicsError,
    StockEconomicsInputs,
    build_stock_economic_candidate,
)
from packages.execution.stock_economics_contract import (
    STOCK_ECONOMICS_CONTRACT,
    STOCK_ECONOMICS_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    InstrumentKind,
    evaluate_actionability,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)


CREATED = datetime(2026, 9, 16, 3, 0, tzinfo=UTC)
CUTOFF = CREATED - timedelta(minutes=1)
SOURCE_FP = "2" * 64


def _threshold() -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=0.01,
        favorable_touch_probability=0.40,
        adverse_touch_probability=0.25,
        favorable_before_adverse_probability=0.32,
        adverse_before_favorable_probability=0.14,
        same_interval_collision_probability=0.04,
        median_favorable_time=10.0,
    )


def _forecast(**overrides: object) -> UnderlyingMoveTimeForecast:
    payload: dict[str, object] = {
        "availability": ForecastAvailability.AVAILABLE,
        "instrument_id": "iid-xyz",
        "ticker": "XYZ",
        "direction": DiscoveryDirection.BULLISH,
        "forecast_created_utc": CREATED,
        "evidence_cutoff_utc": CUTOFF,
        "horizon_unit": ForecastHorizonUnit.MINUTES,
        "horizon_value": 390,
        "method_id": "fixture-forecast-v1",
        "source_label": "fixture forecast",
        "source_fingerprint": SOURCE_FP,
        "sample_size": 1_000,
        "reference_price": 100.0,
        "mean_signed_return": 0.008,
        "median_signed_return": 0.005,
        "p10_signed_return": -0.020,
        "p25_signed_return": -0.006,
        "p75_signed_return": 0.018,
        "p90_signed_return": 0.035,
        "probability_positive_return": 0.58,
        "mean_mfe": 0.022,
        "mean_mae": 0.009,
        "thresholds": (_threshold(),),
        "uncertainty_score": 0.30,
        "reason_codes": ("FIXTURE",),
    }
    payload.update(overrides)
    return UnderlyingMoveTimeForecast(**payload)


def _inputs(**overrides: object) -> StockEconomicsInputs:
    payload: dict[str, object] = {
        "position_notional_dollars": 10_000.0,
        "capital_required_dollars": 5_000.0,
        "entry_slippage_bps": 5.0,
        "exit_slippage_bps": 5.0,
        "round_trip_commission_dollars": 1.0,
        "round_trip_fees_dollars": 1.0,
        "horizon_borrow_cost_dollars": 0.0,
        "horizon_financing_cost_dollars": 2.0,
        "net_probability_profit": 0.50,
        "liquidity_score": 0.85,
        "executable": True,
        "risk_budget_ok": True,
        "shortable_if_bearish": True,
    }
    payload.update(overrides)
    return StockEconomicsInputs(**payload)


def test_contract_fingerprint_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == STOCK_ECONOMICS_CONTRACT_FINGERPRINT
    assert STOCK_ECONOMICS_CONTRACT_FINGERPRINT == (
        "68f4b7ca0e4f86f07bf20afa1c7e6e5aa9708c081db44cc3c18f8123e711f924"
    )
    assert STOCK_ECONOMICS_CONTRACT_VERSION == "atlas-stock-economics-adapter-v1"
    assert STOCK_ECONOMICS_CONTRACT["option_candidate_created"] is False
    assert STOCK_ECONOMICS_CONTRACT["broker_reads"] == 0
    assert STOCK_ECONOMICS_CONTRACT["broker_writes"] == 0
    assert STOCK_ECONOMICS_CONTRACT["paper_authority"] is False
    assert STOCK_ECONOMICS_CONTRACT["live_authority"] is False
    assert STOCK_ECONOMICS_CONTRACT["promotion_authority"] is False


def test_bullish_forecast_builds_deterministic_all_in_stock_economics() -> None:
    forecast = _forecast()
    result = build_stock_economic_candidate(forecast=forecast, inputs=_inputs())
    assert result.source_forecast_fingerprint == forecast_fingerprint(forecast)
    assert result.gross_directional_sign_probability == pytest.approx(0.58)
    assert result.direction_adjusted_mean_return == pytest.approx(0.008)
    assert result.expected_gross_pnl_dollars == pytest.approx(80.0)
    assert result.slippage_cost_dollars == pytest.approx(10.0)
    assert result.all_in_expression_cost_dollars == pytest.approx(14.0)
    assert result.expected_net_value_dollars == pytest.approx(66.0)
    assert result.expected_return_on_capital == pytest.approx(66.0 / 5_000.0)
    assert result.expected_gain_dollars == pytest.approx(220.0)
    assert result.expected_loss_dollars == pytest.approx(90.0)
    assert result.candidate is not None
    assert result.candidate.kind == InstrumentKind.STOCK
    assert result.candidate.expected_net_value == pytest.approx(66.0)
    assert result.candidate.execution_cost_dollars == pytest.approx(14.0)
    assert result.candidate.preference_score == pytest.approx(66.0 / 5_000.0)
    assert result.candidate.scenario_complete is True
    assert result.candidate.identifier.startswith("STOCK:iid-xyz:")


def test_adapter_candidate_interoperates_with_universal_actionability_gate() -> None:
    candidate = build_stock_economic_candidate(
        forecast=_forecast(),
        inputs=_inputs(),
    ).candidate
    assert candidate is not None
    policy = ActionabilityPolicy(
        min_expected_net_value=50.0,
        min_expected_return_on_capital=0.01,
        min_probability_profit=0.45,
        max_expected_loss_to_gain_ratio=0.50,
        max_execution_cost_to_expected_gain_ratio=0.10,
        min_liquidity_score=0.80,
        material_superiority_ratio=1.25,
    )
    evaluation = evaluate_actionability(candidate, policy)
    assert evaluation.eligible is True
    assert "ECONOMIC_GATE_ACCEPTED" in evaluation.reason_codes


def test_bearish_forecast_inverts_mean_and_sign_probability() -> None:
    forecast = _forecast(
        direction=DiscoveryDirection.BEARISH,
        mean_signed_return=-0.010,
        median_signed_return=-0.006,
        p10_signed_return=-0.040,
        p25_signed_return=-0.020,
        p75_signed_return=0.005,
        p90_signed_return=0.020,
        probability_positive_return=0.35,
        mean_mfe=0.030,
        mean_mae=0.010,
    )
    result = build_stock_economic_candidate(
        forecast=forecast,
        inputs=_inputs(
            net_probability_profit=0.55,
            horizon_borrow_cost_dollars=7.0,
            horizon_financing_cost_dollars=0.0,
        ),
    )
    assert result.gross_directional_sign_probability == pytest.approx(0.65)
    assert result.direction_adjusted_mean_return == pytest.approx(0.010)
    assert result.expected_gross_pnl_dollars == pytest.approx(100.0)
    assert result.all_in_expression_cost_dollars == pytest.approx(19.0)
    assert result.expected_net_value_dollars == pytest.approx(81.0)
    assert result.candidate is not None
    assert result.candidate.executable is True


def test_bearish_shortability_failure_is_preserved_for_gate_rejection() -> None:
    forecast = _forecast(
        direction=DiscoveryDirection.BEARISH,
        mean_signed_return=-0.010,
        median_signed_return=-0.006,
        p10_signed_return=-0.040,
        p25_signed_return=-0.020,
        p75_signed_return=0.005,
        p90_signed_return=0.020,
        probability_positive_return=0.35,
    )
    result = build_stock_economic_candidate(
        forecast=forecast,
        inputs=_inputs(net_probability_profit=0.50, shortable_if_bearish=False),
    )
    assert result.candidate is not None
    assert result.candidate.executable is False
    assert "BEARISH_STOCK_NOT_SHORTABLE" in result.reason_codes


def test_net_profit_probability_cannot_exceed_gross_directional_sign_probability() -> None:
    with pytest.raises(StockEconomicsError, match="cannot exceed"):
        build_stock_economic_candidate(
            forecast=_forecast(probability_positive_return=0.58),
            inputs=_inputs(net_probability_profit=0.59),
        )


def test_unavailable_and_neutral_forecasts_do_not_create_stock_candidates() -> None:
    unavailable = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.UNAVAILABLE,
        instrument_id="iid-missing",
        ticker="MISS",
        direction=DiscoveryDirection.NEUTRAL,
        forecast_created_utc=CREATED,
        evidence_cutoff_utc=CUTOFF,
        horizon_unit=ForecastHorizonUnit.SESSIONS,
        horizon_value=5,
        method_id="unavailable",
        source_label="fixture unavailable",
        source_fingerprint=SOURCE_FP,
        reason_codes=("NO_EVIDENCE",),
    )
    unavailable_result = build_stock_economic_candidate(
        forecast=unavailable,
        inputs=_inputs(),
    )
    assert unavailable_result.candidate is None
    assert unavailable_result.reason_codes[0] == "FORECAST_UNAVAILABLE"

    neutral = _forecast(direction=DiscoveryDirection.NEUTRAL, thresholds=())
    neutral_result = build_stock_economic_candidate(forecast=neutral, inputs=_inputs())
    assert neutral_result.candidate is None
    assert neutral_result.reason_codes[0] == "FORECAST_DIRECTION_NEUTRAL"


def test_negative_economics_are_not_hidden_or_clamped_positive() -> None:
    result = build_stock_economic_candidate(
        forecast=_forecast(mean_signed_return=0.001),
        inputs=_inputs(
            entry_slippage_bps=10.0,
            exit_slippage_bps=10.0,
            round_trip_commission_dollars=5.0,
            round_trip_fees_dollars=5.0,
            horizon_financing_cost_dollars=5.0,
        ),
    )
    assert result.candidate is not None
    assert result.expected_gross_pnl_dollars == pytest.approx(10.0)
    assert result.all_in_expression_cost_dollars == pytest.approx(35.0)
    assert result.expected_net_value_dollars == pytest.approx(-25.0)
    assert result.candidate.preference_score == pytest.approx(-0.005)


def test_capital_required_is_independent_of_position_notional() -> None:
    result = build_stock_economic_candidate(
        forecast=_forecast(),
        inputs=_inputs(capital_required_dollars=2_500.0),
    )
    assert result.position_notional_dollars == pytest.approx(10_000.0)
    assert result.capital_required_dollars == pytest.approx(2_500.0)
    assert result.expected_net_value_dollars == pytest.approx(66.0)
    assert result.expected_return_on_capital == pytest.approx(66.0 / 2_500.0)


def test_all_in_cost_includes_slippage_commissions_fees_borrow_and_financing() -> None:
    result = build_stock_economic_candidate(
        forecast=_forecast(),
        inputs=_inputs(
            entry_slippage_bps=4.0,
            exit_slippage_bps=6.0,
            round_trip_commission_dollars=2.0,
            round_trip_fees_dollars=3.0,
            horizon_borrow_cost_dollars=4.0,
            horizon_financing_cost_dollars=5.0,
        ),
    )
    assert result.slippage_cost_dollars == pytest.approx(10.0)
    assert result.all_in_expression_cost_dollars == pytest.approx(24.0)
    assert result.candidate is not None
    assert result.candidate.execution_cost_dollars == pytest.approx(24.0)


def test_input_validation_rejects_hidden_or_invalid_numeric_assumptions() -> None:
    with pytest.raises(StockEconomicsError, match="non-finite"):
        _inputs(position_notional_dollars=float("nan"))
    with pytest.raises(StockEconomicsError, match="position notional"):
        _inputs(position_notional_dollars=0.0)
    with pytest.raises(StockEconomicsError, match="capital required"):
        _inputs(capital_required_dollars=0.0)
    with pytest.raises(StockEconomicsError, match="slippage"):
        _inputs(entry_slippage_bps=-1.0)
    with pytest.raises(StockEconomicsError, match="cannot be negative"):
        _inputs(horizon_borrow_cost_dollars=-1.0)
    with pytest.raises(StockEconomicsError, match="probability"):
        _inputs(net_probability_profit=1.1)
    with pytest.raises(StockEconomicsError, match="liquidity"):
        _inputs(liquidity_score=1.1)
    with pytest.raises(StockEconomicsError, match="must be boolean"):
        _inputs(executable=1)
