from __future__ import annotations

import ctypes
import os
from dataclasses import asdict, dataclass


GIB = 1024**3


@dataclass(frozen=True, slots=True)
class ResearchExecutionProfile:
    logical_cpus: int
    total_memory_bytes: int | None
    reserved_logical_cpus: int
    duckdb_threads: int
    profile_source: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["total_memory_gib"] = (
            None
            if self.total_memory_bytes is None
            else round(self.total_memory_bytes / GIB, 2)
        )
        return payload


@dataclass(frozen=True, slots=True)
class ParallelResearchExecutionProfile:
    """Bounded process/thread budget for independent research replay groups.

    This profile is intentionally separate from ``ResearchExecutionProfile`` so
    parallel replay tuning cannot silently change established single-process jobs.
    """

    logical_cpus: int
    total_memory_bytes: int | None
    reserved_logical_cpus: int
    replay_workers: int
    duckdb_threads_per_worker: int
    aggregate_worker_threads: int
    profile_source: str

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["total_memory_gib"] = (
            None
            if self.total_memory_bytes is None
            else round(self.total_memory_bytes / GIB, 2)
        )
        return payload


def detect_total_memory_bytes() -> int | None:
    """Best-effort total physical memory using only the standard library."""

    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys)
        except (AttributeError, OSError):
            return None
        return None

    try:
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    if pages <= 0 or page_size <= 0:
        return None
    return pages * page_size


def resolve_research_execution_profile(
    *,
    logical_cpus: int | None = None,
    total_memory_bytes: int | None = None,
) -> ResearchExecutionProfile:
    """Resolve a conservative scan profile without oversubscribing the host.

    Research scans reserve two logical CPUs for Windows/GUI/other ATLAS services.
    DuckDB is capped at eight threads because this workload is also storage- and
    memory-bandwidth-sensitive. A low-memory host receives an additional cap.
    """

    logical = int(logical_cpus or os.cpu_count() or 1)
    logical = max(1, logical)
    memory = total_memory_bytes
    if memory is None:
        memory = detect_total_memory_bytes()

    reserve = 0 if logical <= 2 else 2
    usable = max(1, logical - reserve)
    duckdb_threads = min(8, usable)

    if memory is not None:
        memory_gib = memory / GIB
        if memory_gib < 8:
            duckdb_threads = min(duckdb_threads, 2)
        elif memory_gib < 16:
            duckdb_threads = min(duckdb_threads, 4)

    override = os.getenv("ATLAS_RESEARCH_DUCKDB_THREADS")
    source = "hardware_auto"
    if override:
        try:
            requested = int(override)
        except ValueError as exc:
            raise ValueError("ATLAS_RESEARCH_DUCKDB_THREADS must be an integer") from exc
        if requested < 1 or requested > logical:
            raise ValueError(
                "ATLAS_RESEARCH_DUCKDB_THREADS must be between 1 and the detected logical CPU count"
            )
        duckdb_threads = requested
        source = "environment_override"

    return ResearchExecutionProfile(
        logical_cpus=logical,
        total_memory_bytes=memory,
        reserved_logical_cpus=reserve,
        duckdb_threads=max(1, duckdb_threads),
        profile_source=source,
    )


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


def resolve_parallel_research_execution_profile(
    *,
    logical_cpus: int | None = None,
    total_memory_bytes: int | None = None,
) -> ParallelResearchExecutionProfile:
    """Resolve an aggressive-but-bounded budget for independent replay groups.

    The automatic profile reserves two logical CPUs on ordinary workstations for
    Windows/RDP and the parent coordinator. Workers default to two DuckDB threads
    each; this keeps independent groups parallel without allowing every DuckDB
    instance to oversubscribe the host. Memory also caps worker count, reserving
    roughly 4 GiB for the OS/coordinator and budgeting roughly 3 GiB per worker.

    The i7-8700K/24-GiB ATLAS workstation therefore resolves to five workers with
    two DuckDB threads each (10 active worker threads, 2 logical CPUs reserved).
    Environment overrides remain bounded by the same reserved-CPU envelope.
    """

    logical = int(logical_cpus or os.cpu_count() or 1)
    logical = max(1, logical)
    memory = total_memory_bytes
    if memory is None:
        memory = detect_total_memory_bytes()

    reserve = 0 if logical <= 2 else 2
    usable = max(1, logical - reserve)

    threads_per_worker = 2 if usable >= 4 else 1
    workers = max(1, min(5, usable // threads_per_worker))

    if memory is not None:
        # Reserve 4 GiB for Windows/RDP/coordinator where possible, then use a
        # conservative 3-GiB budget per worker. This is a concurrency cap, not a
        # DuckDB memory limit and therefore cannot change scientific semantics.
        memory_gib = memory / GIB
        memory_workers = max(1, int(max(0.0, memory_gib - 4.0) // 3.0))
        workers = min(workers, memory_workers)

    requested_workers = _positive_env_int("ATLAS_B35_REPLAY_WORKERS")
    requested_threads = _positive_env_int("ATLAS_B35_DUCKDB_THREADS_PER_WORKER")
    source = "hardware_auto"
    if requested_workers is not None:
        workers = requested_workers
        source = "environment_override"
    if requested_threads is not None:
        threads_per_worker = requested_threads
        source = "environment_override"

    aggregate = workers * threads_per_worker
    if workers > usable:
        raise ValueError(
            "ATLAS_B35_REPLAY_WORKERS exceeds the reserved-CPU replay envelope"
        )
    if threads_per_worker > usable or aggregate > usable:
        raise ValueError(
            "B35 replay worker/thread overrides oversubscribe the reserved-CPU replay envelope"
        )

    return ParallelResearchExecutionProfile(
        logical_cpus=logical,
        total_memory_bytes=memory,
        reserved_logical_cpus=reserve,
        replay_workers=workers,
        duckdb_threads_per_worker=threads_per_worker,
        aggregate_worker_threads=aggregate,
        profile_source=source,
    )
