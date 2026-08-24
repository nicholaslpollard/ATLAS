from __future__ import annotations

from dataclasses import dataclass

from .registry import StageAuthority, StageDefinition


@dataclass(frozen=True)
class RetryDecision:
    allowed: bool
    reason_code: str


def retry_decision(stage: StageDefinition, *, completed_attempts: int) -> RetryDecision:
    if completed_attempts < 0:
        raise ValueError("completed_attempts must be non-negative")
    if stage.authority is StageAuthority.EXTERNAL_MUTATION:
        return RetryDecision(False, "EXTERNAL_MUTATION_RETRY_FORBIDDEN")
    if stage.authority is StageAuthority.EXTERNAL_READ:
        return RetryDecision(False, "EXTERNAL_READ_OUTSIDE_PHASE20_AUTHORITY")
    if not stage.retry_safe_local:
        return RetryDecision(False, "STAGE_NOT_RETRY_SAFE")
    if completed_attempts >= stage.max_attempts:
        return RetryDecision(False, "MAX_ATTEMPTS_REACHED")
    return RetryDecision(True, "RETRY_SAFE_LOCAL_ATTEMPT_AVAILABLE")
