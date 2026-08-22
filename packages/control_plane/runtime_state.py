from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from packages.core.settings import AtlasSettings
from packages.schemas.control_plane_runtime import (
    CONTROL_PLANE_RUNTIME_CONTRACT_VERSION,
    ControlPlaneRuntimeState,
)


class ControlPlaneRuntimeStateError(RuntimeError):
    pass


class ControlPlaneRuntimeStateStore:
    """Read the Phase 16 operational state without creating or mutating it.

    A missing state file means no explicit selection has ever been made and returns an
    in-memory synthetic default. Invalid/tampered state fails closed; it is never replaced
    with a default. Mutation methods are intentionally absent until the audited action
    ledger is implemented.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "control_plane" / "v1"
        self.state_path = self.root / "runtime_state.json"

    def load(self) -> ControlPlaneRuntimeState:
        if not self.state_path.exists():
            return ControlPlaneRuntimeState.synthetic_default(now_utc=self._clock())
        if not self.state_path.is_file():
            raise ControlPlaneRuntimeStateError(
                f"runtime state path is not a file: {self.state_path}"
            )
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ControlPlaneRuntimeStateError("runtime state is unreadable or invalid JSON") from exc
        if not isinstance(raw, dict):
            raise ControlPlaneRuntimeStateError("runtime state root must be a JSON object")
        if raw.get("contract_version") != CONTROL_PLANE_RUNTIME_CONTRACT_VERSION:
            raise ControlPlaneRuntimeStateError("runtime state contract version changed")
        if raw.get("source") != "persisted":
            raise ControlPlaneRuntimeStateError(
                "only explicitly persisted runtime state may exist on disk"
            )
        try:
            return ControlPlaneRuntimeState.model_validate(raw)
        except Exception as exc:
            raise ControlPlaneRuntimeStateError("runtime state contract validation failed") from exc
