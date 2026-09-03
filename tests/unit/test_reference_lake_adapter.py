from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from packages.backtesting.reference_lake_adapter import (
    EXPECTED_SPLIT_REPORT_CONTRACT,
    REFERENCE_LAKE_ADAPTER_CONTRACT_VERSION,
    ReferenceDailyLakeAdapter,
    ReferenceLakeAdapterError,
    ReferenceLakeScopeError,
    ReferenceLakeSourceBundle,
    validate_reference_lake_scope,
)
from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.features.reference_daily import compute_reference_daily_features


ROOT = Path(__file__).resolve().parents[2]
SESSIONS = (date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_canonical(path: Path, session: date, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    con = duckdb.connect(":memory:")
    try:
        con.register("bars", frame)
        con.execute(
            f"""
            COPY (
                SELECT
                    CAST(symbol AS VARCHAR) symbol,
                    CAST(timestamp_utc AS TIMESTAMPTZ) timestamp_utc,
                    CAST(session_date AS DATE) session_date,
                    CAST(timeframe AS VARCHAR) timeframe,
                    CAST(session_segment AS VARCHAR) session_segment,
                    CAST(open AS DOUBLE) AS open,
                    CAST(high AS DOUBLE) AS high,
                    CAST(low AS DOUBLE) AS low,
                    CAST(close AS DOUBLE) AS close,
                    CAST(volume AS DOUBLE) AS volume,
                    CAST(NULL AS DOUBLE) AS vwap,
                    CAST(NULL AS BIGINT) AS transaction_count,
                    CAST(provider AS VARCHAR) AS provider,
                    CAST(dataset AS VARCHAR) AS dataset,
                    CAST(source_id AS VARCHAR) AS source_id,
                    CAST(NULL AS BOOLEAN) AS is_adjusted,
                    CAST(timestamp_utc AS TIMESTAMPTZ) AS provider_timestamp_utc
                FROM bars ORDER BY symbol
            ) TO '{path.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()


def _bar(symbol: str, session: date, *, provider: str = "massive") -> dict[str, object]:
    return {
        "symbol": symbol,
        "timestamp_utc": datetime(session.year, session.month, session.day, 14, 30, tzinfo=UTC),
        "session_date": session,
        "timeframe": "1d",
        "session_segment": "regular",
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 100_000.0,
        "provider": provider,
        "dataset": "stock_daily_aggregates",
        "source_id": f"source:{session}:{symbol}",
    }


def _write_reference(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            ("ins-good", "GOOD", "strong", "stocks", "us", "XNYS", "CS"),
            ("ins-split", "SPLT", "strong", "stocks", "us", "XNAS", "CS"),
            ("ins-gap", "GAP", "medium", "stocks", "us", "XNYS", "CS"),
            ("ins-amb-1", "AMB", "strong", "stocks", "us", "XNYS", "CS"),
            ("ins-amb-2", "AMB", "strong", "stocks", "us", "XNYS", "CS"),
        ],
        columns=[
            "instrument_id",
            "ticker",
            "identity_quality",
            "market",
            "locale",
            "primary_exchange",
            "security_type",
        ],
    )
    frame["as_of_date"] = SESSIONS[0]
    con = duckdb.connect(":memory:")
    try:
        con.register("reference", frame)
        con.execute(
            f"COPY (SELECT * FROM reference ORDER BY ticker, instrument_id) "
            f"TO '{path.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()


def _write_empty_intervals(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            f"""
            COPY (
                SELECT
                    NULL::VARCHAR instrument_id,
                    NULL::VARCHAR ticker,
                    NULL::DATE valid_from_date,
                    NULL::DATE valid_to_date_exclusive,
                    NULL::BOOLEAN continuity_authority
                WHERE FALSE
            ) TO '{path.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()


def _bundle(tmp_path: Path, *, provider: str = "massive") -> tuple[object, ReferenceLakeSourceBundle]:
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    paths = MarketDataPaths(settings)
    canonical: list[Path] = []
    for session in SESSIONS:
        path = paths.canonical_file(Timeframe.DAY_1, session)
        rows = [
            _bar("GOOD", session, provider=provider),
            _bar("SPLT", session),
            _bar("AMB", session),
        ]
        if session != SESSIONS[1]:
            rows.append(_bar("GAP", session))
        _write_canonical(path, session, rows)
        canonical.append(path)

    reference = paths.reference_snapshot_file(SESSIONS[0])
    _write_reference(reference)
    intervals = paths.authoritative_ticker_intervals_file()
    _write_empty_intervals(intervals)

    split_evidence = tmp_path / "data" / "derived" / "ml" / "split-test.jsonl"
    split_evidence.parent.mkdir(parents=True, exist_ok=True)
    split_evidence.write_text(
        json.dumps({"ticker": "SPLT", "execution_date": "2025-01-03"}) + "\n",
        encoding="utf-8",
    )
    split_report = split_evidence.with_name("split-test.json")
    split_report.write_text(
        json.dumps(
            {
                "contract_version": EXPECTED_SPLIT_REPORT_CONTRACT,
                "history_start": "2021-08-16",
                "history_end": "2025-01-06",
                "split_evidence_path": str(split_evidence),
                "split_evidence_sha256": _sha256(split_evidence),
                "corporate_action_evidence_source": "Massive /stocks/v1/splits",
                "split_adjustment": {
                    "fetched_split_events": 1,
                    "fetched_split_symbols": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    bundle = ReferenceLakeSourceBundle(
        canonical_partitions=tuple(canonical),
        reference_snapshots=(reference,),
        authoritative_intervals=intervals,
        split_report=split_report,
        split_evidence=split_evidence,
    )
    return settings, bundle


def test_reference_lake_adapter_keeps_only_identity_exact_split_free_contiguous_streams(
    tmp_path: Path,
) -> None:
    settings, bundle = _bundle(tmp_path)
    result = ReferenceDailyLakeAdapter(settings).load(
        SESSIONS[0], SESSIONS[-1], bundle=bundle
    )

    assert REFERENCE_LAKE_ADAPTER_CONTRACT_VERSION.endswith("split-free-identity-exact")
    assert result.bars["instrument_id"].unique().tolist() == ["ins-good"]
    assert result.bars["ticker"].tolist() == ["GOOD", "GOOD", "GOOD"]
    assert result.bars["price_adjustment_mode"].eq("SPLIT_ADJUSTED").all()
    assert result.bars["split_adjustment_method"].eq(
        "FACTOR_1_CERTIFIED_NO_DOCUMENTED_SPLIT"
    ).all()
    assert result.report["unresolved_identity_rows"] == 3
    assert result.report["split_excluded_instruments"] == 1
    assert result.report["gap_excluded_instruments"] == 1
    assert result.report["protected_master_return_rows_read"] == 0
    assert result.report["performance_opened"] is False
    assert result.report["provider_writes"] == result.report["broker_writes"] == 0

    features = compute_reference_daily_features(result.bars)
    assert len(features) == 3
    assert features["instrument_id"].unique().tolist() == ["ins-good"]


def test_reference_lake_adapter_rejects_protected_or_preseam_scope() -> None:
    with pytest.raises(ReferenceLakeScopeError, match="provider seam"):
        validate_reference_lake_scope(date(2021, 8, 13), date(2021, 8, 16))
    with pytest.raises(ReferenceLakeScopeError, match="master protected"):
        validate_reference_lake_scope(date(2026, 5, 11), date(2026, 5, 12))


def test_reference_lake_adapter_rejects_split_evidence_hash_drift(tmp_path: Path) -> None:
    settings, bundle = _bundle(tmp_path)
    bundle.split_evidence.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ReferenceLakeAdapterError, match="SHA-256"):
        ReferenceDailyLakeAdapter(settings).load(SESSIONS[0], SESSIONS[-1], bundle=bundle)


def test_reference_lake_adapter_rejects_nonmassive_rows(tmp_path: Path) -> None:
    settings, bundle = _bundle(tmp_path, provider="alpaca")
    with pytest.raises(ReferenceLakeAdapterError, match="non-Massive"):
        ReferenceDailyLakeAdapter(settings).load(SESSIONS[0], SESSIONS[-1], bundle=bundle)


def test_reference_lake_adapter_rejects_future_reference_snapshot(tmp_path: Path) -> None:
    settings, bundle = _bundle(tmp_path)
    future = MarketDataPaths(settings).reference_snapshot_file(date(2025, 1, 7))
    _write_reference(future)
    unsafe = ReferenceLakeSourceBundle(
        canonical_partitions=bundle.canonical_partitions,
        reference_snapshots=(future,),
        authoritative_intervals=bundle.authoritative_intervals,
        split_report=bundle.split_report,
        split_evidence=bundle.split_evidence,
    )
    with pytest.raises(ReferenceLakeAdapterError, match="snapshot after"):
        ReferenceDailyLakeAdapter(settings).load(SESSIONS[0], SESSIONS[-1], bundle=unsafe)


def test_reference_lake_adapter_requires_exact_session_inventory(tmp_path: Path) -> None:
    settings, bundle = _bundle(tmp_path)
    incomplete = ReferenceLakeSourceBundle(
        canonical_partitions=bundle.canonical_partitions[:-1],
        reference_snapshots=bundle.reference_snapshots,
        authoritative_intervals=bundle.authoritative_intervals,
        split_report=bundle.split_report,
        split_evidence=bundle.split_evidence,
    )
    with pytest.raises(ReferenceLakeAdapterError, match="exactly match"):
        ReferenceDailyLakeAdapter(settings).load(
            SESSIONS[0], SESSIONS[-1], bundle=incomplete
        )
