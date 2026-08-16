from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.core.settings import load_settings
from packages.providers.massive.reference_data import MassiveReferenceProvider

ROOT = Path(__file__).resolve().parents[2]


class FakeReferenceClient:
    def list_tickers(self, *, as_of_date: str, active: bool, market: str):
        assert as_of_date == "2026-08-14"
        assert market == "stocks"
        if not active:
            return []
        return [
            {
                "ticker": "BCPC",
                "name": "Balchem Corporation",
                "market": "stocks",
                "type": "CS",
                "active": True,
                "composite_figi": "bbg000bcy878",
            },
            {
                "ticker": "BCpC",
                "name": "Brunswick Corporation 6.375% Notes due 2049",
                "market": "stocks",
                "type": "PFD",
                "active": True,
                "cik": "00014930",
                "primary_exchange": "xnys",
            },
            {
                "ticker": "TPC",
                "name": "Tutor Perini Corporation",
                "market": "stocks",
                "type": "CS",
                "active": True,
                "composite_figi": "bbg000bqxhV1",
            },
            {
                "ticker": "TpC",
                "name": "AT&T Inc. Series C Preferred",
                "market": "stocks",
                "type": "PFD",
                "active": True,
                "cik": "0000732717",
                "primary_exchange": "xnys",
            },
        ]

    def ticker_events(self, identifier: str):
        return []


def test_reference_provider_preserves_provider_native_ticker_case():
    settings = load_settings(ROOT, "development")
    provider = MassiveReferenceProvider(settings, client=FakeReferenceClient())
    rows = provider.stock_snapshot(date(2026, 8, 14), include_inactive=False)

    tickers = [row["ticker"] for row in rows]
    assert "BCPC" in tickers
    assert "BCpC" in tickers
    assert "TPC" in tickers
    assert "TpC" in tickers
    assert len(tickers) == 4

    preferred = next(row for row in rows if row["ticker"] == "BCpC")
    assert preferred["primary_exchange"] == "XNYS"
    assert preferred["type"] == "PFD"
