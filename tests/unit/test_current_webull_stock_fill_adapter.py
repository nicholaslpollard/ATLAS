from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.enums import SessionSegment
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteV1,
    build_current_webull_stock_quote_bundle_v1,
)
from packages.execution.current_webull_stock_fill_adapter import (
    CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT,
    CurrentWebullStockFillAdapterError,
    ExplicitStockEntryFeeV1,
    ExplicitStockExitFeeV1,
    build_current_webull_stock_entries_v1,
    build_current_webull_stock_exits_v1,
)
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
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
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)


BASE = datetime(2026, 8, 24, 14, 50, tzinfo=UTC)
DECIDED = datetime(2026, 8, 24, 14, 55, tzinfo=UTC)
ENTRY_TIME = datetime(2026, 8, 24, 15, 0, 2, tzinfo=UTC)


def _forecast() -> UnderlyingMoveTimeForecast:
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=DECIDED - timedelta(seconds=5),
        evidence_cutoff_utc=DECIDED - timedelta(minutes=1),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=390,
        method_id="fixture-current-stock-entry",
        source_label="fixture accepted forecast",
        source_fingerprint="1" * 64,
        sample_size=1_000,
        reference_price=100.0,
        mean_signed_return=0.008,
        median_signed_return=0.005,
        p10_signed_return=-0.020,
        p25_signed_return=-0.006,
        p75_signed_return=0.018,
        p90_signed_return=0.035,
        probability_positive_return=0.58,
        mean_mfe=0.022,
        mean_mae=0.009,
        thresholds=(
            MoveThresholdProbability(
                threshold_fraction=0.01,
                favorable_touch_probability=0.40,
                adverse_touch_probability=0.25,
                favorable_before_adverse_probability=0.35,
                adverse_before_favorable_probability=0.15,
                same_interval_collision_probability=0.0,
                median_favorable_time=8.0,
            ),
        ),
        uncertainty_score=0.30,
        reason_codes=("FIXTURE",),
    )


def _record():
    return build_simulation_decision_record(
        decision_created_utc=DECIDED,
        forecast=_forecast(),
        stock_inputs=StockEconomicsInputs(
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
            shortable_if_bearish=False,
        ),
        actionability_policy=ActionabilityPolicy(
            min_expected_net_value=10.0,
            min_expected_return_on_capital=0.001,
            min_probability_profit=0.45,
            max_expected_loss_to_gain_ratio=0.50,
            max_execution_cost_to_expected_gain_ratio=0.10,
            min_liquidity_score=0.80,
            material_superiority_ratio=1.25,
        ),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
    )


def _runtime(tmp_path):
    checkpoint = tmp_path / "current.json"
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=BASE,
    )
    record = _record()
    runtime.apply_reservation(record=record)
    return runtime, record


def _bundle(
    *,
    provider_time: datetime,
    bid: float,
    ask: float,
):
    quote = CurrentWebullStockQuoteV1(
        symbol="AAPL",
        provider_timestamp_utc=provider_time,
        received_at_utc=provider_time + timedelta(seconds=1),
        session_date=provider_time.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=bid,
        bid_size=10,
        ask_price=ask,
        ask_size=12,
    )
    return build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(quote,),
        captured_at_utc=provider_time + timedelta(seconds=1),
    )


def test_current_webull_stock_fill_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT
        == "8fde1fd17b9eceabb9ef57271948995088ed049eb22b46ab15bc0f734a3a021c"
    )


def test_webull_ask_builds_stock_entry_and_funding(tmp_path) -> None:
    runtime, record = _runtime(tmp_path)
    bundle = _bundle(
        provider_time=ENTRY_TIME - timedelta(seconds=2),
        bid=101.0,
        ask=101.1,
    )
    batch = build_current_webull_stock_entries_v1(
        bundle=bundle,
        account=runtime.current_account(),
        records=(record,),
        fees=(
            ExplicitStockEntryFeeV1(
                decision_record_fingerprint=record.record_fingerprint,
                entry_fees_dollars=2.0,
            ),
        ),
        valuation_utc=ENTRY_TIME,
    )
    assert len(batch.entries) == 1
    fill, funding = batch.entries[0]
    assert fill.fill_price_per_unit == pytest.approx(101.1)
    assert fill.entry_fees_dollars == pytest.approx(2.0)
    assert fill.fill_source_fingerprint == bundle.bundle_fingerprint
    assert funding.fully_funded is True
    assert batch.provider_read_authority is False
    assert batch.broker_fill_authority is False
    assert len(batch.batch_fingerprint) == 64


def test_webull_bid_builds_full_stock_exit_with_explicit_fee(tmp_path) -> None:
    runtime, record = _runtime(tmp_path)
    entry_bundle = _bundle(
        provider_time=ENTRY_TIME - timedelta(seconds=2),
        bid=101.0,
        ask=101.1,
    )
    entry_batch = build_current_webull_stock_entries_v1(
        bundle=entry_bundle,
        account=runtime.current_account(),
        records=(record,),
        fees=(
            ExplicitStockEntryFeeV1(
                decision_record_fingerprint=record.record_fingerprint,
                entry_fees_dollars=2.0,
            ),
        ),
        valuation_utc=ENTRY_TIME,
    )
    runtime.apply_entry_batch(entry_batch.entries)
    position = runtime.current_account().state.open_positions[0]

    exit_time = ENTRY_TIME + timedelta(minutes=1)
    exit_bundle = _bundle(
        provider_time=exit_time - timedelta(seconds=2),
        bid=102.0,
        ask=102.1,
    )
    exit_batch = build_current_webull_stock_exits_v1(
        bundle=exit_bundle,
        account=runtime.current_account(),
        fees=(
            ExplicitStockExitFeeV1(
                position_fingerprint=position.position_fingerprint,
                exit_fees_dollars=1.0,
            ),
        ),
        valuation_utc=exit_time,
    )
    assert len(exit_batch.fills) == 1
    fill = exit_batch.fills[0]
    assert fill.exit_price_per_unit == pytest.approx(102.0)
    assert fill.exit_fees_dollars == pytest.approx(1.0)
    assert fill.full_close is True
    assert fill.fill_source_fingerprint == exit_bundle.bundle_fingerprint
    assert exit_batch.broker_fill_authority is False


def test_entry_fee_input_must_reference_supplied_record(tmp_path) -> None:
    runtime, _record_value = _runtime(tmp_path)
    bundle = _bundle(
        provider_time=ENTRY_TIME - timedelta(seconds=2),
        bid=101.0,
        ask=101.1,
    )
    with pytest.raises(
        CurrentWebullStockFillAdapterError,
        match="missing decision record",
    ):
        build_current_webull_stock_entries_v1(
            bundle=bundle,
            account=runtime.current_account(),
            records=(),
            fees=(
                ExplicitStockEntryFeeV1(
                    decision_record_fingerprint="f" * 64,
                    entry_fees_dollars=0.0,
                ),
            ),
            valuation_utc=ENTRY_TIME,
        )


def test_stale_webull_quote_cannot_create_entry(tmp_path) -> None:
    runtime, record = _runtime(tmp_path)
    bundle = _bundle(
        provider_time=ENTRY_TIME - timedelta(seconds=31),
        bid=101.0,
        ask=101.1,
    )
    with pytest.raises(
        CurrentWebullStockFillAdapterError,
        match="execution age cap",
    ):
        build_current_webull_stock_entries_v1(
            bundle=bundle,
            account=runtime.current_account(),
            records=(record,),
            fees=(
                ExplicitStockEntryFeeV1(
                    decision_record_fingerprint=record.record_fingerprint,
                    entry_fees_dollars=2.0,
                ),
            ),
            valuation_utc=ENTRY_TIME,
        )
