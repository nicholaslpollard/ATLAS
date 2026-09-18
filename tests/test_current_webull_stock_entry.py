from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from packages.core.enums import SessionSegment
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteV1,
    build_current_webull_stock_quote_bundle_v1,
)
from packages.execution.current_webull_stock_entry import (
    CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT,
    CurrentWebullStockEntryEvidenceError,
    CurrentWebullStockEntryPairV1,
    build_current_webull_stock_entry_evidence_bundle_v1,
    read_current_webull_stock_entry_evidence_bundle_v1,
    write_current_webull_stock_entry_evidence_bundle_v1,
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
from packages.simulation.recurrent_cycle_runner import (
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    build_recurrent_reserve_evidence_bundle_v1,
)


SLOT = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
FEE_SOURCE_FP = "f" * 64


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _forecast(
    ticker: str,
    *,
    source_char: str,
) -> UnderlyingMoveTimeForecast:
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=f"iid-{ticker}",
        ticker=ticker,
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=SLOT + timedelta(seconds=1),
        evidence_cutoff_utc=SLOT,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=240,
        method_id="accepted-product-fixture-v1",
        source_label="accepted product fixture",
        source_fingerprint=source_char * 64,
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


def _record(
    ticker: str = "AAPL",
    *,
    source_char: str = "1",
    decision_offset_seconds: int = 2,
    notional: float = 10_000.0,
):
    return build_simulation_decision_record(
        decision_created_utc=(
            SLOT + timedelta(seconds=decision_offset_seconds)
        ),
        forecast=_forecast(
            ticker,
            source_char=source_char,
        ),
        stock_inputs=StockEconomicsInputs(
            position_notional_dollars=notional,
            capital_required_dollars=notional,
            entry_slippage_bps=0.0,
            exit_slippage_bps=0.0,
            round_trip_commission_dollars=0.0,
            round_trip_fees_dollars=0.0,
            horizon_borrow_cost_dollars=0.0,
            horizon_financing_cost_dollars=0.0,
            net_probability_profit=0.55,
            liquidity_score=0.90,
            executable=True,
            risk_budget_ok=True,
        ),
        actionability_policy=ActionabilityPolicy(
            min_expected_net_value=1.0,
            min_expected_return_on_capital=0.001,
            min_probability_profit=0.50,
            max_expected_loss_to_gain_ratio=1.0,
            max_execution_cost_to_expected_gain_ratio=0.50,
            min_liquidity_score=0.50,
            material_superiority_ratio=1.20,
        ),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
    )


def _identity():
    return build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=SLOT,
    )


def _runtime_with_reservations(
    settings,
    records,
    *,
    initial_equity: float = 100_000.0,
):
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=initial_equity,
        as_of_utc=SLOT,
    )
    reserve_bundle = build_recurrent_reserve_evidence_bundle_v1(
        identity=_identity(),
        decisions=tuple((record, None) for record in records),
        built_at_utc=SLOT + timedelta(seconds=5),
    )
    runtime.apply_reservation_batch(
        reserve_bundle.runner_decisions
    )
    return runtime, reserve_bundle


def _quote(
    ticker: str,
    *,
    bid: float = 100.0,
    ask: float = 100.1,
    received_offset_seconds: int = 8,
):
    received = SLOT + timedelta(
        seconds=received_offset_seconds
    )
    provider = received - timedelta(seconds=1)
    return CurrentWebullStockQuoteV1(
        symbol=ticker,
        provider_timestamp_utc=provider,
        received_at_utc=received,
        session_date=provider.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=bid,
        bid_size=10,
        ask_price=ask,
        ask_size=12,
    )


def _quote_bundle(*quotes):
    return build_current_webull_stock_quote_bundle_v1(
        requested_symbols=tuple(
            quote.symbol for quote in quotes
        ),
        quotes=quotes,
        captured_at_utc=SLOT + timedelta(seconds=9),
    )


def test_current_webull_stock_entry_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT
        == "2a5635ce3cffff6eadeda16a2857a6b71acfb6daa267f786caa9e2aa803d070d"
    )


def test_stock_entry_uses_ask_and_roundtrips(tmp_path) -> None:
    settings = _settings(tmp_path)
    record = _record()
    runtime, reserve_bundle = _runtime_with_reservations(
        settings,
        (record,),
    )
    account = runtime.current_account()
    quotes = _quote_bundle(
        _quote("AAPL", bid=100.0, ask=100.25)
    )
    bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=account,
        reserve_bundle=reserve_bundle,
        quote_bundle=quotes,
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 2.50,
        },
        fee_source_id="explicit-test-fees-v1",
        fee_source_fingerprint=FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    assert len(bundle.pairs) == 1
    pair = bundle.pairs[0]
    assert pair.fill.fill_price_per_unit == pytest.approx(100.25)
    assert pair.fill.entry_fees_dollars == pytest.approx(2.50)
    assert pair.funding.fully_funded is True
    assert (
        pair.funding.supplemental_unreserved_cash_required_dollars
        == pytest.approx(2.50)
    )
    assert bundle.provider_calls_performed == 0
    assert bundle.broker_calls_performed == 0
    assert bundle.paper_authority is False

    path = write_current_webull_stock_entry_evidence_bundle_v1(
        settings,
        bundle,
    )
    restored = read_current_webull_stock_entry_evidence_bundle_v1(
        settings,
        path=path,
    )
    assert restored == bundle


def test_entry_fee_coverage_must_be_exact(tmp_path) -> None:
    settings = _settings(tmp_path)
    record = _record()
    runtime, reserve_bundle = _runtime_with_reservations(
        settings,
        (record,),
    )
    with pytest.raises(
        CurrentWebullStockEntryEvidenceError,
        match="fee coverage must exactly match",
    ):
        build_current_webull_stock_entry_evidence_bundle_v1(
            account=runtime.current_account(),
            reserve_bundle=reserve_bundle,
            quote_bundle=_quote_bundle(_quote("AAPL")),
            explicit_entry_fees_by_decision={},
            fee_source_id="explicit-test-fees-v1",
            fee_source_fingerprint=FEE_SOURCE_FP,
            built_at_utc=SLOT + timedelta(seconds=10),
        )


def test_quote_must_follow_reserve_state(tmp_path) -> None:
    settings = _settings(tmp_path)
    record = _record()
    runtime, reserve_bundle = _runtime_with_reservations(
        settings,
        (record,),
    )
    account = runtime.current_account()
    stale_relative = _quote(
        "AAPL",
        received_offset_seconds=1,
    )
    with pytest.raises(
        CurrentWebullStockEntryEvidenceError,
        match="predates recurrent RESERVE state",
    ):
        build_current_webull_stock_entry_evidence_bundle_v1(
            account=account,
            reserve_bundle=reserve_bundle,
            quote_bundle=_quote_bundle(stale_relative),
            explicit_entry_fees_by_decision={
                record.record_fingerprint: 0.0,
            },
            fee_source_id="explicit-test-fees-v1",
            fee_source_fingerprint=FEE_SOURCE_FP,
            built_at_utc=SLOT + timedelta(seconds=10),
        )


def test_batch_dry_run_blocks_competing_supplemental_fees(tmp_path) -> None:
    settings = _settings(tmp_path)
    first = _record(
        "AAPL",
        source_char="1",
        decision_offset_seconds=2,
    )
    second = _record(
        "MSFT",
        source_char="2",
        decision_offset_seconds=3,
    )
    runtime, reserve_bundle = _runtime_with_reservations(
        settings,
        (first, second),
        initial_equity=20_010.0,
    )
    account = runtime.current_account()
    assert account.state.cash == pytest.approx(10.0)

    with pytest.raises(
        CurrentWebullStockEntryEvidenceError,
        match="batch funding/transition dry-run failed",
    ):
        build_current_webull_stock_entry_evidence_bundle_v1(
            account=account,
            reserve_bundle=reserve_bundle,
            quote_bundle=_quote_bundle(
                _quote("AAPL"),
                _quote("MSFT", received_offset_seconds=9),
            ),
            explicit_entry_fees_by_decision={
                first.record_fingerprint: 8.0,
                second.record_fingerprint: 8.0,
            },
            fee_source_id="explicit-test-fees-v1",
            fee_source_fingerprint=FEE_SOURCE_FP,
            built_at_utc=SLOT + timedelta(seconds=10),
        )


def test_tampered_entry_bundle_fingerprint_fails_read(tmp_path) -> None:
    settings = _settings(tmp_path)
    record = _record()
    runtime, reserve_bundle = _runtime_with_reservations(
        settings,
        (record,),
    )
    bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=_quote_bundle(_quote("AAPL")),
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 0.0,
        },
        fee_source_id="explicit-test-fees-v1",
        fee_source_fingerprint=FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    path = write_current_webull_stock_entry_evidence_bundle_v1(
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
        CurrentWebullStockEntryEvidenceError,
        match="self-fingerprint mismatch",
    ):
        read_current_webull_stock_entry_evidence_bundle_v1(
            settings,
            path=path,
        )


def test_entry_pair_rejects_quote_changed_after_fill_construction(tmp_path) -> None:
    settings = _settings(tmp_path)
    record = _record()
    runtime, reserve_bundle = _runtime_with_reservations(
        settings,
        (record,),
    )
    bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=_quote_bundle(_quote("AAPL")),
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 1.0,
        },
        fee_source_id="explicit-test-fees-v1",
        fee_source_fingerprint=FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    pair = bundle.pairs[0]
    changed_quote = pair.quote.model_copy(
        update={"ask_price": pair.quote.ask_price + 0.25}
    )
    with pytest.raises(
        CurrentWebullStockEntryEvidenceError,
        match="fill price must equal quote ask",
    ):
        CurrentWebullStockEntryPairV1(
            quote=changed_quote,
            explicit_entry_fee_dollars=(
                pair.explicit_entry_fee_dollars
            ),
            fill=pair.fill,
            funding=pair.funding,
        )


def test_entry_pair_rejects_fee_changed_after_fill_construction(tmp_path) -> None:
    settings = _settings(tmp_path)
    record = _record()
    runtime, reserve_bundle = _runtime_with_reservations(
        settings,
        (record,),
    )
    bundle = build_current_webull_stock_entry_evidence_bundle_v1(
        account=runtime.current_account(),
        reserve_bundle=reserve_bundle,
        quote_bundle=_quote_bundle(_quote("AAPL")),
        explicit_entry_fees_by_decision={
            record.record_fingerprint: 1.0,
        },
        fee_source_id="explicit-test-fees-v1",
        fee_source_fingerprint=FEE_SOURCE_FP,
        built_at_utc=SLOT + timedelta(seconds=10),
    )
    pair = bundle.pairs[0]
    with pytest.raises(
        CurrentWebullStockEntryEvidenceError,
        match="fill fee does not match explicit fee evidence",
    ):
        CurrentWebullStockEntryPairV1(
            quote=pair.quote,
            explicit_entry_fee_dollars=2.0,
            fill=pair.fill,
            funding=pair.funding,
        )
