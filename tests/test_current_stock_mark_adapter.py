from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.core.enums import (
    LiveConnectionState,
    LiveFeedMode,
)
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.live_market import LiveStateSnapshot
from packages.simulation.current_live_evidence import (
    CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT,
    CURRENT_LIVE_EVIDENCE_CONTRACT_VERSION,
    CURRENT_LIVE_EVIDENCE_SOURCE_ID,
    CurrentLiveEvidenceV1,
)
from packages.simulation.current_stock_mark_adapter import (
    CURRENT_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT,
    CurrentStockMarkAdapterError,
    build_current_stock_marks_v1,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1


def _position(*, ticker: str = "AAPL") -> SimulatedOpenPositionV1:
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint="1" * 64,
        decision_record_fingerprint="2" * 64,
        candidate_fingerprint="3" * 64,
        fill_fingerprint="4" * 64,
        funding_terms_fingerprint="5" * 64,
        reservation_fingerprint="6" * 64,
        option_reservation_terms_fingerprint=None,
        option_economics_result_fingerprint=None,
        instrument_kind=InstrumentKind.STOCK,
        instrument_id=f"instrument:{ticker}",
        ticker=ticker,
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier=f"STOCK:{ticker}",
        option_contract_ticker=None,
        option_contract_type=None,
        opened_utc=datetime(2026, 9, 18, 19, 57, 30, tzinfo=UTC),
        quantity=10.0,
        quantity_unit="SHARES",
        entry_price_per_unit=100.0,
        contract_multiplier=1.0,
        entry_book_value_dollars=1_000.0,
        entry_fees_dollars=2.0,
        all_in_cash_cost_basis_dollars=1_002.0,
        original_reserved_capital_dollars=1_000.0,
        supplemental_cash_consumed_dollars=2.0,
        unspent_reserve_returned_dollars=0.0,
        stock_gross_entry_exposure_dollars=1_000.0,
        option_premium_at_risk_dollars=0.0,
        option_signed_delta_equivalent_entry_reference_dollars=0.0,
        option_abs_delta_equivalent_entry_reference_dollars=0.0,
        reason_codes=("TEST_STOCK_POSITION",),
    )


def _snapshot(
    *,
    symbol: str = "AAPL",
    feed_mode: str = "realtime",
    delay: int = 0,
    quote: bool = True,
    quote_freshness: str = "fresh",
    connection: str = "subscribed",
    open_gap: bool = False,
    quote_time: str = "2026-09-18T20:00:00+00:00",
) -> LiveStateSnapshot:
    state = {
        "symbol": symbol,
        "as_of_utc": "2026-09-18T20:00:02+00:00",
        "minute": None,
        "minute_freshness": "unknown",
        "quote": None,
        "quote_freshness": "unknown",
    }
    if quote:
        state["quote"] = {
            "symbol": symbol,
            "provider_timestamp_utc": quote_time,
            "session_date": "2026-09-18",
            "session_segment": "regular",
            "bid_price": 101.0,
            "bid_size": 10,
            "ask_price": 101.1,
            "ask_size": 12,
            "sequence": 10,
            "feed_mode": feed_mode,
            "expected_delay_seconds": delay,
            "received_at_utc": "2026-09-18T20:00:01+00:00",
        }
        state["quote_freshness"] = quote_freshness
    return LiveStateSnapshot.model_validate(
        {
            "generated_at_utc": "2026-09-18T20:00:02+00:00",
            "feed_mode": feed_mode,
            "expected_delay_seconds": delay,
            "connection_state": connection,
            "subscriptions": [f"Q.{symbol}"],
            "session": {
                "as_of_utc": "2026-09-18T20:00:02+00:00",
                "local_date": "2026-09-18",
                "is_exchange_session": True,
                "session_segment": "regular",
                "regular_open_utc": "2026-09-18T13:30:00+00:00",
                "regular_close_utc": "2026-09-18T20:00:00+00:00",
                "next_session_date": "2026-09-21",
                "next_regular_open_utc": "2026-09-21T13:30:00+00:00",
            },
            "received_events": 1,
            "accepted_events": 1,
            "ignored_out_of_order_events": 0,
            "parse_errors": 0,
            "reconnects": 0,
            "restored_symbol_count": 0,
            "observed_symbol_count": 1,
            "last_received_at_utc": "2026-09-18T20:00:01+00:00",
            "transport_gaps": [],
            "open_transport_gap_started_at_utc": (
                "2026-09-18T19:59:50+00:00"
                if open_gap
                else None
            ),
            "symbols": [state],
        }
    )


def _evidence(snapshot: LiveStateSnapshot) -> CurrentLiveEvidenceV1:
    return CurrentLiveEvidenceV1(
        contract_version=CURRENT_LIVE_EVIDENCE_CONTRACT_VERSION,
        contract_fingerprint=CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT,
        source_id=CURRENT_LIVE_EVIDENCE_SOURCE_ID,
        source_sha256="a" * 64,
        source_byte_count=100,
        captured_at_utc=datetime(
            2026, 9, 18, 20, 0, 2, tzinfo=UTC
        ),
        snapshot=snapshot,
    )


def test_current_stock_mark_adapter_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
        == "2ff8bfc7afff4b072b37e364a46aa565d40d4d91a29a799de0aece13bb2ac4c0"
    )


def test_realtime_quote_builds_exact_fresh_stock_mark() -> None:
    evidence = _evidence(_snapshot())
    batch = build_current_stock_marks_v1(
        evidence=evidence,
        positions=(_position(),),
        valuation_utc=datetime(
            2026, 9, 18, 20, 0, 3, tzinfo=UTC
        ),
    )
    assert len(batch.marks) == 1
    mark = batch.marks[0]
    assert mark.ticker == "AAPL"
    assert mark.bid_price_per_unit == pytest.approx(101.0)
    assert mark.ask_price_per_unit == pytest.approx(101.1)
    assert mark.selected_mark_price_per_unit == pytest.approx(101.0)
    assert mark.valuation_eligible is True
    assert mark.source_fingerprint == evidence.source_sha256
    assert len(batch.batch_fingerprint) == 64
    assert batch.provider_read_authority is False
    assert batch.broker_read_authority is False


def test_delayed_feed_fails_closed() -> None:
    evidence = _evidence(
        _snapshot(feed_mode="delayed", delay=900)
    )
    with pytest.raises(
        CurrentStockMarkAdapterError,
        match="require realtime",
    ):
        build_current_stock_marks_v1(
            evidence=evidence,
            positions=(_position(),),
            valuation_utc=datetime(
                2026, 9, 18, 20, 0, 3, tzinfo=UTC
            ),
        )


def test_minute_only_state_is_not_fabricated_into_quote() -> None:
    evidence = _evidence(_snapshot(quote=False))
    with pytest.raises(
        CurrentStockMarkAdapterError,
        match="minute bars are not quotes",
    ):
        build_current_stock_marks_v1(
            evidence=evidence,
            positions=(_position(),),
            valuation_utc=datetime(
                2026, 9, 18, 20, 0, 3, tzinfo=UTC
            ),
        )


def test_exact_case_symbol_identity_is_required() -> None:
    evidence = _evidence(_snapshot(symbol="aapl"))
    with pytest.raises(
        CurrentStockMarkAdapterError,
        match="missing exact-case",
    ):
        build_current_stock_marks_v1(
            evidence=evidence,
            positions=(_position(ticker="AAPL"),),
            valuation_utc=datetime(
                2026, 9, 18, 20, 0, 3, tzinfo=UTC
            ),
        )


def test_open_transport_gap_fails_closed() -> None:
    evidence = _evidence(_snapshot(open_gap=True))
    with pytest.raises(
        CurrentStockMarkAdapterError,
        match="open transport gap",
    ):
        build_current_stock_marks_v1(
            evidence=evidence,
            positions=(_position(),),
            valuation_utc=datetime(
                2026, 9, 18, 20, 0, 3, tzinfo=UTC
            ),
        )


def test_mark_older_than_frozen_age_policy_fails_closed() -> None:
    evidence = _evidence(
        _snapshot(quote_time="2026-09-18T19:58:00+00:00")
    )
    with pytest.raises(
        CurrentStockMarkAdapterError,
        match="exceeds mark freshness",
    ):
        build_current_stock_marks_v1(
            evidence=evidence,
            positions=(_position(),),
            valuation_utc=datetime(
                2026, 9, 18, 20, 0, 3, tzinfo=UTC
            ),
        )


def test_evidence_captured_after_valuation_fails_closed() -> None:
    evidence = _evidence(_snapshot())
    with pytest.raises(
        CurrentStockMarkAdapterError,
        match="captured after valuation",
    ):
        build_current_stock_marks_v1(
            evidence=evidence,
            positions=(_position(),),
            valuation_utc=datetime(
                2026, 9, 18, 20, 0, 1, tzinfo=UTC
            ),
        )
