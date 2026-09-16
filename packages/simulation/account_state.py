from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Sequence

from packages.execution.trade_expression import InstrumentKind, SelectionKind
from packages.simulation.account_state_contract import (
    SIMULATION_ACCOUNT_STATE_CONTRACT,
    SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.decision_record import SimulationDecisionRecord
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
)


SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION = str(
    SIMULATION_ACCOUNT_STATE_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class SimulationAccountStateError(ValueError):
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
        raise SimulationAccountStateError(f"{label} must be timezone-aware")


def _require_nonnegative_finite(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise SimulationAccountStateError(f"{label} must be finite and nonnegative")


def _require_positive_finite(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise SimulationAccountStateError(f"{label} must be finite and positive")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _normalize_zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise SimulationAccountStateError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SimulationAccountStateError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


@dataclass(frozen=True)
class SimulatedStockReservation:
    decision_record_fingerprint: str
    candidate_identifier: str
    instrument_id: str
    ticker: str
    direction: str
    reserved_capital: float
    gross_exposure: float
    reserved_utc: datetime

    def __post_init__(self) -> None:
        _require_fingerprint(
            self.decision_record_fingerprint,
            label="decision-record fingerprint",
        )
        if not self.candidate_identifier.strip():
            raise SimulationAccountStateError("candidate identifier cannot be blank")
        if not self.instrument_id.strip():
            raise SimulationAccountStateError("instrument id cannot be blank")
        if not self.ticker.strip():
            raise SimulationAccountStateError("ticker cannot be blank")
        if not self.direction.strip():
            raise SimulationAccountStateError("direction cannot be blank")
        _require_positive_finite(self.reserved_capital, label="reserved capital")
        _require_positive_finite(self.gross_exposure, label="gross exposure")
        _require_aware(self.reserved_utc, label="reservation timestamp")


@dataclass(frozen=True)
class SimulationAccountState:
    contract_version: str
    contract_fingerprint: str
    as_of_utc: datetime
    initial_equity: float
    equity: float
    cash: float
    reserved_capital: float
    gross_exposure: float
    stock_reservations: tuple[SimulatedStockReservation, ...]
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    fill_simulation_authority: bool = False
    realized_pnl_authority: bool = False
    mark_to_market_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION:
            raise SimulationAccountStateError("simulation account-state contract version mismatch")
        if self.contract_fingerprint != SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise SimulationAccountStateError("simulation account-state contract fingerprint mismatch")
        _require_aware(self.as_of_utc, label="account-state timestamp")
        _require_positive_finite(self.initial_equity, label="initial equity")
        _require_positive_finite(self.equity, label="equity")
        _require_nonnegative_finite(self.cash, label="cash")
        _require_nonnegative_finite(self.reserved_capital, label="reserved capital")
        _require_nonnegative_finite(self.gross_exposure, label="gross exposure")
        if not _same(self.equity, self.initial_equity):
            raise SimulationAccountStateError(
                "reservation-only account state cannot change equity"
            )
        if not _same(self.cash + self.reserved_capital, self.equity):
            raise SimulationAccountStateError(
                "cash plus reserved capital must equal equity"
            )
        ordered = tuple(
            sorted(
                self.stock_reservations,
                key=lambda item: item.decision_record_fingerprint,
            )
        )
        if self.stock_reservations != ordered:
            raise SimulationAccountStateError(
                "stock reservations must be ordered by decision fingerprint"
            )
        fingerprints = [
            item.decision_record_fingerprint for item in self.stock_reservations
        ]
        if len(fingerprints) != len(set(fingerprints)):
            raise SimulationAccountStateError(
                "active stock reservations cannot share a decision fingerprint"
            )
        if any(item.reserved_utc > self.as_of_utc for item in self.stock_reservations):
            raise SimulationAccountStateError(
                "active reservation cannot postdate account state"
            )
        reserved_sum = sum(item.reserved_capital for item in self.stock_reservations)
        gross_sum = sum(item.gross_exposure for item in self.stock_reservations)
        if not _same(self.reserved_capital, reserved_sum):
            raise SimulationAccountStateError(
                "reserved-capital total must equal active reservation capital"
            )
        if not _same(self.gross_exposure, gross_sum):
            raise SimulationAccountStateError(
                "gross exposure must equal active reservation notional"
            )
        forbidden_authority = (
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.fill_simulation_authority,
            self.realized_pnl_authority,
            self.mark_to_market_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden_authority):
            raise SimulationAccountStateError(
                "simulation account state cannot grant data, broker, order, fill, P&L, trading, promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return simulation_account_state_fingerprint(self)


class SimulationAccountEventKind(StrEnum):
    RESERVE_STOCK = "RESERVE_STOCK"
    RELEASE_STOCK = "RELEASE_STOCK"
    ABSTAIN = "ABSTAIN"
    REJECT_UNSUPPORTED_OPTION = "REJECT_UNSUPPORTED_OPTION"
    REJECT_INSUFFICIENT_CAPITAL = "REJECT_INSUFFICIENT_CAPITAL"


@dataclass(frozen=True)
class SimulationAccountLedgerEvent:
    sequence: int
    occurred_utc: datetime
    kind: SimulationAccountEventKind
    decision_record_fingerprint: str | None
    candidate_identifier: str | None
    instrument_id: str | None
    ticker: str | None
    direction: str | None
    capital_delta: float
    gross_exposure_delta: float
    reason_codes: tuple[str, ...]
    before_state_fingerprint: str
    after_state_fingerprint: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise SimulationAccountStateError("ledger event sequence must be positive")
        _require_aware(self.occurred_utc, label="ledger event timestamp")
        if self.decision_record_fingerprint is not None:
            _require_fingerprint(
                self.decision_record_fingerprint,
                label="ledger decision-record fingerprint",
            )
        if not math.isfinite(self.capital_delta):
            raise SimulationAccountStateError("capital delta must be finite")
        if not math.isfinite(self.gross_exposure_delta):
            raise SimulationAccountStateError("gross-exposure delta must be finite")
        if not self.reason_codes:
            raise SimulationAccountStateError("ledger event requires reason codes")
        _require_fingerprint(
            self.before_state_fingerprint,
            label="before-state fingerprint",
        )
        _require_fingerprint(
            self.after_state_fingerprint,
            label="after-state fingerprint",
        )
        if self.kind == SimulationAccountEventKind.RESERVE_STOCK:
            if self.decision_record_fingerprint is None:
                raise SimulationAccountStateError("stock reservation requires decision lineage")
            if not self.candidate_identifier or not self.instrument_id or not self.ticker or not self.direction:
                raise SimulationAccountStateError("stock reservation event requires stock identity fields")
            if self.capital_delta <= 0.0 or self.gross_exposure_delta <= 0.0:
                raise SimulationAccountStateError("stock reservation deltas must be positive")
        elif self.kind == SimulationAccountEventKind.RELEASE_STOCK:
            if self.decision_record_fingerprint is None:
                raise SimulationAccountStateError("stock release requires decision lineage")
            if not self.candidate_identifier or not self.instrument_id or not self.ticker or not self.direction:
                raise SimulationAccountStateError("stock release event requires stock identity fields")
            if self.capital_delta >= 0.0 or self.gross_exposure_delta >= 0.0:
                raise SimulationAccountStateError("stock release deltas must be negative")
        elif not _same(self.capital_delta, 0.0) or not _same(
            self.gross_exposure_delta,
            0.0,
        ):
            raise SimulationAccountStateError(
                "non-reservation ledger events cannot change account amounts"
            )

    @property
    def event_fingerprint(self) -> str:
        return simulation_account_event_fingerprint(self)


@dataclass(frozen=True)
class SimulationAccountLedger:
    contract_version: str
    contract_fingerprint: str
    initial_equity: float
    initial_as_of_utc: datetime
    initial_state_fingerprint: str
    events: tuple[SimulationAccountLedgerEvent, ...]

    def __post_init__(self) -> None:
        if self.contract_version != SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION:
            raise SimulationAccountStateError("simulation ledger contract version mismatch")
        if self.contract_fingerprint != SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise SimulationAccountStateError("simulation ledger contract fingerprint mismatch")
        _require_positive_finite(self.initial_equity, label="ledger initial equity")
        _require_aware(self.initial_as_of_utc, label="ledger initial timestamp")
        _require_fingerprint(
            self.initial_state_fingerprint,
            label="ledger initial-state fingerprint",
        )
        previous_time = self.initial_as_of_utc
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence:
                raise SimulationAccountStateError(
                    "ledger event sequence must be contiguous and one-based"
                )
            if event.occurred_utc < previous_time:
                raise SimulationAccountStateError(
                    "ledger events must be chronological"
                )
            previous_time = event.occurred_utc

    @property
    def ledger_fingerprint(self) -> str:
        return simulation_account_ledger_fingerprint(self)


@dataclass(frozen=True)
class SimulationAccount:
    state: SimulationAccountState
    ledger: SimulationAccountLedger

    def __post_init__(self) -> None:
        if not _same(self.state.initial_equity, self.ledger.initial_equity):
            raise SimulationAccountStateError(
                "account state and ledger initial equity must match"
            )
        expected_fingerprint = (
            self.ledger.events[-1].after_state_fingerprint
            if self.ledger.events
            else self.ledger.initial_state_fingerprint
        )
        if self.state.state_fingerprint != expected_fingerprint:
            raise SimulationAccountStateError(
                "account state must match the latest ledger state fingerprint"
            )
        expected_time = (
            self.ledger.events[-1].occurred_utc
            if self.ledger.events
            else self.ledger.initial_as_of_utc
        )
        if self.state.as_of_utc != expected_time:
            raise SimulationAccountStateError(
                "account state timestamp must match the latest ledger timestamp"
            )


@dataclass(frozen=True)
class SimulationAccountTransition:
    account: SimulationAccount
    event: SimulationAccountLedgerEvent | None
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class SimulationCompetitionResult:
    account: SimulationAccount
    ordered_decision_fingerprints: tuple[str, ...]
    transitions: tuple[SimulationAccountTransition, ...]


def simulation_account_state_fingerprint(state: SimulationAccountState) -> str:
    return _fingerprint_payload(state)


def simulation_account_event_fingerprint(event: SimulationAccountLedgerEvent) -> str:
    return _fingerprint_payload(event)


def simulation_account_ledger_fingerprint(ledger: SimulationAccountLedger) -> str:
    return _fingerprint_payload(ledger)


def initialize_simulation_account(
    *,
    as_of_utc: datetime,
    equity: float,
) -> SimulationAccount:
    _require_aware(as_of_utc, label="initial account timestamp")
    _require_positive_finite(equity, label="initial account equity")
    state = SimulationAccountState(
        contract_version=SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        as_of_utc=as_of_utc,
        initial_equity=float(equity),
        equity=float(equity),
        cash=float(equity),
        reserved_capital=0.0,
        gross_exposure=0.0,
        stock_reservations=(),
    )
    ledger = SimulationAccountLedger(
        contract_version=SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        initial_equity=float(equity),
        initial_as_of_utc=as_of_utc,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return SimulationAccount(state=state, ledger=ledger)


def _build_state(
    *,
    previous: SimulationAccountState,
    as_of_utc: datetime,
    cash: float,
    reserved_capital: float,
    gross_exposure: float,
    stock_reservations: Sequence[SimulatedStockReservation],
) -> SimulationAccountState:
    return SimulationAccountState(
        contract_version=SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        equity=previous.equity,
        cash=_normalize_zero(cash),
        reserved_capital=_normalize_zero(reserved_capital),
        gross_exposure=_normalize_zero(gross_exposure),
        stock_reservations=tuple(
            sorted(
                stock_reservations,
                key=lambda item: item.decision_record_fingerprint,
            )
        ),
    )


def _append_event(
    *,
    account: SimulationAccount,
    next_state: SimulationAccountState,
    kind: SimulationAccountEventKind,
    occurred_utc: datetime,
    decision_record_fingerprint: str | None,
    candidate_identifier: str | None,
    instrument_id: str | None,
    ticker: str | None,
    direction: str | None,
    capital_delta: float,
    gross_exposure_delta: float,
    reason_codes: tuple[str, ...],
) -> SimulationAccountTransition:
    event = SimulationAccountLedgerEvent(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=occurred_utc,
        kind=kind,
        decision_record_fingerprint=decision_record_fingerprint,
        candidate_identifier=candidate_identifier,
        instrument_id=instrument_id,
        ticker=ticker,
        direction=direction,
        capital_delta=capital_delta,
        gross_exposure_delta=gross_exposure_delta,
        reason_codes=reason_codes,
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
    )
    ledger = SimulationAccountLedger(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        initial_equity=account.ledger.initial_equity,
        initial_as_of_utc=account.ledger.initial_as_of_utc,
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = SimulationAccount(state=next_state, ledger=ledger)
    return SimulationAccountTransition(
        account=next_account,
        event=event,
        idempotent_reuse=False,
        reason_codes=reason_codes,
    )


def _decision_already_applied(
    account: SimulationAccount,
    decision_record_fingerprint: str,
) -> bool:
    decision_event_kinds = {
        SimulationAccountEventKind.RESERVE_STOCK,
        SimulationAccountEventKind.ABSTAIN,
        SimulationAccountEventKind.REJECT_UNSUPPORTED_OPTION,
        SimulationAccountEventKind.REJECT_INSUFFICIENT_CAPITAL,
    }
    return any(
        event.decision_record_fingerprint == decision_record_fingerprint
        and event.kind in decision_event_kinds
        for event in account.ledger.events
    )


def apply_simulation_decision(
    account: SimulationAccount,
    record: SimulationDecisionRecord,
) -> SimulationAccountTransition:
    if record.contract_fingerprint != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT:
        raise SimulationAccountStateError("decision record contract fingerprint mismatch")
    record_fingerprint = record.record_fingerprint
    if _decision_already_applied(account, record_fingerprint):
        return SimulationAccountTransition(
            account=account,
            event=None,
            idempotent_reuse=True,
            reason_codes=("DECISION_ALREADY_APPLIED",),
        )
    if record.decision_created_utc < account.state.as_of_utc:
        raise SimulationAccountStateError(
            "decision timestamp cannot precede current account state"
        )

    decision = record.trade_expression_decision
    if decision.selection_kind == SelectionKind.ABSTAIN:
        next_state = _build_state(
            previous=account.state,
            as_of_utc=record.decision_created_utc,
            cash=account.state.cash,
            reserved_capital=account.state.reserved_capital,
            gross_exposure=account.state.gross_exposure,
            stock_reservations=account.state.stock_reservations,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=SimulationAccountEventKind.ABSTAIN,
            occurred_utc=record.decision_created_utc,
            decision_record_fingerprint=record_fingerprint,
            candidate_identifier=None,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            capital_delta=0.0,
            gross_exposure_delta=0.0,
            reason_codes=("DECISION_ABSTAINED",) + decision.reason_codes,
        )

    candidate = decision.chosen_candidate
    if candidate is None:
        raise SimulationAccountStateError(
            "non-abstain decision must carry a chosen candidate"
        )

    if decision.selection_kind == SelectionKind.OPTION:
        next_state = _build_state(
            previous=account.state,
            as_of_utc=record.decision_created_utc,
            cash=account.state.cash,
            reserved_capital=account.state.reserved_capital,
            gross_exposure=account.state.gross_exposure,
            stock_reservations=account.state.stock_reservations,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=SimulationAccountEventKind.REJECT_UNSUPPORTED_OPTION,
            occurred_utc=record.decision_created_utc,
            decision_record_fingerprint=record_fingerprint,
            candidate_identifier=candidate.identifier,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            capital_delta=0.0,
            gross_exposure_delta=0.0,
            reason_codes=("OPTION_ACCOUNT_SEMANTICS_NOT_ACCEPTED",),
        )

    if decision.selection_kind != SelectionKind.STOCK or candidate.kind != InstrumentKind.STOCK:
        raise SimulationAccountStateError("unsupported simulation selection kind")
    if candidate.identifier != record.stock_economics.candidate.identifier:
        raise SimulationAccountStateError("chosen stock candidate lineage mismatch")
    capital_required = float(record.stock_economics.capital_required_dollars)
    gross_notional = float(record.stock_economics.position_notional_dollars)
    if not _same(candidate.capital_required, capital_required):
        raise SimulationAccountStateError("stock capital lineage mismatch")

    if capital_required > account.state.cash and not _same(
        capital_required,
        account.state.cash,
    ):
        next_state = _build_state(
            previous=account.state,
            as_of_utc=record.decision_created_utc,
            cash=account.state.cash,
            reserved_capital=account.state.reserved_capital,
            gross_exposure=account.state.gross_exposure,
            stock_reservations=account.state.stock_reservations,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=SimulationAccountEventKind.REJECT_INSUFFICIENT_CAPITAL,
            occurred_utc=record.decision_created_utc,
            decision_record_fingerprint=record_fingerprint,
            candidate_identifier=candidate.identifier,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            capital_delta=0.0,
            gross_exposure_delta=0.0,
            reason_codes=("INSUFFICIENT_UNRESERVED_CAPITAL",),
        )

    reservation = SimulatedStockReservation(
        decision_record_fingerprint=record_fingerprint,
        candidate_identifier=candidate.identifier,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        reserved_capital=capital_required,
        gross_exposure=gross_notional,
        reserved_utc=record.decision_created_utc,
    )
    next_state = _build_state(
        previous=account.state,
        as_of_utc=record.decision_created_utc,
        cash=account.state.cash - capital_required,
        reserved_capital=account.state.reserved_capital + capital_required,
        gross_exposure=account.state.gross_exposure + gross_notional,
        stock_reservations=account.state.stock_reservations + (reservation,),
    )
    return _append_event(
        account=account,
        next_state=next_state,
        kind=SimulationAccountEventKind.RESERVE_STOCK,
        occurred_utc=record.decision_created_utc,
        decision_record_fingerprint=record_fingerprint,
        candidate_identifier=candidate.identifier,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        capital_delta=capital_required,
        gross_exposure_delta=gross_notional,
        reason_codes=("STOCK_CAPITAL_RESERVED",),
    )


def release_stock_reservation(
    account: SimulationAccount,
    *,
    decision_record_fingerprint: str,
    released_utc: datetime,
    reason_codes: tuple[str, ...] = ("STOCK_CAPITAL_RELEASED",),
) -> SimulationAccountTransition:
    _require_fingerprint(
        decision_record_fingerprint,
        label="release decision-record fingerprint",
    )
    _require_aware(released_utc, label="release timestamp")
    if released_utc < account.state.as_of_utc:
        raise SimulationAccountStateError(
            "release timestamp cannot precede current account state"
        )
    reservation = next(
        (
            item
            for item in account.state.stock_reservations
            if item.decision_record_fingerprint == decision_record_fingerprint
        ),
        None,
    )
    if reservation is None:
        already_released = any(
            event.kind == SimulationAccountEventKind.RELEASE_STOCK
            and event.decision_record_fingerprint == decision_record_fingerprint
            for event in account.ledger.events
        )
        if already_released:
            return SimulationAccountTransition(
                account=account,
                event=None,
                idempotent_reuse=True,
                reason_codes=("RESERVATION_ALREADY_RELEASED",),
            )
        raise SimulationAccountStateError("active stock reservation not found")
    if not reason_codes:
        raise SimulationAccountStateError("release requires reason codes")

    remaining = tuple(
        item
        for item in account.state.stock_reservations
        if item.decision_record_fingerprint != decision_record_fingerprint
    )
    next_state = _build_state(
        previous=account.state,
        as_of_utc=released_utc,
        cash=account.state.cash + reservation.reserved_capital,
        reserved_capital=account.state.reserved_capital - reservation.reserved_capital,
        gross_exposure=account.state.gross_exposure - reservation.gross_exposure,
        stock_reservations=remaining,
    )
    return _append_event(
        account=account,
        next_state=next_state,
        kind=SimulationAccountEventKind.RELEASE_STOCK,
        occurred_utc=released_utc,
        decision_record_fingerprint=decision_record_fingerprint,
        candidate_identifier=reservation.candidate_identifier,
        instrument_id=reservation.instrument_id,
        ticker=reservation.ticker,
        direction=reservation.direction,
        capital_delta=-reservation.reserved_capital,
        gross_exposure_delta=-reservation.gross_exposure,
        reason_codes=reason_codes,
    )


def apply_competing_decisions(
    account: SimulationAccount,
    records: Sequence[SimulationDecisionRecord],
) -> SimulationCompetitionResult:
    ordered = tuple(
        sorted(
            records,
            key=lambda record: (
                record.decision_created_utc,
                record.record_fingerprint,
            ),
        )
    )
    current = account
    transitions: list[SimulationAccountTransition] = []
    for record in ordered:
        transition = apply_simulation_decision(current, record)
        current = transition.account
        transitions.append(transition)
    return SimulationCompetitionResult(
        account=current,
        ordered_decision_fingerprints=tuple(
            record.record_fingerprint for record in ordered
        ),
        transitions=tuple(transitions),
    )


def replay_account_ledger(ledger: SimulationAccountLedger) -> SimulationAccount:
    account = initialize_simulation_account(
        as_of_utc=ledger.initial_as_of_utc,
        equity=ledger.initial_equity,
    )
    if account.state.state_fingerprint != ledger.initial_state_fingerprint:
        raise SimulationAccountStateError("ledger initial-state fingerprint mismatch")

    state = account.state
    for event in ledger.events:
        if state.state_fingerprint != event.before_state_fingerprint:
            raise SimulationAccountStateError("ledger before-state fingerprint mismatch")
        if event.occurred_utc < state.as_of_utc:
            raise SimulationAccountStateError("ledger event chronology mismatch")

        reservations = list(state.stock_reservations)
        cash = state.cash
        reserved_capital = state.reserved_capital
        gross_exposure = state.gross_exposure

        if event.kind == SimulationAccountEventKind.RESERVE_STOCK:
            assert event.decision_record_fingerprint is not None
            assert event.candidate_identifier is not None
            assert event.instrument_id is not None
            assert event.ticker is not None
            assert event.direction is not None
            if any(
                item.decision_record_fingerprint == event.decision_record_fingerprint
                for item in reservations
            ):
                raise SimulationAccountStateError(
                    "ledger cannot reserve the same decision twice"
                )
            reservations.append(
                SimulatedStockReservation(
                    decision_record_fingerprint=event.decision_record_fingerprint,
                    candidate_identifier=event.candidate_identifier,
                    instrument_id=event.instrument_id,
                    ticker=event.ticker,
                    direction=event.direction,
                    reserved_capital=event.capital_delta,
                    gross_exposure=event.gross_exposure_delta,
                    reserved_utc=event.occurred_utc,
                )
            )
            cash -= event.capital_delta
            reserved_capital += event.capital_delta
            gross_exposure += event.gross_exposure_delta
        elif event.kind == SimulationAccountEventKind.RELEASE_STOCK:
            assert event.decision_record_fingerprint is not None
            reservation = next(
                (
                    item
                    for item in reservations
                    if item.decision_record_fingerprint
                    == event.decision_record_fingerprint
                ),
                None,
            )
            if reservation is None:
                raise SimulationAccountStateError(
                    "ledger release has no active reservation"
                )
            if not _same(event.capital_delta, -reservation.reserved_capital):
                raise SimulationAccountStateError(
                    "ledger release capital does not match reservation"
                )
            if not _same(event.gross_exposure_delta, -reservation.gross_exposure):
                raise SimulationAccountStateError(
                    "ledger release exposure does not match reservation"
                )
            reservations = [
                item
                for item in reservations
                if item.decision_record_fingerprint
                != event.decision_record_fingerprint
            ]
            cash -= event.capital_delta
            reserved_capital += event.capital_delta
            gross_exposure += event.gross_exposure_delta
        elif event.kind not in {
            SimulationAccountEventKind.ABSTAIN,
            SimulationAccountEventKind.REJECT_UNSUPPORTED_OPTION,
            SimulationAccountEventKind.REJECT_INSUFFICIENT_CAPITAL,
        }:
            raise SimulationAccountStateError("unsupported ledger event kind")

        state = _build_state(
            previous=state,
            as_of_utc=event.occurred_utc,
            cash=cash,
            reserved_capital=reserved_capital,
            gross_exposure=gross_exposure,
            stock_reservations=reservations,
        )
        if state.state_fingerprint != event.after_state_fingerprint:
            raise SimulationAccountStateError("ledger after-state fingerprint mismatch")

    return SimulationAccount(state=state, ledger=ledger)
