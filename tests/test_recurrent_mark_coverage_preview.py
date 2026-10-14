from dataclasses import replace
from datetime import timedelta

import pytest

from packages.execution.trade_expression import InstrumentKind
from packages.simulation.recurrent_engine import RecurrentLifecycleCoordinatorV1
from packages.simulation.recurrent_marked_state import (
    RecurrentMarkedAccountError, build_recurrent_mark_coverage_preview,
    build_recurrent_marked_account_state,
)
from tests.test_lifecycle_reservation_state import _market_mark, _recurrent_positioned_account


def fixture():
    account = _recurrent_positioned_account()
    at = account.state.as_of_utc + timedelta(minutes=2)
    marks = tuple(_market_mark(p, valuation_utc=at,
        bid=1.5 if p.instrument_kind == InstrumentKind.OPTION else 101.0,
        ask=1.6 if p.instrument_kind == InstrumentKind.OPTION else 101.1,
        source_char="d") for p in account.state.open_positions)
    return account, at, marks


def test_partial_coverage_keeps_total_equity_unknown_and_strict_builder_closed():
    account, at, marks = fixture()
    preview = build_recurrent_mark_coverage_preview(source_state=account.state, marks=marks[:1], valuation_utc=at)
    assert preview["known_mark_count"] == 1
    assert preview["unknown_mark_count"] == len(account.state.open_positions) - 1
    assert preview["marked_equity"] is None
    assert preview["aggregate_unrealized_pnl_dollars"] is None
    assert preview["accepted_valuation_state_fingerprint"] is None
    assert preview["cash"] == account.state.cash
    assert preview["known_marked_position_value_dollars"] > 0
    with pytest.raises(RecurrentMarkedAccountError, match="complete"):
        build_recurrent_marked_account_state(source_state=account.state, marks=marks[:1], valuation_utc=at)


def test_stale_and_old_valuation_marks_are_unknown_and_do_not_use_old_prices():
    account, at, marks = fixture()
    first = account.state.open_positions[0]
    stale = _market_mark(first, valuation_utc=at, bid=999.0, ask=1000.0, source_char="e", age_seconds=61)
    preview = build_recurrent_mark_coverage_preview(source_state=account.state, marks=(stale, *marks[1:]), valuation_utc=at)
    assert preview["positions"][0]["status"] == "STALE_OR_INELIGIBLE_MARK"
    assert preview["positions"][0]["marked_value_dollars"] is None
    old = _market_mark(first, valuation_utc=at - timedelta(seconds=1), bid=999.0, ask=1000.0, source_char="e")
    preview = build_recurrent_mark_coverage_preview(source_state=account.state, marks=(old, *marks[1:]), valuation_utc=at)
    assert preview["positions"][0]["status"] == "VALUATION_CLOCK_MISMATCH"
    assert preview["marked_equity"] is None


def test_full_coverage_matches_existing_accepted_valuation_and_order_is_stable():
    account, at, marks = fixture()
    strict = build_recurrent_marked_account_state(source_state=account.state, marks=marks, valuation_utc=at)
    preview = build_recurrent_mark_coverage_preview(source_state=account.state, marks=marks, valuation_utc=at)
    assert preview == build_recurrent_mark_coverage_preview(source_state=account.state, marks=tuple(reversed(marks)), valuation_utc=at)
    assert preview["marked_equity"] == strict.marked_equity
    assert preview["aggregate_unrealized_pnl_dollars"] == strict.aggregate_unrealized_pnl_dollars
    assert preview["accepted_valuation_state_fingerprint"] == strict.state_fingerprint


def test_zero_option_bid_is_a_known_mark_and_never_a_forced_close():
    account, at, marks = fixture()
    option = next(p for p in account.state.open_positions if p.instrument_kind == InstrumentKind.OPTION)
    zero = _market_mark(option, valuation_utc=at, bid=0.0, ask=0.1, source_char="e")
    chosen = tuple(zero if mark.position_fingerprint == option.position_fingerprint else mark for mark in marks)
    coordinator = RecurrentLifecycleCoordinatorV1(account=account)
    before = coordinator.snapshot()
    preview = coordinator.mark_coverage_preview(marks=chosen, valuation_utc=at)
    row = next(r for r in preview["positions"] if r["instrument_kind"] == "OPTION")
    assert row["status"] == "FRESH_BOUND_MARK" and row["marked_value_dollars"] == 0.0
    assert coordinator.snapshot() == before
    assert coordinator.current_marked_state() is None
    assert coordinator.current_dashboard_pair() is None


def test_missing_mark_preview_does_not_mutate_account_or_replace_published_valuation():
    account, at, marks = fixture()
    coordinator = RecurrentLifecycleCoordinatorV1(account=account)
    before = coordinator.snapshot()
    preview = coordinator.mark_coverage_preview(marks=(), valuation_utc=at)
    assert preview["known_marked_position_value_dollars"] == 0.0
    assert preview["marked_equity"] is None
    assert preview["account_mutation_authority"] is False
    assert coordinator.snapshot() == before


def test_duplicate_extra_or_wrong_lineage_marks_still_fail_closed():
    account, at, marks = fixture()
    with pytest.raises(RecurrentMarkedAccountError, match="duplicate"):
        build_recurrent_mark_coverage_preview(source_state=account.state, marks=(*marks, marks[0]), valuation_utc=at)
    altered = replace(marks[0], ticker="WRONG")
    with pytest.raises(RecurrentMarkedAccountError, match="ticker"):
        build_recurrent_mark_coverage_preview(source_state=account.state, marks=(altered, *marks[1:]), valuation_utc=at)
    with pytest.raises(RecurrentMarkedAccountError, match="predates"):
        build_recurrent_mark_coverage_preview(source_state=account.state, marks=(), valuation_utc=account.state.as_of_utc - timedelta(seconds=1))
