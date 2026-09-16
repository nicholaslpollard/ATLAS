from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Mapping, Sequence

from packages.execution.trade_expression import InstrumentKind, SelectionKind
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT,
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    economic_candidate_fingerprint,
)
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
)
from packages.simulation.option_reservation import (
    LongOptionReservationTerms,
    long_option_reservation_terms_fingerprint,
)
from packages.simulation.option_reservation_contract import (
    LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
)


SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION = str(
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class SimulationAccountStateV2Error(ValueError):
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
        raise SimulationAccountStateV2Error(f"{label} must be timezone-aware")


def _require_nonnegative_finite(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise SimulationAccountStateV2Error(f"{label} must be finite and nonnegative")


def _require_positive_finite(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise SimulationAccountStateV2Error(f"{label} must be finite and positive")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _normalize_zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise SimulationAccountStateV2Error(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SimulationAccountStateV2Error(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


@dataclass(frozen=True)
class SimulatedStockReservationV2:
    decision_record_fingerprint: str
    candidate_identifier: str
    instrument_id: str
    ticker: str
    direction: str
    reserved_capital: float
    gross_notional: float
    reserved_utc: datetime

    def __post_init__(self) -> None:
        _require_fingerprint(
            self.decision_record_fingerprint,
            label="stock decision-record fingerprint",
        )
        if not self.candidate_identifier.strip():
            raise SimulationAccountStateV2Error("stock candidate identifier cannot be blank")
        if not self.instrument_id.strip() or not self.ticker.strip() or not self.direction.strip():
            raise SimulationAccountStateV2Error("stock reservation identity cannot be blank")
        _require_positive_finite(self.reserved_capital, label="stock reserved capital")
        _require_positive_finite(self.gross_notional, label="stock gross notional")
        _require_aware(self.reserved_utc, label="stock reservation timestamp")


@dataclass(frozen=True)
class SimulatedOptionReservationV2:
    decision_record_fingerprint: str
    reservation_terms_fingerprint: str
    option_economics_result_fingerprint: str
    candidate_identifier: str
    option_contract_ticker: str
    instrument_id: str
    ticker: str
    direction: str
    reserved_capital: float
    max_loss_cash: float
    premium_at_risk: float
    signed_delta_equivalent_notional: float
    abs_delta_equivalent_notional: float
    reserved_utc: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("option decision-record", self.decision_record_fingerprint),
            ("option reservation-terms", self.reservation_terms_fingerprint),
            ("option economics-result", self.option_economics_result_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        if not self.candidate_identifier.strip():
            raise SimulationAccountStateV2Error("option candidate identifier cannot be blank")
        if not self.option_contract_ticker.strip():
            raise SimulationAccountStateV2Error("option contract ticker cannot be blank")
        if not self.instrument_id.strip() or not self.ticker.strip() or not self.direction.strip():
            raise SimulationAccountStateV2Error("option reservation identity cannot be blank")
        _require_positive_finite(self.reserved_capital, label="option reserved capital")
        _require_positive_finite(self.max_loss_cash, label="option max-loss cash")
        _require_positive_finite(self.premium_at_risk, label="option premium at risk")
        if not _same(self.max_loss_cash, self.reserved_capital):
            raise SimulationAccountStateV2Error(
                "long-option max-loss cash must equal option reserved capital"
            )
        if not math.isfinite(self.signed_delta_equivalent_notional) or _same(
            self.signed_delta_equivalent_notional,
            0.0,
        ):
            raise SimulationAccountStateV2Error(
                "option signed delta-equivalent notional must be finite and nonzero"
            )
        _require_positive_finite(
            self.abs_delta_equivalent_notional,
            label="option absolute delta-equivalent notional",
        )
        if not _same(
            self.abs_delta_equivalent_notional,
            abs(self.signed_delta_equivalent_notional),
        ):
            raise SimulationAccountStateV2Error(
                "option absolute delta-equivalent notional mismatch"
            )
        if self.direction == "BULLISH" and self.signed_delta_equivalent_notional <= 0.0:
            raise SimulationAccountStateV2Error("bullish option reservation requires positive delta exposure")
        if self.direction == "BEARISH" and self.signed_delta_equivalent_notional >= 0.0:
            raise SimulationAccountStateV2Error("bearish option reservation requires negative delta exposure")
        _require_aware(self.reserved_utc, label="option reservation timestamp")


@dataclass(frozen=True)
class SimulationAccountStateV2:
    contract_version: str
    contract_fingerprint: str
    as_of_utc: datetime
    initial_equity: float
    equity: float
    cash: float
    stock_reserved_capital: float
    option_reserved_capital: float
    stock_gross_notional: float
    option_signed_delta_equivalent_notional: float
    option_abs_delta_equivalent_notional: float
    option_max_loss_cash: float
    option_premium_at_risk: float
    stock_reservations: tuple[SimulatedStockReservationV2, ...]
    option_reservations: tuple[SimulatedOptionReservationV2, ...]
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
        if self.contract_version != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION:
            raise SimulationAccountStateV2Error("simulation account-state v2 contract version mismatch")
        if self.contract_fingerprint != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT:
            raise SimulationAccountStateV2Error("simulation account-state v2 contract fingerprint mismatch")
        _require_aware(self.as_of_utc, label="account-state v2 timestamp")
        _require_positive_finite(self.initial_equity, label="initial equity")
        _require_positive_finite(self.equity, label="equity")
        _require_nonnegative_finite(self.cash, label="cash")
        _require_nonnegative_finite(self.stock_reserved_capital, label="stock reserved capital")
        _require_nonnegative_finite(self.option_reserved_capital, label="option reserved capital")
        _require_nonnegative_finite(self.stock_gross_notional, label="stock gross notional")
        if not math.isfinite(self.option_signed_delta_equivalent_notional):
            raise SimulationAccountStateV2Error("option signed delta-equivalent total must be finite")
        _require_nonnegative_finite(
            self.option_abs_delta_equivalent_notional,
            label="option absolute delta-equivalent total",
        )
        _require_nonnegative_finite(self.option_max_loss_cash, label="option max-loss cash total")
        _require_nonnegative_finite(self.option_premium_at_risk, label="option premium-at-risk total")
        if not _same(self.equity, self.initial_equity):
            raise SimulationAccountStateV2Error(
                "reservation-only account state v2 cannot change equity"
            )
        if not _same(
            self.cash + self.stock_reserved_capital + self.option_reserved_capital,
            self.equity,
        ):
            raise SimulationAccountStateV2Error(
                "cash plus stock and option reserved capital must equal equity"
            )

        ordered_stocks = tuple(
            sorted(self.stock_reservations, key=lambda item: item.decision_record_fingerprint)
        )
        ordered_options = tuple(
            sorted(self.option_reservations, key=lambda item: item.decision_record_fingerprint)
        )
        if self.stock_reservations != ordered_stocks:
            raise SimulationAccountStateV2Error("stock reservations must be ordered by decision fingerprint")
        if self.option_reservations != ordered_options:
            raise SimulationAccountStateV2Error("option reservations must be ordered by decision fingerprint")
        stock_ids = [item.decision_record_fingerprint for item in self.stock_reservations]
        option_ids = [item.decision_record_fingerprint for item in self.option_reservations]
        if len(stock_ids) != len(set(stock_ids)):
            raise SimulationAccountStateV2Error("active stock reservations cannot share a decision fingerprint")
        if len(option_ids) != len(set(option_ids)):
            raise SimulationAccountStateV2Error("active option reservations cannot share a decision fingerprint")
        if set(stock_ids).intersection(option_ids):
            raise SimulationAccountStateV2Error("one decision cannot hold both stock and option reservations")
        if any(item.reserved_utc > self.as_of_utc for item in self.stock_reservations):
            raise SimulationAccountStateV2Error("active stock reservation cannot postdate account state")
        if any(item.reserved_utc > self.as_of_utc for item in self.option_reservations):
            raise SimulationAccountStateV2Error("active option reservation cannot postdate account state")

        stock_capital_sum = sum(item.reserved_capital for item in self.stock_reservations)
        option_capital_sum = sum(item.reserved_capital for item in self.option_reservations)
        stock_notional_sum = sum(item.gross_notional for item in self.stock_reservations)
        option_signed_sum = sum(
            item.signed_delta_equivalent_notional for item in self.option_reservations
        )
        option_abs_sum = sum(
            item.abs_delta_equivalent_notional for item in self.option_reservations
        )
        option_max_loss_sum = sum(item.max_loss_cash for item in self.option_reservations)
        option_premium_sum = sum(item.premium_at_risk for item in self.option_reservations)

        checks = (
            (self.stock_reserved_capital, stock_capital_sum, "stock reserved-capital total"),
            (self.option_reserved_capital, option_capital_sum, "option reserved-capital total"),
            (self.stock_gross_notional, stock_notional_sum, "stock gross-notional total"),
            (
                self.option_signed_delta_equivalent_notional,
                option_signed_sum,
                "option signed delta-equivalent total",
            ),
            (
                self.option_abs_delta_equivalent_notional,
                option_abs_sum,
                "option absolute delta-equivalent total",
            ),
            (self.option_max_loss_cash, option_max_loss_sum, "option max-loss total"),
            (self.option_premium_at_risk, option_premium_sum, "option premium-at-risk total"),
        )
        for actual, expected, label in checks:
            if not _same(actual, expected):
                raise SimulationAccountStateV2Error(f"{label} must equal active reservation sum")
        if not _same(self.option_max_loss_cash, self.option_reserved_capital):
            raise SimulationAccountStateV2Error(
                "long-option max-loss total must equal option reserved capital"
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
            raise SimulationAccountStateV2Error(
                "simulation account-state v2 cannot grant provider, broker, order, fill, P&L, trading, promotion, or confluence authority"
            )

    @property
    def total_reserved_capital(self) -> float:
        return self.stock_reserved_capital + self.option_reserved_capital

    @property
    def state_fingerprint(self) -> str:
        return simulation_account_state_v2_fingerprint(self)


class SimulationAccountV2EventKind(StrEnum):
    RESERVE_STOCK = "RESERVE_STOCK"
    RELEASE_STOCK = "RELEASE_STOCK"
    RESERVE_OPTION = "RESERVE_OPTION"
    RELEASE_OPTION = "RELEASE_OPTION"
    ABSTAIN = "ABSTAIN"
    REJECT_MISSING_OPTION_TERMS = "REJECT_MISSING_OPTION_TERMS"
    REJECT_INSUFFICIENT_CAPITAL = "REJECT_INSUFFICIENT_CAPITAL"


@dataclass(frozen=True)
class SimulationAccountV2LedgerEvent:
    sequence: int
    occurred_utc: datetime
    kind: SimulationAccountV2EventKind
    decision_record_fingerprint: str | None
    reservation_terms_fingerprint: str | None
    option_economics_result_fingerprint: str | None
    candidate_identifier: str | None
    option_contract_ticker: str | None
    instrument_id: str | None
    ticker: str | None
    direction: str | None
    stock_capital_delta: float
    option_capital_delta: float
    stock_gross_notional_delta: float
    option_signed_delta_equivalent_delta: float
    option_abs_delta_equivalent_delta: float
    option_max_loss_delta: float
    option_premium_at_risk_delta: float
    reason_codes: tuple[str, ...]
    before_state_fingerprint: str
    after_state_fingerprint: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise SimulationAccountStateV2Error("ledger event sequence must be positive")
        _require_aware(self.occurred_utc, label="ledger event timestamp")
        if self.decision_record_fingerprint is not None:
            _require_fingerprint(
                self.decision_record_fingerprint,
                label="ledger decision-record fingerprint",
            )
        if self.reservation_terms_fingerprint is not None:
            _require_fingerprint(
                self.reservation_terms_fingerprint,
                label="ledger reservation-terms fingerprint",
            )
        if self.option_economics_result_fingerprint is not None:
            _require_fingerprint(
                self.option_economics_result_fingerprint,
                label="ledger option-economics fingerprint",
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
            raise SimulationAccountStateV2Error("ledger event deltas must be finite")
        if not self.reason_codes:
            raise SimulationAccountStateV2Error("ledger event requires reason codes")
        _require_fingerprint(self.before_state_fingerprint, label="before-state fingerprint")
        _require_fingerprint(self.after_state_fingerprint, label="after-state fingerprint")

        stock_deltas = (self.stock_capital_delta, self.stock_gross_notional_delta)
        option_deltas = (
            self.option_capital_delta,
            self.option_signed_delta_equivalent_delta,
            self.option_abs_delta_equivalent_delta,
            self.option_max_loss_delta,
            self.option_premium_at_risk_delta,
        )
        if self.kind == SimulationAccountV2EventKind.RESERVE_STOCK:
            if self.decision_record_fingerprint is None:
                raise SimulationAccountStateV2Error("stock reservation requires decision lineage")
            if self.stock_capital_delta <= 0.0 or self.stock_gross_notional_delta <= 0.0:
                raise SimulationAccountStateV2Error("stock reservation deltas must be positive")
            if any(not _same(value, 0.0) for value in option_deltas):
                raise SimulationAccountStateV2Error("stock reservation cannot mutate option amounts")
        elif self.kind == SimulationAccountV2EventKind.RELEASE_STOCK:
            if self.decision_record_fingerprint is None:
                raise SimulationAccountStateV2Error("stock release requires decision lineage")
            if self.stock_capital_delta >= 0.0 or self.stock_gross_notional_delta >= 0.0:
                raise SimulationAccountStateV2Error("stock release deltas must be negative")
            if any(not _same(value, 0.0) for value in option_deltas):
                raise SimulationAccountStateV2Error("stock release cannot mutate option amounts")
        elif self.kind == SimulationAccountV2EventKind.RESERVE_OPTION:
            if self.decision_record_fingerprint is None or self.reservation_terms_fingerprint is None:
                raise SimulationAccountStateV2Error("option reservation requires decision and terms lineage")
            if self.option_economics_result_fingerprint is None:
                raise SimulationAccountStateV2Error("option reservation requires economics lineage")
            if self.option_capital_delta <= 0.0:
                raise SimulationAccountStateV2Error("option reservation capital delta must be positive")
            if self.option_abs_delta_equivalent_delta <= 0.0:
                raise SimulationAccountStateV2Error("option reservation absolute exposure must be positive")
            if self.option_max_loss_delta <= 0.0 or self.option_premium_at_risk_delta <= 0.0:
                raise SimulationAccountStateV2Error("option reservation risk deltas must be positive")
            if any(not _same(value, 0.0) for value in stock_deltas):
                raise SimulationAccountStateV2Error("option reservation cannot mutate stock amounts")
        elif self.kind == SimulationAccountV2EventKind.RELEASE_OPTION:
            if self.decision_record_fingerprint is None or self.reservation_terms_fingerprint is None:
                raise SimulationAccountStateV2Error("option release requires decision and terms lineage")
            if self.option_economics_result_fingerprint is None:
                raise SimulationAccountStateV2Error("option release requires economics lineage")
            if self.option_capital_delta >= 0.0:
                raise SimulationAccountStateV2Error("option release capital delta must be negative")
            if self.option_abs_delta_equivalent_delta >= 0.0:
                raise SimulationAccountStateV2Error("option release absolute exposure must be negative")
            if self.option_max_loss_delta >= 0.0 or self.option_premium_at_risk_delta >= 0.0:
                raise SimulationAccountStateV2Error("option release risk deltas must be negative")
            if any(not _same(value, 0.0) for value in stock_deltas):
                raise SimulationAccountStateV2Error("option release cannot mutate stock amounts")
        elif any(not _same(value, 0.0) for value in deltas):
            raise SimulationAccountStateV2Error(
                "non-reservation ledger events cannot change account amounts"
            )

    @property
    def event_fingerprint(self) -> str:
        return simulation_account_v2_event_fingerprint(self)


@dataclass(frozen=True)
class SimulationAccountV2Ledger:
    contract_version: str
    contract_fingerprint: str
    initial_equity: float
    initial_as_of_utc: datetime
    initial_state_fingerprint: str
    events: tuple[SimulationAccountV2LedgerEvent, ...]

    def __post_init__(self) -> None:
        if self.contract_version != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION:
            raise SimulationAccountStateV2Error("simulation account-state v2 ledger contract version mismatch")
        if self.contract_fingerprint != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT:
            raise SimulationAccountStateV2Error("simulation account-state v2 ledger fingerprint mismatch")
        _require_positive_finite(self.initial_equity, label="ledger initial equity")
        _require_aware(self.initial_as_of_utc, label="ledger initial timestamp")
        _require_fingerprint(self.initial_state_fingerprint, label="ledger initial-state fingerprint")
        previous_time = self.initial_as_of_utc
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence:
                raise SimulationAccountStateV2Error("ledger event sequence must be contiguous and one-based")
            if event.occurred_utc < previous_time:
                raise SimulationAccountStateV2Error("ledger events must be chronological")
            previous_time = event.occurred_utc

    @property
    def ledger_fingerprint(self) -> str:
        return simulation_account_v2_ledger_fingerprint(self)


@dataclass(frozen=True)
class SimulationAccountV2:
    state: SimulationAccountStateV2
    ledger: SimulationAccountV2Ledger

    def __post_init__(self) -> None:
        if not _same(self.state.initial_equity, self.ledger.initial_equity):
            raise SimulationAccountStateV2Error("account state and ledger initial equity must match")
        expected_fingerprint = (
            self.ledger.events[-1].after_state_fingerprint
            if self.ledger.events
            else self.ledger.initial_state_fingerprint
        )
        if self.state.state_fingerprint != expected_fingerprint:
            raise SimulationAccountStateV2Error("account state must match latest ledger state fingerprint")
        expected_time = (
            self.ledger.events[-1].occurred_utc
            if self.ledger.events
            else self.ledger.initial_as_of_utc
        )
        if self.state.as_of_utc != expected_time:
            raise SimulationAccountStateV2Error("account state timestamp must match latest ledger timestamp")


@dataclass(frozen=True)
class SimulationAccountV2Transition:
    account: SimulationAccountV2
    event: SimulationAccountV2LedgerEvent | None
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class SimulationCompetitionV2Result:
    account: SimulationAccountV2
    ordered_decision_fingerprints: tuple[str, ...]
    transitions: tuple[SimulationAccountV2Transition, ...]


def simulation_account_state_v2_fingerprint(state: SimulationAccountStateV2) -> str:
    return _fingerprint_payload(state)


def simulation_account_v2_event_fingerprint(event: SimulationAccountV2LedgerEvent) -> str:
    return _fingerprint_payload(event)


def simulation_account_v2_ledger_fingerprint(ledger: SimulationAccountV2Ledger) -> str:
    return _fingerprint_payload(ledger)


def initialize_simulation_account_v2(
    *,
    as_of_utc: datetime,
    equity: float,
) -> SimulationAccountV2:
    _require_aware(as_of_utc, label="initial account timestamp")
    _require_positive_finite(equity, label="initial account equity")
    state = SimulationAccountStateV2(
        contract_version=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION,
        contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        as_of_utc=as_of_utc,
        initial_equity=float(equity),
        equity=float(equity),
        cash=float(equity),
        stock_reserved_capital=0.0,
        option_reserved_capital=0.0,
        stock_gross_notional=0.0,
        option_signed_delta_equivalent_notional=0.0,
        option_abs_delta_equivalent_notional=0.0,
        option_max_loss_cash=0.0,
        option_premium_at_risk=0.0,
        stock_reservations=(),
        option_reservations=(),
    )
    ledger = SimulationAccountV2Ledger(
        contract_version=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION,
        contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        initial_equity=float(equity),
        initial_as_of_utc=as_of_utc,
        initial_state_fingerprint=state.state_fingerprint,
        events=(),
    )
    return SimulationAccountV2(state=state, ledger=ledger)


def _build_state(
    *,
    previous: SimulationAccountStateV2,
    as_of_utc: datetime,
    cash: float,
    stock_reserved_capital: float,
    option_reserved_capital: float,
    stock_gross_notional: float,
    option_signed_delta_equivalent_notional: float,
    option_abs_delta_equivalent_notional: float,
    option_max_loss_cash: float,
    option_premium_at_risk: float,
    stock_reservations: Sequence[SimulatedStockReservationV2],
    option_reservations: Sequence[SimulatedOptionReservationV2],
) -> SimulationAccountStateV2:
    return SimulationAccountStateV2(
        contract_version=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION,
        contract_fingerprint=SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        equity=previous.equity,
        cash=_normalize_zero(cash),
        stock_reserved_capital=_normalize_zero(stock_reserved_capital),
        option_reserved_capital=_normalize_zero(option_reserved_capital),
        stock_gross_notional=_normalize_zero(stock_gross_notional),
        option_signed_delta_equivalent_notional=_normalize_zero(
            option_signed_delta_equivalent_notional
        ),
        option_abs_delta_equivalent_notional=_normalize_zero(
            option_abs_delta_equivalent_notional
        ),
        option_max_loss_cash=_normalize_zero(option_max_loss_cash),
        option_premium_at_risk=_normalize_zero(option_premium_at_risk),
        stock_reservations=tuple(
            sorted(stock_reservations, key=lambda item: item.decision_record_fingerprint)
        ),
        option_reservations=tuple(
            sorted(option_reservations, key=lambda item: item.decision_record_fingerprint)
        ),
    )


def _unchanged_state(account: SimulationAccountV2, *, as_of_utc: datetime) -> SimulationAccountStateV2:
    state = account.state
    return _build_state(
        previous=state,
        as_of_utc=as_of_utc,
        cash=state.cash,
        stock_reserved_capital=state.stock_reserved_capital,
        option_reserved_capital=state.option_reserved_capital,
        stock_gross_notional=state.stock_gross_notional,
        option_signed_delta_equivalent_notional=state.option_signed_delta_equivalent_notional,
        option_abs_delta_equivalent_notional=state.option_abs_delta_equivalent_notional,
        option_max_loss_cash=state.option_max_loss_cash,
        option_premium_at_risk=state.option_premium_at_risk,
        stock_reservations=state.stock_reservations,
        option_reservations=state.option_reservations,
    )


def _append_event(
    *,
    account: SimulationAccountV2,
    next_state: SimulationAccountStateV2,
    kind: SimulationAccountV2EventKind,
    occurred_utc: datetime,
    decision_record_fingerprint: str | None,
    reservation_terms_fingerprint: str | None = None,
    option_economics_result_fingerprint: str | None = None,
    candidate_identifier: str | None = None,
    option_contract_ticker: str | None = None,
    instrument_id: str | None = None,
    ticker: str | None = None,
    direction: str | None = None,
    stock_capital_delta: float = 0.0,
    option_capital_delta: float = 0.0,
    stock_gross_notional_delta: float = 0.0,
    option_signed_delta_equivalent_delta: float = 0.0,
    option_abs_delta_equivalent_delta: float = 0.0,
    option_max_loss_delta: float = 0.0,
    option_premium_at_risk_delta: float = 0.0,
    reason_codes: tuple[str, ...],
) -> SimulationAccountV2Transition:
    event = SimulationAccountV2LedgerEvent(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=occurred_utc,
        kind=kind,
        decision_record_fingerprint=decision_record_fingerprint,
        reservation_terms_fingerprint=reservation_terms_fingerprint,
        option_economics_result_fingerprint=option_economics_result_fingerprint,
        candidate_identifier=candidate_identifier,
        option_contract_ticker=option_contract_ticker,
        instrument_id=instrument_id,
        ticker=ticker,
        direction=direction,
        stock_capital_delta=stock_capital_delta,
        option_capital_delta=option_capital_delta,
        stock_gross_notional_delta=stock_gross_notional_delta,
        option_signed_delta_equivalent_delta=option_signed_delta_equivalent_delta,
        option_abs_delta_equivalent_delta=option_abs_delta_equivalent_delta,
        option_max_loss_delta=option_max_loss_delta,
        option_premium_at_risk_delta=option_premium_at_risk_delta,
        reason_codes=reason_codes,
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
    )
    ledger = SimulationAccountV2Ledger(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        initial_equity=account.ledger.initial_equity,
        initial_as_of_utc=account.ledger.initial_as_of_utc,
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = SimulationAccountV2(state=next_state, ledger=ledger)
    return SimulationAccountV2Transition(
        account=next_account,
        event=event,
        idempotent_reuse=False,
        reason_codes=reason_codes,
    )


def _prior_decision_event(
    account: SimulationAccountV2,
    decision_record_fingerprint: str,
) -> SimulationAccountV2LedgerEvent | None:
    decision_kinds = {
        SimulationAccountV2EventKind.RESERVE_STOCK,
        SimulationAccountV2EventKind.RESERVE_OPTION,
        SimulationAccountV2EventKind.ABSTAIN,
        SimulationAccountV2EventKind.REJECT_MISSING_OPTION_TERMS,
        SimulationAccountV2EventKind.REJECT_INSUFFICIENT_CAPITAL,
    }
    return next(
        (
            event
            for event in account.ledger.events
            if event.decision_record_fingerprint == decision_record_fingerprint
            and event.kind in decision_kinds
        ),
        None,
    )


def _validate_option_terms_lineage(
    *,
    record: SimulationDecisionRecord,
    terms: LongOptionReservationTerms,
) -> None:
    if terms.contract_fingerprint != LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT:
        raise SimulationAccountStateV2Error("long-option reservation contract fingerprint mismatch")
    if terms.decision_record_fingerprint != record.record_fingerprint:
        raise SimulationAccountStateV2Error("option reservation decision lineage mismatch")
    if terms.source_forecast_fingerprint != record.forecast_fingerprint:
        raise SimulationAccountStateV2Error("option reservation forecast lineage mismatch")
    decision = record.trade_expression_decision
    candidate = decision.chosen_candidate
    if candidate is None or candidate.kind != InstrumentKind.OPTION:
        raise SimulationAccountStateV2Error("option reservation requires selected option candidate")
    if terms.chosen_candidate_identifier != candidate.identifier:
        raise SimulationAccountStateV2Error("option reservation candidate identifier mismatch")
    if terms.chosen_candidate_fingerprint != economic_candidate_fingerprint(candidate):
        raise SimulationAccountStateV2Error("option reservation candidate fingerprint mismatch")
    if terms.instrument_id != record.forecast.instrument_id or terms.ticker != record.forecast.ticker:
        raise SimulationAccountStateV2Error("option reservation underlying identity mismatch")
    if terms.direction != record.forecast.direction:
        raise SimulationAccountStateV2Error("option reservation direction mismatch")


def apply_simulation_decision_v2(
    account: SimulationAccountV2,
    record: SimulationDecisionRecord,
    *,
    option_terms: LongOptionReservationTerms | None = None,
) -> SimulationAccountV2Transition:
    if record.contract_fingerprint != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT:
        raise SimulationAccountStateV2Error("decision record contract fingerprint mismatch")
    record_fingerprint = record.record_fingerprint
    prior = _prior_decision_event(account, record_fingerprint)
    if prior is not None:
        if prior.kind == SimulationAccountV2EventKind.RESERVE_OPTION and option_terms is not None:
            if prior.reservation_terms_fingerprint != long_option_reservation_terms_fingerprint(option_terms):
                raise SimulationAccountStateV2Error("duplicate option decision supplied different reservation terms")
        return SimulationAccountV2Transition(
            account=account,
            event=None,
            idempotent_reuse=True,
            reason_codes=("DECISION_ALREADY_APPLIED",),
        )
    if record.decision_created_utc < account.state.as_of_utc:
        raise SimulationAccountStateV2Error("decision timestamp cannot precede current account state")

    decision = record.trade_expression_decision
    if decision.selection_kind == SelectionKind.ABSTAIN:
        if option_terms is not None:
            raise SimulationAccountStateV2Error("option reservation terms cannot accompany abstention")
        next_state = _unchanged_state(account, as_of_utc=record.decision_created_utc)
        return _append_event(
            account=account,
            next_state=next_state,
            kind=SimulationAccountV2EventKind.ABSTAIN,
            occurred_utc=record.decision_created_utc,
            decision_record_fingerprint=record_fingerprint,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            reason_codes=("DECISION_ABSTAINED",) + decision.reason_codes,
        )

    candidate = decision.chosen_candidate
    if candidate is None:
        raise SimulationAccountStateV2Error("non-abstain decision must carry a chosen candidate")

    if decision.selection_kind == SelectionKind.STOCK:
        if option_terms is not None:
            raise SimulationAccountStateV2Error("option reservation terms cannot accompany stock decision")
        if candidate.kind != InstrumentKind.STOCK:
            raise SimulationAccountStateV2Error("stock selection does not carry a stock candidate")
        stock_candidate = record.stock_economics.candidate
        if candidate.identifier != stock_candidate.identifier:
            raise SimulationAccountStateV2Error("chosen stock candidate identifier mismatch")
        if economic_candidate_fingerprint(candidate) != economic_candidate_fingerprint(stock_candidate):
            raise SimulationAccountStateV2Error("chosen stock candidate fingerprint mismatch")
        capital_required = float(record.stock_economics.capital_required_dollars)
        gross_notional = float(record.stock_economics.position_notional_dollars)
        if not _same(candidate.capital_required, capital_required):
            raise SimulationAccountStateV2Error("stock capital lineage mismatch")
        if capital_required > account.state.cash and not _same(capital_required, account.state.cash):
            next_state = _unchanged_state(account, as_of_utc=record.decision_created_utc)
            return _append_event(
                account=account,
                next_state=next_state,
                kind=SimulationAccountV2EventKind.REJECT_INSUFFICIENT_CAPITAL,
                occurred_utc=record.decision_created_utc,
                decision_record_fingerprint=record_fingerprint,
                candidate_identifier=candidate.identifier,
                instrument_id=record.forecast.instrument_id,
                ticker=record.forecast.ticker,
                direction=record.forecast.direction.value,
                reason_codes=("INSUFFICIENT_UNRESERVED_CASH", "STOCK_RESERVATION_REJECTED"),
            )
        reservation = SimulatedStockReservationV2(
            decision_record_fingerprint=record_fingerprint,
            candidate_identifier=candidate.identifier,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            reserved_capital=capital_required,
            gross_notional=gross_notional,
            reserved_utc=record.decision_created_utc,
        )
        state = account.state
        next_state = _build_state(
            previous=state,
            as_of_utc=record.decision_created_utc,
            cash=state.cash - capital_required,
            stock_reserved_capital=state.stock_reserved_capital + capital_required,
            option_reserved_capital=state.option_reserved_capital,
            stock_gross_notional=state.stock_gross_notional + gross_notional,
            option_signed_delta_equivalent_notional=state.option_signed_delta_equivalent_notional,
            option_abs_delta_equivalent_notional=state.option_abs_delta_equivalent_notional,
            option_max_loss_cash=state.option_max_loss_cash,
            option_premium_at_risk=state.option_premium_at_risk,
            stock_reservations=state.stock_reservations + (reservation,),
            option_reservations=state.option_reservations,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=SimulationAccountV2EventKind.RESERVE_STOCK,
            occurred_utc=record.decision_created_utc,
            decision_record_fingerprint=record_fingerprint,
            candidate_identifier=candidate.identifier,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            stock_capital_delta=capital_required,
            stock_gross_notional_delta=gross_notional,
            reason_codes=("STOCK_CAPITAL_RESERVED",),
        )

    if decision.selection_kind != SelectionKind.OPTION or candidate.kind != InstrumentKind.OPTION:
        raise SimulationAccountStateV2Error("unsupported simulation selection kind")
    if option_terms is None:
        next_state = _unchanged_state(account, as_of_utc=record.decision_created_utc)
        return _append_event(
            account=account,
            next_state=next_state,
            kind=SimulationAccountV2EventKind.REJECT_MISSING_OPTION_TERMS,
            occurred_utc=record.decision_created_utc,
            decision_record_fingerprint=record_fingerprint,
            candidate_identifier=candidate.identifier,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            reason_codes=("LONG_OPTION_RESERVATION_TERMS_REQUIRED",),
        )

    _validate_option_terms_lineage(record=record, terms=option_terms)
    terms_fingerprint = long_option_reservation_terms_fingerprint(option_terms)
    capital_required = float(option_terms.reserved_capital_dollars)
    if capital_required > account.state.cash and not _same(capital_required, account.state.cash):
        next_state = _unchanged_state(account, as_of_utc=record.decision_created_utc)
        return _append_event(
            account=account,
            next_state=next_state,
            kind=SimulationAccountV2EventKind.REJECT_INSUFFICIENT_CAPITAL,
            occurred_utc=record.decision_created_utc,
            decision_record_fingerprint=record_fingerprint,
            reservation_terms_fingerprint=terms_fingerprint,
            option_economics_result_fingerprint=option_terms.option_economics_result_fingerprint,
            candidate_identifier=candidate.identifier,
            option_contract_ticker=option_terms.option_contract_ticker,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            reason_codes=("INSUFFICIENT_UNRESERVED_CASH", "OPTION_RESERVATION_REJECTED"),
        )

    reservation = SimulatedOptionReservationV2(
        decision_record_fingerprint=record_fingerprint,
        reservation_terms_fingerprint=terms_fingerprint,
        option_economics_result_fingerprint=option_terms.option_economics_result_fingerprint,
        candidate_identifier=candidate.identifier,
        option_contract_ticker=option_terms.option_contract_ticker,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        reserved_capital=option_terms.reserved_capital_dollars,
        max_loss_cash=option_terms.max_loss_cash_dollars,
        premium_at_risk=option_terms.premium_at_risk_dollars,
        signed_delta_equivalent_notional=option_terms.signed_delta_equivalent_notional_dollars,
        abs_delta_equivalent_notional=option_terms.abs_delta_equivalent_notional_dollars,
        reserved_utc=record.decision_created_utc,
    )
    state = account.state
    next_state = _build_state(
        previous=state,
        as_of_utc=record.decision_created_utc,
        cash=state.cash - reservation.reserved_capital,
        stock_reserved_capital=state.stock_reserved_capital,
        option_reserved_capital=state.option_reserved_capital + reservation.reserved_capital,
        stock_gross_notional=state.stock_gross_notional,
        option_signed_delta_equivalent_notional=(
            state.option_signed_delta_equivalent_notional
            + reservation.signed_delta_equivalent_notional
        ),
        option_abs_delta_equivalent_notional=(
            state.option_abs_delta_equivalent_notional
            + reservation.abs_delta_equivalent_notional
        ),
        option_max_loss_cash=state.option_max_loss_cash + reservation.max_loss_cash,
        option_premium_at_risk=state.option_premium_at_risk + reservation.premium_at_risk,
        stock_reservations=state.stock_reservations,
        option_reservations=state.option_reservations + (reservation,),
    )
    return _append_event(
        account=account,
        next_state=next_state,
        kind=SimulationAccountV2EventKind.RESERVE_OPTION,
        occurred_utc=record.decision_created_utc,
        decision_record_fingerprint=record_fingerprint,
        reservation_terms_fingerprint=terms_fingerprint,
        option_economics_result_fingerprint=option_terms.option_economics_result_fingerprint,
        candidate_identifier=candidate.identifier,
        option_contract_ticker=option_terms.option_contract_ticker,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        option_capital_delta=reservation.reserved_capital,
        option_signed_delta_equivalent_delta=reservation.signed_delta_equivalent_notional,
        option_abs_delta_equivalent_delta=reservation.abs_delta_equivalent_notional,
        option_max_loss_delta=reservation.max_loss_cash,
        option_premium_at_risk_delta=reservation.premium_at_risk,
        reason_codes=("LONG_OPTION_CAPITAL_RESERVED", "OPTION_EXPOSURE_RECORDED_SEPARATELY"),
    )


def release_stock_reservation_v2(
    account: SimulationAccountV2,
    *,
    decision_record_fingerprint: str,
    released_utc: datetime,
    reason_codes: tuple[str, ...] = ("STOCK_CAPITAL_RELEASED",),
) -> SimulationAccountV2Transition:
    _require_fingerprint(decision_record_fingerprint, label="stock release decision fingerprint")
    _require_aware(released_utc, label="stock release timestamp")
    if released_utc < account.state.as_of_utc:
        raise SimulationAccountStateV2Error("release timestamp cannot precede current account state")
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
            event.kind == SimulationAccountV2EventKind.RELEASE_STOCK
            and event.decision_record_fingerprint == decision_record_fingerprint
            for event in account.ledger.events
        )
        if already_released:
            return SimulationAccountV2Transition(
                account=account,
                event=None,
                idempotent_reuse=True,
                reason_codes=("RESERVATION_ALREADY_RELEASED",),
            )
        raise SimulationAccountStateV2Error("active stock reservation not found")
    if not reason_codes:
        raise SimulationAccountStateV2Error("stock release requires reason codes")
    state = account.state
    remaining = tuple(
        item
        for item in state.stock_reservations
        if item.decision_record_fingerprint != decision_record_fingerprint
    )
    next_state = _build_state(
        previous=state,
        as_of_utc=released_utc,
        cash=state.cash + reservation.reserved_capital,
        stock_reserved_capital=state.stock_reserved_capital - reservation.reserved_capital,
        option_reserved_capital=state.option_reserved_capital,
        stock_gross_notional=state.stock_gross_notional - reservation.gross_notional,
        option_signed_delta_equivalent_notional=state.option_signed_delta_equivalent_notional,
        option_abs_delta_equivalent_notional=state.option_abs_delta_equivalent_notional,
        option_max_loss_cash=state.option_max_loss_cash,
        option_premium_at_risk=state.option_premium_at_risk,
        stock_reservations=remaining,
        option_reservations=state.option_reservations,
    )
    return _append_event(
        account=account,
        next_state=next_state,
        kind=SimulationAccountV2EventKind.RELEASE_STOCK,
        occurred_utc=released_utc,
        decision_record_fingerprint=decision_record_fingerprint,
        candidate_identifier=reservation.candidate_identifier,
        instrument_id=reservation.instrument_id,
        ticker=reservation.ticker,
        direction=reservation.direction,
        stock_capital_delta=-reservation.reserved_capital,
        stock_gross_notional_delta=-reservation.gross_notional,
        reason_codes=reason_codes,
    )


def release_option_reservation_v2(
    account: SimulationAccountV2,
    *,
    decision_record_fingerprint: str,
    released_utc: datetime,
    reason_codes: tuple[str, ...] = ("LONG_OPTION_CAPITAL_RELEASED",),
) -> SimulationAccountV2Transition:
    _require_fingerprint(decision_record_fingerprint, label="option release decision fingerprint")
    _require_aware(released_utc, label="option release timestamp")
    if released_utc < account.state.as_of_utc:
        raise SimulationAccountStateV2Error("release timestamp cannot precede current account state")
    reservation = next(
        (
            item
            for item in account.state.option_reservations
            if item.decision_record_fingerprint == decision_record_fingerprint
        ),
        None,
    )
    if reservation is None:
        already_released = any(
            event.kind == SimulationAccountV2EventKind.RELEASE_OPTION
            and event.decision_record_fingerprint == decision_record_fingerprint
            for event in account.ledger.events
        )
        if already_released:
            return SimulationAccountV2Transition(
                account=account,
                event=None,
                idempotent_reuse=True,
                reason_codes=("RESERVATION_ALREADY_RELEASED",),
            )
        raise SimulationAccountStateV2Error("active option reservation not found")
    if not reason_codes:
        raise SimulationAccountStateV2Error("option release requires reason codes")
    state = account.state
    remaining = tuple(
        item
        for item in state.option_reservations
        if item.decision_record_fingerprint != decision_record_fingerprint
    )
    next_state = _build_state(
        previous=state,
        as_of_utc=released_utc,
        cash=state.cash + reservation.reserved_capital,
        stock_reserved_capital=state.stock_reserved_capital,
        option_reserved_capital=state.option_reserved_capital - reservation.reserved_capital,
        stock_gross_notional=state.stock_gross_notional,
        option_signed_delta_equivalent_notional=(
            state.option_signed_delta_equivalent_notional
            - reservation.signed_delta_equivalent_notional
        ),
        option_abs_delta_equivalent_notional=(
            state.option_abs_delta_equivalent_notional
            - reservation.abs_delta_equivalent_notional
        ),
        option_max_loss_cash=state.option_max_loss_cash - reservation.max_loss_cash,
        option_premium_at_risk=state.option_premium_at_risk - reservation.premium_at_risk,
        stock_reservations=state.stock_reservations,
        option_reservations=remaining,
    )
    return _append_event(
        account=account,
        next_state=next_state,
        kind=SimulationAccountV2EventKind.RELEASE_OPTION,
        occurred_utc=released_utc,
        decision_record_fingerprint=decision_record_fingerprint,
        reservation_terms_fingerprint=reservation.reservation_terms_fingerprint,
        option_economics_result_fingerprint=reservation.option_economics_result_fingerprint,
        candidate_identifier=reservation.candidate_identifier,
        option_contract_ticker=reservation.option_contract_ticker,
        instrument_id=reservation.instrument_id,
        ticker=reservation.ticker,
        direction=reservation.direction,
        option_capital_delta=-reservation.reserved_capital,
        option_signed_delta_equivalent_delta=-reservation.signed_delta_equivalent_notional,
        option_abs_delta_equivalent_delta=-reservation.abs_delta_equivalent_notional,
        option_max_loss_delta=-reservation.max_loss_cash,
        option_premium_at_risk_delta=-reservation.premium_at_risk,
        reason_codes=reason_codes,
    )


def apply_competing_decisions_v2(
    account: SimulationAccountV2,
    records: Sequence[SimulationDecisionRecord],
    *,
    option_terms_by_decision_fingerprint: Mapping[str, LongOptionReservationTerms] | None = None,
) -> SimulationCompetitionV2Result:
    terms_by_decision = option_terms_by_decision_fingerprint or {}
    ordered = tuple(
        sorted(records, key=lambda record: (record.decision_created_utc, record.record_fingerprint))
    )
    current = account
    transitions: list[SimulationAccountV2Transition] = []
    for record in ordered:
        transition = apply_simulation_decision_v2(
            current,
            record,
            option_terms=terms_by_decision.get(record.record_fingerprint),
        )
        current = transition.account
        transitions.append(transition)
    return SimulationCompetitionV2Result(
        account=current,
        ordered_decision_fingerprints=tuple(record.record_fingerprint for record in ordered),
        transitions=tuple(transitions),
    )


def replay_account_v2_ledger(ledger: SimulationAccountV2Ledger) -> SimulationAccountV2:
    account = initialize_simulation_account_v2(
        as_of_utc=ledger.initial_as_of_utc,
        equity=ledger.initial_equity,
    )
    if account.state.state_fingerprint != ledger.initial_state_fingerprint:
        raise SimulationAccountStateV2Error("ledger initial-state fingerprint mismatch")

    state = account.state
    for event in ledger.events:
        if state.state_fingerprint != event.before_state_fingerprint:
            raise SimulationAccountStateV2Error("ledger before-state fingerprint mismatch")
        if event.occurred_utc < state.as_of_utc:
            raise SimulationAccountStateV2Error("ledger event chronology mismatch")

        stock_reservations = list(state.stock_reservations)
        option_reservations = list(state.option_reservations)
        cash = state.cash
        stock_reserved = state.stock_reserved_capital
        option_reserved = state.option_reserved_capital
        stock_notional = state.stock_gross_notional
        option_signed = state.option_signed_delta_equivalent_notional
        option_abs = state.option_abs_delta_equivalent_notional
        option_max_loss = state.option_max_loss_cash
        option_premium = state.option_premium_at_risk

        if event.kind == SimulationAccountV2EventKind.RESERVE_STOCK:
            assert event.decision_record_fingerprint is not None
            assert event.candidate_identifier is not None
            assert event.instrument_id is not None
            assert event.ticker is not None
            assert event.direction is not None
            if any(
                item.decision_record_fingerprint == event.decision_record_fingerprint
                for item in stock_reservations + option_reservations
            ):
                raise SimulationAccountStateV2Error("ledger cannot reserve same decision twice")
            stock_reservations.append(
                SimulatedStockReservationV2(
                    decision_record_fingerprint=event.decision_record_fingerprint,
                    candidate_identifier=event.candidate_identifier,
                    instrument_id=event.instrument_id,
                    ticker=event.ticker,
                    direction=event.direction,
                    reserved_capital=event.stock_capital_delta,
                    gross_notional=event.stock_gross_notional_delta,
                    reserved_utc=event.occurred_utc,
                )
            )
            cash -= event.stock_capital_delta
            stock_reserved += event.stock_capital_delta
            stock_notional += event.stock_gross_notional_delta
        elif event.kind == SimulationAccountV2EventKind.RELEASE_STOCK:
            assert event.decision_record_fingerprint is not None
            reservation = next(
                (
                    item
                    for item in stock_reservations
                    if item.decision_record_fingerprint == event.decision_record_fingerprint
                ),
                None,
            )
            if reservation is None:
                raise SimulationAccountStateV2Error("ledger stock release has no active reservation")
            if not _same(event.stock_capital_delta, -reservation.reserved_capital):
                raise SimulationAccountStateV2Error("ledger stock release capital mismatch")
            if not _same(event.stock_gross_notional_delta, -reservation.gross_notional):
                raise SimulationAccountStateV2Error("ledger stock release notional mismatch")
            stock_reservations = [
                item
                for item in stock_reservations
                if item.decision_record_fingerprint != event.decision_record_fingerprint
            ]
            cash -= event.stock_capital_delta
            stock_reserved += event.stock_capital_delta
            stock_notional += event.stock_gross_notional_delta
        elif event.kind == SimulationAccountV2EventKind.RESERVE_OPTION:
            assert event.decision_record_fingerprint is not None
            assert event.reservation_terms_fingerprint is not None
            assert event.option_economics_result_fingerprint is not None
            assert event.candidate_identifier is not None
            assert event.option_contract_ticker is not None
            assert event.instrument_id is not None
            assert event.ticker is not None
            assert event.direction is not None
            if any(
                item.decision_record_fingerprint == event.decision_record_fingerprint
                for item in stock_reservations + option_reservations
            ):
                raise SimulationAccountStateV2Error("ledger cannot reserve same decision twice")
            option_reservations.append(
                SimulatedOptionReservationV2(
                    decision_record_fingerprint=event.decision_record_fingerprint,
                    reservation_terms_fingerprint=event.reservation_terms_fingerprint,
                    option_economics_result_fingerprint=event.option_economics_result_fingerprint,
                    candidate_identifier=event.candidate_identifier,
                    option_contract_ticker=event.option_contract_ticker,
                    instrument_id=event.instrument_id,
                    ticker=event.ticker,
                    direction=event.direction,
                    reserved_capital=event.option_capital_delta,
                    max_loss_cash=event.option_max_loss_delta,
                    premium_at_risk=event.option_premium_at_risk_delta,
                    signed_delta_equivalent_notional=event.option_signed_delta_equivalent_delta,
                    abs_delta_equivalent_notional=event.option_abs_delta_equivalent_delta,
                    reserved_utc=event.occurred_utc,
                )
            )
            cash -= event.option_capital_delta
            option_reserved += event.option_capital_delta
            option_signed += event.option_signed_delta_equivalent_delta
            option_abs += event.option_abs_delta_equivalent_delta
            option_max_loss += event.option_max_loss_delta
            option_premium += event.option_premium_at_risk_delta
        elif event.kind == SimulationAccountV2EventKind.RELEASE_OPTION:
            assert event.decision_record_fingerprint is not None
            reservation = next(
                (
                    item
                    for item in option_reservations
                    if item.decision_record_fingerprint == event.decision_record_fingerprint
                ),
                None,
            )
            if reservation is None:
                raise SimulationAccountStateV2Error("ledger option release has no active reservation")
            expected_pairs = (
                (event.option_capital_delta, -reservation.reserved_capital, "capital"),
                (
                    event.option_signed_delta_equivalent_delta,
                    -reservation.signed_delta_equivalent_notional,
                    "signed delta exposure",
                ),
                (
                    event.option_abs_delta_equivalent_delta,
                    -reservation.abs_delta_equivalent_notional,
                    "absolute delta exposure",
                ),
                (event.option_max_loss_delta, -reservation.max_loss_cash, "max loss"),
                (event.option_premium_at_risk_delta, -reservation.premium_at_risk, "premium"),
            )
            for actual, expected, label in expected_pairs:
                if not _same(actual, expected):
                    raise SimulationAccountStateV2Error(f"ledger option release {label} mismatch")
            if event.reservation_terms_fingerprint != reservation.reservation_terms_fingerprint:
                raise SimulationAccountStateV2Error("ledger option release terms lineage mismatch")
            if event.option_economics_result_fingerprint != reservation.option_economics_result_fingerprint:
                raise SimulationAccountStateV2Error("ledger option release economics lineage mismatch")
            option_reservations = [
                item
                for item in option_reservations
                if item.decision_record_fingerprint != event.decision_record_fingerprint
            ]
            cash -= event.option_capital_delta
            option_reserved += event.option_capital_delta
            option_signed += event.option_signed_delta_equivalent_delta
            option_abs += event.option_abs_delta_equivalent_delta
            option_max_loss += event.option_max_loss_delta
            option_premium += event.option_premium_at_risk_delta
        elif event.kind not in {
            SimulationAccountV2EventKind.ABSTAIN,
            SimulationAccountV2EventKind.REJECT_MISSING_OPTION_TERMS,
            SimulationAccountV2EventKind.REJECT_INSUFFICIENT_CAPITAL,
        }:
            raise SimulationAccountStateV2Error("unsupported ledger event kind")

        state = _build_state(
            previous=state,
            as_of_utc=event.occurred_utc,
            cash=cash,
            stock_reserved_capital=stock_reserved,
            option_reserved_capital=option_reserved,
            stock_gross_notional=stock_notional,
            option_signed_delta_equivalent_notional=option_signed,
            option_abs_delta_equivalent_notional=option_abs,
            option_max_loss_cash=option_max_loss,
            option_premium_at_risk=option_premium,
            stock_reservations=stock_reservations,
            option_reservations=option_reservations,
        )
        if state.state_fingerprint != event.after_state_fingerprint:
            raise SimulationAccountStateV2Error("ledger after-state fingerprint mismatch")

    return SimulationAccountV2(state=state, ledger=ledger)
