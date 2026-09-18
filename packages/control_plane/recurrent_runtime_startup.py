from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.control_plane.recurrent_lifecycle_dashboard import (
    RecurrentLifecycleDashboardService,
    source_provider_from_persistent_recurrent_runtime,
)
from packages.control_plane.recurrent_runtime_startup_contract import (
    RECURRENT_RUNTIME_STARTUP_CONTRACT,
    RECURRENT_RUNTIME_STARTUP_CONTRACT_FINGERPRINT,
)
from packages.core.settings import AtlasSettings
from packages.simulation.recurrent_persistent_runtime import (
    PersistentRecurrentLifecycleRuntimeV1,
)
from packages.simulation.recurrent_runtime_store import (
    RecurrentRuntimeAccountStoreV1,
)


RECURRENT_RUNTIME_STARTUP_CONTRACT_VERSION = str(
    RECURRENT_RUNTIME_STARTUP_CONTRACT["contract_id"]
)


class RecurrentRuntimeStartupError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecurrentRuntimeStartupV1:
    contract_version: str
    contract_fingerprint: str
    store_root: Path
    account_restored: bool
    restored_state_fingerprint: str | None
    restored_ledger_fingerprint: str | None
    restored_ledger_event_count: int
    runtime: PersistentRecurrentLifecycleRuntimeV1 | None
    dashboard_service: RecurrentLifecycleDashboardService

    provider_reads: int = 0
    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    order_writes: int = 0
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != RECURRENT_RUNTIME_STARTUP_CONTRACT_VERSION:
            raise RecurrentRuntimeStartupError(
                "recurrent runtime startup contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_RUNTIME_STARTUP_CONTRACT_FINGERPRINT
        ):
            raise RecurrentRuntimeStartupError(
                "recurrent runtime startup contract fingerprint mismatch"
            )
        counts = (
            self.provider_reads,
            self.provider_writes,
            self.broker_reads,
            self.broker_writes,
            self.order_writes,
        )
        if any(value != 0 for value in counts):
            raise RecurrentRuntimeStartupError(
                "recurrent runtime restore cannot perform provider/broker/order I/O"
            )
        if any(
            (
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentRuntimeStartupError(
                "recurrent runtime startup cannot grant trading/research authority"
            )
        if self.restored_ledger_event_count < 0:
            raise RecurrentRuntimeStartupError(
                "restored ledger-event count cannot be negative"
            )

        if self.account_restored:
            if self.runtime is None:
                raise RecurrentRuntimeStartupError(
                    "restored startup must carry persistent recurrent runtime"
                )
            if (
                self.restored_state_fingerprint is None
                or self.restored_ledger_fingerprint is None
            ):
                raise RecurrentRuntimeStartupError(
                    "restored startup requires state and ledger fingerprints"
                )
            account = self.runtime.current_account()
            if (
                account.state.state_fingerprint
                != self.restored_state_fingerprint
                or account.ledger.ledger_fingerprint
                != self.restored_ledger_fingerprint
                or len(account.ledger.events)
                != self.restored_ledger_event_count
            ):
                raise RecurrentRuntimeStartupError(
                    "restored runtime metadata does not match current account"
                )
            if self.runtime.current_marked_state() is not None:
                raise RecurrentRuntimeStartupError(
                    "restored runtime must start without persisted market marks"
                )
        else:
            if (
                self.runtime is not None
                or self.restored_state_fingerprint is not None
                or self.restored_ledger_fingerprint is not None
                or self.restored_ledger_event_count != 0
            ):
                raise RecurrentRuntimeStartupError(
                    "uninitialized startup cannot claim restored account state"
                )


def restore_recurrent_runtime_for_phase19(
    settings: AtlasSettings,
) -> RecurrentRuntimeStartupV1:
    """Restore recurrent runtime truth for the production Phase 19 surface.

    Missing state is an explicit uninitialized condition. Any malformed/corrupt
    persisted state is allowed to raise and abort startup rather than falling back to
    older artifacts or an invented account.
    """

    store = RecurrentRuntimeAccountStoreV1.from_settings(settings)
    runtime = PersistentRecurrentLifecycleRuntimeV1.restore(store=store)

    if runtime is None:
        dashboard = RecurrentLifecycleDashboardService()
        return RecurrentRuntimeStartupV1(
            contract_version=RECURRENT_RUNTIME_STARTUP_CONTRACT_VERSION,
            contract_fingerprint=RECURRENT_RUNTIME_STARTUP_CONTRACT_FINGERPRINT,
            store_root=store.root,
            account_restored=False,
            restored_state_fingerprint=None,
            restored_ledger_fingerprint=None,
            restored_ledger_event_count=0,
            runtime=None,
            dashboard_service=dashboard,
        )

    durable = runtime.durable_snapshot()
    dashboard = RecurrentLifecycleDashboardService(
        source_provider=source_provider_from_persistent_recurrent_runtime(
            runtime
        )
    )
    return RecurrentRuntimeStartupV1(
        contract_version=RECURRENT_RUNTIME_STARTUP_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_RUNTIME_STARTUP_CONTRACT_FINGERPRINT,
        store_root=store.root,
        account_restored=True,
        restored_state_fingerprint=durable.state_fingerprint,
        restored_ledger_fingerprint=durable.ledger_fingerprint,
        restored_ledger_event_count=durable.ledger_event_count,
        runtime=runtime,
        dashboard_service=dashboard,
    )


__all__ = [
    "RECURRENT_RUNTIME_STARTUP_CONTRACT_FINGERPRINT",
    "RecurrentRuntimeStartupError",
    "RecurrentRuntimeStartupV1",
    "restore_recurrent_runtime_for_phase19",
]
