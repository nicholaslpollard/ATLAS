from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from packages.schemas.materialization import MaterializationRecord


class MaterializationManifestStore:
    """Atomic per-source materialization state.

    This mirrors the Phase 2 ingestion-store pattern. PostgreSQL can replace
    the backend later without changing the materializer contract.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, source_id: str) -> Path:
        if not source_id or any(c in source_id for c in ("/", "\\")):
            raise ValueError("Invalid source_id")
        return self.root / f"{source_id}.json"

    def get(self, source_id: str) -> MaterializationRecord | None:
        path = self._path(source_id)
        if not path.exists():
            return None
        return MaterializationRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def put(self, record: MaterializationRecord) -> None:
        path = self._path(record.source_id)
        temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        with self._lock:
            temp.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
            os.replace(temp, path)
