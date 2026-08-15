from __future__ import annotations

import os
from pathlib import Path


def atomic_target(final_path: Path) -> Path:
    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    return final_path.with_name(final_path.name + f".{os.getpid()}.tmp")


def promote(temp_path: Path, final_path: Path) -> None:
    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, final_path)
