from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path


_TRANSIENT_WINDOWS_ERRORS = {5, 32, 33}


def unique_temp_path(final_path: Path) -> Path:
    """Return a unique temporary path beside *final_path*.

    Keeping the temporary file in the destination directory preserves same-volume
    atomic rename semantics. UUID suffixes avoid collisions between repeated writes
    from the same PID and between concurrent ATLAS processes.
    """

    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    return final_path.with_name(f"{final_path.name}.{os.getpid()}.{token}.tmp")


def _is_transient_replace_error(exc: OSError) -> bool:
    if isinstance(exc, PermissionError):
        return True
    return getattr(exc, "winerror", None) in _TRANSIENT_WINDOWS_ERRORS


def replace_with_retry(
    temp_path: Path,
    final_path: Path,
    *,
    max_attempts: int = 8,
    initial_delay_seconds: float = 0.05,
    max_delay_seconds: float = 0.5,
    sleeper: Callable[[float], None] = time.sleep,
    replace_func: Callable[[os.PathLike[str] | str, os.PathLike[str] | str], None] = os.replace,
) -> None:
    """Atomically promote a prepared file, tolerating transient Windows locks.

    Windows antivirus/indexing/backup software can briefly open a JSON file without
    delete sharing, causing ``os.replace`` to raise WinError 5/32 even though the
    filesystem is otherwise healthy. Retry only that narrow class of error, with a
    bounded exponential backoff. Other errors fail immediately.

    The destination is never removed first: either the old file or the new file is
    visible, preserving the atomic-write contract.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    temp_path = Path(temp_path)
    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    delay = max(0.0, initial_delay_seconds)

    for attempt in range(1, max_attempts + 1):
        try:
            replace_func(temp_path, final_path)
            return
        except OSError as exc:
            if not _is_transient_replace_error(exc) or attempt >= max_attempts:
                raise
            sleeper(delay)
            delay = min(max_delay_seconds, max(delay * 2.0, initial_delay_seconds))


def atomic_write_text(
    final_path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    fsync: bool = True,
) -> None:
    """Durably write text to a unique sibling temp file and atomically promote it."""

    final_path = Path(final_path)
    temp_path = unique_temp_path(final_path)
    try:
        with temp_path.open("w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        replace_with_retry(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
