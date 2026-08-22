from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

import packages.core.atomic_io as atomic_io
import packages.ingestion.checkpoint as checkpoint_module
from packages.ingestion.checkpoint import CheckpointStore
from packages.schemas.ingestion import IngestionCheckpoint


def test_replace_with_retry_recovers_from_transient_permission_error(tmp_path: Path):
    source = tmp_path / "state.json.tmp"
    target = tmp_path / "state.json"
    source.write_text("new", encoding="utf-8")
    target.write_text("old", encoding="utf-8")

    calls = 0
    sleeps: list[float] = []

    def flaky_replace(src, dst):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise PermissionError(5, "temporarily locked", str(dst))
        Path(src).replace(dst)

    atomic_io.replace_with_retry(
        source,
        target,
        max_attempts=4,
        initial_delay_seconds=0.01,
        sleeper=sleeps.append,
        replace_func=flaky_replace,
    )

    assert calls == 3
    assert sleeps == [0.01, 0.02]
    assert target.read_text(encoding="utf-8") == "new"
    assert not source.exists()


def test_replace_with_retry_recovers_for_directory_promotion(tmp_path: Path):
    source = tmp_path / ".year=2019.building"
    target = tmp_path / "year=2019"
    source.mkdir()
    (source / "marker.txt").write_text("complete", encoding="utf-8")

    calls = 0
    sleeps: list[float] = []

    def flaky_replace(src, dst):
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise PermissionError(5, "temporarily locked", str(dst))
        Path(src).replace(dst)

    atomic_io.replace_with_retry(
        source,
        target,
        max_attempts=4,
        initial_delay_seconds=0.01,
        sleeper=sleeps.append,
        replace_func=flaky_replace,
    )

    assert calls == 3
    assert sleeps == [0.01, 0.02]
    assert target.is_dir()
    assert (target / "marker.txt").read_text(encoding="utf-8") == "complete"
    assert not source.exists()


def test_replace_with_retry_does_not_retry_unrelated_os_error(tmp_path: Path):
    source = tmp_path / "state.tmp"
    target = tmp_path / "state.json"
    source.write_text("new", encoding="utf-8")
    sleeps: list[float] = []

    def broken_replace(src, dst):
        raise OSError(28, "disk full")

    with pytest.raises(OSError):
        atomic_io.replace_with_retry(
            source,
            target,
            max_attempts=8,
            sleeper=sleeps.append,
            replace_func=broken_replace,
        )

    assert sleeps == []
    assert source.exists()


def test_atomic_write_text_cleans_unique_temp_after_final_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "state.json"
    target.write_text("old", encoding="utf-8")

    def always_locked(temp, final):
        raise PermissionError(5, "locked", str(final))

    monkeypatch.setattr(atomic_io, "replace_with_retry", always_locked)

    with pytest.raises(PermissionError):
        atomic_io.atomic_write_text(target, "new\n", fsync=False)

    assert target.read_text(encoding="utf-8") == "old"
    assert list(tmp_path.glob("state.json.*.tmp")) == []


def test_unique_temp_paths_do_not_collide_within_same_process(tmp_path: Path):
    target = tmp_path / "checkpoint.json"
    first = atomic_io.unique_temp_path(target)
    second = atomic_io.unique_temp_path(target)

    assert first != second
    assert first.parent == target.parent
    assert second.parent == target.parent


def test_unique_temp_path_bounds_long_content_addressed_filename(tmp_path: Path):
    target = tmp_path / ("a" * 64 + ".json.gz")
    temp = atomic_io.unique_temp_path(target)

    assert temp.parent == target.parent
    assert temp.name.startswith("a" * atomic_io._TEMP_NAME_PREFIX_MAX + ".")
    assert temp.name.endswith(".tmp")
    assert len(temp.name) < len(target.name) + 20


def test_persistently_locked_checkpoint_warns_once_then_disables_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls = 0

    def locked_write(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise PermissionError(5, "persistently locked")

    monkeypatch.setattr(checkpoint_module, "atomic_write_text", locked_write)
    store = CheckpointStore(tmp_path / "checkpoints")
    checkpoint = IngestionCheckpoint(
        checkpoint_id="history_test",
        stage="flat_file_sync",
        completed_units=10,
        total_units=100,
        updated_at_utc=datetime.now(UTC),
    )

    with pytest.warns(RuntimeWarning, match="advisory checkpoint"):
        first_saved = store.save(checkpoint)
    second_saved = store.save(checkpoint)

    assert first_saved is False
    assert second_saved is False
    assert calls == 1
