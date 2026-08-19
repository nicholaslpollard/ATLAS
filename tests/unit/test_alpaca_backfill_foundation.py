from __future__ import annotations

import gzip

import pytest

from packages.core.enums import DataProvider
from packages.core.settings import load_settings
from packages.data.alpaca_backfill_inventory import (
    _asset_records,
    _bar_counts,
    _corporate_action_symbols,
    _deterministic_sample,
)
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED,
    ALPACA_BACKFILL_GATES,
    ALPACA_BACKFILL_START,
    ALPACA_MASSIVE_SEAM_START,
    validate_backfill_contract,
)
from packages.data.alpaca_backfill_storage import AlpacaRawPayloadStore
from packages.providers.alpaca import AlpacaApiPage, AlpacaMarketDataClient


def test_alpaca_is_a_first_class_data_provider() -> None:
    assert DataProvider.ALPACA.value == "alpaca"


def test_backfill_contract_locks_twelve_ordered_gates() -> None:
    validate_backfill_contract()
    assert [gate.number for gate in ALPACA_BACKFILL_GATES] == list(range(1, 13))
    assert ALPACA_BACKFILL_START < ALPACA_MASSIVE_SEAM_START
    assert ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED is False


def test_settings_lock_raw_literal_sip_daily_semantics() -> None:
    settings = load_settings()
    cfg = settings.alpaca.market_data
    assert cfg.feed == "sip"
    assert cfg.adjustment == "raw"
    assert cfg.asof == "-"
    assert cfg.timeframe == "1Day"
    assert cfg.page_limit == 10_000
    assert cfg.backfill_start == "2016-01-04"
    assert cfg.backfill_end == "2021-08-15"


def test_asset_records_preserve_provider_symbol_case() -> None:
    rows = _asset_records(
        [
            {"symbol": "BrK.B", "exchange": "nyse", "id": "id1", "name": "Example", "status": "active"},
            {"symbol": " BAD SYMBOL ", "exchange": "NYSE"},
        ]
    )
    assert rows == [
        {
            "symbol": "BrK.B",
            "exchange": "NYSE",
            "asset_id": "id1",
            "name": "Example",
            "status": "active",
        }
    ]


def test_corporate_action_symbol_extraction_keeps_old_and_new_symbols_separate() -> None:
    payload = {
        "corporate_actions": {
            "name_changes": [
                {"old_symbol": "FB", "new_symbol": "META", "symbol": "FB"},
                {"symbol": "S"},
            ]
        }
    }
    assert _corporate_action_symbols(payload) == {"FB", "META", "S"}


def test_multi_symbol_bar_counts_are_observation_driven() -> None:
    payload = {
        "bars": {
            "AAPL": [{"t": "2016-01-04"}, {"t": "2016-01-05"}],
            "LNKD": [{"t": "2016-01-04"}],
        },
        "next_page_token": None,
    }
    assert _bar_counts(payload) == {"AAPL": 2, "LNKD": 1}


def test_deterministic_sample_is_case_sensitive_and_repeatable() -> None:
    symbols = ["AAPL", "aapl", "MSFT", "S", "FB", "META"]
    first = _deterministic_sample(symbols, 4)
    second = _deterministic_sample(reversed(symbols), 4)
    assert first == second
    assert len(first) == 4
    assert len(set(first)) == 4


def test_raw_payload_store_is_content_addressed_and_idempotent(tmp_path) -> None:
    settings = load_settings().model_copy(update={"project_root": tmp_path})
    store = AlpacaRawPayloadStore(settings)
    body = b'{"bars":{"AAPL":[{"t":"2016-01-04"}]}}'
    page = AlpacaApiPage(
        request_name="historical_bars",
        url="https://data.alpaca.markets/v2/stocks/bars?symbols=AAPL",
        http_status=200,
        raw_body=body,
        payload={"bars": {"AAPL": [{"t": "2016-01-04"}]}},
        response_headers={},
    )
    first = store.persist(page, category="test", partition="2016")
    second = store.persist(page, category="test", partition="2016")
    assert first.sha256 == second.sha256
    assert first.payload_path == second.payload_path
    assert gzip.decompress((tmp_path / "data" / "provider" / "alpaca" / "historical_backfill" / "raw" / "test" / "2016" / f"{first.sha256}.json.gz").read_bytes()) == body


def test_client_resolves_existing_paper_environment_without_echoing_secret(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET", "test-secret")
    monkeypatch.setenv("ALPACA_PAPER_ENDPOINT", "https://paper-api.alpaca.markets/v2")
    client = AlpacaMarketDataClient(load_settings(), sleeper=lambda _: None)
    assert client.credential_profile_name == "paper"
    assert "test-secret" not in repr(client.profile)
    headers = client._headers()
    assert headers["APCA-API-KEY-ID"] == "test-key"
    assert headers["APCA-API-SECRET-KEY"] == "test-secret"
