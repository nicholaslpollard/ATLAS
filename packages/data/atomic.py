from __future__ import annotations

from pathlib import Path

from packages.core.atomic_io import replace_with_retry, unique_temp_path


def atomic_target(final_path: Path) -> Path:
    """Return a unique same-directory temporary path for an atomic data write."""

    return unique_temp_path(Path(final_path))


def promote(temp_path: Path, final_path: Path) -> None:
    """Promote a completed data file without sacrificing atomic replacement."""

    temp_path = Path(temp_path)
    try:
        replace_with_retry(temp_path, Path(final_path))
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
