from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_acquisition import (
    AcquisitionUnit,
    AlpacaBackfillAcquirer,
    _bar_stats,
    _chunks,
    _inventory_fingerprint,
    _year_windows,
)
from packages.data.alpaca_backfill_inventory import ALPACA_BACKFILL_INVENTORY_CONTRACT_VERSION
from packages.providers.alpaca import AlpacaApiPage, AlpacaInvalidSymbolError, AlpacaMarketDataClient
from packages.providers.alpaca.client import _invalid_symbol_from_message


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


def test_invalid_symbol_message_parser_is_exact_and_literal() -> None:
    assert _invalid_symbol_from_message("invalid symbol: 0029900E0") == "0029900E0"
    assert _invalid_symbol_from_message("INVALID SYMBOL: BrK.B") == "BrK.B"
    assert _invalid_symbol_from_message("bad request") is None
    assert _invalid_symbol_from_message("invalid symbol: BAD SYMBOL") is None


def test_gate3_isolates_provider_rejected_symbol_and_reuses_evidence(tmp_path, monkeypatch) -> None:
    _configure_alpaca(monkeypatch)
    settings = load_settings().model_copy(update={"project_root": tmp_path})
    acquirer = AlpacaBackfillAcquirer(settings)
    calls: list[tuple[str, ...]] = []

    class FakeClient:
        credential_profile_name = "paper"

        def historical_bar_pages(self, *, symbols, start, end):
            submitted = tuple(symbols)
            calls.append(submitted)
            if "0029900E0" in submitted:
                body = b'{"message":"invalid symbol: 0029900E0"}'
                page = AlpacaApiPage(
                    request_name="historical_bars",
                    url="https://data.alpaca.markets/v2/stocks/bars?symbols=AAPL%2C0029900E0%2CMSFT",
                    http_status=400,
                    raw_body=body,
                    payload={"message": "invalid symbol: 0029900E0"},
                    response_headers={},
                )
                raise AlpacaInvalidSymbolError(
                    "0029900E0", page, "invalid symbol: 0029900E0"
                )
            yield AlpacaApiPage(
                request_name="historical_bars",
                url="https://data.alpaca.markets/v2/stocks/bars?symbols=AAPL%2CMSFT",
                http_status=200,
                raw_body=b'{"bars":{"AAPL":[{"t":"2016-01-04T05:00:00Z"}]},"next_page_token":null}',
                payload={
                    "bars": {"AAPL": [{"t": "2016-01-04T05:00:00Z"}]},
                    "next_page_token": None,
                },
                response_headers={},
            )

    acquirer.client = FakeClient()
    known: dict[str, dict[str, object]] = {}
    first = AcquisitionUnit(
        year=2016,
        batch_index=0,
        start="2016-01-04",
        end="2016-12-31",
        symbols=("AAPL", "0029900E0", "MSFT"),
        inventory_fingerprint="f" * 64,
        unit_id="1" * 64,
    )
    manifest = acquirer._acquire_unit(first, known)
    assert calls == [("AAPL", "0029900E0", "MSFT"), ("AAPL", "MSFT")]
    assert manifest["provider_rejected_symbol_count"] == 1
    assert manifest["submitted_symbol_count"] == 2
    assert manifest["provider_rejections"][0]["symbol"] == "0029900E0"
    assert manifest["observed_symbol_count"] == 1
    assert "0029900E0" in known
    assert Path(manifest["provider_rejections"][0]["payload_path"]).is_file()
    assert Path(manifest["provider_rejections"][0]["metadata_path"]).is_file()

    calls.clear()
    second = AcquisitionUnit(
        year=2017,
        batch_index=0,
        start="2017-01-01",
        end="2017-12-31",
        symbols=("AAPL", "0029900E0", "MSFT"),
        inventory_fingerprint="f" * 64,
        unit_id="2" * 64,
    )
    manifest2 = acquirer._acquire_unit(second, known)
    assert calls == [("AAPL", "MSFT")]
    assert manifest2["provider_rejected_symbol_count"] == 1
    assert manifest2["provider_rejections"][0]["sha256"] == manifest["provider_rejections"][0]["sha256"]


def test_gate3_quarantines_nonexact_response_symbols_without_double_credit(
    tmp_path, monkeypatch
) -> None:
    _configure_alpaca(monkeypatch)
    settings = load_settings().model_copy(update={"project_root": tmp_path})
    acquirer = AlpacaBackfillAcquirer(settings)

    collision = AcquisitionUnit(
        year=2016,
        batch_index=0,
        start="2016-01-04",
        end="2016-12-31",
        symbols=("BCpC",),
        inventory_fingerprint="f" * 64,
        unit_id="1" * 64,
    )
    exact_upper = AcquisitionUnit(
        year=2016,
        batch_index=1,
        start="2016-01-04",
        end="2016-12-31",
        symbols=("BCPC",),
        inventory_fingerprint="f" * 64,
        unit_id="2" * 64,
    )
    casefold_only = AcquisitionUnit(
        year=2016,
        batch_index=2,
        start="2016-01-04",
        end="2016-12-31",
        symbols=("CpN",),
        inventory_fingerprint="f" * 64,
        unit_id="3" * 64,
    )
    unrelated = AcquisitionUnit(
        year=2016,
        batch_index=3,
        start="2016-01-04",
        end="2016-12-31",
        symbols=("AAPL",),
        inventory_fingerprint="f" * 64,
        unit_id="4" * 64,
    )

    manifests = {
        collision.unit_id: {
            "provider_rejections": [],
            "raw_pages": [{"sha256": "a" * 64}],
            "symbol_stats": {
                "BCPC": {
                    "bar_rows": 2,
                    "first_timestamp": "2016-01-04T05:00:00Z",
                    "last_timestamp": "2016-01-05T05:00:00Z",
                }
            },
        },
        exact_upper.unit_id: {
            "provider_rejections": [],
            "raw_pages": [{"sha256": "b" * 64}],
            "symbol_stats": {
                "BCPC": {
                    "bar_rows": 2,
                    "first_timestamp": "2016-01-04T05:00:00Z",
                    "last_timestamp": "2016-01-05T05:00:00Z",
                }
            },
        },
        casefold_only.unit_id: {
            "provider_rejections": [],
            "raw_pages": [{"sha256": "c" * 64}],
            "symbol_stats": {
                "CPN": {
                    "bar_rows": 1,
                    "first_timestamp": "2016-01-04T05:00:00Z",
                    "last_timestamp": "2016-01-04T05:00:00Z",
                }
            },
        },
        unrelated.unit_id: {
            "provider_rejections": [],
            "raw_pages": [{"sha256": "d" * 64}],
            "symbol_stats": {
                "ZZZ": {
                    "bar_rows": 1,
                    "first_timestamp": "2016-01-04T05:00:00Z",
                    "last_timestamp": "2016-01-04T05:00:00Z",
                }
            },
        },
    }

    acquirer._load_completed_manifest = lambda unit: manifests[unit.unit_id]  # type: ignore[method-assign]

    result = acquirer._persist_observed_summary(
        ["AAPL", "BCPC", "BCpC", "CpN"],
        [collision, exact_upper, casefold_only, unrelated],
    )
    assert result == (1, 2, 0, 0, 3, 4, 1, 1, 1)

    con = duckdb.connect(":memory:")
    try:
        observed_rows = con.execute(
            "SELECT symbol, bar_rows, observed, zero_bar FROM read_parquet(?) ORDER BY symbol",
            [str(acquirer.observed_summary_path)],
        ).fetchall()
        anomaly_rows = con.execute(
            "SELECT classification, requested_symbol, returned_symbol, bar_rows "
            "FROM read_parquet(?) ORDER BY batch_index",
            [str(acquirer.response_symbol_anomalies_path)],
        ).fetchall()
    finally:
        con.close()

    assert observed_rows == [
        ("AAPL", 0, False, True),
        ("BCPC", 2, True, False),
        ("BCpC", 0, False, True),
        ("CpN", 0, False, True),
    ]
    assert anomaly_rows == [
        ("CASE_FOLD_IDENTITY_COLLISION", "BCpC", "BCPC", 2),
        ("CASE_FOLD_RESPONSE", "CpN", "CPN", 1),
        ("UNREQUESTED_RESPONSE_SYMBOL", None, "ZZZ", 1),
    ]
