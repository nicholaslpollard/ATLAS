from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.backtesting.recurrent_successor_daily_exit_confirmation import (
    RecurrentSuccessorDailyExitConfirmationError,
    _source_2025_sweep_summary,
)
from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    AUTHORITY,
    CANDIDATE_EXIT_POLICIES,
    FORWARD_CONFIRMATION_WINDOW,
    RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT,
    SOURCE_2025_SWEEP_RUN_FINGERPRINT,
    TUNING_WINDOW,
    recurrent_successor_daily_exit_confirmation_manifest,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep_contract import (
    RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
)


def test_confirmation_contract_freezes_forward_window_and_two_candidates() -> None:
    manifest = recurrent_successor_daily_exit_confirmation_manifest()
    assert (
        manifest["fingerprint"]
        == RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT
    )
    assert TUNING_WINDOW[0].isoformat() == "2025-01-01"
    assert TUNING_WINDOW[1].isoformat() == "2025-12-31"
    assert FORWARD_CONFIRMATION_WINDOW[0].isoformat() == "2026-01-01"
    assert FORWARD_CONFIRMATION_WINDOW[1].isoformat() == "2026-04-30"
    assert CANDIDATE_EXIT_POLICIES == ((0.02, 0.05), (0.03, 0.05))
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False
    assert AUTHORITY["strategy_promotion"] is False


def _source_summary_path(project_root: Path) -> Path:
    return (
        project_root
        / "data"
        / "research"
        / "recurrent_successor_daily_exit_sweep"
        / RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT[:16]
        / SOURCE_2025_SWEEP_RUN_FINGERPRINT[:16]
        / "sweep_summary.json"
    )


def test_source_2025_sweep_binding_requires_exact_frozen_run(
    tmp_path: Path,
) -> None:
    summary_path = _source_summary_path(tmp_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": "COMPLETE_DAILY_EXIT_POLICY_SWEEP_DIAGNOSTIC",
        "contract_fingerprint": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
        "run_fingerprint": SOURCE_2025_SWEEP_RUN_FINGERPRINT,
        "report_fingerprint": "a" * 64,
        "scope": {
            "start_session": "2025-01-01",
            "end_session": "2025-12-31",
            "policy_ids": [],
        },
        "policy_results": [
            {"stop_fraction": 0.02, "target_fraction": 0.05},
            {"stop_fraction": 0.03, "target_fraction": 0.05},
        ],
    }
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    observed = _source_2025_sweep_summary(tmp_path)
    assert observed["run_fingerprint"] == SOURCE_2025_SWEEP_RUN_FINGERPRINT

    summary["run_fingerprint"] = "b" * 64
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(
        RecurrentSuccessorDailyExitConfirmationError,
        match="run fingerprint drifted",
    ):
        _source_2025_sweep_summary(tmp_path)


def test_source_2025_sweep_binding_requires_both_frozen_candidates(
    tmp_path: Path,
) -> None:
    summary_path = _source_summary_path(tmp_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": "COMPLETE_DAILY_EXIT_POLICY_SWEEP_DIAGNOSTIC",
        "contract_fingerprint": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
        "run_fingerprint": SOURCE_2025_SWEEP_RUN_FINGERPRINT,
        "report_fingerprint": "a" * 64,
        "scope": {
            "start_session": "2025-01-01",
            "end_session": "2025-12-31",
            "policy_ids": [],
        },
        "policy_results": [
            {"stop_fraction": 0.02, "target_fraction": 0.05},
        ],
    }
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(
        RecurrentSuccessorDailyExitConfirmationError,
        match="candidate rows are missing",
    ):
        _source_2025_sweep_summary(tmp_path)
