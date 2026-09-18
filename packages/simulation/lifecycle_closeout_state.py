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
from packages.simulation.closeout_account_state import ClosedTradeV1
from packages.simulation.lifecycle_closeout_contract import (
    LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT,
    LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_exit_fill import (
    LifecycleExitFillEvidenceV1,
    lifecycle_exit_fill_fingerprint,
)
from packages.simulation.lifecycle_exit_fill_contract import (
    LIFECYCLE_EXIT_FILL_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_position_contract import (
    LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_position_state import (
    LifecyclePositionAccountStateV1,
    LifecyclePositionAccountV1,
    lifecycle_position_account_state_fingerprint,
    lifecycle_position_ledger_fingerprint,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1


LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_VERSION = str(
    LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class LifecycleCloseoutAccountError(ValueError):
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
        raise LifecycleCloseoutAccountError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise LifecycleCloseoutAccountError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LifecycleCloseoutAccountError(
            f"{label} must be timezone-aware"
        )


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise LifecycleCloseoutAccountError(
            f"{label} must be finite and nonnegative"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


@dataclass(frozen=True)
class LifecycleClosedTradeV1:
    source_lifecycle_position_state_fingerprint: str
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
                "source lifecycle position state",
                self.source_lifecycle_position_state_fingerprint,
            ),
            ("position", self.position_fingerprint),
            ("exit fill", self.exit_fill_fingerprint),
            ("decision record", self.decision_record_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.opened_utc, label="opened timestamp")
        _require_aware(self.exited_utc, label="exited timestamp")
        if self.exited_utc < self.opened_utc:
            raise LifecycleCloseoutAccountError(
                "lifecycle closed trade exit cannot precede open"
            )
        expected_hold = (self.exited_utc - self.opened_utc).total_seconds()
        if (
            not math.isfinite(self.hold_seconds)
            or self.hold_seconds < 0.0
            or not _same(self.hold_seconds, expected_hold)
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closed-trade hold seconds mismatch"
            )
        if (
            not self.instrument_id.strip()
            or not self.ticker.strip()
            or not self.candidate_identifier.strip()
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closed-trade identity cannot be blank"
            )
        for label, value in (
            ("quantity", self.quantity),
            ("entry price", self.entry_price_per_unit),
            ("contract multiplier", self.contract_multiplier),
            ("entry book value", self.entry_book_value_dollars),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise LifecycleCloseoutAccountError(
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
        for label, value in (
            ("account realized P&L", self.account_realized_pnl_delta_dollars),
            ("lifetime trade net P&L", self.lifetime_trade_net_pnl_dollars),
        ):
            if not math.isfinite(value):
                raise LifecycleCloseoutAccountError(
                    f"{label} must be finite"
                )

        if not _same(
            self.entry_book_value_dollars,
            self.quantity
            * self.entry_price_per_unit
            * self.contract_multiplier,
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closed-trade entry book value mismatch"
            )
        if not _same(
            self.gross_exit_proceeds_dollars,
            self.quantity
            * self.exit_price_per_unit
            * self.contract_multiplier,
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closed-trade gross exit proceeds mismatch"
            )
        if self.exit_fees_dollars > self.gross_exit_proceeds_dollars + _TOLERANCE:
            raise LifecycleCloseoutAccountError(
                "lifecycle closed-trade exit fees exceed gross proceeds"
            )
        if not _same(
            self.net_exit_proceeds_dollars,
            self.gross_exit_proceeds_dollars - self.exit_fees_dollars,
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closed-trade net proceeds mismatch"
            )
        account_realized = (
            self.net_exit_proceeds_dollars
            - self.entry_book_value_dollars
        )
        if not _same(
            self.account_realized_pnl_delta_dollars,
            account_realized,
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle account realized P&L must exclude already-expensed entry fee"
            )
        lifetime = account_realized - self.entry_fees_dollars
        if not _same(self.lifetime_trade_net_pnl_dollars, lifetime):
            raise LifecycleCloseoutAccountError(
                "lifecycle lifetime trade net P&L mismatch"
            )
        if not self.reason_codes:
            raise LifecycleCloseoutAccountError(
                "lifecycle closed trade requires reason codes"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES":
                raise LifecycleCloseoutAccountError(
                    "closed stock quantity unit must be SHARES"
                )
            if not _same(self.contract_multiplier, 1.0):
                raise LifecycleCloseoutAccountError(
                    "closed stock multiplier must equal one"
                )
            if (
                self.option_contract_ticker is not None
                or self.option_contract_type is not None
            ):
                raise LifecycleCloseoutAccountError(
                    "closed stock cannot carry option identity"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS":
                raise LifecycleCloseoutAccountError(
                    "closed option quantity unit must be CONTRACTS"
                )
            if not _same(self.quantity, round(self.quantity)):
                raise LifecycleCloseoutAccountError(
                    "closed option quantity must be integral"
                )
            if (
                not self.option_contract_ticker
                or self.option_contract_type not in {"call", "put"}
            ):
                raise LifecycleCloseoutAccountError(
                    "closed option requires call/put identity"
                )
        else:
            raise LifecycleCloseoutAccountError(
                "unsupported lifecycle closed-trade instrument kind"
            )

    @property
    def closed_trade_fingerprint(self) -> str:
        return lifecycle_closed_trade_fingerprint(self)


@dataclass(frozen=True)
class LifecycleCloseoutAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    source_position_contract_fingerprint: str
    source_position_state_fingerprint: str
    source_position_ledger_fingerprint: str
    as_of_utc: datetime

    initial_equity: float
    cumulative_entry_fees_dollars: float
    cumulative_exit_fees_dollars: float
    cumulative_account_realized_pnl_dollars: float
    cumulative_lifetime_trade_net_pnl_dollars: float
    cash: float
    account_book_equity: float

    stock_reserved_capital: float
    option_reserved_capital: float
    stock_reserved_gross_notional: float
    option_reserved_signed_delta_equivalent_notional: float
    option_reserved_abs_delta_equivalent_notional: float
    option_reserved_max_loss_cash: float
    option_reserved_premium_at_risk: float

    open_entry_book_value_dollars: float
    open_stock_gross_entry_exposure_dollars: float
    open_option_entry_book_value_dollars: float
    open_option_signed_delta_equivalent_entry_reference_dollars: float
    open_option_abs_delta_equivalent_entry_reference_dollars: float
    open_option_premium_at_risk_dollars: float

    stock_reservations: tuple[SimulatedStockReservationV2, ...]
    option_reservations: tuple[SimulatedOptionReservationV2, ...]
    open_positions: tuple[SimulatedOpenPositionV1, ...]
    prior_closed_trades: tuple[ClosedTradeV1, ...]
    lifecycle_closed_trades: tuple[LifecycleClosedTradeV1, ...]

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
            != LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_VERSION
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout contract fingerprint mismatch"
            )
        if (
            self.source_position_contract_fingerprint
            != LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecycleCloseoutAccountError(
                "source lifecycle position contract mismatch"
            )
        for label, value in (
            ("source position state", self.source_position_state_fingerprint),
            ("source position ledger", self.source_position_ledger_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.as_of_utc, label="lifecycle closeout timestamp")
        if not math.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise LifecycleCloseoutAccountError(
                "initial equity must be finite and positive"
            )

        nonnegative = (
            ("cumulative entry fees", self.cumulative_entry_fees_dollars),
            ("cumulative exit fees", self.cumulative_exit_fees_dollars),
            ("cash", self.cash),
            ("account book equity", self.account_book_equity),
            ("stock reserved capital", self.stock_reserved_capital),
            ("option reserved capital", self.option_reserved_capital),
            ("stock reserved gross notional", self.stock_reserved_gross_notional),
            (
                "option reserved absolute delta",
                self.option_reserved_abs_delta_equivalent_notional,
            ),
            ("option reserved max loss", self.option_reserved_max_loss_cash),
            (
                "option reserved premium at risk",
                self.option_reserved_premium_at_risk,
            ),
            ("open entry book value", self.open_entry_book_value_dollars),
            (
                "open stock gross exposure",
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
        )
        for label, value in nonnegative:
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
                "option reserved signed delta",
                self.option_reserved_signed_delta_equivalent_notional,
            ),
            (
                "open option signed delta reference",
                self.open_option_signed_delta_equivalent_entry_reference_dollars,
            ),
        ):
            if not math.isfinite(value):
                raise LifecycleCloseoutAccountError(
                    f"{label} must be finite"
                )

        stocks = tuple(sorted(
            self.stock_reservations,
            key=lambda x: x.decision_record_fingerprint,
        ))
        options = tuple(sorted(
            self.option_reservations,
            key=lambda x: x.decision_record_fingerprint,
        ))
        positions = tuple(sorted(
            self.open_positions,
            key=lambda x: x.decision_record_fingerprint,
        ))
        prior = tuple(sorted(
            self.prior_closed_trades,
            key=lambda x: (x.exited_utc, x.exit_fill_fingerprint),
        ))
        lifecycle = tuple(sorted(
            self.lifecycle_closed_trades,
            key=lambda x: (x.exited_utc, x.exit_fill_fingerprint),
        ))
        if (
            stocks != self.stock_reservations
            or options != self.option_reservations
            or positions != self.open_positions
            or prior != self.prior_closed_trades
            or lifecycle != self.lifecycle_closed_trades
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout collections must be deterministically ordered"
            )

        active_ids = [
            *[x.decision_record_fingerprint for x in stocks],
            *[x.decision_record_fingerprint for x in options],
            *[x.decision_record_fingerprint for x in positions],
        ]
        if len(active_ids) != len(set(active_ids)):
            raise LifecycleCloseoutAccountError(
                "one decision cannot occupy multiple active lifecycle buckets"
            )
        closed_ids = [
            *[x.decision_record_fingerprint for x in prior],
            *[x.decision_record_fingerprint for x in lifecycle],
        ]
        if len(closed_ids) != len(set(closed_ids)):
            raise LifecycleCloseoutAccountError(
                "lifecycle closed history cannot duplicate decision fingerprints"
            )
        if set(active_ids).intersection(closed_ids):
            raise LifecycleCloseoutAccountError(
                "one decision cannot be both active and closed"
            )
        if any(x.reserved_utc > self.as_of_utc for x in stocks + options):
            raise LifecycleCloseoutAccountError(
                "active reservation cannot postdate lifecycle closeout state"
            )
        if any(x.opened_utc > self.as_of_utc for x in positions):
            raise LifecycleCloseoutAccountError(
                "open position cannot postdate lifecycle closeout state"
            )
        if any(x.exited_utc > self.as_of_utc for x in prior + lifecycle):
            raise LifecycleCloseoutAccountError(
                "closed trade cannot postdate lifecycle closeout state"
            )
        if any(
            x.source_lifecycle_position_state_fingerprint
            != self.source_position_state_fingerprint
            for x in lifecycle
        ):
            raise LifecycleCloseoutAccountError(
                "new lifecycle closed trades must bind the immutable source position state"
            )

        checks = (
            (
                self.stock_reserved_capital,
                sum(x.reserved_capital for x in stocks),
                "stock reserved capital",
            ),
            (
                self.option_reserved_capital,
                sum(x.reserved_capital for x in options),
                "option reserved capital",
            ),
            (
                self.stock_reserved_gross_notional,
                sum(x.gross_notional for x in stocks),
                "stock reserved gross notional",
            ),
            (
                self.option_reserved_signed_delta_equivalent_notional,
                sum(x.signed_delta_equivalent_notional for x in options),
                "option reserved signed delta",
            ),
            (
                self.option_reserved_abs_delta_equivalent_notional,
                sum(x.abs_delta_equivalent_notional for x in options),
                "option reserved absolute delta",
            ),
            (
                self.option_reserved_max_loss_cash,
                sum(x.max_loss_cash for x in options),
                "option reserved max loss",
            ),
            (
                self.option_reserved_premium_at_risk,
                sum(x.premium_at_risk for x in options),
                "option reserved premium at risk",
            ),
            (
                self.open_entry_book_value_dollars,
                sum(x.entry_book_value_dollars for x in positions),
                "open entry book value",
            ),
            (
                self.open_stock_gross_entry_exposure_dollars,
                sum(x.stock_gross_entry_exposure_dollars for x in positions),
                "open stock gross exposure",
            ),
            (
                self.open_option_entry_book_value_dollars,
                sum(
                    x.entry_book_value_dollars
                    for x in positions
                    if x.instrument_kind == InstrumentKind.OPTION
                ),
                "open option entry book value",
            ),
            (
                self.open_option_signed_delta_equivalent_entry_reference_dollars,
                sum(
                    x.option_signed_delta_equivalent_entry_reference_dollars
                    for x in positions
                ),
                "open option signed delta reference",
            ),
            (
                self.open_option_abs_delta_equivalent_entry_reference_dollars,
                sum(
                    x.option_abs_delta_equivalent_entry_reference_dollars
                    for x in positions
                ),
                "open option absolute delta reference",
            ),
            (
                self.open_option_premium_at_risk_dollars,
                sum(x.option_premium_at_risk_dollars for x in positions),
                "open option premium at risk",
            ),
            (
                self.cumulative_entry_fees_dollars,
                sum(x.entry_fees_dollars for x in positions)
                + sum(x.entry_fees_dollars for x in prior)
                + sum(x.entry_fees_dollars for x in lifecycle),
                "cumulative entry fees",
            ),
            (
                self.cumulative_exit_fees_dollars,
                sum(x.exit_fees_dollars for x in prior)
                + sum(x.exit_fees_dollars for x in lifecycle),
                "cumulative exit fees",
            ),
            (
                self.cumulative_account_realized_pnl_dollars,
                sum(x.account_realized_pnl_delta_dollars for x in prior)
                + sum(
                    x.account_realized_pnl_delta_dollars
                    for x in lifecycle
                ),
                "cumulative account realized P&L",
            ),
            (
                self.cumulative_lifetime_trade_net_pnl_dollars,
                sum(x.lifetime_trade_net_pnl_dollars for x in prior)
                + sum(x.lifetime_trade_net_pnl_dollars for x in lifecycle),
                "cumulative lifetime trade net P&L",
            ),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise LifecycleCloseoutAccountError(
                    f"{label} must equal constituent sum"
                )

        expected_book = (
            self.initial_equity
            - self.cumulative_entry_fees_dollars
            + self.cumulative_account_realized_pnl_dollars
        )
        if not _same(self.account_book_equity, expected_book):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout book equity mismatch"
            )
        balance = (
            self.cash
            + self.stock_reserved_capital
            + self.option_reserved_capital
            + self.open_entry_book_value_dollars
        )
        if not _same(self.account_book_equity, balance):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout balance reconciliation mismatch"
            )
        if (
            not self.simulation_account_state_mutation
            or not self.simulation_realized_pnl_computation
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout must identify simulation mutation and realized P&L"
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
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout cannot grant provider, broker, order, trading, "
                "promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return lifecycle_closeout_account_state_fingerprint(self)


@dataclass(frozen=True)
class LifecycleCloseoutLedgerEventV1:
    sequence: int
    occurred_utc: datetime
    position_fingerprint: str
    exit_fill_fingerprint: str
    decision_record_fingerprint: str
    instrument_kind: InstrumentKind
    cash_delta_dollars: float
    open_entry_book_value_delta_dollars: float
    exit_fee_delta_dollars: float
    account_realized_pnl_delta_dollars: float
    lifetime_trade_net_pnl_dollars: float
    before_state_fingerprint: str
    after_state_fingerprint: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout sequence must be positive"
            )
        _require_aware(self.occurred_utc, label="closeout event timestamp")
        for label, value in (
            ("position", self.position_fingerprint),
            ("exit fill", self.exit_fill_fingerprint),
            ("decision", self.decision_record_fingerprint),
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
        )
        if not all(math.isfinite(x) for x in values):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout event deltas must be finite"
            )
        if self.cash_delta_dollars < -_TOLERANCE:
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout cash delta cannot be negative"
            )
        if self.open_entry_book_value_delta_dollars >= 0.0:
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout must remove open entry book value"
            )
        if self.exit_fee_delta_dollars < 0.0:
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout exit fee delta cannot be negative"
            )
        if not self.reason_codes:
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout event requires reason codes"
            )

    @property
    def event_fingerprint(self) -> str:
        return lifecycle_closeout_ledger_event_fingerprint(self)


@dataclass(frozen=True)
class LifecycleCloseoutLedgerV1:
    contract_version: str
    contract_fingerprint: str
    source_position_state_fingerprint: str
    source_position_ledger_fingerprint: str
    initial_state_fingerprint: str
    events: tuple[LifecycleCloseoutLedgerEventV1, ...]

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_VERSION
            or self.contract_fingerprint
            != LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout ledger contract mismatch"
            )
        for label, value in (
            ("source position state", self.source_position_state_fingerprint),
            ("source position ledger", self.source_position_ledger_fingerprint),
            ("initial state", self.initial_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        previous = self.initial_state_fingerprint
        previous_time: datetime | None = None
        positions: set[str] = set()
        fills: set[str] = set()
        for sequence, event in enumerate(self.events, start=1):
            if event.sequence != sequence:
                raise LifecycleCloseoutAccountError(
                    "lifecycle closeout sequence must be contiguous"
                )
            if (
                previous_time is not None
                and event.occurred_utc < previous_time
            ):
                raise LifecycleCloseoutAccountError(
                    "lifecycle closeout events must be chronological"
                )
            if event.before_state_fingerprint != previous:
                raise LifecycleCloseoutAccountError(
                    "lifecycle closeout state chain is broken"
                )
            if event.position_fingerprint in positions:
                raise LifecycleCloseoutAccountError(
                    "one lifecycle position can close only once"
                )
            if event.exit_fill_fingerprint in fills:
                raise LifecycleCloseoutAccountError(
                    "one lifecycle exit fill can apply only once"
                )
            positions.add(event.position_fingerprint)
            fills.add(event.exit_fill_fingerprint)
            previous = event.after_state_fingerprint
            previous_time = event.occurred_utc

    @property
    def ledger_fingerprint(self) -> str:
        return lifecycle_closeout_ledger_fingerprint(self)


@dataclass(frozen=True)
class LifecycleCloseoutAccountV1:
    state: LifecycleCloseoutAccountStateV1
    ledger: LifecycleCloseoutLedgerV1

    def __post_init__(self) -> None:
        if (
            self.state.source_position_state_fingerprint
            != self.ledger.source_position_state_fingerprint
            or self.state.source_position_ledger_fingerprint
            != self.ledger.source_position_ledger_fingerprint
        ):
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout state and ledger source lineage mismatch"
            )
        expected = (
            self.ledger.events[-1].after_state_fingerprint
            if self.ledger.events
            else self.ledger.initial_state_fingerprint
        )
        if self.state.state_fingerprint != expected:
            raise LifecycleCloseoutAccountError(
                "lifecycle closeout state must match latest ledger state"
            )


@dataclass(frozen=True)
class LifecycleCloseoutTransitionV1:
    account: LifecycleCloseoutAccountV1
    event: LifecycleCloseoutLedgerEventV1 | None
    closed_trade: LifecycleClosedTradeV1
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class LifecycleCloseoutBatchResultV1:
    account: LifecycleCloseoutAccountV1
    ordered_exit_fill_fingerprints: tuple[str, ...]
    transitions: tuple[LifecycleCloseoutTransitionV1, ...]


def lifecycle_closed_trade_fingerprint(
    trade: LifecycleClosedTradeV1,
) -> str:
    return _fingerprint_payload(trade)


def lifecycle_closeout_account_state_fingerprint(
    state: LifecycleCloseoutAccountStateV1,
) -> str:
    return _fingerprint_payload(state)


def lifecycle_closeout_ledger_event_fingerprint(
    event: LifecycleCloseoutLedgerEventV1,
) -> str:
    return _fingerprint_payload(event)


def lifecycle_closeout_ledger_fingerprint(
    ledger: LifecycleCloseoutLedgerV1,
) -> str:
    return _fingerprint_payload(ledger)


def _validate_source(source: LifecyclePositionAccountV1) -> None:
    if (
        source.state.contract_fingerprint
        != LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise LifecycleCloseoutAccountError(
            "source must use accepted lifecycle position contract"
        )
    if (
        source.state.state_fingerprint
        != lifecycle_position_account_state_fingerprint(source.state)
    ):
        raise LifecycleCloseoutAccountError(
            "source lifecycle position state fingerprint mismatch"
        )
    if (
        source.ledger.ledger_fingerprint
        != lifecycle_position_ledger_fingerprint(source.ledger)
    ):
        raise LifecycleCloseoutAccountError(
            "source lifecycle position ledger fingerprint mismatch"
        )
    expected = (
        source.ledger.events[-1].after_state_fingerprint
        if source.ledger.events
        else source.ledger.initial_state_fingerprint
    )
    if expected != source.state.state_fingerprint:
        raise LifecycleCloseoutAccountError(
            "source lifecycle position ledger does not terminate at state"
        )


def initialize_lifecycle_closeout_account_v1(
    *,
    source: LifecyclePositionAccountV1,
) -> LifecycleCloseoutAccountV1:
    _validate_source(source)
    item = source.state
    state = LifecycleCloseoutAccountStateV1(
        contract_version=LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT,
        source_position_contract_fingerprint=item.contract_fingerprint,
        source_position_state_fingerprint=item.state_fingerprint,
        source_position_ledger_fingerprint=source.ledger.ledger_fingerprint,
        as_of_utc=item.as_of_utc,
        initial_equity=item.initial_equity,
        cumulative_entry_fees_dollars=item.cumulative_entry_fees_dollars,
        cumulative_exit_fees_dollars=item.cumulative_exit_fees_dollars,
        cumulative_account_realized_pnl_dollars=(
            item.cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            item.cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=item.cash,
        account_book_equity=item.account_book_equity,
        stock_reserved_capital=item.stock_reserved_capital,
        option_reserved_capital=item.option_reserved_capital,
        stock_reserved_gross_notional=item.stock_reserved_gross_notional,
        option_reserved_signed_delta_equivalent_notional=(
            item.option_reserved_signed_delta_equivalent_notional
        ),
        option_reserved_abs_delta_equivalent_notional=(
            item.option_reserved_abs_delta_equivalent_notional
        ),
        option_reserved_max_loss_cash=item.option_reserved_max_loss_cash,
        option_reserved_premium_at_risk=item.option_reserved_premium_at_risk,
        open_entry_book_value_dollars=item.open_entry_book_value_dollars,
        open_stock_gross_entry_exposure_dollars=(
            item.open_stock_gross_entry_exposure_dollars
        ),
        open_option_entry_book_value_dollars=(
            item.open_option_entry_book_value_dollars
        ),
        open_option_signed_delta_equivalent_entry_reference_dollars=(
            item.open_option_signed_delta_equivalent_entry_reference_dollars
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=(
            item.open_option_abs_delta_equivalent_entry_reference_dollars
        ),
        open_option_premium_at_risk_dollars=(
            item.open_option_premium_at_risk_dollars
        ),
        stock_reservations=item.stock_reservations,
        option_reservations=item.option_reservations,
        open_positions=item.open_positions,
        prior_closed_trades=item.closed_trades,
        lifecycle_closed_trades=(),
    )
    ledger = LifecycleCloseoutLedgerV1(
        contract_version=LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT,
        source_position_state_fingerprint=item.state_fingerprint,
        source_position_ledger_fingerprint=source.ledger.ledger_fingerprint,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return LifecycleCloseoutAccountV1(state=state, ledger=ledger)


def _build_state(
    *,
    previous: LifecycleCloseoutAccountStateV1,
    as_of_utc: datetime,
    cash: float,
    cumulative_exit_fees_dollars: float,
    cumulative_account_realized_pnl_dollars: float,
    cumulative_lifetime_trade_net_pnl_dollars: float,
    open_positions: Sequence[SimulatedOpenPositionV1],
    lifecycle_closed_trades: Sequence[LifecycleClosedTradeV1],
) -> LifecycleCloseoutAccountStateV1:
    positions = tuple(sorted(
        open_positions,
        key=lambda x: x.decision_record_fingerprint,
    ))
    lifecycle = tuple(sorted(
        lifecycle_closed_trades,
        key=lambda x: (x.exited_utc, x.exit_fill_fingerprint),
    ))
    return LifecycleCloseoutAccountStateV1(
        contract_version=previous.contract_version,
        contract_fingerprint=previous.contract_fingerprint,
        source_position_contract_fingerprint=(
            previous.source_position_contract_fingerprint
        ),
        source_position_state_fingerprint=(
            previous.source_position_state_fingerprint
        ),
        source_position_ledger_fingerprint=(
            previous.source_position_ledger_fingerprint
        ),
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        cumulative_entry_fees_dollars=previous.cumulative_entry_fees_dollars,
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
        account_book_equity=_zero(
            previous.initial_equity
            - previous.cumulative_entry_fees_dollars
            + cumulative_account_realized_pnl_dollars
        ),
        stock_reserved_capital=previous.stock_reserved_capital,
        option_reserved_capital=previous.option_reserved_capital,
        stock_reserved_gross_notional=previous.stock_reserved_gross_notional,
        option_reserved_signed_delta_equivalent_notional=(
            previous.option_reserved_signed_delta_equivalent_notional
        ),
        option_reserved_abs_delta_equivalent_notional=(
            previous.option_reserved_abs_delta_equivalent_notional
        ),
        option_reserved_max_loss_cash=previous.option_reserved_max_loss_cash,
        option_reserved_premium_at_risk=previous.option_reserved_premium_at_risk,
        open_entry_book_value_dollars=_zero(
            sum(x.entry_book_value_dollars for x in positions)
        ),
        open_stock_gross_entry_exposure_dollars=_zero(
            sum(x.stock_gross_entry_exposure_dollars for x in positions)
        ),
        open_option_entry_book_value_dollars=_zero(
            sum(
                x.entry_book_value_dollars
                for x in positions
                if x.instrument_kind == InstrumentKind.OPTION
            )
        ),
        open_option_signed_delta_equivalent_entry_reference_dollars=_zero(
            sum(
                x.option_signed_delta_equivalent_entry_reference_dollars
                for x in positions
            )
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=_zero(
            sum(
                x.option_abs_delta_equivalent_entry_reference_dollars
                for x in positions
            )
        ),
        open_option_premium_at_risk_dollars=_zero(
            sum(x.option_premium_at_risk_dollars for x in positions)
        ),
        stock_reservations=previous.stock_reservations,
        option_reservations=previous.option_reservations,
        open_positions=positions,
        prior_closed_trades=previous.prior_closed_trades,
        lifecycle_closed_trades=lifecycle,
    )


def _validate_fill_lineage(
    *,
    account: LifecycleCloseoutAccountV1,
    fill: LifecycleExitFillEvidenceV1,
    position: SimulatedOpenPositionV1,
) -> None:
    if fill.contract_fingerprint != LIFECYCLE_EXIT_FILL_CONTRACT_FINGERPRINT:
        raise LifecycleCloseoutAccountError(
            "lifecycle exit-fill contract fingerprint mismatch"
        )
    if fill.exit_fill_fingerprint != lifecycle_exit_fill_fingerprint(fill):
        raise LifecycleCloseoutAccountError(
            "lifecycle exit-fill fingerprint mismatch"
        )
    if (
        fill.source_position_state_fingerprint
        != account.state.source_position_state_fingerprint
    ):
        raise LifecycleCloseoutAccountError(
            "exit fill must bind immutable lifecycle position source state"
        )
    if fill.position_fingerprint != position.position_fingerprint:
        raise LifecycleCloseoutAccountError(
            "lifecycle exit position fingerprint mismatch"
        )
    pairs = (
        (
            fill.source_account_state_fingerprint,
            position.source_account_state_fingerprint,
            "source account",
        ),
        (
            fill.decision_record_fingerprint,
            position.decision_record_fingerprint,
            "decision",
        ),
        (fill.candidate_fingerprint, position.candidate_fingerprint, "candidate"),
        (fill.entry_fill_fingerprint, position.fill_fingerprint, "entry fill"),
        (
            fill.funding_terms_fingerprint,
            position.funding_terms_fingerprint,
            "funding",
        ),
        (
            fill.reservation_fingerprint,
            position.reservation_fingerprint,
            "reservation",
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
            "option ticker",
        ),
        (
            fill.option_contract_type,
            position.option_contract_type,
            "option type",
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
        (fill.opened_utc, position.opened_utc, "opened timestamp"),
        (fill.quantity_unit, position.quantity_unit, "quantity unit"),
    )
    for left, right, label in pairs:
        if left != right:
            raise LifecycleCloseoutAccountError(
                f"lifecycle exit {label} lineage mismatch"
            )
    if not _same(fill.quantity, position.quantity):
        raise LifecycleCloseoutAccountError(
            "lifecycle exit quantity lineage mismatch"
        )
    if not _same(fill.contract_multiplier, position.contract_multiplier):
        raise LifecycleCloseoutAccountError(
            "lifecycle exit multiplier lineage mismatch"
        )


def _closed_trade(
    *,
    account: LifecycleCloseoutAccountV1,
    position: SimulatedOpenPositionV1,
    fill: LifecycleExitFillEvidenceV1,
) -> LifecycleClosedTradeV1:
    realized = fill.net_exit_proceeds_dollars - position.entry_book_value_dollars
    lifetime = realized - position.entry_fees_dollars
    return LifecycleClosedTradeV1(
        source_lifecycle_position_state_fingerprint=(
            account.state.source_position_state_fingerprint
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
        hold_seconds=(fill.exited_utc - position.opened_utc).total_seconds(),
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
        account_realized_pnl_delta_dollars=realized,
        lifetime_trade_net_pnl_dollars=lifetime,
        reason_codes=(
            "EXACT_LIFECYCLE_POSITION_EXIT_FILL_LINEAGE",
            "ENTRY_FEE_ALREADY_EXPENSED_ACCOUNT_PNL_EXCLUDES_RECHARGE",
            "LIFETIME_TRADE_NET_PNL_INCLUDES_ENTRY_AND_EXIT_FEES_ONCE",
            "PRIOR_CLOSED_HISTORY_PRESERVED_SEPARATELY",
        ),
    )


def apply_lifecycle_closeout_v1(
    account: LifecycleCloseoutAccountV1,
    *,
    fill: LifecycleExitFillEvidenceV1,
) -> LifecycleCloseoutTransitionV1:
    duplicate = tuple(
        x
        for x in account.state.lifecycle_closed_trades
        if x.exit_fill_fingerprint == fill.exit_fill_fingerprint
    )
    if duplicate:
        if len(duplicate) != 1:
            raise LifecycleCloseoutAccountError(
                "duplicate lifecycle exit-fill fingerprint in closed history"
            )
        return LifecycleCloseoutTransitionV1(
            account=account,
            event=None,
            closed_trade=duplicate[0],
            idempotent_reuse=True,
            reason_codes=("DUPLICATE_LIFECYCLE_EXIT_IDEMPOTENT_REUSE",),
        )

    if any(
        x.position_fingerprint == fill.position_fingerprint
        for x in account.state.lifecycle_closed_trades
    ):
        raise LifecycleCloseoutAccountError(
            "conflicting second lifecycle close for already-closed position"
        )
    if fill.exited_utc < account.state.as_of_utc:
        raise LifecycleCloseoutAccountError(
            "lifecycle exit timestamp cannot precede current closeout state"
        )
    matches = tuple(
        x
        for x in account.state.open_positions
        if x.position_fingerprint == fill.position_fingerprint
    )
    if len(matches) != 1:
        raise LifecycleCloseoutAccountError(
            "exact current lifecycle open position is required"
        )
    position = matches[0]
    _validate_fill_lineage(
        account=account,
        fill=fill,
        position=position,
    )
    trade = _closed_trade(
        account=account,
        position=position,
        fill=fill,
    )
    remaining = tuple(
        x
        for x in account.state.open_positions
        if x.position_fingerprint != position.position_fingerprint
    )
    next_state = _build_state(
        previous=account.state,
        as_of_utc=fill.exited_utc,
        cash=account.state.cash + fill.net_exit_proceeds_dollars,
        cumulative_exit_fees_dollars=(
            account.state.cumulative_exit_fees_dollars
            + fill.exit_fees_dollars
        ),
        cumulative_account_realized_pnl_dollars=(
            account.state.cumulative_account_realized_pnl_dollars
            + trade.account_realized_pnl_delta_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            account.state.cumulative_lifetime_trade_net_pnl_dollars
            + trade.lifetime_trade_net_pnl_dollars
        ),
        open_positions=remaining,
        lifecycle_closed_trades=(
            account.state.lifecycle_closed_trades + (trade,)
        ),
    )
    event = LifecycleCloseoutLedgerEventV1(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=fill.exited_utc,
        position_fingerprint=position.position_fingerprint,
        exit_fill_fingerprint=fill.exit_fill_fingerprint,
        decision_record_fingerprint=position.decision_record_fingerprint,
        instrument_kind=position.instrument_kind,
        cash_delta_dollars=fill.net_exit_proceeds_dollars,
        open_entry_book_value_delta_dollars=-position.entry_book_value_dollars,
        exit_fee_delta_dollars=fill.exit_fees_dollars,
        account_realized_pnl_delta_dollars=(
            trade.account_realized_pnl_delta_dollars
        ),
        lifetime_trade_net_pnl_dollars=trade.lifetime_trade_net_pnl_dollars,
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
        reason_codes=(
            "MATCHED_LIFECYCLE_POSITION_REMOVED_ONCE",
            "NET_EXIT_PROCEEDS_RETURNED_TO_LIFECYCLE_CASH",
            "PRIOR_CLOSED_HISTORY_PRESERVED",
            "ACCOUNT_AND_LIFETIME_REALIZED_PNL_RECONCILED",
        ),
    )
    next_ledger = LifecycleCloseoutLedgerV1(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        source_position_state_fingerprint=(
            account.ledger.source_position_state_fingerprint
        ),
        source_position_ledger_fingerprint=(
            account.ledger.source_position_ledger_fingerprint
        ),
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = LifecycleCloseoutAccountV1(
        state=next_state,
        ledger=next_ledger,
    )
    return LifecycleCloseoutTransitionV1(
        account=next_account,
        event=event,
        closed_trade=trade,
        idempotent_reuse=False,
        reason_codes=("LIFECYCLE_POSITION_CLOSED_SIMULATION_ONLY",),
    )


def apply_lifecycle_closeout_batch_v1(
    account: LifecycleCloseoutAccountV1,
    fills: Sequence[LifecycleExitFillEvidenceV1],
) -> LifecycleCloseoutBatchResultV1:
    ordered = tuple(sorted(
        fills,
        key=lambda x: (x.exited_utc, x.exit_fill_fingerprint),
    ))
    current = account
    transitions: list[LifecycleCloseoutTransitionV1] = []
    for fill in ordered:
        transition = apply_lifecycle_closeout_v1(current, fill=fill)
        transitions.append(transition)
        current = transition.account
    return LifecycleCloseoutBatchResultV1(
        account=current,
        ordered_exit_fill_fingerprints=tuple(
            x.exit_fill_fingerprint for x in ordered
        ),
        transitions=tuple(transitions),
    )


def replay_lifecycle_closeout_account_v1(
    *,
    source: LifecyclePositionAccountV1,
    fills: Sequence[LifecycleExitFillEvidenceV1],
) -> LifecycleCloseoutBatchResultV1:
    return apply_lifecycle_closeout_batch_v1(
        initialize_lifecycle_closeout_account_v1(source=source),
        fills,
    )


def verify_lifecycle_closeout_account_replay_v1(
    *,
    account: LifecycleCloseoutAccountV1,
    source: LifecyclePositionAccountV1,
    fills: Sequence[LifecycleExitFillEvidenceV1],
) -> None:
    replay = replay_lifecycle_closeout_account_v1(
        source=source,
        fills=fills,
    )
    if replay.account.state.state_fingerprint != account.state.state_fingerprint:
        raise LifecycleCloseoutAccountError(
            "lifecycle closeout replay state fingerprint mismatch"
        )
    if replay.account.ledger.ledger_fingerprint != account.ledger.ledger_fingerprint:
        raise LifecycleCloseoutAccountError(
            "lifecycle closeout replay ledger fingerprint mismatch"
        )
