from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from pathlib import Path


_TRANSIENT_WINDOWS_ERRORS = {5, 32, 33}
_TEMP_NAME_PREFIX_MAX = 24
# Keep sibling temporary files comfortably below the legacy Windows MAX_PATH limit.
# The final destination may be longer on long-path-enabled systems, but ATLAS must not
# make an otherwise valid destination fail merely because its atomic temp filename adds
# a PID/UUID suffix. 248 also leaves headroom for legacy directory/file APIs.
_WINDOWS_LEGACY_SAFE_PATH_CHARS = 248
_TEMP_TOKEN_MIN_CHARS = 12


def unique_temp_path(final_path: Path) -> Path:
    """Return a unique temporary path beside *final_path*.

    Keeping the temporary file in the destination directory preserves same-volume
    atomic rename semantics. The visible filename prefix is bounded against the
    *entire* sibling path so a deep but valid Windows destination does not cross the
    legacy MAX_PATH boundary merely because ATLAS adds a PID/UUID temp suffix. A full
    UUID is retained whenever it fits; only non-authoritative temp-name decoration is
    shortened when required.
    """

    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    pid = str(os.getpid())
    parent_chars = len(os.fspath(final_path.parent))
    name_budget = _WINDOWS_LEGACY_SAFE_PATH_CHARS - parent_chars - 1
    fixed_after_prefix = len(pid) + 6  # .<pid>.<token>.tmp, excluding token itself.

    prefix_budget = name_budget - fixed_after_prefix - len(token)
    prefix_len = min(_TEMP_NAME_PREFIX_MAX, len(final_path.name), max(1, prefix_budget))
    prefix = final_path.name[:prefix_len] or "t"
    candidate = final_path.with_name(f"{prefix}.{pid}.{token}.tmp")
    if len(os.fspath(candidate)) <= _WINDOWS_LEGACY_SAFE_PATH_CHARS:
        return candidate

    # Extremely deep parents may not leave room for the full UUID. Preserve at least
    # 48 bits of random entropy when a legacy-safe sibling can still be represented.
    token_budget = name_budget - fixed_after_prefix - 1
    if token_budget >= _TEMP_TOKEN_MIN_CHARS:
        short_token = token[: min(len(token), token_budget)]
        return final_path.with_name(f"{final_path.name[:1] or 't'}.{pid}.{short_token}.tmp")

    # If even the minimum unique sibling cannot fit under the legacy limit, return the
    # shortest practical sibling. Such a destination already requires Windows long-path
    # support; callers will receive the underlying filesystem error if it is unavailable.
    return final_path.with_name(
        f"{final_path.name[:1] or 't'}.{pid}.{token[:_TEMP_TOKEN_MIN_CHARS]}.tmp"
    )


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
    fsync: bool = False,
) -> None:
    """Write text to a unique sibling temp file and atomically promote it.

    ``fsync`` is opt-in because ATLAS manifests/checkpoints are reconstructible from
    source/canonical files and are updated very frequently during historical builds.
    Atomic visibility is required; forcing a physical flush on every metadata state
    transition is not.
    """

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
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            # Cleanup is secondary; never mask the write/promotion error that caused
            # this path. A later maintenance pass may remove a stale temp file.
            pass
        raise
