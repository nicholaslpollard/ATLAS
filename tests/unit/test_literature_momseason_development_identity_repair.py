from __future__ import annotations

from datetime import date

import pytest

from packages.backtesting.literature_momseason_development_identity_repair import (
    LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION,
    resolve_target_ticker_from_pit_rows,
)


def _row(ticker: str, *, active: bool, quality: str = "strong") -> dict[str, object]:
    return {
        "ticker": ticker,
        "active": active,
        "identity_quality": quality,
    }


def test_identity_repair_version_is_explicit() -> None:
    assert LIT01_DEVELOPMENT_IDENTITY_REPAIR_VERSION.startswith(
        "lit01-development-target-identity-v2"
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
