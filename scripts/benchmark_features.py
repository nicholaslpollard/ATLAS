from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import tempfile
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.benchmark import build_feature_benchmark_summary, project_feature_storage
from packages.features.engine import compute_core_features
from packages.features.feature_registry import CORE_FEATURE_REGISTRY


def _peak_rss_bytes() -> int | None:
    try:
        if os.name == "nt":
            from ctypes import wintypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.argtypes = []
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(ProcessMemoryCounters),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            handle = kernel32.GetCurrentProcess()
            ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
            if not ok:
                return None
            return int(counters.PeakWorkingSetSize)

        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return peak if sys.platform == "darwin" else peak * 1024
    except Exception:
        return None


def _bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"{value / (1024 ** 2):,.1f} MiB"


def _time(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 60:
        return f"{value:,.1f}s"
    return f"{value / 60:,.1f}m"


def _sample_sessions(calendar: MarketCalendar, end: date, count: int) -> list[date]:
    if count < 1:
        raise ValueError("--sessions must be at least 1")
    lookback_days = max(45, count * 3)
    while True:
        start = end - timedelta(days=lookback_days)
        sessions = calendar.sessions_in_range(start, end)
        if len(sessions) >= count:
            return sessions[-count:]
        lookback_days *= 2
        if lookback_days > 365 * 20:
            raise RuntimeError("could not resolve enough exchange sessions for benchmark")


def _source_path(paths: MarketDataPaths, timeframe: Timeframe, session: date) -> Path:
    if timeframe in {Timeframe.MINUTE_1, Timeframe.DAY_1}:
        return paths.canonical_file(timeframe, session)
    return paths.derived_file(timeframe, session)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark ATLAS core feature computation and Parquet footprint on real historical bars."
    )
    parser.add_argument(
        "--timeframe",
        choices=["15m", "1h", "4h", "1d", "1m"],
        default="4h",
    )
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--sessions", type=int, default=20)
    parser.add_argument(
        "--project-sessions",
        type=int,
        default=None,
        help="Optionally project sample storage/compute linearly to this many sessions.",
    )
    parser.add_argument(
        "--allow-1m",
        action="store_true",
        help="Required for 1m because a multi-session full-market feature frame can consume substantial RAM.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    timeframe = Timeframe(args.timeframe)
    if timeframe == Timeframe.MINUTE_1 and not args.allow_1m:
        raise SystemExit("1m benchmark requires --allow-1m; benchmark larger bars first")

    settings = load_settings(PROJECT_ROOT)
    paths = MarketDataPaths(settings)
    calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
    sessions = _sample_sessions(calendar, args.end, args.sessions)
    source_paths = [_source_path(paths, timeframe, session) for session in sessions]
    missing = [path for path in source_paths if not path.is_file()]
    if missing:
        print("ATLAS feature benchmark cannot run; historical source partitions are missing:")
        for path in missing[:10]:
            print(f"  {path}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
        return 2

    source_bytes = sum(path.stat().st_size for path in source_paths)
    source_sql = "[" + ",".join(sql_string(path) for path in source_paths) + "]"
    con = connect_utc(":memory:")

    print("ATLAS Historical Feature Benchmark")
    print(f"  timeframe:         {timeframe.value}")
    print(f"  sample sessions:   {sessions[0]} -> {sessions[-1]} ({len(sessions)})")
    print(f"  registered core:   {len(CORE_FEATURE_REGISTRY.all())}")
    print(f"  source Parquet:     {_bytes(source_bytes)}")
    print("  loading bars...")

    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    try:
        bars = con.execute(
            f"""
            SELECT symbol, timestamp_utc, high, low, close, volume
            FROM read_parquet({source_sql}, union_by_name=true, hive_partitioning=true)
            ORDER BY symbol, timestamp_utc
            """
        ).fetch_df()
        print(f"  loaded rows:        {len(bars):,}")
        print(f"  symbols:            {bars['symbol'].nunique():,}")
        print("  computing features...")
        features = compute_core_features(bars)
        feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
        compact = features[["symbol", "timestamp_utc", *feature_names]].copy()
        output_memory_bytes = int(compact.memory_usage(index=True, deep=True).sum())

        cache_root = settings.resolved_path(settings.data.paths.cache)
        cache_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="atlas-feature-benchmark-", dir=cache_root) as temp_dir:
            sample_path = Path(temp_dir) / "features.parquet"
            con.register("atlas_feature_benchmark_output", compact)
            compression = settings.data.parquet.compression.upper()
            row_group_size = int(settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (SELECT * FROM atlas_feature_benchmark_output)
                TO {sql_string(sample_path)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            output_parquet_bytes = sample_path.stat().st_size

        wall_seconds = time.perf_counter() - wall_start
        process_cpu_seconds = time.process_time() - cpu_start
        summary = build_feature_benchmark_summary(
            timeframe=timeframe.value,
            sessions=len(sessions),
            rows=len(compact),
            symbols=int(compact["symbol"].nunique()),
            source_bytes=source_bytes,
            output_memory_bytes=output_memory_bytes,
            output_parquet_bytes=output_parquet_bytes,
            wall_seconds=wall_seconds,
            process_cpu_seconds=process_cpu_seconds,
            peak_rss_bytes=_peak_rss_bytes(),
            registered_features=len(feature_names),
        )
        summary["sample_start"] = sessions[0].isoformat()
        summary["sample_end"] = sessions[-1].isoformat()
        summary["feature_registry_fingerprint"] = CORE_FEATURE_REGISTRY.fingerprint()
        if args.project_sessions is not None:
            summary["projection"] = project_feature_storage(
                summary, target_sessions=args.project_sessions
            )

        report_path = paths.feature_benchmark_report(datetime.now(UTC))
        atomic_write_text(report_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    finally:
        con.close()

    print("ATLAS Historical Feature Benchmark result")
    print(f"  wall time:          {_time(summary['wall_seconds'])}")
    print(f"  process CPU:        {_time(summary['process_cpu_seconds'])}")
    print(f"  CPU one-core equiv: {summary['cpu_one_core_percent']:,.1f}%")
    print(f"  rows/second:        {summary['rows_per_second']:,.0f}")
    print(f"  peak process RSS:   {_bytes(summary['peak_rss_bytes'])}")
    print(f"  feature RAM frame:  {_bytes(summary['output_memory_bytes'])}")
    print(f"  feature Parquet:    {_bytes(summary['output_parquet_bytes'])}")
    print(f"  Parquet bytes/row:  {summary['output_parquet_bytes_per_row']:,.1f}")
    print(f"  output/source:      {summary['output_to_source_ratio']:,.2f}x")
    if args.project_sessions is not None:
        projection = summary["projection"]
        print(f"  projected sessions: {projection['target_sessions']:,}")
        print(f"  projected rows:     {projection['projected_rows']:,}")
        print(f"  projected Parquet:  {_bytes(projection['projected_parquet_bytes'])}")
        print(f"  projected compute:  {_time(projection['projected_compute_seconds'])}")
    print(f"  report:             {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
