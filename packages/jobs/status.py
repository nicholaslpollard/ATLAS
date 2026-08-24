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
        if self.state is JobState.SUCCEEDED and self.error_code is not None:
            raise ValueError("successful stage cannot carry an error code")
        if self.error_code is not None and (not self.error_code or len(self.error_code) > 128):
            raise ValueError("error_code must be 1..128 characters when present")

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
        return cls(
            stage_id=str(payload.get("stage_id", "")),
            state=parse_job_state(payload.get("state")),
            attempts=int(payload.get("attempts", 0)),
            error_code=(
                None if payload.get("error_code") is None else str(payload.get("error_code"))
            ),
        )
