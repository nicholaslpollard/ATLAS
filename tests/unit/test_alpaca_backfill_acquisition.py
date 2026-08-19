from __future__ import annotations

import json
from datetime import date

import duckdb
import pandas as pd
import pytest

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_acquisition import (
    AlpacaBackfillAcquirer,
    _bar_stats,
    _chunks,
    _inventory_fingerprint,
    _year_windows,
)
from packages.data.alpaca_backfill_inventory import ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION
from packages.providers.alpaca import AlpacaMarketDataClient


def _configure_alpaca(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET", "test-secret")
    monkeypatch.setenv("ALPACA_PAPER_ENDPOINT", "https://paper-api.alpaca.markets/v2")


def test_gate3_year_windows_cover_locked_range_without_overlap() -> None:
    windows = _year_windows(date(2016, 1, 4), date(2021, 8, 15))
    assert windows == [
        (2016, date(2016, 1, 4), date(2016, 12, 31)),
        (2017, date(2017, 1, 1), date(2017, 12, 31)),
        (2018, date(2018, 1, 1), date(2018, 12, 31)),
        (2019, date(2019, 1, 1), date(2019, 12, 31)),
        (2020, date(2020, 1, 1), date(2020, 12, 31)),
        (2021, date(2021, 1, 1), date(2021, 8, 15)),
    ]


def test_gate3_chunks_are_deterministic_and_bounded() -> None:
    symbols = [f"S{i:03d}" for i in range(205)]
    batches = list(_chunks(symbols, 100))
    assert [len(batch) for batch in batches] == [100, 100, 5]
    assert list(batches[0]) == symbols[:100]
    assert list(batches[-1]) == symbols[200:]


def test_gate3_inventory_fingerprint_is_order_and_case_sensitive() -> None:
    assert _inventory_fingerprint(["AAPL", "MSFT"]) == _inventory_fingerprint(["AAPL", "MSFT"])
    assert _inventory_fingerprint(["AAPL", "MSFT"]) != _inventory_fingerprint(["MSFT", "AAPL"])
    assert _inventory_fingerprint(["AAPL"]) != _inventory_fingerprint(["aapl"])


def test_gate3_bar_stats_preserve_literal_symbol_and_timestamp_bounds() -> None:
    payload = {
        "bars": {
            "BrK.B": [
                {"t": "2016-01-05T05:00:00Z"},
                {"t": "2016-01-04T05:00:00Z"},
            ],
            "S": [{"t": "2016-01-06T05:00:00Z"}],
        }
    }
    assert _bar_stats(payload) == {
        "BrK.B": {
            "bar_rows": 2,
            "first_timestamp": "2016-01-04T05:00:00Z",
            "last_timestamp": "2016-01-05T05:00:00Z",
        },
        "S": {
            "bar_rows": 1,
            "first_timestamp": "2016-01-06T05:00:00Z",
            "last_timestamp": "2016-01-06T05:00:00Z",
        },
    }


def test_gate3_plan_is_100_symbol_batches_crossed_with_six_years(tmp_path, monkeypatch) -> None:
    _configure_alpaca(monkeypatch)
    settings = load_settings().model_copy(update={"project_root": tmp_path})
    root = tmp_path / "data" / "derived" / "historical_backfill" / "alpaca" / "inventory"
    root.mkdir(parents=True, exist_ok=True)
    symbols = [f"SYM{i:03d}" for i in range(201)]
    frame = pd.DataFrame({"symbol": symbols, "sip_acquisition_candidate": [True] * len(symbols)})
    con = duckdb.connect(":memory:")
    try:
        con.register("inventory", frame)
        con.execute(
            "COPY inventory TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(root / "candidate_symbols.parquet")],
        )
    finally:
        con.close()
    (root / "inventory_report.json").write_text(
        json.dumps(
            {
                "contract_version": ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION,
                "sip_candidate_symbols": len(symbols),
            }
        ),
        encoding="utf-8",
    )

    acquirer = AlpacaBackfillAcquirer(settings)
    planned_symbols, fingerprint, units = acquirer.build_plan()
    assert planned_symbols == sorted(symbols)
    assert len(fingerprint) == 64
    assert len(units) == 18
    assert units[0].year == 2016 and units[0].start == "2016-01-04" and len(units[0].symbols) == 100
    assert units[-1].year == 2021 and units[-1].end == "2021-08-15" and len(units[-1].symbols) == 1
    assert len({unit.unit_id for unit in units}) == len(units)
    assert all(len(unit.unit_id) == 64 for unit in units)


def test_alpaca_client_paces_requests_at_locked_180_per_minute(monkeypatch) -> None:
    _configure_alpaca(monkeypatch)
    now = [100.0]
    sleeps: list[float] = []

    def clock() -> float:
        return now[0]

    def sleeper(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    client = AlpacaMarketDataClient(load_settings(), sleeper=sleeper, clock=clock)
    assert client.cfg.requests_per_minute == 180
    client._pace_request()
    now[0] += 0.1
    client._pace_request()
    assert sleeps == [pytest.approx((60.0 / 180.0) - 0.1)]
