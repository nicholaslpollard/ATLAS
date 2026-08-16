from __future__ import annotations

import warnings
from datetime import datetime, timezone
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.schemas.ingestion import IngestionCheckpoint


class CheckpointStore:
    """Best-effort progress checkpoints.

    Checkpoints improve observability but are not the authoritative recovery state:
    ingestion/materialization manifests and committed data files are. A checkpoint
    that remains locked after atomic replace retries therefore emits one warning and
    disables further checkpoint writes for this store instance rather than aborting
    or repeatedly stalling a long historical build.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._writes_disabled = False

    def _path(self, checkpoint_id: str) -> Path:
        return self.root / f"{checkpoint_id}.json"

    def load(self, checkpoint_id: str) -> IngestionCheckpoint | None:
        path = self._path(checkpoint_id)
        if not path.exists():
            return None
        return IngestionCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, checkpoint: IngestionCheckpoint) -> bool:
        if self._writes_disabled:
            return False
        path = self._path(checkpoint.checkpoint_id)
        try:
            atomic_write_text(path, checkpoint.model_dump_json(indent=2) + "\n")
            return True
        except OSError as exc:
            self._writes_disabled = True
            warnings.warn(
                f"ATLAS could not update advisory checkpoint {path.name}: "
                f"{type(exc).__name__}: {exc}. Checkpoint writes are disabled for the remainder "
                "of this process; authoritative manifests/data remain usable.",
                RuntimeWarning,
                stacklevel=2,
            )
            return False

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
