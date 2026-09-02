from __future__ import annotations

from datetime import date

import pytest

from packages.backtesting.literature_momseason_development_identity_repair import (
    LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION,
    _unique_authoritative_composite_figi,
    authoritative_ticker_from_massive_events,
    resolve_target_ticker_from_pit_rows,
)


def _row(
    ticker: str,
    *,
    active: bool,
    quality: str = "strong",
    composite_figi: str | None = None,
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "active": active,
        "identity_quality": quality,
        "composite_figi": composite_figi,
    }


def _ticker_event(event_date: str, ticker: str) -> dict[str, object]:
    return {
        "type": "ticker_change",
        "date": event_date,
        "ticker_change": {"ticker": ticker},
    }


def test_identity_repair_version_is_explicit() -> None:
    assert LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION.startswith(
        "lit01-development-target-identity-v4"
    )


def test_unique_active_alias_wins_over_inactive_historical_alias() -> None:
    ticker, reason = resolve_target_ticker_from_pit_rows(
        [_row("OLD", active=False), _row("NEW", active=True)],
        endpoint_session=date(2021, 10, 29),
        instrument_id="ins_test",
        authoritative_ticker=None,
    )
    assert ticker == "NEW"
    assert reason == "UNIQUE_ACTIVE_PIT_ALIAS"


def test_authoritative_interval_disambiguates_multiple_active_aliases() -> None:
    ticker, reason = resolve_target_ticker_from_pit_rows(
        [_row("AAA", active=True), _row("BBB", active=True)],
        endpoint_session=date(2021, 10, 29),
        instrument_id="ins_test",
        authoritative_ticker="BBB",
    )
    assert ticker == "BBB"
    assert reason == "AUTHORITATIVE_INTERVAL_ACTIVE_ALIAS"


def test_exact_when_issued_pair_retains_regular_alias() -> None:
    ticker, reason = resolve_target_ticker_from_pit_rows(
        [_row("VMW", active=True), _row("VMWw", active=True)],
        endpoint_session=date(2021, 10, 29),
        instrument_id="ins_test",
        authoritative_ticker=None,
    )
    assert ticker == "VMW"
    assert reason == "REGULAR_ALIAS_WITH_WHEN_ISSUED_VARIANT"


def test_when_issued_rule_is_case_sensitive_and_narrow() -> None:
    with pytest.raises(RuntimeError, match="ambiguous active PIT ticker"):
        resolve_target_ticker_from_pit_rows(
            [_row("VMW", active=True), _row("VMWW", active=True)],
            endpoint_session=date(2021, 10, 29),
            instrument_id="ins_test",
            authoritative_ticker=None,
        )


def test_when_issued_rule_does_not_resolve_more_than_exact_pair() -> None:
    with pytest.raises(RuntimeError, match="ambiguous active PIT ticker"):
        resolve_target_ticker_from_pit_rows(
            [
                _row("AAA", active=True),
                _row("AAAw", active=True),
                _row("BBB", active=True),
            ],
            endpoint_session=date(2021, 10, 29),
            instrument_id="ins_test",
            authoritative_ticker=None,
        )


def test_ambiguous_active_aliases_without_authority_fail_closed() -> None:
    with pytest.raises(RuntimeError, match="ambiguous active PIT ticker"):
        resolve_target_ticker_from_pit_rows(
            [_row("AAA", active=True), _row("BBB", active=True)],
            endpoint_session=date(2021, 10, 29),
            instrument_id="ins_test",
            authoritative_ticker=None,
        )


def test_authoritative_interval_must_match_safe_alias() -> None:
    with pytest.raises(RuntimeError, match="ambiguous active PIT ticker"):
        resolve_target_ticker_from_pit_rows(
            [_row("AAA", active=True), _row("BBB", active=True)],
            endpoint_session=date(2021, 10, 29),
            instrument_id="ins_test",
            authoritative_ticker="CCC",
        )


def test_multiple_inactive_safe_aliases_can_use_authoritative_interval() -> None:
    ticker, reason = resolve_target_ticker_from_pit_rows(
        [_row("OLD", active=False), _row("NEW", active=False)],
        endpoint_session=date(2021, 10, 29),
        instrument_id="ins_test",
        authoritative_ticker="NEW",
    )
    assert ticker == "NEW"
    assert reason == "AUTHORITATIVE_INTERVAL_SAFE_ALIAS"


def test_unsafe_identity_rows_are_not_used() -> None:
    ticker, reason = resolve_target_ticker_from_pit_rows(
        [_row("FALLBACK", active=True, quality="fallback")],
        endpoint_session=date(2021, 10, 29),
        instrument_id="ins_test",
        authoritative_ticker=None,
    )
    assert ticker is None
    assert reason == "NO_SAFE_PIT_ALIAS"


def test_unique_composite_figi_is_required_for_source_authority() -> None:
    rows = [
        _row("CGA", active=True, composite_figi="BBG000BTEST1"),
        _row("ENFY", active=True, composite_figi="BBG000BTEST1"),
    ]
    assert _unique_authoritative_composite_figi(
        rows,
        endpoint_session=date(2024, 11, 29),
        instrument_id="ins_test",
    ) == "BBG000BTEST1"


def test_multiple_composite_figis_fail_closed() -> None:
    rows = [
        _row("AAA", active=True, composite_figi="BBG000BTEST1"),
        _row("BBB", active=True, composite_figi="BBG000BTEST2"),
    ]
    with pytest.raises(RuntimeError, match="multiple Composite FIGIs"):
        _unique_authoritative_composite_figi(
            rows,
            endpoint_session=date(2024, 11, 29),
            instrument_id="ins_test",
        )


def test_ticker_events_resolve_latest_effective_ticker_without_prices() -> None:
    events = [
        _ticker_event("2009-02-02", "CGA"),
        _ticker_event("2024-11-26", "ENFY"),
    ]
    assert authoritative_ticker_from_massive_events(
        events,
        endpoint_session=date(2024, 11, 29),
        instrument_id="ins_test",
    ) == "ENFY"
    assert authoritative_ticker_from_massive_events(
        events,
        endpoint_session=date(2024, 11, 25),
        instrument_id="ins_test",
    ) == "CGA"


def test_ticker_event_timeline_does_not_infer_before_first_event() -> None:
    events = [_ticker_event("2024-11-26", "ENFY")]
    assert authoritative_ticker_from_massive_events(
        events,
        endpoint_session=date(2024, 11, 25),
        instrument_id="ins_test",
    ) is None


def test_same_day_ticker_event_contradiction_fails_closed() -> None:
    events = [
        _ticker_event("2024-11-26", "CGA"),
        _ticker_event("2024-11-26", "ENFY"),
    ]
    with pytest.raises(RuntimeError, match="multiple tickers on one event date"):
        authoritative_ticker_from_massive_events(
            events,
            endpoint_session=date(2024, 11, 29),
            instrument_id="ins_test",
        )
