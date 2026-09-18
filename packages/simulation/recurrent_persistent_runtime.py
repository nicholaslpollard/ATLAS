from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Sequence

from packages.simulation.decision_record import SimulationDecisionRecord
from packages.simulation.market_mark_evidence import SimulatedMarketMarkEvidence
from packages.simulation.option_reservation import LongOptionReservationTerms
from packages.simulation.recurrent_close_position import (
    RecurrentClosePositionBatchResultV1,
    RecurrentClosePositionTransitionV1,
)
from packages.simulation.recurrent_engine import (
    RecurrentCoordinatorMarkPublicationV1,
    RecurrentCoordinatorMutationResultV1,
    RecurrentLifecycleCoordinatorV1,
)
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingTermsV1,
)
from packages.simulation.recurrent_exit_fill import RecurrentExitFillEvidenceV1
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
)
from packages.simulation.recurrent_marked_state import RecurrentMarkedAccountStateV1
from packages.simulation.recurrent_persistent_runtime_contract import (
    PERSISTENT_RECURRENT_RUNTIME_CONTRACT,
    PERSISTENT_RECURRENT_RUNTIME_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_positions import (
    RecurrentPositionBatchResultV1,
    RecurrentPositionTransitionV1,
)
from packages.simulation.recurrent_reservations import (
    RecurrentReservationBatchResultV1,
    RecurrentReservationTransitionV1,
)
from packages.simulation.recurrent_runtime_store import (
    RecurrentRuntimeAccountStoreV1,
    RecurrentRuntimeSnapshotV1,
)


PERSISTENT_RECURRENT_RUNTIME_CONTRACT_VERSION = str(
    PERSISTENT_RECURRENT_RUNTIME_CONTRACT["contract_id"]
)


class PersistentRecurrentRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistentRecurrentRuntimeStatusV1:
    contract_version: str
    contract_fingerprint: str
    account_state_fingerprint: str
    account_ledger_fingerprint: str
    ledger_event_count: int
    coordinator_revision: int
    marks_current: bool
    durable: bool

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
        if (
            self.contract_version
            != PERSISTENT_RECURRENT_RUNTIME_CONTRACT_VERSION
        ):
            raise PersistentRecurrentRuntimeError(
                "persistent recurrent runtime contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != PERSISTENT_RECURRENT_RUNTIME_CONTRACT_FINGERPRINT
        ):
            raise PersistentRecurrentRuntimeError(
                "persistent recurrent runtime contract fingerprint mismatch"
            )
        if self.ledger_event_count < 0 or self.coordinator_revision < 0:
            raise PersistentRecurrentRuntimeError(
                "persistent recurrent runtime revisions cannot be negative"
            )
        if not self.durable:
            raise PersistentRecurrentRuntimeError(
                "persistent recurrent runtime status must represent durable account state"
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
            raise PersistentRecurrentRuntimeError(
                "persistent recurrent runtime cannot grant external/trading authority"
            )


class PersistentRecurrentLifecycleRuntimeV1:
    """Durable wrapper around the accepted recurrent coordinator.

    Account mutations are not reported as successful until the exact resulting
    recurrent account has passed compare-and-swap persistence and post-write reread.
    Marks remain transient current-market evidence and are intentionally not persisted.
    """

    def __init__(
        self,
        *,
        store: RecurrentRuntimeAccountStoreV1,
        account: RecurrentLifecycleAccountV1,
    ) -> None:
        self._lock = RLock()
        self._store = store
        self._coordinator = RecurrentLifecycleCoordinatorV1(account=account)

    @classmethod
    def restore(
        cls,
        *,
        store: RecurrentRuntimeAccountStoreV1,
    ) -> "PersistentRecurrentLifecycleRuntimeV1 | None":
        snapshot = store.load()
        if snapshot is None:
            return None
        return cls(store=store, account=snapshot.account)

    @classmethod
    def bootstrap(
        cls,
        *,
        store: RecurrentRuntimeAccountStoreV1,
        account: RecurrentLifecycleAccountV1,
    ) -> "PersistentRecurrentLifecycleRuntimeV1":
        # Coordinator construction validates the exact recurrent account before the
        # first durable write. No equity/account defaults are inferred here.
        RecurrentLifecycleCoordinatorV1(account=account)
        store.persist(
            account,
            expected_prior_state_fingerprint=None,
        )
        return cls(store=store, account=account)

    @property
    def revision(self) -> int:
        with self._lock:
            return self._coordinator.revision

    def current_account(self) -> RecurrentLifecycleAccountV1:
        with self._lock:
            return self._coordinator.current_account()

    def current_marked_state(self) -> RecurrentMarkedAccountStateV1 | None:
        with self._lock:
            return self._coordinator.current_marked_state()

    def current_dashboard_pair(
        self,
    ) -> tuple[
        RecurrentLifecycleAccountV1,
        RecurrentMarkedAccountStateV1,
    ] | None:
        with self._lock:
            return self._coordinator.current_dashboard_pair()

    def durable_snapshot(self) -> RecurrentRuntimeSnapshotV1:
        with self._lock:
            snapshot = self._store.load()
            if snapshot is None:
                raise PersistentRecurrentRuntimeError(
                    "persistent recurrent runtime lost its durable snapshot"
                )
            current = self._coordinator.current_account()
            if snapshot.state_fingerprint != current.state.state_fingerprint:
                raise PersistentRecurrentRuntimeError(
                    "durable recurrent snapshot does not match current runtime account"
                )
            if snapshot.ledger_fingerprint != current.ledger.ledger_fingerprint:
                raise PersistentRecurrentRuntimeError(
                    "durable recurrent ledger does not match current runtime account"
                )
            return snapshot

    def status(self) -> PersistentRecurrentRuntimeStatusV1:
        with self._lock:
            snapshot = self.durable_snapshot()
            account = self._coordinator.current_account()
            return PersistentRecurrentRuntimeStatusV1(
                contract_version=PERSISTENT_RECURRENT_RUNTIME_CONTRACT_VERSION,
                contract_fingerprint=(
                    PERSISTENT_RECURRENT_RUNTIME_CONTRACT_FINGERPRINT
                ),
                account_state_fingerprint=account.state.state_fingerprint,
                account_ledger_fingerprint=account.ledger.ledger_fingerprint,
                ledger_event_count=len(account.ledger.events),
                coordinator_revision=self._coordinator.revision,
                marks_current=(
                    self._coordinator.current_marked_state() is not None
                ),
                durable=(
                    snapshot.state_fingerprint
                    == account.state.state_fingerprint
                    and snapshot.ledger_fingerprint
                    == account.ledger.ledger_fingerprint
                ),
            )

    def _persist_mutation(
        self,
        *,
        before: RecurrentLifecycleAccountV1,
        mutation: RecurrentCoordinatorMutationResultV1,
    ) -> None:
        after = mutation.account
        if mutation.new_ledger_event_count == 0:
            if after != before:
                raise PersistentRecurrentRuntimeError(
                    "zero-event recurrent runtime mutation changed account state"
                )
            return

        try:
            persisted = self._store.persist(
                after,
                expected_prior_state_fingerprint=(
                    before.state.state_fingerprint
                ),
            )
        except Exception as exc:
            # The coordinator had already applied the pure in-memory transition.
            # Restore the prior durable account and intentionally discard valuation.
            self._coordinator = RecurrentLifecycleCoordinatorV1(
                account=before
            )
            raise PersistentRecurrentRuntimeError(
                "recurrent mutation persistence failed; in-memory account rolled back"
            ) from exc

        if (
            persisted.state_fingerprint
            != after.state.state_fingerprint
            or persisted.ledger_fingerprint
            != after.ledger.ledger_fingerprint
        ):
            self._coordinator = RecurrentLifecycleCoordinatorV1(
                account=before
            )
            raise PersistentRecurrentRuntimeError(
                "persisted recurrent account differs from accepted mutation"
            )

    def apply_reservation(
        self,
        *,
        record: SimulationDecisionRecord,
        option_terms: LongOptionReservationTerms | None = None,
    ) -> tuple[
        RecurrentReservationTransitionV1,
        RecurrentCoordinatorMutationResultV1,
    ]:
        with self._lock:
            before = self._coordinator.current_account()
            transition, mutation = self._coordinator.apply_reservation(
                record=record,
                option_terms=option_terms,
            )
            self._persist_mutation(before=before, mutation=mutation)
            return transition, mutation

    def apply_reservation_batch(
        self,
        decisions: Sequence[
            tuple[
                SimulationDecisionRecord,
                LongOptionReservationTerms | None,
            ]
        ],
    ) -> tuple[
        RecurrentReservationBatchResultV1,
        RecurrentCoordinatorMutationResultV1,
    ]:
        with self._lock:
            before = self._coordinator.current_account()
            result, mutation = self._coordinator.apply_reservation_batch(
                decisions
            )
            self._persist_mutation(before=before, mutation=mutation)
            return result, mutation

    def apply_entry(
        self,
        *,
        fill: RecurrentEntryFillEvidenceV1,
        funding: RecurrentFundingTermsV1,
    ) -> tuple[
        RecurrentPositionTransitionV1,
        RecurrentCoordinatorMutationResultV1,
    ]:
        with self._lock:
            before = self._coordinator.current_account()
            transition, mutation = self._coordinator.apply_entry(
                fill=fill,
                funding=funding,
            )
            self._persist_mutation(before=before, mutation=mutation)
            return transition, mutation

    def apply_entry_batch(
        self,
        entries: Sequence[
            tuple[
                RecurrentEntryFillEvidenceV1,
                RecurrentFundingTermsV1,
            ]
        ],
    ) -> tuple[
        RecurrentPositionBatchResultV1,
        RecurrentCoordinatorMutationResultV1,
    ]:
        with self._lock:
            before = self._coordinator.current_account()
            result, mutation = self._coordinator.apply_entry_batch(
                entries
            )
            self._persist_mutation(before=before, mutation=mutation)
            return result, mutation

    def apply_close(
        self,
        *,
        fill: RecurrentExitFillEvidenceV1,
    ) -> tuple[
        RecurrentClosePositionTransitionV1,
        RecurrentCoordinatorMutationResultV1,
    ]:
        with self._lock:
            before = self._coordinator.current_account()
            transition, mutation = self._coordinator.apply_close(
                fill=fill,
            )
            self._persist_mutation(before=before, mutation=mutation)
            return transition, mutation

    def apply_close_batch(
        self,
        fills: Sequence[RecurrentExitFillEvidenceV1],
    ) -> tuple[
        RecurrentClosePositionBatchResultV1,
        RecurrentCoordinatorMutationResultV1,
    ]:
        with self._lock:
            before = self._coordinator.current_account()
            result, mutation = self._coordinator.apply_close_batch(fills)
            self._persist_mutation(before=before, mutation=mutation)
            return result, mutation

    def publish_marks(
        self,
        *,
        marks: Sequence[SimulatedMarketMarkEvidence],
        valuation_utc,
    ) -> RecurrentCoordinatorMarkPublicationV1:
        with self._lock:
            before = self._store.load()
            if before is None:
                raise PersistentRecurrentRuntimeError(
                    "cannot publish marks without durable recurrent account"
                )
            publication = self._coordinator.publish_marks(
                marks=marks,
                valuation_utc=valuation_utc,
            )
            after = self._store.load()
            if after != before:
                raise PersistentRecurrentRuntimeError(
                    "mark publication unexpectedly changed durable account state"
                )
            return publication


__all__ = [
    "PERSISTENT_RECURRENT_RUNTIME_CONTRACT_FINGERPRINT",
    "PersistentRecurrentLifecycleRuntimeV1",
    "PersistentRecurrentRuntimeError",
    "PersistentRecurrentRuntimeStatusV1",
]
