from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb

from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    ALPACA_V2_SOURCE_PREFIX,
    B34_MASTER_PROTECTED_START,
    run_b34_audit,
    validate_minute_rows,
)
from packages.schemas.canonical_market import (
    CANONICAL_STOCK_BAR_COLUMNS,
    CANONICAL_STOCK_DAILY_COLUMNS,
    canonical_stock_bar_schema_matches,
    canonical_stock_daily_schema_matches,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _row(symbol: str, timestamp: datetime) -> tuple[object, ...]:
    session_date = timestamp.astimezone(UTC).date()
    return (
        symbol,
        timestamp,
        session_date,
        "1m",
        "regular",
        100.0,
        101.0,
        99.0,
        100.5,
        1000.0,
        100.25,
        10,
        "alpaca",
        "stock_minute_aggregates",
        f"{ALPACA_V2_SOURCE_PREFIX}fixture",
        False,
        timestamp,
    )


def _write_parquet(path: Path, rows: list[tuple[object, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE bars(
                symbol VARCHAR,
                timestamp_utc TIMESTAMPTZ,
                session_date DATE,
                timeframe VARCHAR,
                session_segment VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                vwap DOUBLE,
                transaction_count BIGINT,
                provider VARCHAR,
                dataset VARCHAR,
                source_id VARCHAR,
                is_adjusted BOOLEAN,
                provider_timestamp_utc TIMESTAMPTZ
            )
            """
        )
        con.executemany(
            "INSERT INTO bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.execute(
            "COPY (SELECT * FROM bars ORDER BY symbol, timestamp_utc) "
            "TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(path)],
        )
    finally:
        con.close()


def _write_unit(
    layout: V2Layout,
    *,
    year: int,
    month: int,
    batch: int,
    symbols: tuple[str, ...],
    rows: list[tuple[object, ...]],
) -> None:
    unit_id = f"fixture-{year:04d}-{month:02d}-{batch:04d}"
    partition = (
        Path(f"year={year:04d}")
        / f"month={month:02d}"
        / f"batch={batch:04d}"
    )
    canonical = layout.canonical_minute / partition / f"{unit_id}.parquet"
    raw = layout.source / "bars" / "1m" / partition / f"{unit_id}.concat.json.gz"
    checkpoint = (
        layout.checkpoints
        / "native_units"
        / "1m"
        / partition
        / f"{unit_id}.json"
    )
    _write_parquet(canonical, rows)
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_bytes(gzip.compress(b'{"fixture":true}\n', mtime=0))
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "contract": "atlas-alpaca-sip-v2-native-unit-v1",
        "status": "COMPLETE",
        "unit_id": unit_id,
        "unit": {
            "unit_id": unit_id,
            "provider_timeframe": "1Min",
            "canonical_timeframe": "1m",
            "window_start": f"{year:04d}-{month:02d}-01",
            "window_end_exclusive": (
                f"{year + 1:04d}-01-01"
                if month == 12
                else f"{year:04d}-{month + 1:02d}-01"
            ),
            "year": year,
            "month": month,
            "batch_index": batch,
            "symbols": list(symbols),
            "universe_sha256": "u" * 64,
            "policy_sha256": "p" * 64,
        },
        "canonical": {
            "path": str(canonical),
            "sha256": _sha256(canonical),
            "canonical_rows": len(rows),
        },
        "raw_bundle": {
            "path": str(raw),
            "sha256": _sha256(raw),
        },
    }
    checkpoint.write_text(json.dumps(document), encoding="utf-8")


def test_b34_real_data_audit_contract_covers_required_classes_without_protected_reads(
    tmp_path: Path,
) -> None:
    layout = V2Layout.beneath(tmp_path / "data")
    layout.create()

    march_rows = [
        _row("AAPL", datetime(2026, 3, 9, 13, 30, tzinfo=UTC)),
        _row("AAPL", datetime(2026, 3, 20, 13, 30, tzinfo=UTC)),
    ]
    april_rows = [
        _row("SPLT", datetime(2026, 4, 15, 13, 30, tzinfo=UTC)),
        _row("AAPL", datetime(2026, 4, 30, 13, 30, tzinfo=UTC)),
        _row("AAPL", datetime(2026, 4, 30, 13, 31, tzinfo=UTC)),
    ]
    _write_unit(
        layout,
        year=2026,
        month=3,
        batch=0,
        symbols=("AAPL", "OTHER"),
        rows=march_rows,
    )
    _write_unit(
        layout,
        year=2026,
        month=4,
        batch=0,
        symbols=("AAPL", "SPLT", "THIN"),
        rows=april_rows,
    )

    actions = layout.corporate_actions / "native_actions.jsonl.gz"
    actions.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            {
                "action_type": "forward_splits",
                "payload": {"symbol": "SPLT", "ex_date": "2026-04-15"},
            }
        )
        + "\n"
        + json.dumps(
            {
                "action_type": "cash_dividends",
                "payload": {"symbol": "AAPL", "ex_date": "2026-03-20"},
            }
        )
        + "\n"
    ).encode("utf-8")
    actions.write_bytes(gzip.compress(payload, mtime=0))

    report = run_b34_audit(tmp_path)

    assert report["accepted"] is True
    assert report["status"] == "ACCEPTED"
    assert report["provider_calls"] == 0
    assert report["broker_reads"] == 0
    assert report["broker_writes"] == 0
    assert report["paper_authority"] is False
    assert report["full_minute_materialization_authority"] is False
    assert report["protected_interval"]["overlapping_canonical_partitions_opened"] == 0

    samples = {sample["sample_class"]: sample for sample in report["sample_classes"]}
    assert set(samples) == {
        "liquid_symbol_day",
        "sparse_or_no_trade_symbol_day",
        "split_day",
        "other_corporate_action_day",
        "dst_session_boundary_day",
    }
    assert samples["liquid_symbol_day"]["row_count"] == 2
    assert samples["sparse_or_no_trade_symbol_day"]["absence_evidence"] is True
    assert samples["split_day"]["action_type"] == "forward_splits"
    assert samples["other_corporate_action_day"]["action_type"] == "cash_dividends"
    assert samples["dst_session_boundary_day"]["utc_offset_seconds"] == [-14400]
    assert all(item["accepted"] for item in report["unit_integrity"])


def test_minute_validator_rejects_consumed_master_holdout_dates() -> None:
    protected = B34_MASTER_PROTECTED_START
    report = validate_minute_rows(
        [],
        sample_class="sparse_or_no_trade_symbol_day",
        symbol="AAPL",
        session_date=protected,
        allow_empty=True,
    )
    assert report["accepted"] is False
    assert any("master holdout" in error for error in report["errors"])


def test_canonical_stock_bar_schema_generalizes_daily_alias_without_breaking_it() -> None:
    assert CANONICAL_STOCK_BAR_COLUMNS == CANONICAL_STOCK_DAILY_COLUMNS
    description = [
        (name, duck_type)
        for name, duck_type in zip(
            CANONICAL_STOCK_BAR_COLUMNS,
            (
                "VARCHAR",
                "TIMESTAMP WITH TIME ZONE",
                "DATE",
                "VARCHAR",
                "VARCHAR",
                "DOUBLE",
                "DOUBLE",
                "DOUBLE",
                "DOUBLE",
                "DOUBLE",
                "DOUBLE",
                "BIGINT",
                "VARCHAR",
                "VARCHAR",
                "VARCHAR",
                "BOOLEAN",
                "TIMESTAMP WITH TIME ZONE",
            ),
            strict=True,
        )
    ]
    assert canonical_stock_bar_schema_matches(description)
    assert canonical_stock_daily_schema_matches(description)
