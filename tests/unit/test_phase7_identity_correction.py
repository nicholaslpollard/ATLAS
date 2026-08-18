from datetime import date

from packages.core.enums import InstrumentIdentityQuality
from packages.instruments.identity import InstrumentIdentityResolver


def test_medium_identity_does_not_collapse_distinct_tickers_from_same_issuer():
    resolver = InstrumentIdentityResolver()
    base = {
        "cik": "0000070858",
        "primary_exchange": "XNYS",
        "type": "PFD",
    }
    first_id, _, first_quality = resolver.resolve({**base, "ticker": "BACpA"}, date(2026, 8, 14))
    second_id, _, second_quality = resolver.resolve({**base, "ticker": "BACpB"}, date(2026, 8, 14))

    assert first_quality == InstrumentIdentityQuality.MEDIUM
    assert second_quality == InstrumentIdentityQuality.MEDIUM
    assert first_id != second_id


def test_medium_identity_is_stable_for_same_exact_provider_ticker_across_snapshots():
    resolver = InstrumentIdentityResolver()
    row = {
        "ticker": "TpC",
        "cik": "0000000001",
        "primary_exchange": "XNYS",
        "type": "PFD",
    }
    first_id, _, _ = resolver.resolve(row, date(2026, 1, 2))
    second_id, _, _ = resolver.resolve(row, date(2026, 8, 14))
    assert first_id == second_id


def test_strong_figi_identity_still_survives_ticker_change():
    resolver = InstrumentIdentityResolver()
    old_id, _, old_quality = resolver.resolve(
        {"ticker": "FB", "composite_figi": "BBG000MM2P62"},
        date(2021, 8, 16),
    )
    new_id, _, new_quality = resolver.resolve(
        {"ticker": "META", "composite_figi": "BBG000MM2P62"},
        date(2026, 8, 14),
    )
    assert old_quality == InstrumentIdentityQuality.STRONG
    assert new_quality == InstrumentIdentityQuality.STRONG
    assert old_id == new_id


def test_fallback_identity_remains_point_in_time_conservative():
    resolver = InstrumentIdentityResolver()
    row = {"ticker": "XYZ"}
    first_id, _, first_quality = resolver.resolve(row, date(2026, 1, 2))
    second_id, _, second_quality = resolver.resolve(row, date(2026, 8, 14))

    assert first_quality == InstrumentIdentityQuality.FALLBACK
    assert second_quality == InstrumentIdentityQuality.FALLBACK
    assert first_id != second_id
