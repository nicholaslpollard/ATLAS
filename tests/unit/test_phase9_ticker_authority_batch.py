from __future__ import annotations

import pytest

from packages.regimes.ticker_authority_batch import (
    TICKER_AUTHORITY_BATCH_CONTRACT_VERSION,
    TICKER_AUTHORITY_BATCH_DEFAULT_LIMIT,
    TICKER_AUTHORITY_BATCH_MAX_ERRORS,
    select_provider_candidates,
)


def _row(
    instrument_id: str,
    ticker: str,
    *,
    alias_count: int = 1,
    reuse_identity_count: int = 1,
    composite_figi: str = "BBG000000001",
    current_interval_count: int = 0,
) -> dict[str, object]:
    return {
        "instrument_id": instrument_id,
        "ticker": ticker,
        "alias_count": alias_count,
        "reuse_identity_count": reuse_identity_count,
        "composite_figi": composite_figi,
        "authoritative_current_interval_count": current_interval_count,
    }


def test_ticker_authority_batch_contract_defaults_are_locked() -> None:
    assert TICKER_AUTHORITY_BATCH_CONTRACT_VERSION == (
        "ticker-authority-batch-v1-composite-figi-sequential-resumable"
    )
    assert TICKER_AUTHORITY_BATCH_DEFAULT_LIMIT == 25
    assert TICKER_AUTHORITY_BATCH_MAX_ERRORS == 3


def test_select_provider_candidates_requires_unresolved_figi_and_skips_cache() -> None:
    rows = [
        _row("ins_3", "THREE", alias_count=2, composite_figi="bbg3"),
        _row("ins_1", "ONE", reuse_identity_count=2, composite_figi="bbg1"),
        _row("ins_2", "TWO", alias_count=2, composite_figi=""),
        _row("ins_4", "FOUR", alias_count=2, composite_figi="bbg4", current_interval_count=1),
        _row("ins_5", "FIVE"),
    ]
    selected = select_provider_candidates(
        rows,
        cached_instrument_ids={"ins_3"},
        limit=25,
    )
    assert [(item.instrument_id, item.ticker, item.composite_figi) for item in selected] == [
        ("ins_1", "ONE", "BBG1")
    ]


def test_select_provider_candidates_is_deterministic_limited_and_validates_limit() -> None:
    rows = [
        _row("ins_c", "CCC", alias_count=2, composite_figi="bbgc"),
        _row("ins_a", "AAA", reuse_identity_count=2, composite_figi="bbga"),
        _row("ins_b", "BBB", alias_count=2, composite_figi="bbgb"),
    ]
    selected = select_provider_candidates(rows, cached_instrument_ids=set(), limit=2)
    assert [item.instrument_id for item in selected] == ["ins_a", "ins_b"]
    assert [item.composite_figi for item in selected] == ["BBGA", "BBGB"]
    with pytest.raises(ValueError, match="limit must be positive"):
        select_provider_candidates(rows, cached_instrument_ids=set(), limit=0)
