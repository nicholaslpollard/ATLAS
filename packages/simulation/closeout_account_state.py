from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2 import (
    SimulatedOptionReservationV2,
    SimulatedStockReservationV2,
)
from packages.simulation.closeout_account_state_contract import (
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT,
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.open_position_state import (
    OpenPositionAccountStateV1,
    SimulatedOpenPositionV1,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.simulated_exit_fill import (
    SimulatedExitFillEvidence,
    simulated_exit_fill_fingerprint,
)
from packages.simulation.simulated_exit_fill_contract import (
    SIMULATED_EXIT_FILL_CONTRACT_FINGERPRINT,
)


SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION = str(
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class CloseoutAccountStateError(ValueError):
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
        raise CloseoutAccountStateError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise CloseoutAccountStateError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CloseoutAccountStateError(f"{label} must be timezone-aware")


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise CloseoutAccountStateError(
            f"{label} must be finite and nonnegative"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


@dataclass(frozen=True)
class ClosedTradeV1:
    source_open_position_state_fingerprint: str
    position_fingerprint: str
    exit_fill_fingerprint: str
    decision_record_fingerprint: str
    instrument_kind: InstrumentKind
    instrument_id: str
    ticker: str
    direction: DiscoveryDirection
    candidate_identifier: str
    option_contract_ticker: str | None
    option_contract_type: str | None
    opened_utc: datetime
    exited_utc: datetime
    hold_seconds: float
    quantity: float
    quantity_unit: str
    entry_price_per_unit: float
    exit_price_per_unit: float
    contract_multiplier: float
    entry_book_value_dollars: float
    entry_fees_dollars: float
    gross_exit_proceeds_dollars: float
    exit_fees_dollars: float
    net_exit_proceeds_dollars: float
    account_realized_pnl_delta_dollars: float
    lifetime_trade_net_pnl_dollars: float
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for label, value in (
            (
                "source open-position state",
                self.source_open_position_state_fingerprint,
            ),
            ("position", self.position_fingerprint),
            ("exit fill", self.exit_fill_fingerprint),
            ("decision record", self.decision_record_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.opened_utc, label="closed-trade opened timestamp")
        _require_aware(self.exited_utc, label="closed-trade exited timestamp")
        if self.exited_utc < self.opened_utc:
            raise CloseoutAccountStateError(
                "closed trade exit cannot precede position open"
            )
        expected_hold = (self.exited_utc - self.opened_utc).total_seconds()
        if (
            not math.isfinite(self.hold_seconds)
            or self.hold_seconds < 0.0
            or not _same(self.hold_seconds, expected_hold)
        ):
            raise CloseoutAccountStateError(
                "closed-trade hold seconds must match open-to-exit duration"
            )
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise CloseoutAccountStateError(
                "closed-trade identity cannot be blank"
            )
        if not self.candidate_identifier.strip():
            raise CloseoutAccountStateError(
                "closed-trade candidate identifier cannot be blank"
            )
        for label, value in (
            ("quantity", self.quantity),
            ("entry price", self.entry_price_per_unit),
            ("contract multiplier", self.contract_multiplier),
            ("entry book value", self.entry_book_value_dollars),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise CloseoutAccountStateError(
                    f"{label} must be finite and positive"
                )
        for label, value in (
            ("exit price", self.exit_price_per_unit),
            ("entry fees", self.entry_fees_dollars),
            ("gross exit proceeds", self.gross_exit_proceeds_dollars),
            ("exit fees", self.exit_fees_dollars),
            ("net exit proceeds", self.net_exit_proceeds_dollars),
        ):
            _require_nonnegative(value, label=label)
        if not math.isfinite(self.account_realized_pnl_delta_dollars):
            raise CloseoutAccountStateError(
                "account realized P&L delta must be finite"
            )
        if not math.isfinite(self.lifetime_trade_net_pnl_dollars):
            raise CloseoutAccountStateError(
                "lifetime trade net P&L must be finite"
            )

        expected_entry_book = (
            self.quantity
            * self.entry_price_per_unit
            * self.contract_multiplier
        )
        if not _same(self.entry_book_value_dollars, expected_entry_book):
            raise CloseoutAccountStateError(
                "closed-trade entry book value mismatch"
            )
        expected_gross = (
            self.quantity
            * self.exit_price_per_unit
            * self.contract_multiplier
        )
        if not _same(self.gross_exit_proceeds_dollars, expected_gross):
            raise CloseoutAccountStateError(
                "closed-trade gross exit proceeds mismatch"
            )
        if self.exit_fees_dollars > self.gross_exit_proceeds_dollars + _TOLERANCE:
            raise CloseoutAccountStateError(
                "closed-trade exit fees cannot exceed gross proceeds"
            )
        if not _same(
            self.net_exit_proceeds_dollars,
            self.gross_exit_proceeds_dollars - self.exit_fees_dollars,
        ):
            raise CloseoutAccountStateError(
                "closed-trade net exit proceeds mismatch"
            )
        expected_account_realized = (
            self.net_exit_proceeds_dollars - self.entry_book_value_dollars
        )
        if not _same(
            self.account_realized_pnl_delta_dollars,
            expected_account_realized,
        ):
            raise CloseoutAccountStateError(
                "account realized P&L must exclude already-expensed entry fees"
            )
        expected_lifetime = (
            self.gross_exit_proceeds_dollars
            - self.entry_book_value_dollars
            - self.entry_fees_dollars
            - self.exit_fees_dollars
        )
        if not _same(
            self.lifetime_trade_net_pnl_dollars,
            expected_lifetime,
        ):
            raise CloseoutAccountStateError(
                "lifetime trade net P&L must include entry and exit fees once"
            )
        if not _same(
            self.lifetime_trade_net_pnl_dollars,
            self.account_realized_pnl_delta_dollars
            - self.entry_fees_dollars,
        ):
            raise CloseoutAccountStateError(
                "closed-trade P&L semantics do not reconcile"
            )
        if not self.reason_codes:
            raise CloseoutAccountStateError(
                "closed trade requires reason codes"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES":
                raise CloseoutAccountStateError(
                    "closed stock quantity unit must be SHARES"
                )
            if not _same(self.contract_multiplier, 1.0):
                raise CloseoutAccountStateError(
                    "closed stock multiplier must equal one"
                )
            if (
                self.option_contract_ticker is not None
                or self.option_contract_type is not None
            ):
                raise CloseoutAccountStateError(
                    "closed stock cannot carry option identity"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS":
                raise CloseoutAccountStateError(
                    "closed option quantity unit must be CONTRACTS"
                )
            if not _same(self.quantity, round(self.quantity)):
                raise CloseoutAccountStateError(
                    "closed option quantity must be integral contracts"
                )
            if (
                not self.option_contract_ticker
                or self.option_contract_type not in {"call", "put"}
            ):
                raise CloseoutAccountStateError(
                    "closed option requires call/put identity"
                )
        else:
            raise CloseoutAccountStateError(
                "unsupported closed-trade instrument kind"
            )

    @property
    def closed_trade_fingerprint(self) -> str:
        return closed_trade_fingerprint(self)


@dataclass(frozen=True)
class CloseoutAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    source_open_position_contract_fingerprint: str
    source_open_position_state_fingerprint: str
    as_of_utc: datetime

    initial_equity: float
    source_entry_book_equity: float
    cumulative_entry_fees_dollars: float
    cumulative_exit_fees_dollars: float
    cumulative_account_realized_pnl_dollars: float
    cumulative_lifetime_trade_net_pnl_dollars: float
    cash: float
    account_book_equity: float

    remaining_stock_reserved_capital: float
    remaining_option_reserved_capital: float
    remaining_stock_gross_notional: float
    remaining_option_signed_delta_equivalent_notional: float
    remaining_option_abs_delta_equivalent_notional: float

    open_entry_book_value_dollars: float
    open_stock_gross_entry_exposure_dollars: float
    open_option_entry_book_value_dollars: float
    open_option_signed_delta_equivalent_entry_reference_dollars: float
    open_option_abs_delta_equivalent_entry_reference_dollars: float
    open_option_premium_at_risk_dollars: float

    remaining_stock_reservations: tuple[SimulatedStockReservationV2, ...]
    remaining_option_reservations: tuple[SimulatedOptionReservationV2, ...]
    open_positions: tuple[SimulatedOpenPositionV1, ...]
    closed_trades: tuple[ClosedTradeV1, ...]

    simulation_account_state_mutation: bool = True
    simulation_realized_pnl_computation: bool = True
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
            != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION
        ):
            raise CloseoutAccountStateError(
                "closeout account-state contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ):
            raise CloseoutAccountStateError(
                "closeout account-state contract fingerprint mismatch"
            )
        if (
            self.source_open_position_contract_fingerprint
            != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ):
            raise CloseoutAccountStateError(
                "source open-position contract fingerprint mismatch"
            )
        _require_fingerprint(
            self.source_open_position_state_fingerprint,
            label="source open-position state fingerprint",
        )
        _require_aware(self.as_of_utc, label="closeout account-state timestamp")
        if not math.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise CloseoutAccountStateError(
                "initial equity must be finite and positive"
            )
        for label, value in (
            ("source entry-book equity", self.source_entry_book_equity),
            ("cumulative entry fees", self.cumulative_entry_fees_dollars),
            ("cumulative exit fees", self.cumulative_exit_fees_dollars),
            ("cash", self.cash),
            ("account book equity", self.account_book_equity),
            (
                "remaining stock reserved capital",
                self.remaining_stock_reserved_capital,
            ),
            (
                "remaining option reserved capital",
                self.remaining_option_reserved_capital,
            ),
            (
                "remaining stock gross notional",
                self.remaining_stock_gross_notional,
            ),
            (
                "remaining option absolute delta",
                self.remaining_option_abs_delta_equivalent_notional,
            ),
            ("open entry book value", self.open_entry_book_value_dollars),
            (
                "open stock gross entry exposure",
                self.open_stock_gross_entry_exposure_dollars,
            ),
            (
                "open option entry book value",
                self.open_option_entry_book_value_dollars,
            ),
            (
                "open option absolute delta reference",
                self.open_option_abs_delta_equivalent_entry_reference_dollars,
            ),
            (
                "open option premium at risk",
                self.open_option_premium_at_risk_dollars,
            ),
        ):
            _require_nonnegative(value, label=label)
        for label, value in (
            (
                "cumulative account realized P&L",
                self.cumulative_account_realized_pnl_dollars,
            ),
            (
                "cumulative lifetime trade net P&L",
                self.cumulative_lifetime_trade_net_pnl_dollars,
            ),
            (
                "remaining option signed delta",
                self.remaining_option_signed_delta_equivalent_notional,
            ),
            (
                "open option signed delta reference",
                self.open_option_signed_delta_equivalent_entry_reference_dollars,
            ),
        ):
            if not math.isfinite(value):
                raise CloseoutAccountStateError(
                    f"{label} must be finite"
                )
        if (
            not self.simulation_account_state_mutation
            or not self.simulation_realized_pnl_computation
        ):
            raise CloseoutAccountStateError(
                "closeout state must identify simulation mutation and realized-P&L computation"
            )

        stock_reservations = tuple(
            sorted(
                self.remaining_stock_reservations,
                key=lambda item: item.decision_record_fingerprint,
            )
        )
        option_reservations = tuple(
            sorted(
                self.remaining_option_reservations,
                key=lambda item: item.decision_record_fingerprint,
            )
        )
        positions = tuple(
            sorted(
                self.open_positions,
                key=lambda item: item.decision_record_fingerprint,
            )
        )
        closed = tuple(
            sorted(
                self.closed_trades,
                key=lambda item: (
                    item.exited_utc,
                    item.exit_fill_fingerprint,
                ),
            )
        )
        if stock_reservations != self.remaining_stock_reservations:
            raise CloseoutAccountStateError(
                "remaining stock reservations must be ordered"
            )
        if option_reservations != self.remaining_option_reservations:
            raise CloseoutAccountStateError(
                "remaining option reservations must be ordered"
            )
        if positions != self.open_positions:
            raise CloseoutAccountStateError(
                "open positions must be ordered by decision fingerprint"
            )
        if closed != self.closed_trades:
            raise CloseoutAccountStateError(
                "closed trades must be chronological and deterministic"
            )

        open_position_ids = [item.position_fingerprint for item in self.open_positions]
        closed_position_ids = [item.position_fingerprint for item in self.closed_trades]
        if len(open_position_ids) != len(set(open_position_ids)):
            raise CloseoutAccountStateError(
                "open positions cannot duplicate position fingerprints"
            )
        if len(closed_position_ids) != len(set(closed_position_ids)):
            raise CloseoutAccountStateError(
                "closed trades cannot duplicate position fingerprints"
            )
        if set(open_position_ids).intersection(closed_position_ids):
            raise CloseoutAccountStateError(
                "one position cannot be open and closed simultaneously"
            )
        if any(item.opened_utc > self.as_of_utc for item in self.open_positions):
            raise CloseoutAccountStateError(
                "open position cannot postdate closeout state"
            )
        if any(item.exited_utc > self.as_of_utc for item in self.closed_trades):
            raise CloseoutAccountStateError(
                "closed trade cannot postdate closeout state"
            )
        if any(
            item.source_open_position_state_fingerprint
            != self.source_open_position_state_fingerprint
            for item in self.closed_trades
        ):
            raise CloseoutAccountStateError(
                "closed trades must bind the same source open-position state"
            )

        checks = (
            (
                self.remaining_stock_reserved_capital,
                sum(x.reserved_capital for x in self.remaining_stock_reservations),
                "remaining stock reserved capital",
            ),
            (
                self.remaining_option_reserved_capital,
                sum(x.reserved_capital for x in self.remaining_option_reservations),
                "remaining option reserved capital",
            ),
            (
                self.remaining_stock_gross_notional,
                sum(x.gross_notional for x in self.remaining_stock_reservations),
                "remaining stock gross notional",
            ),
            (
                self.remaining_option_signed_delta_equivalent_notional,
                sum(
                    x.signed_delta_equivalent_notional
                    for x in self.remaining_option_reservations
                ),
                "remaining option signed delta",
            ),
            (
                self.remaining_option_abs_delta_equivalent_notional,
                sum(
                    x.abs_delta_equivalent_notional
                    for x in self.remaining_option_reservations
                ),
                "remaining option absolute delta",
            ),
            (
                self.open_entry_book_value_dollars,
                sum(x.entry_book_value_dollars for x in self.open_positions),
                "open entry book value",
            ),
            (
                self.open_stock_gross_entry_exposure_dollars,
                sum(
                    x.stock_gross_entry_exposure_dollars
                    for x in self.open_positions
                ),
                "open stock gross exposure",
            ),
            (
                self.open_option_entry_book_value_dollars,
                sum(
                    x.entry_book_value_dollars
                    for x in self.open_positions
                    if x.instrument_kind == InstrumentKind.OPTION
                ),
                "open option entry book value",
            ),
            (
                self.open_option_signed_delta_equivalent_entry_reference_dollars,
                sum(
                    x.option_signed_delta_equivalent_entry_reference_dollars
                    for x in self.open_positions
                ),
                "open option signed delta reference",
            ),
            (
                self.open_option_abs_delta_equivalent_entry_reference_dollars,
                sum(
                    x.option_abs_delta_equivalent_entry_reference_dollars
                    for x in self.open_positions
                ),
                "open option absolute delta reference",
            ),
            (
                self.open_option_premium_at_risk_dollars,
                sum(
                    x.option_premium_at_risk_dollars
                    for x in self.open_positions
                ),
                "open option premium at risk",
            ),
            (
                self.cumulative_exit_fees_dollars,
                sum(x.exit_fees_dollars for x in self.closed_trades),
                "cumulative exit fees",
            ),
            (
                self.cumulative_account_realized_pnl_dollars,
                sum(
                    x.account_realized_pnl_delta_dollars
                    for x in self.closed_trades
                ),
                "cumulative account realized P&L",
            ),
            (
                self.cumulative_lifetime_trade_net_pnl_dollars,
                sum(
                    x.lifetime_trade_net_pnl_dollars
                    for x in self.closed_trades
                ),
                "cumulative lifetime trade net P&L",
            ),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise CloseoutAccountStateError(
                    f"{label} must equal constituent sum"
                )

        if not _same(
            self.source_entry_book_equity,
            self.initial_equity - self.cumulative_entry_fees_dollars,
        ):
            raise CloseoutAccountStateError(
                "source entry-book equity must preserve already-expensed entry fees"
            )
        expected_book_equity = (
            self.initial_equity
            - self.cumulative_entry_fees_dollars
            + self.cumulative_account_realized_pnl_dollars
        )
        if not _same(self.account_book_equity, expected_book_equity):
            raise CloseoutAccountStateError(
                "account book equity must add realized P&L without re-expensing entry fees"
            )
        balance_equity = (
            self.cash
            + self.remaining_stock_reserved_capital
            + self.remaining_option_reserved_capital
            + self.open_entry_book_value_dollars
        )
        if not _same(self.account_book_equity, balance_equity):
            raise CloseoutAccountStateError(
                "closeout account must reconcile cash, reservations, and open book value"
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
            raise CloseoutAccountStateError(
                "closeout state cannot grant provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return closeout_account_state_fingerprint(self)


@dataclass(frozen=True)
class CloseoutLedgerEventV1:
    sequence: int
    occurred_utc: datetime
    decision_record_fingerprint: str
    position_fingerprint: str
    exit_fill_fingerprint: str
    instrument_kind: InstrumentKind
    cash_delta_dollars: float
    open_entry_book_value_delta_dollars: float
    exit_fee_delta_dollars: float
    account_realized_pnl_delta_dollars: float
    lifetime_trade_net_pnl_dollars: float
    stock_gross_entry_exposure_delta_dollars: float
    option_signed_delta_entry_reference_delta_dollars: float
    option_abs_delta_entry_reference_delta_dollars: float
    option_premium_at_risk_delta_dollars: float
    before_state_fingerprint: str
    after_state_fingerprint: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise CloseoutAccountStateError(
                "closeout ledger sequence must be positive"
            )
        _require_aware(self.occurred_utc, label="closeout ledger timestamp")
        for label, value in (
            ("decision record", self.decision_record_fingerprint),
            ("position", self.position_fingerprint),
            ("exit fill", self.exit_fill_fingerprint),
            ("before state", self.before_state_fingerprint),
            ("after state", self.after_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        values = (
            self.cash_delta_dollars,
            self.open_entry_book_value_delta_dollars,
            self.exit_fee_delta_dollars,
            self.account_realized_pnl_delta_dollars,
            self.lifetime_trade_net_pnl_dollars,
            self.stock_gross_entry_exposure_delta_dollars,
            self.option_signed_delta_entry_reference_delta_dollars,
            self.option_abs_delta_entry_reference_delta_dollars,
            self.option_premium_at_risk_delta_dollars,
        )
        if not all(math.isfinite(value) for value in values):
            raise CloseoutAccountStateError(
                "closeout ledger deltas must be finite"
            )
        if self.cash_delta_dollars < -_TOLERANCE:
            raise CloseoutAccountStateError(
                "closeout cash delta cannot be negative"
            )
        if self.open_entry_book_value_delta_dollars >= 0.0:
            raise CloseoutAccountStateError(
                "closeout must remove positive open entry book value"
            )
        if self.exit_fee_delta_dollars < 0.0:
            raise CloseoutAccountStateError(
                "closeout exit fee delta cannot be negative"
            )
        if not self.reason_codes:
            raise CloseoutAccountStateError(
                "closeout ledger event requires reason codes"
            )
        if self.instrument_kind == InstrumentKind.STOCK:
            if self.stock_gross_entry_exposure_delta_dollars >= 0.0:
                raise CloseoutAccountStateError(
                    "stock closeout must remove stock gross exposure"
                )
            if any(
                not _same(value, 0.0)
                for value in (
                    self.option_signed_delta_entry_reference_delta_dollars,
                    self.option_abs_delta_entry_reference_delta_dollars,
                    self.option_premium_at_risk_delta_dollars,
                )
            ):
                raise CloseoutAccountStateError(
                    "stock closeout cannot mutate option exposure"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if not _same(
                self.stock_gross_entry_exposure_delta_dollars,
                0.0,
            ):
                raise CloseoutAccountStateError(
                    "option closeout cannot mutate stock exposure"
                )
            if self.option_abs_delta_entry_reference_delta_dollars >= 0.0:
                raise CloseoutAccountStateError(
                    "option closeout must remove absolute delta reference"
                )
            if self.option_premium_at_risk_delta_dollars >= 0.0:
                raise CloseoutAccountStateError(
                    "option closeout must remove premium at risk"
                )
        else:
            raise CloseoutAccountStateError(
                "unsupported closeout ledger instrument kind"
            )

    @property
    def event_fingerprint(self) -> str:
        return closeout_ledger_event_fingerprint(self)


@dataclass(frozen=True)
class CloseoutLedgerV1:
    contract_version: str
    contract_fingerprint: str
    source_open_position_state_fingerprint: str
    initial_state_fingerprint: str
    events: tuple[CloseoutLedgerEventV1, ...]

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION
        ):
            raise CloseoutAccountStateError(
                "closeout ledger contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ):
            raise CloseoutAccountStateError(
                "closeout ledger contract fingerprint mismatch"
            )
        _require_fingerprint(
            self.source_open_position_state_fingerprint,
            label="ledger source open-position state fingerprint",
        )
        _require_fingerprint(
            self.initial_state_fingerprint,
            label="ledger initial state fingerprint",
        )
        previous_time: datetime | None = None
        previous_after = self.initial_state_fingerprint
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence:
                raise CloseoutAccountStateError(
                    "closeout ledger sequence must be contiguous"
                )
            if (
                previous_time is not None
                and event.occurred_utc < previous_time
            ):
                raise CloseoutAccountStateError(
                    "closeout ledger events must be chronological"
                )
            if event.before_state_fingerprint != previous_after:
                raise CloseoutAccountStateError(
                    "closeout ledger before-state chain is broken"
                )
            previous_time = event.occurred_utc
            previous_after = event.after_state_fingerprint

    @property
    def ledger_fingerprint(self) -> str:
        return closeout_ledger_fingerprint(self)


@dataclass(frozen=True)
class CloseoutAccountV1:
    state: CloseoutAccountStateV1
    ledger: CloseoutLedgerV1

    def __post_init__(self) -> None:
        if (
            self.state.source_open_position_state_fingerprint
            != self.ledger.source_open_position_state_fingerprint
        ):
            raise CloseoutAccountStateError(
                "closeout state and ledger source fingerprints must match"
            )
        expected = (
            self.ledger.events[-1].after_state_fingerprint
            if self.ledger.events
            else self.ledger.initial_state_fingerprint
        )
        if self.state.state_fingerprint != expected:
            raise CloseoutAccountStateError(
                "closeout state must match latest ledger state fingerprint"
            )


@dataclass(frozen=True)
class CloseoutTransitionV1:
    account: CloseoutAccountV1
    event: CloseoutLedgerEventV1 | None
    closed_trade: ClosedTradeV1
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class CloseoutBatchResultV1:
    account: CloseoutAccountV1
    ordered_exit_fill_fingerprints: tuple[str, ...]
    transitions: tuple[CloseoutTransitionV1, ...]


def closed_trade_fingerprint(trade: ClosedTradeV1) -> str:
    return _fingerprint_payload(trade)


def closeout_account_state_fingerprint(state: CloseoutAccountStateV1) -> str:
    return _fingerprint_payload(state)


def closeout_ledger_event_fingerprint(event: CloseoutLedgerEventV1) -> str:
    return _fingerprint_payload(event)


def closeout_ledger_fingerprint(ledger: CloseoutLedgerV1) -> str:
    return _fingerprint_payload(ledger)


def _build_state(
    *,
    previous: CloseoutAccountStateV1,
    as_of_utc: datetime,
    cash: float,
    cumulative_exit_fees_dollars: float,
    cumulative_account_realized_pnl_dollars: float,
    cumulative_lifetime_trade_net_pnl_dollars: float,
    open_positions: Sequence[SimulatedOpenPositionV1],
    closed_trades: Sequence[ClosedTradeV1],
) -> CloseoutAccountStateV1:
    positions = tuple(
        sorted(
            open_positions,
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    closed = tuple(
        sorted(
            closed_trades,
            key=lambda item: (
                item.exited_utc,
                item.exit_fill_fingerprint,
            ),
        )
    )
    stock_reservations = previous.remaining_stock_reservations
    option_reservations = previous.remaining_option_reservations

    stock_reserved = sum(x.reserved_capital for x in stock_reservations)
    option_reserved = sum(x.reserved_capital for x in option_reservations)
    stock_gross = sum(x.gross_notional for x in stock_reservations)
    option_signed = sum(
        x.signed_delta_equivalent_notional for x in option_reservations
    )
    option_abs = sum(
        x.abs_delta_equivalent_notional for x in option_reservations
    )
    open_book = sum(x.entry_book_value_dollars for x in positions)
    open_stock = sum(x.stock_gross_entry_exposure_dollars for x in positions)
    open_option_book = sum(
        x.entry_book_value_dollars
        for x in positions
        if x.instrument_kind == InstrumentKind.OPTION
    )
    open_option_signed = sum(
        x.option_signed_delta_equivalent_entry_reference_dollars
        for x in positions
    )
    open_option_abs = sum(
        x.option_abs_delta_equivalent_entry_reference_dollars
        for x in positions
    )
    open_option_premium = sum(
        x.option_premium_at_risk_dollars for x in positions
    )
    book_equity = (
        previous.initial_equity
        - previous.cumulative_entry_fees_dollars
        + cumulative_account_realized_pnl_dollars
    )
    return CloseoutAccountStateV1(
        contract_version=SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=(
            SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_open_position_contract_fingerprint=(
            previous.source_open_position_contract_fingerprint
        ),
        source_open_position_state_fingerprint=(
            previous.source_open_position_state_fingerprint
        ),
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        source_entry_book_equity=previous.source_entry_book_equity,
        cumulative_entry_fees_dollars=(
            previous.cumulative_entry_fees_dollars
        ),
        cumulative_exit_fees_dollars=_zero(
            cumulative_exit_fees_dollars
        ),
        cumulative_account_realized_pnl_dollars=_zero(
            cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=_zero(
            cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=_zero(cash),
        account_book_equity=_zero(book_equity),
        remaining_stock_reserved_capital=_zero(stock_reserved),
        remaining_option_reserved_capital=_zero(option_reserved),
        remaining_stock_gross_notional=_zero(stock_gross),
        remaining_option_signed_delta_equivalent_notional=_zero(
            option_signed
        ),
        remaining_option_abs_delta_equivalent_notional=_zero(option_abs),
        open_entry_book_value_dollars=_zero(open_book),
        open_stock_gross_entry_exposure_dollars=_zero(open_stock),
        open_option_entry_book_value_dollars=_zero(open_option_book),
        open_option_signed_delta_equivalent_entry_reference_dollars=_zero(
            open_option_signed
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=_zero(
            open_option_abs
        ),
        open_option_premium_at_risk_dollars=_zero(open_option_premium),
        remaining_stock_reservations=stock_reservations,
        remaining_option_reservations=option_reservations,
        open_positions=positions,
        closed_trades=closed,
    )


def initialize_closeout_account_v1(
    *,
    source_state: OpenPositionAccountStateV1,
) -> CloseoutAccountV1:
    if (
        source_state.contract_fingerprint
        != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
    ):
        raise CloseoutAccountStateError(
            "source account must use accepted open-position account state"
        )
    state = CloseoutAccountStateV1(
        contract_version=SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=(
            SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_open_position_contract_fingerprint=(
            source_state.contract_fingerprint
        ),
        source_open_position_state_fingerprint=source_state.state_fingerprint,
        as_of_utc=source_state.as_of_utc,
        initial_equity=source_state.initial_equity,
        source_entry_book_equity=source_state.entry_book_equity,
        cumulative_entry_fees_dollars=(
            source_state.cumulative_entry_fees_dollars
        ),
        cumulative_exit_fees_dollars=0.0,
        cumulative_account_realized_pnl_dollars=0.0,
        cumulative_lifetime_trade_net_pnl_dollars=0.0,
        cash=source_state.cash,
        account_book_equity=source_state.entry_book_equity,
        remaining_stock_reserved_capital=(
            source_state.remaining_stock_reserved_capital
        ),
        remaining_option_reserved_capital=(
            source_state.remaining_option_reserved_capital
        ),
        remaining_stock_gross_notional=(
            source_state.remaining_stock_gross_notional
        ),
        remaining_option_signed_delta_equivalent_notional=(
            source_state.remaining_option_signed_delta_equivalent_notional
        ),
        remaining_option_abs_delta_equivalent_notional=(
            source_state.remaining_option_abs_delta_equivalent_notional
        ),
        open_entry_book_value_dollars=(
            source_state.open_entry_book_value_dollars
        ),
        open_stock_gross_entry_exposure_dollars=(
            source_state.open_stock_gross_entry_exposure_dollars
        ),
        open_option_entry_book_value_dollars=(
            source_state.open_option_entry_book_value_dollars
        ),
        open_option_signed_delta_equivalent_entry_reference_dollars=(
            source_state.open_option_signed_delta_equivalent_entry_reference_dollars
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=(
            source_state.open_option_abs_delta_equivalent_entry_reference_dollars
        ),
        open_option_premium_at_risk_dollars=(
            source_state.open_option_premium_at_risk_dollars
        ),
        remaining_stock_reservations=source_state.remaining_stock_reservations,
        remaining_option_reservations=source_state.remaining_option_reservations,
        open_positions=source_state.open_positions,
        closed_trades=(),
    )
    ledger = CloseoutLedgerV1(
        contract_version=SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=(
            SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_open_position_state_fingerprint=source_state.state_fingerprint,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return CloseoutAccountV1(state=state, ledger=ledger)


def _validate_fill_contract(fill: SimulatedExitFillEvidence) -> None:
    if (
        fill.contract_fingerprint
        != SIMULATED_EXIT_FILL_CONTRACT_FINGERPRINT
    ):
        raise CloseoutAccountStateError(
            "simulated exit-fill contract fingerprint mismatch"
        )
    if fill.exit_fill_fingerprint != simulated_exit_fill_fingerprint(fill):
        raise CloseoutAccountStateError(
            "simulated exit-fill fingerprint mismatch"
        )
    if not fill.full_close:
        raise CloseoutAccountStateError(
            "closeout requires full-close exit-fill evidence"
        )


def _validate_fill_position_lineage(
    *,
    account: CloseoutAccountV1,
    fill: SimulatedExitFillEvidence,
    position: SimulatedOpenPositionV1,
) -> None:
    if (
        fill.source_open_position_state_fingerprint
        != account.state.source_open_position_state_fingerprint
    ):
        raise CloseoutAccountStateError(
            "exit fill must bind immutable source open-position state"
        )
    if fill.position_fingerprint != position.position_fingerprint:
        raise CloseoutAccountStateError(
            "exit-fill position fingerprint lineage mismatch"
        )
    exact_pairs = (
        (
            fill.source_account_state_fingerprint,
            position.source_account_state_fingerprint,
            "source account state",
        ),
        (
            fill.decision_record_fingerprint,
            position.decision_record_fingerprint,
            "decision record",
        ),
        (
            fill.candidate_fingerprint,
            position.candidate_fingerprint,
            "candidate",
        ),
        (
            fill.entry_fill_fingerprint,
            position.fill_fingerprint,
            "entry fill",
        ),
        (
            fill.funding_terms_fingerprint,
            position.funding_terms_fingerprint,
            "funding terms",
        ),
        (
            fill.reservation_fingerprint,
            position.reservation_fingerprint,
            "reservation",
        ),
        (
            fill.option_reservation_terms_fingerprint,
            position.option_reservation_terms_fingerprint,
            "option reservation terms",
        ),
        (
            fill.option_economics_result_fingerprint,
            position.option_economics_result_fingerprint,
            "option economics",
        ),
        (fill.instrument_kind, position.instrument_kind, "instrument kind"),
        (fill.instrument_id, position.instrument_id, "instrument id"),
        (fill.ticker, position.ticker, "ticker"),
        (fill.direction, position.direction, "direction"),
        (
            fill.candidate_identifier,
            position.candidate_identifier,
            "candidate identifier",
        ),
        (
            fill.option_contract_ticker,
            position.option_contract_ticker,
            "option contract ticker",
        ),
        (
            fill.option_contract_type,
            position.option_contract_type,
            "option contract type",
        ),
        (fill.opened_utc, position.opened_utc, "opened timestamp"),
        (fill.quantity_unit, position.quantity_unit, "quantity unit"),
    )
    for left, right, label in exact_pairs:
        if left != right:
            raise CloseoutAccountStateError(
                f"exit-fill {label} lineage mismatch"
            )
    if not _same(fill.quantity, position.quantity):
        raise CloseoutAccountStateError(
            "exit-fill quantity lineage mismatch"
        )
    if not _same(fill.contract_multiplier, position.contract_multiplier):
        raise CloseoutAccountStateError(
            "exit-fill multiplier lineage mismatch"
        )


def _build_closed_trade(
    *,
    account: CloseoutAccountV1,
    position: SimulatedOpenPositionV1,
    fill: SimulatedExitFillEvidence,
) -> ClosedTradeV1:
    account_realized = (
        fill.net_exit_proceeds_dollars
        - position.entry_book_value_dollars
    )
    lifetime_net = account_realized - position.entry_fees_dollars
    return ClosedTradeV1(
        source_open_position_state_fingerprint=(
            account.state.source_open_position_state_fingerprint
        ),
        position_fingerprint=position.position_fingerprint,
        exit_fill_fingerprint=fill.exit_fill_fingerprint,
        decision_record_fingerprint=position.decision_record_fingerprint,
        instrument_kind=position.instrument_kind,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        direction=position.direction,
        candidate_identifier=position.candidate_identifier,
        option_contract_ticker=position.option_contract_ticker,
        option_contract_type=position.option_contract_type,
        opened_utc=position.opened_utc,
        exited_utc=fill.exited_utc,
        hold_seconds=(
            fill.exited_utc - position.opened_utc
        ).total_seconds(),
        quantity=position.quantity,
        quantity_unit=position.quantity_unit,
        entry_price_per_unit=position.entry_price_per_unit,
        exit_price_per_unit=fill.exit_price_per_unit,
        contract_multiplier=position.contract_multiplier,
        entry_book_value_dollars=position.entry_book_value_dollars,
        entry_fees_dollars=position.entry_fees_dollars,
        gross_exit_proceeds_dollars=fill.gross_exit_proceeds_dollars,
        exit_fees_dollars=fill.exit_fees_dollars,
        net_exit_proceeds_dollars=fill.net_exit_proceeds_dollars,
        account_realized_pnl_delta_dollars=account_realized,
        lifetime_trade_net_pnl_dollars=lifetime_net,
        reason_codes=(
            "EXACT_OPEN_POSITION_EXIT_FILL_LINEAGE",
            "ENTRY_FEE_ALREADY_EXPENSED_ACCOUNT_PNL_EXCLUDES_RECHARGE",
            "LIFETIME_TRADE_NET_PNL_INCLUDES_ENTRY_AND_EXIT_FEES_ONCE",
        ),
    )


def apply_closeout_exit_fill_v1(
    account: CloseoutAccountV1,
    *,
    fill: SimulatedExitFillEvidence,
) -> CloseoutTransitionV1:
    _validate_fill_contract(fill)

    duplicate = tuple(
        trade
        for trade in account.state.closed_trades
        if trade.exit_fill_fingerprint == fill.exit_fill_fingerprint
    )
    if duplicate:
        if len(duplicate) != 1:
            raise CloseoutAccountStateError(
                "duplicate exit-fill fingerprint in closed-trade ledger"
            )
        return CloseoutTransitionV1(
            account=account,
            event=None,
            closed_trade=duplicate[0],
            idempotent_reuse=True,
            reason_codes=("DUPLICATE_EXIT_FILL_IDEMPOTENT_REUSE",),
        )

    prior_close = tuple(
        trade
        for trade in account.state.closed_trades
        if trade.position_fingerprint == fill.position_fingerprint
    )
    if prior_close:
        raise CloseoutAccountStateError(
            "conflicting second close for an already-closed position"
        )

    if fill.exited_utc < account.state.as_of_utc:
        raise CloseoutAccountStateError(
            "exit-fill timestamp cannot precede current closeout state"
        )

    matches = tuple(
        position
        for position in account.state.open_positions
        if position.position_fingerprint == fill.position_fingerprint
    )
    if len(matches) != 1:
        raise CloseoutAccountStateError(
            "exact active position is required for closeout"
        )
    position = matches[0]
    _validate_fill_position_lineage(
        account=account,
        fill=fill,
        position=position,
    )

    closed_trade = _build_closed_trade(
        account=account,
        position=position,
        fill=fill,
    )
    new_cash = account.state.cash + fill.net_exit_proceeds_dollars
    remaining_positions = tuple(
        item
        for item in account.state.open_positions
        if item.position_fingerprint != position.position_fingerprint
    )
    next_state = _build_state(
        previous=account.state,
        as_of_utc=fill.exited_utc,
        cash=new_cash,
        cumulative_exit_fees_dollars=(
            account.state.cumulative_exit_fees_dollars
            + fill.exit_fees_dollars
        ),
        cumulative_account_realized_pnl_dollars=(
            account.state.cumulative_account_realized_pnl_dollars
            + closed_trade.account_realized_pnl_delta_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            account.state.cumulative_lifetime_trade_net_pnl_dollars
            + closed_trade.lifetime_trade_net_pnl_dollars
        ),
        open_positions=remaining_positions,
        closed_trades=account.state.closed_trades + (closed_trade,),
    )

    stock_delta = -position.stock_gross_entry_exposure_dollars
    option_signed_delta = (
        -position.option_signed_delta_equivalent_entry_reference_dollars
    )
    option_abs_delta = (
        -position.option_abs_delta_equivalent_entry_reference_dollars
    )
    option_premium_delta = -position.option_premium_at_risk_dollars

    event = CloseoutLedgerEventV1(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=fill.exited_utc,
        decision_record_fingerprint=position.decision_record_fingerprint,
        position_fingerprint=position.position_fingerprint,
        exit_fill_fingerprint=fill.exit_fill_fingerprint,
        instrument_kind=position.instrument_kind,
        cash_delta_dollars=_zero(fill.net_exit_proceeds_dollars),
        open_entry_book_value_delta_dollars=(
            -position.entry_book_value_dollars
        ),
        exit_fee_delta_dollars=fill.exit_fees_dollars,
        account_realized_pnl_delta_dollars=(
            closed_trade.account_realized_pnl_delta_dollars
        ),
        lifetime_trade_net_pnl_dollars=(
            closed_trade.lifetime_trade_net_pnl_dollars
        ),
        stock_gross_entry_exposure_delta_dollars=_zero(stock_delta),
        option_signed_delta_entry_reference_delta_dollars=_zero(
            option_signed_delta
        ),
        option_abs_delta_entry_reference_delta_dollars=_zero(
            option_abs_delta
        ),
        option_premium_at_risk_delta_dollars=_zero(
            option_premium_delta
        ),
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
        reason_codes=(
            "MATCHED_POSITION_REMOVED_ONCE",
            "NET_EXIT_PROCEEDS_RETURNED_TO_SIMULATION_CASH",
            "ACCOUNT_AND_LIFETIME_REALIZED_PNL_RECONCILED",
        ),
    )
    next_ledger = CloseoutLedgerV1(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        source_open_position_state_fingerprint=(
            account.ledger.source_open_position_state_fingerprint
        ),
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = CloseoutAccountV1(
        state=next_state,
        ledger=next_ledger,
    )
    return CloseoutTransitionV1(
        account=next_account,
        event=event,
        closed_trade=closed_trade,
        idempotent_reuse=False,
        reason_codes=("POSITION_CLOSED_SIMULATION_ONLY",),
    )


def apply_closeout_batch_v1(
    account: CloseoutAccountV1,
    fills: Sequence[SimulatedExitFillEvidence],
) -> CloseoutBatchResultV1:
    ordered = tuple(
        sorted(
            fills,
            key=lambda fill: (
                fill.exited_utc,
                fill.exit_fill_fingerprint,
            ),
        )
    )
    current = account
    transitions: list[CloseoutTransitionV1] = []
    for fill in ordered:
        transition = apply_closeout_exit_fill_v1(
            current,
            fill=fill,
        )
        transitions.append(transition)
        current = transition.account
    return CloseoutBatchResultV1(
        account=current,
        ordered_exit_fill_fingerprints=tuple(
            fill.exit_fill_fingerprint for fill in ordered
        ),
        transitions=tuple(transitions),
    )


def replay_closeout_account_v1(
    *,
    source_state: OpenPositionAccountStateV1,
    fills: Sequence[SimulatedExitFillEvidence],
) -> CloseoutBatchResultV1:
    return apply_closeout_batch_v1(
        initialize_closeout_account_v1(source_state=source_state),
        fills,
    )


def verify_closeout_account_replay_v1(
    *,
    account: CloseoutAccountV1,
    source_state: OpenPositionAccountStateV1,
    fills: Sequence[SimulatedExitFillEvidence],
) -> None:
    replay = replay_closeout_account_v1(
        source_state=source_state,
        fills=fills,
    )
    if replay.account.state.state_fingerprint != account.state.state_fingerprint:
        raise CloseoutAccountStateError(
            "closeout state replay fingerprint mismatch"
        )
    if (
        replay.account.ledger.ledger_fingerprint
        != account.ledger.ledger_fingerprint
    ):
        raise CloseoutAccountStateError(
            "closeout ledger replay fingerprint mismatch"
        )
