from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    CANDIDATE_EXIT_POLICIES,
    RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT,
)
from packages.backtesting.recurrent_successor_daily_exit_regime_robustness import (
    RecurrentSuccessorDailyExitRegimeRobustnessError,
    _source_2026_confirmation_summary,
)
from packages.backtesting.recurrent_successor_daily_exit_regime_robustness_contract import (
    ANNUAL_REGIME_WINDOWS,
    AUTHORITY,
    RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT,
    SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT,
    recurrent_successor_daily_exit_regime_robustness_manifest,
)


def test_regime_robustness_contract_freezes_2018_2024_and_candidates() -> None:
    manifest = recurrent_successor_daily_exit_regime_robustness_manifest()
    assert (
        manifest["fingerprint"]
        == RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT
    )
    assert [item[0] for item in ANNUAL_REGIME_WINDOWS] == [
        "2018",
        "2019",
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
    ]
    assert CANDIDATE_EXIT_POLICIES == ((0.02, 0.05), (0.03, 0.05))
    assert AUTHORITY["retrospective_regime_robustness_only"] is True
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False


def _confirmation_summary_path(project_root: Path) -> Path:
    return (
        project_root
        / "data"
        / "research"
        / "recurrent_successor_daily_exit_confirmation"
        / RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT[:16]
        / SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT[:16]
        / "confirmation_summary.json"
    )


def _valid_summary() -> dict[str, object]:
    return {
        "status": "COMPLETE_FORWARD_DAILY_EXIT_CONFIRMATION_DIAGNOSTIC",
        "contract_fingerprint": (
            RECURRENT_SUCCESSOR_DAILY_EXIT_CONFIRMATION_CONTRACT_FINGERPRINT
        ),
        "run_fingerprint": SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT,
        "report_fingerprint": "a" * 64,
        "candidate_results": [
            {"stop_fraction": 0.02, "target_fraction": 0.05},
            {"stop_fraction": 0.03, "target_fraction": 0.05},
        ],
    }


def test_source_2026_confirmation_requires_exact_run_fingerprint(
    tmp_path: Path,
) -> None:
    path = _confirmation_summary_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = _valid_summary()
    path.write_text(json.dumps(summary), encoding="utf-8")

    observed = _source_2026_confirmation_summary(tmp_path)
    assert observed["run_fingerprint"] == SOURCE_2026_CONFIRMATION_RUN_FINGERPRINT

    summary["run_fingerprint"] = "b" * 64
    path.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(
        RecurrentSuccessorDailyExitRegimeRobustnessError,
        match="run fingerprint drifted",
    ):
        _source_2026_confirmation_summary(tmp_path)


def test_source_2026_confirmation_requires_both_candidate_rows(
    tmp_path: Path,
) -> None:
    path = _confirmation_summary_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = _valid_summary()
    summary["candidate_results"] = [
        {"stop_fraction": 0.02, "target_fraction": 0.05}
    ]
    path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(
        RecurrentSuccessorDailyExitRegimeRobustnessError,
        match="candidate rows are missing",
    ):
        _source_2026_confirmation_summary(tmp_path)
