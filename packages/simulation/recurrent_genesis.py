from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from packages.simulation.account_state_v2 import initialize_simulation_account_v2
from packages.simulation.closeout_account_state import initialize_closeout_account_v1
from packages.simulation.lifecycle_closeout_state import initialize_lifecycle_closeout_account_v1
from packages.simulation.lifecycle_position_state import initialize_lifecycle_position_account_v1
from packages.simulation.lifecycle_reservation_state import (
    initialize_lifecycle_reservation_account_v1,
)
from packages.simulation.open_position_state import initialize_open_position_account_v1
from packages.simulation.recurrent_engine import RecurrentLifecycleCoordinatorV1
from packages.simulation.recurrent_genesis_contract import (
    RECURRENT_GENESIS_BOOTSTRAP_CONTRACT,
    RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    initialize_recurrent_lifecycle_account_v1,
)
from packages.simulation.recurrent_runtime import (
    DurableRecurrentLifecycleRuntimeV1,
)


RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_VERSION = str(
    RECURRENT_GENESIS_BOOTSTRAP_CONTRACT["contract_id"]
)


class RecurrentGenesisBootstrapError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecurrentGenesisBootstrapResultV1:
    contract_version: str
    contract_fingerprint: str
    initial_equity: float
    as_of_utc: datetime

    simulation_account_state_fingerprint: str
    open_position_state_fingerprint: str
    closeout_state_fingerprint: str
    lifecycle_reservation_state_fingerprint: str
    lifecycle_position_state_fingerprint: str
    lifecycle_closeout_state_fingerprint: str
    recurrent_state_fingerprint: str
    recurrent_ledger_fingerprint: str
    checkpoint_sha256: str
    checkpoint_path: str

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
        if self.contract_version != RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_VERSION:
            raise RecurrentGenesisBootstrapError(
                "recurrent genesis contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_FINGERPRINT
        ):
            raise RecurrentGenesisBootstrapError(
                "recurrent genesis contract fingerprint mismatch"
            )
        if self.initial_equity <= 0.0:
            raise RecurrentGenesisBootstrapError(
                "recurrent genesis initial equity must be positive"
            )
        if self.as_of_utc.tzinfo is None or self.as_of_utc.utcoffset() is None:
            raise RecurrentGenesisBootstrapError(
                "recurrent genesis timestamp must be timezone-aware"
            )
        for label, value in (
            ("simulation account state", self.simulation_account_state_fingerprint),
            ("open-position state", self.open_position_state_fingerprint),
            ("closeout state", self.closeout_state_fingerprint),
            (
                "lifecycle reservation state",
                self.lifecycle_reservation_state_fingerprint,
            ),
            (
                "lifecycle position state",
                self.lifecycle_position_state_fingerprint,
            ),
            (
                "lifecycle closeout state",
                self.lifecycle_closeout_state_fingerprint,
            ),
            ("recurrent state", self.recurrent_state_fingerprint),
            ("recurrent ledger", self.recurrent_ledger_fingerprint),
            ("checkpoint", self.checkpoint_sha256),
        ):
            if (
                len(value) != 64
                or any(ch not in "0123456789abcdef" for ch in value)
            ):
                raise RecurrentGenesisBootstrapError(
                    f"recurrent genesis {label} fingerprint is invalid"
                )
        if not self.checkpoint_path:
            raise RecurrentGenesisBootstrapError(
                "recurrent genesis checkpoint path cannot be blank"
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
            raise RecurrentGenesisBootstrapError(
                "recurrent genesis cannot grant external/trading authority"
            )


def build_empty_recurrent_genesis_account_v1(
    *,
    initial_equity: float,
    as_of_utc: datetime,
) -> tuple[
    RecurrentLifecycleAccountV1,
    dict[str, str],
]:
    if initial_equity <= 0.0:
        raise RecurrentGenesisBootstrapError(
            "initial equity must be positive"
        )
    if as_of_utc.tzinfo is None or as_of_utc.utcoffset() is None:
        raise RecurrentGenesisBootstrapError(
            "genesis timestamp must be timezone-aware"
        )

    simulation = initialize_simulation_account_v2(
        as_of_utc=as_of_utc,
        equity=float(initial_equity),
    )
    open_position = initialize_open_position_account_v1(
        source_account=simulation
    )
    closeout = initialize_closeout_account_v1(
        source_state=open_position.state
    )
    lifecycle_reservation = initialize_lifecycle_reservation_account_v1(
        source=closeout
    )
    lifecycle_position = initialize_lifecycle_position_account_v1(
        source=lifecycle_reservation
    )
    lifecycle_closeout = initialize_lifecycle_closeout_account_v1(
        source=lifecycle_position
    )
    recurrent = initialize_recurrent_lifecycle_account_v1(
        source=lifecycle_closeout
    )

    intermediate_ledgers = (
        simulation.ledger.events,
        open_position.ledger.events,
        closeout.ledger.events,
        lifecycle_reservation.ledger.events,
        lifecycle_position.ledger.events,
        lifecycle_closeout.ledger.events,
        recurrent.ledger.events,
    )
    if any(intermediate_ledgers):
        raise RecurrentGenesisBootstrapError(
            "accepted empty-state chain produced a nonempty transition ledger"
        )

    if (
        simulation.state.stock_reservations
        or simulation.state.option_reservations
        or open_position.state.remaining_stock_reservations
        or open_position.state.remaining_option_reservations
        or open_position.state.open_positions
        or closeout.state.remaining_stock_reservations
        or closeout.state.remaining_option_reservations
        or closeout.state.open_positions
        or closeout.state.closed_trades
        or lifecycle_reservation.state.stock_reservations
        or lifecycle_reservation.state.option_reservations
        or lifecycle_reservation.state.open_positions
        or lifecycle_reservation.state.closed_trades
        or lifecycle_position.state.stock_reservations
        or lifecycle_position.state.option_reservations
        or lifecycle_position.state.open_positions
        or lifecycle_position.state.closed_trades
        or lifecycle_closeout.state.stock_reservations
        or lifecycle_closeout.state.option_reservations
        or lifecycle_closeout.state.open_positions
        or lifecycle_closeout.state.prior_closed_trades
        or lifecycle_closeout.state.lifecycle_closed_trades
    ):
        raise RecurrentGenesisBootstrapError(
            "accepted empty-state chain produced active or closed trade records"
        )

    state = recurrent.state
    if (
        state.cash != float(initial_equity)
        or state.account_book_equity != float(initial_equity)
        or state.stock_reservations
        or state.option_reservations
        or state.open_positions
        or state.closed_trades
        or recurrent.ledger.events
    ):
        raise RecurrentGenesisBootstrapError(
            "accepted empty-state chain did not produce an empty recurrent account"
        )
    if any(
        abs(value) > 1e-9
        for value in (
            state.cumulative_entry_fees_dollars,
            state.cumulative_exit_fees_dollars,
            state.cumulative_account_realized_pnl_dollars,
            state.cumulative_lifetime_trade_net_pnl_dollars,
            state.stock_reserved_capital,
            state.option_reserved_capital,
            state.stock_reserved_gross_notional,
            state.option_reserved_signed_delta_equivalent_notional,
            state.option_reserved_abs_delta_equivalent_notional,
            state.option_reserved_max_loss_cash,
            state.option_reserved_premium_at_risk,
            state.open_entry_book_value_dollars,
            state.open_stock_gross_entry_exposure_dollars,
            state.open_option_entry_book_value_dollars,
            state.open_option_signed_delta_equivalent_entry_reference_dollars,
            state.open_option_abs_delta_equivalent_entry_reference_dollars,
            state.open_option_premium_at_risk_dollars,
        )
    ):
        raise RecurrentGenesisBootstrapError(
            "accepted empty-state chain produced nonzero exposure or P&L"
        )

    lineage = {
        "simulation_account_state_fingerprint": (
            simulation.state.state_fingerprint
        ),
        "open_position_state_fingerprint": (
            open_position.state.state_fingerprint
        ),
        "closeout_state_fingerprint": closeout.state.state_fingerprint,
        "lifecycle_reservation_state_fingerprint": (
            lifecycle_reservation.state.state_fingerprint
        ),
        "lifecycle_position_state_fingerprint": (
            lifecycle_position.state.state_fingerprint
        ),
        "lifecycle_closeout_state_fingerprint": (
            lifecycle_closeout.state.state_fingerprint
        ),
        "recurrent_state_fingerprint": state.state_fingerprint,
        "recurrent_ledger_fingerprint": (
            recurrent.ledger.ledger_fingerprint
        ),
    }
    return recurrent, lineage


def bootstrap_recurrent_genesis_v1(
    *,
    checkpoint_path: Path,
    initial_equity: float,
    as_of_utc: datetime,
) -> tuple[
    DurableRecurrentLifecycleRuntimeV1,
    RecurrentGenesisBootstrapResultV1,
]:
    path = Path(checkpoint_path)
    history_dir = path.parent / "history"
    if path.exists():
        raise RecurrentGenesisBootstrapError(
            "recurrent genesis refuses to overwrite an existing checkpoint"
        )
    if any(history_dir.glob("*.json")):
        raise RecurrentGenesisBootstrapError(
            "recurrent genesis refuses to run while checkpoint history exists"
        )

    account, lineage = build_empty_recurrent_genesis_account_v1(
        initial_equity=initial_equity,
        as_of_utc=as_of_utc,
    )
    runtime = DurableRecurrentLifecycleRuntimeV1.bootstrap(
        checkpoint_path=path,
        coordinator=RecurrentLifecycleCoordinatorV1(account=account),
    )
    checkpoint = runtime.status()
    result = RecurrentGenesisBootstrapResultV1(
        contract_version=RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_VERSION,
        contract_fingerprint=(
            RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_FINGERPRINT
        ),
        initial_equity=float(initial_equity),
        as_of_utc=as_of_utc,
        checkpoint_sha256=checkpoint.checkpoint_sha256,
        checkpoint_path=str(path),
        **lineage,
    )
    return runtime, result


__all__ = [
    "RECURRENT_GENESIS_BOOTSTRAP_CONTRACT_FINGERPRINT",
    "RecurrentGenesisBootstrapError",
    "RecurrentGenesisBootstrapResultV1",
    "bootstrap_recurrent_genesis_v1",
    "build_empty_recurrent_genesis_account_v1",
]
