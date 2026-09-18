from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from packages.core.enums import SessionSegment
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteV1,
    build_current_webull_stock_quote_bundle_v1,
)
from packages.execution.current_webull_stock_mark_adapter import (
    CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT,
    CurrentWebullStockMarkAdapterError,
    build_current_webull_stock_marks_v1,
)
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.open_position_state import SimulatedOpenPositionV1


NOW = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)


def _position(
    *,
    ticker: str = "AAPL",
    decision_char: str = "2",
    kind: InstrumentKind = InstrumentKind.STOCK,
) -> SimulatedOpenPositionV1:
    if kind == InstrumentKind.STOCK:
        option_ticker = None
        option_type = None
        option_terms = None
        option_economics = None
        quantity_unit = "SHARES"
        quantity = 10.0
        multiplier = 1.0
        stock_exposure = 1_000.0
        option_premium = 0.0
        option_signed = 0.0
        option_abs = 0.0
    else:
        option_ticker = "AAPL260925C00100000"
        option_type = "call"
        option_terms = "7" * 64
        option_economics = "8" * 64
        quantity_unit = "CONTRACTS"
        quantity = 1.0
        multiplier = 100.0
        stock_exposure = 0.0
        option_premium = 1_000.0
        option_signed = 5_000.0
        option_abs = 5_000.0
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint="1" * 64,
        decision_record_fingerprint=decision_char * 64,
        candidate_fingerprint="3" * 64,
        fill_fingerprint="4" * 64,
        funding_terms_fingerprint="5" * 64,
        reservation_fingerprint="6" * 64,
        option_reservation_terms_fingerprint=option_terms,
        option_economics_result_fingerprint=option_economics,
        instrument_kind=kind,
        instrument_id=f"instrument:{ticker}",
        ticker=ticker,
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier=f"{kind.value}:{ticker}",
        option_contract_ticker=option_ticker,
        option_contract_type=option_type,
        opened_utc=NOW - timedelta(minutes=2),
        quantity=quantity,
        quantity_unit=quantity_unit,
        entry_price_per_unit=100.0 if kind == InstrumentKind.STOCK else 10.0,
        contract_multiplier=multiplier,
        entry_book_value_dollars=1_000.0,
        entry_fees_dollars=2.0,
        all_in_cash_cost_basis_dollars=1_002.0,
        original_reserved_capital_dollars=1_002.0,
        supplemental_cash_consumed_dollars=0.0,
        unspent_reserve_returned_dollars=0.0,
        stock_gross_entry_exposure_dollars=stock_exposure,
        option_premium_at_risk_dollars=option_premium,
        option_signed_delta_equivalent_entry_reference_dollars=option_signed,
        option_abs_delta_equivalent_entry_reference_dollars=option_abs,
        reason_codes=("TEST_POSITION",),
    )


def _quote(symbol: str, *, seconds_old: int = 5):
    provider = NOW - timedelta(seconds=seconds_old)
    return CurrentWebullStockQuoteV1(
        symbol=symbol,
        provider_timestamp_utc=provider,
        received_at_utc=provider + timedelta(seconds=1),
        session_date=provider.date(),
        session_segment=SessionSegment.REGULAR,
        bid_price=101.0,
        bid_size=10,
        ask_price=101.1,
        ask_size=12,
    )


def _bundle(*quotes: CurrentWebullStockQuoteV1):
    symbols = tuple(quote.symbol for quote in quotes)
    return build_current_webull_stock_quote_bundle_v1(
        requested_symbols=symbols,
        quotes=quotes,
        captured_at_utc=NOW - timedelta(seconds=1),
    )


def test_current_webull_stock_mark_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
        == "c862121c97cfedba968a9dad05d979ce2bc46bc6fdf8c9bf6dac53ca6e40b4d8"
    )


def test_webull_bundle_builds_exact_stock_marks() -> None:
    bundle = _bundle(_quote("MSFT"), _quote("AAPL"))
    batch = build_current_webull_stock_marks_v1(
        bundle=bundle,
        positions=(
            _position(ticker="MSFT", decision_char="9"),
            _position(ticker="AAPL", decision_char="2"),
        ),
        valuation_utc=NOW,
    )
    assert tuple(mark.ticker for mark in batch.marks) == (
        "AAPL",
        "MSFT",
    )
    assert all(mark.valuation_eligible for mark in batch.marks)
    assert all(
        mark.source_fingerprint == bundle.bundle_fingerprint
        for mark in batch.marks
    )
    assert all(
        mark.selected_mark_price_per_unit == pytest.approx(101.0)
        for mark in batch.marks
    )
    assert batch.provider_read_authority is False
    assert batch.broker_write_authority is False
    assert len(batch.batch_fingerprint) == 64


def test_webull_mark_adapter_requires_complete_exact_case_coverage() -> None:
    bundle = _bundle(_quote("aapl"))
    with pytest.raises(
        CurrentWebullStockMarkAdapterError,
        match="missing exact-case",
    ):
        build_current_webull_stock_marks_v1(
            bundle=bundle,
            positions=(_position(ticker="AAPL"),),
            valuation_utc=NOW,
        )


def test_webull_mark_adapter_rejects_stale_quote() -> None:
    bundle = _bundle(_quote("AAPL", seconds_old=31))
    with pytest.raises(
        CurrentWebullStockMarkAdapterError,
        match="execution age cap",
    ):
        build_current_webull_stock_marks_v1(
            bundle=bundle,
            positions=(_position(),),
            valuation_utc=NOW,
        )


def test_webull_mark_adapter_rejects_option_position() -> None:
    bundle = _bundle(_quote("AAPL"))
    with pytest.raises(
        CurrentWebullStockMarkAdapterError,
        match="stock positions only",
    ):
        build_current_webull_stock_marks_v1(
            bundle=bundle,
            positions=(
                _position(kind=InstrumentKind.OPTION),
            ),
            valuation_utc=NOW,
        )


def test_webull_mark_adapter_rejects_bundle_after_valuation() -> None:
    bundle = build_current_webull_stock_quote_bundle_v1(
        requested_symbols=("AAPL",),
        quotes=(_quote("AAPL"),),
        captured_at_utc=NOW + timedelta(seconds=1),
    )
    with pytest.raises(
        CurrentWebullStockMarkAdapterError,
        match="captured after valuation",
    ):
        build_current_webull_stock_marks_v1(
            bundle=bundle,
            positions=(_position(),),
            valuation_utc=NOW,
        )
