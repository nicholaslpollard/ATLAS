from __future__ import annotations

import json

import pytest

from packages.backtesting.successor_worker_scaling import (
    candidate_profile,
    decide_worker_scaling,
    load_baseline_progress,
)
from packages.core.successor_execution_profile import SuccessorResearchExecutionProfile


def _base_profile() -> SuccessorResearchExecutionProfile:
    return SuccessorResearchExecutionProfile(
        logical_cpus=12,
        total_memory_bytes=24 * 1024**3,
        reserved_logical_cpus=2,
        workers=8,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=8,
        profile_source="test",
        thermal_headroom_policy="test",
    )


def test_nine_by_one_candidate_fits_twelve_logical_cpu_and_24_gib_envelope() -> None:
    profile = candidate_profile(_base_profile(), workers=9)
    assert profile.workers == 9
    assert profile.duckdb_threads_per_worker == 1
    assert profile.aggregate_worker_threads == 9


def test_candidate_rejects_reserved_cpu_oversubscription() -> None:
    with pytest.raises(ValueError, match="reserved CPU envelope"):
        candidate_profile(_base_profile(), workers=11)


def test_break_even_selects_candidate_only_when_savings_repay_benchmark() -> None:
    decision = decide_worker_scaling(
        baseline_workers=8,
        candidate_workers=9,
        baseline_groups_per_hour=29.0,
        candidate_groups_per_hour=33.0,
        benchmark_elapsed_seconds=1800.0,
        remaining_groups_after_benchmark=380,
    )
    assert decision.use_candidate is True
    assert decision.projected_gross_savings_seconds > decision.benchmark_elapsed_seconds
    assert decision.projected_net_savings_seconds > 0


def test_break_even_keeps_baseline_when_gain_does_not_repay_test() -> None:
    decision = decide_worker_scaling(
        baseline_workers=8,
        candidate_workers=9,
        baseline_groups_per_hour=29.0,
        candidate_groups_per_hour=30.0,
        benchmark_elapsed_seconds=1800.0,
        remaining_groups_after_benchmark=100,
    )
    assert decision.use_candidate is False
    assert "do not repay" in decision.reason


def test_break_even_rejects_sub_noise_improvement_even_if_long_run_could_repay() -> None:
    decision = decide_worker_scaling(
        baseline_workers=8,
        candidate_workers=9,
        baseline_groups_per_hour=29.0,
        candidate_groups_per_hour=29.5,
        benchmark_elapsed_seconds=60.0,
        remaining_groups_after_benchmark=1000,
        minimum_speedup_fraction=0.03,
    )
    assert decision.use_candidate is False
    assert "noise margin" in decision.reason


def test_load_baseline_progress_requires_sustained_nx1_measurement(tmp_path) -> None:
    path = tmp_path / "progress.json"
    path.write_text(
        json.dumps(
            {
                "state": "INTERRUPTED",
                "groups_total": 546,
                "groups_completed": 129,
                "groups_new": 7,
                "elapsed_seconds": 700.0,
                "new_groups_per_hour": 36.0,
                "execution_profile": {
                    "workers": 8,
                    "duckdb_threads_per_worker": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    baseline = load_baseline_progress(path)
    assert baseline.workers == 8
    assert baseline.groups_new == 7
    assert baseline.groups_per_hour == 36.0
    assert baseline.state == "INTERRUPTED"


def test_load_baseline_progress_rejects_short_measurement(tmp_path) -> None:
    path = tmp_path / "progress.json"
    path.write_text(
        json.dumps(
            {
                "state": "INTERRUPTED",
                "groups_total": 546,
                "groups_completed": 125,
                "groups_new": 3,
                "elapsed_seconds": 120.0,
                "new_groups_per_hour": 90.0,
                "execution_profile": {
                    "workers": 8,
                    "duckdb_threads_per_worker": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="at least 5"):
        load_baseline_progress(path)
