from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .registry import StageAuthority, StageDefinition


_ERROR_CLASS_RE = re.compile(r"[^A-Za-z0-9_]")


class WorkerAuthorityError(RuntimeError):
    pass


@dataclass(frozen=True)
class StageExecutionContext:
    run_id: str
    logical_slot: str
    stage_id: str
    attempt: int
    idempotency_key: str


@dataclass(frozen=True)
class WorkerResult:
    succeeded: bool
    error_code: str | None = None


StageHandler = Callable[[StageExecutionContext], None]


def _sanitized_handler_error(exc: Exception) -> str:
    class_name = _ERROR_CLASS_RE.sub("_", type(exc).__name__)[:64] or "Exception"
    return f"STAGE_HANDLER_ERROR_{class_name}"


class LocalWorker:
    """Executes exactly one local stage attempt and never retries implicitly."""

    def __init__(self, handlers: Mapping[str, StageHandler]) -> None:
        self._handlers = dict(handlers)

    def execute(
        self,
        stage: StageDefinition,
        *,
        context: StageExecutionContext,
    ) -> WorkerResult:
        if stage.authority is not StageAuthority.LOCAL_ONLY:
            raise WorkerAuthorityError(
                f"Phase 20 worker cannot execute {stage.authority.value} stage"
            )
        if context.stage_id != stage.stage_id:
            raise ValueError("worker context stage_id does not match stage definition")
        handler = self._handlers.get(stage.stage_id)
        if handler is None:
            return WorkerResult(False, "STAGE_HANDLER_UNAVAILABLE")
        try:
            handler(context)
        except Exception as exc:  # sanitized boundary: exception message is never persisted
            return WorkerResult(False, _sanitized_handler_error(exc))
        return WorkerResult(True, None)
