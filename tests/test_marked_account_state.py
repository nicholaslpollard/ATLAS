from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.marked_account_state import (
    MarkedAccountStateError,
    build_marked_account_state,
)
from packages.simulation.marked_account_state_contract import (
    MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.market_mark_evidence import (
    MarketMarkInputs,
    MarketMarkTransport,
    build_simulated_market_mark_evidence,
)
from packages.simulation.open_position_state import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
    OpenPositionAccountStateV1,
    SimulatedOpenPositionV1,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)


UTC = timezone.utc
OPENED = datetime(2026, 9, 16, 14, 50, tzinfo=UTC)
STATE_AS_OF = datetime(2026, 9, 16, 14, 55, tzinfo=UTC)
VALUATION = datetime(2026, 9, 16, 15, 0, tzinfo=UTC)


def _fp(char: str) -> str:
    return char * 64


def _stock_position() -> SimulatedOpenPositionV1:
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=_fp("a"),
        decision_record_fingerprint=_fp("1"),
        candidate_fingerprint=_fp("b"),
        fill_fingerprint=_fp("c"),
        funding_terms_fingerprint=_fp("d"),
        reservation_fingerprint=_fp("e"),
        option_reservation_terms_fingerprint=None,
        option_economics_result_fingerprint=None,
        instrument_kind=InstrumentKind.STOCK,
        instrument_id="AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier="stock-aapl-long",
        option_contract_ticker=None,
        option_contract_type=None,
        opened_utc=OPENED,
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
        source_account_state_fingerprint=_fp("a"),
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
        opened_utc=OPENED,
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


def _mixed_source_state() -> OpenPositionAccountStateV1:
    stock = _stock_position()
    option = _option_position()
    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=_fp("a"),
        as_of_utc=STATE_AS_OF,
        initial_equity=1000.0,
        source_stock_gross_notional=100.0,
        source_option_signed_delta_equivalent_notional=120.0,
        source_option_abs_delta_equivalent_notional=120.0,
        cash=698.0,
        entry_book_equity=998.0,
        cumulative_entry_fees_dollars=2.0,
        remaining_stock_reserved_capital=0.0,
        remaining_option_reserved_capital=0.0,
        remaining_stock_gross_notional=0.0,
        remaining_option_signed_delta_equivalent_notional=0.0,
        remaining_option_abs_delta_equivalent_notional=0.0,
        open_entry_book_value_dollars=300.0,
        open_stock_gross_entry_exposure_dollars=100.0,
        open_option_entry_book_value_dollars=200.0,
        open_option_signed_delta_equivalent_entry_reference_dollars=120.0,
        open_option_abs_delta_equivalent_entry_reference_dollars=120.0,
        open_option_premium_at_risk_dollars=200.0,
        remaining_stock_reservations=(),
        remaining_option_reservations=(),
        open_positions=(stock, option),
    )


def _empty_source_state() -> OpenPositionAccountStateV1:
    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=_fp("a"),
        as_of_utc=STATE_AS_OF,
        initial_equity=1000.0,
        source_stock_gross_notional=0.0,
        source_option_signed_delta_equivalent_notional=0.0,
        source_option_abs_delta_equivalent_notional=0.0,
        cash=1000.0,
        entry_book_equity=1000.0,
        cumulative_entry_fees_dollars=0.0,
        remaining_stock_reserved_capital=0.0,
        remaining_option_reserved_capital=0.0,
        remaining_stock_gross_notional=0.0,
        remaining_option_signed_delta_equivalent_notional=0.0,
        remaining_option_abs_delta_equivalent_notional=0.0,
        open_entry_book_value_dollars=0.0,
        open_stock_gross_entry_exposure_dollars=0.0,
        open_option_entry_book_value_dollars=0.0,
        open_option_signed_delta_equivalent_entry_reference_dollars=0.0,
        open_option_abs_delta_equivalent_entry_reference_dollars=0.0,
        open_option_premium_at_risk_dollars=0.0,
        remaining_stock_reservations=(),
        remaining_option_reservations=(),
        open_positions=(),
    )


def _mark(position: SimulatedOpenPositionV1, *, bid: float, ask: float, age: float = 10.0):
    market = VALUATION - timedelta(seconds=age)
    return build_simulated_market_mark_evidence(
        position=position,
        inputs=MarketMarkInputs(
            source_id=f"mark-{position.decision_record_fingerprint[:4]}",
            source_fingerprint=_fp("9" if position.instrument_kind == InstrumentKind.STOCK else "0"),
            provider="ALPACA",
            feed="IEX" if position.instrument_kind == InstrumentKind.STOCK else "INDICATIVE_OPTIONS",
            transport=MarketMarkTransport.STREAM,
            feed_quality="REALTIME",
            market_timestamp_utc=market,
            received_utc=market + timedelta(seconds=1),
            valuation_utc=VALUATION,
            bid_price_per_unit=bid,
            ask_price_per_unit=ask,
            last_price_per_unit=(bid + ask) / 2.0,
        ),
    )


def test_contract_fingerprint_is_frozen() -> None:
    assert (
        MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        == "f09a1ead48e86ae82442785f281c0e57d242db3773537a3ba64a44bb2519c082"
    )


def test_mixed_account_marks_and_unrealized_pnl_reconcile() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    state = build_marked_account_state(
        source_state=source,
        marks=(
            _mark(option, bid=1.5, ask=1.6),
            _mark(stock, bid=11.0, ask=11.1),
        ),
        valuation_utc=VALUATION,
    )
    by_kind = {item.instrument_kind: item for item in state.marked_positions}
    assert by_kind[InstrumentKind.STOCK].marked_value_dollars == pytest.approx(110.0)
    assert by_kind[InstrumentKind.STOCK].unrealized_pnl_dollars == pytest.approx(10.0)
    assert by_kind[InstrumentKind.STOCK].unrealized_return == pytest.approx(0.10)
    assert by_kind[InstrumentKind.OPTION].marked_value_dollars == pytest.approx(150.0)
    assert by_kind[InstrumentKind.OPTION].unrealized_pnl_dollars == pytest.approx(-50.0)
    assert by_kind[InstrumentKind.OPTION].unrealized_return == pytest.approx(-0.25)
    assert state.marked_open_position_value_dollars == pytest.approx(260.0)
    assert state.aggregate_unrealized_pnl_dollars == pytest.approx(-40.0)
    assert state.entry_book_equity == pytest.approx(998.0)
    assert state.marked_equity == pytest.approx(958.0)
    assert state.cash + state.marked_open_position_value_dollars == pytest.approx(958.0)


def test_entry_fees_are_not_double_counted_in_unrealized_pnl() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    state = build_marked_account_state(
        source_state=source,
        marks=(
            _mark(stock, bid=10.0, ask=10.1),
            _mark(option, bid=2.0, ask=2.1),
        ),
        valuation_utc=VALUATION,
    )
    assert state.aggregate_unrealized_pnl_dollars == pytest.approx(0.0)
    assert state.marked_equity == pytest.approx(998.0)
    assert state.initial_equity - state.marked_equity == pytest.approx(2.0)


def test_zero_bid_long_option_can_mark_to_zero() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    state = build_marked_account_state(
        source_state=source,
        marks=(
            _mark(stock, bid=10.0, ask=10.1),
            _mark(option, bid=0.0, ask=0.1),
        ),
        valuation_utc=VALUATION,
    )
    marked_option = next(
        item for item in state.marked_positions if item.instrument_kind == InstrumentKind.OPTION
    )
    assert marked_option.marked_value_dollars == 0.0
    assert marked_option.unrealized_pnl_dollars == pytest.approx(-200.0)
    assert marked_option.unrealized_return == pytest.approx(-1.0)


def test_missing_extra_and_duplicate_marks_fail_closed() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    stock_mark = _mark(stock, bid=10.0, ask=10.1)
    option_mark = _mark(option, bid=2.0, ask=2.1)
    with pytest.raises(MarkedAccountStateError, match="complete active-position mark coverage"):
        build_marked_account_state(
            source_state=source,
            marks=(stock_mark,),
            valuation_utc=VALUATION,
        )
    with pytest.raises(MarkedAccountStateError, match="multiple marks"):
        build_marked_account_state(
            source_state=source,
            marks=(stock_mark, stock_mark, option_mark),
            valuation_utc=VALUATION,
        )
    extra = replace(option_mark, decision_record_fingerprint=_fp("f"))
    with pytest.raises(MarkedAccountStateError, match="complete active-position mark coverage"):
        build_marked_account_state(
            source_state=source,
            marks=(stock_mark, option_mark, extra),
            valuation_utc=VALUATION,
        )


def test_stale_mark_fails_closed_for_current_account_valuation() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    stale = _mark(stock, bid=10.0, ask=10.1, age=61.0)
    with pytest.raises(MarkedAccountStateError, match="stale or ineligible"):
        build_marked_account_state(
            source_state=source,
            marks=(stale, _mark(option, bid=2.0, ask=2.1)),
            valuation_utc=VALUATION,
        )


def test_common_valuation_timestamp_is_required() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    mark = _mark(option, bid=2.0, ask=2.1)
    shifted_inputs = MarketMarkInputs(
        source_id="shifted",
        source_fingerprint=_fp("f"),
        provider="ALPACA",
        feed="IEX",
        transport=MarketMarkTransport.SNAPSHOT,
        feed_quality="REALTIME",
        market_timestamp_utc=VALUATION + timedelta(seconds=1),
        received_utc=VALUATION + timedelta(seconds=2),
        valuation_utc=VALUATION + timedelta(seconds=3),
        bid_price_per_unit=10.0,
        ask_price_per_unit=10.1,
    )
    shifted = build_simulated_market_mark_evidence(position=stock, inputs=shifted_inputs)
    with pytest.raises(MarkedAccountStateError, match="share the requested valuation timestamp"):
        build_marked_account_state(
            source_state=source,
            marks=(shifted, mark),
            valuation_utc=VALUATION,
        )


def test_mark_cannot_predate_position_open() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    early_valuation = OPENED + timedelta(seconds=30)
    early_inputs = MarketMarkInputs(
        source_id="early",
        source_fingerprint=_fp("f"),
        provider="LOCAL_CANONICAL_REPLAY",
        feed="QUOTE",
        transport=MarketMarkTransport.REPLAY,
        feed_quality="CANONICAL_REPLAY",
        market_timestamp_utc=OPENED - timedelta(seconds=1),
        received_utc=OPENED,
        valuation_utc=early_valuation,
        bid_price_per_unit=10.0,
        ask_price_per_unit=10.1,
    )
    early = build_simulated_market_mark_evidence(position=stock, inputs=early_inputs)
    option_early = build_simulated_market_mark_evidence(
        position=option,
        inputs=replace(
            early_inputs,
            source_id="early-option",
            source_fingerprint=_fp("0"),
            bid_price_per_unit=2.0,
            ask_price_per_unit=2.1,
        ),
    )
    with pytest.raises(MarkedAccountStateError, match="valuation timestamp cannot predate"):
        build_marked_account_state(
            source_state=source,
            marks=(early, option_early),
            valuation_utc=early_valuation,
        )


def test_empty_account_has_complete_zero_position_valuation() -> None:
    source = _empty_source_state()
    state = build_marked_account_state(
        source_state=source,
        marks=(),
        valuation_utc=VALUATION,
    )
    assert state.complete_mark_coverage is True
    assert state.marked_positions == ()
    assert state.marked_open_position_value_dollars == 0.0
    assert state.aggregate_unrealized_pnl_dollars == 0.0
    assert state.marked_equity == 1000.0


def test_snapshot_is_deterministic_and_mark_order_independent() -> None:
    source = _mixed_source_state()
    stock, option = source.open_positions
    stock_mark = _mark(stock, bid=11.0, ask=11.1)
    option_mark = _mark(option, bid=1.5, ask=1.6)
    first = build_marked_account_state(
        source_state=source,
        marks=(stock_mark, option_mark),
        valuation_utc=VALUATION,
    )
    second = build_marked_account_state(
        source_state=source,
        marks=(option_mark, stock_mark),
        valuation_utc=VALUATION,
    )
    assert first == second
    assert first.state_fingerprint == second.state_fingerprint


def test_authority_escalation_fails_closed() -> None:
    source = _empty_source_state()
    state = build_marked_account_state(
        source_state=source,
        marks=(),
        valuation_utc=VALUATION,
    )
    with pytest.raises(MarkedAccountStateError, match="cannot grant"):
        replace(state, realized_pnl_authority=True)
    with pytest.raises(MarkedAccountStateError, match="cannot grant"):
        replace(state, provider_read_authority=True)
    with pytest.raises(MarkedAccountStateError, match="cannot grant"):
        replace(state, paper_authority=True)
