from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.control_plane.simulation_lifecycle_dashboard import (
    source_provider_from_coordinator,
)
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.engine import (
    SimulationLifecycleCoordinatorV1,
    replay_simulation_lifecycle_cycle_v1,
    verify_simulation_lifecycle_cycle_replay_v1,
)
from packages.simulation.lifecycle_coordinator_contract import (
    SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT,
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
SOURCE_AS_OF = datetime(2026, 9, 17, 14, 55, tzinfo=UTC)
STOCK_EXIT = datetime(2026, 9, 17, 15, 0, tzinfo=UTC)
OPTION_EXIT = datetime(2026, 9, 17, 15, 5, tzinfo=UTC)
VALUATION_0 = datetime(2026, 9, 17, 14, 59, tzinfo=UTC)
VALUATION_1 = datetime(2026, 9, 17, 15, 1, tzinfo=UTC)
VALUATION_2 = datetime(2026, 9, 17, 15, 6, tzinfo=UTC)


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


def _source() -> OpenPositionAccountStateV1:
    stock = _stock_position()
    option = _option_position()
    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=_fp("a"),
        as_of_utc=SOURCE_AS_OF,
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


def _mark(
    position: SimulatedOpenPositionV1,
    *,
    valuation: datetime,
    bid: float,
    ask: float,
    source_char: str,
):
    market = valuation - timedelta(seconds=5)
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
        SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT
        == "696254240971db5a9a7ae2a0307c2c847b376d360d5cfe1f8b5f30ec80a93a9b"
    )


def test_initial_state_is_unmarked_atomic_single_cycle() -> None:
    source = _source()
    coordinator = SimulationLifecycleCoordinatorV1(source_state=source)
    snapshot = coordinator.snapshot()

    assert snapshot.revision == 0
    assert snapshot.source_open_position_state_fingerprint == source.state_fingerprint
    assert snapshot.closeout_account.state.open_positions == source.open_positions
    assert snapshot.marked_state is None
    assert snapshot.marks_current is False
    assert coordinator.current_dashboard_pair() is None
    assert snapshot.single_cycle_only is True
    assert snapshot.reentry_supported is False
    assert snapshot.provider_read_authority is False
    assert snapshot.broker_write_authority is False
    assert snapshot.paper_authority is False
    assert snapshot.live_authority is False


def test_mark_publication_is_atomic_and_identical_republish_is_idempotent() -> None:
    source = _source()
    stock, option = source.open_positions
    coordinator = SimulationLifecycleCoordinatorV1(source_state=source)
    marks = (
        _mark(
            stock,
            valuation=VALUATION_0,
            bid=11.0,
            ask=11.1,
            source_char="9",
        ),
        _mark(
            option,
            valuation=VALUATION_0,
            bid=1.5,
            ask=1.6,
            source_char="0",
        ),
    )

    first = coordinator.publish_marks(
        marks=marks,
        valuation_utc=VALUATION_0,
    )
    pair = coordinator.current_dashboard_pair()
    assert first.revision == 1
    assert first.idempotent_reuse is False
    assert pair is not None
    account, marked = pair
    assert marked.source_closeout_state_fingerprint == account.state.state_fingerprint
    assert marked.aggregate_unrealized_pnl_dollars == pytest.approx(-40.0)

    second = coordinator.publish_marks(
        marks=reversed(marks),
        valuation_utc=VALUATION_0,
    )
    assert second.revision == 1
    assert second.idempotent_reuse is True
    assert coordinator.snapshot().revision == 1


def test_real_exit_invalidates_prior_valuation() -> None:
    source = _source()
    stock, option = source.open_positions
    coordinator = SimulationLifecycleCoordinatorV1(source_state=source)
    coordinator.publish_marks(
        marks=(
            _mark(
                stock,
                valuation=VALUATION_0,
                bid=11.0,
                ask=11.1,
                source_char="9",
            ),
            _mark(
                option,
                valuation=VALUATION_0,
                bid=1.5,
                ask=1.6,
                source_char="0",
            ),
        ),
        valuation_utc=VALUATION_0,
    )

    stock_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="7",
    )
    closed = coordinator.apply_exit_fill(fill=stock_fill)

    assert closed.revision == 2
    assert closed.valuation_invalidated is True
    assert closed.idempotent_reuse is False
    assert coordinator.current_marked_state() is None
    assert coordinator.current_dashboard_pair() is None
    assert len(coordinator.current_closeout_account().state.open_positions) == 1
    assert coordinator.current_closeout_account().state.open_positions[0].position_fingerprint == option.position_fingerprint


def test_duplicate_exit_does_not_destroy_new_current_valuation() -> None:
    source = _source()
    stock, option = source.open_positions
    stock_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="7",
    )
    coordinator = SimulationLifecycleCoordinatorV1(source_state=source)
    first = coordinator.apply_exit_fill(fill=stock_fill)
    assert first.revision == 1

    published = coordinator.publish_marks(
        marks=(
            _mark(
                option,
                valuation=VALUATION_1,
                bid=1.5,
                ask=1.6,
                source_char="0",
            ),
        ),
        valuation_utc=VALUATION_1,
    )
    assert published.revision == 2
    pair_before = coordinator.current_dashboard_pair()
    assert pair_before is not None

    duplicate = coordinator.apply_exit_fill(fill=stock_fill)
    assert duplicate.idempotent_reuse is True
    assert duplicate.valuation_invalidated is False
    assert duplicate.revision == 2
    assert coordinator.current_dashboard_pair() == pair_before


def test_batch_and_sequential_exit_paths_share_logical_revision() -> None:
    source = _source()
    stock, option = source.open_positions
    stock_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="7",
    )
    option_fill = _exit_fill(
        source,
        option,
        exited_utc=OPTION_EXIT,
        price=1.5,
        fees=1.0,
        source_char="8",
    )

    sequential = SimulationLifecycleCoordinatorV1(source_state=source)
    sequential.apply_exit_fill(fill=stock_fill)
    sequential.apply_exit_fill(fill=option_fill)

    batch = SimulationLifecycleCoordinatorV1(source_state=source)
    result = batch.apply_exit_batch((option_fill, stock_fill))

    assert result.new_closeout_event_count == 2
    assert result.revision == 2
    assert sequential.snapshot().revision == 2
    assert (
        sequential.snapshot().closeout_account
        == batch.snapshot().closeout_account
    )
    assert (
        sequential.snapshot().snapshot_fingerprint
        == batch.snapshot().snapshot_fingerprint
    )


def test_replay_rebuilds_exact_close_and_survivor_mark_snapshot() -> None:
    source = _source()
    stock, option = source.open_positions
    stock_fill = _exit_fill(
        source,
        stock,
        exited_utc=STOCK_EXIT,
        price=11.0,
        fees=1.0,
        source_char="7",
    )
    option_mark = _mark(
        option,
        valuation=VALUATION_1,
        bid=1.5,
        ask=1.6,
        source_char="0",
    )

    expected = replay_simulation_lifecycle_cycle_v1(
        source_state=source,
        exit_fills=(stock_fill,),
        marks=(option_mark,),
        valuation_utc=VALUATION_1,
    )
    assert expected.revision == 2
    assert expected.marked_state is not None
    assert expected.marked_state.closed_trade_count == 1
    assert len(expected.marked_state.marked_positions) == 1

    verify_simulation_lifecycle_cycle_replay_v1(
        expected=expected,
        source_state=source,
        exit_fills=(stock_fill,),
        marks=(option_mark,),
        valuation_utc=VALUATION_1,
    )


def test_all_closed_cycle_can_publish_zero_mark_current_snapshot() -> None:
    source = _source()
    stock, option = source.open_positions
    coordinator = SimulationLifecycleCoordinatorV1(source_state=source)
    coordinator.apply_exit_batch(
        (
            _exit_fill(
                source,
                option,
                exited_utc=OPTION_EXIT,
                price=1.5,
                fees=1.0,
                source_char="8",
            ),
            _exit_fill(
                source,
                stock,
                exited_utc=STOCK_EXIT,
                price=11.0,
                fees=1.0,
                source_char="7",
            ),
        )
    )
    publication = coordinator.publish_marks(
        marks=(),
        valuation_utc=VALUATION_2,
    )
    pair = coordinator.current_dashboard_pair()
    assert publication.revision == 3
    assert pair is not None
    account, marked = pair
    assert account.state.open_positions == ()
    assert marked.marked_positions == ()
    assert marked.marked_equity == pytest.approx(account.state.account_book_equity)
    assert marked.aggregate_unrealized_pnl_dollars == 0.0


def test_single_cycle_boundary_exposes_no_reentry_mutator() -> None:
    coordinator = SimulationLifecycleCoordinatorV1(source_state=_source())
    assert not hasattr(coordinator, "apply_entry_fill")
    assert not hasattr(coordinator, "reserve_capital")
    assert coordinator.snapshot().reentry_supported is False


def test_dashboard_adapter_exposes_only_atomic_current_mark_pair() -> None:
    source = _source()
    stock, option = source.open_positions
    coordinator = SimulationLifecycleCoordinatorV1(source_state=source)
    provider = source_provider_from_coordinator(coordinator)

    assert provider() is None

    coordinator.publish_marks(
        marks=(
            _mark(
                stock,
                valuation=VALUATION_0,
                bid=11.0,
                ask=11.1,
                source_char="9",
            ),
            _mark(
                option,
                valuation=VALUATION_0,
                bid=1.5,
                ask=1.6,
                source_char="0",
            ),
        ),
        valuation_utc=VALUATION_0,
    )
    first = provider()
    assert first is not None
    assert (
        first.marked_state.source_closeout_state_fingerprint
        == first.closeout_account.state.state_fingerprint
    )

    coordinator.apply_exit_fill(
        fill=_exit_fill(
            source,
            stock,
            exited_utc=STOCK_EXIT,
            price=11.0,
            fees=1.0,
            source_char="7",
        )
    )
    assert provider() is None

    coordinator.publish_marks(
        marks=(
            _mark(
                option,
                valuation=VALUATION_1,
                bid=1.5,
                ask=1.6,
                source_char="0",
            ),
        ),
        valuation_utc=VALUATION_1,
    )
    second = provider()
    assert second is not None
    assert len(second.closeout_account.state.open_positions) == 1
    assert len(second.marked_state.marked_positions) == 1
    assert (
        second.marked_state.source_closeout_state_fingerprint
        == second.closeout_account.state.state_fingerprint
    )
