from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from packages.execution.trade_expression import InstrumentKind
from packages.simulation.marked_account_state_contract import (
    MARKED_ACCOUNT_STATE_CONTRACT,
    MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.market_mark_evidence import (
    MarketMarkFreshness,
    SimulatedMarketMarkEvidence,
    simulated_market_mark_fingerprint,
)
from packages.simulation.market_mark_evidence_contract import (
    MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.simulation.open_position_state import (
    OpenPositionAccountStateV1,
    SimulatedOpenPositionV1,
    open_position_account_state_fingerprint,
    simulated_open_position_fingerprint,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)


MARKED_ACCOUNT_STATE_CONTRACT_VERSION = str(MARKED_ACCOUNT_STATE_CONTRACT["contract_id"])
_TOLERANCE = 1e-9


class MarkedAccountStateError(ValueError):
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
        raise MarkedAccountStateError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise MarkedAccountStateError(f"{label} must be a SHA-256 fingerprint") from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarkedAccountStateError(f"{label} must be timezone-aware")


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise MarkedAccountStateError(f"{label} must be finite and nonnegative")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class MarkedOpenPositionV1:
    position_fingerprint: str
    mark_fingerprint: str
    decision_record_fingerprint: str
    instrument_kind: InstrumentKind
    instrument_id: str
    ticker: str
    option_contract_ticker: str | None
    option_contract_type: str | None
    valuation_utc: datetime
    quantity: float
    contract_multiplier: float
    entry_book_value_dollars: float
    entry_fees_dollars: float
    selected_mark_price_per_unit: float
    marked_value_dollars: float
    unrealized_pnl_dollars: float
    unrealized_return: float
    stock_gross_entry_exposure_dollars: float
    option_premium_at_risk_dollars: float
    option_signed_delta_equivalent_entry_reference_dollars: float
    option_abs_delta_equivalent_entry_reference_dollars: float
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for label, value in (
            ("position", self.position_fingerprint),
            ("mark", self.mark_fingerprint),
            ("decision record", self.decision_record_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.valuation_utc, label="marked-position valuation timestamp")
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise MarkedAccountStateError("marked-position identity cannot be blank")
        if not math.isfinite(self.quantity) or self.quantity <= 0.0:
            raise MarkedAccountStateError("marked-position quantity must be finite and positive")
        if not math.isfinite(self.contract_multiplier) or self.contract_multiplier <= 0.0:
            raise MarkedAccountStateError("marked-position multiplier must be finite and positive")
        if not math.isfinite(self.entry_book_value_dollars) or self.entry_book_value_dollars <= 0.0:
            raise MarkedAccountStateError("marked-position entry book value must be finite and positive")
        for label, value in (
            ("entry fees", self.entry_fees_dollars),
            ("selected mark", self.selected_mark_price_per_unit),
            ("marked value", self.marked_value_dollars),
            ("stock gross entry exposure", self.stock_gross_entry_exposure_dollars),
            ("option premium at risk", self.option_premium_at_risk_dollars),
            ("option absolute delta entry reference", self.option_abs_delta_equivalent_entry_reference_dollars),
        ):
            _require_nonnegative(value, label=label)
        for label, value in (
            ("unrealized P&L", self.unrealized_pnl_dollars),
            ("unrealized return", self.unrealized_return),
            ("option signed delta entry reference", self.option_signed_delta_equivalent_entry_reference_dollars),
        ):
            if not math.isfinite(value):
                raise MarkedAccountStateError(f"{label} must be finite")
        expected_value = self.quantity * self.selected_mark_price_per_unit * self.contract_multiplier
        if not _same(self.marked_value_dollars, expected_value):
            raise MarkedAccountStateError("marked value must match quantity, selected mark, and multiplier")
        expected_pnl = self.marked_value_dollars - self.entry_book_value_dollars
        if not _same(self.unrealized_pnl_dollars, expected_pnl):
            raise MarkedAccountStateError("unrealized P&L must equal marked value less entry book value")
        if not _same(
            self.unrealized_return,
            self.unrealized_pnl_dollars / self.entry_book_value_dollars,
        ):
            raise MarkedAccountStateError("unrealized return must use entry book value denominator")
        if not self.reason_codes:
            raise MarkedAccountStateError("marked position requires reason codes")
        if self.instrument_kind == InstrumentKind.STOCK:
            if self.option_contract_ticker is not None or self.option_contract_type is not None:
                raise MarkedAccountStateError("marked stock cannot carry option identity")
            if not _same(self.stock_gross_entry_exposure_dollars, self.entry_book_value_dollars):
                raise MarkedAccountStateError("marked stock must preserve stock entry exposure")
            if any(
                not _same(value, 0.0)
                for value in (
                    self.option_premium_at_risk_dollars,
                    self.option_signed_delta_equivalent_entry_reference_dollars,
                    self.option_abs_delta_equivalent_entry_reference_dollars,
                )
            ):
                raise MarkedAccountStateError("marked stock cannot carry option risk/reference exposure")
        elif self.instrument_kind == InstrumentKind.OPTION:
            if not self.option_contract_ticker or self.option_contract_type not in {"call", "put"}:
                raise MarkedAccountStateError("marked option requires call/put identity")
            if not _same(self.stock_gross_entry_exposure_dollars, 0.0):
                raise MarkedAccountStateError("marked option cannot carry stock gross exposure")
            if not _same(self.option_premium_at_risk_dollars, self.entry_book_value_dollars):
                raise MarkedAccountStateError("marked option must preserve entry premium at risk")
            if not _same(
                self.option_abs_delta_equivalent_entry_reference_dollars,
                abs(self.option_signed_delta_equivalent_entry_reference_dollars),
            ):
                raise MarkedAccountStateError("marked option entry delta reference mismatch")
        else:
            raise MarkedAccountStateError("unsupported marked-position instrument kind")

    @property
    def marked_position_fingerprint(self) -> str:
        return marked_open_position_fingerprint(self)


@dataclass(frozen=True)
class MarkedAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    source_open_position_contract_fingerprint: str
    source_open_position_state_fingerprint: str
    valuation_utc: datetime
    initial_equity: float
    entry_book_equity: float
    cumulative_entry_fees_dollars: float
    cash: float
    remaining_stock_reserved_capital: float
    remaining_option_reserved_capital: float
    open_entry_book_value_dollars: float
    marked_open_position_value_dollars: float
    aggregate_unrealized_pnl_dollars: float
    marked_equity: float
    complete_mark_coverage: bool
    marked_positions: tuple[MarkedOpenPositionV1, ...]
    simulation_mark_to_market_computation: bool = True
    simulation_unrealized_pnl_computation: bool = True
    account_mutation_authority: bool = False
    realized_pnl_authority: bool = False
    exit_closeout_authority: bool = False
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
        if self.contract_version != MARKED_ACCOUNT_STATE_CONTRACT_VERSION:
            raise MarkedAccountStateError("marked-account contract version mismatch")
        if self.contract_fingerprint != MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise MarkedAccountStateError("marked-account contract fingerprint mismatch")
        if self.source_open_position_contract_fingerprint != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise MarkedAccountStateError("source open-position contract fingerprint mismatch")
        _require_fingerprint(
            self.source_open_position_state_fingerprint,
            label="source open-position state fingerprint",
        )
        _require_aware(self.valuation_utc, label="marked-account valuation timestamp")
        for label, value in (
            ("initial equity", self.initial_equity),
            ("entry book equity", self.entry_book_equity),
            ("cumulative entry fees", self.cumulative_entry_fees_dollars),
            ("cash", self.cash),
            ("remaining stock reserved capital", self.remaining_stock_reserved_capital),
            ("remaining option reserved capital", self.remaining_option_reserved_capital),
            ("open entry book value", self.open_entry_book_value_dollars),
            ("marked open-position value", self.marked_open_position_value_dollars),
            ("marked equity", self.marked_equity),
        ):
            _require_nonnegative(value, label=label)
        if not math.isfinite(self.aggregate_unrealized_pnl_dollars):
            raise MarkedAccountStateError("aggregate unrealized P&L must be finite")
        if not self.complete_mark_coverage:
            raise MarkedAccountStateError("accepted marked-account state requires complete fresh mark coverage")
        if not self.simulation_mark_to_market_computation or not self.simulation_unrealized_pnl_computation:
            raise MarkedAccountStateError("marked-account state must explicitly identify simulation valuation computations")
        ordered = tuple(sorted(self.marked_positions, key=lambda item: item.decision_record_fingerprint))
        if self.marked_positions != ordered:
            raise MarkedAccountStateError("marked positions must be ordered by decision fingerprint")
        decision_ids = [item.decision_record_fingerprint for item in self.marked_positions]
        if len(decision_ids) != len(set(decision_ids)):
            raise MarkedAccountStateError("marked positions cannot duplicate a decision fingerprint")
        if any(item.valuation_utc != self.valuation_utc for item in self.marked_positions):
            raise MarkedAccountStateError("all marked positions must share the account valuation timestamp")
        if not _same(
            self.marked_open_position_value_dollars,
            sum(item.marked_value_dollars for item in self.marked_positions),
        ):
            raise MarkedAccountStateError("marked open-position value must equal constituent sum")
        if not _same(
            self.aggregate_unrealized_pnl_dollars,
            sum(item.unrealized_pnl_dollars for item in self.marked_positions),
        ):
            raise MarkedAccountStateError("aggregate unrealized P&L must equal constituent sum")
        if not _same(
            self.entry_book_equity,
            self.initial_equity - self.cumulative_entry_fees_dollars,
        ):
            raise MarkedAccountStateError("entry-book equity must preserve already-expensed entry fees")
        if not _same(
            self.marked_equity,
            self.entry_book_equity + self.aggregate_unrealized_pnl_dollars,
        ):
            raise MarkedAccountStateError("marked equity must equal entry-book equity plus unrealized P&L")
        if not _same(
            self.marked_equity,
            self.cash
            + self.remaining_stock_reserved_capital
            + self.remaining_option_reserved_capital
            + self.marked_open_position_value_dollars,
        ):
            raise MarkedAccountStateError("marked equity must reconcile cash, reservations, and marked positions")
        forbidden = (
            self.account_mutation_authority,
            self.realized_pnl_authority,
            self.exit_closeout_authority,
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
            raise MarkedAccountStateError(
                "marked-account state cannot grant mutation, realized-P&L, exit, provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return marked_account_state_fingerprint(self)


def marked_open_position_fingerprint(position: MarkedOpenPositionV1) -> str:
    return _fingerprint_payload(position)


def marked_account_state_fingerprint(state: MarkedAccountStateV1) -> str:
    return _fingerprint_payload(state)


def _validate_mark_for_position(
    *,
    position: SimulatedOpenPositionV1,
    mark: SimulatedMarketMarkEvidence,
    valuation_utc: datetime,
) -> None:
    if mark.contract_fingerprint != MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT:
        raise MarkedAccountStateError("market-mark contract fingerprint mismatch")
    if mark.mark_fingerprint != simulated_market_mark_fingerprint(mark):
        raise MarkedAccountStateError("market-mark fingerprint mismatch")
    if mark.position_fingerprint != simulated_open_position_fingerprint(position):
        raise MarkedAccountStateError("mark does not bind the exact active open position")
    if mark.decision_record_fingerprint != position.decision_record_fingerprint:
        raise MarkedAccountStateError("mark decision lineage mismatch")
    if mark.source_account_state_fingerprint != position.source_account_state_fingerprint:
        raise MarkedAccountStateError("mark source account-state lineage mismatch")
    if mark.fill_fingerprint != position.fill_fingerprint:
        raise MarkedAccountStateError("mark fill lineage mismatch")
    if mark.funding_terms_fingerprint != position.funding_terms_fingerprint:
        raise MarkedAccountStateError("mark funding lineage mismatch")
    if mark.instrument_kind != position.instrument_kind:
        raise MarkedAccountStateError("mark instrument kind mismatch")
    if mark.instrument_id != position.instrument_id or mark.ticker != position.ticker:
        raise MarkedAccountStateError("mark underlying identity mismatch")
    if mark.option_contract_ticker != position.option_contract_ticker or mark.option_contract_type != position.option_contract_type:
        raise MarkedAccountStateError("mark option identity mismatch")
    if mark.valuation_utc != valuation_utc:
        raise MarkedAccountStateError("all marks must share the requested valuation timestamp")
    if mark.market_timestamp_utc < position.opened_utc:
        raise MarkedAccountStateError("market mark cannot predate the position open")
    if mark.freshness != MarketMarkFreshness.FRESH or not mark.valuation_eligible:
        raise MarkedAccountStateError("stale or ineligible mark cannot create current valuation")


def _mark_position(
    *,
    position: SimulatedOpenPositionV1,
    mark: SimulatedMarketMarkEvidence,
    valuation_utc: datetime,
) -> MarkedOpenPositionV1:
    _validate_mark_for_position(position=position, mark=mark, valuation_utc=valuation_utc)
    marked_value = position.quantity * mark.selected_mark_price_per_unit * position.contract_multiplier
    unrealized_pnl = marked_value - position.entry_book_value_dollars
    return MarkedOpenPositionV1(
        position_fingerprint=position.position_fingerprint,
        mark_fingerprint=mark.mark_fingerprint,
        decision_record_fingerprint=position.decision_record_fingerprint,
        instrument_kind=position.instrument_kind,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        option_contract_ticker=position.option_contract_ticker,
        option_contract_type=position.option_contract_type,
        valuation_utc=valuation_utc,
        quantity=position.quantity,
        contract_multiplier=position.contract_multiplier,
        entry_book_value_dollars=position.entry_book_value_dollars,
        entry_fees_dollars=position.entry_fees_dollars,
        selected_mark_price_per_unit=mark.selected_mark_price_per_unit,
        marked_value_dollars=marked_value,
        unrealized_pnl_dollars=unrealized_pnl,
        unrealized_return=unrealized_pnl / position.entry_book_value_dollars,
        stock_gross_entry_exposure_dollars=position.stock_gross_entry_exposure_dollars,
        option_premium_at_risk_dollars=position.option_premium_at_risk_dollars,
        option_signed_delta_equivalent_entry_reference_dollars=(
            position.option_signed_delta_equivalent_entry_reference_dollars
        ),
        option_abs_delta_equivalent_entry_reference_dollars=(
            position.option_abs_delta_equivalent_entry_reference_dollars
        ),
        reason_codes=(
            "EXACT_OPEN_POSITION_AND_FRESH_MARK_BOUND",
            "MARKED_VALUE_USES_FROZEN_SELECTED_MARK",
            "UNREALIZED_PNL_RELATIVE_TO_ENTRY_BOOK_VALUE",
            "ENTRY_FEES_ALREADY_EXPENSED_NOT_DOUBLE_COUNTED",
            "OPTION_ENTRY_DELTA_REMAINS_REFERENCE_ONLY",
        ),
    )


def build_marked_account_state(
    *,
    source_state: OpenPositionAccountStateV1,
    marks: Sequence[SimulatedMarketMarkEvidence],
    valuation_utc: datetime,
) -> MarkedAccountStateV1:
    if source_state.contract_fingerprint != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
        raise MarkedAccountStateError("open-position state contract fingerprint mismatch")
    if source_state.state_fingerprint != open_position_account_state_fingerprint(source_state):
        raise MarkedAccountStateError("open-position state fingerprint mismatch")
    _require_aware(valuation_utc, label="requested valuation timestamp")
    if valuation_utc < source_state.as_of_utc:
        raise MarkedAccountStateError("valuation timestamp cannot predate open-position account state")

    positions = tuple(source_state.open_positions)
    mark_by_decision: dict[str, SimulatedMarketMarkEvidence] = {}
    for mark in marks:
        key = mark.decision_record_fingerprint
        if key in mark_by_decision:
            raise MarkedAccountStateError("one active position cannot receive multiple marks in one valuation snapshot")
        mark_by_decision[key] = mark

    expected_ids = {item.decision_record_fingerprint for item in positions}
    provided_ids = set(mark_by_decision)
    if provided_ids != expected_ids:
        missing = sorted(expected_ids - provided_ids)
        extra = sorted(provided_ids - expected_ids)
        raise MarkedAccountStateError(
            f"complete active-position mark coverage required; missing={missing}, extra={extra}"
        )

    marked_positions = tuple(
        sorted(
            (
                _mark_position(
                    position=position,
                    mark=mark_by_decision[position.decision_record_fingerprint],
                    valuation_utc=valuation_utc,
                )
                for position in positions
            ),
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    marked_value = sum(item.marked_value_dollars for item in marked_positions)
    unrealized_pnl = sum(item.unrealized_pnl_dollars for item in marked_positions)
    marked_equity = source_state.entry_book_equity + unrealized_pnl

    return MarkedAccountStateV1(
        contract_version=MARKED_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_open_position_contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_open_position_state_fingerprint=source_state.state_fingerprint,
        valuation_utc=valuation_utc,
        initial_equity=source_state.initial_equity,
        entry_book_equity=source_state.entry_book_equity,
        cumulative_entry_fees_dollars=source_state.cumulative_entry_fees_dollars,
        cash=source_state.cash,
        remaining_stock_reserved_capital=source_state.remaining_stock_reserved_capital,
        remaining_option_reserved_capital=source_state.remaining_option_reserved_capital,
        open_entry_book_value_dollars=source_state.open_entry_book_value_dollars,
        marked_open_position_value_dollars=marked_value,
        aggregate_unrealized_pnl_dollars=unrealized_pnl,
        marked_equity=marked_equity,
        complete_mark_coverage=True,
        marked_positions=marked_positions,
    )
