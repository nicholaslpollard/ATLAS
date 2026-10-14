from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from packages.simulation.offline_option_exit_retry_v1 import (
    OptionExitRetryCursorV1, OptionExitRetryError, SyntheticExitQuoteV1,
    advance_option_exit_retry, build_option_exit_retry_plan,
    restore_option_exit_retry_cursor,
)


def stamp(day: str, clock: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{clock}+00:00")


def plan(**overrides):
    fields = dict(
        option_symbol="O:TEST220121C00100000", expiration=date(2022, 1, 21),
        opened_at_utc=stamp("2022-01-04", "14:35:00"),
        requested_exit_at_utc=stamp("2022-01-05", "14:35:00"),
        deadline_at_utc=stamp("2022-01-05", "14:40:00"),
        retry_interval_seconds=60, maximum_attempts=3, maximum_quote_age_seconds=30,
    )
    return build_option_exit_retry_plan(**(fields | overrides))


def quote(at, **overrides):
    fields = dict(
        option_symbol="O:TEST220121C00100000", observed_at_utc=at,
        available_at_utc=at, bid_per_share="3.00", ask_per_share="3.10",
        bid_size_contracts=10, source_integrity_qualified=True,
        observation_clock_qualified=True,
    )
    return SyntheticExitQuoteV1(**(fields | overrides))


def cursor(p=None):
    p = p or plan()
    return OptionExitRetryCursorV1(p, 4, "0.00", p.opened_at_utc)


def test_schedule_is_frozen_bounded_and_independent_of_quote_outcomes():
    p = plan()
    assert p.attempt_times_utc == tuple(stamp("2022-01-05", f"14:{minute}:00")
                                       for minute in (35, 36, 37))
    assert p == plan()
    assert p.fingerprint == plan().fingerprint
    calls = []
    advanced = advance_option_exit_retry(cursor(p), as_of_utc=p.deadline_at_utc,
        read_quote=lambda symbol, at: calls.append((symbol, at)))
    assert calls == [(p.option_symbol, at) for at in p.attempt_times_utc]
    assert [a.result for a in advanced.attempts] == ["NO_QUOTE"] * 3
    assert advanced.status == "OPEN_UNRESOLVED_EXIT_RETRY_LIMIT"


def test_early_close_holiday_and_weekend_roll_to_next_regular_open():
    p = plan(
        option_symbol="O:TEST251219C00100000", expiration=date(2025, 12, 19),
        opened_at_utc=stamp("2025-11-26", "14:35:00"),
        requested_exit_at_utc=stamp("2025-11-27", "15:00:00"),
        deadline_at_utc=stamp("2025-12-01", "15:00:00"),
        retry_interval_seconds=3 * 3600, maximum_attempts=4,
    )
    assert p.attempt_times_utc == (
        stamp("2025-11-28", "14:30:00"), stamp("2025-11-28", "17:30:00"),
        stamp("2025-12-01", "14:30:00"),
    )
    assert p.session_windows_utc[0][1] == stamp("2025-11-28", "18:00:00")
    at_close = plan(
        option_symbol=p.option_symbol, expiration=p.expiration,
        opened_at_utc=p.opened_at_utc,
        requested_exit_at_utc=stamp("2025-11-28", "18:00:00"),
        deadline_at_utc=p.deadline_at_utc,
    )
    assert at_close.attempt_times_utc[0] == stamp("2025-12-01", "14:30:00")


def test_daylight_saving_shift_uses_calendar_open_not_fixed_utc_hour():
    p = plan(
        option_symbol="O:TEST220318C00100000", expiration=date(2022, 3, 18),
        opened_at_utc=stamp("2022-03-11", "14:35:00"),
        requested_exit_at_utc=stamp("2022-03-11", "20:59:00"),
        deadline_at_utc=stamp("2022-03-14", "13:35:00"),
        retry_interval_seconds=60,
    )
    assert p.attempt_times_utc == (
        stamp("2022-03-11", "20:59:00"), stamp("2022-03-14", "13:30:00"),
        stamp("2022-03-14", "13:31:00"),
    )


def test_deadline_is_inclusive_and_does_not_extend_to_future_quote():
    p = plan(deadline_at_utc=stamp("2022-01-05", "14:36:00"), maximum_attempts=64)
    calls = []
    c = advance_option_exit_retry(cursor(p), as_of_utc=stamp("2022-01-06", "15:00:00"),
        read_quote=lambda symbol, at: calls.append(at))
    assert calls == list(p.attempt_times_utc)
    assert len(c.attempts) == 2
    assert c.status == "OPEN_UNRESOLVED_EXIT_RETRY_DEADLINE"


def test_no_regular_session_in_window_stays_unresolved_without_source_read():
    p = plan(opened_at_utc=stamp("2022-01-07", "14:35:00"),
             requested_exit_at_utc=stamp("2022-01-08", "15:00:00"),
             deadline_at_utc=stamp("2022-01-09", "20:00:00"))
    assert p.attempt_times_utc == ()
    c = advance_option_exit_retry(cursor(p), as_of_utc=p.deadline_at_utc,
        read_quote=lambda *_: pytest.fail("weekend must not request a quote"))
    assert c.status == "OPEN_UNRESOLVED_EXIT_RETRY_DEADLINE"


@pytest.mark.parametrize("changes,reason", [
    ({"option_symbol": "O:OTHER220121C00100000"}, "QUOTE_CONTRACT_MISMATCH"),
    ({"source_integrity_qualified": False}, "UNQUALIFIED_QUOTE_SOURCE"),
    ({"observation_clock_qualified": False}, "UNQUALIFIED_QUOTE_CLOCK"),
    ({"bid_per_share": None}, "ONE_SIDED_QUOTE"),
    ({"ask_per_share": None}, "ONE_SIDED_QUOTE"),
    ({"bid_per_share": "0"}, "NO_EXECUTABLE_BID"),
    ({"ask_per_share": "2.9"}, "CROSSED_QUOTE"),
    ({"bid_per_share": "NaN"}, "INVALID_QUOTE_PRICE"),
    ({"bid_per_share": "Infinity"}, "INVALID_QUOTE_PRICE"),
    ({"bid_per_share": "1e999999"}, "INVALID_QUOTE_PRICE"),
    ({"bid_per_share": "0.000001"}, "NO_POSITIVE_MODELED_EXIT_CREDIT"),
    ({"bid_size_contracts": 3}, "INSUFFICIENT_DISPLAYED_BID_SIZE"),
    ({"bid_size_contracts": None}, "INSUFFICIENT_DISPLAYED_BID_SIZE"),
])
def test_unusable_quotes_are_attempt_failures_not_closes(changes, reason):
    c = cursor()
    at = c.plan.attempt_times_utc[0]
    after = advance_option_exit_retry(c, as_of_utc=at, read_quote=lambda *_: quote(at, **changes))
    assert after.ready_quote is None
    assert after.attempts[0].result == reason
    assert after.status == "OPEN_AWAITING_EXIT_RETRY"


@pytest.mark.parametrize("observed_delta,available_delta,reason", [
    (1, 1, "FUTURE_QUOTE"),
    (0, 1, "QUOTE_NOT_AVAILABLE_BY_ATTEMPT"),
    (-31, 0, "STALE_QUOTE"),
    (0, -1, "INVALID_QUOTE_AVAILABILITY_CLOCK"),
])
def test_quote_observation_availability_and_age_are_distinct(observed_delta, available_delta, reason):
    c = cursor()
    at = c.plan.attempt_times_utc[0]
    q = quote(at, observed_at_utc=at + timedelta(seconds=observed_delta),
              available_at_utc=at + timedelta(seconds=available_delta))
    after = advance_option_exit_retry(c, as_of_utc=at, read_quote=lambda *_: q)
    assert after.attempts[0].result == reason


def test_preopen_quote_is_not_reused_as_an_opening_quote_even_with_fresh_clock():
    p = plan(requested_exit_at_utc=stamp("2022-01-05", "14:30:00"))
    at = p.attempt_times_utc[0]
    c = advance_option_exit_retry(cursor(p), as_of_utc=at,
        read_quote=lambda *_: quote(at, observed_at_utc=at - timedelta(seconds=1)))
    assert c.attempts[0].result == "QUOTE_OUTSIDE_PLANNED_SESSION"


def test_known_slippage_that_consumes_bid_cannot_fabricate_zero_price_exit():
    c = replace(cursor(), slippage_per_share="3.00")
    at = c.plan.attempt_times_utc[0]
    after = advance_option_exit_retry(c, as_of_utc=at, read_quote=lambda *_: quote(at))
    assert after.attempts[0].result == "SLIPPAGE_CONSUMES_BID"


def test_restart_reuses_completed_prefix_and_stops_after_first_ready_quote():
    c = cursor()
    first, second, third = c.plan.attempt_times_utc
    partial = advance_option_exit_retry(c, as_of_utc=first, read_quote=lambda *_: None)
    restored = restore_option_exit_retry_cursor(json.loads(json.dumps(partial.payload())),
        expected_fingerprint=partial.fingerprint, expected_plan_fingerprint=c.plan.fingerprint)
    calls = []
    resumed = advance_option_exit_retry(restored, as_of_utc=c.plan.deadline_at_utc,
        read_quote=lambda symbol, at: calls.append(at) or quote(at))
    assert calls == [second]
    assert resumed.ready_quote.observed_at_utc == second
    continuous = advance_option_exit_retry(c, as_of_utc=c.plan.deadline_at_utc,
        read_quote=lambda symbol, at: None if at == first else quote(at))
    assert resumed == continuous
    assert advance_option_exit_retry(resumed, as_of_utc=resumed.as_of_utc,
        read_quote=lambda *_: pytest.fail("completed retry must not be reread")) == resumed
    assert third not in calls


def test_future_quotes_are_not_read_before_scheduled_attempt():
    c = cursor()
    before = advance_option_exit_retry(c, as_of_utc=c.plan.requested_exit_at_utc - timedelta(seconds=1),
        read_quote=lambda *_: pytest.fail("future quote must not be read"))
    assert before.attempts == ()
    assert before.status == "OPEN_EXIT_NOT_REQUESTED_YET"


def test_checkpoint_tampering_and_a_different_plan_cannot_resume():
    c = cursor()
    at = c.plan.attempt_times_utc[0]
    c = advance_option_exit_retry(c, as_of_utc=at, read_quote=lambda *_: None)
    for field, value in (("required_contracts", 5), ("as_of_utc", "2022-01-05T15:00:00+00:00")):
        altered = copy.deepcopy(c.payload())
        altered[field] = value
        with pytest.raises(OptionExitRetryError, match="fingerprint"):
            restore_option_exit_retry_cursor(altered, expected_fingerprint=c.fingerprint,
                                              expected_plan_fingerprint=c.plan.fingerprint)
    with pytest.raises(OptionExitRetryError, match="fingerprint"):
        restore_option_exit_retry_cursor(c.payload(), expected_fingerprint=c.fingerprint,
                                          expected_plan_fingerprint=plan(maximum_attempts=4).fingerprint)
    with pytest.raises(OptionExitRetryError, match="omitted"):
        replace(c, attempts=())
    with pytest.raises(OptionExitRetryError, match="backwards"):
        advance_option_exit_retry(c, as_of_utc=c.as_of_utc - timedelta(seconds=1), read_quote=lambda *_: None)


@pytest.mark.parametrize("changes", [
    {"maximum_attempts": 65}, {"maximum_attempts": True}, {"retry_interval_seconds": 0},
    {"maximum_quote_age_seconds": -1}, {"maximum_quote_age_seconds": 3601},
    {"requested_exit_at_utc": datetime(2022, 1, 5, 14, 35)},
    {"deadline_at_utc": stamp("2022-01-21", "14:35:00")},
    {"option_symbol": "O:TEST220122C00100000"},
])
def test_invalid_plan_never_queries_calendar(changes):
    class ForbiddenCalendar:
        exchange = "XNYS"
        def sessions_in_range(self, *_):
            pytest.fail("invalid policy must fail before calendar reads")
    with pytest.raises(OptionExitRetryError):
        plan(calendar=ForbiddenCalendar(), **changes)


def test_long_window_fails_before_calendar_and_historical_origin_is_rejected():
    with pytest.raises(OptionExitRetryError, match="window"):
        plan(option_symbol="O:TEST220318C00100000", expiration=date(2022, 3, 18),
             deadline_at_utc=stamp("2022-03-01", "15:00:00"))
    with pytest.raises(OptionExitRetryError, match="impersonate"):
        quote(stamp("2022-01-05", "14:35:00"), origin="HISTORICAL_SOURCE")


def test_checkpoint_restore_refuses_oversized_or_nonjson_objects():
    c = cursor()
    for extra in ("x" * (256 * 1024), {"not_json"}):
        payload = c.payload() | {"extra": extra}
        with pytest.raises(OptionExitRetryError, match="encoding"):
            restore_option_exit_retry_cursor(payload, expected_fingerprint=c.fingerprint,
                                              expected_plan_fingerprint=c.plan.fingerprint)


def test_checkpoint_reconciles_saved_failures_and_ready_quote_without_reopening_source():
    c = cursor()
    first, second, _ = c.plan.attempt_times_utc
    after = advance_option_exit_retry(c, as_of_utc=second,
        read_quote=lambda symbol, at: quote(at, ask_per_share="2.90") if at == first else quote(at))
    restored = restore_option_exit_retry_cursor(json.loads(json.dumps(after.payload())),
        expected_fingerprint=after.fingerprint, expected_plan_fingerprint=c.plan.fingerprint)
    assert restored == after
    assert restored.attempts[0].result == "CROSSED_QUOTE"
    assert restored.ready_quote is not None
