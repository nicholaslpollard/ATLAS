from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from packages.core.settings import load_settings
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    EconomicCandidate,
    InstrumentKind,
    SelectionKind,
    TradeExpressionMode,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
)
from packages.simulation.decision_record import (
    build_simulation_decision_record,
    economic_candidate_fingerprint,
)
from packages.simulation.option_reservation import (
    LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
    LONG_OPTION_RESERVATION_CONTRACT_VERSION,
    LongOptionReservationTerms,
)
from packages.simulation.recurrent_cycle_runner import (
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT,
    RecurrentReserveEvidenceError,
    build_recurrent_reserve_evidence_bundle_v1,
    read_recurrent_reserve_evidence_bundle_v1,
    write_recurrent_reserve_evidence_bundle_v1,
)


SLOT = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
DECIDED = SLOT + timedelta(seconds=5)


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _forecast() -> UnderlyingMoveTimeForecast:
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=SLOT,
        evidence_cutoff_utc=SLOT - timedelta(minutes=1),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=240,
        method_id="accepted-product-fixture-v1",
        source_label="accepted product fixture",
        source_fingerprint="1" * 64,
        sample_size=500,
        reference_price=100.0,
        mean_signed_return=0.01,
        median_signed_return=0.008,
        p10_signed_return=-0.02,
        p25_signed_return=-0.005,
        p75_signed_return=0.02,
        p90_signed_return=0.04,
        probability_positive_return=0.60,
        mean_mfe=0.03,
        mean_mae=0.01,
        thresholds=(
            MoveThresholdProbability(
                threshold_fraction=0.01,
                favorable_touch_probability=0.50,
                adverse_touch_probability=0.20,
                favorable_before_adverse_probability=0.40,
                adverse_before_favorable_probability=0.10,
                same_interval_collision_probability=0.05,
                median_favorable_time=30.0,
            ),
        ),
        uncertainty_score=0.25,
        reason_codes=("ACCEPTED_PRODUCT_FIXTURE",),
    )


def _stock_inputs(*, executable: bool = True):
    return StockEconomicsInputs(
        position_notional_dollars=10_000.0,
        capital_required_dollars=10_000.0,
        entry_slippage_bps=0.0,
        exit_slippage_bps=0.0,
        round_trip_commission_dollars=0.0,
        round_trip_fees_dollars=0.0,
        horizon_borrow_cost_dollars=0.0,
        horizon_financing_cost_dollars=0.0,
        net_probability_profit=0.55,
        liquidity_score=0.90,
        executable=executable,
        risk_budget_ok=True,
    )


def _policy() -> ActionabilityPolicy:
    return ActionabilityPolicy(
        min_expected_net_value=1.0,
        min_expected_return_on_capital=0.001,
        min_probability_profit=0.50,
        max_expected_loss_to_gain_ratio=1.0,
        max_execution_cost_to_expected_gain_ratio=0.50,
        min_liquidity_score=0.50,
        material_superiority_ratio=1.20,
    )


def _stock_record():
    return build_simulation_decision_record(
        decision_created_utc=DECIDED,
        forecast=_forecast(),
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
    )


def _abstain_record():
    return build_simulation_decision_record(
        decision_created_utc=DECIDED + timedelta(seconds=1),
        forecast=_forecast(),
        stock_inputs=_stock_inputs(executable=False),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
    )


def _option_record():
    option = EconomicCandidate(
        identifier="OPTION:AAPL:fixture",
        kind=InstrumentKind.OPTION,
        capital_required=500.0,
        expected_net_value=100.0,
        expected_return_on_capital=0.20,
        probability_profit=0.60,
        expected_gain_dollars=150.0,
        expected_loss_dollars=50.0,
        execution_cost_dollars=5.0,
        liquidity_score=0.90,
        preference_score=0.20,
        executable=True,
        risk_budget_ok=True,
        scenario_complete=True,
        option_contract_complete=True,
        greeks_complete=True,
        iv_context_complete=True,
        liquidity_context_complete=True,
        event_context_complete=True,
    )
    return build_simulation_decision_record(
        decision_created_utc=DECIDED + timedelta(seconds=2),
        forecast=_forecast(),
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.OPTIONS_ONLY,
        option_candidates=(option,),
    )


def _option_terms(record) -> LongOptionReservationTerms:
    chosen = record.trade_expression_decision.chosen_candidate
    assert chosen is not None
    assert record.trade_expression_decision.selection_kind == SelectionKind.OPTION
    return LongOptionReservationTerms(
        contract_version=LONG_OPTION_RESERVATION_CONTRACT_VERSION,
        contract_fingerprint=LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
        decision_record_fingerprint=record.record_fingerprint,
        option_economics_contract_fingerprint="2" * 64,
        option_economics_result_fingerprint="3" * 64,
        chosen_candidate_identifier=chosen.identifier,
        chosen_candidate_fingerprint=economic_candidate_fingerprint(
            chosen
        ),
        option_evidence_fingerprint="4" * 64,
        source_forecast_fingerprint=record.forecast_fingerprint,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction,
        option_contract_ticker="AAPL260925C00100000",
        option_contract_type="call",
        contracts=1,
        contract_multiplier=100.0,
        underlying_reference_price=100.0,
        option_delta=0.50,
        entry_ask_per_share=2.0,
        entry_cash_debit_dollars=200.0,
        cash_fee_reserve_dollars=5.0,
        reserved_capital_dollars=205.0,
        max_loss_cash_dollars=205.0,
        premium_at_risk_dollars=200.0,
        signed_delta_equivalent_notional_dollars=5_000.0,
        abs_delta_equivalent_notional_dollars=5_000.0,
        reason_codes=("TEST_OPTION_TERMS",),
    )


def _identity():
    return build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=SLOT,
    )


def test_recurrent_reserve_evidence_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
        == "e410ab31187b4b35cd5c036ba02073f63de41dd35269f33af4b9ff10357de875"
    )


def test_stock_and_abstain_roundtrip_preserves_exact_records(tmp_path) -> None:
    settings = _settings(tmp_path)
    stock = _stock_record()
    abstain = _abstain_record()
    bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=_identity(),
        decisions=((abstain, None), (stock, None)),
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    assert bundle.decision_count == 2
    assert tuple(
        entry.record.record_fingerprint
        for entry in bundle.entries
    ) == (stock.record_fingerprint, abstain.record_fingerprint)
    assert bundle.entries[0].record.trade_expression_decision.selection_kind == (
        SelectionKind.STOCK
    )
    assert bundle.entries[1].record.trade_expression_decision.selection_kind == (
        SelectionKind.ABSTAIN
    )
    assert bundle.provider_reads == 0
    assert bundle.broker_writes == 0
    assert bundle.paper_authority is False

    path = write_recurrent_reserve_evidence_bundle_v1(
        settings,
        bundle,
    )
    restored = read_recurrent_reserve_evidence_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle
    assert tuple(
        item[0].record_fingerprint
        for item in restored.runner_decisions
    ) == (
        stock.record_fingerprint,
        abstain.record_fingerprint,
    )


def test_selected_option_requires_exact_terms() -> None:
    record = _option_record()
    with pytest.raises(
        RecurrentReserveEvidenceError,
        match="requires exact reservation terms",
    ):
        build_recurrent_reserve_evidence_bundle_v1(
            identity=_identity(),
            decisions=((record, None),),
            built_at_utc=SLOT + timedelta(seconds=10),
        )


def test_selected_option_terms_roundtrip(tmp_path) -> None:
    settings = _settings(tmp_path)
    record = _option_record()
    terms = _option_terms(record)
    bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=_identity(),
        decisions=((record, terms),),
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    path = write_recurrent_reserve_evidence_bundle_v1(
        settings,
        bundle,
    )
    restored = read_recurrent_reserve_evidence_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle
    assert (
        restored.entries[0].option_terms.terms_fingerprint
        == terms.terms_fingerprint
    )


def test_stock_decision_rejects_option_terms() -> None:
    option_record = _option_record()
    terms = _option_terms(option_record)
    with pytest.raises(
        RecurrentReserveEvidenceError,
        match="cannot carry option reservation terms",
    ):
        build_recurrent_reserve_evidence_bundle_v1(
            identity=_identity(),
            decisions=((_stock_record(), terms),),
            built_at_utc=SLOT + timedelta(seconds=10),
        )


def test_future_decision_relative_to_bundle_fails_closed() -> None:
    with pytest.raises(
        RecurrentReserveEvidenceError,
        match="future decision",
    ):
        build_recurrent_reserve_evidence_bundle_v1(
            identity=_identity(),
            decisions=((_stock_record(), None),),
            built_at_utc=SLOT + timedelta(seconds=1),
        )


def test_tampered_bundle_fingerprint_fails_read(tmp_path) -> None:
    settings = _settings(tmp_path)
    bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=_identity(),
        decisions=((_stock_record(), None),),
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    path = write_recurrent_reserve_evidence_bundle_v1(
        settings,
        bundle,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bundle_fingerprint"] = "0" * 64
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        RecurrentReserveEvidenceError,
        match="self-fingerprint mismatch",
    ):
        read_recurrent_reserve_evidence_bundle_v1(
            settings,
            path=path,
        )
