from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

from packages.core.exceptions import ManifestError
from packages.schemas.ingestion import IngestionManifestRecord


class DirectoryManifestStore:
    """Atomic per-source manifest records.

    A directory of small JSON records is deliberately used during the local
    foundation phases. It avoids rewriting a giant manifest after every file
    and is naturally restartable. A PostgreSQL implementation can later satisfy
    the same interface without changing ingestion logic.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, source_id: str) -> Path:
        if not source_id or any(char in source_id for char in ("/", "\\")):
            raise ManifestError("Invalid source_id for manifest path")
        return self.root / f"{source_id}.json"

    def get(self, source_id: str) -> IngestionManifestRecord | None:
        path = self._path(source_id)
        if not path.exists():
            return None
        try:
            return IngestionManifestRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ManifestError(f"Could not read ingestion manifest record: {path.name}") from exc

    def put(self, record: IngestionManifestRecord) -> None:
        path = self._path(record.source_id)
        temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        payload = record.model_dump_json(indent=2)
        with self._lock:
            try:
                temp.write_text(payload + "\n", encoding="utf-8")
                os.replace(temp, path)
            except OSError as exc:
                temp.unlink(missing_ok=True)
                raise ManifestError(f"Could not write ingestion manifest record: {path.name}") from exc

    def list_records(self) -> list[IngestionManifestRecord]:
        records: list[IngestionManifestRecord] = []
        for path in sorted(self.root.glob("src_*.json")):
            try:
                records.append(IngestionManifestRecord.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception as exc:
                raise ManifestError(f"Could not read ingestion manifest record: {path.name}") from exc
        return records
