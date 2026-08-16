from __future__ import annotations

import ctypes
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from packages.core.enums import LiveFreshness
from packages.providers.massive.websocket import MassiveWebSocketRuntimeStats
from packages.schemas.live_market import LiveStateSnapshot


def tree_size_bytes(root: Path) -> int:
    """Return total regular-file bytes below root; missing roots count as zero."""

    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def process_peak_rss_bytes() -> int | None:
    """Return peak resident/working-set bytes without adding a runtime dependency."""

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

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle,
                ctypes.byref(counters),
                counters.cb,
            )
            return int(counters.PeakWorkingSetSize) if ok else None

        import resource

        peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # macOS reports bytes; Linux/BSD commonly report KiB.
        return peak if sys.platform == "darwin" else peak * 1024
    except Exception:
        return None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def build_benchmark_summary(
    snapshot: LiveStateSnapshot,
    runtime_stats: MassiveWebSocketRuntimeStats,
    *,
    wall_seconds: float,
    process_cpu_seconds: float,
    peak_rss_bytes: int | None,
    journal_growth_bytes: int,
) -> dict[str, Any]:
    """Build a JSON-ready benchmark summary from a completed live-state run."""

    duration = max(0.0, float(wall_seconds))
    received_rate = snapshot.received_events / duration if duration > 0 else 0.0
    accepted_rate = snapshot.accepted_events / duration if duration > 0 else 0.0
    cpu_one_core_percent = process_cpu_seconds / duration * 100.0 if duration > 0 else 0.0

    freshness = Counter(
        state.minute_freshness.value
        for state in snapshot.symbols
        if state.minute is not None
    )
    for value in LiveFreshness:
        freshness.setdefault(value.value, 0)

    excess_lag_seconds: list[float] = []
    for state in snapshot.symbols:
        minute = state.minute
        if minute is None:
            continue
        excess_lag_seconds.append(
            (minute.received_at_utc - minute.bar_end_utc).total_seconds()
            - minute.expected_delay_seconds
        )

    queue_utilization = runtime_stats.peak_queue_utilization
    baseline_healthy = (
        snapshot.parse_errors == 0
        and snapshot.reconnects == 0
        and queue_utilization < 0.80
    )

    return {
        "generated_at_utc": snapshot.generated_at_utc.isoformat(),
        "feed_mode": snapshot.feed_mode.value,
        "expected_delay_seconds": snapshot.expected_delay_seconds,
        "subscriptions": list(snapshot.subscriptions),
        "session_segment": snapshot.session.session_segment.value,
        "wall_seconds": duration,
        "process_cpu_seconds": float(process_cpu_seconds),
        "cpu_one_core_percent": cpu_one_core_percent,
        "peak_rss_bytes": peak_rss_bytes,
        "frames_received": runtime_stats.frames_received,
        "processed_events": runtime_stats.processed_events,
        "received_events": snapshot.received_events,
        "accepted_events": snapshot.accepted_events,
        "received_events_per_second": received_rate,
        "accepted_events_per_second": accepted_rate,
        "ignored_out_of_order_events": snapshot.ignored_out_of_order_events,
        "parse_errors": snapshot.parse_errors,
        "reconnects": snapshot.reconnects,
        "symbol_count": snapshot.symbol_count,
        "restored_symbol_count": snapshot.restored_symbol_count,
        "observed_symbol_count": snapshot.observed_symbol_count,
        "peak_ingress_queue_depth": runtime_stats.peak_ingress_queue_depth,
        "ingress_queue_capacity": runtime_stats.ingress_queue_capacity,
        "peak_queue_utilization": queue_utilization,
        "minute_freshness_counts": dict(sorted(freshness.items())),
        "latest_minute_excess_lag_seconds": {
            "min": min(excess_lag_seconds) if excess_lag_seconds else None,
            "p50": _percentile(excess_lag_seconds, 0.50),
            "p95": _percentile(excess_lag_seconds, 0.95),
            "max": max(excess_lag_seconds) if excess_lag_seconds else None,
        },
        "journal_growth_bytes": max(0, int(journal_growth_bytes)),
        "baseline_healthy": baseline_healthy,
    }
