from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.backtesting.literature_momseason_policy import LITERATURE_MOMSEASON_FORMATION_START
from packages.backtesting.literature_momseason_total_return_source import (
    ALPACA_RESEARCH_NAMESPACE,
    MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END,
    _best_action_match,
    _evenly_spaced_sample,
    extract_alpaca_bar_closes,
    normalize_alpaca_action_page,
)
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.providers.alpaca.client import AlpacaApiPage, AlpacaMarketDataClient


class _RecordingAlpacaClient(AlpacaMarketDataClient):
    def __init__(self) -> None:
        self.cfg = SimpleNamespace(
            base_url="https://data.alpaca.markets",
            symbol_batch_size=100,
            timeframe="1Day",
            adjustment="raw",
            feed="sip",
            asof="-",
            page_limit=10000,
        )
        self.calls: list[dict[str, object]] = []

    def _request_json(self, **kwargs):  # type: ignore[override]
        self.calls.append(dict(kwargs))
        return AlpacaApiPage(
            request_name=str(kwargs["request_name"]),
            url="https://example.invalid",
            http_status=200,
            raw_body=b"{}",
            payload={},
            response_headers={},
            page_token_used=kwargs.get("page_token_used"),
            next_page_token=None,
        )


class _FakeSettings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = SimpleNamespace(paths=SimpleNamespace(provider="data/provider"))

    def resolved_path(self, value: str) -> Path:
        return self.root / value


def test_historical_bar_defaults_preserve_raw_configuration() -> None:
    client = _RecordingAlpacaClient()
    list(client.historical_bar_pages(symbols=["AAPL"], start="2020-01-02", end="2020-01-03"))
    assert len(client.calls) == 1
    params = client.calls[0]["params"]
    assert isinstance(params, dict)
    assert params["adjustment"] == "raw"
    assert params["feed"] == "sip"
    assert params["asof"] == "-"
    assert params["timeframe"] == "1Day"


def test_historical_bar_research_override_does_not_mutate_config() -> None:
    client = _RecordingAlpacaClient()
    list(
        client.historical_bar_pages(
            symbols=["AAPL"],
            start="2020-01-02",
            end="2020-01-03",
            adjustment="all",
            asof="2020-01-03",
            feed="iex",
            timeframe="1Week",
        )
    )
    params = client.calls[0]["params"]
    assert isinstance(params, dict)
    assert params["adjustment"] == "all"
    assert params["feed"] == "iex"
    assert params["asof"] == "2020-01-03"
    assert params["timeframe"] == "1Week"
    assert client.cfg.adjustment == "raw"
    assert client.cfg.feed == "sip"
    assert client.cfg.asof == "-"
    assert client.cfg.timeframe == "1Day"


def test_historical_bar_rejects_unknown_adjustment_before_request() -> None:
    client = _RecordingAlpacaClient()
    with pytest.raises(ValueError, match="unsupported Alpaca historical-bar adjustment"):
        list(
            client.historical_bar_pages(
                symbols=["AAPL"],
                start="2020-01-02",
                end="2020-01-03",
                adjustment="mystery",
            )
        )
    assert client.calls == []


def test_namespaced_alpaca_raw_store_preserves_default_path(tmp_path: Path) -> None:
    settings = _FakeSettings(tmp_path)
    default = AlpacaRawPayloadStore(settings)  # type: ignore[arg-type]
    research = AlpacaRawPayloadStore(  # type: ignore[arg-type]
        settings, namespace=ALPACA_RESEARCH_NAMESPACE
    )
    assert default.root == tmp_path / "data/provider/alpaca/historical_backfill/raw"
    assert research.root == (
        tmp_path / f"data/provider/alpaca/{ALPACA_RESEARCH_NAMESPACE}/raw"
    )
    assert default.root != research.root


def test_total_return_price_audit_is_frozen_before_first_target_month() -> None:
    assert MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END == date(2021, 8, 31)
    assert MOMSEASON_TOTAL_RETURN_BAR_AUDIT_END < LITERATURE_MOMSEASON_FORMATION_START


def test_normalize_alpaca_action_page_flattens_known_collections() -> None:
    payload = {
        "corporate_actions": {
            "cash_dividends": [
                {
                    "id": "d1",
                    "symbol": "AAA",
                    "ex_date": "2020-04-15",
                    "rate": "0.25",
                }
            ],
            "forward_splits": [
                {
                    "id": "s1",
                    "symbol": "BBB",
                    "ex_date": "2020-08-31",
                    "old_rate": "1",
                    "new_rate": "4",
                }
            ],
        },
        "next_page_token": None,
    }
    rows = normalize_alpaca_action_page(payload, source_page_sha256="abc123")
    assert [row["_alpaca_action_type"] for row in rows] == [
        "cash_dividend",
        "forward_split",
    ]
    assert all(row["_source_page_sha256"] == "abc123" for row in rows)


def test_extract_alpaca_bar_closes_uses_literal_symbol_and_daily_timestamp() -> None:
    payload = {
        "bars": {
            "AAA": [
                {"t": "2020-01-02T05:00:00Z", "c": 10.0},
                {"t": "2020-01-03T05:00:00Z", "c": 10.5},
            ],
            "OTHER": [{"t": "2020-01-02T05:00:00Z", "c": 99.0}],
        }
    }
    assert extract_alpaca_bar_closes(payload, "AAA") == {
        date(2020, 1, 2): 10.0,
        date(2020, 1, 3): 10.5,
    }


def test_best_action_match_reconciles_dividend_and_split_values() -> None:
    actions = [
        {
            "_alpaca_action_type": "cash_dividend",
            "id": "div",
            "symbol": "AAA",
            "ex_date": "2020-04-15",
            "rate": "0.25",
        },
        {
            "_alpaca_action_type": "forward_split",
            "id": "split",
            "symbol": "BBB",
            "ex_date": "2020-08-31",
            "old_rate": "1",
            "new_rate": "4",
        },
    ]
    dividend = _best_action_match(
        {
            "kind": "dividend_missing_factor",
            "ticker": "AAA",
            "event_date": "2020-04-15",
            "massive_cash_amounts": [0.25],
        },
        actions,
    )
    split = _best_action_match(
        {
            "kind": "split",
            "ticker": "BBB",
            "event_date": "2020-08-31",
            "massive_split_ratio": 4.0,
        },
        actions,
    )
    assert dividend["alpaca_action_match"] is True
    assert dividend["value_relative_error"] == 0.0
    assert split["alpaca_action_match"] is True
    assert split["value_relative_error"] == 0.0


def test_evenly_spaced_sample_is_deterministic_and_spans_population() -> None:
    rows = [{"value": index} for index in range(101)]
    sample = _evenly_spaced_sample(rows, 5)
    assert [row["value"] for row in sample] == [0, 25, 50, 75, 100]
