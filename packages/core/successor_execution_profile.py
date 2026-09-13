from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from packages.core.execution_profile import GIB, detect_total_memory_bytes


@dataclass(frozen=True, slots=True)
class SuccessorResearchExecutionProfile:
    logical_cpus: int
    total_memory_bytes: int | None
    reserved_logical_cpus: int
    workers: int
    duckdb_threads_per_worker: int
    aggregate_worker_threads: int
    profile_source: str
    thermal_headroom_policy: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["total_memory_gib"] = (
            None if self.total_memory_bytes is None else round(self.total_memory_bytes / GIB, 2)
        )
        return payload


def _positive_env_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


def resolve_successor_research_execution_profile(
    *,
    logical_cpus: int | None = None,
    total_memory_bytes: int | None = None,
) -> SuccessorResearchExecutionProfile:
    """Resolve a bounded high-throughput profile for successor research groups.

    Successor workloads are expected to mix Python strategy logic with DuckDB scans,
    so independent single-threaded workers are preferred to nested DuckDB threading.
    Two logical CPUs are reserved on ordinary hosts. On 12-logical-CPU workstations,
    the automatic profile deliberately uses eight 1-thread workers rather than all
    ten usable logical CPUs because the B35 targeted replay empirically showed that
    10x1 reached thermal throttling while 8x1 sustained strong throughput without it.

    This is an execution-only policy. Worker/thread choices are excluded from all
    scientific fingerprints and may be changed only after exact-output equivalence.
    """

    logical = max(1, int(logical_cpus or os.cpu_count() or 1))
    memory = total_memory_bytes if total_memory_bytes is not None else detect_total_memory_bytes()
    reserve = 0 if logical <= 2 else 2
    usable = max(1, logical - reserve)

    threads_per_worker = 1
    # Keep thermal/OS headroom on desktop-class hosts. 8x1 is the measured sustained
    # reference on the ATLAS i7-8700K/24-GiB workstation, but lower-core machines scale down.
    workers = min(8, usable)

    if memory is not None:
        memory_gib = memory / GIB
        # Reserve 4 GiB for the OS/coordinator. Successor workers are budgeted at
        # roughly 2 GiB apiece until real benchmark evidence supports a denser cap.
        memory_workers = max(1, int(max(0.0, memory_gib - 4.0) // 2.0))
        workers = min(workers, memory_workers)

    requested_workers = _positive_env_int("ATLAS_SUCCESSOR_REPLAY_WORKERS")
    requested_threads = _positive_env_int("ATLAS_SUCCESSOR_DUCKDB_THREADS_PER_WORKER")
    source = "hardware_auto_thermal_headroom"
    if requested_workers is not None:
        workers = requested_workers
        source = "environment_override"
    if requested_threads is not None:
        threads_per_worker = requested_threads
        source = "environment_override"

    aggregate = workers * threads_per_worker
    if workers > usable:
        raise ValueError("ATLAS_SUCCESSOR_REPLAY_WORKERS exceeds the reserved-CPU envelope")
    if threads_per_worker > usable or aggregate > usable:
        raise ValueError("successor worker/thread overrides oversubscribe the reserved-CPU envelope")

    return SuccessorResearchExecutionProfile(
        logical_cpus=logical,
        total_memory_bytes=memory,
        reserved_logical_cpus=reserve,
        workers=workers,
        duckdb_threads_per_worker=threads_per_worker,
        aggregate_worker_threads=aggregate,
        profile_source=source,
        thermal_headroom_policy=(
            "prefer measured sustained throughput over peak throughput; reject profiles that thermally throttle"
        ),
    )
