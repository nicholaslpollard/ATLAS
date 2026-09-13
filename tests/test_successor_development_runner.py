from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from packages.backtesting import successor_development_runner as runner
from packages.backtesting.successor_parallel import ResearchWorkUnit, publish_completed_group
from packages.core.successor_execution_profile import SuccessorResearchExecutionProfile


class _FakeUnit:
    def __init__(self, *, unit_id: str = "unit", sha: str = "a" * 64) -> None:
        self.unit_id = unit_id
        self.canonical_sha256 = sha
        self.symbols = ("SPY",)


class _FakeCalendar:
    def __init__(self, sessions: tuple[date, ...]) -> None:
        self._sessions = sessions

    def sessions_in_range(self, start: date, end: date) -> tuple[date, ...]:
        return tuple(item for item in self._sessions if start <= item <= end)

    def regular_open_close(self, session: date) -> tuple[datetime, datetime]:
        return (
            datetime(session.year, session.month, session.day, 14, 30, tzinfo=UTC),
            datetime(session.year, session.month, session.day, 21, 0, tzinfo=UTC),
        )


class _FakeMinuteSource:
    def __init__(self, frame: pd.DataFrame, sessions: tuple[date, ...]) -> None:
        self.frame = frame
        self.calendar = _FakeCalendar(sessions)

    def load_unit(self, binding, *, start_session: date, end_session: date) -> pd.DataFrame:
        assert binding.symbols == ("SPY",)
        assert start_session == runner.DEVELOPMENT_START
        assert end_session == runner.DEVELOPMENT_END
        return self.frame.copy()


def _spy_frame(sessions: tuple[date, ...]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, session in enumerate(sessions):
        close_time = datetime(session.year, session.month, session.day, 20, 59, tzinfo=UTC)
        rows.extend(
            [
                {
                    "symbol": "SPY",
                    "session_segment": "regular",
                    "session_date": session,
                    "timestamp_utc": close_time - timedelta(minutes=1),
                    "close": 500.0 + index,
                },
                {
                    "symbol": "SPY",
                    "session_segment": "regular",
                    "session_date": session,
                    "timestamp_utc": close_time,
                    "close": 501.0 + index,
                },
            ]
        )
    return pd.DataFrame(rows)


def test_scientific_input_fingerprint_binds_derived_hashes(tmp_path: Path) -> None:
    first = runner._input_unit(
        token="daily_00",
        kind="daily",
        scientific={
            "run_contract_fingerprint": "1" * 64,
            "materialized_parquet_sha256": "2" * 64,
            "benchmark_sha256": "3" * 64,
        },
        operational={"parquet_locator": "a", "benchmark_locator": "b"},
        input_root=tmp_path / "one",
    )
    second = runner._input_unit(
        token="daily_00",
        kind="daily",
        scientific={
            "run_contract_fingerprint": "1" * 64,
            "materialized_parquet_sha256": "4" * 64,
            "benchmark_sha256": "3" * 64,
        },
        operational={"parquet_locator": "a", "benchmark_locator": "b"},
        input_root=tmp_path / "two",
    )
    assert first.input_fingerprint != second.input_fingerprint


def test_corrupt_external_standalone_artifact_invalidates_restart_reuse(tmp_path: Path) -> None:
    unit = ResearchWorkUnit(token="daily_00", input_fingerprint="a" * 64)
    contract = "b" * 64
    artifact = tmp_path / "standalone" / "daily_00.jsonl"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    result = {
        "kind": "daily",
        "standalone_artifact_locator": "standalone/daily_00.jsonl",
        "standalone_artifact_sha256": runner._sha256_file(artifact),
        "standalone_record_count": 1,
        "policy_record_counts": {},
    }
    publish_completed_group(
        tmp_path,
        unit,
        result,
        scientific_contract_fingerprint=contract,
    )
    artifact.write_text('{"tampered":true}\n', encoding="utf-8")

    invalidated = runner.invalidate_corrupt_standalone_reuse(
        tmp_path,
        (unit,),
        scientific_contract_fingerprint=contract,
    )

    assert invalidated == 1
    assert not artifact.exists()
    assert not (tmp_path / "groups" / "daily_00" / "output.json").exists()
    assert not (tmp_path / "groups" / "daily_00" / "receipt.json").exists()


def test_authority_is_development_only_and_never_promotes() -> None:
    authority = runner.development_outcome_authority()
    assert authority["development_outcomes_permitted"] is True
    assert authority["consumed_master_rows_permitted"] == 0
    assert authority["future_blind_rows_permitted"] == 0
    assert authority["provider_calls_permitted"] == 0
    assert authority["broker_reads_permitted"] == 0
    assert authority["broker_writes_permitted"] == 0
    assert authority["paper_authority"] is False
    assert authority["live_authority"] is False
    assert authority["promotion_authority"] is False
    assert authority["conditioning_before_standalone_complete"] is False
    assert authority["confluence_before_standalone_complete"] is False


def test_benchmark_requires_identical_scientific_outputs_across_worker_shapes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    units = tuple(
        ResearchWorkUnit(token=token, input_fingerprint=(f"{index + 1:064x}"))
        for index, token in enumerate(
            (
                "daily_00",
                "daily_32",
                "minute_0000",
                "minute_0060",
                "minute_0120",
                "minute_0180",
                "minute_0240",
                "minute_0300",
                "minute_0360",
                "minute_0420",
            )
        )
    )
    inputs = SimpleNamespace(work_units=units)
    settings = SimpleNamespace(project_root=tmp_path)
    identity = SimpleNamespace(fingerprint="f" * 64)
    base = SuccessorResearchExecutionProfile(
        logical_cpus=12,
        total_memory_bytes=24 * 1024**3,
        reserved_logical_cpus=2,
        workers=8,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=8,
        profile_source="test",
        thermal_headroom_policy="test",
    )
    monkeypatch.setattr(runner, "resolve_successor_research_execution_profile", lambda: base)

    observed_workers: list[int] = []

    def fake_run(settings, *, identity, inputs, execution_profile, units, output_root):
        observed_workers.append(execution_profile.workers)
        return {
            "parallel_run": {"run_fingerprint": "1" * 64},
            "standalone": {
                "artifact_set_fingerprint": "2" * 64,
                "record_count": 123,
            },
        }

    monkeypatch.setattr(runner, "run_successor_development_standalone", fake_run)
    report = runner.run_successor_development_benchmark(
        settings,
        identity=identity,
        inputs=inputs,
    )

    assert report["status"] == "PASS_EXACT_EQUIVALENCE"
    assert observed_workers == [4, 6, 8]
    assert report["record_count"] == 123
    assert report["thermal_acceptance"] == "OPERATOR_CONFIRMATION_REQUIRED_BEFORE_LONG_RUN"


def test_benchmark_rejects_scientific_output_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tokens = (
        "daily_00",
        "daily_32",
        "minute_0000",
        "minute_0060",
        "minute_0120",
        "minute_0180",
        "minute_0240",
        "minute_0300",
        "minute_0360",
        "minute_0420",
    )
    units = tuple(
        ResearchWorkUnit(token=token, input_fingerprint=f"{index + 1:064x}")
        for index, token in enumerate(tokens)
    )
    inputs = SimpleNamespace(work_units=units)
    settings = SimpleNamespace(project_root=tmp_path)
    identity = SimpleNamespace(fingerprint="f" * 64)
    base = SuccessorResearchExecutionProfile(
        logical_cpus=12,
        total_memory_bytes=24 * 1024**3,
        reserved_logical_cpus=2,
        workers=8,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=8,
        profile_source="test",
        thermal_headroom_policy="test",
    )
    monkeypatch.setattr(runner, "resolve_successor_research_execution_profile", lambda: base)
    calls = 0

    def fake_run(settings, *, identity, inputs, execution_profile, units, output_root):
        nonlocal calls
        calls += 1
        return {
            "parallel_run": {"run_fingerprint": f"{calls:064x}"},
            "standalone": {
                "artifact_set_fingerprint": "2" * 64,
                "record_count": 123,
            },
        }

    monkeypatch.setattr(runner, "run_successor_development_standalone", fake_run)
    with pytest.raises(runner.SuccessorDevelopmentRunnerError, match="not scientifically equivalent"):
        runner.run_successor_development_benchmark(
            settings,
            identity=identity,
            inputs=inputs,
        )

def test_runner_parquet_io_uses_duckdb_without_pandas_optional_engines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("pandas optional Parquet engine must not be used")

    monkeypatch.setattr(pd, "read_parquet", blocked)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", blocked)
    path = tmp_path / "daily.parquet"
    frame = pd.DataFrame(
        [
            {
                "instrument_id": "B",
                "session_date": date(2020, 1, 3),
                "timestamp_utc": pd.Timestamp("2020-01-03T14:30:00Z"),
                "value": 2.0,
            },
            {
                "instrument_id": "A",
                "session_date": date(2020, 1, 2),
                "timestamp_utc": pd.Timestamp("2020-01-02T14:30:00Z"),
                "value": 1.0,
            },
        ]
    )

    sha256 = runner._write_parquet_atomic(path, frame)
    loaded = runner._read_parquet_frame(path)

    assert len(sha256) == 64
    assert loaded["instrument_id"].tolist() == ["A", "B"]
    assert loaded["value"].tolist() == [1.0, 2.0]

