from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from packages.core.execution_profile import GIB
from packages.core.successor_execution_profile import SuccessorResearchExecutionProfile


SUCCESSOR_WORKER_SCALING_BENCHMARK_CONTRACT = (
    "successor-worker-scaling-work-conserving-v1"
)


@dataclass(frozen=True, slots=True)
class BaselineProgress:
    workers: int
    duckdb_threads_per_worker: int
    groups_new: int
    groups_completed: int
    groups_total: int
    elapsed_seconds: float
    groups_per_hour: float
    state: str


@dataclass(frozen=True, slots=True)
class WorkerScalingDecision:
    baseline_workers: int
    candidate_workers: int
    baseline_groups_per_hour: float
    candidate_groups_per_hour: float
    benchmark_elapsed_seconds: float
    remaining_groups_after_benchmark: int
    minimum_speedup_fraction: float
    speedup_fraction: float
    baseline_remaining_seconds: float
    candidate_remaining_seconds: float
    projected_gross_savings_seconds: float
    projected_net_savings_seconds: float
    use_candidate: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def load_baseline_progress(
    progress_path: Path,
    *,
    minimum_new_groups: int = 5,
    minimum_elapsed_seconds: float = 300.0,
) -> BaselineProgress:
    payload = json.loads(progress_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("successor progress payload is not an object")
    profile = payload.get("execution_profile")
    if not isinstance(profile, dict):
        raise RuntimeError("successor progress has no execution profile")
    workers = int(profile.get("workers", 0))
    threads = int(profile.get("duckdb_threads_per_worker", 0))
    new_groups = int(payload.get("groups_new", 0))
    completed = int(payload.get("groups_completed", 0))
    total = int(payload.get("groups_total", 0))
    elapsed = float(payload.get("elapsed_seconds") or 0.0)
    rate = float(payload.get("new_groups_per_hour") or 0.0)
    state = str(payload.get("state") or "UNKNOWN")
    if workers < 1 or threads != 1:
        raise RuntimeError("baseline must be a positive Nx1 successor execution profile")
    if new_groups < minimum_new_groups:
        raise RuntimeError(
            f"baseline has only {new_groups} new groups; at least {minimum_new_groups} are required"
        )
    if elapsed < minimum_elapsed_seconds:
        raise RuntimeError(
            f"baseline elapsed {elapsed:.1f}s is below required {minimum_elapsed_seconds:.1f}s"
        )
    if rate <= 0:
        raise RuntimeError("baseline successor rate is unavailable")
    return BaselineProgress(
        workers=workers,
        duckdb_threads_per_worker=threads,
        groups_new=new_groups,
        groups_completed=completed,
        groups_total=total,
        elapsed_seconds=elapsed,
        groups_per_hour=rate,
        state=state,
    )


def candidate_profile(
    base: SuccessorResearchExecutionProfile,
    *,
    workers: int,
) -> SuccessorResearchExecutionProfile:
    if workers < 1:
        raise ValueError("candidate workers must be positive")
    usable = max(1, base.logical_cpus - base.reserved_logical_cpus)
    if workers > usable:
        raise ValueError(
            f"candidate {workers}x1 exceeds reserved CPU envelope of {usable} logical CPUs"
        )
    if base.total_memory_bytes is not None:
        memory_gib = base.total_memory_bytes / GIB
        memory_workers = max(1, int(max(0.0, memory_gib - 4.0) // 2.0))
        if workers > memory_workers:
            raise ValueError(
                f"candidate {workers}x1 exceeds conservative memory envelope of {memory_workers} workers"
            )
    return SuccessorResearchExecutionProfile(
        logical_cpus=base.logical_cpus,
        total_memory_bytes=base.total_memory_bytes,
        reserved_logical_cpus=base.reserved_logical_cpus,
        workers=workers,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=workers,
        profile_source="successor_worker_scaling_benchmark",
        thermal_headroom_policy=base.thermal_headroom_policy,
    )


def decide_worker_scaling(
    *,
    baseline_workers: int,
    candidate_workers: int,
    baseline_groups_per_hour: float,
    candidate_groups_per_hour: float,
    benchmark_elapsed_seconds: float,
    remaining_groups_after_benchmark: int,
    minimum_speedup_fraction: float = 0.03,
) -> WorkerScalingDecision:
    if baseline_groups_per_hour <= 0 or candidate_groups_per_hour <= 0:
        raise ValueError("benchmark rates must be positive")
    if benchmark_elapsed_seconds < 0:
        raise ValueError("benchmark elapsed time cannot be negative")
    if remaining_groups_after_benchmark < 0:
        raise ValueError("remaining groups cannot be negative")
    if minimum_speedup_fraction < 0:
        raise ValueError("minimum speedup fraction cannot be negative")

    speedup = candidate_groups_per_hour / baseline_groups_per_hour - 1.0
    baseline_remaining = remaining_groups_after_benchmark * 3600.0 / baseline_groups_per_hour
    candidate_remaining = remaining_groups_after_benchmark * 3600.0 / candidate_groups_per_hour
    gross_savings = baseline_remaining - candidate_remaining
    net_savings = gross_savings - benchmark_elapsed_seconds

    if speedup < minimum_speedup_fraction:
        use_candidate = False
        reason = "candidate speedup is below the minimum noise margin"
    elif gross_savings <= benchmark_elapsed_seconds:
        use_candidate = False
        reason = "projected remaining-run savings do not repay benchmark elapsed time"
    else:
        use_candidate = True
        reason = "projected remaining-run savings exceed benchmark elapsed time"

    return WorkerScalingDecision(
        baseline_workers=baseline_workers,
        candidate_workers=candidate_workers,
        baseline_groups_per_hour=baseline_groups_per_hour,
        candidate_groups_per_hour=candidate_groups_per_hour,
        benchmark_elapsed_seconds=benchmark_elapsed_seconds,
        remaining_groups_after_benchmark=remaining_groups_after_benchmark,
        minimum_speedup_fraction=minimum_speedup_fraction,
        speedup_fraction=speedup,
        baseline_remaining_seconds=baseline_remaining,
        candidate_remaining_seconds=candidate_remaining,
        projected_gross_savings_seconds=gross_savings,
        projected_net_savings_seconds=net_savings,
        use_candidate=use_candidate,
        reason=reason,
    )
