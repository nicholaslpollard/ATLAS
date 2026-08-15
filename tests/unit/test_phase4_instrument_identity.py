from datetime import date

from packages.core.enums import InstrumentIdentityQuality
from packages.instruments.identity import InstrumentIdentityResolver


def test_composite_figi_survives_ticker_change():
    resolver = InstrumentIdentityResolver()
    old = resolver.resolve({"ticker": "OLD", "composite_figi": "BBG000ABC123"}, date(2024, 1, 2))
    new = resolver.resolve({"ticker": "NEW", "composite_figi": "BBG000ABC123"}, date(2026, 1, 2))
    assert old[0] == new[0]
    assert old[1] == new[1]
    assert old[2] == InstrumentIdentityQuality.STRONG


def test_cik_exchange_type_is_medium_fallback():
    resolver = InstrumentIdentityResolver()
    _, key, quality = resolver.resolve(
        {"ticker": "XYZ", "cik": "000123", "primary_exchange": "XNAS", "type": "CS"},
        date(2026, 8, 14),
    )
    assert "cik:000123" in key
    assert quality == InstrumentIdentityQuality.MEDIUM


def test_ticker_only_identity_is_snapshot_scoped():
    resolver = InstrumentIdentityResolver()
    first = resolver.resolve({"ticker": "XYZ"}, date(2026, 8, 14))
    second = resolver.resolve({"ticker": "XYZ"}, date(2026, 8, 15))
    assert first[0] != second[0]
    assert first[2] == InstrumentIdentityQuality.FALLBACK
