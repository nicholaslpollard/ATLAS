from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Any, Sequence

from packages.simulation.decision_record import SimulationDecisionRecord
from packages.simulation.market_mark_evidence import SimulatedMarketMarkEvidence
from packages.simulation.option_reservation import LongOptionReservationTerms
from packages.simulation.recurrent_close_position import (
    RecurrentClosePositionBatchResultV1,
    RecurrentClosePositionTransitionV1,
    apply_recurrent_close_position_batch_v1,
    apply_recurrent_close_position_v1,
)
from packages.simulation.recurrent_coordinator_contract import (
    RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT,
    RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingTermsV1,
)
from packages.simulation.recurrent_exit_fill import RecurrentExitFillEvidenceV1
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    recurrent_lifecycle_account_state_fingerprint,
    recurrent_lifecycle_ledger_fingerprint,
)
from packages.simulation.recurrent_marked_state import (
    RecurrentMarkedAccountStateV1,
    build_recurrent_marked_account_state,
    recurrent_marked_account_state_fingerprint,
)
from packages.simulation.recurrent_positions import (
    RecurrentPositionBatchResultV1,
    RecurrentPositionTransitionV1,
    apply_recurrent_entry_batch_v1,
    apply_recurrent_entry_v1,
)
from packages.simulation.recurrent_reservations import (
    RecurrentReservationBatchResultV1,
    RecurrentReservationTransitionV1,
    apply_recurrent_decision_reservation_v1,
    apply_recurrent_reservation_batch_v1,
)


RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_VERSION = str(
    RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT["contract_id"]
)


class RecurrentLifecycleCoordinatorError(RuntimeError):
    pass


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _fingerprint_payload(value: Any) -> str:
    raw = json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_account(account: RecurrentLifecycleAccountV1) -> None:
    if (
        account.state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentLifecycleCoordinatorError(
            "recurrent account contract fingerprint mismatch"
        )
    if (
        account.state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(account.state)
    ):
        raise RecurrentLifecycleCoordinatorError(
            "recurrent account state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != recurrent_lifecycle_ledger_fingerprint(account.ledger)
    ):
        raise RecurrentLifecycleCoordinatorError(
            "recurrent account ledger fingerprint mismatch"
        )
    expected = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected != account.state.state_fingerprint:
        raise RecurrentLifecycleCoordinatorError(
            "recurrent account ledger does not terminate at current state"
        )


@dataclass(frozen=True)
class RecurrentLifecycleCoordinatorSnapshotV1:
    contract_version: str
    contract_fingerprint: str
    revision: int
    account: RecurrentLifecycleAccountV1
    marked_state: RecurrentMarkedAccountStateV1 | None

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
            != RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_VERSION
        ):
            raise RecurrentLifecycleCoordinatorError(
                "recurrent coordinator contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT
        ):
            raise RecurrentLifecycleCoordinatorError(
                "recurrent coordinator contract fingerprint mismatch"
            )
        if self.revision < 0:
            raise RecurrentLifecycleCoordinatorError(
                "recurrent coordinator revision cannot be negative"
            )
        _validate_account(self.account)
        if self.marked_state is not None:
            if (
                self.marked_state.state_fingerprint
                != recurrent_marked_account_state_fingerprint(
                    self.marked_state
                )
            ):
                raise RecurrentLifecycleCoordinatorError(
                    "recurrent coordinator marked-state fingerprint mismatch"
                )
            if (
                self.marked_state.source_account_state_fingerprint
                != self.account.state.state_fingerprint
            ):
                raise RecurrentLifecycleCoordinatorError(
                    "recurrent coordinator marked state is stale"
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
            raise RecurrentLifecycleCoordinatorError(
                "recurrent coordinator cannot grant external/trading authority"
            )

    @property
    def marks_current(self) -> bool:
        return self.marked_state is not None

    @property
    def snapshot_fingerprint(self) -> str:
        return recurrent_lifecycle_coordinator_snapshot_fingerprint(self)


@dataclass(frozen=True)
class RecurrentCoordinatorMutationResultV1:
    account: RecurrentLifecycleAccountV1
    revision: int
    new_ledger_event_count: int
    valuation_invalidated: bool
    idempotent_reuse: bool


@dataclass(frozen=True)
class RecurrentCoordinatorMarkPublicationV1:
    marked_state: RecurrentMarkedAccountStateV1
    revision: int
    idempotent_reuse: bool


def recurrent_lifecycle_coordinator_snapshot_fingerprint(
    snapshot: RecurrentLifecycleCoordinatorSnapshotV1,
) -> str:
    return _fingerprint_payload(snapshot)


class RecurrentLifecycleCoordinatorV1:
    """Atomic owner for repeated simulation cycles on one recurrent account.

    The coordinator owns only accepted simulation objects. It performs no provider,
    broker, order, filesystem, or network I/O. External evidence builders may read an
    immutable snapshot and later submit evidence back through exact-state or
    common-source batch transitions.
    """

    def __init__(
        self,
        *,
        account: RecurrentLifecycleAccountV1,
    ) -> None:
        _validate_account(account)
        self._lock = RLock()
        self._account = account
        self._marked_state: RecurrentMarkedAccountStateV1 | None = None
        self._revision = len(account.ledger.events)

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def current_account(self) -> RecurrentLifecycleAccountV1:
        with self._lock:
            return self._account

    def current_marked_state(
        self,
    ) -> RecurrentMarkedAccountStateV1 | None:
        with self._lock:
            return self._marked_state

    def current_dashboard_pair(
        self,
    ) -> tuple[
        RecurrentLifecycleAccountV1,
        RecurrentMarkedAccountStateV1,
    ] | None:
        with self._lock:
            marked = self._marked_state
            if marked is None:
                return None
            if (
                marked.source_account_state_fingerprint
                != self._account.state.state_fingerprint
            ):
                raise RecurrentLifecycleCoordinatorError(
                    "internal recurrent valuation is stale"
                )
            return self._account, marked

    def snapshot(self) -> RecurrentLifecycleCoordinatorSnapshotV1:
        with self._lock:
            return RecurrentLifecycleCoordinatorSnapshotV1(
                contract_version=(
                    RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_VERSION
                ),
                contract_fingerprint=(
                    RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT
                ),
                revision=self._revision,
                account=self._account,
                marked_state=self._marked_state,
            )

    def _commit_account(
        self,
        *,
        before: RecurrentLifecycleAccountV1,
        after: RecurrentLifecycleAccountV1,
    ) -> RecurrentCoordinatorMutationResultV1:
        _validate_account(after)
        delta = len(after.ledger.events) - len(before.ledger.events)
        if delta < 0:
            raise RecurrentLifecycleCoordinatorError(
                "recurrent mutation reduced ledger length"
            )
        invalidated = False
        if delta:
            self._account = after
            invalidated = self._marked_state is not None
            self._marked_state = None
            self._revision += delta
            return RecurrentCoordinatorMutationResultV1(
                account=after,
                revision=self._revision,
                new_ledger_event_count=delta,
                valuation_invalidated=invalidated,
                idempotent_reuse=False,
            )
        if after != before:
            raise RecurrentLifecycleCoordinatorError(
                "zero-event recurrent mutation changed account state"
            )
        return RecurrentCoordinatorMutationResultV1(
            account=before,
            revision=self._revision,
            new_ledger_event_count=0,
            valuation_invalidated=False,
            idempotent_reuse=True,
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
            before = self._account
            transition = apply_recurrent_decision_reservation_v1(
                before,
                record,
                option_terms=option_terms,
            )
            mutation = self._commit_account(
                before=before,
                after=transition.account,
            )
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
            before = self._account
            result = apply_recurrent_reservation_batch_v1(
                before,
                decisions,
            )
            mutation = self._commit_account(
                before=before,
                after=result.account,
            )
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
            before = self._account
            transition = apply_recurrent_entry_v1(
                before,
                fill=fill,
                funding=funding,
            )
            mutation = self._commit_account(
                before=before,
                after=transition.account,
            )
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
            before = self._account
            result = apply_recurrent_entry_batch_v1(
                before,
                entries,
            )
            mutation = self._commit_account(
                before=before,
                after=result.account,
            )
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
            before = self._account
            transition = apply_recurrent_close_position_v1(
                before,
                fill=fill,
            )
            mutation = self._commit_account(
                before=before,
                after=transition.account,
            )
            return transition, mutation

    def apply_close_batch(
        self,
        fills: Sequence[RecurrentExitFillEvidenceV1],
    ) -> tuple[
        RecurrentClosePositionBatchResultV1,
        RecurrentCoordinatorMutationResultV1,
    ]:
        with self._lock:
            before = self._account
            result = apply_recurrent_close_position_batch_v1(
                before,
                fills,
            )
            mutation = self._commit_account(
                before=before,
                after=result.account,
            )
            return result, mutation

    def publish_marks(
        self,
        *,
        marks: Sequence[SimulatedMarketMarkEvidence],
        valuation_utc: datetime,
    ) -> RecurrentCoordinatorMarkPublicationV1:
        with self._lock:
            marked = build_recurrent_marked_account_state(
                source_state=self._account.state,
                marks=marks,
                valuation_utc=valuation_utc,
            )
            if (
                marked.source_account_state_fingerprint
                != self._account.state.state_fingerprint
            ):
                raise RecurrentLifecycleCoordinatorError(
                    "new recurrent valuation does not bind current account"
                )
            existing = self._marked_state
            if (
                existing is not None
                and existing.state_fingerprint == marked.state_fingerprint
            ):
                return RecurrentCoordinatorMarkPublicationV1(
                    marked_state=existing,
                    revision=self._revision,
                    idempotent_reuse=True,
                )
            self._marked_state = marked
            self._revision += 1
            return RecurrentCoordinatorMarkPublicationV1(
                marked_state=marked,
                revision=self._revision,
                idempotent_reuse=False,
            )


__all__ = [
    "RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT",
    "RecurrentCoordinatorMarkPublicationV1",
    "RecurrentCoordinatorMutationResultV1",
    "RecurrentLifecycleCoordinatorError",
    "RecurrentLifecycleCoordinatorSnapshotV1",
    "RecurrentLifecycleCoordinatorV1",
    "recurrent_lifecycle_coordinator_snapshot_fingerprint",
]
