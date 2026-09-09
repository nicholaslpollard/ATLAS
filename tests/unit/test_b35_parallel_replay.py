from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import packages.backtesting.b35_parallel_replay as parallel
from packages.backtesting.b35_development_replay import (
    B35_DEVELOPMENT_REPLAY_CONTRACT,
    _receipt_id,
)
from packages.backtesting.b35_development_source import (
    B35DevelopmentSourcePlan,
    B35DevelopmentUnitBinding,
)
from packages.core.execution_profile import ParallelResearchExecutionProfile
from packages.strategies.b35_conditional_evidence_contract import (
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
)


def _unit(tmp_path: Path) -> B35DevelopmentUnitBinding:
    return B35DevelopmentUnitBinding(
        unit_id="a" * 64,
        year=2026,
        month=4,
        batch_index=0,
        window_start=date(2026, 4, 1),
        window_end_exclusive=date(2026, 5, 1),
        symbols=("TEST",),
        policy_sha256="b" * 64,
        universe_sha256="c" * 64,
        canonical_path=tmp_path / "canonical.parquet",
        canonical_sha256="d" * 64,
        checkpoint_path=tmp_path / "checkpoint.json",
    )


def _plan(unit: B35DevelopmentUnitBinding) -> B35DevelopmentSourcePlan:
    return B35DevelopmentSourcePlan(
        contract="source-contract",
        b35_preoutcome_fingerprint=B35_PREOUTCOME_FINGERPRINT,
        start_session=date(2026, 4, 1),
        end_session=date(2026, 4, 30),
        units=(unit,),
        native_plan_sha256="e" * 64,
        native_plan_file_sha256="f" * 64,
        source_fingerprint="1" * 64,
    )


def _profile() -> ParallelResearchExecutionProfile:
    return ParallelResearchExecutionProfile(
        logical_cpus=4,
        total_memory_bytes=None,
        reserved_logical_cpus=2,
        replay_workers=1,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=1,
        profile_source="test",
    )


def _empty_receipt(
    output_path: Path,
    unit: B35DevelopmentUnitBinding,
    *,
    group_fingerprint: str,
    source_fingerprint: str = "1" * 64,
    split_fingerprint: str = "2" * 64,
    authorization_id: str = "3" * 64,
) -> dict[str, object]:
    counters = {
        strategy_id: {"evaluated_fired": 0, "comparable": 0, "noncomparable": 0}
        for strategy_id in B34_STRATEGY_IDS
    }
    receipt: dict[str, object] = {
        "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,
        "status": "COMPLETE",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "source_fingerprint": source_fingerprint,
        "split_evidence_fingerprint": split_fingerprint,
        "authorization_id": authorization_id,
        "group_fingerprint": group_fingerprint,
        "symbols": ["TEST"],
        "unit_count": 1,
        "unit_bindings": [
            {
                "unit_id": unit.unit_id,
                "canonical_sha256": unit.canonical_sha256,
                "year": unit.year,
                "month": unit.month,
                "batch_index": unit.batch_index,
            }
        ],
        "record_count": 0,
        "strategy_counts": counters,
        "output_path": str(output_path),
        "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
    }
    receipt["receipt_id"] = _receipt_id(receipt)
    return receipt


def test_progress_payload_is_explicitly_non_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(parallel.monotonic_time, "monotonic", lambda: 7200.0)
    payload = parallel._build_progress_payload(
        state="RUNNING",
        started_at_utc="2026-09-09T00:00:00+00:00",
        started_monotonic=3600.0,
        profile=_profile(),
        groups_total=482,
        groups_completed=71,
        groups_reused_at_start=69,
        groups_computed_this_run=2,
        units_total=59768,
        units_completed=8804,
        units_reused_at_start=8556,
        units_computed_this_run=248,
        active_group_tokens=["abc"],
    )
    assert payload["contract"] == parallel.B35_PROGRESS_CONTRACT
    assert payload["status_authority"] == "NON_AUTHORITATIVE_OPERATIONAL"
    assert payload["scientific_completion_authority"] == "GROUP_RECEIPTS_AND_FINAL_SUMMARY_ONLY"
    assert payload["groups_total"] == 482
    assert payload["groups_completed"] == 71
    assert payload["units_per_hour_this_run"] == 248.0
    assert payload["eta_seconds"] is not None


def test_group_worker_empty_output_matches_legacy_receipt_contract(tmp_path: Path) -> None:
    unit = _unit(tmp_path)
    output = tmp_path / "group.jsonl"
    receipt_path = tmp_path / "group.receipt.json"
    group_fingerprint = "4" * 64

    class EmptySource:
        def load_unit(self, *_args, **_kwargs):
            return pd.DataFrame()

    parallel._WORKER_SOURCE = EmptySource()  # type: ignore[assignment]
    parallel._WORKER_SPLIT_EVIDENCE = SimpleNamespace(
        fingerprint="2" * 64,
        split_dates_by_symbol={},
    )
    task = parallel.B35GroupTask(
        group_fingerprint=group_fingerprint,
        units=(unit,),
        start_session=date(2026, 4, 1),
        end_session=date(2026, 4, 30),
        source_fingerprint="1" * 64,
        split_evidence_fingerprint="2" * 64,
        authorization_id="3" * 64,
        output_path=str(output),
        receipt_path=str(receipt_path),
    )
    receipt = parallel._run_group_task(task)
    assert output.read_bytes() == b""
    assert receipt["contract"] == B35_DEVELOPMENT_REPLAY_CONTRACT
    assert receipt["record_count"] == 0
    assert receipt["receipt_id"] == _receipt_id(receipt)
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["receipt_id"] == receipt["receipt_id"]


def test_parallel_engine_reuses_valid_receipt_without_recomputing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _unit(tmp_path)
    plan = _plan(unit)
    output_root = tmp_path / "run"
    groups_root = output_root / "groups"
    groups_root.mkdir(parents=True)
    group_fingerprint = "4" * 64
    token = group_fingerprint[:20]
    output = groups_root / f"{token}.jsonl"
    output.write_text("", encoding="utf-8")
    receipt = _empty_receipt(output, unit, group_fingerprint=group_fingerprint)
    (groups_root / f"{token}.receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    split = SimpleNamespace(
        contract="split-contract",
        fingerprint="2" * 64,
        corporate_actions_sha256="5" * 64,
        split_dates_by_symbol={},
    )
    monkeypatch.setattr(parallel, "validate_source_plan", lambda _plan: None)
    monkeypatch.setattr(parallel, "load_b35_split_evidence", lambda _layout: split)
    monkeypatch.setattr(
        parallel,
        "validate_development_authorization",
        lambda *_args, **_kwargs: "3" * 64,
    )
    monkeypatch.setattr(
        parallel,
        "ensure_read_start_marker",
        lambda *_args, **_kwargs: {"marker_id": "6" * 64},
    )
    monkeypatch.setattr(
        parallel,
        "_group_units",
        lambda *_args, **_kwargs: ((group_fingerprint, (unit,)),),
    )

    source = SimpleNamespace(
        layout=object(),
        settings=SimpleNamespace(project_root=tmp_path),
    )
    summary = parallel.B35ParallelDevelopmentReplayEngine(
        source,  # type: ignore[arg-type]
        execution_profile=_profile(),
        progress_interval_seconds=0.05,
    ).run(plan, output_root=output_root, authorization={})

    assert summary["group_count"] == 1
    assert summary["source_unit_count"] == 1
    assert summary["group_receipt_ids"] == [receipt["receipt_id"]]
    assert "workers" not in summary
    progress = json.loads((output_root / "progress.json").read_text(encoding="utf-8"))
    assert progress["state"] == "COMPLETE"
    assert progress["groups_reused_at_start"] == 1
    assert progress["groups_computed_this_run"] == 0
