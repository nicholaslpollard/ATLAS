from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
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
    SimulatedExitFillError,
    SimulatedExitFillInputs,
    build_simulated_exit_fill_evidence,
)
from packages.simulation.simulated_exit_fill_contract import (
    SIMULATED_EXIT_FILL_CONTRACT_FINGERPRINT,
)


UTC = timezone.utc
OPENED = datetime(2026, 9, 17, 14, 30, tzinfo=UTC)
STATE_AS_OF = datetime(2026, 9, 17, 14, 35, tzinfo=UTC)
EXITED = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)


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


def _source_state(position: SimulatedOpenPositionV1) -> OpenPositionAccountStateV1:
    initial_equity = 1000.0
    entry_book_equity = initial_equity - position.entry_fees_dollars
    cash = entry_book_equity - position.entry_book_value_dollars
    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=position.source_account_state_fingerprint,
        as_of_utc=STATE_AS_OF,
        initial_equity=initial_equity,
        source_stock_gross_notional=position.stock_gross_entry_exposure_dollars,
        source_option_signed_delta_equivalent_notional=(
            position.option_signed_delta_equivalent_entry_reference_dollars
        ),
        source_option_abs_delta_equivalent_notional=(
            position.option_abs_delta_equivalent_entry_reference_dollars
        ),
        cash=cash,
        entry_book_equity=entry_book_equity,
        cumulative_entry_fees_dollars=position.entry_fees_dollars,
        remaining_stock_reserved_capital=0.0,
        remaining_option_reserved_capital=0.0,
        remaining_stock_gross_notional=0.0,
        remaining_option_signed_delta_equivalent_notional=0.0,
        remaining_option_abs_delta_equivalent_notional=0.0,
        open_entry_book_value_dollars=position.entry_book_value_dollars,
        open_stock_gross_entry_exposure_dollars=(
            position.stock_gross_entry_exposure_dollars
        ),
        open_option_entry_book_value_dollars=(
            position.entry_book_value_dollars
            if position.instrument_kind == InstrumentKind.OPTION
            else 0.0
        ),
        open_option_signed_delta_equivalent_entry_reference_dollars=(
            position.option_signed_delta_equivalent_entry_reference_dollars
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=(
            position.option_abs_delta_equivalent_entry_reference_dollars
        ),
        open_option_premium_at_risk_dollars=(
            position.option_premium_at_risk_dollars
        ),
        remaining_stock_reservations=(),
        remaining_option_reservations=(),
        open_positions=(position,),
    )


def _inputs(
    *,
    price: float = 11.0,
    fees: float = 1.0,
    exited_utc: datetime = EXITED,
    source_char: str = "9",
) -> SimulatedExitFillInputs:
    return SimulatedExitFillInputs(
        fill_source_id="local-replay-exit-001",
        fill_source_fingerprint=_fp(source_char),
        exited_utc=exited_utc,
        exit_price_per_unit=price,
        explicit_exit_fees_dollars=fees,
    )


def test_contract_fingerprint_is_frozen() -> None:
    assert (
        SIMULATED_EXIT_FILL_CONTRACT_FINGERPRINT
        == "d823bdf481f6ae6266be0a7e87d36702e1687d5a84f97da105e64cfc7e8f77c0"
    )


def test_stock_complete_exit_fill_binds_exact_active_position() -> None:
    position = _stock_position()
    source = _source_state(position)
    fill = build_simulated_exit_fill_evidence(
        source_state=source,
        position_fingerprint=position.position_fingerprint,
        inputs=_inputs(),
    )
    assert fill.position_fingerprint == position.position_fingerprint
    assert fill.source_open_position_state_fingerprint == source.state_fingerprint
    assert fill.quantity == 10.0
    assert fill.quantity_unit == "SHARES"
    assert fill.contract_multiplier == 1.0
    assert fill.gross_exit_proceeds_dollars == pytest.approx(110.0)
    assert fill.exit_fees_dollars == pytest.approx(1.0)
    assert fill.net_exit_proceeds_dollars == pytest.approx(109.0)
    assert fill.full_close is True


def test_option_zero_price_complete_loss_exit_is_representable() -> None:
    position = _option_position()
    source = _source_state(position)
    fill = build_simulated_exit_fill_evidence(
        source_state=source,
        position_fingerprint=position.position_fingerprint,
        inputs=_inputs(price=0.0, fees=0.0),
    )
    assert fill.instrument_kind == InstrumentKind.OPTION
    assert fill.quantity == 1.0
    assert fill.contract_multiplier == 100.0
    assert fill.gross_exit_proceeds_dollars == 0.0
    assert fill.net_exit_proceeds_dollars == 0.0
    assert fill.option_contract_ticker == position.option_contract_ticker


def test_unknown_or_inactive_position_fails_closed() -> None:
    source = _source_state(_stock_position())
    with pytest.raises(
        SimulatedExitFillError,
        match="exact active open position is required",
    ):
        build_simulated_exit_fill_evidence(
            source_state=source,
            position_fingerprint=_fp("f"),
            inputs=_inputs(),
        )


def test_exit_timestamp_cannot_precede_source_state() -> None:
    position = _stock_position()
    source = _source_state(position)
    with pytest.raises(
        SimulatedExitFillError,
        match="cannot precede open-position account state",
    ):
        build_simulated_exit_fill_evidence(
            source_state=source,
            position_fingerprint=position.position_fingerprint,
            inputs=_inputs(
                exited_utc=STATE_AS_OF - timedelta(seconds=1)
            ),
        )


def test_exit_fees_cannot_exceed_gross_proceeds() -> None:
    position = _option_position()
    source = _source_state(position)
    with pytest.raises(
        SimulatedExitFillError,
        match="exit fees cannot exceed gross exit proceeds",
    ):
        build_simulated_exit_fill_evidence(
            source_state=source,
            position_fingerprint=position.position_fingerprint,
            inputs=_inputs(price=0.01, fees=2.0),
        )


def test_input_validation_requires_source_hash_and_nonnegative_price() -> None:
    with pytest.raises(
        SimulatedExitFillError,
        match="SHA-256 fingerprint",
    ):
        SimulatedExitFillInputs(
            fill_source_id="bad",
            fill_source_fingerprint="not-a-hash",
            exited_utc=EXITED,
            exit_price_per_unit=1.0,
        )
    with pytest.raises(
        SimulatedExitFillError,
        match="finite and nonnegative",
    ):
        _inputs(price=-0.01)


def test_exit_fill_fingerprint_is_deterministic_and_source_bound() -> None:
    position = _stock_position()
    source = _source_state(position)
    first = build_simulated_exit_fill_evidence(
        source_state=source,
        position_fingerprint=position.position_fingerprint,
        inputs=_inputs(),
    )
    second = build_simulated_exit_fill_evidence(
        source_state=source,
        position_fingerprint=position.position_fingerprint,
        inputs=_inputs(),
    )
    changed_source = build_simulated_exit_fill_evidence(
        source_state=source,
        position_fingerprint=position.position_fingerprint,
        inputs=_inputs(source_char="0"),
    )
    assert first == second
    assert first.exit_fill_fingerprint == second.exit_fill_fingerprint
    assert first.exit_fill_fingerprint != changed_source.exit_fill_fingerprint


def test_tampered_quantity_and_partial_exit_fail_closed() -> None:
    position = _stock_position()
    fill = build_simulated_exit_fill_evidence(
        source_state=_source_state(position),
        position_fingerprint=position.position_fingerprint,
        inputs=_inputs(),
    )
    with pytest.raises(
        SimulatedExitFillError,
        match="gross exit proceeds must match",
    ):
        replace(fill, quantity=9.0)
    with pytest.raises(
        SimulatedExitFillError,
        match="must close the full position",
    ):
        replace(fill, full_close=False)


def test_authority_escalation_fails_closed() -> None:
    position = _stock_position()
    fill = build_simulated_exit_fill_evidence(
        source_state=_source_state(position),
        position_fingerprint=position.position_fingerprint,
        inputs=_inputs(),
    )
    with pytest.raises(SimulatedExitFillError, match="cannot grant"):
        replace(fill, position_mutation_authority=True)
    with pytest.raises(SimulatedExitFillError, match="cannot grant"):
        replace(fill, realized_pnl_authority=True)
    with pytest.raises(SimulatedExitFillError, match="cannot grant"):
        replace(fill, broker_fill_authority=True)
    with pytest.raises(SimulatedExitFillError, match="cannot grant"):
        replace(fill, paper_authority=True)
