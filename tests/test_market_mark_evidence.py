from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.market_mark_evidence import (
    MarketMarkEvidenceError,
    MarketMarkFreshness,
    MarketMarkInputs,
    MarketMarkTransport,
    build_simulated_market_mark_evidence,
)
from packages.simulation.market_mark_evidence_contract import (
    MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT,
    MAX_MARK_AGE_SECONDS,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1


UTC = timezone.utc
BASE_TIME = datetime(2026, 9, 16, 15, 0, tzinfo=UTC)


def _fp(char: str) -> str:
    return char * 64


def _stock_position() -> SimulatedOpenPositionV1:
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=_fp("a"),
        decision_record_fingerprint=_fp("b"),
        candidate_fingerprint=_fp("c"),
        fill_fingerprint=_fp("d"),
        funding_terms_fingerprint=_fp("e"),
        reservation_fingerprint=_fp("f"),
        option_reservation_terms_fingerprint=None,
        option_economics_result_fingerprint=None,
        instrument_kind=InstrumentKind.STOCK,
        instrument_id="AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier="stock-aapl-long",
        option_contract_ticker=None,
        option_contract_type=None,
        opened_utc=BASE_TIME - timedelta(minutes=5),
        quantity=10.0,
        quantity_unit="SHARES",
        entry_price_per_unit=10.0,
        contract_multiplier=1.0,
        entry_book_value_dollars=100.0,
        entry_fees_dollars=1.0,
        all_in_cash_cost_basis_dollars=101.0,
        original_reserved_capital_dollars=80.0,
        supplemental_cash_consumed_dollars=21.0,
        unspent_reserve_returned_dollars=0.0,
        stock_gross_entry_exposure_dollars=100.0,
        option_premium_at_risk_dollars=0.0,
        option_signed_delta_equivalent_entry_reference_dollars=0.0,
        option_abs_delta_equivalent_entry_reference_dollars=0.0,
        reason_codes=("TEST_STOCK_POSITION",),
    )


def _option_position() -> SimulatedOpenPositionV1:
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=_fp("1"),
        decision_record_fingerprint=_fp("2"),
        candidate_fingerprint=_fp("3"),
        fill_fingerprint=_fp("4"),
        funding_terms_fingerprint=_fp("5"),
        reservation_fingerprint=_fp("6"),
        option_reservation_terms_fingerprint=_fp("7"),
        option_economics_result_fingerprint=_fp("8"),
        instrument_kind=InstrumentKind.OPTION,
        instrument_id="AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier="aapl-call-long",
        option_contract_ticker="AAPL260918C00200000",
        option_contract_type="call",
        opened_utc=BASE_TIME - timedelta(minutes=5),
        quantity=1.0,
        quantity_unit="CONTRACTS",
        entry_price_per_unit=2.0,
        contract_multiplier=100.0,
        entry_book_value_dollars=200.0,
        entry_fees_dollars=1.0,
        all_in_cash_cost_basis_dollars=201.0,
        original_reserved_capital_dollars=250.0,
        supplemental_cash_consumed_dollars=0.0,
        unspent_reserve_returned_dollars=49.0,
        stock_gross_entry_exposure_dollars=0.0,
        option_premium_at_risk_dollars=200.0,
        option_signed_delta_equivalent_entry_reference_dollars=120.0,
        option_abs_delta_equivalent_entry_reference_dollars=120.0,
        reason_codes=("TEST_OPTION_POSITION",),
    )


def _inputs(
    *,
    bid: float = 11.0,
    ask: float = 11.1,
    age_seconds: float = 30.0,
    last: float | None = 11.05,
) -> MarketMarkInputs:
    valuation = BASE_TIME
    market = valuation - timedelta(seconds=age_seconds)
    received = market + timedelta(seconds=min(1.0, age_seconds))
    return MarketMarkInputs(
        source_id="alpaca-stock-stream-message-001",
        source_fingerprint=_fp("9"),
        provider="ALPACA",
        feed="IEX",
        transport=MarketMarkTransport.STREAM,
        feed_quality="REALTIME_LIMITED_VENUE",
        market_timestamp_utc=market,
        received_utc=received,
        valuation_utc=valuation,
        bid_price_per_unit=bid,
        ask_price_per_unit=ask,
        last_price_per_unit=last,
    )


def test_contract_fingerprint_is_frozen() -> None:
    assert (
        MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT
        == "1219f600e447f90718213ce0f974314f6480e90e13f46487770785e45c87c154"
    )
    assert MAX_MARK_AGE_SECONDS == 60.0


def test_fresh_stock_mark_uses_conservative_bid() -> None:
    mark = build_simulated_market_mark_evidence(
        position=_stock_position(),
        inputs=_inputs(),
    )
    assert mark.selected_mark_side == "BID"
    assert mark.selected_mark_price_per_unit == 11.0
    assert mark.freshness == MarketMarkFreshness.FRESH
    assert mark.valuation_eligible is True
    assert mark.mark_age_seconds == 30.0
    assert "CONSERVATIVE_EXECUTABLE_BID_SELECTED" in mark.reason_codes


def test_stale_mark_is_preserved_but_not_valuation_eligible() -> None:
    mark = build_simulated_market_mark_evidence(
        position=_stock_position(),
        inputs=_inputs(age_seconds=MAX_MARK_AGE_SECONDS + 1.0),
    )
    assert mark.freshness == MarketMarkFreshness.STALE
    assert mark.valuation_eligible is False
    assert "STALE_MARK_PRESERVED_NOT_VALUATION_ELIGIBLE" in mark.reason_codes


def test_exact_age_boundary_is_fresh() -> None:
    mark = build_simulated_market_mark_evidence(
        position=_stock_position(),
        inputs=_inputs(age_seconds=MAX_MARK_AGE_SECONDS),
    )
    assert mark.freshness == MarketMarkFreshness.FRESH
    assert mark.valuation_eligible is True


def test_long_option_zero_bid_is_valid_conservative_mark() -> None:
    inputs = replace(
        _inputs(bid=0.0, ask=0.10, last=0.05),
        source_id="alpaca-option-stream-message-001",
        feed="INDICATIVE_OPTIONS",
        feed_quality="REALTIME_INDICATIVE",
    )
    mark = build_simulated_market_mark_evidence(
        position=_option_position(),
        inputs=inputs,
    )
    assert mark.instrument_kind == InstrumentKind.OPTION
    assert mark.selected_mark_price_per_unit == 0.0
    assert mark.valuation_eligible is True


def test_stock_zero_bid_fails_closed() -> None:
    with pytest.raises(MarketMarkEvidenceError, match="stock bid price"):
        build_simulated_market_mark_evidence(
            position=_stock_position(),
            inputs=_inputs(bid=0.0, ask=0.1, last=0.05),
        )


def test_crossed_quote_fails_closed() -> None:
    with pytest.raises(MarketMarkEvidenceError, match="ask price cannot be below bid price"):
        _inputs(bid=11.0, ask=10.99)


def test_timestamp_order_fails_closed() -> None:
    inputs = _inputs()
    with pytest.raises(MarketMarkEvidenceError, match="market timestamp cannot follow receive timestamp"):
        replace(
            inputs,
            market_timestamp_utc=inputs.received_utc + timedelta(seconds=1),
        )
    with pytest.raises(MarketMarkEvidenceError, match="receive timestamp cannot follow valuation timestamp"):
        replace(
            inputs,
            received_utc=inputs.valuation_utc + timedelta(seconds=1),
        )


def test_midpoint_and_last_do_not_change_selected_bid_mark() -> None:
    position = _stock_position()
    mark_a = build_simulated_market_mark_evidence(
        position=position,
        inputs=_inputs(ask=11.2, last=12.0),
    )
    mark_b = build_simulated_market_mark_evidence(
        position=position,
        inputs=_inputs(ask=11.8, last=9.0),
    )
    assert mark_a.selected_mark_price_per_unit == 11.0
    assert mark_b.selected_mark_price_per_unit == 11.0
    assert mark_a.mark_fingerprint != mark_b.mark_fingerprint


def test_mark_fingerprint_is_deterministic_and_source_bound() -> None:
    position = _stock_position()
    inputs = _inputs()
    first = build_simulated_market_mark_evidence(position=position, inputs=inputs)
    second = build_simulated_market_mark_evidence(position=position, inputs=inputs)
    changed_source = build_simulated_market_mark_evidence(
        position=position,
        inputs=replace(inputs, source_fingerprint=_fp("0")),
    )
    assert first == second
    assert first.mark_fingerprint == second.mark_fingerprint
    assert first.mark_fingerprint != changed_source.mark_fingerprint


def test_authority_escalation_fails_closed() -> None:
    mark = build_simulated_market_mark_evidence(
        position=_stock_position(),
        inputs=_inputs(),
    )
    with pytest.raises(MarketMarkEvidenceError, match="cannot grant"):
        replace(mark, mark_to_market_authority=True)
    with pytest.raises(MarketMarkEvidenceError, match="cannot grant"):
        replace(mark, provider_read_authority=True)
    with pytest.raises(MarketMarkEvidenceError, match="cannot grant"):
        replace(mark, paper_authority=True)


def test_position_identity_and_lineage_are_bound() -> None:
    position = _option_position()
    mark = build_simulated_market_mark_evidence(
        position=position,
        inputs=replace(
            _inputs(bid=1.8, ask=2.0, last=1.9),
            source_id="replay-option-quote-001",
            provider="LOCAL_CANONICAL_REPLAY",
            feed="OPTION_QUOTE",
            transport=MarketMarkTransport.REPLAY,
            feed_quality="CANONICAL_REPLAY",
        ),
    )
    assert mark.position_fingerprint == position.position_fingerprint
    assert mark.source_account_state_fingerprint == position.source_account_state_fingerprint
    assert mark.decision_record_fingerprint == position.decision_record_fingerprint
    assert mark.fill_fingerprint == position.fill_fingerprint
    assert mark.funding_terms_fingerprint == position.funding_terms_fingerprint
    assert mark.option_contract_ticker == position.option_contract_ticker
