from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from packages.control_plane.simulation_lifecycle_dashboard import (
    SimulationLifecycleDashboardService,
    SimulationLifecycleDashboardSource,
)
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.closeout_account_state import (
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION,
    CloseoutAccountStateV1,
    CloseoutAccountV1,
    CloseoutLedgerV1,
)
from packages.simulation.closeout_account_state_contract import (
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_marked_account_state import (
    build_lifecycle_marked_account_state,
)
from packages.simulation.market_mark_evidence import (
    MarketMarkInputs,
    MarketMarkTransport,
    build_simulated_market_mark_evidence,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)


NOW = datetime(2026, 9, 17, 16, 0, tzinfo=UTC)
OPENED = NOW - timedelta(hours=1)
BOOK_AS_OF = NOW - timedelta(minutes=5)
VALUATION = NOW - timedelta(seconds=2)


def _fp(char: str) -> str:
    return char * 64


def _position() -> SimulatedOpenPositionV1:
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
        reason_codes=("TEST_POSITION",),
    )


def _source() -> SimulationLifecycleDashboardSource:
    position = _position()
    state = CloseoutAccountStateV1(
        contract_version=SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=(
            SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_open_position_contract_fingerprint=(
            OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_open_position_state_fingerprint=_fp("f"),
        as_of_utc=BOOK_AS_OF,
        initial_equity=1000.0,
        source_entry_book_equity=999.0,
        cumulative_entry_fees_dollars=1.0,
        cumulative_exit_fees_dollars=0.0,
        cumulative_account_realized_pnl_dollars=0.0,
        cumulative_lifetime_trade_net_pnl_dollars=0.0,
        cash=899.0,
        account_book_equity=999.0,
        remaining_stock_reserved_capital=0.0,
        remaining_option_reserved_capital=0.0,
        remaining_stock_gross_notional=0.0,
        remaining_option_signed_delta_equivalent_notional=0.0,
        remaining_option_abs_delta_equivalent_notional=0.0,
        open_entry_book_value_dollars=100.0,
        open_stock_gross_entry_exposure_dollars=100.0,
        open_option_entry_book_value_dollars=0.0,
        open_option_signed_delta_equivalent_entry_reference_dollars=0.0,
        open_option_abs_delta_equivalent_entry_reference_dollars=0.0,
        open_option_premium_at_risk_dollars=0.0,
        remaining_stock_reservations=(),
        remaining_option_reservations=(),
        open_positions=(position,),
        closed_trades=(),
    )
    ledger = CloseoutLedgerV1(
        contract_version=SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=(
            SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_open_position_state_fingerprint=(
            state.source_open_position_state_fingerprint
        ),
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    account = CloseoutAccountV1(state=state, ledger=ledger)

    market_time = VALUATION - timedelta(seconds=5)
    mark = build_simulated_market_mark_evidence(
        position=position,
        inputs=MarketMarkInputs(
            source_id="test-aapl-mark",
            source_fingerprint=_fp("9"),
            provider="ALPACA",
            feed="IEX",
            transport=MarketMarkTransport.STREAM,
            feed_quality="REALTIME",
            market_timestamp_utc=market_time,
            received_utc=market_time + timedelta(seconds=1),
            valuation_utc=VALUATION,
            bid_price_per_unit=11.0,
            ask_price_per_unit=11.1,
            last_price_per_unit=11.05,
        ),
    )
    marked = build_lifecycle_marked_account_state(
        source_state=state,
        marks=(mark,),
        valuation_utc=VALUATION,
    )
    return SimulationLifecycleDashboardSource(
        closeout_account=account,
        marked_state=marked,
    )


def test_not_connected_is_explicit_and_zero_authority() -> None:
    payload = SimulationLifecycleDashboardService(
        now_utc=lambda: NOW
    ).snapshot()
    assert payload["status"] == "NOT_CONNECTED"
    assert payload["read_only"] is True
    assert payload["provider_reads"] == 0
    assert payload["provider_writes"] == 0
    assert payload["broker_reads"] == 0
    assert payload["broker_writes"] == 0
    assert payload["order_writes"] == 0
    assert payload["open_positions"] == []
    assert payload["closed_trades"] == []
    assert payload["health"]["engine_source_connected"] is False


def test_valid_engine_owned_source_projects_current_account_and_position() -> None:
    source = _source()
    calls = 0

    def provider():
        nonlocal calls
        calls += 1
        return source

    payload = SimulationLifecycleDashboardService(
        source_provider=provider,
        now_utc=lambda: NOW,
    ).snapshot()

    assert calls == 1
    assert payload["status"] == "AVAILABLE"
    assert payload["read_only"] is True
    assert payload["provider_reads"] == 0
    assert payload["broker_reads"] == 0
    assert payload["provider_writes"] == 0
    assert payload["broker_writes"] == 0
    assert payload["order_writes"] == 0

    account = payload["account"]
    assert account["cash"] == 899.0
    assert account["account_book_equity"] == 999.0
    assert account["marked_equity"] == 1009.0
    assert account["aggregate_unrealized_pnl_dollars"] == 10.0
    assert account["snapshot_kind"] == (
        "ENGINE_OWNED_SIMULATION_LIFECYCLE_CURRENT"
    )

    assert len(payload["open_positions"]) == 1
    row = payload["open_positions"][0]
    assert row["ticker"] == "AAPL"
    assert row["direction"] == "bullish"
    assert row["quantity"] == 10.0
    assert row["entry_price_per_unit"] == 10.0
    assert row["selected_mark_price_per_unit"] == 11.0
    assert row["unrealized_pnl_dollars"] == 10.0
    assert row["position_state"] == "OPEN_SIMULATION_MARKED"

    assert payload["statistics"]["open_position_count"] == 1
    assert payload["statistics"]["closed_trade_count"] == 0
    assert payload["health"]["source_valid"] is True
    assert payload["health"]["complete_mark_coverage"] is True
    assert payload["authority"]["paper_authority"] is False
    assert payload["authority"]["live_authority"] is False


def test_marked_state_must_bind_exact_closeout_state() -> None:
    source = _source()
    tampered_marked = replace(
        source.marked_state,
        source_closeout_state_fingerprint=_fp("0"),
    )
    payload = SimulationLifecycleDashboardService(
        source_provider=lambda: SimulationLifecycleDashboardSource(
            closeout_account=source.closeout_account,
            marked_state=tampered_marked,
        ),
        now_utc=lambda: NOW,
    ).snapshot()
    assert payload["status"] == "INVALID"
    assert payload["account"] is None
    assert payload["open_positions"] == []
    assert payload["health"]["source_valid"] is False


def test_source_provider_failure_is_invalid_without_external_fallback() -> None:
    def provider():
        raise RuntimeError("synthetic source failure")

    payload = SimulationLifecycleDashboardService(
        source_provider=provider,
        now_utc=lambda: NOW,
    ).snapshot()
    assert payload["status"] == "INVALID"
    assert payload["error"] == "RuntimeError"
    assert payload["provider_reads"] == 0
    assert payload["broker_reads"] == 0
    assert payload["provider_writes"] == 0
    assert payload["broker_writes"] == 0
    assert payload["health"]["reason"] == (
        "ENGINE_LIFECYCLE_SOURCE_FAILED_VALIDATION"
    )


def test_none_from_injected_provider_remains_not_connected() -> None:
    payload = SimulationLifecycleDashboardService(
        source_provider=lambda: None,
        now_utc=lambda: NOW,
    ).snapshot()
    assert payload["status"] == "NOT_CONNECTED"
    assert payload["health"]["engine_source_connected"] is False
    assert payload["health"]["reason"] == (
        "SIMULATION_LIFECYCLE_SOURCE_NOT_AVAILABLE"
    )
