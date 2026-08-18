from __future__ import annotations

from typing import Any


def build_feature_benchmark_summary(
    *,
    timeframe: str,
    sessions: int,
    rows: int,
    symbols: int,
    source_bytes: int,
    output_memory_bytes: int,
    output_parquet_bytes: int,
    wall_seconds: float,
    process_cpu_seconds: float,
    peak_rss_bytes: int | None,
    registered_features: int,
) -> dict[str, Any]:
    duration = max(0.0, float(wall_seconds))
    rows_per_second = rows / duration if duration > 0 else 0.0
    cpu_one_core_percent = process_cpu_seconds / duration * 100.0 if duration > 0 else 0.0
    return {
        "timeframe": timeframe,
        "sessions": int(sessions),
        "rows": int(rows),
        "symbols": int(symbols),
        "registered_features": int(registered_features),
        "source_bytes": int(source_bytes),
        "output_memory_bytes": int(output_memory_bytes),
        "output_parquet_bytes": int(output_parquet_bytes),
        "output_parquet_bytes_per_row": (
            output_parquet_bytes / rows if rows > 0 else None
        ),
        "output_to_source_ratio": (
            output_parquet_bytes / source_bytes if source_bytes > 0 else None
        ),
        "wall_seconds": duration,
        "process_cpu_seconds": float(process_cpu_seconds),
        "cpu_one_core_percent": cpu_one_core_percent,
        "rows_per_second": rows_per_second,
        "peak_rss_bytes": peak_rss_bytes,
    }


def project_feature_storage(summary: dict[str, Any], *, target_sessions: int) -> dict[str, float | int | None]:
    sample_sessions = int(summary["sessions"])
    if sample_sessions <= 0 or target_sessions <= 0:
        raise ValueError("session counts must be positive")
    scale = target_sessions / sample_sessions
    return {
        "target_sessions": int(target_sessions),
        "projected_rows": int(round(int(summary["rows"]) * scale)),
        "projected_parquet_bytes": int(round(int(summary["output_parquet_bytes"]) * scale)),
        "projected_compute_seconds": float(summary["wall_seconds"]) * scale,
    }
