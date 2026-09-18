from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Any, Sequence

from packages.simulation.closeout_account_state import (
    CloseoutAccountV1,
    CloseoutBatchResultV1,
    CloseoutTransitionV1,
    apply_closeout_batch_v1,
    apply_closeout_exit_fill_v1,
    closeout_account_state_fingerprint,
    closeout_ledger_fingerprint,
    initialize_closeout_account_v1,
)
from packages.simulation.lifecycle_coordinator_contract import (
    SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT,
    SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_marked_account_state import (
    LifecycleMarkedAccountStateV1,
    build_lifecycle_marked_account_state,
    lifecycle_marked_account_state_fingerprint,
)
from packages.simulation.market_mark_evidence import SimulatedMarketMarkEvidence
from packages.simulation.open_position_state import (
    OpenPositionAccountStateV1,
    open_position_account_state_fingerprint,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.simulated_exit_fill import SimulatedExitFillEvidence


SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_VERSION = str(
    SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT["contract_id"]
)


class SimulationLifecycleCoordinatorError(RuntimeError):
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


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise SimulationLifecycleCoordinatorError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise SimulationLifecycleCoordinatorError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _validate_source_state(source_state: OpenPositionAccountStateV1) -> None:
    if (
        source_state.contract_fingerprint
        != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
    ):
        raise SimulationLifecycleCoordinatorError(
            "source must use the accepted open-position account-state contract"
        )
    if (
        source_state.state_fingerprint
        != open_position_account_state_fingerprint(source_state)
    ):
        raise SimulationLifecycleCoordinatorError(
            "source open-position account-state fingerprint mismatch"
        )


def _validate_closeout_account(account: CloseoutAccountV1) -> None:
    if (
        account.state.state_fingerprint
        != closeout_account_state_fingerprint(account.state)
    ):
        raise SimulationLifecycleCoordinatorError(
            "coordinator closeout state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != closeout_ledger_fingerprint(account.ledger)
    ):
        raise SimulationLifecycleCoordinatorError(
            "coordinator closeout ledger fingerprint mismatch"
        )
    expected_latest = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected_latest != account.state.state_fingerprint:
        raise SimulationLifecycleCoordinatorError(
            "coordinator closeout ledger does not terminate at current state"
        )


@dataclass(frozen=True)
class SimulationLifecycleCoordinatorSnapshotV1:
    contract_version: str
    contract_fingerprint: str
    revision: int
    source_open_position_state_fingerprint: str
    closeout_account: CloseoutAccountV1
    marked_state: LifecycleMarkedAccountStateV1 | None

    single_cycle_only: bool = True
    reentry_supported: bool = False
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
            != SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_VERSION
        ):
            raise SimulationLifecycleCoordinatorError(
                "lifecycle coordinator contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT
        ):
            raise SimulationLifecycleCoordinatorError(
                "lifecycle coordinator contract fingerprint mismatch"
            )
        if self.revision < 0:
            raise SimulationLifecycleCoordinatorError(
                "lifecycle coordinator revision cannot be negative"
            )
        _require_fingerprint(
            self.source_open_position_state_fingerprint,
            label="source open-position state fingerprint",
        )
        _validate_closeout_account(self.closeout_account)
        if (
            self.closeout_account.state.source_open_position_state_fingerprint
            != self.source_open_position_state_fingerprint
        ):
            raise SimulationLifecycleCoordinatorError(
                "closeout account source lineage mismatch"
            )

        if self.marked_state is not None:
            if (
                self.marked_state.state_fingerprint
                != lifecycle_marked_account_state_fingerprint(
                    self.marked_state
                )
            ):
                raise SimulationLifecycleCoordinatorError(
                    "coordinator marked-state fingerprint mismatch"
                )
            if (
                self.marked_state.source_closeout_state_fingerprint
                != self.closeout_account.state.state_fingerprint
            ):
                raise SimulationLifecycleCoordinatorError(
                    "coordinator marked state is stale relative to current closeout state"
                )

        if not self.single_cycle_only or self.reentry_supported:
            raise SimulationLifecycleCoordinatorError(
                "v1 coordinator must remain single-cycle with re-entry disabled"
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
            raise SimulationLifecycleCoordinatorError(
                "lifecycle coordinator cannot grant provider, broker, order, "
                "trading, promotion, or confluence authority"
            )

    @property
    def marks_current(self) -> bool:
        return self.marked_state is not None

    @property
    def snapshot_fingerprint(self) -> str:
        return simulation_lifecycle_coordinator_snapshot_fingerprint(self)


@dataclass(frozen=True)
class CoordinatorExitTransitionV1:
    transition: CloseoutTransitionV1
    revision: int
    valuation_invalidated: bool

    @property
    def idempotent_reuse(self) -> bool:
        return self.transition.idempotent_reuse


@dataclass(frozen=True)
class CoordinatorExitBatchTransitionV1:
    result: CloseoutBatchResultV1
    revision: int
    new_closeout_event_count: int
    valuation_invalidated: bool


@dataclass(frozen=True)
class CoordinatorMarkPublicationV1:
    marked_state: LifecycleMarkedAccountStateV1
    revision: int
    idempotent_reuse: bool


def simulation_lifecycle_coordinator_snapshot_fingerprint(
    snapshot: SimulationLifecycleCoordinatorSnapshotV1,
) -> str:
    return _fingerprint_payload(snapshot)


class SimulationLifecycleCoordinatorV1:
    """Atomic owner for one accepted simulation lifecycle cycle.

    The coordinator starts from one immutable accepted open-position account state.
    It can close those positions and publish current marks for survivors. It does not
    create new reservations or entries; re-entry is intentionally deferred to a
    later contract. All supplied fills/marks are already materialized evidence, so
    this object performs no provider, broker, order, or filesystem I/O.
    """

    def __init__(
        self,
        *,
        source_state: OpenPositionAccountStateV1,
    ) -> None:
        _validate_source_state(source_state)
        account = initialize_closeout_account_v1(source_state=source_state)
        _validate_closeout_account(account)

        self._lock = RLock()
        self._source_state = source_state
        self._account = account
        self._marked_state: LifecycleMarkedAccountStateV1 | None = None
        self._revision = 0

    @property
    def source_state(self) -> OpenPositionAccountStateV1:
        return self._source_state

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def snapshot(self) -> SimulationLifecycleCoordinatorSnapshotV1:
        with self._lock:
            return SimulationLifecycleCoordinatorSnapshotV1(
                contract_version=(
                    SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_VERSION
                ),
                contract_fingerprint=(
                    SIMULATION_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT
                ),
                revision=self._revision,
                source_open_position_state_fingerprint=(
                    self._source_state.state_fingerprint
                ),
                closeout_account=self._account,
                marked_state=self._marked_state,
            )

    def current_closeout_account(self) -> CloseoutAccountV1:
        with self._lock:
            return self._account

    def current_marked_state(
        self,
    ) -> LifecycleMarkedAccountStateV1 | None:
        with self._lock:
            return self._marked_state

    def current_dashboard_pair(
        self,
    ) -> tuple[CloseoutAccountV1, LifecycleMarkedAccountStateV1] | None:
        """Return one atomic book+mark pair or None when valuation is absent/stale."""
        with self._lock:
            marked = self._marked_state
            if marked is None:
                return None
            if (
                marked.source_closeout_state_fingerprint
                != self._account.state.state_fingerprint
            ):
                raise SimulationLifecycleCoordinatorError(
                    "internal marked-state lineage is stale"
                )
            return self._account, marked

    def apply_exit_fill(
        self,
        *,
        fill: SimulatedExitFillEvidence,
    ) -> CoordinatorExitTransitionV1:
        with self._lock:
            before_account = self._account
            before_event_count = len(before_account.ledger.events)
            transition = apply_closeout_exit_fill_v1(
                before_account,
                fill=fill,
            )
            after_account = transition.account
            _validate_closeout_account(after_account)
            new_event_count = (
                len(after_account.ledger.events) - before_event_count
            )
            if new_event_count not in (0, 1):
                raise SimulationLifecycleCoordinatorError(
                    "single exit application produced an invalid ledger delta"
                )

            invalidated = False
            if new_event_count == 1:
                self._account = after_account
                invalidated = self._marked_state is not None
                self._marked_state = None
                self._revision += 1
            elif after_account != before_account:
                raise SimulationLifecycleCoordinatorError(
                    "idempotent exit reuse changed the closeout account"
                )

            return CoordinatorExitTransitionV1(
                transition=transition,
                revision=self._revision,
                valuation_invalidated=invalidated,
            )

    def apply_exit_batch(
        self,
        fills: Sequence[SimulatedExitFillEvidence],
    ) -> CoordinatorExitBatchTransitionV1:
        with self._lock:
            before_account = self._account
            before_event_count = len(before_account.ledger.events)
            result = apply_closeout_batch_v1(before_account, fills)
            after_account = result.account
            _validate_closeout_account(after_account)
            new_event_count = (
                len(after_account.ledger.events) - before_event_count
            )
            if new_event_count < 0:
                raise SimulationLifecycleCoordinatorError(
                    "exit batch reduced the closeout ledger"
                )

            invalidated = False
            if new_event_count:
                self._account = after_account
                invalidated = self._marked_state is not None
                self._marked_state = None
                self._revision += new_event_count
            elif after_account != before_account:
                raise SimulationLifecycleCoordinatorError(
                    "zero-event exit batch changed the closeout account"
                )

            return CoordinatorExitBatchTransitionV1(
                result=result,
                revision=self._revision,
                new_closeout_event_count=new_event_count,
                valuation_invalidated=invalidated,
            )

    def publish_marks(
        self,
        *,
        marks: Sequence[SimulatedMarketMarkEvidence],
        valuation_utc: datetime,
    ) -> CoordinatorMarkPublicationV1:
        with self._lock:
            marked = build_lifecycle_marked_account_state(
                source_state=self._account.state,
                marks=marks,
                valuation_utc=valuation_utc,
            )
            if (
                marked.source_closeout_state_fingerprint
                != self._account.state.state_fingerprint
            ):
                raise SimulationLifecycleCoordinatorError(
                    "new marked state does not bind current closeout state"
                )

            existing = self._marked_state
            if (
                existing is not None
                and existing.state_fingerprint == marked.state_fingerprint
            ):
                return CoordinatorMarkPublicationV1(
                    marked_state=existing,
                    revision=self._revision,
                    idempotent_reuse=True,
                )

            self._marked_state = marked
            self._revision += 1
            return CoordinatorMarkPublicationV1(
                marked_state=marked,
                revision=self._revision,
                idempotent_reuse=False,
            )


def replay_simulation_lifecycle_cycle_v1(
    *,
    source_state: OpenPositionAccountStateV1,
    exit_fills: Sequence[SimulatedExitFillEvidence] = (),
    marks: Sequence[SimulatedMarketMarkEvidence] | None = None,
    valuation_utc: datetime | None = None,
) -> SimulationLifecycleCoordinatorSnapshotV1:
    coordinator = SimulationLifecycleCoordinatorV1(
        source_state=source_state,
    )
    coordinator.apply_exit_batch(exit_fills)

    if marks is None:
        if valuation_utc is not None:
            raise SimulationLifecycleCoordinatorError(
                "valuation timestamp requires an explicit mark sequence"
            )
    else:
        if valuation_utc is None:
            raise SimulationLifecycleCoordinatorError(
                "mark replay requires an explicit valuation timestamp"
            )
        coordinator.publish_marks(
            marks=marks,
            valuation_utc=valuation_utc,
        )
    return coordinator.snapshot()


def verify_simulation_lifecycle_cycle_replay_v1(
    *,
    expected: SimulationLifecycleCoordinatorSnapshotV1,
    source_state: OpenPositionAccountStateV1,
    exit_fills: Sequence[SimulatedExitFillEvidence] = (),
    marks: Sequence[SimulatedMarketMarkEvidence] | None = None,
    valuation_utc: datetime | None = None,
) -> None:
    replayed = replay_simulation_lifecycle_cycle_v1(
        source_state=source_state,
        exit_fills=exit_fills,
        marks=marks,
        valuation_utc=valuation_utc,
    )
    if (
        replayed.snapshot_fingerprint
        != expected.snapshot_fingerprint
    ):
        raise SimulationLifecycleCoordinatorError(
            "lifecycle coordinator replay fingerprint mismatch"
        )
