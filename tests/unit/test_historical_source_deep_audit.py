from __future__ import annotations

from packages.data.alpaca_history_audit import (
    ALPACA_DEPTH_SYMBOLS,
    ALPACA_HISTORY_AUDIT_CONTRACT_VERSION,
    ALPACA_OVERLAP_SYMBOLS,
    ALPACA_SPLIT_WINDOWS,
    _largest_adjacent_close_ratio,
    _relative_difference,
)
from packages.data.historical_source_probe import alpaca_bar_url
from packages.data.stooq_bulk_audit import (
    STOOQ_BULK_AUDIT_CONTRACT_VERSION,
    STOOQ_BULK_CANDIDATE_URLS,
    _find_symbol_member,
    _parse_stooq_txt,
)


def test_alpaca_deep_audit_contract_is_read_only_compatible() -> None:
    assert ALPACA_HISTORY_AUDIT_CONTRACT_VERSION == (
        "historical-source-audit-v2-alpaca-sip-raw-depth-massive-overlap"
    )
    assert ALPACA_DEPTH_SYMBOLS == ("AAPL", "SPY", "IBM")
    assert "TWTR" in ALPACA_OVERLAP_SYMBOLS
    assert "FB" in ALPACA_OVERLAP_SYMBOLS
    assert {item[0] for item in ALPACA_SPLIT_WINDOWS} == {"AMZN", "GOOG", "TSLA", "NVDA"}


def test_alpaca_audit_url_preserves_raw_literal_sip_semantics() -> None:
    url = alpaca_bar_url(
        "FB",
        start="2021-08-16",
        end="2021-09-10",
        feed="sip",
        adjustment="raw",
        asof="-",
    )
    assert "feed=sip" in url
    assert "adjustment=raw" in url
    assert "asof=-" in url


def test_relative_difference_is_symmetric() -> None:
    assert _relative_difference(100.0, 101.0) == _relative_difference(101.0, 100.0)
    assert 0.0 < _relative_difference(100.0, 101.0) < 0.02


def test_largest_adjacent_close_ratio_detects_split_like_jump() -> None:
    rows = {
        "2024-06-07": {"c": 1200.0},
        "2024-06-10": {"c": 120.0},
        "2024-06-11": {"c": 121.0},
    }
    result = _largest_adjacent_close_ratio(rows, "c")
    assert result is not None
    assert result["from"] == "2024-06-07"
    assert result["to"] == "2024-06-10"
    assert result["max_ratio"] == 10.0


def test_stooq_bulk_contract_and_candidate_urls_are_locked() -> None:
    assert STOOQ_BULK_AUDIT_CONTRACT_VERSION == (
        "historical-source-audit-v2-stooq-bulk-preflight-zip-inspection"
    )
    assert len(STOOQ_BULK_CANDIDATE_URLS) == 3
    assert all(url.endswith("d_us_txt.zip") for url in STOOQ_BULK_CANDIDATE_URLS)


def test_stooq_txt_parser_accepts_archive_format() -> None:
    raw = (
        b"<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n"
        b"AAPL.US,D,20100104,000000,7.62,7.66,7.58,7.64,493729600,0\n"
    )
    rows = _parse_stooq_txt(raw)
    assert len(rows) == 1
    assert rows[0]["<TICKER>"] == "AAPL.US"
    assert rows[0]["<DATE>"] == "20100104"


def test_stooq_member_lookup_handles_nested_and_backslash_paths() -> None:
    names = ["data\\nasdaq stocks\\1\\aapl.us.txt", "data/nyse etfs/spy.us.txt"]
    assert _find_symbol_member(names, "aapl.us") == names[0]
    assert _find_symbol_member(names, "spy.us") == names[1]
