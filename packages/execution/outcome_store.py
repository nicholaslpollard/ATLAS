from __future__ import annotations

import hashlib
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.schemas.execution import ExecutionOutcome


class ExecutionOutcomeStoreError(RuntimeError):
    pass


class ExecutionOutcomeStore:
    """Immutable local evidence store for realized Phase 15 outcomes.

    Outcome files are content-addressed by the deterministic intent identity and cannot
    be overwritten with different evidence. They remain descriptive and are not a model
    registry, strategy-support registry, or threshold-tuning surface.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "execution" / "phase15" / "v1" / "outcomes"

    def path(self, outcome: ExecutionOutcome) -> Path:
        safe_intent = hashlib.sha256(outcome.intent_id.encode("utf-8")).hexdigest()[:24]
        return self.root / f"year={outcome.closed_at_utc.year:04d}" / safe_intent / "outcome.json"

    def write(self, outcome: ExecutionOutcome) -> tuple[Path, str]:
        path = self.path(outcome)
        payload = outcome.model_dump_json(indent=2) + "\n"
        if path.is_file():
            existing = path.read_text(encoding="utf-8")
            if existing != payload:
                raise ExecutionOutcomeStoreError(
                    "immutable execution outcome already exists with different evidence"
                )
            return path, sha256_file(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, payload)
        return path, sha256_file(path)
