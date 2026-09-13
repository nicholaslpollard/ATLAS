from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from packages.backtesting import successor_spy_benchmark_source as source


def _minute_rows(*, session: date, close: float, stale: float, valid: bool) -> dict[str, object]:
    return {
        "session_date": session,
        "timestamp_utc": pd.Timestamp(f"{session.isoformat()}T19:31:00Z"),
        "close": close,
        "staleness_minutes": stale,
        "minute_valid": valid,
    }


def test_2019_08_12_uses_same_session_native_daily_repair() -> None:
    session = date(2019, 8, 12)
    minute = pd.DataFrame([_minute_rows(session=session, close=288.50, stale=28.0, valid=False)])
    daily = pd.DataFrame([{"session_date": session, "close": 287.44}])

    benchmark, report = source.resolve_spy_benchmark_source(minute, daily)

    assert benchmark.to_dict("records") == [{"session_date": session, "close": 287.44}]
    assert report["daily_fallback_session_count"] == 1
    assert report["daily_fallback_sessions"][0]["session_date"] == "2019-08-12"
    assert report["daily_fallback_sessions"][0]["minute_staleness_minutes"] == 28.0
    assert report["daily_fallback_sessions"][0]["replacement_source"] == "NATIVE_RAW_DAILY"
    assert report["unresolved_session_count"] == 0


def test_valid_minute_close_remains_primary() -> None:
    session = date(2019, 8, 13)
    minute = pd.DataFrame([_minute_rows(session=session, close=292.55, stale=0.0, valid=True)])
    daily = pd.DataFrame([{"session_date": session, "close": 999.0}])

    benchmark, report = source.resolve_spy_benchmark_source(minute, daily)

    assert benchmark["close"].tolist() == [292.55]
    assert report["minute_primary_session_count"] == 1
    assert report["daily_fallback_session_count"] == 0


def test_2026_over_stale_minute_cannot_open_native_daily_fallback() -> None:
    session = date(2026, 4, 1)
    minute = pd.DataFrame([_minute_rows(session=session, close=500.0, stale=28.0, valid=False)])
    daily = pd.DataFrame([{"session_date": session, "close": 501.0}])

    with pytest.raises(
        source.SuccessorSpyBenchmarkSourceError,
        match="unresolved session",
    ):
        source.resolve_spy_benchmark_source(minute, daily)


def test_missing_pre2026_daily_repair_fails_closed() -> None:
    session = date(2019, 8, 12)
    minute = pd.DataFrame([_minute_rows(session=session, close=288.50, stale=28.0, valid=False)])
    daily = pd.DataFrame(columns=["session_date", "close"])

    with pytest.raises(source.SuccessorSpyBenchmarkSourceError, match="unresolved session"):
        source.resolve_spy_benchmark_source(minute, daily)


def test_duplicate_daily_repair_session_fails_closed() -> None:
    session = date(2019, 8, 12)
    minute = pd.DataFrame([_minute_rows(session=session, close=288.50, stale=28.0, valid=False)])
    daily = pd.DataFrame(
        [
            {"session_date": session, "close": 287.44},
            {"session_date": session, "close": 287.45},
        ]
    )

    with pytest.raises(source.SuccessorSpyBenchmarkSourceError, match="duplicate sessions"):
        source.resolve_spy_benchmark_source(minute, daily)


def test_source_audit_authority_never_promotes() -> None:
    authority = source.source_audit_authority()
    assert authority["strategy_outcomes_opened"] is False
    assert authority["consumed_master_rows_read"] == 0
    assert authority["future_blind_rows_read"] == 0
    assert authority["provider_calls"] == 0
    assert authority["broker_reads"] == 0
    assert authority["broker_writes"] == 0
    assert authority["paper_authority"] is False
    assert authority["live_authority"] is False
    assert authority["promotion_authority"] is False


def test_contract_forbids_2026_native_daily_partition() -> None:
    assert source.SPY_DAILY_FALLBACK_LAST_YEAR == 2025
    assert source.SPY_BENCHMARK_MAX_STALENESS_MINUTES == 5
    assert len(source.SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT) == 64


def test_parquet_io_uses_duckdb_without_pandas_optional_engines(tmp_path, monkeypatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("pandas optional Parquet engine must not be used")

    monkeypatch.setattr(pd, "read_parquet", blocked)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", blocked)
    path = tmp_path / "spy.parquet"
    frame = pd.DataFrame(
        [{"session_date": date(2019, 8, 12), "close": 287.44}]
    )

    sha256 = source._write_parquet_atomic(path, frame)
    loaded = source._read_parquet_frame(
        path, columns=("session_date", "close")
    )

    assert len(sha256) == 64
    assert pd.to_datetime(loaded["session_date"], errors="raise").dt.date.tolist() == [
        date(2019, 8, 12)
    ]
    assert loaded["close"].tolist() == [287.44]
