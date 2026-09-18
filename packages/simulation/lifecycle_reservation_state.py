from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Sequence

from packages.execution.trade_expression import InstrumentKind, SelectionKind
from packages.simulation.account_state_v2 import (
    SimulatedOptionReservationV2,
    SimulatedStockReservationV2,
)
from packages.simulation.closeout_account_state import (
    ClosedTradeV1,
    CloseoutAccountV1,
    closeout_account_state_fingerprint,
    closeout_ledger_fingerprint,
)
from packages.simulation.closeout_account_state_contract import (
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    economic_candidate_fingerprint,
)
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_reservation_contract import (
    LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT,
    LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1
from packages.simulation.option_reservation import (
    LongOptionReservationTerms,
    long_option_reservation_terms_fingerprint,
)
from packages.simulation.option_reservation_contract import (
    LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
)


LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_VERSION = str(
    LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class LifecycleReservationAccountError(ValueError):
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
        raise LifecycleReservationAccountError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise LifecycleReservationAccountError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LifecycleReservationAccountError(
            f"{label} must be timezone-aware"
        )


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise LifecycleReservationAccountError(
            f"{label} must be finite and nonnegative"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


class LifecycleReservationEventKind(StrEnum):
    RESERVE_STOCK = "RESERVE_STOCK"
    RESERVE_OPTION = "RESERVE_OPTION"
    ABSTAIN = "ABSTAIN"
    REJECT_MISSING_OPTION_TERMS = "REJECT_MISSING_OPTION_TERMS"
    REJECT_INSUFFICIENT_CAPITAL = "REJECT_INSUFFICIENT_CAPITAL"


@dataclass(frozen=True)
class LifecycleReservationAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    source_closeout_contract_fingerprint: str
    source_closeout_state_fingerprint: str
    source_closeout_ledger_fingerprint: str
    as_of_utc: datetime

    initial_equity: float
    source_entry_book_equity: float
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
    closed_trades: tuple[ClosedTradeV1, ...]

    simulation_reservation_mutation: bool = True
    entry_fill_authority: bool = False
    new_open_position_authority: bool = False
    exit_closeout_authority: bool = False
    mark_to_market_authority: bool = False
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
            != LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_VERSION
        ):
            raise LifecycleReservationAccountError(
                "lifecycle reservation contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecycleReservationAccountError(
                "lifecycle reservation contract fingerprint mismatch"
            )
        if (
            self.source_closeout_contract_fingerprint
            != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ):
            raise LifecycleReservationAccountError(
                "source closeout contract fingerprint mismatch"
            )
        for label, value in (
            ("source closeout state", self.source_closeout_state_fingerprint),
            ("source closeout ledger", self.source_closeout_ledger_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.as_of_utc, label="lifecycle reservation timestamp")
        if not math.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise LifecycleReservationAccountError(
                "initial equity must be finite and positive"
            )

        for label, value in (
            ("source entry-book equity", self.source_entry_book_equity),
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
                "option reserved signed delta",
                self.option_reserved_signed_delta_equivalent_notional,
            ),
            (
                "open option signed delta reference",
                self.open_option_signed_delta_equivalent_entry_reference_dollars,
            ),
        ):
            if not math.isfinite(value):
                raise LifecycleReservationAccountError(
                    f"{label} must be finite"
                )

        if not self.simulation_reservation_mutation:
            raise LifecycleReservationAccountError(
                "lifecycle reservation state must identify reservation mutation"
            )

        stocks = tuple(
            sorted(
                self.stock_reservations,
                key=lambda item: item.decision_record_fingerprint,
            )
        )
        options = tuple(
            sorted(
                self.option_reservations,
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
        if stocks != self.stock_reservations:
            raise LifecycleReservationAccountError(
                "stock reservations must be ordered"
            )
        if options != self.option_reservations:
            raise LifecycleReservationAccountError(
                "option reservations must be ordered"
            )
        if positions != self.open_positions:
            raise LifecycleReservationAccountError(
                "open positions must be ordered"
            )
        if closed != self.closed_trades:
            raise LifecycleReservationAccountError(
                "closed trades must be chronological"
            )

        stock_ids = [item.decision_record_fingerprint for item in stocks]
        option_ids = [item.decision_record_fingerprint for item in options]
        open_ids = [item.decision_record_fingerprint for item in positions]
        closed_ids = [item.decision_record_fingerprint for item in closed]
        for label, ids in (
            ("stock reservations", stock_ids),
            ("option reservations", option_ids),
            ("open positions", open_ids),
            ("closed trades", closed_ids),
        ):
            if len(ids) != len(set(ids)):
                raise LifecycleReservationAccountError(
                    f"{label} cannot duplicate decision fingerprints"
                )
        active_sets = [set(stock_ids), set(option_ids), set(open_ids)]
        for index, left in enumerate(active_sets):
            for right in active_sets[index + 1 :]:
                if left.intersection(right):
                    raise LifecycleReservationAccountError(
                        "one decision cannot be active in multiple lifecycle buckets"
                    )
        if set(open_ids).intersection(closed_ids):
            raise LifecycleReservationAccountError(
                "one decision cannot be both open and closed"
            )

        if any(x.reserved_utc > self.as_of_utc for x in stocks + options):
            raise LifecycleReservationAccountError(
                "active reservation cannot postdate account state"
            )
        if any(x.opened_utc > self.as_of_utc for x in positions):
            raise LifecycleReservationAccountError(
                "open position cannot postdate account state"
            )
        if any(x.exited_utc > self.as_of_utc for x in closed):
            raise LifecycleReservationAccountError(
                "closed trade cannot postdate account state"
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
                "open stock gross entry exposure",
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
            (
                self.cumulative_entry_fees_dollars,
                sum(x.entry_fees_dollars for x in positions)
                + sum(x.entry_fees_dollars for x in closed),
                "cumulative entry fees",
            ),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise LifecycleReservationAccountError(
                    f"{label} must equal constituent sum"
                )
        if not _same(
            self.option_reserved_max_loss_cash,
            self.option_reserved_capital,
        ):
            raise LifecycleReservationAccountError(
                "long-option reserved max loss must equal option reserved capital"
            )
        if not _same(
            self.source_entry_book_equity,
            self.initial_equity - self.cumulative_entry_fees_dollars,
        ):
            raise LifecycleReservationAccountError(
                "source entry-book equity must preserve cumulative entry fees"
            )
        expected_book = (
            self.initial_equity
            - self.cumulative_entry_fees_dollars
            + self.cumulative_account_realized_pnl_dollars
        )
        if not _same(self.account_book_equity, expected_book):
            raise LifecycleReservationAccountError(
                "account book equity must preserve realized-P&L accounting"
            )
        balance = (
            self.cash
            + self.stock_reserved_capital
            + self.option_reserved_capital
            + self.open_entry_book_value_dollars
        )
        if not _same(balance, self.account_book_equity):
            raise LifecycleReservationAccountError(
                "cash, reservations, and open book value must reconcile to account book equity"
            )

        forbidden = (
            self.entry_fill_authority,
            self.new_open_position_authority,
            self.exit_closeout_authority,
            self.mark_to_market_authority,
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
            raise LifecycleReservationAccountError(
                "lifecycle reservation state cannot grant fill, position, exit, mark, "
                "provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return lifecycle_reservation_account_state_fingerprint(self)


@dataclass(frozen=True)
class LifecycleReservationLedgerEventV1:
    sequence: int
    occurred_utc: datetime
    kind: LifecycleReservationEventKind
    decision_record_fingerprint: str
    reservation_terms_fingerprint: str | None
    option_economics_result_fingerprint: str | None
    candidate_identifier: str | None
    option_contract_ticker: str | None
    instrument_id: str
    ticker: str
    direction: str
    stock_capital_delta: float
    option_capital_delta: float
    stock_gross_notional_delta: float
    option_signed_delta_equivalent_delta: float
    option_abs_delta_equivalent_delta: float
    option_max_loss_delta: float
    option_premium_at_risk_delta: float
    before_state_fingerprint: str
    after_state_fingerprint: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise LifecycleReservationAccountError(
                "reservation ledger sequence must be positive"
            )
        _require_aware(self.occurred_utc, label="reservation ledger timestamp")
        _require_fingerprint(
            self.decision_record_fingerprint,
            label="decision-record fingerprint",
        )
        for label, value in (
            ("reservation terms", self.reservation_terms_fingerprint),
            ("option economics", self.option_economics_result_fingerprint),
        ):
            if value is not None:
                _require_fingerprint(value, label=f"{label} fingerprint")
        for label, value in (
            ("before state", self.before_state_fingerprint),
            ("after state", self.after_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        if not self.instrument_id.strip() or not self.ticker.strip() or not self.direction.strip():
            raise LifecycleReservationAccountError(
                "reservation event identity cannot be blank"
            )
        deltas = (
            self.stock_capital_delta,
            self.option_capital_delta,
            self.stock_gross_notional_delta,
            self.option_signed_delta_equivalent_delta,
            self.option_abs_delta_equivalent_delta,
            self.option_max_loss_delta,
            self.option_premium_at_risk_delta,
        )
        if not all(math.isfinite(value) for value in deltas):
            raise LifecycleReservationAccountError(
                "reservation event deltas must be finite"
            )
        if self.kind == LifecycleReservationEventKind.RESERVE_STOCK:
            if self.stock_capital_delta <= 0.0 or self.stock_gross_notional_delta <= 0.0:
                raise LifecycleReservationAccountError(
                    "stock reservation event requires positive stock deltas"
                )
            if any(
                not _same(value, 0.0)
                for value in (
                    self.option_capital_delta,
                    self.option_signed_delta_equivalent_delta,
                    self.option_abs_delta_equivalent_delta,
                    self.option_max_loss_delta,
                    self.option_premium_at_risk_delta,
                )
            ):
                raise LifecycleReservationAccountError(
                    "stock reservation cannot mutate option reservation exposure"
                )
        elif self.kind == LifecycleReservationEventKind.RESERVE_OPTION:
            if (
                self.option_capital_delta <= 0.0
                or self.option_abs_delta_equivalent_delta <= 0.0
                or self.option_max_loss_delta <= 0.0
                or self.option_premium_at_risk_delta <= 0.0
            ):
                raise LifecycleReservationAccountError(
                    "option reservation event requires positive option risk deltas"
                )
            if not _same(self.stock_capital_delta, 0.0) or not _same(
                self.stock_gross_notional_delta, 0.0
            ):
                raise LifecycleReservationAccountError(
                    "option reservation cannot mutate stock reservation exposure"
                )
        else:
            if any(not _same(value, 0.0) for value in deltas):
                raise LifecycleReservationAccountError(
                    "non-reservation decision events cannot mutate reservation exposure"
                )
        if not self.reason_codes:
            raise LifecycleReservationAccountError(
                "reservation ledger event requires reason codes"
            )

    @property
    def event_fingerprint(self) -> str:
        return lifecycle_reservation_ledger_event_fingerprint(self)


@dataclass(frozen=True)
class LifecycleReservationLedgerV1:
    contract_version: str
    contract_fingerprint: str
    source_closeout_state_fingerprint: str
    source_closeout_ledger_fingerprint: str
    initial_state_fingerprint: str
    events: tuple[LifecycleReservationLedgerEventV1, ...]

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_VERSION
        ):
            raise LifecycleReservationAccountError(
                "reservation ledger contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecycleReservationAccountError(
                "reservation ledger contract fingerprint mismatch"
            )
        for label, value in (
            ("source closeout state", self.source_closeout_state_fingerprint),
            ("source closeout ledger", self.source_closeout_ledger_fingerprint),
            ("initial state", self.initial_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")

        previous_after = self.initial_state_fingerprint
        previous_time: datetime | None = None
        seen_decisions: set[str] = set()
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence:
                raise LifecycleReservationAccountError(
                    "reservation ledger sequence must be contiguous"
                )
            if previous_time is not None and event.occurred_utc < previous_time:
                raise LifecycleReservationAccountError(
                    "reservation ledger must be chronological"
                )
            if event.before_state_fingerprint != previous_after:
                raise LifecycleReservationAccountError(
                    "reservation ledger fingerprint chain is broken"
                )
            if event.decision_record_fingerprint in seen_decisions:
                raise LifecycleReservationAccountError(
                    "one decision can create only one reservation-account event"
                )
            seen_decisions.add(event.decision_record_fingerprint)
            previous_time = event.occurred_utc
            previous_after = event.after_state_fingerprint

    @property
    def ledger_fingerprint(self) -> str:
        return lifecycle_reservation_ledger_fingerprint(self)


@dataclass(frozen=True)
class LifecycleReservationAccountV1:
    state: LifecycleReservationAccountStateV1
    ledger: LifecycleReservationLedgerV1

    def __post_init__(self) -> None:
        if (
            self.state.source_closeout_state_fingerprint
            != self.ledger.source_closeout_state_fingerprint
            or self.state.source_closeout_ledger_fingerprint
            != self.ledger.source_closeout_ledger_fingerprint
        ):
            raise LifecycleReservationAccountError(
                "reservation state and ledger source lineage must match"
            )
        expected = (
            self.ledger.events[-1].after_state_fingerprint
            if self.ledger.events
            else self.ledger.initial_state_fingerprint
        )
        if self.state.state_fingerprint != expected:
            raise LifecycleReservationAccountError(
                "reservation account state must match latest ledger fingerprint"
            )


@dataclass(frozen=True)
class LifecycleReservationTransitionV1:
    account: LifecycleReservationAccountV1
    event: LifecycleReservationLedgerEventV1 | None
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class LifecycleReservationBatchResultV1:
    account: LifecycleReservationAccountV1
    ordered_decision_fingerprints: tuple[str, ...]
    transitions: tuple[LifecycleReservationTransitionV1, ...]


def lifecycle_reservation_account_state_fingerprint(
    state: LifecycleReservationAccountStateV1,
) -> str:
    return _fingerprint_payload(state)


def lifecycle_reservation_ledger_event_fingerprint(
    event: LifecycleReservationLedgerEventV1,
) -> str:
    return _fingerprint_payload(event)


def lifecycle_reservation_ledger_fingerprint(
    ledger: LifecycleReservationLedgerV1,
) -> str:
    return _fingerprint_payload(ledger)


def _validate_closeout_source(source: CloseoutAccountV1) -> None:
    if (
        source.state.contract_fingerprint
        != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
    ):
        raise LifecycleReservationAccountError(
            "source must use accepted closeout-account contract"
        )
    if (
        source.state.state_fingerprint
        != closeout_account_state_fingerprint(source.state)
    ):
        raise LifecycleReservationAccountError(
            "source closeout state fingerprint mismatch"
        )
    if (
        source.ledger.ledger_fingerprint
        != closeout_ledger_fingerprint(source.ledger)
    ):
        raise LifecycleReservationAccountError(
            "source closeout ledger fingerprint mismatch"
        )
    expected = (
        source.ledger.events[-1].after_state_fingerprint
        if source.ledger.events
        else source.ledger.initial_state_fingerprint
    )
    if expected != source.state.state_fingerprint:
        raise LifecycleReservationAccountError(
            "source closeout ledger does not terminate at source state"
        )


def initialize_lifecycle_reservation_account_v1(
    *,
    source: CloseoutAccountV1,
) -> LifecycleReservationAccountV1:
    _validate_closeout_source(source)
    item = source.state
    state = LifecycleReservationAccountStateV1(
        contract_version=LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=(
            LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
        ),
        source_closeout_contract_fingerprint=item.contract_fingerprint,
        source_closeout_state_fingerprint=item.state_fingerprint,
        source_closeout_ledger_fingerprint=source.ledger.ledger_fingerprint,
        as_of_utc=item.as_of_utc,
        initial_equity=item.initial_equity,
        source_entry_book_equity=item.source_entry_book_equity,
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
        stock_reserved_capital=item.remaining_stock_reserved_capital,
        option_reserved_capital=item.remaining_option_reserved_capital,
        stock_reserved_gross_notional=item.remaining_stock_gross_notional,
        option_reserved_signed_delta_equivalent_notional=(
            item.remaining_option_signed_delta_equivalent_notional
        ),
        option_reserved_abs_delta_equivalent_notional=(
            item.remaining_option_abs_delta_equivalent_notional
        ),
        option_reserved_max_loss_cash=sum(
            x.max_loss_cash for x in item.remaining_option_reservations
        ),
        option_reserved_premium_at_risk=sum(
            x.premium_at_risk for x in item.remaining_option_reservations
        ),
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
        stock_reservations=item.remaining_stock_reservations,
        option_reservations=item.remaining_option_reservations,
        open_positions=item.open_positions,
        closed_trades=item.closed_trades,
    )
    ledger = LifecycleReservationLedgerV1(
        contract_version=LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=(
            LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
        ),
        source_closeout_state_fingerprint=item.state_fingerprint,
        source_closeout_ledger_fingerprint=source.ledger.ledger_fingerprint,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return LifecycleReservationAccountV1(state=state, ledger=ledger)


def _build_state(
    *,
    previous: LifecycleReservationAccountStateV1,
    as_of_utc: datetime,
    cash: float,
    stock_reservations: Sequence[SimulatedStockReservationV2],
    option_reservations: Sequence[SimulatedOptionReservationV2],
) -> LifecycleReservationAccountStateV1:
    stocks = tuple(
        sorted(
            stock_reservations,
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    options = tuple(
        sorted(
            option_reservations,
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    return LifecycleReservationAccountStateV1(
        contract_version=previous.contract_version,
        contract_fingerprint=previous.contract_fingerprint,
        source_closeout_contract_fingerprint=(
            previous.source_closeout_contract_fingerprint
        ),
        source_closeout_state_fingerprint=(
            previous.source_closeout_state_fingerprint
        ),
        source_closeout_ledger_fingerprint=(
            previous.source_closeout_ledger_fingerprint
        ),
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        source_entry_book_equity=previous.source_entry_book_equity,
        cumulative_entry_fees_dollars=previous.cumulative_entry_fees_dollars,
        cumulative_exit_fees_dollars=previous.cumulative_exit_fees_dollars,
        cumulative_account_realized_pnl_dollars=(
            previous.cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            previous.cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=_zero(cash),
        account_book_equity=previous.account_book_equity,
        stock_reserved_capital=_zero(
            sum(x.reserved_capital for x in stocks)
        ),
        option_reserved_capital=_zero(
            sum(x.reserved_capital for x in options)
        ),
        stock_reserved_gross_notional=_zero(
            sum(x.gross_notional for x in stocks)
        ),
        option_reserved_signed_delta_equivalent_notional=_zero(
            sum(x.signed_delta_equivalent_notional for x in options)
        ),
        option_reserved_abs_delta_equivalent_notional=_zero(
            sum(x.abs_delta_equivalent_notional for x in options)
        ),
        option_reserved_max_loss_cash=_zero(
            sum(x.max_loss_cash for x in options)
        ),
        option_reserved_premium_at_risk=_zero(
            sum(x.premium_at_risk for x in options)
        ),
        open_entry_book_value_dollars=previous.open_entry_book_value_dollars,
        open_stock_gross_entry_exposure_dollars=(
            previous.open_stock_gross_entry_exposure_dollars
        ),
        open_option_entry_book_value_dollars=(
            previous.open_option_entry_book_value_dollars
        ),
        open_option_signed_delta_equivalent_entry_reference_dollars=(
            previous.open_option_signed_delta_equivalent_entry_reference_dollars
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=(
            previous.open_option_abs_delta_equivalent_entry_reference_dollars
        ),
        open_option_premium_at_risk_dollars=(
            previous.open_option_premium_at_risk_dollars
        ),
        stock_reservations=stocks,
        option_reservations=options,
        open_positions=previous.open_positions,
        closed_trades=previous.closed_trades,
    )


def _unchanged_state(
    account: LifecycleReservationAccountV1,
    *,
    as_of_utc: datetime,
) -> LifecycleReservationAccountStateV1:
    return _build_state(
        previous=account.state,
        as_of_utc=as_of_utc,
        cash=account.state.cash,
        stock_reservations=account.state.stock_reservations,
        option_reservations=account.state.option_reservations,
    )


def _prior_event(
    account: LifecycleReservationAccountV1,
    decision_record_fingerprint: str,
) -> LifecycleReservationLedgerEventV1 | None:
    return next(
        (
            event
            for event in account.ledger.events
            if event.decision_record_fingerprint
            == decision_record_fingerprint
        ),
        None,
    )


def _source_contains_decision(
    state: LifecycleReservationAccountStateV1,
    decision_record_fingerprint: str,
) -> bool:
    return any(
        item.decision_record_fingerprint == decision_record_fingerprint
        for item in (
            *state.stock_reservations,
            *state.option_reservations,
            *state.open_positions,
            *state.closed_trades,
        )
    )


def _append_event(
    *,
    account: LifecycleReservationAccountV1,
    next_state: LifecycleReservationAccountStateV1,
    kind: LifecycleReservationEventKind,
    record: SimulationDecisionRecord,
    reservation_terms_fingerprint: str | None = None,
    option_economics_result_fingerprint: str | None = None,
    candidate_identifier: str | None = None,
    option_contract_ticker: str | None = None,
    stock_capital_delta: float = 0.0,
    option_capital_delta: float = 0.0,
    stock_gross_notional_delta: float = 0.0,
    option_signed_delta_equivalent_delta: float = 0.0,
    option_abs_delta_equivalent_delta: float = 0.0,
    option_max_loss_delta: float = 0.0,
    option_premium_at_risk_delta: float = 0.0,
    reason_codes: tuple[str, ...],
) -> LifecycleReservationTransitionV1:
    event = LifecycleReservationLedgerEventV1(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=record.decision_created_utc,
        kind=kind,
        decision_record_fingerprint=record.record_fingerprint,
        reservation_terms_fingerprint=reservation_terms_fingerprint,
        option_economics_result_fingerprint=(
            option_economics_result_fingerprint
        ),
        candidate_identifier=candidate_identifier,
        option_contract_ticker=option_contract_ticker,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        stock_capital_delta=stock_capital_delta,
        option_capital_delta=option_capital_delta,
        stock_gross_notional_delta=stock_gross_notional_delta,
        option_signed_delta_equivalent_delta=(
            option_signed_delta_equivalent_delta
        ),
        option_abs_delta_equivalent_delta=(
            option_abs_delta_equivalent_delta
        ),
        option_max_loss_delta=option_max_loss_delta,
        option_premium_at_risk_delta=option_premium_at_risk_delta,
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
        reason_codes=reason_codes,
    )
    ledger = LifecycleReservationLedgerV1(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        source_closeout_state_fingerprint=(
            account.ledger.source_closeout_state_fingerprint
        ),
        source_closeout_ledger_fingerprint=(
            account.ledger.source_closeout_ledger_fingerprint
        ),
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    return LifecycleReservationTransitionV1(
        account=LifecycleReservationAccountV1(
            state=next_state,
            ledger=ledger,
        ),
        event=event,
        idempotent_reuse=False,
        reason_codes=reason_codes,
    )


def _validate_option_terms(
    *,
    record: SimulationDecisionRecord,
    terms: LongOptionReservationTerms,
) -> str:
    if terms.contract_fingerprint != LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT:
        raise LifecycleReservationAccountError(
            "long-option reservation contract fingerprint mismatch"
        )
    if terms.decision_record_fingerprint != record.record_fingerprint:
        raise LifecycleReservationAccountError(
            "option reservation decision lineage mismatch"
        )
    if terms.source_forecast_fingerprint != record.forecast_fingerprint:
        raise LifecycleReservationAccountError(
            "option reservation forecast lineage mismatch"
        )
    decision = record.trade_expression_decision
    candidate = decision.chosen_candidate
    if candidate is None or candidate.kind != InstrumentKind.OPTION:
        raise LifecycleReservationAccountError(
            "option reservation requires selected option candidate"
        )
    if terms.chosen_candidate_identifier != candidate.identifier:
        raise LifecycleReservationAccountError(
            "option reservation candidate identifier mismatch"
        )
    if (
        terms.chosen_candidate_fingerprint
        != economic_candidate_fingerprint(candidate)
    ):
        raise LifecycleReservationAccountError(
            "option reservation candidate fingerprint mismatch"
        )
    if (
        terms.instrument_id != record.forecast.instrument_id
        or terms.ticker != record.forecast.ticker
    ):
        raise LifecycleReservationAccountError(
            "option reservation underlying identity mismatch"
        )
    if terms.direction != record.forecast.direction:
        raise LifecycleReservationAccountError(
            "option reservation direction mismatch"
        )
    return long_option_reservation_terms_fingerprint(terms)


def apply_lifecycle_decision_reservation_v1(
    account: LifecycleReservationAccountV1,
    record: SimulationDecisionRecord,
    *,
    option_terms: LongOptionReservationTerms | None = None,
) -> LifecycleReservationTransitionV1:
    if (
        record.contract_fingerprint
        != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT
    ):
        raise LifecycleReservationAccountError(
            "simulation decision-record contract fingerprint mismatch"
        )
    record_fp = record.record_fingerprint

    prior = _prior_event(account, record_fp)
    if prior is not None:
        if (
            prior.kind == LifecycleReservationEventKind.RESERVE_OPTION
            and option_terms is not None
        ):
            supplied = long_option_reservation_terms_fingerprint(option_terms)
            if prior.reservation_terms_fingerprint != supplied:
                raise LifecycleReservationAccountError(
                    "duplicate option decision supplied different reservation terms"
                )
        return LifecycleReservationTransitionV1(
            account=account,
            event=None,
            idempotent_reuse=True,
            reason_codes=("DECISION_ALREADY_APPLIED",),
        )

    if _source_contains_decision(account.state, record_fp):
        return LifecycleReservationTransitionV1(
            account=account,
            event=None,
            idempotent_reuse=True,
            reason_codes=("DECISION_ALREADY_PRESENT_IN_SOURCE_LIFECYCLE",),
        )

    if record.decision_created_utc < account.state.as_of_utc:
        raise LifecycleReservationAccountError(
            "decision timestamp cannot precede current lifecycle account state"
        )

    decision = record.trade_expression_decision
    if decision.selection_kind == SelectionKind.ABSTAIN:
        if option_terms is not None:
            raise LifecycleReservationAccountError(
                "option reservation terms cannot accompany abstention"
            )
        next_state = _unchanged_state(
            account,
            as_of_utc=record.decision_created_utc,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=LifecycleReservationEventKind.ABSTAIN,
            record=record,
            reason_codes=("DECISION_ABSTAINED",) + decision.reason_codes,
        )

    candidate = decision.chosen_candidate
    if candidate is None:
        raise LifecycleReservationAccountError(
            "non-abstain decision must carry a chosen candidate"
        )

    if decision.selection_kind == SelectionKind.STOCK:
        if option_terms is not None:
            raise LifecycleReservationAccountError(
                "option reservation terms cannot accompany stock decision"
            )
        if candidate.kind != InstrumentKind.STOCK:
            raise LifecycleReservationAccountError(
                "stock selection does not carry a stock candidate"
            )
        stock_candidate = record.stock_economics.candidate
        if candidate.identifier != stock_candidate.identifier:
            raise LifecycleReservationAccountError(
                "chosen stock candidate identifier mismatch"
            )
        if (
            economic_candidate_fingerprint(candidate)
            != economic_candidate_fingerprint(stock_candidate)
        ):
            raise LifecycleReservationAccountError(
                "chosen stock candidate fingerprint mismatch"
            )
        capital = float(record.stock_economics.capital_required_dollars)
        gross = float(record.stock_economics.position_notional_dollars)
        if not _same(candidate.capital_required, capital):
            raise LifecycleReservationAccountError(
                "stock capital lineage mismatch"
            )
        if capital > account.state.cash and not _same(
            capital, account.state.cash
        ):
            next_state = _unchanged_state(
                account,
                as_of_utc=record.decision_created_utc,
            )
            return _append_event(
                account=account,
                next_state=next_state,
                kind=LifecycleReservationEventKind.REJECT_INSUFFICIENT_CAPITAL,
                record=record,
                candidate_identifier=candidate.identifier,
                reason_codes=(
                    "INSUFFICIENT_CURRENT_LIFECYCLE_CASH",
                    "STOCK_RESERVATION_REJECTED",
                ),
            )
        reservation = SimulatedStockReservationV2(
            decision_record_fingerprint=record_fp,
            candidate_identifier=candidate.identifier,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            reserved_capital=capital,
            gross_notional=gross,
            reserved_utc=record.decision_created_utc,
        )
        next_state = _build_state(
            previous=account.state,
            as_of_utc=record.decision_created_utc,
            cash=account.state.cash - capital,
            stock_reservations=account.state.stock_reservations
            + (reservation,),
            option_reservations=account.state.option_reservations,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=LifecycleReservationEventKind.RESERVE_STOCK,
            record=record,
            candidate_identifier=candidate.identifier,
            stock_capital_delta=capital,
            stock_gross_notional_delta=gross,
            reason_codes=(
                "POST_CLOSE_STOCK_CAPITAL_RESERVED",
                "CURRENT_LIFECYCLE_CASH_REDUCED",
                "OPEN_AND_CLOSED_TRADE_HISTORY_PRESERVED",
            ),
        )

    if (
        decision.selection_kind != SelectionKind.OPTION
        or candidate.kind != InstrumentKind.OPTION
    ):
        raise LifecycleReservationAccountError(
            "unsupported lifecycle reservation selection kind"
        )

    if option_terms is None:
        next_state = _unchanged_state(
            account,
            as_of_utc=record.decision_created_utc,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=LifecycleReservationEventKind.REJECT_MISSING_OPTION_TERMS,
            record=record,
            candidate_identifier=candidate.identifier,
            reason_codes=("LONG_OPTION_RESERVATION_TERMS_REQUIRED",),
        )

    terms_fp = _validate_option_terms(record=record, terms=option_terms)
    capital = float(option_terms.reserved_capital_dollars)
    if capital > account.state.cash and not _same(capital, account.state.cash):
        next_state = _unchanged_state(
            account,
            as_of_utc=record.decision_created_utc,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=LifecycleReservationEventKind.REJECT_INSUFFICIENT_CAPITAL,
            record=record,
            reservation_terms_fingerprint=terms_fp,
            option_economics_result_fingerprint=(
                option_terms.option_economics_result_fingerprint
            ),
            candidate_identifier=candidate.identifier,
            option_contract_ticker=option_terms.option_contract_ticker,
            reason_codes=(
                "INSUFFICIENT_CURRENT_LIFECYCLE_CASH",
                "OPTION_RESERVATION_REJECTED",
            ),
        )

    reservation = SimulatedOptionReservationV2(
        decision_record_fingerprint=record_fp,
        reservation_terms_fingerprint=terms_fp,
        option_economics_result_fingerprint=(
            option_terms.option_economics_result_fingerprint
        ),
        candidate_identifier=candidate.identifier,
        option_contract_ticker=option_terms.option_contract_ticker,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        reserved_capital=capital,
        max_loss_cash=float(option_terms.max_loss_cash_dollars),
        premium_at_risk=float(option_terms.premium_at_risk_dollars),
        signed_delta_equivalent_notional=float(
            option_terms.signed_delta_equivalent_notional_dollars
        ),
        abs_delta_equivalent_notional=float(
            option_terms.abs_delta_equivalent_notional_dollars
        ),
        reserved_utc=record.decision_created_utc,
    )
    next_state = _build_state(
        previous=account.state,
        as_of_utc=record.decision_created_utc,
        cash=account.state.cash - capital,
        stock_reservations=account.state.stock_reservations,
        option_reservations=account.state.option_reservations
        + (reservation,),
    )
    return _append_event(
        account=account,
        next_state=next_state,
        kind=LifecycleReservationEventKind.RESERVE_OPTION,
        record=record,
        reservation_terms_fingerprint=terms_fp,
        option_economics_result_fingerprint=(
            option_terms.option_economics_result_fingerprint
        ),
        candidate_identifier=candidate.identifier,
        option_contract_ticker=option_terms.option_contract_ticker,
        option_capital_delta=capital,
        option_signed_delta_equivalent_delta=(
            reservation.signed_delta_equivalent_notional
        ),
        option_abs_delta_equivalent_delta=(
            reservation.abs_delta_equivalent_notional
        ),
        option_max_loss_delta=reservation.max_loss_cash,
        option_premium_at_risk_delta=reservation.premium_at_risk,
        reason_codes=(
            "POST_CLOSE_LONG_OPTION_CAPITAL_RESERVED",
            "CURRENT_LIFECYCLE_CASH_REDUCED",
            "RESERVED_OPTION_EXPOSURE_RECORDED_SEPARATELY",
            "OPEN_AND_CLOSED_TRADE_HISTORY_PRESERVED",
        ),
    )


def apply_lifecycle_reservation_batch_v1(
    account: LifecycleReservationAccountV1,
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
) -> LifecycleReservationBatchResultV1:
    ordered = tuple(
        sorted(
            decisions,
            key=lambda item: (
                item[0].decision_created_utc,
                item[0].record_fingerprint,
            ),
        )
    )
    current = account
    transitions: list[LifecycleReservationTransitionV1] = []
    for record, option_terms in ordered:
        transition = apply_lifecycle_decision_reservation_v1(
            current,
            record,
            option_terms=option_terms,
        )
        transitions.append(transition)
        current = transition.account
    return LifecycleReservationBatchResultV1(
        account=current,
        ordered_decision_fingerprints=tuple(
            record.record_fingerprint for record, _ in ordered
        ),
        transitions=tuple(transitions),
    )


def replay_lifecycle_reservation_account_v1(
    *,
    source: CloseoutAccountV1,
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
) -> LifecycleReservationBatchResultV1:
    return apply_lifecycle_reservation_batch_v1(
        initialize_lifecycle_reservation_account_v1(source=source),
        decisions,
    )


def verify_lifecycle_reservation_account_replay_v1(
    *,
    account: LifecycleReservationAccountV1,
    source: CloseoutAccountV1,
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
) -> None:
    replayed = replay_lifecycle_reservation_account_v1(
        source=source,
        decisions=decisions,
    )
    if replayed.account.state.state_fingerprint != account.state.state_fingerprint:
        raise LifecycleReservationAccountError(
            "lifecycle reservation state replay fingerprint mismatch"
        )
    if (
        replayed.account.ledger.ledger_fingerprint
        != account.ledger.ledger_fingerprint
    ):
        raise LifecycleReservationAccountError(
            "lifecycle reservation ledger replay fingerprint mismatch"
        )
