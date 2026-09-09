from __future__ import annotations

import pytest

from packages.core.execution_profile import GIB, resolve_research_execution_profile


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
