from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from packages.simulation.account_state_v2 import initialize_simulation_account_v2
from packages.simulation.closeout_account_state import initialize_closeout_account_v1
from packages.simulation.lifecycle_closeout_state import (
    initialize_lifecycle_closeout_account_v1,
)
from packages.simulation.lifecycle_position_state import (
    initialize_lifecycle_position_account_v1,
)
from packages.simulation.lifecycle_reservation_state import (
    initialize_lifecycle_reservation_account_v1,
)
from packages.simulation.open_position_state import (
    initialize_open_position_account_v1,
)
from packages.simulation.recurrent_genesis_contract import (
    RECURRENT_GENESIS_CONTRACT,
    RECURRENT_GENESIS_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    initialize_recurrent_lifecycle_account_v1,
)


RECURRENT_GENESIS_CONTRACT_VERSION = str(
    RECURRENT_GENESIS_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class RecurrentGenesisError(ValueError):
    pass


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise RecurrentGenesisError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise RecurrentGenesisError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class RecurrentGenesisEvidenceV1:
    contract_version: str
    contract_fingerprint: str
    as_of_utc: datetime
    initial_equity: float

    simulation_v2_state_fingerprint: str
    simulation_v2_ledger_fingerprint: str
    open_position_state_fingerprint: str
    open_position_ledger_fingerprint: str
    closeout_state_fingerprint: str
    closeout_ledger_fingerprint: str
    lifecycle_reservation_state_fingerprint: str
    lifecycle_reservation_ledger_fingerprint: str
    lifecycle_position_state_fingerprint: str
    lifecycle_position_ledger_fingerprint: str
    lifecycle_closeout_state_fingerprint: str
    lifecycle_closeout_ledger_fingerprint: str
    recurrent_state_fingerprint: str
    recurrent_ledger_fingerprint: str

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
        if self.contract_version != RECURRENT_GENESIS_CONTRACT_VERSION:
            raise RecurrentGenesisError(
                "recurrent genesis contract version mismatch"
            )
        if self.contract_fingerprint != RECURRENT_GENESIS_CONTRACT_FINGERPRINT:
            raise RecurrentGenesisError(
                "recurrent genesis contract fingerprint mismatch"
            )
        if self.as_of_utc.tzinfo is None or self.as_of_utc.utcoffset() is None:
            raise RecurrentGenesisError(
                "recurrent genesis timestamp must be timezone-aware"
            )
        if not math.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise RecurrentGenesisError(
                "recurrent genesis initial equity must be finite and positive"
            )
        for label, value in (
            ("simulation v2 state", self.simulation_v2_state_fingerprint),
            ("simulation v2 ledger", self.simulation_v2_ledger_fingerprint),
            ("open-position state", self.open_position_state_fingerprint),
            ("open-position ledger", self.open_position_ledger_fingerprint),
            ("closeout state", self.closeout_state_fingerprint),
            ("closeout ledger", self.closeout_ledger_fingerprint),
            (
                "lifecycle reservation state",
                self.lifecycle_reservation_state_fingerprint,
            ),
            (
                "lifecycle reservation ledger",
                self.lifecycle_reservation_ledger_fingerprint,
            ),
            (
                "lifecycle position state",
                self.lifecycle_position_state_fingerprint,
            ),
            (
                "lifecycle position ledger",
                self.lifecycle_position_ledger_fingerprint,
            ),
            (
                "lifecycle closeout state",
                self.lifecycle_closeout_state_fingerprint,
            ),
            (
                "lifecycle closeout ledger",
                self.lifecycle_closeout_ledger_fingerprint,
            ),
            ("recurrent state", self.recurrent_state_fingerprint),
            ("recurrent ledger", self.recurrent_ledger_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")

        counts = (
            self.provider_reads,
            self.provider_writes,
            self.broker_reads,
            self.broker_writes,
            self.order_writes,
        )
        if any(value != 0 for value in counts):
            raise RecurrentGenesisError(
                "recurrent genesis cannot perform provider/broker/order I/O"
            )
        if any(
            (
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentGenesisError(
                "recurrent genesis cannot grant trading/research authority"
            )


@dataclass(frozen=True)
class RecurrentGenesisResultV1:
    account: RecurrentLifecycleAccountV1
    evidence: RecurrentGenesisEvidenceV1

    def __post_init__(self) -> None:
        state = self.account.state
        ledger = self.account.ledger
        if state.state_fingerprint != self.evidence.recurrent_state_fingerprint:
            raise RecurrentGenesisError(
                "recurrent genesis evidence state fingerprint mismatch"
            )
        if ledger.ledger_fingerprint != self.evidence.recurrent_ledger_fingerprint:
            raise RecurrentGenesisError(
                "recurrent genesis evidence ledger fingerprint mismatch"
            )
        if state.as_of_utc != self.evidence.as_of_utc:
            raise RecurrentGenesisError(
                "recurrent genesis evidence timestamp mismatch"
            )
        if not _same(state.initial_equity, self.evidence.initial_equity):
            raise RecurrentGenesisError(
                "recurrent genesis evidence initial-equity mismatch"
            )

        if (
            state.stock_reservations
            or state.option_reservations
            or state.open_positions
            or state.closed_trades
            or ledger.events
        ):
            raise RecurrentGenesisError(
                "recurrent genesis must be economically empty"
            )
        if not _same(state.cash, state.initial_equity):
            raise RecurrentGenesisError(
                "recurrent genesis cash must equal initial equity"
            )
        if not _same(state.account_book_equity, state.initial_equity):
            raise RecurrentGenesisError(
                "recurrent genesis book equity must equal initial equity"
            )
        if any(
            not _same(value, 0.0)
            for value in (
                state.cumulative_entry_fees_dollars,
                state.cumulative_exit_fees_dollars,
                state.cumulative_account_realized_pnl_dollars,
                state.cumulative_lifetime_trade_net_pnl_dollars,
                state.stock_reserved_capital,
                state.option_reserved_capital,
                state.open_entry_book_value_dollars,
            )
        ):
            raise RecurrentGenesisError(
                "recurrent genesis must start with zero fees, P&L, reservations, and positions"
            )


def build_empty_recurrent_genesis_v1(
    *,
    as_of_utc: datetime,
    initial_equity: float,
) -> RecurrentGenesisResultV1:
    if as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise RecurrentGenesisError(
            "recurrent genesis timestamp must be timezone-aware"
        )
    if not math.isfinite(initial_equity) or initial_equity <= 0.0:
        raise RecurrentGenesisError(
            "recurrent genesis initial equity must be finite and positive"
        )

    reservation_account = initialize_simulation_account_v2(
        as_of_utc=as_of_utc,
        equity=float(initial_equity),
    )
    open_account = initialize_open_position_account_v1(
        source_account=reservation_account,
    )
    closeout_account = initialize_closeout_account_v1(
        source_state=open_account.state,
    )
    lifecycle_reservation = initialize_lifecycle_reservation_account_v1(
        source=closeout_account,
    )
    lifecycle_position = initialize_lifecycle_position_account_v1(
        source=lifecycle_reservation,
    )
    lifecycle_closeout = initialize_lifecycle_closeout_account_v1(
        source=lifecycle_position,
    )
    recurrent = initialize_recurrent_lifecycle_account_v1(
        source=lifecycle_closeout,
    )

    evidence = RecurrentGenesisEvidenceV1(
        contract_version=RECURRENT_GENESIS_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_GENESIS_CONTRACT_FINGERPRINT,
        as_of_utc=as_of_utc,
        initial_equity=float(initial_equity),
        simulation_v2_state_fingerprint=(
            reservation_account.state.state_fingerprint
        ),
        simulation_v2_ledger_fingerprint=(
            reservation_account.ledger.ledger_fingerprint
        ),
        open_position_state_fingerprint=open_account.state.state_fingerprint,
        open_position_ledger_fingerprint=open_account.ledger.ledger_fingerprint,
        closeout_state_fingerprint=closeout_account.state.state_fingerprint,
        closeout_ledger_fingerprint=closeout_account.ledger.ledger_fingerprint,
        lifecycle_reservation_state_fingerprint=(
            lifecycle_reservation.state.state_fingerprint
        ),
        lifecycle_reservation_ledger_fingerprint=(
            lifecycle_reservation.ledger.ledger_fingerprint
        ),
        lifecycle_position_state_fingerprint=(
            lifecycle_position.state.state_fingerprint
        ),
        lifecycle_position_ledger_fingerprint=(
            lifecycle_position.ledger.ledger_fingerprint
        ),
        lifecycle_closeout_state_fingerprint=(
            lifecycle_closeout.state.state_fingerprint
        ),
        lifecycle_closeout_ledger_fingerprint=(
            lifecycle_closeout.ledger.ledger_fingerprint
        ),
        recurrent_state_fingerprint=recurrent.state.state_fingerprint,
        recurrent_ledger_fingerprint=recurrent.ledger.ledger_fingerprint,
    )
    return RecurrentGenesisResultV1(
        account=recurrent,
        evidence=evidence,
    )


__all__ = [
    "RECURRENT_GENESIS_CONTRACT_FINGERPRINT",
    "RecurrentGenesisError",
    "RecurrentGenesisEvidenceV1",
    "RecurrentGenesisResultV1",
    "build_empty_recurrent_genesis_v1",
]
