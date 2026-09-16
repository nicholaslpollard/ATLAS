from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from packages.execution.option_economics import (
    OPTION_ECONOMICS_CONTRACT_VERSION,
    OptionEconomicsError,
    OptionEconomicsInputs,
    build_option_economic_candidate,
)
from packages.execution.option_economics_contract import (
    OPTION_ECONOMICS_CONTRACT,
    OPTION_ECONOMICS_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    InstrumentKind,
    evaluate_actionability,
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


CREATED = datetime(2026, 9, 16, 4, 0, tzinfo=UTC)
CUTOFF = CREATED - timedelta(minutes=1)
SOURCE_FP = "2" * 64
SCENARIO_FP = "3" * 64
EVENT_FP = "4" * 64


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


def _option(**overrides: object) -> OptionCandidateEvidence:
    payload: dict[str, object] = {
        "contract_ticker": "O:XYZ261016C00100000",
        "contract_type": "call",
        "expiration_date": date(2026, 10, 16),
        "dte": 30,
        "strike": 100.0,
        "bid": 4.8,
        "ask": 5.2,
        "mid": 5.0,
        "spread_to_mid": 0.08,
        "open_interest": 1_000,
        "volume": 200,
        "delta": 0.55,
        "implied_volatility": 0.30,
        "eligible": True,
        "reason_codes": ("FIXTURE_OPTION",),
    }
    payload.update(overrides)
    return OptionCandidateEvidence(**payload)


def _inputs(forecast: UnderlyingMoveTimeForecast, **overrides: object) -> OptionEconomicsInputs:
    payload: dict[str, object] = {
        "contracts": 2,
        "contract_multiplier": 100.0,
        "capital_required_dollars": 1_040.0,
        "holding_period_calendar_days": 5.0,
        "expected_terminal_premium_per_share": 6.2,
        "favorable_terminal_premium_per_share": 8.0,
        "adverse_terminal_premium_per_share": 2.5,
        "model_probability_profit": 0.58,
        "scenario_model_id": "fixture-option-scenario-v1",
        "scenario_model_fingerprint": SCENARIO_FP,
        "scenario_forecast_fingerprint": forecast_fingerprint(forecast),
        "gamma": 0.04,
        "theta_per_calendar_day": -0.08,
        "vega_per_one_iv_fraction": 12.0,
        "iv_percentile": 0.60,
        "skew_signal": -0.10,
        "term_structure_signal": 0.05,
        "risk_free_rate": 0.04,
        "dividend_yield": 0.01,
        "event_within_horizon": False,
        "event_risk_acceptable": True,
        "event_context_fingerprint": EVENT_FP,
        "liquidity_score": 0.90,
        "exit_slippage_dollars": 8.0,
        "round_trip_commission_dollars": 2.0,
        "round_trip_fees_dollars": 1.0,
        "executable": True,
        "risk_budget_ok": True,
        "model_reference_premium_per_share": 5.5,
    }
    payload.update(overrides)
    return OptionEconomicsInputs(**payload)


def test_contract_fingerprint_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == OPTION_ECONOMICS_CONTRACT_FINGERPRINT
    assert OPTION_ECONOMICS_CONTRACT_FINGERPRINT == (
        "b18b7e1388cd58518a5261143fdffa2f81b46d2366162a6074f113a31ea2ca33"
    )
    assert OPTION_ECONOMICS_CONTRACT_VERSION == "atlas-option-scenario-economics-adapter-v1"
    assert OPTION_ECONOMICS_CONTRACT["capital_required_floor"] == "entry_cash_debit"
    assert OPTION_ECONOMICS_CONTRACT["historical_option_pnl_claimed"] is False
    assert OPTION_ECONOMICS_CONTRACT["capital_required_is_simulator_reservation_authority"] is False
    assert OPTION_ECONOMICS_CONTRACT["provider_reads"] == 0
    assert OPTION_ECONOMICS_CONTRACT["broker_reads"] == 0
    assert OPTION_ECONOMICS_CONTRACT["broker_writes"] == 0
    assert OPTION_ECONOMICS_CONTRACT["paper_authority"] is False
    assert OPTION_ECONOMICS_CONTRACT["live_authority"] is False
    assert OPTION_ECONOMICS_CONTRACT["promotion_authority"] is False


def test_bullish_call_builds_deterministic_scenario_economics() -> None:
    forecast = _forecast()
    result = build_option_economic_candidate(
        forecast=forecast,
        option=_option(),
        inputs=_inputs(forecast),
    )
    assert result.source_forecast_fingerprint == forecast_fingerprint(forecast)
    assert result.entry_cash_debit_dollars == pytest.approx(1_040.0)
    assert result.entry_spread_cost_dollars == pytest.approx(40.0)
    assert result.expected_gross_pnl_dollars == pytest.approx(240.0)
    assert result.all_in_expression_cost_dollars == pytest.approx(51.0)
    assert result.expected_net_value_dollars == pytest.approx(189.0)
    assert result.expected_return_on_capital == pytest.approx(189.0 / 1_040.0)
    assert result.expected_gain_dollars == pytest.approx(600.0)
    assert result.expected_loss_dollars == pytest.approx(500.0)
    assert result.model_relative_undervalued is True
    assert result.scenario_complete is True
    assert result.candidate is not None
    assert result.candidate.kind == InstrumentKind.OPTION
    assert result.candidate.expected_net_value == pytest.approx(189.0)
    assert result.candidate.execution_cost_dollars == pytest.approx(51.0)
    assert result.candidate.model_relative_undervalued is True
    assert result.candidate.identifier.startswith("OPTION:O:XYZ261016C00100000:")
    assert "CAPITAL_AT_LEAST_LONG_OPTION_ASK_DEBIT" in result.reason_codes


def test_complete_option_candidate_interoperates_with_universal_gate() -> None:
    forecast = _forecast()
    candidate = build_option_economic_candidate(
        forecast=forecast,
        option=_option(),
        inputs=_inputs(forecast),
    ).candidate
    assert candidate is not None
    policy = ActionabilityPolicy(
        min_expected_net_value=100.0,
        min_expected_return_on_capital=0.10,
        min_probability_profit=0.55,
        max_expected_loss_to_gain_ratio=0.90,
        max_execution_cost_to_expected_gain_ratio=0.10,
        min_liquidity_score=0.85,
        material_superiority_ratio=1.25,
    )
    evaluation = evaluate_actionability(candidate, policy)
    assert evaluation.eligible is True
    assert "MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY" in evaluation.reason_codes
    assert "ECONOMIC_GATE_ACCEPTED" in evaluation.reason_codes


def test_bearish_put_is_direction_aligned_and_supported() -> None:
    forecast = _forecast(
        direction=DiscoveryDirection.BEARISH,
        mean_signed_return=-0.012,
        median_signed_return=-0.008,
        p10_signed_return=-0.045,
        p25_signed_return=-0.022,
        p75_signed_return=0.006,
        p90_signed_return=0.018,
        probability_positive_return=0.34,
        mean_mfe=0.030,
        mean_mae=0.012,
    )
    option = _option(
        contract_ticker="O:XYZ261016P00100000",
        contract_type="put",
        delta=-0.45,
    )
    result = build_option_economic_candidate(
        forecast=forecast,
        option=option,
        inputs=_inputs(forecast),
    )
    assert result.candidate is not None
    assert result.candidate.kind == InstrumentKind.OPTION
    assert "OPTION_DIRECTION_ALIGNED" in result.reason_codes


def test_direction_mismatch_does_not_create_candidate() -> None:
    forecast = _forecast(direction=DiscoveryDirection.BEARISH)
    result = build_option_economic_candidate(
        forecast=forecast,
        option=_option(contract_type="call"),
        inputs=_inputs(forecast),
    )
    assert result.candidate is None
    assert result.reason_codes[0] == "OPTION_DIRECTION_MISMATCH"


def test_unavailable_and_neutral_forecasts_do_not_create_candidates() -> None:
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
    result = build_option_economic_candidate(
        forecast=unavailable,
        option=_option(),
        inputs=_inputs(unavailable),
    )
    assert result.candidate is None
    assert result.reason_codes[0] == "FORECAST_UNAVAILABLE"

    neutral = _forecast(direction=DiscoveryDirection.NEUTRAL, thresholds=())
    neutral_result = build_option_economic_candidate(
        forecast=neutral,
        option=_option(),
        inputs=_inputs(neutral),
    )
    assert neutral_result.candidate is None
    assert neutral_result.reason_codes[0] == "FORECAST_DIRECTION_NEUTRAL"


def test_scenario_model_must_be_bound_to_exact_forecast_instance() -> None:
    forecast = _forecast()
    with pytest.raises(OptionEconomicsError, match="does not match"):
        build_option_economic_candidate(
            forecast=forecast,
            option=_option(),
            inputs=_inputs(forecast, scenario_forecast_fingerprint="f" * 64),
        )


def test_long_option_capital_cannot_be_below_ask_debit() -> None:
    forecast = _forecast()
    with pytest.raises(OptionEconomicsError, match="below the long-option ask debit"):
        build_option_economic_candidate(
            forecast=forecast,
            option=_option(),
            inputs=_inputs(forecast, capital_required_dollars=1_039.99),
        )


def test_incomplete_greeks_are_preserved_for_gate_rejection() -> None:
    forecast = _forecast()
    result = build_option_economic_candidate(
        forecast=forecast,
        option=_option(delta=None),
        inputs=_inputs(forecast, gamma=None),
    )
    assert result.candidate is not None
    assert result.greeks_complete is False
    assert result.scenario_complete is False
    evaluation = evaluate_actionability(
        result.candidate,
        ActionabilityPolicy(
            min_expected_net_value=0.0,
            min_expected_return_on_capital=0.0,
            min_probability_profit=0.0,
            max_expected_loss_to_gain_ratio=10.0,
            max_execution_cost_to_expected_gain_ratio=10.0,
            min_liquidity_score=0.0,
            material_superiority_ratio=1.0,
        ),
    )
    assert evaluation.eligible is False
    assert "OPTION_GREEKS_INCOMPLETE" in evaluation.reason_codes
    assert "SCENARIO_EVIDENCE_INCOMPLETE" in evaluation.reason_codes


def test_upstream_option_screen_and_event_risk_can_make_candidate_nonexecutable() -> None:
    forecast = _forecast()
    screened = build_option_economic_candidate(
        forecast=forecast,
        option=_option(eligible=False),
        inputs=_inputs(forecast),
    )
    assert screened.candidate is not None
    assert screened.candidate.executable is False
    assert "UPSTREAM_OPTION_SCREEN_REJECTED" in screened.reason_codes

    event_blocked = build_option_economic_candidate(
        forecast=forecast,
        option=_option(),
        inputs=_inputs(
            forecast,
            event_within_horizon=True,
            event_risk_acceptable=False,
        ),
    )
    assert event_blocked.candidate is not None
    assert event_blocked.candidate.executable is False
    assert "EVENT_RISK_NOT_ACCEPTED" in event_blocked.reason_codes


def test_negative_option_economics_are_not_hidden_or_clamped_positive() -> None:
    forecast = _forecast()
    result = build_option_economic_candidate(
        forecast=forecast,
        option=_option(),
        inputs=_inputs(
            forecast,
            expected_terminal_premium_per_share=4.9,
            favorable_terminal_premium_per_share=5.5,
            adverse_terminal_premium_per_share=3.0,
            model_reference_premium_per_share=4.7,
        ),
    )
    assert result.expected_gross_pnl_dollars == pytest.approx(-20.0)
    assert result.all_in_expression_cost_dollars == pytest.approx(51.0)
    assert result.expected_net_value_dollars == pytest.approx(-71.0)
    assert result.candidate is not None
    assert result.candidate.preference_score == pytest.approx(-71.0 / 1_040.0)
    assert result.model_relative_undervalued is False


def test_input_and_holding_period_validation_fail_closed() -> None:
    forecast = _forecast()
    with pytest.raises(OptionEconomicsError, match="scenario terminal premiums"):
        _inputs(
            forecast,
            adverse_terminal_premium_per_share=7.0,
            expected_terminal_premium_per_share=6.0,
            favorable_terminal_premium_per_share=8.0,
        )
    with pytest.raises(OptionEconomicsError, match="costs cannot be negative"):
        _inputs(forecast, exit_slippage_dollars=-1.0)
    with pytest.raises(OptionEconomicsError, match="fingerprint"):
        _inputs(forecast, scenario_model_fingerprint="bad")
    with pytest.raises(OptionEconomicsError, match="IV percentile"):
        _inputs(forecast, iv_percentile=1.1)
    with pytest.raises(OptionEconomicsError, match="cannot exceed option DTE"):
        build_option_economic_candidate(
            forecast=forecast,
            option=_option(dte=3),
            inputs=_inputs(forecast, holding_period_calendar_days=5.0),
        )
