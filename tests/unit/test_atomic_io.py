from __future__ import annotations

from pathlib import Path

import pytest

import packages.core.atomic_io as atomic_io


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
