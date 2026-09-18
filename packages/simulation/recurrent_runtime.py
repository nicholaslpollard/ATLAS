from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Sequence, TypeVar

from packages.simulation.decision_record import SimulationDecisionRecord
from packages.simulation.market_mark_evidence import SimulatedMarketMarkEvidence
from packages.simulation.option_reservation import LongOptionReservationTerms
from packages.simulation.recurrent_engine import (
    RecurrentCoordinatorMarkPublicationV1,
    RecurrentCoordinatorMutationResultV1,
    RecurrentLifecycleCoordinatorSnapshotV1,
    RecurrentLifecycleCoordinatorV1,
)
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingTermsV1,
)
from packages.simulation.recurrent_exit_fill import RecurrentExitFillEvidenceV1
from packages.simulation.recurrent_persistence import (
    RecurrentLifecycleCheckpointV1,
    RecurrentLifecyclePersistenceError,
    read_recurrent_lifecycle_checkpoint,
    write_recurrent_lifecycle_checkpoint,
)
from packages.simulation.recurrent_runtime_contract import (
    RECURRENT_DURABLE_RUNTIME_CONTRACT,
    RECURRENT_DURABLE_RUNTIME_CONTRACT_FINGERPRINT,
)


RECURRENT_DURABLE_RUNTIME_CONTRACT_VERSION = str(
    RECURRENT_DURABLE_RUNTIME_CONTRACT["contract_id"]
)
_T = TypeVar("_T")


class RecurrentDurableRuntimeError(RuntimeError):
    pass


class RecurrentDurableRuntimeCommitError(RecurrentDurableRuntimeError):
    pass


class RecurrentDurableRuntimeUncertainError(
    RecurrentDurableRuntimeError
):
    pass


@dataclass(frozen=True)
class RecurrentDurableRuntimeStatusV1:
    contract_version: str
    contract_fingerprint: str
    checkpoint_path: str
    checkpoint_sha256: str
    revision: int
    snapshot_fingerprint: str
    uncertain: bool

    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != RECURRENT_DURABLE_RUNTIME_CONTRACT_VERSION:
            raise RecurrentDurableRuntimeError(
                "durable recurrent runtime contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_DURABLE_RUNTIME_CONTRACT_FINGERPRINT
        ):
            raise RecurrentDurableRuntimeError(
                "durable recurrent runtime contract fingerprint mismatch"
            )
        if self.revision < 0:
            raise RecurrentDurableRuntimeError(
                "durable recurrent runtime revision cannot be negative"
            )
        if not self.checkpoint_path:
            raise RecurrentDurableRuntimeError(
                "durable recurrent runtime checkpoint path cannot be blank"
            )
        for label, value in (
            ("checkpoint", self.checkpoint_sha256),
            ("snapshot", self.snapshot_fingerprint),
        ):
            if (
                len(value) != 64
                or any(ch not in "0123456789abcdef" for ch in value)
            ):
                raise RecurrentDurableRuntimeError(
                    f"durable recurrent runtime {label} fingerprint is invalid"
                )
        forbidden = (
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden):
            raise RecurrentDurableRuntimeError(
                "durable recurrent runtime cannot grant external/trading authority"
            )


class DurableRecurrentLifecycleRuntimeV1:
    """Crash-aware durable wrapper around the recurrent in-memory coordinator.

    The underlying coordinator remains deterministic and filesystem-I/O free. This
    wrapper serializes one mutation/mark operation at a time, then commits the exact
    resulting coordinator snapshot through the recurrent checkpoint contract.

    If persistence raises, durable state is read back and classified against the
    pre/post snapshots. A proven pre-state rolls memory back; a proven post-state is
    accepted; anything else locks the runtime into UNCERTAIN until an explicit reload
    from a valid checkpoint.
    """

    def __init__(
        self,
        *,
        checkpoint_path: Path,
        coordinator: RecurrentLifecycleCoordinatorV1,
        checkpoint: RecurrentLifecycleCheckpointV1,
    ) -> None:
        self._lock = RLock()
        self._checkpoint_path = Path(checkpoint_path)
        self._coordinator = coordinator
        self._checkpoint = checkpoint
        self._uncertain = False

        current = coordinator.snapshot()
        if current.snapshot_fingerprint != checkpoint.snapshot_fingerprint:
            raise RecurrentDurableRuntimeError(
                "coordinator/checkpoint snapshot mismatch at runtime initialization"
            )

    @classmethod
    def restore(
        cls,
        checkpoint_path: Path,
    ) -> "DurableRecurrentLifecycleRuntimeV1":
        checkpoint = read_recurrent_lifecycle_checkpoint(checkpoint_path)
        coordinator = RecurrentLifecycleCoordinatorV1.from_snapshot(
            checkpoint.snapshot
        )
        return cls(
            checkpoint_path=checkpoint_path,
            coordinator=coordinator,
            checkpoint=checkpoint,
        )

    @classmethod
    def bootstrap(
        cls,
        *,
        checkpoint_path: Path,
        coordinator: RecurrentLifecycleCoordinatorV1,
    ) -> "DurableRecurrentLifecycleRuntimeV1":
        path = Path(checkpoint_path)
        checkpoint = write_recurrent_lifecycle_checkpoint(
            path,
            coordinator.snapshot(),
        )
        return cls(
            checkpoint_path=path,
            coordinator=coordinator,
            checkpoint=checkpoint,
        )

    def _require_certain(self) -> None:
        if self._uncertain:
            raise RecurrentDurableRuntimeUncertainError(
                "durable recurrent runtime state is uncertain; explicit checkpoint reload required"
            )

    def status(self) -> RecurrentDurableRuntimeStatusV1:
        with self._lock:
            snapshot = self._coordinator.snapshot()
            return RecurrentDurableRuntimeStatusV1(
                contract_version=RECURRENT_DURABLE_RUNTIME_CONTRACT_VERSION,
                contract_fingerprint=(
                    RECURRENT_DURABLE_RUNTIME_CONTRACT_FINGERPRINT
                ),
                checkpoint_path=str(self._checkpoint_path),
                checkpoint_sha256=self._checkpoint.checkpoint_sha256,
                revision=snapshot.revision,
                snapshot_fingerprint=snapshot.snapshot_fingerprint,
                uncertain=self._uncertain,
            )

    @property
    def revision(self) -> int:
        with self._lock:
            self._require_certain()
            return self._coordinator.revision

    def snapshot(self) -> RecurrentLifecycleCoordinatorSnapshotV1:
        with self._lock:
            self._require_certain()
            return self._coordinator.snapshot()

    def current_account(self):
        with self._lock:
            self._require_certain()
            return self._coordinator.current_account()

    def current_marked_state(self):
        with self._lock:
            self._require_certain()
            return self._coordinator.current_marked_state()

    def current_dashboard_pair(self):
        with self._lock:
            self._require_certain()
            return self._coordinator.current_dashboard_pair()

    def reload_from_checkpoint(self) -> RecurrentLifecycleCheckpointV1:
        with self._lock:
            checkpoint = read_recurrent_lifecycle_checkpoint(
                self._checkpoint_path
            )
            coordinator = RecurrentLifecycleCoordinatorV1.from_snapshot(
                checkpoint.snapshot
            )
            self._coordinator = coordinator
            self._checkpoint = checkpoint
            self._uncertain = False
            return checkpoint

    def _resolve_failed_commit(
        self,
        *,
        before: RecurrentLifecycleCoordinatorSnapshotV1,
        after: RecurrentLifecycleCoordinatorSnapshotV1,
        cause: Exception,
    ) -> None:
        try:
            observed = read_recurrent_lifecycle_checkpoint(
                self._checkpoint_path
            )
        except Exception as read_exc:
            self._uncertain = True
            raise RecurrentDurableRuntimeUncertainError(
                "checkpoint commit failed and durable state cannot be classified"
            ) from read_exc

        observed_fp = observed.snapshot.snapshot_fingerprint
        if observed_fp == after.snapshot_fingerprint:
            self._checkpoint = observed
            return

        if observed_fp == before.snapshot_fingerprint:
            self._coordinator = RecurrentLifecycleCoordinatorV1.from_snapshot(
                before
            )
            self._checkpoint = observed
            raise RecurrentDurableRuntimeCommitError(
                "checkpoint commit failed; recurrent mutation was rolled back to durable pre-state"
            ) from cause

        self._uncertain = True
        raise RecurrentDurableRuntimeUncertainError(
            "checkpoint commit failed and durable state differs from both pre/post snapshots"
        ) from cause

    def _commit_after(
        self,
        *,
        before: RecurrentLifecycleCoordinatorSnapshotV1,
    ) -> None:
        after = self._coordinator.snapshot()
        if after.snapshot_fingerprint == before.snapshot_fingerprint:
            return

        expected = self._checkpoint.checkpoint_sha256
        try:
            checkpoint = write_recurrent_lifecycle_checkpoint(
                self._checkpoint_path,
                after,
                expected_previous_checkpoint_sha256=expected,
            )
        except Exception as exc:
            self._resolve_failed_commit(
                before=before,
                after=after,
                cause=exc,
            )
            return

        if checkpoint.snapshot.snapshot_fingerprint != after.snapshot_fingerprint:
            self._uncertain = True
            raise RecurrentDurableRuntimeUncertainError(
                "checkpoint commit returned a different recurrent snapshot"
            )
        self._checkpoint = checkpoint

    def _transact(self, operation: Callable[[], _T]) -> _T:
        with self._lock:
            self._require_certain()
            before = self._coordinator.snapshot()
            result = operation()
            self._commit_after(before=before)
            return result

    def apply_reservation(
        self,
        *,
        record: SimulationDecisionRecord,
        option_terms: LongOptionReservationTerms | None = None,
    ):
        return self._transact(
            lambda: self._coordinator.apply_reservation(
                record=record,
                option_terms=option_terms,
            )
        )

    def apply_reservation_batch(
        self,
        decisions: Sequence[
            tuple[
                SimulationDecisionRecord,
                LongOptionReservationTerms | None,
            ]
        ],
    ):
        return self._transact(
            lambda: self._coordinator.apply_reservation_batch(decisions)
        )

    def apply_entry(
        self,
        *,
        fill: RecurrentEntryFillEvidenceV1,
        funding: RecurrentFundingTermsV1,
    ):
        return self._transact(
            lambda: self._coordinator.apply_entry(
                fill=fill,
                funding=funding,
            )
        )

    def apply_entry_batch(
        self,
        entries: Sequence[
            tuple[
                RecurrentEntryFillEvidenceV1,
                RecurrentFundingTermsV1,
            ]
        ],
    ):
        return self._transact(
            lambda: self._coordinator.apply_entry_batch(entries)
        )

    def apply_close(
        self,
        *,
        fill: RecurrentExitFillEvidenceV1,
    ):
        return self._transact(
            lambda: self._coordinator.apply_close(fill=fill)
        )

    def apply_close_batch(
        self,
        fills: Sequence[RecurrentExitFillEvidenceV1],
    ):
        return self._transact(
            lambda: self._coordinator.apply_close_batch(fills)
        )

    def publish_marks(
        self,
        *,
        marks: Sequence[SimulatedMarketMarkEvidence],
        valuation_utc,
    ) -> RecurrentCoordinatorMarkPublicationV1:
        return self._transact(
            lambda: self._coordinator.publish_marks(
                marks=marks,
                valuation_utc=valuation_utc,
            )
        )


def restore_durable_recurrent_lifecycle_runtime(
    checkpoint_path: Path,
) -> DurableRecurrentLifecycleRuntimeV1:
    try:
        return DurableRecurrentLifecycleRuntimeV1.restore(checkpoint_path)
    except RecurrentLifecyclePersistenceError:
        raise
    except Exception as exc:
        raise RecurrentDurableRuntimeError(
            "durable recurrent runtime restore failed"
        ) from exc
