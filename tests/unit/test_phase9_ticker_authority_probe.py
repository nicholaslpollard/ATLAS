from __future__ import annotations

from packages.regimes.ticker_authority_probe import (
    AMBIGUOUS_AUTHORITATIVE_INTERVAL,
    NEEDS_COMPOSITE_FIGI_EVENT,
    NOT_REQUIRED,
    RESOLVED_AUTHORITATIVE_INTERVAL,
    TICKER_AUTHORITY_PROBE_CONTRACT_VERSION,
    UNRESOLVED_NO_COMPOSITE_FIGI,
    authority_status,
)


def test_ticker_authority_contract() -> None:
    assert TICKER_AUTHORITY_PROBE_CONTRACT_VERSION == (
        "ticker-authority-probe-v1-unresolved-composite-figi-cache-audit"
    )


def test_authority_status_accepts_one_exact_current_interval() -> None:
    assert authority_status(
        alias_count=3,
        reuse_identity_count=2,
        authoritative_current_interval_count=1,
        has_composite_figi=True,
    ) == RESOLVED_AUTHORITATIVE_INTERVAL


def test_authority_status_blocks_ambiguous_current_intervals() -> None:
    assert authority_status(
        alias_count=2,
        reuse_identity_count=1,
        authoritative_current_interval_count=2,
        has_composite_figi=True,
    ) == AMBIGUOUS_AUTHORITATIVE_INTERVAL


def test_authority_status_routes_unresolved_identity_to_composite_figi_event() -> None:
    assert authority_status(
        alias_count=2,
        reuse_identity_count=1,
        authoritative_current_interval_count=0,
        has_composite_figi=True,
    ) == NEEDS_COMPOSITE_FIGI_EVENT
    assert authority_status(
        alias_count=1,
        reuse_identity_count=3,
        authoritative_current_interval_count=0,
        has_composite_figi=True,
    ) == NEEDS_COMPOSITE_FIGI_EVENT


def test_authority_status_distinguishes_no_figi_from_simple_identity() -> None:
    assert authority_status(
        alias_count=2,
        reuse_identity_count=1,
        authoritative_current_interval_count=0,
        has_composite_figi=False,
    ) == UNRESOLVED_NO_COMPOSITE_FIGI
    assert authority_status(
        alias_count=1,
        reuse_identity_count=1,
        authoritative_current_interval_count=0,
        has_composite_figi=False,
    ) == NOT_REQUIRED
