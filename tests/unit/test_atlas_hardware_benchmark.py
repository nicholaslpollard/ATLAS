from __future__ import annotations

from scripts.benchmark_atlas_hardware import (
    BENCHMARK_CONTRACT,
    _comparison_rows,
    _config,
    _python_kernel,
)


def test_python_kernel_is_deterministic() -> None:
    assert _python_kernel(10_000, 12345) == _python_kernel(10_000, 12345)
    assert _python_kernel(10_000, 12345) != _python_kernel(10_000, 54321)


def test_smoke_config_is_strictly_smaller_than_full_config() -> None:
    smoke = _config(True)
    full = _config(False)

    assert smoke.python_iterations < full.python_iterations
    assert smoke.numpy_size < full.numpy_size
    assert smoke.pandas_rows < full.pandas_rows
    assert smoke.duckdb_rows < full.duckdb_rows
    assert smoke.parquet_rows < full.parquet_rows
    assert smoke.parallel_tasks < full.parallel_tasks
    assert smoke.parallel_iterations_per_task < full.parallel_iterations_per_task


def test_comparison_rows_compute_only_positive_timings() -> None:
    baseline = {
        "contract": BENCHMARK_CONTRACT,
        "stages": {
            "python_scalar": {"seconds": 10.0},
            "ignored": {"seconds": 0.0},
        },
        "benchmark_seconds": 20.0,
    }
    current = {
        "contract": BENCHMARK_CONTRACT,
        "stages": {
            "python_scalar": {"seconds": 5.0},
            "ignored": {"seconds": 2.0},
        },
        "benchmark_seconds": 10.0,
    }

    assert _comparison_rows(baseline, current) == [
        ("python_scalar", 10.0, 5.0),
        ("TOTAL", 20.0, 10.0),
    ]
