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
    SimulationAccountV2,
)
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.funding_terms import (
    SimulationFundingCollateralTerms,
    simulation_funding_terms_fingerprint,
)
from packages.simulation.funding_terms_contract import (
    SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT,
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.simulated_fill import (
    SimulatedEntryFillEvidence,
    simulated_entry_fill_fingerprint,
    simulated_reservation_fingerprint,
)
from packages.simulation.simulated_fill_contract import (
    SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT,
)


OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION = str(
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class OpenPositionAccountStateError(ValueError):
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


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OpenPositionAccountStateError(f"{label} must be timezone-aware")


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise OpenPositionAccountStateError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise OpenPositionAccountStateError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise OpenPositionAccountStateError(f"{label} must be finite and nonnegative")


def _require_positive(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise OpenPositionAccountStateError(f"{label} must be finite and positive")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


@dataclass(frozen=True)
class SimulatedOpenPositionV1:
    source_account_state_fingerprint: str
    decision_record_fingerprint: str
    candidate_fingerprint: str
    fill_fingerprint: str
    funding_terms_fingerprint: str
    reservation_fingerprint: str
    option_reservation_terms_fingerprint: str | None
    option_economics_result_fingerprint: str | None
    instrument_kind: InstrumentKind
    instrument_id: str
    ticker: str
    direction: DiscoveryDirection
    candidate_identifier: str
    option_contract_ticker: str | None
    option_contract_type: str | None
    opened_utc: datetime
    quantity: float
    quantity_unit: str
    entry_price_per_unit: float
    contract_multiplier: float
    entry_book_value_dollars: float
    entry_fees_dollars: float
    all_in_cash_cost_basis_dollars: float
    original_reserved_capital_dollars: float
    supplemental_cash_consumed_dollars: float
    unspent_reserve_returned_dollars: float
    stock_gross_entry_exposure_dollars: float
    option_premium_at_risk_dollars: float
    option_signed_delta_equivalent_entry_reference_dollars: float
    option_abs_delta_equivalent_entry_reference_dollars: float
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for label, value in (
            ("source account state", self.source_account_state_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("candidate", self.candidate_fingerprint),
            ("fill", self.fill_fingerprint),
            ("funding terms", self.funding_terms_fingerprint),
            ("reservation", self.reservation_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.opened_utc, label="position opened timestamp")
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise OpenPositionAccountStateError("open-position identity cannot be blank")
        if not self.candidate_identifier.strip():
            raise OpenPositionAccountStateError("open-position candidate identifier cannot be blank")
        for label, value in (
            ("quantity", self.quantity),
            ("entry price", self.entry_price_per_unit),
            ("contract multiplier", self.contract_multiplier),
            ("entry book value", self.entry_book_value_dollars),
            ("all-in cash cost basis", self.all_in_cash_cost_basis_dollars),
            ("original reserved capital", self.original_reserved_capital_dollars),
        ):
            _require_positive(value, label=label)
        for label, value in (
            ("entry fees", self.entry_fees_dollars),
            ("supplemental cash", self.supplemental_cash_consumed_dollars),
            ("unspent reserve", self.unspent_reserve_returned_dollars),
            ("stock gross entry exposure", self.stock_gross_entry_exposure_dollars),
            ("option premium at risk", self.option_premium_at_risk_dollars),
            ("option absolute delta reference", self.option_abs_delta_equivalent_entry_reference_dollars),
        ):
            _require_nonnegative(value, label=label)
        if not math.isfinite(self.option_signed_delta_equivalent_entry_reference_dollars):
            raise OpenPositionAccountStateError("option signed delta reference must be finite")
        expected_book_value = self.quantity * self.entry_price_per_unit * self.contract_multiplier
        if not _same(self.entry_book_value_dollars, expected_book_value):
            raise OpenPositionAccountStateError("entry book value must match quantity, price, and multiplier")
        if not _same(
            self.all_in_cash_cost_basis_dollars,
            self.entry_book_value_dollars + self.entry_fees_dollars,
        ):
            raise OpenPositionAccountStateError("all-in cash cost basis must equal entry book value plus fees")
        if (
            self.supplemental_cash_consumed_dollars > _TOLERANCE
            and self.unspent_reserve_returned_dollars > _TOLERANCE
        ):
            raise OpenPositionAccountStateError("a position cannot both consume supplemental cash and return unspent reserve")
        if not _same(
            self.all_in_cash_cost_basis_dollars,
            self.original_reserved_capital_dollars
            + self.supplemental_cash_consumed_dollars
            - self.unspent_reserve_returned_dollars,
        ):
            raise OpenPositionAccountStateError("position cash funding must reconcile to the released reservation")
        if not self.reason_codes:
            raise OpenPositionAccountStateError("open position requires reason codes")

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.direction != DiscoveryDirection.BULLISH:
                raise OpenPositionAccountStateError("v1 open stock positions must be bullish cash-funded longs")
            if self.quantity_unit != "SHARES" or not _same(self.contract_multiplier, 1.0):
                raise OpenPositionAccountStateError("stock position quantity/multiplier mismatch")
            if self.option_contract_ticker is not None or self.option_contract_type is not None:
                raise OpenPositionAccountStateError("stock position cannot carry option contract identity")
            if self.option_reservation_terms_fingerprint is not None or self.option_economics_result_fingerprint is not None:
                raise OpenPositionAccountStateError("stock position cannot carry option lineage")
            if not _same(self.stock_gross_entry_exposure_dollars, self.entry_book_value_dollars):
                raise OpenPositionAccountStateError("stock gross entry exposure must equal stock entry book value")
            if any(
                not _same(value, 0.0)
                for value in (
                    self.option_premium_at_risk_dollars,
                    self.option_signed_delta_equivalent_entry_reference_dollars,
                    self.option_abs_delta_equivalent_entry_reference_dollars,
                )
            ):
                raise OpenPositionAccountStateError("stock position cannot carry option risk/exposure")
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.direction not in {DiscoveryDirection.BULLISH, DiscoveryDirection.BEARISH}:
                raise OpenPositionAccountStateError("long-option position direction must be bullish or bearish")
            if self.quantity_unit != "CONTRACTS" or not _same(self.quantity, round(self.quantity)):
                raise OpenPositionAccountStateError("option position quantity must be integral contracts")
            if not self.option_contract_ticker or self.option_contract_type not in {"call", "put"}:
                raise OpenPositionAccountStateError("option position requires contract identity")
            if self.option_reservation_terms_fingerprint is None or self.option_economics_result_fingerprint is None:
                raise OpenPositionAccountStateError("option position requires reservation/economics lineage")
            _require_fingerprint(self.option_reservation_terms_fingerprint, label="option reservation terms fingerprint")
            _require_fingerprint(self.option_economics_result_fingerprint, label="option economics fingerprint")
            if not _same(self.stock_gross_entry_exposure_dollars, 0.0):
                raise OpenPositionAccountStateError("option position cannot mutate stock gross exposure")
            if not _same(self.option_premium_at_risk_dollars, self.entry_book_value_dollars):
                raise OpenPositionAccountStateError("option premium at risk must equal entry book value")
            if _same(self.option_signed_delta_equivalent_entry_reference_dollars, 0.0):
                raise OpenPositionAccountStateError("option entry delta reference must be nonzero")
            if not _same(
                self.option_abs_delta_equivalent_entry_reference_dollars,
                abs(self.option_signed_delta_equivalent_entry_reference_dollars),
            ):
                raise OpenPositionAccountStateError("option absolute delta reference mismatch")
            if self.direction == DiscoveryDirection.BULLISH and self.option_signed_delta_equivalent_entry_reference_dollars <= 0.0:
                raise OpenPositionAccountStateError("bullish option requires positive entry delta reference")
            if self.direction == DiscoveryDirection.BEARISH and self.option_signed_delta_equivalent_entry_reference_dollars >= 0.0:
                raise OpenPositionAccountStateError("bearish option requires negative entry delta reference")
        else:
            raise OpenPositionAccountStateError("unsupported open-position instrument kind")

    @property
    def position_fingerprint(self) -> str:
        return simulated_open_position_fingerprint(self)


@dataclass(frozen=True)
class OpenPositionAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    source_account_contract_fingerprint: str
    source_account_state_fingerprint: str
    as_of_utc: datetime
    initial_equity: float
    source_stock_gross_notional: float
    source_option_signed_delta_equivalent_notional: float
    source_option_abs_delta_equivalent_notional: float
    cash: float
    entry_book_equity: float
    cumulative_entry_fees_dollars: float
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
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    mark_to_market_authority: bool = False
    unrealized_pnl_authority: bool = False
    realized_pnl_authority: bool = False
    exit_closeout_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION:
            raise OpenPositionAccountStateError("open-position account-state contract version mismatch")
        if self.contract_fingerprint != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise OpenPositionAccountStateError("open-position account-state contract fingerprint mismatch")
        if self.source_account_contract_fingerprint != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT:
            raise OpenPositionAccountStateError("source reservation account contract fingerprint mismatch")
        _require_fingerprint(self.source_account_state_fingerprint, label="source account-state fingerprint")
        _require_aware(self.as_of_utc, label="open-position account-state timestamp")
        _require_positive(self.initial_equity, label="initial equity")
        for label, value in (
            ("source stock gross notional", self.source_stock_gross_notional),
            ("source option absolute delta", self.source_option_abs_delta_equivalent_notional),
            ("cash", self.cash),
            ("entry book equity", self.entry_book_equity),
            ("cumulative entry fees", self.cumulative_entry_fees_dollars),
            ("remaining stock reserved capital", self.remaining_stock_reserved_capital),
            ("remaining option reserved capital", self.remaining_option_reserved_capital),
            ("remaining stock gross notional", self.remaining_stock_gross_notional),
            ("remaining option absolute delta", self.remaining_option_abs_delta_equivalent_notional),
            ("open entry book value", self.open_entry_book_value_dollars),
            ("open stock gross entry exposure", self.open_stock_gross_entry_exposure_dollars),
            ("open option entry book value", self.open_option_entry_book_value_dollars),
            ("open option absolute delta reference", self.open_option_abs_delta_equivalent_entry_reference_dollars),
            ("open option premium at risk", self.open_option_premium_at_risk_dollars),
        ):
            _require_nonnegative(value, label=label)
        for label, value in (
            ("source option signed delta", self.source_option_signed_delta_equivalent_notional),
            ("remaining option signed delta", self.remaining_option_signed_delta_equivalent_notional),
            ("open option signed delta reference", self.open_option_signed_delta_equivalent_entry_reference_dollars),
        ):
            if not math.isfinite(value):
                raise OpenPositionAccountStateError(f"{label} must be finite")

        stock_reservations = tuple(sorted(self.remaining_stock_reservations, key=lambda item: item.decision_record_fingerprint))
        option_reservations = tuple(sorted(self.remaining_option_reservations, key=lambda item: item.decision_record_fingerprint))
        positions = tuple(sorted(self.open_positions, key=lambda item: item.decision_record_fingerprint))
        if stock_reservations != self.remaining_stock_reservations:
            raise OpenPositionAccountStateError("remaining stock reservations must be ordered")
        if option_reservations != self.remaining_option_reservations:
            raise OpenPositionAccountStateError("remaining option reservations must be ordered")
        if positions != self.open_positions:
            raise OpenPositionAccountStateError("open positions must be ordered by decision fingerprint")
        decision_ids = [item.decision_record_fingerprint for item in self.remaining_stock_reservations]
        decision_ids += [item.decision_record_fingerprint for item in self.remaining_option_reservations]
        position_ids = [item.decision_record_fingerprint for item in self.open_positions]
        if len(decision_ids) != len(set(decision_ids)) or len(position_ids) != len(set(position_ids)):
            raise OpenPositionAccountStateError("reservation/position decision fingerprints must be unique")
        if set(decision_ids).intersection(position_ids):
            raise OpenPositionAccountStateError("one decision cannot remain reserved and open simultaneously")
        if any(item.opened_utc > self.as_of_utc for item in self.open_positions):
            raise OpenPositionAccountStateError("open position cannot postdate account state")

        checks = (
            (self.remaining_stock_reserved_capital, sum(x.reserved_capital for x in self.remaining_stock_reservations), "remaining stock reserved capital"),
            (self.remaining_option_reserved_capital, sum(x.reserved_capital for x in self.remaining_option_reservations), "remaining option reserved capital"),
            (self.remaining_stock_gross_notional, sum(x.gross_notional for x in self.remaining_stock_reservations), "remaining stock gross notional"),
            (self.remaining_option_signed_delta_equivalent_notional, sum(x.signed_delta_equivalent_notional for x in self.remaining_option_reservations), "remaining option signed delta"),
            (self.remaining_option_abs_delta_equivalent_notional, sum(x.abs_delta_equivalent_notional for x in self.remaining_option_reservations), "remaining option absolute delta"),
            (self.open_entry_book_value_dollars, sum(x.entry_book_value_dollars for x in self.open_positions), "open entry book value"),
            (self.open_stock_gross_entry_exposure_dollars, sum(x.stock_gross_entry_exposure_dollars for x in self.open_positions), "open stock gross exposure"),
            (self.open_option_entry_book_value_dollars, sum(x.entry_book_value_dollars for x in self.open_positions if x.instrument_kind == InstrumentKind.OPTION), "open option entry book value"),
            (self.open_option_signed_delta_equivalent_entry_reference_dollars, sum(x.option_signed_delta_equivalent_entry_reference_dollars for x in self.open_positions), "open option signed delta reference"),
            (self.open_option_abs_delta_equivalent_entry_reference_dollars, sum(x.option_abs_delta_equivalent_entry_reference_dollars for x in self.open_positions), "open option absolute delta reference"),
            (self.open_option_premium_at_risk_dollars, sum(x.option_premium_at_risk_dollars for x in self.open_positions), "open option premium at risk"),
            (self.cumulative_entry_fees_dollars, sum(x.entry_fees_dollars for x in self.open_positions), "cumulative entry fees"),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise OpenPositionAccountStateError(f"{label} must equal constituent sum")
        if not _same(
            self.entry_book_equity,
            self.initial_equity - self.cumulative_entry_fees_dollars,
        ):
            raise OpenPositionAccountStateError("entry book equity must equal initial equity less entry fees")
        if not _same(
            self.cash
            + self.remaining_stock_reserved_capital
            + self.remaining_option_reserved_capital
            + self.open_entry_book_value_dollars,
            self.entry_book_equity,
        ):
            raise OpenPositionAccountStateError("cash, remaining reservations, and open entry book value must reconcile to entry book equity")
        if not _same(
            self.remaining_stock_gross_notional + self.open_stock_gross_entry_exposure_dollars,
            self.source_stock_gross_notional,
        ):
            raise OpenPositionAccountStateError("stock gross exposure must transfer exactly from reservation to open position")
        if not _same(
            self.remaining_option_signed_delta_equivalent_notional
            + self.open_option_signed_delta_equivalent_entry_reference_dollars,
            self.source_option_signed_delta_equivalent_notional,
        ):
            raise OpenPositionAccountStateError("option signed delta reference must transfer exactly from reservation to open position")
        if not _same(
            self.remaining_option_abs_delta_equivalent_notional
            + self.open_option_abs_delta_equivalent_entry_reference_dollars,
            self.source_option_abs_delta_equivalent_notional,
        ):
            raise OpenPositionAccountStateError("option absolute delta reference must transfer exactly from reservation to open position")

        forbidden = (
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.mark_to_market_authority,
            self.unrealized_pnl_authority,
            self.realized_pnl_authority,
            self.exit_closeout_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden):
            raise OpenPositionAccountStateError("open-position state cannot grant provider, broker, order, valuation, P&L, exit, trading, promotion, or confluence authority")

    @property
    def state_fingerprint(self) -> str:
        return open_position_account_state_fingerprint(self)


@dataclass(frozen=True)
class OpenPositionLedgerEventV1:
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
    reason_codes: tuple[str, ...]
    before_state_fingerprint: str
    after_state_fingerprint: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise OpenPositionAccountStateError("ledger sequence must be positive")
        _require_aware(self.occurred_utc, label="ledger timestamp")
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
        values = (
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
        if not all(math.isfinite(value) for value in values):
            raise OpenPositionAccountStateError("ledger deltas must be finite")
        if self.open_entry_book_value_delta_dollars <= 0.0 or self.entry_fee_delta_dollars < 0.0:
            raise OpenPositionAccountStateError("open-position ledger requires positive book value and nonnegative fee")
        if self.instrument_kind == InstrumentKind.STOCK:
            if self.stock_reserved_capital_delta_dollars >= 0.0 or self.option_reserved_capital_delta_dollars != 0.0:
                raise OpenPositionAccountStateError("stock open event must release stock reservation only")
            if self.stock_gross_entry_exposure_delta_dollars <= 0.0:
                raise OpenPositionAccountStateError("stock open event requires positive stock exposure")
            if any(
                not _same(value, 0.0)
                for value in (
                    self.option_signed_delta_entry_reference_delta_dollars,
                    self.option_abs_delta_entry_reference_delta_dollars,
                    self.option_premium_at_risk_delta_dollars,
                )
            ):
                raise OpenPositionAccountStateError("stock open event cannot add option exposure")
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.option_reserved_capital_delta_dollars >= 0.0 or self.stock_reserved_capital_delta_dollars != 0.0:
                raise OpenPositionAccountStateError("option open event must release option reservation only")
            if not _same(self.stock_gross_entry_exposure_delta_dollars, 0.0):
                raise OpenPositionAccountStateError("option open event cannot add stock exposure")
            if self.option_abs_delta_entry_reference_delta_dollars <= 0.0 or self.option_premium_at_risk_delta_dollars <= 0.0:
                raise OpenPositionAccountStateError("option open event requires positive option reference/risk")
        else:
            raise OpenPositionAccountStateError("unsupported ledger instrument kind")
        if not self.reason_codes:
            raise OpenPositionAccountStateError("ledger event requires reason codes")

    @property
    def event_fingerprint(self) -> str:
        return open_position_ledger_event_fingerprint(self)


@dataclass(frozen=True)
class OpenPositionLedgerV1:
    contract_version: str
    contract_fingerprint: str
    source_account_state_fingerprint: str
    initial_state_fingerprint: str
    events: tuple[OpenPositionLedgerEventV1, ...]

    def __post_init__(self) -> None:
        if self.contract_version != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION:
            raise OpenPositionAccountStateError("open-position ledger contract version mismatch")
        if self.contract_fingerprint != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise OpenPositionAccountStateError("open-position ledger contract fingerprint mismatch")
        _require_fingerprint(self.source_account_state_fingerprint, label="ledger source account-state fingerprint")
        _require_fingerprint(self.initial_state_fingerprint, label="ledger initial-state fingerprint")
        previous_time: datetime | None = None
        previous_after = self.initial_state_fingerprint
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence:
                raise OpenPositionAccountStateError("ledger sequence must be contiguous")
            if previous_time is not None and event.occurred_utc < previous_time:
                raise OpenPositionAccountStateError("ledger events must be chronological")
            if event.before_state_fingerprint != previous_after:
                raise OpenPositionAccountStateError("ledger before-state chain is broken")
            previous_time = event.occurred_utc
            previous_after = event.after_state_fingerprint

    @property
    def ledger_fingerprint(self) -> str:
        return open_position_ledger_fingerprint(self)


@dataclass(frozen=True)
class OpenPositionAccountV1:
    state: OpenPositionAccountStateV1
    ledger: OpenPositionLedgerV1

    def __post_init__(self) -> None:
        if self.state.source_account_state_fingerprint != self.ledger.source_account_state_fingerprint:
            raise OpenPositionAccountStateError("state and ledger source account fingerprints must match")
        expected = self.ledger.events[-1].after_state_fingerprint if self.ledger.events else self.ledger.initial_state_fingerprint
        if self.state.state_fingerprint != expected:
            raise OpenPositionAccountStateError("state must match latest ledger state fingerprint")


@dataclass(frozen=True)
class OpenPositionTransitionV1:
    account: OpenPositionAccountV1
    event: OpenPositionLedgerEventV1 | None
    position: SimulatedOpenPositionV1
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class OpenPositionBatchResultV1:
    account: OpenPositionAccountV1
    ordered_fill_fingerprints: tuple[str, ...]
    transitions: tuple[OpenPositionTransitionV1, ...]


def simulated_open_position_fingerprint(position: SimulatedOpenPositionV1) -> str:
    return _fingerprint_payload(position)


def open_position_account_state_fingerprint(state: OpenPositionAccountStateV1) -> str:
    return _fingerprint_payload(state)


def open_position_ledger_event_fingerprint(event: OpenPositionLedgerEventV1) -> str:
    return _fingerprint_payload(event)


def open_position_ledger_fingerprint(ledger: OpenPositionLedgerV1) -> str:
    return _fingerprint_payload(ledger)


def _build_state(
    *,
    previous: OpenPositionAccountStateV1,
    as_of_utc: datetime,
    cash: float,
    cumulative_entry_fees_dollars: float,
    remaining_stock_reservations: Sequence[SimulatedStockReservationV2],
    remaining_option_reservations: Sequence[SimulatedOptionReservationV2],
    open_positions: Sequence[SimulatedOpenPositionV1],
) -> OpenPositionAccountStateV1:
    stock_reservations = tuple(sorted(remaining_stock_reservations, key=lambda item: item.decision_record_fingerprint))
    option_reservations = tuple(sorted(remaining_option_reservations, key=lambda item: item.decision_record_fingerprint))
    positions = tuple(sorted(open_positions, key=lambda item: item.decision_record_fingerprint))
    stock_reserved = sum(item.reserved_capital for item in stock_reservations)
    option_reserved = sum(item.reserved_capital for item in option_reservations)
    stock_gross = sum(item.gross_notional for item in stock_reservations)
    option_signed = sum(item.signed_delta_equivalent_notional for item in option_reservations)
    option_abs = sum(item.abs_delta_equivalent_notional for item in option_reservations)
    open_book = sum(item.entry_book_value_dollars for item in positions)
    open_stock = sum(item.stock_gross_entry_exposure_dollars for item in positions)
    open_option_book = sum(item.entry_book_value_dollars for item in positions if item.instrument_kind == InstrumentKind.OPTION)
    open_option_signed = sum(item.option_signed_delta_equivalent_entry_reference_dollars for item in positions)
    open_option_abs = sum(item.option_abs_delta_equivalent_entry_reference_dollars for item in positions)
    open_option_premium = sum(item.option_premium_at_risk_dollars for item in positions)
    return OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=previous.source_account_contract_fingerprint,
        source_account_state_fingerprint=previous.source_account_state_fingerprint,
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        source_stock_gross_notional=previous.source_stock_gross_notional,
        source_option_signed_delta_equivalent_notional=previous.source_option_signed_delta_equivalent_notional,
        source_option_abs_delta_equivalent_notional=previous.source_option_abs_delta_equivalent_notional,
        cash=_zero(cash),
        entry_book_equity=_zero(previous.initial_equity - cumulative_entry_fees_dollars),
        cumulative_entry_fees_dollars=_zero(cumulative_entry_fees_dollars),
        remaining_stock_reserved_capital=_zero(stock_reserved),
        remaining_option_reserved_capital=_zero(option_reserved),
        remaining_stock_gross_notional=_zero(stock_gross),
        remaining_option_signed_delta_equivalent_notional=_zero(option_signed),
        remaining_option_abs_delta_equivalent_notional=_zero(option_abs),
        open_entry_book_value_dollars=_zero(open_book),
        open_stock_gross_entry_exposure_dollars=_zero(open_stock),
        open_option_entry_book_value_dollars=_zero(open_option_book),
        open_option_signed_delta_equivalent_entry_reference_dollars=_zero(open_option_signed),
        open_option_abs_delta_equivalent_entry_reference_dollars=_zero(open_option_abs),
        open_option_premium_at_risk_dollars=_zero(open_option_premium),
        remaining_stock_reservations=stock_reservations,
        remaining_option_reservations=option_reservations,
        open_positions=positions,
    )


def initialize_open_position_account_v1(*, source_account: SimulationAccountV2) -> OpenPositionAccountV1:
    if source_account.state.contract_fingerprint != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT:
        raise OpenPositionAccountStateError("source account must use accepted simulation account-state v2")
    state = OpenPositionAccountStateV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=source_account.state.contract_fingerprint,
        source_account_state_fingerprint=source_account.state.state_fingerprint,
        as_of_utc=source_account.state.as_of_utc,
        initial_equity=source_account.state.initial_equity,
        source_stock_gross_notional=source_account.state.stock_gross_notional,
        source_option_signed_delta_equivalent_notional=source_account.state.option_signed_delta_equivalent_notional,
        source_option_abs_delta_equivalent_notional=source_account.state.option_abs_delta_equivalent_notional,
        cash=source_account.state.cash,
        entry_book_equity=source_account.state.initial_equity,
        cumulative_entry_fees_dollars=0.0,
        remaining_stock_reserved_capital=source_account.state.stock_reserved_capital,
        remaining_option_reserved_capital=source_account.state.option_reserved_capital,
        remaining_stock_gross_notional=source_account.state.stock_gross_notional,
        remaining_option_signed_delta_equivalent_notional=source_account.state.option_signed_delta_equivalent_notional,
        remaining_option_abs_delta_equivalent_notional=source_account.state.option_abs_delta_equivalent_notional,
        open_entry_book_value_dollars=0.0,
        open_stock_gross_entry_exposure_dollars=0.0,
        open_option_entry_book_value_dollars=0.0,
        open_option_signed_delta_equivalent_entry_reference_dollars=0.0,
        open_option_abs_delta_equivalent_entry_reference_dollars=0.0,
        open_option_premium_at_risk_dollars=0.0,
        remaining_stock_reservations=source_account.state.stock_reservations,
        remaining_option_reservations=source_account.state.option_reservations,
        open_positions=(),
    )
    ledger = OpenPositionLedgerV1(
        contract_version=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_account_state_fingerprint=source_account.state.state_fingerprint,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return OpenPositionAccountV1(state=state, ledger=ledger)


def _validate_evidence_lineage(
    *,
    account: OpenPositionAccountV1,
    fill: SimulatedEntryFillEvidence,
    funding: SimulationFundingCollateralTerms,
) -> None:
    if fill.contract_fingerprint != SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT:
        raise OpenPositionAccountStateError("simulated fill contract fingerprint mismatch")
    if funding.contract_fingerprint != SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT:
        raise OpenPositionAccountStateError("funding/collateral contract fingerprint mismatch")
    if fill.fill_fingerprint != simulated_entry_fill_fingerprint(fill):
        raise OpenPositionAccountStateError("simulated fill fingerprint mismatch")
    if funding.terms_fingerprint != simulation_funding_terms_fingerprint(funding):
        raise OpenPositionAccountStateError("funding terms fingerprint mismatch")
    source_fp = account.state.source_account_state_fingerprint
    if fill.account_state_fingerprint != source_fp or funding.account_state_fingerprint != source_fp:
        raise OpenPositionAccountStateError("fill and funding evidence must bind the immutable source reservation account state")
    pairs = (
        (funding.fill_fingerprint, fill.fill_fingerprint, "funding fill lineage"),
        (funding.active_reservation_fingerprint, fill.active_reservation_fingerprint, "funding reservation lineage"),
        (funding.decision_record_fingerprint, fill.decision_record_fingerprint, "funding decision lineage"),
        (funding.candidate_fingerprint, fill.candidate_fingerprint, "funding candidate lineage"),
    )
    for left, right, label in pairs:
        if left != right:
            raise OpenPositionAccountStateError(f"{label} mismatch")
    if funding.instrument_kind != fill.instrument_kind or funding.direction != fill.direction:
        raise OpenPositionAccountStateError("funding instrument/direction lineage mismatch")
    if not funding.fully_funded:
        raise OpenPositionAccountStateError("funding terms must be fully funded")
    if not _same(funding.required_cash_dollars, fill.gross_fill_notional_dollars + fill.entry_fees_dollars):
        raise OpenPositionAccountStateError("funding required cash must equal fill book value plus entry fees")
    if not _same(funding.reserved_capital_dollars, fill.reserved_capital_dollars):
        raise OpenPositionAccountStateError("funding reserved capital mismatch")


def _find_reservation(
    account: OpenPositionAccountV1,
    fill: SimulatedEntryFillEvidence,
) -> SimulatedStockReservationV2 | SimulatedOptionReservationV2:
    source = (
        account.state.remaining_stock_reservations
        if fill.instrument_kind == InstrumentKind.STOCK
        else account.state.remaining_option_reservations
    )
    matches = tuple(item for item in source if item.decision_record_fingerprint == fill.decision_record_fingerprint)
    if len(matches) != 1:
        raise OpenPositionAccountStateError("exact remaining reservation is required")
    reservation = matches[0]
    if simulated_reservation_fingerprint(reservation) != fill.active_reservation_fingerprint:
        raise OpenPositionAccountStateError("remaining reservation fingerprint lineage mismatch")
    return reservation


def _build_position(
    *,
    fill: SimulatedEntryFillEvidence,
    funding: SimulationFundingCollateralTerms,
    reservation: SimulatedStockReservationV2 | SimulatedOptionReservationV2,
) -> SimulatedOpenPositionV1:
    if fill.instrument_kind == InstrumentKind.STOCK:
        signed_delta = 0.0
        abs_delta = 0.0
        stock_exposure = fill.gross_fill_notional_dollars
        option_premium = 0.0
    else:
        if not isinstance(reservation, SimulatedOptionReservationV2):
            raise OpenPositionAccountStateError("option fill requires option reservation")
        signed_delta = reservation.signed_delta_equivalent_notional
        abs_delta = reservation.abs_delta_equivalent_notional
        stock_exposure = 0.0
        option_premium = fill.gross_fill_notional_dollars
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=fill.account_state_fingerprint,
        decision_record_fingerprint=fill.decision_record_fingerprint,
        candidate_fingerprint=fill.candidate_fingerprint,
        fill_fingerprint=fill.fill_fingerprint,
        funding_terms_fingerprint=funding.terms_fingerprint,
        reservation_fingerprint=fill.active_reservation_fingerprint,
        option_reservation_terms_fingerprint=fill.option_reservation_terms_fingerprint,
        option_economics_result_fingerprint=fill.option_economics_result_fingerprint,
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
        supplemental_cash_consumed_dollars=funding.supplemental_unreserved_cash_required_dollars,
        unspent_reserve_returned_dollars=funding.unspent_reserved_capital_dollars,
        stock_gross_entry_exposure_dollars=stock_exposure,
        option_premium_at_risk_dollars=option_premium,
        option_signed_delta_equivalent_entry_reference_dollars=signed_delta,
        option_abs_delta_equivalent_entry_reference_dollars=abs_delta,
        reason_codes=(
            "EXACT_RESERVATION_FILL_FUNDING_LINEAGE",
            "ENTRY_BOOK_VALUE_ONLY_NO_MARK_TO_MARKET",
            "RESERVATION_RELEASED_ONCE",
        ),
    )


def apply_open_position_fill_v1(
    account: OpenPositionAccountV1,
    *,
    fill: SimulatedEntryFillEvidence,
    funding: SimulationFundingCollateralTerms,
) -> OpenPositionTransitionV1:
    _validate_evidence_lineage(account=account, fill=fill, funding=funding)
    existing = tuple(
        position
        for position in account.state.open_positions
        if position.decision_record_fingerprint == fill.decision_record_fingerprint
    )
    if existing:
        if len(existing) != 1:
            raise OpenPositionAccountStateError("duplicate open-position decision lineage")
        position = existing[0]
        if position.fill_fingerprint == fill.fill_fingerprint and position.funding_terms_fingerprint == funding.terms_fingerprint:
            return OpenPositionTransitionV1(
                account=account,
                event=None,
                position=position,
                idempotent_reuse=True,
                reason_codes=("DUPLICATE_FILL_IDEMPOTENT_REUSE",),
            )
        raise OpenPositionAccountStateError("conflicting fill for an already-open decision")
    if fill.filled_utc < account.state.as_of_utc:
        raise OpenPositionAccountStateError("fill timestamp cannot precede current account state")
    reservation = _find_reservation(account, fill)
    if fill.instrument_kind == InstrumentKind.STOCK:
        if not isinstance(reservation, SimulatedStockReservationV2):
            raise OpenPositionAccountStateError("stock fill requires stock reservation")
        if fill.direction != DiscoveryDirection.BULLISH:
            raise OpenPositionAccountStateError("v1 cannot open stock shorts")
    elif fill.instrument_kind == InstrumentKind.OPTION:
        if not isinstance(reservation, SimulatedOptionReservationV2):
            raise OpenPositionAccountStateError("option fill requires option reservation")
    else:
        raise OpenPositionAccountStateError("unsupported fill instrument kind")

    new_cash = account.state.cash + reservation.reserved_capital - funding.required_cash_dollars
    if new_cash < -_TOLERANCE:
        raise OpenPositionAccountStateError("insufficient current cash after competing fill transitions")
    position = _build_position(fill=fill, funding=funding, reservation=reservation)
    if fill.instrument_kind == InstrumentKind.STOCK:
        stocks = tuple(item for item in account.state.remaining_stock_reservations if item.decision_record_fingerprint != fill.decision_record_fingerprint)
        options = account.state.remaining_option_reservations
    else:
        stocks = account.state.remaining_stock_reservations
        options = tuple(item for item in account.state.remaining_option_reservations if item.decision_record_fingerprint != fill.decision_record_fingerprint)
    next_state = _build_state(
        previous=account.state,
        as_of_utc=fill.filled_utc,
        cash=new_cash,
        cumulative_entry_fees_dollars=account.state.cumulative_entry_fees_dollars + fill.entry_fees_dollars,
        remaining_stock_reservations=stocks,
        remaining_option_reservations=options,
        open_positions=account.state.open_positions + (position,),
    )
    stock_reserve_delta = -reservation.reserved_capital if fill.instrument_kind == InstrumentKind.STOCK else 0.0
    option_reserve_delta = -reservation.reserved_capital if fill.instrument_kind == InstrumentKind.OPTION else 0.0
    stock_exposure_delta = position.stock_gross_entry_exposure_dollars
    option_signed_delta = position.option_signed_delta_equivalent_entry_reference_dollars
    option_abs_delta = position.option_abs_delta_equivalent_entry_reference_dollars
    option_premium_delta = position.option_premium_at_risk_dollars
    event = OpenPositionLedgerEventV1(
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
        open_entry_book_value_delta_dollars=position.entry_book_value_dollars,
        entry_fee_delta_dollars=position.entry_fees_dollars,
        stock_gross_entry_exposure_delta_dollars=stock_exposure_delta,
        option_signed_delta_entry_reference_delta_dollars=option_signed_delta,
        option_abs_delta_entry_reference_delta_dollars=option_abs_delta,
        option_premium_at_risk_delta_dollars=option_premium_delta,
        reason_codes=("OPEN_POSITION_FROM_ACCEPTED_RESERVATION_FILL_FUNDING",),
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
    )
    next_ledger = OpenPositionLedgerV1(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        source_account_state_fingerprint=account.ledger.source_account_state_fingerprint,
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = OpenPositionAccountV1(state=next_state, ledger=next_ledger)
    return OpenPositionTransitionV1(
        account=next_account,
        event=event,
        position=position,
        idempotent_reuse=False,
        reason_codes=("POSITION_OPENED_ENTRY_BOOK_ONLY",),
    )


def apply_open_position_batch_v1(
    account: OpenPositionAccountV1,
    entries: Sequence[tuple[SimulatedEntryFillEvidence, SimulationFundingCollateralTerms]],
) -> OpenPositionBatchResultV1:
    ordered = tuple(sorted(entries, key=lambda item: (item[0].filled_utc, item[0].fill_fingerprint)))
    current = account
    transitions: list[OpenPositionTransitionV1] = []
    for fill, funding in ordered:
        transition = apply_open_position_fill_v1(current, fill=fill, funding=funding)
        transitions.append(transition)
        current = transition.account
    return OpenPositionBatchResultV1(
        account=current,
        ordered_fill_fingerprints=tuple(fill.fill_fingerprint for fill, _ in ordered),
        transitions=tuple(transitions),
    )


def replay_open_position_account_v1(
    *,
    source_account: SimulationAccountV2,
    entries: Sequence[tuple[SimulatedEntryFillEvidence, SimulationFundingCollateralTerms]],
) -> OpenPositionBatchResultV1:
    return apply_open_position_batch_v1(
        initialize_open_position_account_v1(source_account=source_account),
        entries,
    )


def verify_open_position_account_replay_v1(
    *,
    account: OpenPositionAccountV1,
    source_account: SimulationAccountV2,
    entries: Sequence[tuple[SimulatedEntryFillEvidence, SimulationFundingCollateralTerms]],
) -> None:
    replay = replay_open_position_account_v1(source_account=source_account, entries=entries)
    if replay.account.state.state_fingerprint != account.state.state_fingerprint:
        raise OpenPositionAccountStateError("replayed open-position state fingerprint mismatch")
    if replay.account.ledger.ledger_fingerprint != account.ledger.ledger_fingerprint:
        raise OpenPositionAccountStateError("replayed open-position ledger fingerprint mismatch")
