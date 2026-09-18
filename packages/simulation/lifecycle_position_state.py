from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from packages.execution.trade_expression import InstrumentKind
from packages.simulation.account_state_v2 import (
    SimulatedOptionReservationV2,
    SimulatedStockReservationV2,
)
from packages.simulation.closeout_account_state import ClosedTradeV1
from packages.simulation.lifecycle_entry_evidence import (
    LifecycleEntryFillEvidenceV1,
    LifecycleFundingModel,
    LifecycleFundingTermsV1,
    lifecycle_entry_fill_fingerprint,
    lifecycle_funding_terms_fingerprint,
)
from packages.simulation.lifecycle_entry_evidence_contract import (
    LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT,
    LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_position_contract import (
    LIFECYCLE_POSITION_ACCOUNT_CONTRACT,
    LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_reservation_contract import (
    LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_reservation_state import (
    LifecycleReservationAccountV1,
    lifecycle_reservation_account_state_fingerprint,
    lifecycle_reservation_ledger_fingerprint,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1
from packages.simulation.simulated_fill import simulated_reservation_fingerprint


LIFECYCLE_POSITION_ACCOUNT_CONTRACT_VERSION = str(
    LIFECYCLE_POSITION_ACCOUNT_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class LifecyclePositionAccountError(ValueError):
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
        raise LifecyclePositionAccountError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise LifecyclePositionAccountError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LifecyclePositionAccountError(
            f"{label} must be timezone-aware"
        )


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise LifecyclePositionAccountError(
            f"{label} must be finite and nonnegative"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


@dataclass(frozen=True)
class LifecyclePositionAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    source_reservation_contract_fingerprint: str
    source_reservation_state_fingerprint: str
    source_reservation_ledger_fingerprint: str
    source_reservation_cash_dollars: float
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
    closed_trades: tuple[ClosedTradeV1, ...]

    simulation_position_mutation: bool = True
    reservation_mutation_authority: bool = False
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
        if self.contract_version != LIFECYCLE_POSITION_ACCOUNT_CONTRACT_VERSION:
            raise LifecyclePositionAccountError(
                "lifecycle position contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecyclePositionAccountError(
                "lifecycle position contract fingerprint mismatch"
            )
        if (
            self.source_reservation_contract_fingerprint
            != LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecyclePositionAccountError(
                "source lifecycle reservation contract fingerprint mismatch"
            )
        for label, value in (
            ("source reservation state", self.source_reservation_state_fingerprint),
            ("source reservation ledger", self.source_reservation_ledger_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.as_of_utc, label="lifecycle position timestamp")
        if not math.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise LifecyclePositionAccountError(
                "initial equity must be finite and positive"
            )

        for label, value in (
            ("source reservation cash", self.source_reservation_cash_dollars),
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
                raise LifecyclePositionAccountError(
                    f"{label} must be finite"
                )

        if not self.simulation_position_mutation:
            raise LifecyclePositionAccountError(
                "lifecycle position state must identify position mutation"
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
            raise LifecyclePositionAccountError(
                "stock reservations must be ordered"
            )
        if options != self.option_reservations:
            raise LifecyclePositionAccountError(
                "option reservations must be ordered"
            )
        if positions != self.open_positions:
            raise LifecyclePositionAccountError(
                "open positions must be ordered"
            )
        if closed != self.closed_trades:
            raise LifecyclePositionAccountError(
                "closed trades must be chronological"
            )

        stock_ids = [x.decision_record_fingerprint for x in stocks]
        option_ids = [x.decision_record_fingerprint for x in options]
        open_ids = [x.decision_record_fingerprint for x in positions]
        closed_ids = [x.decision_record_fingerprint for x in closed]
        for label, ids in (
            ("stock reservations", stock_ids),
            ("option reservations", option_ids),
            ("open positions", open_ids),
            ("closed trades", closed_ids),
        ):
            if len(ids) != len(set(ids)):
                raise LifecyclePositionAccountError(
                    f"{label} cannot duplicate decision fingerprints"
                )
        active_sets = [set(stock_ids), set(option_ids), set(open_ids)]
        for index, left in enumerate(active_sets):
            for right in active_sets[index + 1 :]:
                if left.intersection(right):
                    raise LifecyclePositionAccountError(
                        "one decision cannot occupy multiple active lifecycle buckets"
                    )
        if set(open_ids).intersection(closed_ids):
            raise LifecyclePositionAccountError(
                "one decision cannot be both open and closed"
            )

        if any(x.reserved_utc > self.as_of_utc for x in stocks + options):
            raise LifecyclePositionAccountError(
                "active reservation cannot postdate position account state"
            )
        if any(x.opened_utc > self.as_of_utc for x in positions):
            raise LifecyclePositionAccountError(
                "open position cannot postdate position account state"
            )
        if any(x.exited_utc > self.as_of_utc for x in closed):
            raise LifecyclePositionAccountError(
                "closed trade cannot postdate position account state"
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
                raise LifecyclePositionAccountError(
                    f"{label} must equal constituent sum"
                )

        expected_book = (
            self.initial_equity
            - self.cumulative_entry_fees_dollars
            + self.cumulative_account_realized_pnl_dollars
        )
        if not _same(self.account_book_equity, expected_book):
            raise LifecyclePositionAccountError(
                "account book equity must preserve fee and realized-P&L semantics"
            )
        balance = (
            self.cash
            + self.stock_reserved_capital
            + self.option_reserved_capital
            + self.open_entry_book_value_dollars
        )
        if not _same(self.account_book_equity, balance):
            raise LifecyclePositionAccountError(
                "position account must reconcile cash, reservations, and open book value"
            )

        forbidden = (
            self.reservation_mutation_authority,
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
            raise LifecyclePositionAccountError(
                "lifecycle position state cannot grant reservation, exit, mark, "
                "provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return lifecycle_position_account_state_fingerprint(self)


@dataclass(frozen=True)
class LifecyclePositionLedgerEventV1:
    sequence: int
    occurred_utc: datetime
    decision_record_fingerprint: str
    fill_fingerprint: str
    funding_terms_fingerprint: str
    reservation_fingerprint: str
    position_fingerprint: str
    instrument_kind: InstrumentKind
    cash_delta_dollars: float
    stock_reserved_capital_delta_dollars: float
    option_reserved_capital_delta_dollars: float
    open_entry_book_value_delta_dollars: float
    entry_fee_delta_dollars: float
    stock_gross_entry_exposure_delta_dollars: float
    option_signed_delta_entry_reference_delta_dollars: float
    option_abs_delta_entry_reference_delta_dollars: float
    option_premium_at_risk_delta_dollars: float
    before_state_fingerprint: str
    after_state_fingerprint: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise LifecyclePositionAccountError(
                "position ledger sequence must be positive"
            )
        _require_aware(self.occurred_utc, label="position ledger timestamp")
        for label, value in (
            ("decision record", self.decision_record_fingerprint),
            ("fill", self.fill_fingerprint),
            ("funding terms", self.funding_terms_fingerprint),
            ("reservation", self.reservation_fingerprint),
            ("position", self.position_fingerprint),
            ("before state", self.before_state_fingerprint),
            ("after state", self.after_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        deltas = (
            self.cash_delta_dollars,
            self.stock_reserved_capital_delta_dollars,
            self.option_reserved_capital_delta_dollars,
            self.open_entry_book_value_delta_dollars,
            self.entry_fee_delta_dollars,
            self.stock_gross_entry_exposure_delta_dollars,
            self.option_signed_delta_entry_reference_delta_dollars,
            self.option_abs_delta_entry_reference_delta_dollars,
            self.option_premium_at_risk_delta_dollars,
        )
        if not all(math.isfinite(value) for value in deltas):
            raise LifecyclePositionAccountError(
                "position ledger deltas must be finite"
            )
        if self.open_entry_book_value_delta_dollars <= 0.0:
            raise LifecyclePositionAccountError(
                "position creation requires positive entry book value"
            )
        if self.entry_fee_delta_dollars < 0.0:
            raise LifecyclePositionAccountError(
                "position entry fee delta cannot be negative"
            )
        if self.instrument_kind == InstrumentKind.STOCK:
            if self.stock_reserved_capital_delta_dollars >= 0.0:
                raise LifecyclePositionAccountError(
                    "stock position creation must consume stock reservation"
                )
            if self.stock_gross_entry_exposure_delta_dollars <= 0.0:
                raise LifecyclePositionAccountError(
                    "stock position creation must add stock exposure"
                )
            if any(
                not _same(value, 0.0)
                for value in (
                    self.option_reserved_capital_delta_dollars,
                    self.option_signed_delta_entry_reference_delta_dollars,
                    self.option_abs_delta_entry_reference_delta_dollars,
                    self.option_premium_at_risk_delta_dollars,
                )
            ):
                raise LifecyclePositionAccountError(
                    "stock position event cannot mutate option buckets"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.option_reserved_capital_delta_dollars >= 0.0:
                raise LifecyclePositionAccountError(
                    "option position creation must consume option reservation"
                )
            if not _same(self.stock_reserved_capital_delta_dollars, 0.0):
                raise LifecyclePositionAccountError(
                    "option position event cannot mutate stock reserve"
                )
            if not _same(
                self.stock_gross_entry_exposure_delta_dollars,
                0.0,
            ):
                raise LifecyclePositionAccountError(
                    "option position event cannot mutate stock exposure"
                )
            if self.option_abs_delta_entry_reference_delta_dollars <= 0.0:
                raise LifecyclePositionAccountError(
                    "option position creation must add absolute delta reference"
                )
            if self.option_premium_at_risk_delta_dollars <= 0.0:
                raise LifecyclePositionAccountError(
                    "option position creation must add premium at risk"
                )
        else:
            raise LifecyclePositionAccountError(
                "unsupported lifecycle position ledger instrument kind"
            )
        if not self.reason_codes:
            raise LifecyclePositionAccountError(
                "position ledger event requires reason codes"
            )

    @property
    def event_fingerprint(self) -> str:
        return lifecycle_position_ledger_event_fingerprint(self)


@dataclass(frozen=True)
class LifecyclePositionLedgerV1:
    contract_version: str
    contract_fingerprint: str
    source_reservation_state_fingerprint: str
    source_reservation_ledger_fingerprint: str
    initial_state_fingerprint: str
    events: tuple[LifecyclePositionLedgerEventV1, ...]

    def __post_init__(self) -> None:
        if self.contract_version != LIFECYCLE_POSITION_ACCOUNT_CONTRACT_VERSION:
            raise LifecyclePositionAccountError(
                "position ledger contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise LifecyclePositionAccountError(
                "position ledger contract fingerprint mismatch"
            )
        for label, value in (
            ("source reservation state", self.source_reservation_state_fingerprint),
            ("source reservation ledger", self.source_reservation_ledger_fingerprint),
            ("initial state", self.initial_state_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        previous_after = self.initial_state_fingerprint
        previous_time: datetime | None = None
        seen_fills: set[str] = set()
        seen_decisions: set[str] = set()
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence:
                raise LifecyclePositionAccountError(
                    "position ledger sequence must be contiguous"
                )
            if previous_time is not None and event.occurred_utc < previous_time:
                raise LifecyclePositionAccountError(
                    "position ledger events must be chronological"
                )
            if event.before_state_fingerprint != previous_after:
                raise LifecyclePositionAccountError(
                    "position ledger before-state chain is broken"
                )
            if event.fill_fingerprint in seen_fills:
                raise LifecyclePositionAccountError(
                    "one lifecycle fill can create only one position event"
                )
            if event.decision_record_fingerprint in seen_decisions:
                raise LifecyclePositionAccountError(
                    "one decision can create only one new lifecycle position"
                )
            seen_fills.add(event.fill_fingerprint)
            seen_decisions.add(event.decision_record_fingerprint)
            previous_after = event.after_state_fingerprint
            previous_time = event.occurred_utc

    @property
    def ledger_fingerprint(self) -> str:
        return lifecycle_position_ledger_fingerprint(self)


@dataclass(frozen=True)
class LifecyclePositionAccountV1:
    state: LifecyclePositionAccountStateV1
    ledger: LifecyclePositionLedgerV1

    def __post_init__(self) -> None:
        if (
            self.state.source_reservation_state_fingerprint
            != self.ledger.source_reservation_state_fingerprint
            or self.state.source_reservation_ledger_fingerprint
            != self.ledger.source_reservation_ledger_fingerprint
        ):
            raise LifecyclePositionAccountError(
                "position state and ledger source lineage must match"
            )
        expected = (
            self.ledger.events[-1].after_state_fingerprint
            if self.ledger.events
            else self.ledger.initial_state_fingerprint
        )
        if self.state.state_fingerprint != expected:
            raise LifecyclePositionAccountError(
                "position state must match latest ledger fingerprint"
            )


@dataclass(frozen=True)
class LifecyclePositionTransitionV1:
    account: LifecyclePositionAccountV1
    event: LifecyclePositionLedgerEventV1 | None
    position: SimulatedOpenPositionV1
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class LifecyclePositionBatchResultV1:
    account: LifecyclePositionAccountV1
    ordered_fill_fingerprints: tuple[str, ...]
    transitions: tuple[LifecyclePositionTransitionV1, ...]


def lifecycle_position_account_state_fingerprint(
    state: LifecyclePositionAccountStateV1,
) -> str:
    return _fingerprint_payload(state)


def lifecycle_position_ledger_event_fingerprint(
    event: LifecyclePositionLedgerEventV1,
) -> str:
    return _fingerprint_payload(event)


def lifecycle_position_ledger_fingerprint(
    ledger: LifecyclePositionLedgerV1,
) -> str:
    return _fingerprint_payload(ledger)


def _validate_source(source: LifecycleReservationAccountV1) -> None:
    if (
        source.state.contract_fingerprint
        != LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise LifecyclePositionAccountError(
            "source must use accepted lifecycle reservation contract"
        )
    if (
        source.state.state_fingerprint
        != lifecycle_reservation_account_state_fingerprint(source.state)
    ):
        raise LifecyclePositionAccountError(
            "source lifecycle reservation state fingerprint mismatch"
        )
    if (
        source.ledger.ledger_fingerprint
        != lifecycle_reservation_ledger_fingerprint(source.ledger)
    ):
        raise LifecyclePositionAccountError(
            "source lifecycle reservation ledger fingerprint mismatch"
        )
    expected = (
        source.ledger.events[-1].after_state_fingerprint
        if source.ledger.events
        else source.ledger.initial_state_fingerprint
    )
    if expected != source.state.state_fingerprint:
        raise LifecyclePositionAccountError(
            "source lifecycle reservation ledger does not terminate at state"
        )


def initialize_lifecycle_position_account_v1(
    *,
    source: LifecycleReservationAccountV1,
) -> LifecyclePositionAccountV1:
    _validate_source(source)
    item = source.state
    state = LifecyclePositionAccountStateV1(
        contract_version=LIFECYCLE_POSITION_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT,
        source_reservation_contract_fingerprint=item.contract_fingerprint,
        source_reservation_state_fingerprint=item.state_fingerprint,
        source_reservation_ledger_fingerprint=source.ledger.ledger_fingerprint,
        source_reservation_cash_dollars=item.cash,
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
        closed_trades=item.closed_trades,
    )
    ledger = LifecyclePositionLedgerV1(
        contract_version=LIFECYCLE_POSITION_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=LIFECYCLE_POSITION_ACCOUNT_CONTRACT_FINGERPRINT,
        source_reservation_state_fingerprint=item.state_fingerprint,
        source_reservation_ledger_fingerprint=source.ledger.ledger_fingerprint,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return LifecyclePositionAccountV1(state=state, ledger=ledger)


def _build_state(
    *,
    previous: LifecyclePositionAccountStateV1,
    as_of_utc: datetime,
    cash: float,
    cumulative_entry_fees_dollars: float,
    stock_reservations: Sequence[SimulatedStockReservationV2],
    option_reservations: Sequence[SimulatedOptionReservationV2],
    open_positions: Sequence[SimulatedOpenPositionV1],
) -> LifecyclePositionAccountStateV1:
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
    positions = tuple(
        sorted(
            open_positions,
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    stock_reserved = sum(x.reserved_capital for x in stocks)
    option_reserved = sum(x.reserved_capital for x in options)
    open_book = sum(x.entry_book_value_dollars for x in positions)
    return LifecyclePositionAccountStateV1(
        contract_version=previous.contract_version,
        contract_fingerprint=previous.contract_fingerprint,
        source_reservation_contract_fingerprint=(
            previous.source_reservation_contract_fingerprint
        ),
        source_reservation_state_fingerprint=(
            previous.source_reservation_state_fingerprint
        ),
        source_reservation_ledger_fingerprint=(
            previous.source_reservation_ledger_fingerprint
        ),
        source_reservation_cash_dollars=previous.source_reservation_cash_dollars,
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        cumulative_entry_fees_dollars=_zero(
            cumulative_entry_fees_dollars
        ),
        cumulative_exit_fees_dollars=previous.cumulative_exit_fees_dollars,
        cumulative_account_realized_pnl_dollars=(
            previous.cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            previous.cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=_zero(cash),
        account_book_equity=_zero(
            previous.initial_equity
            - cumulative_entry_fees_dollars
            + previous.cumulative_account_realized_pnl_dollars
        ),
        stock_reserved_capital=_zero(stock_reserved),
        option_reserved_capital=_zero(option_reserved),
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
        open_entry_book_value_dollars=_zero(open_book),
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
        stock_reservations=stocks,
        option_reservations=options,
        open_positions=positions,
        closed_trades=previous.closed_trades,
    )


def _validate_evidence(
    *,
    account: LifecyclePositionAccountV1,
    fill: LifecycleEntryFillEvidenceV1,
    funding: LifecycleFundingTermsV1,
):
    if fill.contract_fingerprint != LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT:
        raise LifecyclePositionAccountError(
            "lifecycle entry-fill contract fingerprint mismatch"
        )
    if funding.contract_fingerprint != LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT:
        raise LifecyclePositionAccountError(
            "lifecycle funding contract fingerprint mismatch"
        )
    if fill.fill_fingerprint != lifecycle_entry_fill_fingerprint(fill):
        raise LifecyclePositionAccountError(
            "lifecycle entry-fill fingerprint mismatch"
        )
    if funding.terms_fingerprint != lifecycle_funding_terms_fingerprint(funding):
        raise LifecyclePositionAccountError(
            "lifecycle funding fingerprint mismatch"
        )

    source_fp = account.state.source_reservation_state_fingerprint
    if (
        fill.lifecycle_reservation_state_fingerprint != source_fp
        or funding.lifecycle_reservation_state_fingerprint != source_fp
    ):
        raise LifecyclePositionAccountError(
            "fill/funding must bind immutable source lifecycle reservation state"
        )
    pairs = (
        (funding.fill_fingerprint, fill.fill_fingerprint, "funding fill"),
        (
            funding.active_reservation_fingerprint,
            fill.active_reservation_fingerprint,
            "funding reservation",
        ),
        (
            funding.decision_record_fingerprint,
            fill.decision_record_fingerprint,
            "funding decision",
        ),
        (
            funding.candidate_fingerprint,
            fill.candidate_fingerprint,
            "funding candidate",
        ),
        (funding.instrument_kind, fill.instrument_kind, "funding instrument"),
        (funding.direction, fill.direction, "funding direction"),
    )
    for left, right, label in pairs:
        if left != right:
            raise LifecyclePositionAccountError(
                f"{label} lineage mismatch"
            )
    if not funding.fully_funded:
        raise LifecyclePositionAccountError(
            "lifecycle funding terms must be fully funded"
        )

    reservations = (
        account.state.stock_reservations
        if fill.instrument_kind == InstrumentKind.STOCK
        else account.state.option_reservations
    )
    matches = tuple(
        x
        for x in reservations
        if x.decision_record_fingerprint
        == fill.decision_record_fingerprint
    )
    if len(matches) != 1:
        raise LifecyclePositionAccountError(
            "exact current lifecycle reservation is required"
        )
    reservation = matches[0]
    if (
        simulated_reservation_fingerprint(reservation)
        != fill.active_reservation_fingerprint
    ):
        raise LifecyclePositionAccountError(
            "current lifecycle reservation fingerprint mismatch"
        )
    if not _same(
        reservation.reserved_capital,
        fill.reserved_capital_dollars,
    ):
        raise LifecyclePositionAccountError(
            "current lifecycle reserved-capital mismatch"
        )

    if fill.instrument_kind == InstrumentKind.STOCK:
        required = (
            fill.gross_fill_notional_dollars
            + fill.entry_fees_dollars
        )
        expected_supplemental = max(
            0.0,
            required - reservation.reserved_capital,
        )
        expected_unspent = max(
            0.0,
            reservation.reserved_capital - required,
        )
        if funding.funding_model != LifecycleFundingModel.CASH_ONLY_STOCK_LONG:
            raise LifecyclePositionAccountError(
                "stock lifecycle funding model mismatch"
            )
    elif fill.instrument_kind == InstrumentKind.OPTION:
        if (
            fill.cash_debit_dollars is None
            or fill.unspent_reserved_capital_dollars is None
        ):
            raise LifecyclePositionAccountError(
                "option lifecycle fill is missing reserved debit semantics"
            )
        required = fill.cash_debit_dollars
        expected_supplemental = 0.0
        expected_unspent = fill.unspent_reserved_capital_dollars
        if (
            funding.funding_model
            != LifecycleFundingModel.RESERVED_LONG_OPTION_DEBIT
        ):
            raise LifecyclePositionAccountError(
                "option lifecycle funding model mismatch"
            )
    else:
        raise LifecyclePositionAccountError(
            "unsupported lifecycle position instrument kind"
        )

    arithmetic = (
        (
            funding.required_cash_dollars,
            required,
            "required cash",
        ),
        (
            funding.reserved_capital_dollars,
            reservation.reserved_capital,
            "reserved capital",
        ),
        (
            funding.supplemental_unreserved_cash_required_dollars,
            expected_supplemental,
            "supplemental cash",
        ),
        (
            funding.unspent_reserved_capital_dollars,
            expected_unspent,
            "unspent reserve",
        ),
        (
            funding.projected_unreserved_cash_after_entry_dollars,
            account.state.source_reservation_cash_dollars
            - expected_supplemental
            + expected_unspent,
            "source projected cash",
        ),
    )
    for actual, expected, label in arithmetic:
        if not _same(actual, expected):
            raise LifecyclePositionAccountError(
                f"lifecycle funding {label} mismatch"
            )
    return reservation


def _build_position(
    *,
    fill: LifecycleEntryFillEvidenceV1,
    funding: LifecycleFundingTermsV1,
    reservation: SimulatedStockReservationV2 | SimulatedOptionReservationV2,
) -> SimulatedOpenPositionV1:
    if fill.instrument_kind == InstrumentKind.STOCK:
        stock_exposure = fill.gross_fill_notional_dollars
        option_premium = 0.0
        signed_delta = 0.0
        abs_delta = 0.0
    else:
        if not isinstance(reservation, SimulatedOptionReservationV2):
            raise LifecyclePositionAccountError(
                "option entry requires option reservation"
            )
        stock_exposure = 0.0
        option_premium = fill.gross_fill_notional_dollars
        signed_delta = reservation.signed_delta_equivalent_notional
        abs_delta = reservation.abs_delta_equivalent_notional

    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=(
            fill.lifecycle_reservation_state_fingerprint
        ),
        decision_record_fingerprint=fill.decision_record_fingerprint,
        candidate_fingerprint=fill.candidate_fingerprint,
        fill_fingerprint=fill.fill_fingerprint,
        funding_terms_fingerprint=funding.terms_fingerprint,
        reservation_fingerprint=fill.active_reservation_fingerprint,
        option_reservation_terms_fingerprint=(
            fill.option_reservation_terms_fingerprint
        ),
        option_economics_result_fingerprint=(
            fill.option_economics_result_fingerprint
        ),
        instrument_kind=fill.instrument_kind,
        instrument_id=fill.instrument_id,
        ticker=fill.ticker,
        direction=fill.direction,
        candidate_identifier=fill.candidate_identifier,
        option_contract_ticker=fill.option_contract_ticker,
        option_contract_type=fill.option_contract_type,
        opened_utc=fill.filled_utc,
        quantity=fill.quantity,
        quantity_unit=fill.quantity_unit,
        entry_price_per_unit=fill.fill_price_per_unit,
        contract_multiplier=fill.contract_multiplier,
        entry_book_value_dollars=fill.gross_fill_notional_dollars,
        entry_fees_dollars=fill.entry_fees_dollars,
        all_in_cash_cost_basis_dollars=funding.required_cash_dollars,
        original_reserved_capital_dollars=reservation.reserved_capital,
        supplemental_cash_consumed_dollars=(
            funding.supplemental_unreserved_cash_required_dollars
        ),
        unspent_reserve_returned_dollars=(
            funding.unspent_reserved_capital_dollars
        ),
        stock_gross_entry_exposure_dollars=stock_exposure,
        option_premium_at_risk_dollars=option_premium,
        option_signed_delta_equivalent_entry_reference_dollars=(
            signed_delta
        ),
        option_abs_delta_equivalent_entry_reference_dollars=abs_delta,
        reason_codes=(
            "EXACT_LIFECYCLE_RESERVATION_FILL_FUNDING_LINEAGE",
            "ENTRY_FEE_EXPENSED_ONCE",
            "RESERVATION_CONSUMED_ONCE",
            "PRIOR_LIFECYCLE_HISTORY_PRESERVED",
        ),
    )


def apply_lifecycle_entry_v1(
    account: LifecyclePositionAccountV1,
    *,
    fill: LifecycleEntryFillEvidenceV1,
    funding: LifecycleFundingTermsV1,
) -> LifecyclePositionTransitionV1:
    existing = tuple(
        x
        for x in account.state.open_positions
        if x.decision_record_fingerprint
        == fill.decision_record_fingerprint
    )
    if existing:
        if len(existing) != 1:
            raise LifecyclePositionAccountError(
                "duplicate lifecycle open-position decision lineage"
            )
        position = existing[0]
        if (
            position.fill_fingerprint == fill.fill_fingerprint
            and position.funding_terms_fingerprint
            == funding.terms_fingerprint
        ):
            return LifecyclePositionTransitionV1(
                account=account,
                event=None,
                position=position,
                idempotent_reuse=True,
                reason_codes=("DUPLICATE_LIFECYCLE_ENTRY_IDEMPOTENT_REUSE",),
            )
        raise LifecyclePositionAccountError(
            "conflicting fill for an already-open lifecycle decision"
        )

    if fill.filled_utc < account.state.as_of_utc:
        raise LifecyclePositionAccountError(
            "fill timestamp cannot precede current lifecycle position state"
        )

    reservation = _validate_evidence(
        account=account,
        fill=fill,
        funding=funding,
    )
    supplemental = funding.supplemental_unreserved_cash_required_dollars
    unspent = funding.unspent_reserved_capital_dollars
    if account.state.cash + _TOLERANCE < supplemental:
        raise LifecyclePositionAccountError(
            "insufficient current cash after competing lifecycle entries"
        )
    new_cash = account.state.cash - supplemental + unspent
    if new_cash < -_TOLERANCE:
        raise LifecyclePositionAccountError(
            "lifecycle entry would create negative current cash"
        )

    position = _build_position(
        fill=fill,
        funding=funding,
        reservation=reservation,
    )
    if fill.instrument_kind == InstrumentKind.STOCK:
        stocks = tuple(
            x
            for x in account.state.stock_reservations
            if x.decision_record_fingerprint
            != fill.decision_record_fingerprint
        )
        options = account.state.option_reservations
        stock_reserve_delta = -reservation.reserved_capital
        option_reserve_delta = 0.0
    else:
        stocks = account.state.stock_reservations
        options = tuple(
            x
            for x in account.state.option_reservations
            if x.decision_record_fingerprint
            != fill.decision_record_fingerprint
        )
        stock_reserve_delta = 0.0
        option_reserve_delta = -reservation.reserved_capital

    next_state = _build_state(
        previous=account.state,
        as_of_utc=fill.filled_utc,
        cash=new_cash,
        cumulative_entry_fees_dollars=(
            account.state.cumulative_entry_fees_dollars
            + fill.entry_fees_dollars
        ),
        stock_reservations=stocks,
        option_reservations=options,
        open_positions=account.state.open_positions + (position,),
    )
    event = LifecyclePositionLedgerEventV1(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=fill.filled_utc,
        decision_record_fingerprint=fill.decision_record_fingerprint,
        fill_fingerprint=fill.fill_fingerprint,
        funding_terms_fingerprint=funding.terms_fingerprint,
        reservation_fingerprint=fill.active_reservation_fingerprint,
        position_fingerprint=position.position_fingerprint,
        instrument_kind=fill.instrument_kind,
        cash_delta_dollars=_zero(new_cash - account.state.cash),
        stock_reserved_capital_delta_dollars=_zero(stock_reserve_delta),
        option_reserved_capital_delta_dollars=_zero(option_reserve_delta),
        open_entry_book_value_delta_dollars=(
            position.entry_book_value_dollars
        ),
        entry_fee_delta_dollars=position.entry_fees_dollars,
        stock_gross_entry_exposure_delta_dollars=(
            position.stock_gross_entry_exposure_dollars
        ),
        option_signed_delta_entry_reference_delta_dollars=(
            position.option_signed_delta_equivalent_entry_reference_dollars
        ),
        option_abs_delta_entry_reference_delta_dollars=(
            position.option_abs_delta_equivalent_entry_reference_dollars
        ),
        option_premium_at_risk_delta_dollars=(
            position.option_premium_at_risk_dollars
        ),
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
        reason_codes=(
            "LIFECYCLE_RESERVATION_CONSUMED",
            "LIFECYCLE_POSITION_CREATED_ENTRY_BOOK_ONLY",
            "ENTRY_FEE_EXPENSED_ONCE",
            "PRIOR_OPEN_CLOSED_AND_REALIZED_HISTORY_PRESERVED",
        ),
    )
    next_ledger = LifecyclePositionLedgerV1(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        source_reservation_state_fingerprint=(
            account.ledger.source_reservation_state_fingerprint
        ),
        source_reservation_ledger_fingerprint=(
            account.ledger.source_reservation_ledger_fingerprint
        ),
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = LifecyclePositionAccountV1(
        state=next_state,
        ledger=next_ledger,
    )
    return LifecyclePositionTransitionV1(
        account=next_account,
        event=event,
        position=position,
        idempotent_reuse=False,
        reason_codes=("LIFECYCLE_POSITION_OPENED",),
    )


def apply_lifecycle_entry_batch_v1(
    account: LifecyclePositionAccountV1,
    entries: Sequence[
        tuple[LifecycleEntryFillEvidenceV1, LifecycleFundingTermsV1]
    ],
) -> LifecyclePositionBatchResultV1:
    ordered = tuple(
        sorted(
            entries,
            key=lambda item: (
                item[0].filled_utc,
                item[0].fill_fingerprint,
            ),
        )
    )
    current = account
    transitions: list[LifecyclePositionTransitionV1] = []
    for fill, funding in ordered:
        transition = apply_lifecycle_entry_v1(
            current,
            fill=fill,
            funding=funding,
        )
        transitions.append(transition)
        current = transition.account
    return LifecyclePositionBatchResultV1(
        account=current,
        ordered_fill_fingerprints=tuple(
            fill.fill_fingerprint for fill, _ in ordered
        ),
        transitions=tuple(transitions),
    )


def replay_lifecycle_position_account_v1(
    *,
    source: LifecycleReservationAccountV1,
    entries: Sequence[
        tuple[LifecycleEntryFillEvidenceV1, LifecycleFundingTermsV1]
    ],
) -> LifecyclePositionBatchResultV1:
    return apply_lifecycle_entry_batch_v1(
        initialize_lifecycle_position_account_v1(source=source),
        entries,
    )


def verify_lifecycle_position_account_replay_v1(
    *,
    account: LifecyclePositionAccountV1,
    source: LifecycleReservationAccountV1,
    entries: Sequence[
        tuple[LifecycleEntryFillEvidenceV1, LifecycleFundingTermsV1]
    ],
) -> None:
    replay = replay_lifecycle_position_account_v1(
        source=source,
        entries=entries,
    )
    if replay.account.state.state_fingerprint != account.state.state_fingerprint:
        raise LifecyclePositionAccountError(
            "lifecycle position replay state fingerprint mismatch"
        )
    if (
        replay.account.ledger.ledger_fingerprint
        != account.ledger.ledger_fingerprint
    ):
        raise LifecyclePositionAccountError(
            "lifecycle position replay ledger fingerprint mismatch"
        )
