from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2 import (
    SimulatedOptionReservationV2,
    SimulatedStockReservationV2,
)
from packages.simulation.closeout_account_state import (
    ClosedTradeV1,
    closed_trade_fingerprint,
)
from packages.simulation.lifecycle_closeout_contract import (
    LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_closeout_state import (
    LifecycleClosedTradeV1,
    LifecycleCloseoutAccountV1,
    lifecycle_closed_trade_fingerprint,
    lifecycle_closeout_account_state_fingerprint,
    lifecycle_closeout_ledger_fingerprint,
)
from packages.simulation.lifecycle_position_contract import (
    LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.open_position_state import (
    SimulatedOpenPositionV1,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT,
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)


RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION = str(
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class RecurrentLifecycleAccountError(ValueError):
    pass


class RecurrentClosedTradeOrigin(StrEnum):
    ORIGINAL_CLOSEOUT_V1 = "ORIGINAL_CLOSEOUT_V1"
    LIFECYCLE_CLOSEOUT_V1 = "LIFECYCLE_CLOSEOUT_V1"


class RecurrentLifecycleEventKind(StrEnum):
    RESERVE_STOCK = "RESERVE_STOCK"
    RESERVE_OPTION = "RESERVE_OPTION"
    ABSTAIN = "ABSTAIN"
    REJECT_MISSING_OPTION_TERMS = "REJECT_MISSING_OPTION_TERMS"
    REJECT_INSUFFICIENT_CAPITAL = "REJECT_INSUFFICIENT_CAPITAL"
    OPEN_POSITION = "OPEN_POSITION"
    CLOSE_POSITION = "CLOSE_POSITION"


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
        raise RecurrentLifecycleAccountError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise RecurrentLifecycleAccountError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentLifecycleAccountError(
            f"{label} must be timezone-aware"
        )


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise RecurrentLifecycleAccountError(
            f"{label} must be finite and nonnegative"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class RecurrentClosedTradeV1:
    origin: RecurrentClosedTradeOrigin
    source_state_contract_fingerprint: str
    source_state_fingerprint: str
    source_record_fingerprint: str

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
            ("source state contract", self.source_state_contract_fingerprint),
            ("source state", self.source_state_fingerprint),
            ("source record", self.source_record_fingerprint),
            ("position", self.position_fingerprint),
            ("exit fill", self.exit_fill_fingerprint),
            ("decision record", self.decision_record_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        if self.origin == RecurrentClosedTradeOrigin.ORIGINAL_CLOSEOUT_V1:
            if (
                self.source_state_contract_fingerprint
                != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
            ):
                raise RecurrentLifecycleAccountError(
                    "original closeout provenance contract mismatch"
                )
        elif self.origin == RecurrentClosedTradeOrigin.LIFECYCLE_CLOSEOUT_V1:
            if (
                self.source_state_contract_fingerprint
                != LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT
            ):
                raise RecurrentLifecycleAccountError(
                    "lifecycle closeout provenance contract mismatch"
                )
        else:
            raise RecurrentLifecycleAccountError(
                "unsupported recurrent closed-trade origin"
            )

        _require_aware(self.opened_utc, label="trade opened timestamp")
        _require_aware(self.exited_utc, label="trade exited timestamp")
        if self.exited_utc < self.opened_utc:
            raise RecurrentLifecycleAccountError(
                "closed trade exit cannot precede open"
            )
        expected_hold = (self.exited_utc - self.opened_utc).total_seconds()
        if (
            not math.isfinite(self.hold_seconds)
            or self.hold_seconds < 0.0
            or not _same(self.hold_seconds, expected_hold)
        ):
            raise RecurrentLifecycleAccountError(
                "closed-trade hold seconds mismatch"
            )
        if (
            not self.instrument_id.strip()
            or not self.ticker.strip()
            or not self.candidate_identifier.strip()
        ):
            raise RecurrentLifecycleAccountError(
                "closed-trade identity cannot be blank"
            )
        for label, value in (
            ("quantity", self.quantity),
            ("entry price", self.entry_price_per_unit),
            ("contract multiplier", self.contract_multiplier),
            ("entry book value", self.entry_book_value_dollars),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise RecurrentLifecycleAccountError(
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
                raise RecurrentLifecycleAccountError(
                    f"{label} must be finite"
                )

        expected_entry = (
            self.quantity
            * self.entry_price_per_unit
            * self.contract_multiplier
        )
        expected_gross = (
            self.quantity
            * self.exit_price_per_unit
            * self.contract_multiplier
        )
        expected_net = expected_gross - self.exit_fees_dollars
        expected_realized = expected_net - expected_entry
        expected_lifetime = expected_realized - self.entry_fees_dollars
        checks = (
            (self.entry_book_value_dollars, expected_entry, "entry book value"),
            (self.gross_exit_proceeds_dollars, expected_gross, "gross exit proceeds"),
            (self.net_exit_proceeds_dollars, expected_net, "net exit proceeds"),
            (
                self.account_realized_pnl_delta_dollars,
                expected_realized,
                "account realized P&L",
            ),
            (
                self.lifetime_trade_net_pnl_dollars,
                expected_lifetime,
                "lifetime trade net P&L",
            ),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise RecurrentLifecycleAccountError(
                    f"recurrent closed-trade {label} mismatch"
                )
        if self.exit_fees_dollars > self.gross_exit_proceeds_dollars + _TOLERANCE:
            raise RecurrentLifecycleAccountError(
                "closed-trade exit fees cannot exceed gross proceeds"
            )
        if not self.reason_codes:
            raise RecurrentLifecycleAccountError(
                "recurrent closed trade requires reason codes"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES":
                raise RecurrentLifecycleAccountError(
                    "closed stock quantity unit must be SHARES"
                )
            if not _same(self.contract_multiplier, 1.0):
                raise RecurrentLifecycleAccountError(
                    "closed stock multiplier must equal one"
                )
            if (
                self.option_contract_ticker is not None
                or self.option_contract_type is not None
            ):
                raise RecurrentLifecycleAccountError(
                    "closed stock cannot carry option identity"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS":
                raise RecurrentLifecycleAccountError(
                    "closed option quantity unit must be CONTRACTS"
                )
            if not _same(self.quantity, round(self.quantity)):
                raise RecurrentLifecycleAccountError(
                    "closed option quantity must be integral"
                )
            if (
                not self.option_contract_ticker
                or self.option_contract_type not in {"call", "put"}
            ):
                raise RecurrentLifecycleAccountError(
                    "closed option requires call/put identity"
                )
        else:
            raise RecurrentLifecycleAccountError(
                "unsupported recurrent closed-trade instrument kind"
            )

    @property
    def history_fingerprint(self) -> str:
        return recurrent_closed_trade_fingerprint(self)


@dataclass(frozen=True)
class RecurrentLifecycleAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    bootstrap_contract_fingerprint: str
    bootstrap_state_fingerprint: str
    bootstrap_ledger_fingerprint: str
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
    closed_trades: tuple[RecurrentClosedTradeV1, ...]

    stable_repeated_cycle_contract: bool = True
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
        if self.contract_version != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION:
            raise RecurrentLifecycleAccountError(
                "recurrent lifecycle contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise RecurrentLifecycleAccountError(
                "recurrent lifecycle contract fingerprint mismatch"
            )
        if (
            self.bootstrap_contract_fingerprint
            != LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise RecurrentLifecycleAccountError(
                "recurrent lifecycle bootstrap contract mismatch"
            )
        for label, value in (
            ("bootstrap state", self.bootstrap_state_fingerprint),
            ("bootstrap ledger", self.bootstrap_ledger_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.as_of_utc, label="recurrent account timestamp")
        if not math.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise RecurrentLifecycleAccountError(
                "initial equity must be finite and positive"
            )
        if not self.stable_repeated_cycle_contract:
            raise RecurrentLifecycleAccountError(
                "recurrent account must identify stable-cycle semantics"
            )

        for label, value in (
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
                "option reserved signed delta",
                self.option_reserved_signed_delta_equivalent_notional,
            ),
            (
                "open option signed delta reference",
                self.open_option_signed_delta_equivalent_entry_reference_dollars,
            ),
        ):
            if not math.isfinite(value):
                raise RecurrentLifecycleAccountError(
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
        closed = tuple(sorted(
            self.closed_trades,
            key=lambda x: (x.exited_utc, x.exit_fill_fingerprint),
        ))
        if (
            stocks != self.stock_reservations
            or options != self.option_reservations
            or positions != self.open_positions
            or closed != self.closed_trades
        ):
            raise RecurrentLifecycleAccountError(
                "recurrent lifecycle collections must be deterministically ordered"
            )

        active_ids = [
            *[x.decision_record_fingerprint for x in stocks],
            *[x.decision_record_fingerprint for x in options],
            *[x.decision_record_fingerprint for x in positions],
        ]
        closed_ids = [x.decision_record_fingerprint for x in closed]
        if len(active_ids) != len(set(active_ids)):
            raise RecurrentLifecycleAccountError(
                "one decision cannot occupy multiple active recurrent buckets"
            )
        if len(closed_ids) != len(set(closed_ids)):
            raise RecurrentLifecycleAccountError(
                "recurrent closed history cannot duplicate decision fingerprints"
            )
        if set(active_ids).intersection(closed_ids):
            raise RecurrentLifecycleAccountError(
                "one decision cannot be active and closed"
            )
        if any(x.reserved_utc > self.as_of_utc for x in stocks + options):
            raise RecurrentLifecycleAccountError(
                "reservation cannot postdate recurrent state"
            )
        if any(x.opened_utc > self.as_of_utc for x in positions):
            raise RecurrentLifecycleAccountError(
                "open position cannot postdate recurrent state"
            )
        if any(x.exited_utc > self.as_of_utc for x in closed):
            raise RecurrentLifecycleAccountError(
                "closed trade cannot postdate recurrent state"
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
                + sum(x.entry_fees_dollars for x in closed),
                "cumulative entry fees",
            ),
            (
                self.cumulative_exit_fees_dollars,
                sum(x.exit_fees_dollars for x in closed),
                "cumulative exit fees",
            ),
            (
                self.cumulative_account_realized_pnl_dollars,
                sum(x.account_realized_pnl_delta_dollars for x in closed),
                "cumulative account realized P&L",
            ),
            (
                self.cumulative_lifetime_trade_net_pnl_dollars,
                sum(x.lifetime_trade_net_pnl_dollars for x in closed),
                "cumulative lifetime trade net P&L",
            ),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise RecurrentLifecycleAccountError(
                    f"{label} must equal constituent sum"
                )
        if not _same(
            self.option_reserved_max_loss_cash,
            self.option_reserved_capital,
        ):
            raise RecurrentLifecycleAccountError(
                "option max-loss total must equal option reserved capital"
            )
        expected_book = (
            self.initial_equity
            - self.cumulative_entry_fees_dollars
            + self.cumulative_account_realized_pnl_dollars
        )
        if not _same(self.account_book_equity, expected_book):
            raise RecurrentLifecycleAccountError(
                "recurrent account book equity mismatch"
            )
        balance = (
            self.cash
            + self.stock_reserved_capital
            + self.option_reserved_capital
            + self.open_entry_book_value_dollars
        )
        if not _same(self.account_book_equity, balance):
            raise RecurrentLifecycleAccountError(
                "recurrent account balance reconciliation mismatch"
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
            raise RecurrentLifecycleAccountError(
                "recurrent account cannot grant provider, broker, order, trading, "
                "promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return recurrent_lifecycle_account_state_fingerprint(self)


@dataclass(frozen=True)
class RecurrentLifecycleLedgerEventV1:
    sequence: int
    occurred_utc: datetime
    kind: RecurrentLifecycleEventKind
    decision_record_fingerprint: str | None
    reservation_fingerprint: str | None
    reservation_terms_fingerprint: str | None
    option_economics_result_fingerprint: str | None
    fill_fingerprint: str | None
    funding_terms_fingerprint: str | None
    position_fingerprint: str | None
    exit_fill_fingerprint: str | None
    closed_trade_fingerprint: str | None
    candidate_identifier: str | None
    option_contract_ticker: str | None
    instrument_id: str | None
    ticker: str | None
    direction: str | None

    cash_delta_dollars: float
    stock_reserved_capital_delta_dollars: float
    option_reserved_capital_delta_dollars: float
    stock_reserved_gross_notional_delta_dollars: float
    option_reserved_signed_delta_delta_dollars: float
    option_reserved_abs_delta_delta_dollars: float
    option_reserved_max_loss_delta_dollars: float
    option_reserved_premium_at_risk_delta_dollars: float
    open_entry_book_value_delta_dollars: float
    entry_fee_delta_dollars: float
    exit_fee_delta_dollars: float
    account_realized_pnl_delta_dollars: float
    lifetime_trade_net_pnl_delta_dollars: float
    open_stock_gross_exposure_delta_dollars: float
    open_option_signed_delta_reference_delta_dollars: float
    open_option_abs_delta_reference_delta_dollars: float
    open_option_premium_at_risk_delta_dollars: float

    before_state_fingerprint: str
    after_state_fingerprint: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise RecurrentLifecycleAccountError(
                "recurrent ledger sequence must be positive"
            )
        _require_aware(self.occurred_utc, label="recurrent ledger timestamp")
        for label, value in (
            ("before state", self.before_state_fingerprint),
            ("after state", self.after_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        for label, value in (
            ("decision record", self.decision_record_fingerprint),
            ("reservation", self.reservation_fingerprint),
            ("reservation terms", self.reservation_terms_fingerprint),
            ("option economics", self.option_economics_result_fingerprint),
            ("fill", self.fill_fingerprint),
            ("funding terms", self.funding_terms_fingerprint),
            ("position", self.position_fingerprint),
            ("exit fill", self.exit_fill_fingerprint),
            ("closed trade", self.closed_trade_fingerprint),
        ):
            if value is not None:
                _require_fingerprint(value, label=f"{label} fingerprint")
        deltas = (
            self.cash_delta_dollars,
            self.stock_reserved_capital_delta_dollars,
            self.option_reserved_capital_delta_dollars,
            self.stock_reserved_gross_notional_delta_dollars,
            self.option_reserved_signed_delta_delta_dollars,
            self.option_reserved_abs_delta_delta_dollars,
            self.option_reserved_max_loss_delta_dollars,
            self.option_reserved_premium_at_risk_delta_dollars,
            self.open_entry_book_value_delta_dollars,
            self.entry_fee_delta_dollars,
            self.exit_fee_delta_dollars,
            self.account_realized_pnl_delta_dollars,
            self.lifetime_trade_net_pnl_delta_dollars,
            self.open_stock_gross_exposure_delta_dollars,
            self.open_option_signed_delta_reference_delta_dollars,
            self.open_option_abs_delta_reference_delta_dollars,
            self.open_option_premium_at_risk_delta_dollars,
        )
        if not all(math.isfinite(x) for x in deltas):
            raise RecurrentLifecycleAccountError(
                "recurrent ledger deltas must be finite"
            )
        if not self.reason_codes:
            raise RecurrentLifecycleAccountError(
                "recurrent ledger event requires reason codes"
            )

    @property
    def event_fingerprint(self) -> str:
        return recurrent_lifecycle_ledger_event_fingerprint(self)


@dataclass(frozen=True)
class RecurrentLifecycleLedgerV1:
    contract_version: str
    contract_fingerprint: str
    bootstrap_state_fingerprint: str
    bootstrap_ledger_fingerprint: str
    initial_state_fingerprint: str
    events: tuple[RecurrentLifecycleLedgerEventV1, ...]

    def __post_init__(self) -> None:
        if self.contract_version != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION:
            raise RecurrentLifecycleAccountError(
                "recurrent ledger contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise RecurrentLifecycleAccountError(
                "recurrent ledger contract fingerprint mismatch"
            )
        for label, value in (
            ("bootstrap state", self.bootstrap_state_fingerprint),
            ("bootstrap ledger", self.bootstrap_ledger_fingerprint),
            ("initial state", self.initial_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")

        previous_after = self.initial_state_fingerprint
        previous_time: datetime | None = None
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence:
                raise RecurrentLifecycleAccountError(
                    "recurrent ledger sequence must be contiguous"
                )
            if previous_time is not None and event.occurred_utc < previous_time:
                raise RecurrentLifecycleAccountError(
                    "recurrent ledger must be chronological"
                )
            if event.before_state_fingerprint != previous_after:
                raise RecurrentLifecycleAccountError(
                    "recurrent ledger state chain is broken"
                )
            previous_after = event.after_state_fingerprint
            previous_time = event.occurred_utc

    @property
    def ledger_fingerprint(self) -> str:
        return recurrent_lifecycle_ledger_fingerprint(self)


@dataclass(frozen=True)
class RecurrentLifecycleAccountV1:
    state: RecurrentLifecycleAccountStateV1
    ledger: RecurrentLifecycleLedgerV1

    def __post_init__(self) -> None:
        if (
            self.state.bootstrap_state_fingerprint
            != self.ledger.bootstrap_state_fingerprint
            or self.state.bootstrap_ledger_fingerprint
            != self.ledger.bootstrap_ledger_fingerprint
        ):
            raise RecurrentLifecycleAccountError(
                "recurrent state and ledger bootstrap lineage mismatch"
            )
        expected = (
            self.ledger.events[-1].after_state_fingerprint
            if self.ledger.events
            else self.ledger.initial_state_fingerprint
        )
        if self.state.state_fingerprint != expected:
            raise RecurrentLifecycleAccountError(
                "recurrent account state must match latest ledger fingerprint"
            )


def recurrent_closed_trade_fingerprint(
    trade: RecurrentClosedTradeV1,
) -> str:
    return _fingerprint_payload(trade)


def recurrent_lifecycle_account_state_fingerprint(
    state: RecurrentLifecycleAccountStateV1,
) -> str:
    return _fingerprint_payload(state)


def recurrent_lifecycle_ledger_event_fingerprint(
    event: RecurrentLifecycleLedgerEventV1,
) -> str:
    return _fingerprint_payload(event)


def recurrent_lifecycle_ledger_fingerprint(
    ledger: RecurrentLifecycleLedgerV1,
) -> str:
    return _fingerprint_payload(ledger)


def _from_original_trade(trade: ClosedTradeV1) -> RecurrentClosedTradeV1:
    return RecurrentClosedTradeV1(
        origin=RecurrentClosedTradeOrigin.ORIGINAL_CLOSEOUT_V1,
        source_state_contract_fingerprint=(
            OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_state_fingerprint=trade.source_open_position_state_fingerprint,
        source_record_fingerprint=closed_trade_fingerprint(trade),
        position_fingerprint=trade.position_fingerprint,
        exit_fill_fingerprint=trade.exit_fill_fingerprint,
        decision_record_fingerprint=trade.decision_record_fingerprint,
        instrument_kind=trade.instrument_kind,
        instrument_id=trade.instrument_id,
        ticker=trade.ticker,
        direction=trade.direction,
        candidate_identifier=trade.candidate_identifier,
        option_contract_ticker=trade.option_contract_ticker,
        option_contract_type=trade.option_contract_type,
        opened_utc=trade.opened_utc,
        exited_utc=trade.exited_utc,
        hold_seconds=trade.hold_seconds,
        quantity=trade.quantity,
        quantity_unit=trade.quantity_unit,
        entry_price_per_unit=trade.entry_price_per_unit,
        exit_price_per_unit=trade.exit_price_per_unit,
        contract_multiplier=trade.contract_multiplier,
        entry_book_value_dollars=trade.entry_book_value_dollars,
        entry_fees_dollars=trade.entry_fees_dollars,
        gross_exit_proceeds_dollars=trade.gross_exit_proceeds_dollars,
        exit_fees_dollars=trade.exit_fees_dollars,
        net_exit_proceeds_dollars=trade.net_exit_proceeds_dollars,
        account_realized_pnl_delta_dollars=(
            trade.account_realized_pnl_delta_dollars
        ),
        lifetime_trade_net_pnl_dollars=(
            trade.lifetime_trade_net_pnl_dollars
        ),
        reason_codes=(
            "CANONICALIZED_ORIGINAL_CLOSEOUT_V1",
            *trade.reason_codes,
        ),
    )


def _from_lifecycle_trade(
    trade: LifecycleClosedTradeV1,
) -> RecurrentClosedTradeV1:
    return RecurrentClosedTradeV1(
        origin=RecurrentClosedTradeOrigin.LIFECYCLE_CLOSEOUT_V1,
        source_state_contract_fingerprint=(
            LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT
        ),
        source_state_fingerprint=(
            trade.source_lifecycle_position_state_fingerprint
        ),
        source_record_fingerprint=lifecycle_closed_trade_fingerprint(trade),
        position_fingerprint=trade.position_fingerprint,
        exit_fill_fingerprint=trade.exit_fill_fingerprint,
        decision_record_fingerprint=trade.decision_record_fingerprint,
        instrument_kind=trade.instrument_kind,
        instrument_id=trade.instrument_id,
        ticker=trade.ticker,
        direction=trade.direction,
        candidate_identifier=trade.candidate_identifier,
        option_contract_ticker=trade.option_contract_ticker,
        option_contract_type=trade.option_contract_type,
        opened_utc=trade.opened_utc,
        exited_utc=trade.exited_utc,
        hold_seconds=trade.hold_seconds,
        quantity=trade.quantity,
        quantity_unit=trade.quantity_unit,
        entry_price_per_unit=trade.entry_price_per_unit,
        exit_price_per_unit=trade.exit_price_per_unit,
        contract_multiplier=trade.contract_multiplier,
        entry_book_value_dollars=trade.entry_book_value_dollars,
        entry_fees_dollars=trade.entry_fees_dollars,
        gross_exit_proceeds_dollars=trade.gross_exit_proceeds_dollars,
        exit_fees_dollars=trade.exit_fees_dollars,
        net_exit_proceeds_dollars=trade.net_exit_proceeds_dollars,
        account_realized_pnl_delta_dollars=(
            trade.account_realized_pnl_delta_dollars
        ),
        lifetime_trade_net_pnl_dollars=(
            trade.lifetime_trade_net_pnl_dollars
        ),
        reason_codes=(
            "CANONICALIZED_LIFECYCLE_CLOSEOUT_V1",
            *trade.reason_codes,
        ),
    )


def initialize_recurrent_lifecycle_account_v1(
    *,
    source: LifecycleCloseoutAccountV1,
) -> RecurrentLifecycleAccountV1:
    if (
        source.state.contract_fingerprint
        != LIFECYCLE_CLOSEOUT_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentLifecycleAccountError(
            "bootstrap source must use accepted lifecycle closeout contract"
        )
    if (
        source.state.state_fingerprint
        != lifecycle_closeout_account_state_fingerprint(source.state)
    ):
        raise RecurrentLifecycleAccountError(
            "bootstrap lifecycle closeout state fingerprint mismatch"
        )
    if (
        source.ledger.ledger_fingerprint
        != lifecycle_closeout_ledger_fingerprint(source.ledger)
    ):
        raise RecurrentLifecycleAccountError(
            "bootstrap lifecycle closeout ledger fingerprint mismatch"
        )
    expected = (
        source.ledger.events[-1].after_state_fingerprint
        if source.ledger.events
        else source.ledger.initial_state_fingerprint
    )
    if expected != source.state.state_fingerprint:
        raise RecurrentLifecycleAccountError(
            "bootstrap lifecycle closeout ledger does not terminate at state"
        )

    item = source.state
    closed = tuple(sorted(
        (
            *(_from_original_trade(x) for x in item.prior_closed_trades),
            *(_from_lifecycle_trade(x) for x in item.lifecycle_closed_trades),
        ),
        key=lambda x: (x.exited_utc, x.exit_fill_fingerprint),
    ))
    state = RecurrentLifecycleAccountStateV1(
        contract_version=RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
        bootstrap_contract_fingerprint=item.contract_fingerprint,
        bootstrap_state_fingerprint=item.state_fingerprint,
        bootstrap_ledger_fingerprint=source.ledger.ledger_fingerprint,
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
        closed_trades=closed,
    )
    ledger = RecurrentLifecycleLedgerV1(
        contract_version=RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
        bootstrap_state_fingerprint=item.state_fingerprint,
        bootstrap_ledger_fingerprint=source.ledger.ledger_fingerprint,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return RecurrentLifecycleAccountV1(state=state, ledger=ledger)
