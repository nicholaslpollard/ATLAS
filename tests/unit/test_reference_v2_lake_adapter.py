from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from packages.backtesting.reference_v2_lake_adapter import (
    REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION,
    ReferenceV2DailyLakeAdapter,
    ReferenceV2LakeAdapterError,
    ReferenceV2LakeScopeError,
    ReferenceV2UnavailableRegimeContextAdapter,
)
from packages.core.settings import load_settings
from packages.data.alpaca_v2_postbuild import RESEARCH_DAILY_CONTRACT
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.features.reference_daily import compute_reference_daily_features


SESSIONS = (date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _settings(tmp_path: Path):
    return load_settings().model_copy(update={"project_root": tmp_path})


def _source(tmp_path: Path):
    settings = _settings(tmp_path)
    layout = V2Layout.beneath((tmp_path / "data").resolve())
    fingerprint = "a" * 64
    target = (
        layout.derived
        / "research_daily"
        / fingerprint[:16]
        / "year=2025"
        / "part-000.parquet"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = pd.DataFrame(
        [
            {
                "instrument_id": "asset-aapl",
                "ticker": "AAPL",
                "session_date": session,
                "timestamp_utc": datetime(
                    session.year, session.month, session.day, 14, 30, tzinfo=UTC
                ),
                "signal_available_at_utc": datetime(
                    session.year, session.month, session.day, 21, 0, tzinfo=UTC
                ),
                "open": 100.0 + index,
                "high": 102.0 + index,
                "low": 99.0 + index,
                "close": 101.0 + index,
                "volume": 1_000_000.0,
                "unadjusted_close": 101.0 + index,
                "pit_active": True,
                "security_type": "CS",
                "identity_clear": True,
                "price_adjustment_mode": "SPLIT_ADJUSTED",
                "raw_price_lineage_id": f"alpaca-v2:{fingerprint}",
                "source_provider": "alpaca",
                "source_dataset": "stock_daily_aggregates_split_adjusted",
                "adjusted_source_id": "alpaca:sip:1Day:split:asof=-:v2:unit=test",
            }
            for index, session in enumerate(SESSIONS)
        ]
    )
    con = duckdb.connect(":memory:")
    try:
        con.register("rows", rows)
        con.execute(
            f"""
            COPY (
                SELECT
                    instrument_id::VARCHAR AS instrument_id,
                    ticker::VARCHAR AS ticker,
                    session_date::DATE AS session_date,
                    timestamp_utc::TIMESTAMPTZ AS timestamp_utc,
                    signal_available_at_utc::TIMESTAMPTZ AS signal_available_at_utc,
                    open::DOUBLE AS open,
                    high::DOUBLE AS high,
                    low::DOUBLE AS low,
                    close::DOUBLE AS close,
                    volume::DOUBLE AS volume,
                    unadjusted_close::DOUBLE AS unadjusted_close,
                    pit_active::BOOLEAN AS pit_active,
                    security_type::VARCHAR AS security_type,
                    identity_clear::BOOLEAN AS identity_clear,
                    price_adjustment_mode::VARCHAR AS price_adjustment_mode,
                    raw_price_lineage_id::VARCHAR AS raw_price_lineage_id,
                    source_provider::VARCHAR AS source_provider,
                    source_dataset::VARCHAR AS source_dataset,
                    adjusted_source_id::VARCHAR AS adjusted_source_id
                FROM rows ORDER BY instrument_id, session_date
            ) TO '{target.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    manifest = {
        "contract": RESEARCH_DAILY_CONTRACT,
        "status": "PASS",
        "source_fingerprint": fingerprint,
        "start_date": SESSIONS[0].isoformat(),
        "cutoff_session": SESSIONS[-1].isoformat(),
        "source_cutoff_session": SESSIONS[-1].isoformat(),
        "research_rows": len(rows),
        "partitions": [
            {
                "year": 2025,
                "path": str(target),
                "sha256": _sha256(target),
                "bytes": target.stat().st_size,
                "rows": len(rows),
            }
        ],
        "v1_ancestry": "FORBIDDEN",
        "v1_rows_read": 0,
        "master_protected_return_rows_read": 0,
        "historical_performance_opened": False,
        "production_promoted": False,
        "paper_authority": False,
        "live_authority": False,
        "cash_dividend_credits_materialized": False,
        "development_only": True,
        "protected_return_rows_materialized": 0,
    }
    manifest_path = layout.manifests / "research_daily.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return settings, target


def test_v2_adapter_loads_only_hash_bound_isolated_research_view(
    tmp_path: Path,
) -> None:
    settings, _target = _source(tmp_path)
    adapted = ReferenceV2DailyLakeAdapter(settings).load(SESSIONS[0], SESSIONS[-1])
    context = ReferenceV2UnavailableRegimeContextAdapter().attach(
        adapted.bars, SESSIONS[0], SESSIONS[-1]
    )
    features = compute_reference_daily_features(context.bars)

    assert adapted.report["contract_version"] == REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION
    assert adapted.report["output_rows"] == 3
    assert adapted.report["v1_rows_read"] == 0
    assert adapted.report["legacy_fallback_used"] is False
    assert adapted.bars["security_type"].eq("CS").all()
    assert context.bars["market_regime_composite"].eq("UNAVAILABLE").all()
    assert context.report["v1_regime_rows_read"] == 0
    assert features["universe_common_stock_ok"].eq(1.0).all()


def test_v2_adapter_rejects_partition_hash_drift(tmp_path: Path) -> None:
    settings, target = _source(tmp_path)
    with target.open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(ReferenceV2LakeAdapterError, match="SHA-256 drifted"):
        ReferenceV2DailyLakeAdapter(settings).load(SESSIONS[0], SESSIONS[-1])


def test_v2_adapter_rejects_physical_rows_beyond_manifest_cutoff(
    tmp_path: Path,
) -> None:
    settings, _target = _source(tmp_path)
    manifest_path = (
        V2Layout.beneath((tmp_path / "data").resolve()).manifests
        / "research_daily.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cutoff_session"] = SESSIONS[1].isoformat()
    manifest["source_cutoff_session"] = SESSIONS[1].isoformat()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with pytest.raises(ReferenceV2LakeAdapterError, match="row/date bounds"):
        ReferenceV2DailyLakeAdapter(settings).load(SESSIONS[0], SESSIONS[1])


def test_v2_adapter_rejects_protected_window(tmp_path: Path) -> None:
    settings, _target = _source(tmp_path)
    with pytest.raises(ReferenceV2LakeScopeError, match="protected"):
        ReferenceV2DailyLakeAdapter(settings).load(
            date(2026, 5, 12), date(2026, 5, 13)
        )


def test_v2_adapter_rejects_arbitrary_manifest_path(tmp_path: Path) -> None:
    settings, _target = _source(tmp_path)
    alternate = tmp_path / "alternate.json"
    alternate.write_text("{}", encoding="utf-8")
    with pytest.raises(ReferenceV2LakeAdapterError, match="isolated"):
        ReferenceV2DailyLakeAdapter(settings).load(
            SESSIONS[0], SESSIONS[-1], manifest_path=alternate
        )
