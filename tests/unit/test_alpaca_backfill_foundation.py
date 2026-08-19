from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from packages.core.enums import DataProvider
from packages.core.settings import load_settings
from packages.data.alpaca_backfill_inventory import (
    _asset_records,
    _bar_counts,
    _corporate_action_symbols,
    _cusip_like_identifier_shape,
    _deterministic_sample,
    _is_inactive_reference_only_identifier,
)
from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_CANONICAL_WRITE_ENABLED,
    ALPACA_BACKFILL_GATES,
    ALPACA_BACKFILL_REQUESTS_PER_MINUTE,
    ALPACA_BACKFILL_START,
    ALPACA_MASSIVE_SEAM_START,
    validate_backfill_contract,
)
from packages.data.alpaca_backfill_storage import (
    ALPACA_RAW_PROVENANCE_KEY_HEX_LENGTH,
    ALPACA_RAW_STORAGE_LAYOUT_VERSION,
    AlpacaRawPayloadStore,
)
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
    assert cfg.requests_per_minute == ALPACA_BACKFILL_REQUESTS_PER_MINUTE == 180
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


def test_inactive_only_cusip_like_identifier_is_reference_only_without_ticker_corroboration() -> None:
    assert _cusip_like_identifier_shape("0029900E0") is True
    assert _cusip_like_identifier_shape("AAPL") is False
    base = {
        "from_active_assets": False,
        "from_inactive_assets": True,
        "from_massive_observed": False,
        "from_corporate_actions": False,
    }
    assert _is_inactive_reference_only_identifier(base, "0029900E0") is True
    assert _is_inactive_reference_only_identifier({**base, "from_massive_observed": True}, "0029900E0") is False
    assert _is_inactive_reference_only_identifier({**base, "from_corporate_actions": True}, "0029900E0") is False
    assert _is_inactive_reference_only_identifier(base, "LNKD") is False


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
    payload_path = Path(first.payload_path)
    assert first.sha256 == second.sha256
    assert first.payload_path == second.payload_path
    assert ALPACA_RAW_STORAGE_LAYOUT_VERSION == "alpaca-raw-store-v2-hashed-provenance-directory"
    assert payload_path.parent.parent.name == "v2"
    assert len(payload_path.parent.name) == ALPACA_RAW_PROVENANCE_KEY_HEX_LENGTH == 20
    assert payload_path.name == f"{first.sha256}.json.gz"
    assert gzip.decompress(payload_path.read_bytes()) == body


def test_raw_payload_store_bounds_final_path_under_long_provenance(tmp_path) -> None:
    settings = load_settings().model_copy(update={"project_root": tmp_path})
    store = AlpacaRawPayloadStore(settings)
    body = b'{"message":"invalid symbol: 0029900E0"}'
    page = AlpacaApiPage(
        request_name="historical_bars",
        url="https://data.alpaca.markets/v2/stocks/bars?symbols=0029900E0",
        http_status=400,
        raw_body=body,
        payload={"message": "invalid symbol: 0029900E0"},
        response_headers={},
    )
    record = store.persist(
        page,
        category="bars_rejections",
        partition="2016_batch_0000_reject_0000",
    )
    payload_path = Path(record.payload_path)
    assert payload_path.is_file()
    assert Path(record.metadata_path).is_file()
    assert len(payload_path.parent.name) == 20
    assert record.category == "bars_rejections"
    assert record.partition == "2016_batch_0000_reject_0000"
    assert gzip.decompress(payload_path.read_bytes()) == body


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
