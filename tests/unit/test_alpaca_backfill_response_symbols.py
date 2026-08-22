from __future__ import annotations

import duckdb

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_acquisition import AcquisitionUnit, AlpacaBackfillAcquirer


def _configure_alpaca(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_PAPER_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_PAPER_API_SECRET", "test-secret")
    monkeypatch.setenv("ALPACA_PAPER_ENDPOINT", "https://paper-api.alpaca.markets/v2")


def test_gate3_quarantines_same_batch_casefold_collision(tmp_path, monkeypatch) -> None:
    _configure_alpaca(monkeypatch)
    settings = load_settings().model_copy(update={"project_root": tmp_path})
    acquirer = AlpacaBackfillAcquirer(settings)
    unit = AcquisitionUnit(
        year=2016,
        batch_index=0,
        start="2016-01-04",
        end="2016-12-31",
        symbols=("BCPC", "BCpC"),
        inventory_fingerprint="f" * 64,
        unit_id="1" * 64,
    )
    manifest = {
        "provider_rejections": [],
        "raw_pages": [{"sha256": "a" * 64}],
        "symbol_stats": {
            "BCPC": {
                "bar_rows": 252,
                "first_timestamp": "2016-01-04T05:00:00Z",
                "last_timestamp": "2016-12-30T05:00:00Z",
            }
        },
    }
    acquirer._load_completed_manifest = lambda candidate: manifest if candidate == unit else None  # type: ignore[method-assign]

    result = acquirer._persist_observed_summary(["BCPC", "BCpC"], [unit])
    assert result == (0, 0, 0, 0, 1, 252, 0, 0, 1)

    con = duckdb.connect(":memory:")
    try:
        anomaly = con.execute(
            "SELECT classification, requested_symbol, returned_symbol, casefold_match_count, bar_rows "
            "FROM read_parquet(?)",
            [str(acquirer.response_symbol_anomalies_path)],
        ).fetchone()
        observed = con.execute(
            "SELECT symbol, bar_rows, observed, zero_bar FROM read_parquet(?) ORDER BY symbol",
            [str(acquirer.observed_summary_path)],
        ).fetchall()
    finally:
        con.close()

    assert anomaly == ("AMBIGUOUS_CASE_FOLD_RESPONSE", None, "BCPC", 2, 252)
    assert observed == [
        ("BCPC", 0, False, True),
        ("BCpC", 0, False, True),
    ]
