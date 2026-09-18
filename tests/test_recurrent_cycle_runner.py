from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from packages.simulation.recurrent_cycle import RecurrentCycleStatus
from packages.simulation.recurrent_cycle_runner import (
    RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT,
    RecurrentCycleRunnerError,
    RecurrentCycleRunnerV1,
    build_recurrent_cycle_run_identity_v1,
    read_recurrent_cycle_stage_admission,
    recurrent_cycle_stage_admission_path,
)
from packages.simulation.recurrent_genesis import bootstrap_recurrent_genesis_v1


def _fp(character: str) -> str:
    return character * 64


def _runtime(tmp_path):
    checkpoint = tmp_path / "current.json"
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
    )
    return checkpoint, runtime


def _identity():
    return build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
    )


def test_recurrent_cycle_runner_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_CYCLE_RUNNER_CONTRACT_FINGERPRINT
        == "2de1540cddf58f0c724efbbd25378800143de586c7d0f159fefa2e4af0ac5e0d"
    )


def test_cycle_identity_normalizes_equivalent_timezone_slots() -> None:
    utc_identity = _identity()
    eastern_identity = build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=datetime(
            2026,
            9,
            18,
            16,
            0,
            tzinfo=timezone(timedelta(hours=-4)),
        ),
    )
    assert eastern_identity == utc_identity
    assert utc_identity.cycle_id == (
        "four-hour-simulation@2026-09-18T20:00:00Z"
    )

    with pytest.raises(
        RecurrentCycleRunnerError,
        match="timezone-aware",
    ):
        build_recurrent_cycle_run_identity_v1(
            schedule_id="four-hour-simulation",
            scheduled_for_utc=datetime(2026, 9, 18, 20, 0),
        )


def test_empty_admitted_cycle_runs_without_account_mutation(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = _identity()

    _path, opened = runner.begin(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 5, 0, tzinfo=UTC),
    )
    assert opened.status == RecurrentCycleStatus.OPEN
    runner.apply_close(
        identity=identity,
        evidence_source_id="accepted-close-plan",
        evidence_source_fingerprint=_fp("a"),
        fills=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 1, tzinfo=UTC),
    )
    runner.apply_reserve(
        identity=identity,
        evidence_source_id="accepted-decision-plan",
        evidence_source_fingerprint=_fp("b"),
        decisions=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 2, tzinfo=UTC),
    )
    runner.apply_entry(
        identity=identity,
        evidence_source_id="accepted-entry-plan",
        evidence_source_fingerprint=_fp("c"),
        entries=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 3, tzinfo=UTC),
    )
    runner.apply_mark(
        identity=identity,
        evidence_source_id="accepted-mark-plan",
        evidence_source_fingerprint=_fp("d"),
        marks=(),
        valuation_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
        now_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
    )
    completed = runner.complete(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 5, 5, tzinfo=UTC),
    )

    assert completed.status == RecurrentCycleStatus.COMPLETE
    assert runtime.current_account().state.cash == pytest.approx(100_000.0)
    assert runtime.current_account().state.open_positions == ()
    assert runtime.current_marked_state() is not None
    assert runtime.current_marked_state().marked_positions == ()
    assert runtime.revision == 1

    close_admission = read_recurrent_cycle_stage_admission(
        recurrent_cycle_stage_admission_path(
            checkpoint,
            identity.cycle_id,
            completed.stages[0].stage,
        )
    )
    assert close_admission.evidence_count == 0
    assert close_admission.scheduler_trigger_authority is False
    assert close_admission.provider_read_authority is False
    assert close_admission.broker_write_authority is False
    assert close_admission.paper_authority is False
    assert close_admission.live_authority is False


def test_runner_restores_and_resumes_same_admitted_cycle(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    identity = _identity()
    first = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    first.begin(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 5, 0, tzinfo=UTC),
    )
    first.apply_close(
        identity=identity,
        evidence_source_id="accepted-close-plan",
        evidence_source_fingerprint=_fp("a"),
        fills=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 1, tzinfo=UTC),
    )

    restored = RecurrentCycleRunnerV1.restore(checkpoint)
    _path, reopened = restored.begin(identity=identity)
    assert len(reopened.stages) == 1
    replayed = restored.apply_close(
        identity=identity,
        evidence_source_id="accepted-close-plan",
        evidence_source_fingerprint=_fp("a"),
        fills=(),
    )
    assert replayed == reopened

    restored.apply_reserve(
        identity=identity,
        evidence_source_id="accepted-decision-plan",
        evidence_source_fingerprint=_fp("b"),
        decisions=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 2, tzinfo=UTC),
    )
    restored.apply_entry(
        identity=identity,
        evidence_source_id="accepted-entry-plan",
        evidence_source_fingerprint=_fp("c"),
        entries=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 3, tzinfo=UTC),
    )
    restored.apply_mark(
        identity=identity,
        evidence_source_id="accepted-mark-plan",
        evidence_source_fingerprint=_fp("d"),
        marks=(),
        valuation_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
        now_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
    )
    completed = restored.complete(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 5, 5, tzinfo=UTC),
    )
    assert completed.status == RecurrentCycleStatus.COMPLETE
    assert restored.runtime.revision == 1


def test_runner_rejects_conflicting_stage_admission(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = _identity()
    runner.begin(identity=identity)
    runner.apply_close(
        identity=identity,
        evidence_source_id="accepted-close-plan",
        evidence_source_fingerprint=_fp("a"),
        fills=(),
    )

    with pytest.raises(
        RecurrentCycleRunnerError,
        match="conflicting evidence",
    ):
        runner.apply_close(
            identity=identity,
            evidence_source_id="accepted-close-plan",
            evidence_source_fingerprint=_fp("b"),
            fills=(),
        )


def test_runner_stage_admission_tamper_fails_closed(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = _identity()
    runner.begin(identity=identity)
    receipt = runner.apply_close(
        identity=identity,
        evidence_source_id="accepted-close-plan",
        evidence_source_fingerprint=_fp("a"),
        fills=(),
    )
    admission_path = recurrent_cycle_stage_admission_path(
        checkpoint,
        identity.cycle_id,
        receipt.stages[0].stage,
    )
    raw = json.loads(admission_path.read_text(encoding="utf-8"))
    raw["evidence_source_id"] = "tampered-source"
    admission_path.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RecurrentCycleRunnerError,
        match="self-hash mismatch",
    ):
        read_recurrent_cycle_stage_admission(admission_path)
