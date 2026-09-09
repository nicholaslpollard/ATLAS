from __future__ import annotations

import pytest

from packages.core.execution_profile import (
    GIB,
    resolve_parallel_research_execution_profile,
    resolve_research_execution_profile,
)


def test_8700k_24gib_profile_uses_eight_duckdb_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_RESEARCH_DUCKDB_THREADS", raising=False)
    profile = resolve_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=24 * GIB,
    )
    assert profile.logical_cpus == 12
    assert profile.reserved_logical_cpus == 2
    assert profile.duckdb_threads == 8
    assert profile.profile_source == "hardware_auto"


def test_lower_memory_profiles_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_RESEARCH_DUCKDB_THREADS", raising=False)
    assert resolve_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=6 * GIB,
    ).duckdb_threads == 2
    assert resolve_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=12 * GIB,
    ).duckdb_threads == 4


def test_environment_override_is_bounded_by_detected_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_RESEARCH_DUCKDB_THREADS", "6")
    profile = resolve_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=24 * GIB,
    )
    assert profile.duckdb_threads == 6
    assert profile.profile_source == "environment_override"

    monkeypatch.setenv("ATLAS_RESEARCH_DUCKDB_THREADS", "13")
    with pytest.raises(ValueError, match="between 1"):
        resolve_research_execution_profile(
            logical_cpus=12,
            total_memory_bytes=24 * GIB,
        )


def test_8700k_24gib_parallel_profile_uses_five_by_two(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_B35_REPLAY_WORKERS", raising=False)
    monkeypatch.delenv("ATLAS_B35_DUCKDB_THREADS_PER_WORKER", raising=False)
    profile = resolve_parallel_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=24 * GIB,
    )
    assert profile.logical_cpus == 12
    assert profile.reserved_logical_cpus == 2
    assert profile.replay_workers == 5
    assert profile.duckdb_threads_per_worker == 2
    assert profile.aggregate_worker_threads == 10
    assert profile.profile_source == "hardware_auto"


def test_parallel_profile_memory_caps_worker_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ATLAS_B35_REPLAY_WORKERS", raising=False)
    monkeypatch.delenv("ATLAS_B35_DUCKDB_THREADS_PER_WORKER", raising=False)
    assert resolve_parallel_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=12 * GIB,
    ).replay_workers == 2
    assert resolve_parallel_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=6 * GIB,
    ).replay_workers == 1


def test_parallel_profile_overrides_must_stay_inside_reserved_cpu_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ATLAS_B35_REPLAY_WORKERS", "4")
    monkeypatch.setenv("ATLAS_B35_DUCKDB_THREADS_PER_WORKER", "2")
    profile = resolve_parallel_research_execution_profile(
        logical_cpus=12,
        total_memory_bytes=24 * GIB,
    )
    assert profile.replay_workers == 4
    assert profile.duckdb_threads_per_worker == 2
    assert profile.aggregate_worker_threads == 8
    assert profile.profile_source == "environment_override"

    monkeypatch.setenv("ATLAS_B35_REPLAY_WORKERS", "6")
    with pytest.raises(ValueError, match="oversubscribe"):
        resolve_parallel_research_execution_profile(
            logical_cpus=12,
            total_memory_bytes=24 * GIB,
        )
