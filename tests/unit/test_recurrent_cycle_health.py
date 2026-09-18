from __future__ import annotations

import json
from datetime import UTC, datetime

from packages.control_plane.recurrent_cycle_health import (
    RecurrentCycleHealthService,
)
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunnerV1,
    build_recurrent_cycle_run_identity_v1,
)
from packages.simulation.recurrent_genesis import (
    bootstrap_recurrent_genesis_v1,
)


def _settings(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _bootstrap(settings):
    checkpoint = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    runtime, _result = bootstrap_recurrent_genesis_v1(
        checkpoint_path=checkpoint,
        initial_equity=100_000.0,
        as_of_utc=datetime(2026, 9, 18, 20, 0, tzinfo=UTC),
    )
    return checkpoint, runtime


def test_cycle_health_reports_not_bootstrapped_without_synthesis(tmp_path) -> None:
    settings = _settings(tmp_path)
    payload = RecurrentCycleHealthService(
        settings,
        now_utc=lambda: datetime(
            2026, 9, 18, 20, 5, tzinfo=UTC
        ),
    ).snapshot()
    assert payload["status"] == "NOT_BOOTSTRAPPED"
    assert payload["runtime"] is None
    assert payload["latest_cycle"] is None
    assert payload["authority"]["read_only"] is True
    assert payload["authority"]["provider_reads"] == 0
    assert payload["current_evidence"]["available"] is False


def test_cycle_health_shows_open_cycle_and_admission_lineage(tmp_path) -> None:
    settings = _settings(tmp_path)
    checkpoint, runtime = _bootstrap(settings)
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=datetime(
            2026, 9, 18, 20, 0, tzinfo=UTC
        ),
    )
    runner.begin(
        identity=identity,
        now_utc=datetime(2026, 9, 18, 20, 1, tzinfo=UTC),
    )
    runner.apply_close(
        identity=identity,
        evidence_source_id="accepted-close-source",
        evidence_source_fingerprint="a" * 64,
        fills=(),
        now_utc=datetime(2026, 9, 18, 20, 1, 1, tzinfo=UTC),
    )

    payload = RecurrentCycleHealthService(
        settings,
        now_utc=lambda: datetime(
            2026, 9, 18, 20, 2, tzinfo=UTC
        ),
    ).snapshot()
    assert payload["status"] == "OPEN_CYCLE"
    assert payload["runtime"]["uncertain"] is False
    latest = payload["latest_cycle"]
    assert latest["cycle_id"] == identity.cycle_id
    assert latest["status"] == "OPEN"
    assert latest["completed_stages"] == ["CLOSE"]
    assert latest["next_stage"] == "RESERVE"
    admissions = {
        row["stage"]: row for row in latest["admissions"]
    }
    assert admissions["CLOSE"]["status"] == "ADMITTED"
    assert admissions["CLOSE"]["evidence_source_id"] == (
        "accepted-close-source"
    )
    assert admissions["RESERVE"]["status"] == "MISSING"


def test_cycle_health_degrades_on_tampered_cycle_receipt(tmp_path) -> None:
    settings = _settings(tmp_path)
    checkpoint, runtime = _bootstrap(settings)
    runner = RecurrentCycleRunnerV1(
        checkpoint_path=checkpoint,
        runtime=runtime,
    )
    identity = build_recurrent_cycle_run_identity_v1(
        schedule_id="four-hour-simulation",
        scheduled_for_utc=datetime(
            2026, 9, 18, 20, 0, tzinfo=UTC
        ),
    )
    receipt_path, _receipt = runner.begin(identity=identity)
    raw = json.loads(receipt_path.read_text(encoding="utf-8"))
    raw["current_revision"] += 1
    receipt_path.write_text(
        json.dumps(raw, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    payload = RecurrentCycleHealthService(
        settings,
        now_utc=lambda: datetime(
            2026, 9, 18, 20, 2, tzinfo=UTC
        ),
    ).snapshot()
    assert payload["status"] == "DEGRADED"
    assert payload["invalid_cycle_receipt_count"] == 1
    assert payload["latest_cycle"] is None
