from __future__ import annotations

import hashlib
import heapq
from dataclasses import dataclass


class QueueError(ValueError):
    pass


class DuplicateIdempotencyKeyError(QueueError):
    pass


class DuplicateStageQueueError(QueueError):
    pass


def stage_idempotency_key(run_id: str, stage_id: str) -> str:
    if not run_id or not stage_id:
        raise ValueError("run_id and stage_id are required")
    digest = hashlib.sha256(f"phase20-stage-v1:{run_id}:{stage_id}".encode("utf-8")).hexdigest()
    return f"job-{digest[:24]}"


@dataclass(frozen=True)
class JobEnvelope:
    run_id: str
    stage_id: str
    topological_rank: int
    idempotency_key: str

    def __post_init__(self) -> None:
        if not self.run_id or not self.stage_id or not self.idempotency_key:
            raise QueueError("run_id, stage_id, and idempotency_key are required")
        if self.topological_rank < 0:
            raise QueueError("topological_rank must be non-negative")


class DeterministicJobQueue:
    """Single-run deterministic queue with permanent duplicate protection."""

    def __init__(self) -> None:
        self._heap: list[tuple[int, str, str, JobEnvelope]] = []
        self._seen_idempotency_keys: set[str] = set()
        self._seen_stage_ids: set[str] = set()
        self._queued_stage_ids: set[str] = set()

    def __len__(self) -> int:
        return len(self._heap)

    def contains_stage(self, stage_id: str) -> bool:
        return stage_id in self._queued_stage_ids

    def enqueue(self, envelope: JobEnvelope) -> None:
        if envelope.idempotency_key in self._seen_idempotency_keys:
            raise DuplicateIdempotencyKeyError(
                f"duplicate idempotency key: {envelope.idempotency_key}"
            )
        if envelope.stage_id in self._seen_stage_ids:
            raise DuplicateStageQueueError(
                f"stage already scheduled in this queue: {envelope.stage_id}"
            )
        self._seen_idempotency_keys.add(envelope.idempotency_key)
        self._seen_stage_ids.add(envelope.stage_id)
        self._queued_stage_ids.add(envelope.stage_id)
        heapq.heappush(
            self._heap,
            (
                envelope.topological_rank,
                envelope.stage_id,
                envelope.idempotency_key,
                envelope,
            ),
        )

    def pop(self) -> JobEnvelope:
        if not self._heap:
            raise QueueError("cannot pop from an empty queue")
        _, _, _, envelope = heapq.heappop(self._heap)
        self._queued_stage_ids.remove(envelope.stage_id)
        return envelope
