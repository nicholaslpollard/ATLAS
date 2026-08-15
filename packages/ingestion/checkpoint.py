from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from packages.schemas.ingestion import IngestionCheckpoint


class CheckpointStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, checkpoint_id: str) -> Path:
        return self.root / f"{checkpoint_id}.json"

    def load(self, checkpoint_id: str) -> IngestionCheckpoint | None:
        path = self._path(checkpoint_id)
        if not path.exists():
            return None
        return IngestionCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, checkpoint: IngestionCheckpoint) -> None:
        path = self._path(checkpoint.checkpoint_id)
        temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temp.write_text(checkpoint.model_dump_json(indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)

    def advance(
        self,
        checkpoint_id: str,
        *,
        stage: str,
        source_id: str | None,
        cursor: str | None,
        completed_units: int,
        total_units: int | None,
    ) -> IngestionCheckpoint:
        checkpoint = IngestionCheckpoint(
            checkpoint_id=checkpoint_id,
            stage=stage,
            source_id=source_id,
            cursor=cursor,
            completed_units=completed_units,
            total_units=total_units,
            updated_at_utc=datetime.now(timezone.utc),
        )
        self.save(checkpoint)
        return checkpoint
