from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.control_plane.recurrent_cycle_health import (
    RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT,
    RecurrentCycleHealthService,
)
from packages.simulation.recurrent_cycle import (
    RecurrentCycleStage,
    apply_recurrent_cycle_close_stage,
    apply_recurrent_cycle_entry_stage,
    apply_recurrent_cycle_mark_stage,
    apply_recurrent_cycle_reserve_stage,
    begin_recurrent_cycle,
    complete_recurrent_cycle,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunnerV1,
    admit_recurrent_cycle_stage_v1,
    build_recurrent_cycle_run_identity_v1,
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


def _complete_runner_cycle(checkpoint, runtime):
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = _identity()
    runner.begin(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 5, 0, tzinfo=UTC),
    )
    runner.apply_close(
        identity=identity,
        evidence_source_id="close-source",
        evidence_source_fingerprint=_fp("a"),
        fills=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 1, tzinfo=UTC),
    )
    runner.apply_reserve(
        identity=identity,
        evidence_source_id="reserve-source",
        evidence_source_fingerprint=_fp("b"),
        decisions=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 2, tzinfo=UTC),
    )
    runner.apply_entry(
        identity=identity,
        evidence_source_id="entry-source",
        evidence_source_fingerprint=_fp("c"),
        entries=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 3, tzinfo=UTC),
    )
    runner.apply_mark(
        identity=identity,
        evidence_source_id="mark-source",
        evidence_source_fingerprint=_fp("d"),
        marks=(),
        valuation_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
        now_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
    )
    runner.complete(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 5, 5, tzinfo=UTC),
    )
    return identity


def test_recurrent_cycle_health_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_CYCLE_HEALTH_CONTRACT_FINGERPRINT
        == "6f46af10c4925a2f73a7d6ba08a49b0ae2a2285c66380029e98ef740b0a90e80"
    )


def test_health_reports_not_connected_and_ready_no_cycle(tmp_path) -> None:
    checkpoint = tmp_path / "current.json"
    service = RecurrentCycleHealthService(
        checkpoint,
        now_provider=lambda: datetime(2026, 9, 18, 21, 0, tzinfo=UTC),
    )
    missing = service.snapshot()
    assert missing["status"] == "NOT_CONNECTED"
    assert missing["authority"]["provider_reads"] == 0
    assert missing["authority"]["broker_writes"] == 0

    _checkpoint, _runtime_value = _runtime(tmp_path)
    ready = service.snapshot()
    assert ready["status"] == "READY_NO_CYCLE"
    assert ready["cycle_count"] == 0
    assert ready["current_checkpoint"] is not None


def test_health_validates_complete_admitted_cycle(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    identity = _complete_runner_cycle(checkpoint, runtime)
    service = RecurrentCycleHealthService(checkpoint)

    payload = service.snapshot()

    assert payload["status"] == "COMPLETE"
    assert payload["cycle_count"] == 1
    assert payload["legacy_unadmitted_stage_count"] == 0
    assert payload["latest_cycle"]["cycle_id"] == identity.cycle_id
    assert payload["latest_cycle"]["recorded_stage_count"] == 4
    assert payload["latest_cycle"]["next_stage"] is None
    assert {
        row["state"] for row in payload["latest_cycle"]["stages"]
    } == {"RECORDED_ADMITTED"}
    assert payload["authority"]["provider_reads"] == 0
    assert payload["authority"]["order_writes"] == 0
    assert payload["authority"]["paper_submits"] == 0
    assert payload["authority"]["live_writes"] == 0


def test_health_fails_closed_on_tampered_admission(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    identity = _complete_runner_cycle(checkpoint, runtime)
    path = recurrent_cycle_stage_admission_path(
        checkpoint,
        identity.cycle_id,
        RecurrentCycleStage.CLOSE,
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["evidence_source_id"] = "tampered"
    path.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    payload = RecurrentCycleHealthService(checkpoint).snapshot()

    assert payload["status"] == "INVALID"
    assert (
        "DURABLE_CYCLE_HEALTH_VALIDATION_FAILED"
        in payload["reason_codes"]
    )


def test_health_marks_pre_runner_cycle_as_legacy_unadmitted(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    path, _receipt = begin_recurrent_cycle(
        checkpoint_path=checkpoint,
        runtime=runtime,
        cycle_id="legacy-empty-cycle",
        now_utc=datetime(2026, 9, 18, 20, 5, 0, tzinfo=UTC),
    )
    apply_recurrent_cycle_close_stage(
        path=path,
        runtime=runtime,
        fills=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 1, tzinfo=UTC),
    )
    apply_recurrent_cycle_reserve_stage(
        path=path,
        runtime=runtime,
        decisions=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 2, tzinfo=UTC),
    )
    apply_recurrent_cycle_entry_stage(
        path=path,
        runtime=runtime,
        entries=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 3, tzinfo=UTC),
    )
    apply_recurrent_cycle_mark_stage(
        path=path,
        runtime=runtime,
        marks=(),
        valuation_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
        now_utc=datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC),
    )
    complete_recurrent_cycle(
        path=path,
        runtime=runtime,
        now_utc=datetime(2026, 9, 18, 20, 5, 5, tzinfo=UTC),
    )

    payload = RecurrentCycleHealthService(checkpoint).snapshot()

    assert payload["status"] == "COMPLETE_LEGACY_UNADMITTED"
    assert payload["legacy_unadmitted_stage_count"] == 4


def test_health_surfaces_admitted_post_commit_recovery_boundary(tmp_path) -> None:
    checkpoint, runtime = _runtime(tmp_path)
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = _identity()
    runner.begin(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 5, 0, tzinfo=UTC),
    )
    runner.apply_close(
        identity=identity,
        evidence_source_id="close-source",
        evidence_source_fingerprint=_fp("a"),
        fills=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 1, tzinfo=UTC),
    )
    runner.apply_reserve(
        identity=identity,
        evidence_source_id="reserve-source",
        evidence_source_fingerprint=_fp("b"),
        decisions=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 2, tzinfo=UTC),
    )
    receipt = runner.apply_entry(
        identity=identity,
        evidence_source_id="entry-source",
        evidence_source_fingerprint=_fp("c"),
        entries=(),
        now_utc=datetime(2026, 9, 18, 20, 5, 3, tzinfo=UTC),
    )
    valuation = datetime(2026, 9, 18, 20, 5, 4, tzinfo=UTC)
    admit_recurrent_cycle_stage_v1(
        checkpoint_path=checkpoint,
        receipt=receipt,
        stage=RecurrentCycleStage.MARK,
        evidence_source_id="mark-source",
        evidence_source_fingerprint=_fp("d"),
        evidence_fingerprint=_fp("e"),
        evidence_count=0,
        action_context=valuation.isoformat(),
        now_utc=valuation,
    )

    runtime.publish_marks(marks=(), valuation_utc=valuation)

    payload = RecurrentCycleHealthService(checkpoint).snapshot()

    assert payload["status"] == "RECOVERY_REQUIRED"
    assert payload["latest_cycle"]["next_stage"] == "MARK"
    mark = payload["latest_cycle"]["stages"][3]
    assert mark["state"] == "ADMITTED_PENDING"
    assert "RUNNER_RESUME_REQUIRED" in payload["reason_codes"]
