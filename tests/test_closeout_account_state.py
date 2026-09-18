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
    CloseoutAccountStateError,
    apply_closeout_batch_v1,
    apply_closeout_exit_fill_v1,
    initialize_closeout_account_v1,
    replay_closeout_account_v1,
    verify_closeout_account_replay_v1,
)
from packages.simulation.closeout_account_state_contract import (
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
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
STATE_AS_OF = datetime(2026, 9, 17, 14, 55, tzinfo=UTC)
STOCK_EXIT = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)
OPTION_EXIT = datetime(2026, 9, 17, 15, 5, tzinfo=UTC)


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


def _source_state(
    positions: tuple[SimulatedOpenPositionV1, ...],
) -> OpenPositionAccountStateV1:
    ordered = tuple(
        sorted(positions, key=lambda item: item.decision_record_fingerprint)
    )
    initial_equity = 1000.0
    entry_fees = sum(item.entry_fees_dollars for item in ordered)
    open_book = sum(item.entry_book_value_dollars for item in ordered)
    cash = initial_equity - entry_fees - open_book

    stock_gross = sum(
        item.stock_gross_entry_exposure_dollars for item in ordered
    )
    option_signed = sum(
        item.option_signed_delta_equivalent_entry_reference_dollars
        for item in ordered
    )
    option_abs = sum(
        item.option_abs_delta_equivalent_entry_reference_dollars
        for item in ordered
    )
    option_book = sum(
        item.entry_book_value_dollars
        for item in ordered
        if item.instrument_kind == InstrumentKind.OPTION
    )
    option_premium = sum(
        item.option_premium_at_risk_dollars for item in ordered
    )

    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=_fp("a"),
        as_of_utc=STATE_AS_OF,
        initial_equity=initial_equity,
        source_stock_gross_notional=stock_gross,
        source_option_signed_delta_equivalent_notional=option_signed,
        source_option_abs_delta_equivalent_notional=option_abs,
        cash=cash,
        entry_book_equity=initial_equity - entry_fees,
        cumulative_entry_fees_dollars=entry_fees,
        remaining_stock_reserved_capital=0.0,
        remaining_option_reserved_capital=0.0,
        remaining_stock_gross_notional=0.0,
        remaining_option_signed_delta_equivalent_notional=0.0,
        remaining_option_abs_delta_equivalent_notional=0.0,
        open_entry_book_value_dollars=open_book,
        open_stock_gross_entry_exposure_dollars=stock_gross,
        open_option_entry_book_value_dollars=option_book,
        open_option_signed_delta_equivalent_entry_reference_dollars=option_signed,
        open_option_abs_delta_equivalent_entry_reference_dollars=option_abs,
        open_option_premium_at_risk_dollars=option_premium,
        remaining_stock_reservations=(),
        remaining_option_reservations=(),
        open_positions=ordered,
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


def test_contract_fingerprint_is_frozen() -> None:
    assert (
        SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        == "d8363e6a0dba68ad8894691a308eff6231770e59ccea909a38fd95af317aa599"
    )


def test_initialization_preserves_entry_book_account_exactly() -> None:
    source = _source_state((_stock_position(), _option_position()))
    account = initialize_closeout_account_v1(source_state=source)
    assert account.state.cash == pytest.approx(698.0)
    assert account.state.source_entry_book_equity == pytest.approx(998.0)
    assert account.state.account_book_equity == pytest.approx(998.0)
    assert account.state.cumulative_entry_fees_dollars == pytest.approx(2.0)
    assert account.state.cumulative_exit_fees_dollars == 0.0
    assert account.state.cumulative_account_realized_pnl_dollars == 0.0
    assert account.state.cumulative_lifetime_trade_net_pnl_dollars == 0.0
    assert account.state.open_entry_book_value_dollars == pytest.approx(300.0)
    assert account.state.closed_trades == ()


def test_stock_close_returns_net_proceeds_and_realizes_without_recharging_entry_fee() -> None:
    stock = _stock_position()
    option = _option_position()
    source = _source_state((stock, option))
    fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    transition = apply_closeout_exit_fill_v1(
        initialize_closeout_account_v1(source_state=source),
        fill=fill,
    )
    state = transition.account.state
    trade = transition.closed_trade

    assert transition.idempotent_reuse is False
    assert state.cash == pytest.approx(807.0)
    assert state.open_entry_book_value_dollars == pytest.approx(200.0)
    assert state.account_book_equity == pytest.approx(1007.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(9.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(8.0)
    assert trade.account_realized_pnl_delta_dollars == pytest.approx(9.0)
    assert trade.lifetime_trade_net_pnl_dollars == pytest.approx(8.0)
    assert trade.entry_fees_dollars == pytest.approx(1.0)
    assert trade.exit_fees_dollars == pytest.approx(1.0)
    assert trade.hold_seconds == pytest.approx(
        (STOCK_EXIT - OPENED).total_seconds()
    )
    assert tuple(x.position_fingerprint for x in state.open_positions) == (
        option.position_fingerprint,
    )


def test_mixed_account_full_close_reconciles_account_and_lifetime_pnl() -> None:
    stock = _stock_position()
    option = _option_position()
    source = _source_state((stock, option))
    stock_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    option_fill = _exit_fill(
        source,
        option,
        exited_utc=OPTION_EXIT,
        price=1.5,
        fees=1.0,
        source_char="0",
    )

    result = apply_closeout_batch_v1(
        initialize_closeout_account_v1(source_state=source),
        (option_fill, stock_fill),
    )
    state = result.account.state

    assert result.ordered_exit_fill_fingerprints == (
        stock_fill.exit_fill_fingerprint,
        option_fill.exit_fill_fingerprint,
    )
    assert state.cash == pytest.approx(956.0)
    assert state.open_positions == ()
    assert state.open_entry_book_value_dollars == 0.0
    assert state.open_stock_gross_entry_exposure_dollars == 0.0
    assert state.open_option_entry_book_value_dollars == 0.0
    assert state.open_option_premium_at_risk_dollars == 0.0
    assert state.cumulative_entry_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_exit_fees_dollars == pytest.approx(2.0)
    assert state.cumulative_account_realized_pnl_dollars == pytest.approx(-42.0)
    assert state.cumulative_lifetime_trade_net_pnl_dollars == pytest.approx(-44.0)
    assert state.account_book_equity == pytest.approx(956.0)
    assert state.account_book_equity == pytest.approx(
        state.initial_equity
        + state.cumulative_lifetime_trade_net_pnl_dollars
    )


def test_zero_price_option_close_is_complete_loss() -> None:
    option = _option_position()
    source = _source_state((option,))
    fill = _exit_fill(
        source,
        option,
        exited_utc=OPTION_EXIT,
        price=0.0,
        fees=0.0,
        source_char="0",
    )
    transition = apply_closeout_exit_fill_v1(
        initialize_closeout_account_v1(source_state=source),
        fill=fill,
    )
    state = transition.account.state
    trade = transition.closed_trade

    assert trade.gross_exit_proceeds_dollars == 0.0
    assert trade.net_exit_proceeds_dollars == 0.0
    assert trade.account_realized_pnl_delta_dollars == pytest.approx(-200.0)
    assert trade.lifetime_trade_net_pnl_dollars == pytest.approx(-201.0)
    assert state.cash == pytest.approx(799.0)
    assert state.account_book_equity == pytest.approx(799.0)
    assert state.open_positions == ()


def test_same_exit_fill_is_idempotent() -> None:
    stock = _stock_position()
    source = _source_state((stock,))
    fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    first = apply_closeout_exit_fill_v1(
        initialize_closeout_account_v1(source_state=source),
        fill=fill,
    )
    second = apply_closeout_exit_fill_v1(first.account, fill=fill)

    assert second.idempotent_reuse is True
    assert second.event is None
    assert second.account == first.account
    assert second.closed_trade == first.closed_trade


def test_conflicting_second_close_fails_closed() -> None:
    stock = _stock_position()
    source = _source_state((stock,))
    first_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    second_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT + timedelta(minutes=1),
        price=10.5,
        fees=1.0,
        source_char="8",
    )
    first = apply_closeout_exit_fill_v1(
        initialize_closeout_account_v1(source_state=source),
        fill=first_fill,
    )
    with pytest.raises(
        CloseoutAccountStateError,
        match="conflicting second close",
    ):
        apply_closeout_exit_fill_v1(first.account, fill=second_fill)


def test_exit_fill_lineage_tamper_fails_closed() -> None:
    stock = _stock_position()
    source = _source_state((stock,))
    fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    tampered = replace(fill, decision_record_fingerprint=_fp("f"))
    with pytest.raises(
        CloseoutAccountStateError,
        match="decision record lineage mismatch",
    ):
        apply_closeout_exit_fill_v1(
            initialize_closeout_account_v1(source_state=source),
            fill=tampered,
        )


def test_nonchronological_new_close_fails_closed() -> None:
    stock = _stock_position()
    option = _option_position()
    source = _source_state((stock, option))
    later = _exit_fill(
        source,
        option,
        exited_utc=OPTION_EXIT,
        price=1.5,
        fees=1.0,
        source_char="0",
    )
    earlier = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    first = apply_closeout_exit_fill_v1(
        initialize_closeout_account_v1(source_state=source),
        fill=later,
    )
    with pytest.raises(
        CloseoutAccountStateError,
        match="cannot precede current closeout state",
    ):
        apply_closeout_exit_fill_v1(first.account, fill=earlier)


def test_batch_is_order_independent_and_replay_is_exact() -> None:
    stock = _stock_position()
    option = _option_position()
    source = _source_state((stock, option))
    stock_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    option_fill = _exit_fill(
        source,
        option,
        exited_utc=OPTION_EXIT,
        price=1.5,
        fees=1.0,
        source_char="0",
    )

    first = replay_closeout_account_v1(
        source_state=source,
        fills=(option_fill, stock_fill),
    )
    second = replay_closeout_account_v1(
        source_state=source,
        fills=(stock_fill, option_fill),
    )
    assert first.account.state == second.account.state
    assert (
        first.account.state.state_fingerprint
        == second.account.state.state_fingerprint
    )
    assert first.account.ledger == second.account.ledger
    assert (
        first.account.ledger.ledger_fingerprint
        == second.account.ledger.ledger_fingerprint
    )
    verify_closeout_account_replay_v1(
        account=first.account,
        source_state=source,
        fills=(stock_fill, option_fill),
    )


def test_replay_verifier_rejects_incomplete_valid_state() -> None:
    stock = _stock_position()
    source = _source_state((stock,))
    fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="9",
    )
    incomplete = initialize_closeout_account_v1(source_state=source)
    with pytest.raises(
        CloseoutAccountStateError,
        match="state replay fingerprint mismatch",
    ):
        verify_closeout_account_replay_v1(
            account=incomplete,
            source_state=source,
            fills=(fill,),
        )


def test_state_authority_escalation_fails_closed() -> None:
    source = _source_state((_stock_position(),))
    state = initialize_closeout_account_v1(source_state=source).state
    with pytest.raises(CloseoutAccountStateError, match="cannot grant"):
        replace(state, provider_read_authority=True)
    with pytest.raises(CloseoutAccountStateError, match="cannot grant"):
        replace(state, broker_write_authority=True)
    with pytest.raises(CloseoutAccountStateError, match="cannot grant"):
        replace(state, paper_authority=True)
