from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_hardware_benchmark_smoke_runs_end_to_end(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    script = repository_root / "scripts" / "benchmark_atlas_hardware.py"

    completed = subprocess.run(
        [sys.executable, str(script), "--smoke"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert "ATLAS Hardware Benchmark" in completed.stdout
    assert "Network/provider calls: NONE" in completed.stdout
    assert "Benchmark complete:" in completed.stdout
    assert "This run is now the baseline." in completed.stdout

    result_root = tmp_path / "data" / "derived" / "hardware_benchmarks"
    results = list(result_root.glob("atlas_hardware_benchmark_*_smoke.json"))
    assert len(results) == 1

    payload = json.loads(results[0].read_text(encoding="utf-8"))
    assert payload["contract"] == "atlas-hardware-benchmark-v1"
    assert payload["smoke"] is True
    assert payload["benchmark_seconds"] > 0
    assert set(payload["stages"]) == {
        "python_scalar",
        "numpy_vector",
        "pandas_aggregation",
        "duckdb_analytics",
        "parquet_roundtrip",
        "parallel_python",
    }
    assert all(float(stage["seconds"]) > 0 for stage in payload["stages"].values())
