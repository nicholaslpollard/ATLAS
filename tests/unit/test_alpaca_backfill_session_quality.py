from datetime import date

from packages.data.alpaca_backfill_session_quality import (
    TRADE_BACKED,
    ZERO_ACTIVITY_PLACEHOLDER,
    analyze_symbol_session_status,
    merge_unit_session,
    xnys_session_ordinals,
)


def test_gate5b_xnys_calendar_excludes_july_2020_holiday_and_weekend() -> None:
    ordinals = xnys_session_ordinals(date(2020, 7, 1), date(2020, 7, 6))
    sessions = [date.fromordinal(value) for value in ordinals]

    assert sessions == [
        date(2020, 7, 1),
        date(2020, 7, 2),
        date(2020, 7, 6),
    ]


def test_gate5b_trade_lifespan_counts_trade_placeholder_and_absent_runs() -> None:
    sessions = tuple(date(2020, 1, day).toordinal() for day in (6, 7, 8, 9))
    index = {ordinal: position for position, ordinal in enumerate(sessions)}
    status = {
        sessions[0]: TRADE_BACKED,
        sessions[1]: ZERO_ACTIVITY_PLACEHOLDER,
        sessions[3]: TRADE_BACKED,
    }

    result = analyze_symbol_session_status(status, sessions, index)

    assert result.evaluable_trade_lifespan is True
    assert result.expected_xnys_sessions == 4
    assert result.trade_backed_sessions == 2
    assert result.placeholder_sessions == 1
    assert result.missing_sessions == 1
    assert result.raw_session_coverage_ratio == 0.75
    assert result.trade_backed_coverage_ratio == 0.5
    assert result.max_consecutive_placeholder_sessions == 1
    assert result.max_consecutive_missing_sessions == 1
    assert result.max_consecutive_no_trade_backed_sessions == 2


def test_gate5b_placeholder_tails_do_not_expand_trade_lifespan() -> None:
    sessions = tuple(date(2020, 1, day).toordinal() for day in (6, 7, 8, 9, 10))
    index = {ordinal: position for position, ordinal in enumerate(sessions)}
    status = {
        sessions[0]: ZERO_ACTIVITY_PLACEHOLDER,
        sessions[1]: TRADE_BACKED,
        sessions[3]: TRADE_BACKED,
        sessions[4]: ZERO_ACTIVITY_PLACEHOLDER,
    }

    result = analyze_symbol_session_status(status, sessions, index)

    assert result.first_trade_session == "2020-01-07"
    assert result.last_trade_session == "2020-01-09"
    assert result.expected_xnys_sessions == 3
    assert result.trade_backed_sessions == 2
    assert result.placeholder_sessions == 0
    assert result.missing_sessions == 1
    assert result.placeholder_sessions_outside_trade_lifespan == 2


def test_gate5b_placeholder_only_symbol_is_not_assumed_missing_lifespan() -> None:
    sessions = tuple(date(2020, 1, day).toordinal() for day in (6, 7, 8))
    index = {ordinal: position for position, ordinal in enumerate(sessions)}
    status = {
        sessions[0]: ZERO_ACTIVITY_PLACEHOLDER,
        sessions[2]: ZERO_ACTIVITY_PLACEHOLDER,
    }

    result = analyze_symbol_session_status(status, sessions, index)

    assert result.evaluable_trade_lifespan is False
    assert result.placeholder_only is True
    assert result.trade_backed_nonexchange_only is False
    assert result.expected_xnys_sessions == 0
    assert result.missing_sessions == 0
    assert result.placeholder_sessions_outside_trade_lifespan == 2


def test_gate5b_duplicate_merge_distinguishes_exact_and_conflicting_evidence() -> None:
    merged = merge_unit_session(None, status=TRADE_BACKED, signature="A")
    merged = merge_unit_session(merged, status=TRADE_BACKED, signature="A")
    merged = merge_unit_session(
        merged,
        status=ZERO_ACTIVITY_PLACEHOLDER,
        signature="B",
    )

    assert merged["row_count"] == 3
    assert merged["exact_duplicate_rows"] == 1
    assert merged["conflicting_duplicate_rows"] == 1
    assert merged["signatures"] == {"A", "B"}
    assert merged["statuses"] == {TRADE_BACKED, ZERO_ACTIVITY_PLACEHOLDER}
    assert merged["merged_status"] == TRADE_BACKED
