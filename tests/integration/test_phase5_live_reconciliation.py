from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from packages.core.enums import LiveFeedMode, Timeframe
from packages.core.settings import load_settings
from packages.core.timestamps import utc_to_epoch_ms
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.live.journal import LiveEventJournal
from packages.live.reconciliation import LiveFinalizationReconciler

ROOT = Path(__file__).resolve().parents[2]


def _raw_bar(symbol: str, start: datetime, close: float, volume: float) -> dict[str, object]:
    return {
        "ev": "AM",
        "sym": symbol,
        "o": 100.0,
        "h": max(101.0, close),
        "l": min(99.0, close),
        "c": close,
        "v": volume,
        "s": utc_to_epoch_ms(start),
        "e": utc_to_epoch_ms(start + timedelta(minutes=1)),
    }


def test_live_reconciliation_dedupes_updates_and_keeps_canonical_authority(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    paths = MarketDataPaths(settings)
    session = date(2026, 8, 14)
    t0 = datetime(2026, 8, 14, 14, 30, tzinfo=UTC)

    with LiveEventJournal(settings, flush_every=1) as journal:
        journal.append(
            _raw_bar("AAPL", t0, 100.1, 1000),
            session_date=session,
            received_at_utc=t0 + timedelta(minutes=16),
            feed_mode=LiveFeedMode.DELAYED,
        )
        journal.append(
            _raw_bar("AAPL", t0, 100.2, 1000),
            session_date=session,
            received_at_utc=t0 + timedelta(minutes=17),
            feed_mode=LiveFeedMode.DELAYED,
        )
        journal.append(
            _raw_bar("AAPL", t0 + timedelta(minutes=1), 101.0, 1200),
            session_date=session,
            received_at_utc=t0 + timedelta(minutes=18),
            feed_mode=LiveFeedMode.DELAYED,
        )
        journal.append(
            _raw_bar("MSFT", t0, 200.0, 500),
            session_date=session,
            received_at_utc=t0 + timedelta(minutes=16),
            feed_mode=LiveFeedMode.DELAYED,
        )

    canonical = paths.canonical_file(Timeframe.MINUTE_1, session)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    con = connect_utc(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE bars (
                symbol VARCHAR,
                timestamp_utc TIMESTAMPTZ,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE
            )
            """
        )
        con.executemany(
            "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("AAPL", t0, 100.0, 101.0, 99.0, 100.2, 1000.0),
                ("AAPL", t0 + timedelta(minutes=1), 100.0, 101.1, 99.0, 101.1, 1200.0),
                ("GOOG", t0, 100.0, 101.0, 99.0, 100.0, 700.0),
            ],
        )
        con.execute(f"COPY bars TO {sql_string(canonical)} (FORMAT PARQUET)")
    finally:
        con.close()

    result = LiveFinalizationReconciler(settings).reconcile(session)
    assert result.live_bar_count == 3
    assert result.canonical_bar_count == 3
    assert result.matched_key_count == 2
    assert result.exact_match_count == 1
    assert result.value_mismatch_count == 1
    assert result.live_only_key_count == 1
    assert result.canonical_only_key_count == 1

    payload = json.loads(paths.live_reconciliation_report(session).read_text(encoding="utf-8"))
    assert payload["policy"]["canonical_final_is_authoritative"] is True
    assert payload["policy"]["live_values_rewrite_canonical"] is False
    assert payload["summary"]["value_mismatch_count"] == 1
