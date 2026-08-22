from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from typing import Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.schemas.control_plane_runtime import (
    CONTROL_PLANE_RUNTIME_CONTRACT_VERSION,
    ControlPlaneRuntimeState,
)


class ControlPlaneRuntimeStateError(RuntimeError):
    pass


class ControlPlaneRuntimeStateConflict(ControlPlaneRuntimeStateError):
    pass


class ControlPlaneRuntimeStateStore:
    """Revision-checked operational state store.

    Missing state is an in-memory unselected default and is never written implicitly.
    Persisted transitions must already be bound to an audit event hash; writes are atomic,
    fsynced, and compare the expected prior revision before promotion.
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
        self._lock = threading.RLock()

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
            raise ControlPlaneRuntimeStateError(
                "runtime state is unreadable or invalid JSON"
            ) from exc
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
            raise ControlPlaneRuntimeStateError(
                "runtime state contract validation failed"
            ) from exc

    def persist_transition(
        self,
        state: ControlPlaneRuntimeState,
        *,
        expected_prior_revision: int,
    ) -> ControlPlaneRuntimeState:
        with self._lock:
            current = self.load()
            if current.revision != expected_prior_revision:
                raise ControlPlaneRuntimeStateConflict(
                    f"runtime revision changed: expected {expected_prior_revision}, found {current.revision}"
                )
            if state.source != "persisted":
                raise ControlPlaneRuntimeStateError(
                    "runtime persistence requires a persisted-source state"
                )
            if state.revision != expected_prior_revision + 1:
                raise ControlPlaneRuntimeStateError(
                    "runtime transition revision must increment exactly once"
                )
            # The synthetic revision-zero state is deliberately ephemeral: its timestamp
            # records when the absence of persisted state was observed, not an operational
            # transition. It therefore cannot constrain the timestamp of the first real
            # persisted transition. Once a state has been persisted, timestamps are
            # monotonic across all subsequent revisions.
            if (
                current.source == "persisted"
                and state.updated_at_utc < current.updated_at_utc
            ):
                raise ControlPlaneRuntimeStateError(
                    "runtime transition timestamp cannot move backward"
                )
            if (
                state.last_transition_action_id is None
                or state.last_transition_audit_hash is None
            ):
                raise ControlPlaneRuntimeStateError(
                    "runtime transition must be bound to an action and audit hash"
                )
            payload = (
                json.dumps(
                    state.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            atomic_write_text(self.state_path, payload, fsync=True)
            reloaded = self.load()
            if reloaded != state:
                raise ControlPlaneRuntimeStateError(
                    "runtime state re-read differs after atomic persistence"
                )
            return reloaded
