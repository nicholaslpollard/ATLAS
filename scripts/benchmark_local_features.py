from __future__ import annotations

import argparse
import glob
import json
import sys
import tempfile
import time
import tracemalloc
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from packages.core.enums import Timeframe
from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.benchmark import build_feature_benchmark_summary
from packages.features.engine import CORE_BAR_COLUMNS, compute_core_features
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.historical_materializer import HistoricalFeatureMaterializer
from packages.features.incremental import IncrementalFeatureEngine

BENCHMARK_CONTRACT = "atlas-local-feature-benchmark-v2-batch-vs-production-incremental-provider-free"
STEADY_STATE_CONTRACT = "atlas-production-incremental-steady-state-benchmark-v1-provider-free"
DEFAULT_MAX_ROWS = 250_000
DEFAULT_STEADY_STATE_SYMBOLS = 1_000
DEFAULT_STEADY_STATE_BARS = 10
STEADY_STATE_WARMUP_BARS = 200
PARITY_ATOL = 1e-10
PARITY_RTOL = 1e-10


def _matched_source_inventory(pattern: str) -> tuple[int, int]:
    matches = glob.glob(pattern, recursive=True)
    if not matches and Path(pattern).is_file():
        matches = [pattern]
    files = [Path(item) for item in matches if Path(item).is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def _configured_source_for_timeframe(timeframe: str) -> str:
    try:
        resolved_timeframe = Timeframe(timeframe)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in Timeframe)
        raise ValueError(f"unsupported timeframe {timeframe!r}; expected one of: {allowed}") from exc
    settings = load_settings(ROOT)
    return MarketDataPaths(settings).glob_for_timeframe(resolved_timeframe)


def _load_bounded_source(source: str, max_rows: int) -> tuple[pd.DataFrame, bool]:
    if max_rows <= 0:
        raise ValueError("max_rows must be positive")
    con = connect_utc(":memory:")
    try:
        source_sql = sql_string(source)
        description = con.execute(
            f"DESCRIBE SELECT * FROM read_parquet({source_sql}, union_by_name=true)"
        ).fetchall()
        available = {str(row[0]) for row in description}
        missing = [column for column in CORE_BAR_COLUMNS if column not in available]
        if missing:
            raise ValueError(f"source is missing required feature columns: {', '.join(missing)}")

        columns = list(CORE_BAR_COLUMNS)
        if "session_segment" in available:
            columns.append("session_segment")
        if "session_date" in available:
            columns.append("session_date")
        select_columns = ", ".join(columns)
        # Keep the benchmark sample bounded. The batch engine sorts by exact stream
        # internally; the production incremental path below reuses that exact sorted
        # source order so its timing mirrors HistoricalFeatureMaterializer._update_engine.
        frame = con.execute(
            f"""
            SELECT {select_columns}
            FROM read_parquet({source_sql}, union_by_name=true)
            LIMIT {int(max_rows) + 1}
            """
        ).fetch_df()
    finally:
        con.close()
    bounded = len(frame) > max_rows
    if bounded:
        frame = frame.iloc[:max_rows].copy()
    return frame, bounded


def _write_temp_parquet(frame: pd.DataFrame, target: Path) -> int:
    con = connect_utc(":memory:")
    try:
        con.register("benchmark_features", frame)
        con.execute(
            f"COPY benchmark_features TO {sql_string(target)} "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"
        )
    finally:
        con.close()
    return target.stat().st_size


def _measure_batch(feature_input: pd.DataFrame) -> tuple[pd.DataFrame, float, float, int]:
    tracemalloc.start()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    try:
        output = compute_core_features(feature_input)
        cpu_seconds = time.process_time() - cpu_start
        wall_seconds = time.perf_counter() - wall_start
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return output, wall_seconds, cpu_seconds, int(peak_bytes)


def _measure_production_incremental(
    ordered_batch_output: pd.DataFrame,
) -> tuple[pd.DataFrame, float, float, int]:
    source_columns = list(CORE_BAR_COLUMNS)
    if "session_segment" in ordered_batch_output.columns:
        source_columns.append("session_segment")
    ordered_bars = ordered_batch_output[source_columns].copy()
    feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
    engine = IncrementalFeatureEngine()

    tracemalloc.start()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    try:
        # This is the exact row-by-row production transformation used by the
        # accepted HistoricalFeatureMaterializer, not a benchmark-only imitation.
        output = HistoricalFeatureMaterializer._update_engine(engine, ordered_bars, feature_names)
        cpu_seconds = time.process_time() - cpu_start
        wall_seconds = time.perf_counter() - wall_start
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return output, wall_seconds, cpu_seconds, int(peak_bytes)


def _parity_summary(batch_output: pd.DataFrame, incremental_output: pd.DataFrame) -> dict[str, Any]:
    feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
    failed: list[str] = []
    maximum_abs_diff = 0.0
    if len(batch_output) != len(incremental_output):
        failed = list(feature_names)
    else:
        for name in feature_names:
            expected = batch_output[name].to_numpy(dtype="float64")
            actual = incremental_output[name].to_numpy(dtype="float64")
            finite = np.isfinite(expected) & np.isfinite(actual)
            if finite.any():
                maximum_abs_diff = max(
                    maximum_abs_diff,
                    float(np.max(np.abs(expected[finite] - actual[finite]))),
                )
            if not np.allclose(
                expected,
                actual,
                atol=PARITY_ATOL,
                rtol=PARITY_RTOL,
                equal_nan=True,
            ):
                failed.append(name)
    return {
        "passed": not failed,
        "failed_feature_count": len(failed),
        "failed_features": failed,
        "maximum_abs_diff": maximum_abs_diff,
        "atol": PARITY_ATOL,
        "rtol": PARITY_RTOL,
    }


def benchmark_source(source: str, *, timeframe: str, max_rows: int = DEFAULT_MAX_ROWS) -> dict[str, Any]:
    source_file_count, source_bytes = _matched_source_inventory(source)
    if source_file_count <= 0 or source_bytes <= 0:
        raise FileNotFoundError("local benchmark source did not resolve to readable files")

    bars, sample_was_bounded = _load_bounded_source(source, max_rows)
    if bars.empty:
        raise ValueError("local benchmark source contains no rows")

    session_count = 0
    if "session_date" in bars.columns:
        session_count = int(bars["session_date"].nunique(dropna=True))
    symbol_count = int(bars["symbol"].nunique(dropna=True))

    feature_input = bars.drop(columns=["session_date"], errors="ignore")
    batch_output, wall_seconds, process_cpu_seconds, peak_tracemalloc_bytes = _measure_batch(feature_input)
    incremental_output, incremental_wall, incremental_cpu, incremental_peak = _measure_production_incremental(batch_output)
    parity = _parity_summary(batch_output, incremental_output)
    if not parity["passed"]:
        raise RuntimeError(
            "batch/incremental feature parity failed: " + ", ".join(parity["failed_features"])
        )

    output_memory_bytes = int(batch_output.memory_usage(index=True, deep=True).sum())
    with tempfile.TemporaryDirectory(prefix="atlas-feature-benchmark-") as temp_dir:
        temp_path = Path(temp_dir) / "features.parquet"
        output_parquet_bytes = _write_temp_parquet(batch_output, temp_path)

    summary = build_feature_benchmark_summary(
        timeframe=timeframe,
        sessions=session_count,
        rows=len(feature_input),
        symbols=symbol_count,
        source_bytes=source_bytes,
        output_memory_bytes=output_memory_bytes,
        output_parquet_bytes=output_parquet_bytes,
        wall_seconds=wall_seconds,
        process_cpu_seconds=process_cpu_seconds,
        peak_rss_bytes=None,
        registered_features=len(CORE_FEATURE_REGISTRY.all()),
    )
    if sample_was_bounded:
        summary["output_to_source_ratio"] = None
    incremental_rows_per_second = len(feature_input) / incremental_wall if incremental_wall > 0 else 0.0
    summary.update(
        {
            "contract_version": BENCHMARK_CONTRACT,
            "max_rows": int(max_rows),
            "source_file_count": int(source_file_count),
            "source_bytes_scope": "MATCHED_FILES_TOTAL_NOT_SAMPLE_BYTES" if sample_was_bounded else "FULL_BENCHMARK_INPUT",
            "sample_was_bounded": sample_was_bounded,
            "peak_tracemalloc_bytes": int(peak_tracemalloc_bytes),
            "batch_engine": {
                "wall_seconds": wall_seconds,
                "process_cpu_seconds": process_cpu_seconds,
                "rows_per_second": summary["rows_per_second"],
                "cpu_one_core_percent": summary["cpu_one_core_percent"],
                "peak_tracemalloc_bytes": int(peak_tracemalloc_bytes),
            },
            "production_incremental_engine": {
                "wall_seconds": incremental_wall,
                "process_cpu_seconds": incremental_cpu,
                "rows_per_second": incremental_rows_per_second,
                "cpu_one_core_percent": (incremental_cpu / incremental_wall * 100.0) if incremental_wall > 0 else 0.0,
                "peak_tracemalloc_bytes": int(incremental_peak),
            },
            "incremental_vs_batch_rows_per_second_ratio": (
                incremental_rows_per_second / summary["rows_per_second"]
                if summary["rows_per_second"] > 0
                else None
            ),
            "feature_parity": parity,
            "provider_calls_performed": 0,
            "provider_writes_performed": 0,
            "broker_calls_performed": 0,
            "broker_writes_performed": 0,
            "temporary_output_deleted": True,
        }
    )
    return summary


def benchmark_production_steady_state(
    *,
    symbol_count: int = DEFAULT_STEADY_STATE_SYMBOLS,
    timed_bars_per_symbol: int = DEFAULT_STEADY_STATE_BARS,
) -> dict[str, Any]:
    if symbol_count <= 0:
        raise ValueError("symbol_count must be positive")
    if timed_bars_per_symbol <= 0:
        raise ValueError("timed_bars_per_symbol must be positive")

    feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
    engine = IncrementalFeatureEngine()
    symbols = [f"BENCH{index:05d}" for index in range(symbol_count)]
    start = datetime(2024, 1, 2, tzinfo=UTC)

    warmup_start = time.perf_counter()
    for symbol_index, symbol in enumerate(symbols):
        base = 40.0 + (symbol_index % 500) * 0.2
        for step in range(STEADY_STATE_WARMUP_BARS):
            close = base + step * 0.01 + ((step % 7) - 3) * 0.003
            engine.update(
                symbol=symbol,
                timestamp_utc=start + timedelta(days=step),
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=float(100_000 + symbol_index * 5 + step * 10),
            )
    warmup_wall_seconds = time.perf_counter() - warmup_start

    timed_records: list[dict[str, object]] = []
    for symbol_index, symbol in enumerate(symbols):
        base = 40.0 + (symbol_index % 500) * 0.2
        for offset in range(timed_bars_per_symbol):
            step = STEADY_STATE_WARMUP_BARS + offset
            close = base + step * 0.01 + ((step % 7) - 3) * 0.003
            timed_records.append(
                {
                    "symbol": symbol,
                    "timestamp_utc": start + timedelta(days=step),
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": float(100_000 + symbol_index * 5 + step * 10),
                }
            )
    timed_frame = pd.DataFrame.from_records(timed_records, columns=list(CORE_BAR_COLUMNS))

    tracemalloc.start()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    try:
        output = HistoricalFeatureMaterializer._update_engine(engine, timed_frame, feature_names)
        cpu_seconds = time.process_time() - cpu_start
        wall_seconds = time.perf_counter() - wall_start
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    row_count = len(timed_frame)
    finite_feature_cells = int(np.isfinite(output[feature_names].to_numpy(dtype="float64")).sum())
    expected_feature_cells = row_count * len(feature_names)
    rows_per_second = row_count / wall_seconds if wall_seconds > 0 else 0.0
    return {
        "contract_version": STEADY_STATE_CONTRACT,
        "symbol_count": symbol_count,
        "warmup_bars_per_symbol": STEADY_STATE_WARMUP_BARS,
        "timed_bars_per_symbol": timed_bars_per_symbol,
        "timed_rows": row_count,
        "registered_features": len(feature_names),
        "warmup_wall_seconds": warmup_wall_seconds,
        "wall_seconds": wall_seconds,
        "process_cpu_seconds": cpu_seconds,
        "rows_per_second": rows_per_second,
        "cpu_one_core_percent": (cpu_seconds / wall_seconds * 100.0) if wall_seconds > 0 else 0.0,
        "peak_tracemalloc_bytes": int(peak_bytes),
        "finite_feature_cells": finite_feature_cells,
        "expected_feature_cells": expected_feature_cells,
        "finite_feature_fraction": finite_feature_cells / expected_feature_cells if expected_feature_cells else 0.0,
        "provider_calls_performed": 0,
        "provider_writes_performed": 0,
        "broker_calls_performed": 0,
        "broker_writes_performed": 0,
        "production_data_writes_performed": 0,
    }


def _synthetic_source(target: Path) -> None:
    rows: list[dict[str, object]] = []
    timestamps = pd.date_range("2025-01-02", periods=260, freq="D", tz="UTC")
    for symbol_index, symbol in enumerate(("AAA", "BBB", "CCC", "DDD")):
        base = 50.0 + symbol_index * 10.0
        for index, timestamp in enumerate(timestamps):
            close = base + index * 0.05 + ((index % 7) - 3) * 0.02
            rows.append(
                {
                    "symbol": symbol,
                    "timestamp_utc": timestamp,
                    "session_date": timestamp.date(),
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": float(100_000 + symbol_index * 10_000 + index * 25),
                }
            )
    frame = pd.DataFrame.from_records(rows)
    _write_temp_parquet(frame, target)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark ATLAS batch and accepted production incremental feature computation locally; no providers or brokers are initialized."
    )
    parser.add_argument(
        "--source",
        help="Optional local Parquet file/glob override. When omitted, ATLAS resolves the configured source for --timeframe. The path is never emitted in benchmark output.",
    )
    parser.add_argument("--timeframe", default="1d", help="ATLAS timeframe to benchmark (default: 1d).")
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS, help=f"Bounded sample row cap (default: {DEFAULT_MAX_ROWS:,}).")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON.")
    parser.add_argument("--self-test", action="store_true", help="Run a deterministic synthetic local-only batch/parity benchmark for CI/smoke validation.")
    parser.add_argument("--steady-state-only", action="store_true", help="Skip Parquet/batch work and benchmark only fully-warmed production incremental updates.")
    parser.add_argument("--steady-state-symbols", type=int, default=DEFAULT_STEADY_STATE_SYMBOLS, help=f"Synthetic exact symbol streams for steady-state mode (default: {DEFAULT_STEADY_STATE_SYMBOLS:,}).")
    parser.add_argument("--steady-state-bars", type=int, default=DEFAULT_STEADY_STATE_BARS, help=f"Timed bars per fully-warmed symbol stream (default: {DEFAULT_STEADY_STATE_BARS}).")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.self_test and (args.source or args.steady_state_only):
        raise SystemExit("--self-test cannot be combined with --source or --steady-state-only")

    if args.steady_state_only:
        summary = benchmark_production_steady_state(
            symbol_count=args.steady_state_symbols,
            timed_bars_per_symbol=args.steady_state_bars,
        )
    elif args.self_test:
        with tempfile.TemporaryDirectory(prefix="atlas-feature-benchmark-selftest-") as temp_dir:
            source = Path(temp_dir) / "source.parquet"
            _synthetic_source(source)
            summary = benchmark_source(str(source), timeframe="1d", max_rows=args.max_rows)
    else:
        try:
            source = str(args.source) if args.source else _configured_source_for_timeframe(str(args.timeframe))
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        summary = benchmark_source(source, timeframe=str(args.timeframe), max_rows=args.max_rows)

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    elif args.steady_state_only:
        print("ATLAS production incremental steady-state benchmark")
        print(f"  contract: {summary['contract_version']}")
        print(f"  symbols: {summary['symbol_count']:,}")
        print(f"  warmup bars/symbol: {summary['warmup_bars_per_symbol']}")
        print(f"  timed rows: {summary['timed_rows']:,}")
        print(f"  rows/second: {summary['rows_per_second']:,.0f}")
        print(f"  finite feature fraction: {summary['finite_feature_fraction']:.4f}")
        print("  provider calls/writes: 0 / 0")
        print("  broker calls/writes: 0 / 0")
        print("  production data writes: 0")
    else:
        print("ATLAS local feature benchmark")
        print(f"  contract: {summary['contract_version']}")
        print(f"  timeframe: {summary['timeframe']}")
        print(f"  rows: {summary['rows']:,}")
        print(f"  symbols: {summary['symbols']:,}")
        print(f"  sessions: {summary['sessions']:,}")
        print(f"  registered features: {summary['registered_features']}")
        print(f"  batch rows/second: {summary['batch_engine']['rows_per_second']:,.0f}")
        print(f"  production incremental rows/second: {summary['production_incremental_engine']['rows_per_second']:,.0f}")
        print(f"  incremental/batch speed ratio: {summary['incremental_vs_batch_rows_per_second_ratio']:.2f}x")
        print(f"  exact feature parity: {summary['feature_parity']['passed']}")
        print(f"  maximum parity diff: {summary['feature_parity']['maximum_abs_diff']:.3e}")
        print(f"  output parquet bytes: {summary['output_parquet_bytes']:,}")
        print(f"  source scope: {summary['source_bytes_scope']}")
        print("  provider calls/writes: 0 / 0")
        print("  broker calls/writes: 0 / 0")
        print("  temporary output: deleted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
