from __future__ import annotations

import pytest

from scripts.benchmark_local_features import (
    _configured_source_for_timeframe,
    _synthetic_source,
    benchmark_production_steady_state,
    benchmark_source,
)


def test_configured_daily_benchmark_source_uses_atlas_path_contract() -> None:
    source = _configured_source_for_timeframe("1d").replace("\\", "/")
    assert source.endswith("/data/canonical/stocks/1d/**/*.parquet")


def test_configured_benchmark_source_rejects_unknown_timeframe() -> None:
    with pytest.raises(ValueError, match="unsupported timeframe"):
        _configured_source_for_timeframe("not-a-timeframe")


def test_synthetic_benchmark_compares_batch_with_production_incremental(tmp_path) -> None:
    source = tmp_path / "source.parquet"
    _synthetic_source(source)
    result = benchmark_source(str(source), timeframe="1d", max_rows=250_000)

    assert result["feature_parity"]["passed"] is True
    assert result["feature_parity"]["failed_feature_count"] == 0
    assert result["production_incremental_engine"]["rows_per_second"] > 0
    assert result["batch_engine"]["rows_per_second"] > 0
    assert result["provider_calls_performed"] == 0
    assert result["provider_writes_performed"] == 0
    assert result["broker_calls_performed"] == 0
    assert result["broker_writes_performed"] == 0
    assert result["temporary_output_deleted"] is True


def test_steady_state_benchmark_exercises_fully_warmed_production_features() -> None:
    result = benchmark_production_steady_state(symbol_count=4, timed_bars_per_symbol=2)

    assert result["warmup_bars_per_symbol"] == 200
    assert result["timed_rows"] == 8
    assert result["registered_features"] == 33
    assert result["rows_per_second"] > 0
    assert result["finite_feature_fraction"] == pytest.approx(1.0)
    assert result["provider_calls_performed"] == 0
    assert result["provider_writes_performed"] == 0
    assert result["broker_calls_performed"] == 0
    assert result["broker_writes_performed"] == 0
    assert result["production_data_writes_performed"] == 0
