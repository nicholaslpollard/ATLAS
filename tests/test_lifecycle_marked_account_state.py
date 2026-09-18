from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.closeout_account_state import (
    apply_closeout_exit_fill_v1,
    initialize_closeout_account_v1,
)
from packages.simulation.lifecycle_marked_account_state import (
    LifecycleMarkedAccountStateError,
    build_lifecycle_marked_account_state,
)
from packages.simulation.lifecycle_marked_account_state_contract import (
    LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
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
from packages.simulation.simulated_exit_fill import (
    SimulatedExitFillInputs,
    build_simulated_exit_fill_evidence,
)


UTC = timezone.utc
OPENED = datetime(2026, 9, 17, 14, 30, tzinfo=UTC)
OPEN_STATE_AS_OF = datetime(2026, 9, 17, 14, 55, tzinfo=UTC)
STOCK_EXIT = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)
OPTION_EXIT = datetime(2026, 9, 17, 15, 5, tzinfo=UTC)
VALUATION = datetime(2026, 9, 17, 15, 10, tzinfo=UTC)


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


def _open_source() -> OpenPositionAccountStateV1:
    stock = _stock_position()
    option = _option_position()
    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=_fp("a"),
        as_of_utc=OPEN_STATE_AS_OF,
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


def _exit_fill(
    source: OpenPositionAccountStateV1,
    position: SimulatedOpenPositionV1,
    *,
    exited_utc: datetime,
    price: float,
    fees: float,
    source_char: str,
):
    return build_simulated_exit_fill_evidence(
        source_state=source,
        position_fingerprint=position.position_fingerprint,
        inputs=SimulatedExitFillInputs(
            fill_source_id=f"exit-{position.decision_record_fingerprint[:4]}",
            fill_source_fingerprint=_fp(source_char),
            exited_utc=exited_utc,
            exit_price_per_unit=price,
            explicit_exit_fees_dollars=fees,
        ),
    )


def _close_stock_only():
    source = _open_source()
    stock, _option = source.open_positions
    stock_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    transition = apply_closeout_exit_fill_v1(
        initialize_closeout_account_v1(source_state=source),
        fill=stock_fill,
    )
    return source, transition.account.state


def _close_both():
    source, state = _close_stock_only()
    _stock, option = source.open_positions
    option_fill = _exit_fill(
        source,
        option,
        exited_utc=OPTION_EXIT,
        price=1.5,
        fees=1.0,
        source_char="0",
    )
    account = initialize_closeout_account_v1(source_state=source)
    stock_fill = _exit_fill(
        source,
        source.open_positions[0],
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    first = apply_closeout_exit_fill_v1(account, fill=stock_fill)
    second = apply_closeout_exit_fill_v1(first.account, fill=option_fill)
    return source, second.account.state


def _mark(
    position: SimulatedOpenPositionV1,
    *,
    bid: float,
    ask: float,
    age: float = 10.0,
    valuation: datetime = VALUATION,
    source_char: str = "f",
):
    market = valuation - timedelta(seconds=age)
    return build_simulated_market_mark_evidence(
        position=position,
        inputs=MarketMarkInputs(
            source_id=f"mark-{position.decision_record_fingerprint[:4]}",
            source_fingerprint=_fp(source_char),
            provider="ALPACA",
            feed=(
                "IEX"
                if position.instrument_kind == InstrumentKind.STOCK
                else "INDICATIVE_OPTIONS"
            ),
            transport=MarketMarkTransport.STREAM,
            feed_quality="REALTIME",
            market_timestamp_utc=market,
            received_utc=market + timedelta(seconds=1),
            valuation_utc=valuation,
            bid_price_per_unit=bid,
            ask_price_per_unit=ask,
            last_price_per_unit=(bid + ask) / 2.0,
        ),
    )


def test_contract_fingerprint_is_frozen() -> None:
    assert (
        LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        == "4cc4fb35c5a95cb48603f581a48127fe188c844c44e445394ad3d662e07a5346"
    )


def test_post_close_survivor_mark_preserves_realized_and_adds_only_current_unrealized() -> None:
    source, closeout = _close_stock_only()
    _stock, option = source.open_positions
    state = build_lifecycle_marked_account_state(
        source_state=closeout,
        marks=(_mark(option, bid=1.5, ask=1.6, source_char="0"),),
        valuation_utc=VALUATION,
    )

    assert closeout.cash == pytest.approx(807.0)
    assert closeout.account_book_equity == pytest.approx(1007.0)
    assert closeout.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert closeout.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)

    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)
    assert state.cumulative_entry_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(1.0)
    assert state.closed_trade_count == 1
    assert len(state.marked_positions) == 1
    assert state.marked_positions[0].position_fingerprint == option.position_fingerprint
    assert state.marked_open_position_value_dollars == pytest.approx(150.0)
    assert state.aggregate_unrealized_pnl_dollars == pytest.approx(-50.0)
    assert state.marked_equity == pytest.approx(957.0)
    assert state.cash + state.marked_open_position_value_dollars == pytest.approx(957.0)


def test_closed_position_mark_is_rejected_as_extra_current_position() -> None:
    source, closeout = _close_stock_only()
    stock, option = source.open_positions
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="complete current open-position mark coverage",
    ):
        build_lifecycle_marked_account_state(
            source_state=closeout,
            marks=(
                _mark(stock, bid=11.0, ask=11.1, source_char="9"),
                _mark(option, bid=1.5, ask=1.6, source_char="0"),
            ),
            valuation_utc=VALUATION,
        )


def test_missing_duplicate_and_stale_current_marks_fail_closed() -> None:
    source, closeout = _close_stock_only()
    _stock, option = source.open_positions
    option_mark = _mark(option, bid=1.5, ask=1.6, source_char="0")

    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="complete current open-position mark coverage",
    ):
        build_lifecycle_marked_account_state(
            source_state=closeout,
            marks=(),
            valuation_utc=VALUATION,
        )

    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="multiple marks",
    ):
        build_lifecycle_marked_account_state(
            source_state=closeout,
            marks=(option_mark, option_mark),
            valuation_utc=VALUATION,
        )

    stale = _mark(
        option,
        bid=1.5,
        ask=1.6,
        age=61.0,
        source_char="0",
    )
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="stale or ineligible",
    ):
        build_lifecycle_marked_account_state(
            source_state=closeout,
            marks=(stale,),
            valuation_utc=VALUATION,
        )


def test_marked_account_after_all_positions_close_is_complete_without_marks() -> None:
    _source, closeout = _close_both()
    state = build_lifecycle_marked_account_state(
        source_state=closeout,
        marks=(),
        valuation_utc=VALUATION,
    )
    assert state.complete_mark_coverage is True
    assert state.marked_positions == ()
    assert state.marked_open_position_value_dollars == 0.0
    assert state.aggregate_unrealized_pnl_dollars == 0.0
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(-42.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(-44.0)
    assert state.cash == pytest.approx(956.0)
    assert state.account_book_equity == pytest.approx(956.0)
    assert state.marked_equity == pytest.approx(956.0)
    assert state.closed_trade_count == 2


def test_preclose_state_can_mark_all_current_positions_and_is_order_independent() -> None:
    source = _open_source()
    closeout = initialize_closeout_account_v1(source_state=source).state
    stock, option = source.open_positions
    stock_mark = _mark(stock, bid=11.0, ask=11.1, source_char="9")
    option_mark = _mark(option, bid=1.5, ask=1.6, source_char="0")
    first = build_lifecycle_marked_account_state(
        source_state=closeout,
        marks=(stock_mark, option_mark),
        valuation_utc=VALUATION,
    )
    second = build_lifecycle_marked_account_state(
        source_state=closeout,
        marks=(option_mark, stock_mark),
        valuation_utc=VALUATION,
    )
    assert first == second
    assert first.state_fingerprint == second.state_fingerprint
    assert first.cumulative_account_realized_pnl_dollars == 0.0
    assert first.aggregate_unrealized_pnl_dollars == pytest.approx(-40.0)
    assert first.marked_equity == pytest.approx(958.0)


def test_common_valuation_timestamp_and_closeout_chronology_are_required() -> None:
    source, closeout = _close_stock_only()
    _stock, option = source.open_positions
    shifted = _mark(
        option,
        bid=1.5,
        ask=1.6,
        valuation=VALUATION + timedelta(seconds=3),
        source_char="0",
    )
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="share the requested lifecycle valuation timestamp",
    ):
        build_lifecycle_marked_account_state(
            source_state=closeout,
            marks=(shifted,),
            valuation_utc=VALUATION,
        )

    too_early = closeout.as_of_utc - timedelta(seconds=1)
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="cannot predate closeout account state",
    ):
        build_lifecycle_marked_account_state(
            source_state=closeout,
            marks=(),
            valuation_utc=too_early,
        )


def test_realized_pnl_and_fee_layers_are_not_recomputed_by_marks() -> None:
    source, closeout = _close_stock_only()
    _stock, option = source.open_positions
    at_entry = build_lifecycle_marked_account_state(
        source_state=closeout,
        marks=(_mark(option, bid=2.0, ask=2.1, source_char="0"),),
        valuation_utc=VALUATION,
    )
    assert at_entry.aggregate_unrealized_pnl_dollars == 0.0
    assert at_entry.marked_equity == pytest.approx(
        closeout.account_book_equity
    )
    assert at_entry.cumulative_entry_fees_dollars == pytest.approx(2.0)
    assert at_entry.cumulative_exit_fees_dollars == pytest.approx(1.0)
    assert at_entry.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert at_entry.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)


def test_authority_escalation_fails_closed() -> None:
    _source, closeout = _close_both()
    state = build_lifecycle_marked_account_state(
        source_state=closeout,
        marks=(),
        valuation_utc=VALUATION,
    )
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="cannot grant",
    ):
        replace(state, account_mutation_authority=True)
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="cannot grant",
    ):
        replace(state, new_realized_pnl_authority=True)
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="cannot grant",
    ):
        replace(state, provider_read_authority=True)
    with pytest.raises(
        LifecycleMarkedAccountStateError,
        match="cannot grant",
    ):
        replace(state, paper_authority=True)
