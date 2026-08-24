from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UnknownRunStateError(ValueError):
    """Raised when persisted run state cannot be interpreted safely."""


class UnknownJobStateError(ValueError):
    """Raised when persisted job state cannot be interpreted safely."""


class RunState(str, Enum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class JobState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


RUN_TERMINAL_STATES = frozenset({RunState.SUCCEEDED, RunState.FAILED, RunState.BLOCKED})
JOB_TERMINAL_STATES = frozenset({JobState.SUCCEEDED, JobState.FAILED, JobState.BLOCKED})


def parse_run_state(value: object) -> RunState:
    try:
        return RunState(str(value))
    except (TypeError, ValueError) as exc:
        raise UnknownRunStateError(f"unknown persisted run state: {value!r}") from exc


def parse_job_state(value: object) -> JobState:
    try:
        return JobState(str(value))
    except (TypeError, ValueError) as exc:
        raise UnknownJobStateError(f"unknown persisted job state: {value!r}") from exc


@dataclass(frozen=True)
class StageStatus:
    stage_id: str
    state: JobState = JobState.PENDING
    attempts: int = 0
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.stage_id:
            raise ValueError("stage_id must not be empty")
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")
        if self.error_code is not None and (not self.error_code or len(self.error_code) > 128):
            raise ValueError("error_code must be 1..128 characters when present")

        if self.state is JobState.PENDING:
            if self.attempts != 0 or self.error_code is not None:
                raise ValueError("pending stage must have zero attempts and no error code")
        elif self.state is JobState.RUNNING:
            if self.attempts < 1 or self.error_code is not None:
                raise ValueError("running stage must have at least one attempt and no error code")
        elif self.state is JobState.SUCCEEDED:
            if self.attempts < 1 or self.error_code is not None:
                raise ValueError("successful stage must have at least one attempt and no error code")
        elif self.state is JobState.FAILED:
            if self.attempts < 1 or self.error_code is None:
                raise ValueError("failed stage must have at least one attempt and an error code")
        elif self.state is JobState.BLOCKED:
            if self.attempts != 0 or self.error_code is None:
                raise ValueError("blocked stage must have zero attempts and an error code")

    @property
    def terminal(self) -> bool:
        return self.state in JOB_TERMINAL_STATES

    def to_payload(self) -> dict[str, object]:
        return {
            "stage_id": self.stage_id,
            "state": self.state.value,
            "attempts": self.attempts,
            "error_code": self.error_code,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "StageStatus":
        stage_id = payload.get("stage_id")
        state = payload.get("state")
        attempts = payload.get("attempts")
        error_code = payload.get("error_code")
        if not isinstance(stage_id, str):
            raise ValueError("persisted stage_id must be a string")
        if not isinstance(state, str):
            raise ValueError("persisted stage state must be a string")
        if not isinstance(attempts, int) or isinstance(attempts, bool):
            raise ValueError("persisted stage attempts must be an integer")
        if error_code is not None and not isinstance(error_code, str):
            raise ValueError("persisted stage error_code must be a string or null")
        return cls(
            stage_id=stage_id,
            state=parse_job_state(state),
            attempts=attempts,
            error_code=error_code,
        )
