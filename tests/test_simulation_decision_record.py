from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.stock_economics_contract import STOCK_ECONOMICS_CONTRACT_FINGERPRINT
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    EconomicCandidate,
    InstrumentKind,
    SelectionKind,
    TradeExpressionMode,
)
from packages.execution.trade_expression_contract import TRADE_EXPRESSION_CONTRACT_FINGERPRINT
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
)
from packages.schemas.move_time_forecast_contract import MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
from packages.simulation.decision_record import (
    SIMULATION_DECISION_RECORD_CONTRACT_VERSION,
    SimulationDecisionRecordError,
    actionability_policy_fingerprint,
    build_simulation_decision_record,
    economic_candidate_fingerprint,
    simulation_decision_record_payload,
)
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT,
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)


CREATED = datetime(2026, 9, 16, 3, 0, tzinfo=UTC)
DECIDED = CREATED + timedelta(minutes=1)
CUTOFF = CREATED - timedelta(minutes=1)
SOURCE_FP = "3" * 64


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


def _stock_inputs(**overrides: object) -> StockEconomicsInputs:
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


def _policy(**overrides: object) -> ActionabilityPolicy:
    payload: dict[str, object] = {
        "min_expected_net_value": 50.0,
        "min_expected_return_on_capital": 0.01,
        "min_probability_profit": 0.45,
        "max_expected_loss_to_gain_ratio": 0.50,
        "max_execution_cost_to_expected_gain_ratio": 0.10,
        "min_liquidity_score": 0.80,
        "material_superiority_ratio": 1.25,
    }
    payload.update(overrides)
    return ActionabilityPolicy(**payload)


def _option(identifier: str, preference_score: float = 0.020) -> EconomicCandidate:
    return EconomicCandidate(
        identifier=identifier,
        kind=InstrumentKind.OPTION,
        capital_required=1_000.0,
        expected_net_value=60.0,
        expected_return_on_capital=0.060,
        probability_profit=0.52,
        expected_gain_dollars=100.0,
        expected_loss_dollars=40.0,
        execution_cost_dollars=5.0,
        liquidity_score=0.90,
        preference_score=preference_score,
        executable=True,
        risk_budget_ok=True,
        scenario_complete=True,
        option_contract_complete=True,
        greeks_complete=True,
        iv_context_complete=True,
        liquidity_context_complete=True,
        event_context_complete=True,
    )


def _record(**overrides: object):
    payload: dict[str, object] = {
        "decision_created_utc": DECIDED,
        "forecast": _forecast(),
        "stock_inputs": _stock_inputs(),
        "actionability_policy": _policy(),
        "trade_expression_mode": TradeExpressionMode.STOCKS_ONLY,
        "option_candidates": (),
    }
    payload.update(overrides)
    return build_simulation_decision_record(**payload)


def test_contract_identity_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT
    assert SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT == (
        "62dceacde38687828e610c096d8c0a39479d5bc65b26b56aed2bf4164d8c8af8"
    )
    assert SIMULATION_DECISION_RECORD_CONTRACT_VERSION == "atlas-simulation-decision-record-v1"
    assert SIMULATION_DECISION_RECORD_CONTRACT["provider_reads"] == 0
    assert SIMULATION_DECISION_RECORD_CONTRACT["broker_reads"] == 0
    assert SIMULATION_DECISION_RECORD_CONTRACT["broker_writes"] == 0
    assert SIMULATION_DECISION_RECORD_CONTRACT["order_creation_authority"] is False
    assert SIMULATION_DECISION_RECORD_CONTRACT["paper_authority"] is False
    assert SIMULATION_DECISION_RECORD_CONTRACT["live_authority"] is False
    assert SIMULATION_DECISION_RECORD_CONTRACT["promotion_authority"] is False
    assert SIMULATION_DECISION_RECORD_CONTRACT["confluence_authority"] is False


def test_stock_only_record_is_deterministic_and_preserves_complete_lineage() -> None:
    first = _record()
    second = _record()
    assert first.record_fingerprint == second.record_fingerprint
    assert len(first.record_fingerprint) == 64
    assert first.forecast_contract_fingerprint == MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
    assert first.stock_economics_contract_fingerprint == STOCK_ECONOMICS_CONTRACT_FINGERPRINT
    assert first.trade_expression_contract_fingerprint == TRADE_EXPRESSION_CONTRACT_FINGERPRINT
    assert first.actionability_policy_fingerprint == actionability_policy_fingerprint(_policy())
    assert first.stock_economics.candidate is not None
    assert first.trade_expression_decision.selection_kind == SelectionKind.STOCK
    assert first.reason_lineage.stock_gate_evaluated is True
    assert first.reason_lineage.stock_gate_eligible is True
    assert "ECONOMIC_GATE_ACCEPTED" in first.reason_lineage.stock_gate_reason_codes
    assert first.stock_inputs.entry_slippage_bps == 5.0
    payload = simulation_decision_record_payload(first)
    assert payload["record_fingerprint"] == first.record_fingerprint
    assert payload["trade_expression_mode"] == "STOCKS_ONLY"


def test_negative_stock_economics_flow_to_auditable_abstention() -> None:
    record = _record(
        forecast=_forecast(mean_signed_return=0.001),
        actionability_policy=_policy(min_expected_net_value=0.0),
        stock_inputs=_stock_inputs(
            entry_slippage_bps=10.0,
            exit_slippage_bps=10.0,
            round_trip_commission_dollars=5.0,
            round_trip_fees_dollars=5.0,
            horizon_financing_cost_dollars=5.0,
        ),
    )
    assert record.stock_economics.expected_net_value_dollars == pytest.approx(-25.0)
    assert record.trade_expression_decision.selection_kind == SelectionKind.ABSTAIN
    assert record.reason_lineage.stock_gate_eligible is False
    assert "EXPECTED_NET_VALUE_BELOW_POLICY" in record.reason_lineage.stock_gate_reason_codes
    assert "ABSTAIN" in record.reason_lineage.selection_reason_codes


def test_options_only_preserves_viable_stock_but_marks_stock_gate_not_evaluated() -> None:
    record = _record(trade_expression_mode=TradeExpressionMode.OPTIONS_ONLY)
    assert record.stock_economics.candidate is not None
    assert record.reason_lineage.stock_gate_evaluated is False
    assert record.reason_lineage.stock_gate_eligible is None
    assert record.reason_lineage.stock_gate_reason_codes == (
        "STOCK_GATE_NOT_EVALUATED_BY_MODE_OR_ABSENT",
    )
    assert record.trade_expression_decision.selection_kind == SelectionKind.ABSTAIN
    assert "OPTIONS_ONLY_NO_ACCEPTABLE_OPTION" in record.reason_lineage.selection_reason_codes


def test_preferred_mode_can_select_materially_superior_option() -> None:
    option = _option("OPT-XYZ-A")
    record = _record(
        trade_expression_mode=TradeExpressionMode.STOCKS_PREFERRED,
        option_candidates=(option,),
    )
    assert record.trade_expression_decision.selection_kind == SelectionKind.OPTION
    assert record.trade_expression_decision.chosen_identifier == "OPT-XYZ-A"
    assert "ALTERNATE_EXPRESSION_MATERIALLY_SUPERIOR" in (
        record.reason_lineage.selection_reason_codes
    )
    assert len(record.reason_lineage.option_gate_lineage) == 1
    option_line = record.reason_lineage.option_gate_lineage[0]
    assert option_line.evaluated is True
    assert option_line.eligible is True
    assert option_line.candidate_fingerprint == economic_candidate_fingerprint(option)


def test_stocks_only_preserves_option_inputs_but_marks_option_gates_not_evaluated() -> None:
    option = _option("OPT-XYZ-A")
    record = _record(
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(option,),
    )
    assert record.trade_expression_decision.selection_kind == SelectionKind.STOCK
    line = record.reason_lineage.option_gate_lineage[0]
    assert line.evaluated is False
    assert line.eligible is None
    assert line.reason_codes == ("OPTION_GATE_NOT_EVALUATED_BY_MODE",)


def test_option_input_order_is_normalized_for_identical_record_and_selection() -> None:
    option_a = _option("OPT-A", preference_score=0.021)
    option_b = _option("OPT-B", preference_score=0.020)
    first = _record(
        trade_expression_mode=TradeExpressionMode.OPTIONS_ONLY,
        option_candidates=(option_b, option_a),
    )
    second = _record(
        trade_expression_mode=TradeExpressionMode.OPTIONS_ONLY,
        option_candidates=(option_a, option_b),
    )
    assert [candidate.identifier for candidate in first.option_candidates] == ["OPT-A", "OPT-B"]
    assert first.record_fingerprint == second.record_fingerprint
    assert first.trade_expression_decision.chosen_identifier == "OPT-A"
    assert second.trade_expression_decision.chosen_identifier == "OPT-A"


def test_mode_policy_and_timestamp_are_fingerprint_material() -> None:
    baseline = _record()
    mode_changed = _record(trade_expression_mode=TradeExpressionMode.STOCKS_PREFERRED)
    policy_changed = _record(actionability_policy=_policy(min_expected_net_value=55.0))
    time_changed = _record(decision_created_utc=DECIDED + timedelta(seconds=1))
    assert baseline.record_fingerprint != mode_changed.record_fingerprint
    assert baseline.record_fingerprint != policy_changed.record_fingerprint
    assert baseline.record_fingerprint != time_changed.record_fingerprint


def test_unavailable_and_neutral_forecasts_flow_to_abstention_with_lineage() -> None:
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
    unavailable_record = _record(forecast=unavailable)
    assert unavailable_record.stock_economics.candidate is None
    assert unavailable_record.reason_lineage.stock_economics_reason_codes[0] == "FORECAST_UNAVAILABLE"
    assert unavailable_record.trade_expression_decision.selection_kind == SelectionKind.ABSTAIN

    neutral = _forecast(direction=DiscoveryDirection.NEUTRAL, thresholds=())
    neutral_record = _record(forecast=neutral)
    assert neutral_record.stock_economics.candidate is None
    assert neutral_record.reason_lineage.stock_economics_reason_codes[0] == "FORECAST_DIRECTION_NEUTRAL"
    assert neutral_record.trade_expression_decision.selection_kind == SelectionKind.ABSTAIN


def test_decision_timestamp_must_be_timezone_aware_and_not_precede_forecast() -> None:
    with pytest.raises(SimulationDecisionRecordError, match="timezone-aware"):
        _record(decision_created_utc=datetime(2026, 9, 16, 3, 1))
    with pytest.raises(SimulationDecisionRecordError, match="cannot precede"):
        _record(decision_created_utc=CREATED - timedelta(seconds=1))


def test_duplicate_or_non_option_option_inputs_are_rejected() -> None:
    option = _option("OPT-DUP")
    with pytest.raises(SimulationDecisionRecordError, match="duplicate"):
        _record(option_candidates=(option, option))

    stock = EconomicCandidate(
        identifier="STOCK-INVALID",
        kind=InstrumentKind.STOCK,
        capital_required=1_000.0,
        expected_net_value=20.0,
        expected_return_on_capital=0.02,
        probability_profit=0.52,
        expected_gain_dollars=100.0,
        expected_loss_dollars=40.0,
        execution_cost_dollars=5.0,
        liquidity_score=0.90,
        preference_score=0.02,
        executable=True,
        risk_budget_ok=True,
        scenario_complete=True,
    )
    with pytest.raises(SimulationDecisionRecordError, match="only OPTION"):
        _record(option_candidates=(stock,))


def test_record_cannot_grant_authority() -> None:
    record = _record()
    assert record.provider_read_authority is False
    assert record.provider_write_authority is False
    assert record.broker_read_authority is False
    assert record.broker_write_authority is False
    assert record.order_creation_authority is False
    assert record.paper_authority is False
    assert record.live_authority is False
    assert record.promotion_authority is False
    assert record.confluence_authority is False
