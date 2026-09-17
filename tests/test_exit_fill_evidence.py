from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.exit_fill_evidence import (
    ExitFillEvidenceError,
    SimulatedExitFillInputs,
    build_simulated_exit_fill_evidence,
)
from packages.simulation.exit_fill_evidence_contract import (
    EXIT_FILL_EVIDENCE_CONTRACT_FINGERPRINT,
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
EXITED = datetime(2026, 9, 16, 15, 0, tzinfo=UTC)


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


def _source_state() -> OpenPositionAccountStateV1:
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


def _inputs(*, price: float, fee: float = 0.5, exited: datetime = EXITED) -> SimulatedExitFillInputs:
    return SimulatedExitFillInputs(
        source_id="canonical-exit-quote",
        source_fingerprint=_fp("9"),
        filled_utc=exited,
        fill_price_per_unit=price,
        explicit_exit_fees_dollars=fee,
    )


def test_contract_fingerprint_is_frozen() -> None:
    assert (
        EXIT_FILL_EVIDENCE_CONTRACT_FINGERPRINT
        == "31c5c204c6582219aaa6f5f0d9c1c4e487669f84a002328e72fc85ea55ea02f5"
    )


def test_stock_complete_exit_fill_is_source_bound_and_deterministic() -> None:
    source = _source_state()
    stock = source.open_positions[0]
    fill = build_simulated_exit_fill_evidence(
        source_state=source,
        position=stock,
        inputs=_inputs(price=11.0, fee=1.5),
    )
    repeated = build_simulated_exit_fill_evidence(
        source_state=source,
        position=stock,
        inputs=_inputs(price=11.0, fee=1.5),
    )
    assert fill.instrument_kind == InstrumentKind.STOCK
    assert fill.quantity == pytest.approx(10.0)
    assert fill.gross_exit_value_dollars == pytest.approx(110.0)
    assert fill.exit_fees_dollars == pytest.approx(1.5)
    assert fill.complete_close is True
    assert fill.exit_fill_fingerprint == repeated.exit_fill_fingerprint
    assert fill.realized_pnl_authority is False
    assert fill.position_mutation_authority is False


def test_long_option_can_exit_at_zero_value() -> None:
    source = _source_state()
    option = source.open_positions[1]
    fill = build_simulated_exit_fill_evidence(
        source_state=source,
        position=option,
        inputs=_inputs(price=0.0, fee=0.0),
    )
    assert fill.instrument_kind == InstrumentKind.OPTION
    assert fill.quantity == pytest.approx(1.0)
    assert fill.contract_multiplier == pytest.approx(100.0)
    assert fill.gross_exit_value_dollars == pytest.approx(0.0)
    assert "LONG_OPTION_ZERO_VALUE_EXIT_ALLOWED" in fill.reason_codes


def test_stock_zero_exit_price_fails_closed() -> None:
    source = _source_state()
    with pytest.raises(ExitFillEvidenceError, match="stock exit-fill price must be positive"):
        build_simulated_exit_fill_evidence(
            source_state=source,
            position=source.open_positions[0],
            inputs=_inputs(price=0.0),
        )


def test_exit_cannot_predate_source_state_or_position() -> None:
    source = _source_state()
    stock = source.open_positions[0]
    with pytest.raises(ExitFillEvidenceError, match="cannot predate source open-position state"):
        build_simulated_exit_fill_evidence(
            source_state=source,
            position=stock,
            inputs=_inputs(price=10.0, exited=STATE_AS_OF - timedelta(seconds=1)),
        )
    with pytest.raises(ExitFillEvidenceError, match="cannot predate position open"):
        build_simulated_exit_fill_evidence(
            source_state=replace(source, as_of_utc=OPENED - timedelta(seconds=2)),
            position=stock,
            inputs=_inputs(price=10.0, exited=OPENED - timedelta(seconds=1)),
        )


def test_exact_active_position_payload_is_required() -> None:
    source = _source_state()
    tampered = replace(source.open_positions[0], candidate_identifier="tampered")
    with pytest.raises(ExitFillEvidenceError, match="exact active open position is required"):
        build_simulated_exit_fill_evidence(
            source_state=source,
            position=tampered,
            inputs=_inputs(price=10.0),
        )


def test_exit_source_fingerprint_must_be_sha256() -> None:
    with pytest.raises(ExitFillEvidenceError, match="SHA-256"):
        SimulatedExitFillInputs(
            source_id="bad",
            source_fingerprint="not-a-fingerprint",
            filled_utc=EXITED,
            fill_price_per_unit=10.0,
        )


def test_authority_escalation_fails_closed() -> None:
    source = _source_state()
    fill = build_simulated_exit_fill_evidence(
        source_state=source,
        position=source.open_positions[0],
        inputs=_inputs(price=10.0),
    )
    with pytest.raises(ExitFillEvidenceError, match="cannot grant"):
        replace(fill, realized_pnl_authority=True)
    with pytest.raises(ExitFillEvidenceError, match="cannot grant"):
        replace(fill, broker_write_authority=True)
