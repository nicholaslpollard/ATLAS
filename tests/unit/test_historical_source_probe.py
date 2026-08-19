from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from packages.data.historical_source_probe import (
    ALPACA_CREDENTIAL_PROFILES,
    ALPACA_MARKET_DATA_BASE_URL,
    HISTORICAL_SOURCE_AUDIT_CONTRACT_VERSION,
    STOOQ_DAILY_CSV_URL,
    alpaca_bar_url,
    parse_stooq_csv,
    stooq_daily_url,
)


def test_historical_source_audit_contract_and_credential_env_names_are_locked() -> None:
    assert HISTORICAL_SOURCE_AUDIT_CONTRACT_VERSION == (
        "historical-source-audit-v1-alpaca-marketdata-stooq-csv-access"
    )
    assert ALPACA_CREDENTIAL_PROFILES == {
        "paper": ("ALPACA_PAPER_API_KEY", "ALPACA_PAPER_API_SECRET"),
        "live": ("ALPACA_LIVE_API_KEY", "ALPACA_LIVE_API_SECRET"),
    }


def test_alpaca_bar_url_uses_market_data_raw_literal_symbol_contract() -> None:
    url = alpaca_bar_url(
        "AAPL",
        start="2016-01-04",
        end="2016-01-15",
        feed="sip",
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}" == ALPACA_MARKET_DATA_BASE_URL
    assert parsed.path == "/v2/stocks/AAPL/bars"
    assert query["timeframe"] == ["1Day"]
    assert query["feed"] == ["sip"]
    assert query["adjustment"] == ["raw"]
    assert query["asof"] == ["-"]
    assert query["sort"] == ["asc"]


def test_stooq_daily_url_normalizes_symbol_and_dates() -> None:
    url = stooq_daily_url("AAPL.US", start="2010-01-04", end="2010-01-15")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == STOOQ_DAILY_CSV_URL
    assert query == {
        "s": ["aapl.us"],
        "d1": ["20100104"],
        "d2": ["20100115"],
        "i": ["d"],
    }


def test_parse_stooq_csv_accepts_expected_daily_schema() -> None:
    rows = parse_stooq_csv(
        "Date,Open,High,Low,Close,Volume\n"
        "2010-01-04,7.62,7.66,7.58,7.64,493729600\n"
        "2010-01-05,7.66,7.70,7.62,7.66,601904800\n"
    )
    assert len(rows) == 2
    assert rows[0]["Date"] == "2010-01-04"
    assert rows[1]["Close"] == "7.66"


def test_parse_stooq_csv_rejects_non_csv_or_incomplete_schema() -> None:
    assert parse_stooq_csv("Get your API key") == []
    assert parse_stooq_csv("Date,Close\n2010-01-04,7.64\n") == []
