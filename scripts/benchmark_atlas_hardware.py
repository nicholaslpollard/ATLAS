from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


BENCHMARK_CONTRACT = "atlas-hardware-benchmark-v1"
RESULT_ROOT = Path("data/derived/hardware_benchmarks")


@dataclass(frozen=True)
class BenchmarkConfig:
    python_iterations: int
    numpy_size: int
    numpy_repeats: int
    pandas_rows: int
    duckdb_rows: int
    parquet_rows: int
    parallel_tasks: int
    parallel_iterations_per_task: int


def _config(smoke: bool) -> BenchmarkConfig:
    if smoke:
        return BenchmarkConfig(
            python_iterations=100_000,
            numpy_size=50_000,
            numpy_repeats=2,
            pandas_rows=40_000,
            duckdb_rows=60_000,
            parquet_rows=50_000,
            parallel_tasks=4,
            parallel_iterations_per_task=30_000,
        )
    return BenchmarkConfig(
        python_iterations=10_000_000,
        numpy_size=4_000_000,
        numpy_repeats=5,
        pandas_rows=1_500_000,
        duckdb_rows=3_000_000,
        parquet_rows=2_000_000,
        parallel_tasks=48,
        parallel_iterations_per_task=700_000,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _cpu_model() -> str:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                if str(value).strip():
                    return str(value).strip()
        except OSError:
            pass
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.lower().startswith("model name") and ":" in line:
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor().strip() or platform.machine()


def _python_kernel(iterations: int, seed: int = 320_832) -> int:
    x = seed & 0xFFFFFFFF
    acc = 0
    for i in range(iterations):
        x = (x * 1_664_525 + 1_013_904_223) & 0xFFFFFFFF
        acc = (acc + ((x ^ (x >> 16)) * ((i & 31) + 1))) & 0xFFFFFFFFFFFFFFFF
    return acc


def _run_python_scalar(config: BenchmarkConfig) -> int:
    return _python_kernel(config.python_iterations)


def _run_numpy_vector(config: BenchmarkConfig) -> float:
    import numpy as np

    values = np.arange(config.numpy_size, dtype=np.float64)
    values = (values % 100_003.0) * 0.00001
    checksum = 0.0
    for repeat in range(config.numpy_repeats):
        shifted = values + (repeat + 1) * 0.0001
        derived = np.sqrt(np.abs(np.sin(shifted) + np.cos(shifted * 0.37)) + 1.0)
        checksum += float(derived.sum(dtype=np.float64))
    return checksum


def _run_pandas_aggregation(config: BenchmarkConfig) -> float:
    import numpy as np
    import pandas as pd

    index = np.arange(config.pandas_rows, dtype=np.int64)
    frame = pd.DataFrame(
        {
            "grp": (index % 1024).astype(np.int32),
            "x": ((index * 17) % 100_003).astype(np.float64) / 100_003.0,
            "y": ((index * 31) % 65_521).astype(np.float64) / 65_521.0,
            "z": ((index * 43) % 32_749).astype(np.float64) / 32_749.0,
        }
    )
    grouped = frame.groupby("grp", sort=True, observed=True).agg(
        x_sum=("x", "sum"),
        y_mean=("y", "mean"),
        z_std=("z", "std"),
    )
    return float(grouped["x_sum"].sum() + grouped["y_mean"].sum() + grouped["z_std"].sum())


def _run_duckdb_analytics(config: BenchmarkConfig) -> float:
    import duckdb

    threads = max(1, os.cpu_count() or 1)
    with duckdb.connect(":memory:") as connection:
        connection.execute(f"PRAGMA threads={threads}")
        connection.execute(
            f"""
            CREATE TABLE bench AS
            SELECT
                i::BIGINT AS i,
                (i % 2048)::INTEGER AS grp,
                sin(i * 0.001)::DOUBLE AS x,
                cos(i * 0.0007)::DOUBLE AS y,
                ((i * 17) % 100003)::DOUBLE / 100003.0 AS z
            FROM range({config.duckdb_rows}) AS t(i)
            """
        )
        grouped = connection.execute(
            """
            SELECT grp, count(*) AS n, sum(x) AS sx, avg(y) AS ay, stddev_pop(z) AS sz
            FROM bench
            GROUP BY grp
            ORDER BY grp
            """
        ).fetchall()
        windowed = connection.execute(
            """
            SELECT sum(v)
            FROM (
                SELECT avg(x) OVER (
                    PARTITION BY grp ORDER BY i ROWS BETWEEN 15 PRECEDING AND CURRENT ROW
                ) AS v
                FROM bench
            )
            """
        ).fetchone()[0]
    grouped_checksum = sum(float(row[1]) + float(row[2]) + float(row[3]) + float(row[4]) for row in grouped)
    return grouped_checksum + float(windowed or 0.0)


def _run_parquet_roundtrip(config: BenchmarkConfig) -> float:
    import duckdb

    threads = max(1, os.cpu_count() or 1)
    with tempfile.TemporaryDirectory(prefix="atlas-hwbench-", dir=Path.cwd()) as directory:
        parquet_path = Path(directory) / "atlas_hardware_benchmark.parquet"
        parquet_sql_path = parquet_path.as_posix().replace("'", "''")
        with duckdb.connect(":memory:") as connection:
            connection.execute(f"PRAGMA threads={threads}")
            connection.execute(
                f"""
                COPY (
                    SELECT
                        i::BIGINT AS i,
                        (i % 4096)::INTEGER AS grp,
                        sin(i * 0.002)::DOUBLE AS x,
                        cos(i * 0.0013)::DOUBLE AS y
                    FROM range({config.parquet_rows}) AS t(i)
                ) TO '{parquet_sql_path}'
                (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)
                """
            )
            rows = connection.execute(
                f"""
                SELECT grp, count(*) AS n, sum(x) AS sx, avg(y) AS ay
                FROM read_parquet('{parquet_sql_path}')
                GROUP BY grp
                ORDER BY grp
                """
            ).fetchall()
        size = parquet_path.stat().st_size
    return float(size) + sum(float(row[1]) + float(row[2]) + float(row[3]) for row in rows)


def _parallel_task(arguments: tuple[int, int]) -> int:
    iterations, seed = arguments
    return _python_kernel(iterations, seed)


def _run_parallel_python(config: BenchmarkConfig) -> int:
    workers = max(1, min(os.cpu_count() or 1, 32))
    arguments = [
        (config.parallel_iterations_per_task, 320_832 + task * 7_919)
        for task in range(config.parallel_tasks)
    ]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_parallel_task, arguments, chunksize=1))
    checksum = 0
    for value in results:
        checksum ^= int(value)
    return checksum


def _timed_stage(name: str, fn: Callable[[], Any], *, started_at: float) -> dict[str, Any]:
    total_elapsed = time.perf_counter() - started_at
    print(f"[{total_elapsed:8.2f}s] {name}: starting", flush=True)
    stage_start = time.perf_counter()
    checksum = fn()
    seconds = time.perf_counter() - stage_start
    total_elapsed = time.perf_counter() - started_at
    print(f"[{total_elapsed:8.2f}s] {name}: {seconds:.3f}s", flush=True)
    return {"seconds": seconds, "checksum": str(checksum)}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _find_latest_compatible_result(*, script_sha256: str, smoke: bool) -> tuple[Path, dict[str, Any]] | None:
    if not RESULT_ROOT.exists():
        return None
    for path in sorted(RESULT_ROOT.glob("atlas_hardware_benchmark_*.json"), reverse=True):
        payload = _load_json(path)
        if payload is None:
            continue
        if payload.get("contract") != BENCHMARK_CONTRACT:
            continue
        if payload.get("script_sha256") != script_sha256:
            continue
        if bool(payload.get("smoke")) != smoke:
            continue
        return path, payload
    return None


def _comparison_rows(baseline: dict[str, Any], current: dict[str, Any]) -> list[tuple[str, float, float]]:
    rows: list[tuple[str, float, float]] = []
    baseline_stages = baseline.get("stages")
    current_stages = current.get("stages")
    if isinstance(baseline_stages, dict) and isinstance(current_stages, dict):
        for name in current_stages:
            before = baseline_stages.get(name)
            after = current_stages.get(name)
            if not isinstance(before, dict) or not isinstance(after, dict):
                continue
            before_seconds = float(before.get("seconds", 0.0))
            after_seconds = float(after.get("seconds", 0.0))
            if before_seconds > 0 and after_seconds > 0:
                rows.append((name, before_seconds, after_seconds))
    before_total = float(baseline.get("benchmark_seconds", 0.0))
    after_total = float(current.get("benchmark_seconds", 0.0))
    if before_total > 0 and after_total > 0:
        rows.append(("TOTAL", before_total, after_total))
    return rows


def _print_comparison(baseline_path: Path, baseline: dict[str, Any], current: dict[str, Any]) -> None:
    print()
    print("Automatic before/after comparison")
    print(f"Baseline: {baseline_path}")
    baseline_cpu = baseline.get("system", {}).get("cpu_model", "unknown") if isinstance(baseline.get("system"), dict) else "unknown"
    current_cpu = current.get("system", {}).get("cpu_model", "unknown") if isinstance(current.get("system"), dict) else "unknown"
    print(f"Baseline CPU: {baseline_cpu}")
    print(f"Current CPU:  {current_cpu}")
    print()
    print(f"{'Stage':28} {'Before':>10} {'After':>10} {'Speedup':>10} {'Time change':>12}")
    print("-" * 76)
    for name, before, after in _comparison_rows(baseline, current):
        speedup = before / after
        time_change = (1.0 - after / before) * 100.0
        print(f"{name:28} {before:9.3f}s {after:9.3f}s {speedup:9.2f}x {time_change:10.1f}%")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic local ATLAS hardware benchmark with automatic timing and before/after comparison."
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run a very small validation workload instead of the hardware-comparison workload.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        help="Compare this run with a specific prior benchmark JSON instead of automatic latest-compatible selection.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    script_path = Path(__file__).resolve()
    script_sha256 = _sha256_file(script_path)
    config = _config(args.smoke)
    cpu_model = _cpu_model()
    logical_threads = max(1, os.cpu_count() or 1)

    if args.baseline is not None:
        baseline_payload = _load_json(args.baseline)
        if baseline_payload is None:
            print(f"ERROR: baseline is not readable JSON: {args.baseline}")
            return 2
        if baseline_payload.get("contract") != BENCHMARK_CONTRACT:
            print("ERROR: baseline benchmark contract does not match this benchmark.")
            return 2
        if baseline_payload.get("script_sha256") != script_sha256:
            print("ERROR: baseline script SHA256 differs; refusing a non-identical before/after comparison.")
            return 2
        if bool(baseline_payload.get("smoke")) != bool(args.smoke):
            print("ERROR: baseline smoke/full mode differs from this run.")
            return 2
        baseline = (args.baseline, baseline_payload)
    else:
        baseline = _find_latest_compatible_result(script_sha256=script_sha256, smoke=args.smoke)

    print("ATLAS Hardware Benchmark")
    print(f"Contract: {BENCHMARK_CONTRACT}")
    print(f"Script SHA256: {script_sha256}")
    print(f"CPU: {cpu_model}")
    print(f"Logical CPU threads: {logical_threads}")
    print(f"Python: {platform.python_version()}")
    print(f"Mode: {'SMOKE' if args.smoke else 'FULL'}")
    print("Network/provider calls: NONE")
    print("Market data/outcomes: NONE")
    print("GPU benchmark: NONE")
    print("Close other heavy applications and do not run ATLAS workloads concurrently for a clean comparison.")
    print()

    benchmark_start = time.perf_counter()
    stages: dict[str, dict[str, Any]] = {}
    stages["python_scalar"] = _timed_stage(
        "Python scalar compute",
        lambda: _run_python_scalar(config),
        started_at=benchmark_start,
    )
    stages["numpy_vector"] = _timed_stage(
        "NumPy vector compute",
        lambda: _run_numpy_vector(config),
        started_at=benchmark_start,
    )
    stages["pandas_aggregation"] = _timed_stage(
        "Pandas aggregation",
        lambda: _run_pandas_aggregation(config),
        started_at=benchmark_start,
    )
    stages["duckdb_analytics"] = _timed_stage(
        "DuckDB analytics",
        lambda: _run_duckdb_analytics(config),
        started_at=benchmark_start,
    )
    stages["parquet_roundtrip"] = _timed_stage(
        "Parquet write/read",
        lambda: _run_parquet_roundtrip(config),
        started_at=benchmark_start,
    )
    stages["parallel_python"] = _timed_stage(
        "Parallel Python compute",
        lambda: _run_parallel_python(config),
        started_at=benchmark_start,
    )
    benchmark_seconds = time.perf_counter() - benchmark_start

    timestamp = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "contract": BENCHMARK_CONTRACT,
        "script_sha256": script_sha256,
        "timestamp_utc": timestamp.isoformat(),
        "git_commit": _git_head(),
        "smoke": bool(args.smoke),
        "system": {
            "cpu_model": cpu_model,
            "logical_cpu_threads": logical_threads,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        },
        "config": asdict(config),
        "stages": stages,
        "benchmark_seconds": benchmark_seconds,
    }

    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = "smoke" if args.smoke else "full"
    output_path = RESULT_ROOT / f"atlas_hardware_benchmark_{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{suffix}.json"
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print()
    print(f"Benchmark complete: {benchmark_seconds:.3f}s")
    print(f"Result saved: {output_path}")

    if baseline is None:
        print("No earlier compatible result found. This run is now the baseline.")
        print("After the CPU upgrade, run this exact command again and comparison will be automatic.")
    else:
        _print_comparison(baseline[0], baseline[1], payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
