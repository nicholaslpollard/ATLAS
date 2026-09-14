from __future__ import annotations

from packages.backtesting.successor_parallel import SuccessorParallelCoordinator
from packages.core.successor_execution_profile import SuccessorResearchExecutionProfile


def _profile() -> SuccessorResearchExecutionProfile:
    return SuccessorResearchExecutionProfile(
        logical_cpus=4,
        total_memory_bytes=8 * 1024**3,
        reserved_logical_cpus=1,
        workers=2,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=2,
        profile_source="test",
        thermal_headroom_policy="test",
    )


def test_console_progress_reports_counts_rate_and_eta(capsys) -> None:
    coordinator = SuccessorParallelCoordinator(execution_profile=_profile())
    coordinator._print_progress(
        {
            "state": "RUNNING",
            "groups_total": 546,
            "groups_completed": 27,
            "groups_reused": 2,
            "groups_new": 25,
            "groups_pending_not_submitted": 511,
            "active_group_tokens": ["a", "b", "c", "d", "e", "f", "g", "h"],
            "elapsed_seconds": 1800.0,
            "new_groups_per_hour": 50.0,
            "eta_seconds": 37368.0,
        }
    )
    output = capsys.readouterr().out
    assert "successor progress state=RUNNING 27/546 (4.9%)" in output
    assert "reused=2 new=25 active=8 queued=511" in output
    assert "rate=50.00/h" in output
    assert "eta=10h22m48s" in output


def test_default_progress_heartbeat_is_thirty_seconds() -> None:
    coordinator = SuccessorParallelCoordinator(execution_profile=_profile())
    assert coordinator.heartbeat_seconds == 30.0
