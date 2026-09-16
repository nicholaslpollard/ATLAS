from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from packages.execution.trade_expression import InstrumentKind, SelectionKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2 import (
    SimulationAccountV2,
    SimulatedOptionReservationV2,
    SimulatedStockReservationV2,
)
from packages.simulation.account_state_v2_contract import (
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
from packages.simulation.simulated_fill_contract import (
    SIMULATED_ENTRY_FILL_CONTRACT,
    SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT,
)


SIMULATED_ENTRY_FILL_CONTRACT_VERSION = str(
    SIMULATED_ENTRY_FILL_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class SimulatedEntryFillError(ValueError):
    pass


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="json"))
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
        raise SimulatedEntryFillError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SimulatedEntryFillError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise SimulatedEntryFillError(f"{label} must be timezone-aware")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def simulated_reservation_fingerprint(
    reservation: SimulatedStockReservationV2 | SimulatedOptionReservationV2,
) -> str:
    return _fingerprint_payload(reservation)


@dataclass(frozen=True)
class SimulatedEntryFillInputs:
    """Explicit source-bound evidence for one complete simulated entry fill.

    The caller supplies only the fill price, timestamp, explicit entry fees, and the
    immutable source identity/fingerprint. Quantity comes from the accepted reservation
    semantics: stock quantity is the reserved economic notional divided by the supplied
    fill price; option quantity is the exact reserved contract count.
    """

    fill_source_id: str
    fill_source_fingerprint: str
    filled_utc: datetime
    fill_price_per_unit: float
    explicit_entry_fees_dollars: float = 0.0

    def __post_init__(self) -> None:
        if not self.fill_source_id.strip():
            raise SimulatedEntryFillError("fill source id cannot be blank")
        _require_fingerprint(
            self.fill_source_fingerprint,
            label="fill source fingerprint",
        )
        _require_aware(self.filled_utc, label="fill timestamp")
        if not math.isfinite(self.fill_price_per_unit) or self.fill_price_per_unit <= 0.0:
            raise SimulatedEntryFillError("fill price must be finite and positive")
        if (
            not math.isfinite(self.explicit_entry_fees_dollars)
            or self.explicit_entry_fees_dollars < 0.0
        ):
            raise SimulatedEntryFillError("entry fees must be finite and nonnegative")


@dataclass(frozen=True)
class SimulatedEntryFillEvidence:
    contract_version: str
    contract_fingerprint: str
    account_state_fingerprint: str
    decision_record_fingerprint: str
    active_reservation_fingerprint: str
    candidate_fingerprint: str
    option_reservation_terms_fingerprint: str | None
    option_economics_result_fingerprint: str | None

    instrument_kind: InstrumentKind
    instrument_id: str
    ticker: str
    direction: DiscoveryDirection
    candidate_identifier: str
    option_contract_ticker: str | None
    option_contract_type: str | None

    fill_source_id: str
    fill_source_fingerprint: str
    filled_utc: datetime
    quantity: float
    quantity_unit: str
    fill_price_per_unit: float
    contract_multiplier: float
    gross_fill_notional_dollars: float
    entry_fees_dollars: float
    reserved_capital_dollars: float
    cash_debit_dollars: float | None
    unspent_reserved_capital_dollars: float | None
    funding_semantics_resolved: bool

    reason_codes: tuple[str, ...]
    descriptive_only: bool = True
    account_mutation_authority: bool = False
    reservation_release_authority: bool = False
    open_position_authority: bool = False
    mark_to_market_authority: bool = False
    realized_pnl_authority: bool = False
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != SIMULATED_ENTRY_FILL_CONTRACT_VERSION:
            raise SimulatedEntryFillError("simulated fill contract version mismatch")
        if self.contract_fingerprint != SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT:
            raise SimulatedEntryFillError("simulated fill contract fingerprint mismatch")
        for label, value in (
            ("account state", self.account_state_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("active reservation", self.active_reservation_fingerprint),
            ("candidate", self.candidate_fingerprint),
            ("fill source", self.fill_source_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.filled_utc, label="fill timestamp")
        if not self.fill_source_id.strip():
            raise SimulatedEntryFillError("fill source id cannot be blank")
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise SimulatedEntryFillError("fill underlying identity cannot be blank")
        if not self.candidate_identifier.strip():
            raise SimulatedEntryFillError("fill candidate identifier cannot be blank")
        positive = (
            self.quantity,
            self.fill_price_per_unit,
            self.contract_multiplier,
            self.gross_fill_notional_dollars,
            self.reserved_capital_dollars,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in positive):
            raise SimulatedEntryFillError("fill quantity, price, multiplier, notional, and reserve must be positive")
        if not math.isfinite(self.entry_fees_dollars) or self.entry_fees_dollars < 0.0:
            raise SimulatedEntryFillError("fill entry fees must be finite and nonnegative")
        expected_notional = self.quantity * self.fill_price_per_unit * self.contract_multiplier
        if not _same(self.gross_fill_notional_dollars, expected_notional):
            raise SimulatedEntryFillError("gross fill notional does not match quantity, price, and multiplier")
        if not self.reason_codes:
            raise SimulatedEntryFillError("simulated fill evidence requires reason codes")
        if not self.descriptive_only:
            raise SimulatedEntryFillError("simulated fill evidence must remain descriptive only")

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES":
                raise SimulatedEntryFillError("stock fill quantity unit must be SHARES")
            if not _same(self.contract_multiplier, 1.0):
                raise SimulatedEntryFillError("stock fill multiplier must equal one")
            if self.option_contract_ticker is not None or self.option_contract_type is not None:
                raise SimulatedEntryFillError("stock fill cannot carry option contract identity")
            if self.option_reservation_terms_fingerprint is not None:
                raise SimulatedEntryFillError("stock fill cannot carry option reservation terms")
            if self.option_economics_result_fingerprint is not None:
                raise SimulatedEntryFillError("stock fill cannot carry option economics lineage")
            if self.cash_debit_dollars is not None or self.unspent_reserved_capital_dollars is not None:
                raise SimulatedEntryFillError("stock fill cannot infer cash funding semantics")
            if self.funding_semantics_resolved:
                raise SimulatedEntryFillError("stock fill funding semantics must remain unresolved")
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS":
                raise SimulatedEntryFillError("option fill quantity unit must be CONTRACTS")
            if not _same(self.quantity, round(self.quantity)):
                raise SimulatedEntryFillError("option fill contract quantity must be integral")
            if not self.option_contract_ticker or self.option_contract_type not in {"call", "put"}:
                raise SimulatedEntryFillError("option fill requires call/put contract identity")
            if self.option_reservation_terms_fingerprint is None:
                raise SimulatedEntryFillError("option fill requires reservation-terms fingerprint")
            if self.option_economics_result_fingerprint is None:
                raise SimulatedEntryFillError("option fill requires option-economics fingerprint")
            _require_fingerprint(
                self.option_reservation_terms_fingerprint,
                label="option reservation-terms fingerprint",
            )
            _require_fingerprint(
                self.option_economics_result_fingerprint,
                label="option economics-result fingerprint",
            )
            if self.cash_debit_dollars is None or self.unspent_reserved_capital_dollars is None:
                raise SimulatedEntryFillError("option fill requires explicit resolved cash debit")
            if not self.funding_semantics_resolved:
                raise SimulatedEntryFillError("option fill funding semantics must be resolved")
            if self.cash_debit_dollars <= 0.0 or self.unspent_reserved_capital_dollars < -_TOLERANCE:
                raise SimulatedEntryFillError("option cash debit/unspent reserve is invalid")
            if not _same(
                self.cash_debit_dollars + self.unspent_reserved_capital_dollars,
                self.reserved_capital_dollars,
            ):
                raise SimulatedEntryFillError("option cash debit plus unspent reserve must equal reserved capital")
        else:
            raise SimulatedEntryFillError("unsupported simulated fill instrument kind")

        forbidden = (
            self.account_mutation_authority,
            self.reservation_release_authority,
            self.open_position_authority,
            self.mark_to_market_authority,
            self.realized_pnl_authority,
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.broker_fill_authority,
            self.order_creation_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden):
            raise SimulatedEntryFillError("simulated fill evidence cannot grant mutation, broker, order, P&L, trading, promotion, or confluence authority")

    @property
    def fill_fingerprint(self) -> str:
        return simulated_entry_fill_fingerprint(self)


def simulated_entry_fill_fingerprint(fill: SimulatedEntryFillEvidence) -> str:
    return _fingerprint_payload(fill)


def _chosen_candidate(record: SimulationDecisionRecord, expected: InstrumentKind):
    decision = record.trade_expression_decision
    expected_selection = (
        SelectionKind.STOCK if expected == InstrumentKind.STOCK else SelectionKind.OPTION
    )
    if decision.selection_kind != expected_selection:
        raise SimulatedEntryFillError(f"decision record did not select {expected.value.lower()}")
    candidate = decision.chosen_candidate
    if candidate is None or candidate.kind != expected:
        raise SimulatedEntryFillError("selected decision is missing its expected candidate")
    return candidate


def _stock_reservation(
    account: SimulationAccountV2,
    decision_record_fingerprint: str,
) -> SimulatedStockReservationV2:
    matches = tuple(
        item
        for item in account.state.stock_reservations
        if item.decision_record_fingerprint == decision_record_fingerprint
    )
    if len(matches) != 1:
        raise SimulatedEntryFillError("exact active stock reservation is required")
    return matches[0]


def _option_reservation(
    account: SimulationAccountV2,
    decision_record_fingerprint: str,
) -> SimulatedOptionReservationV2:
    matches = tuple(
        item
        for item in account.state.option_reservations
        if item.decision_record_fingerprint == decision_record_fingerprint
    )
    if len(matches) != 1:
        raise SimulatedEntryFillError("exact active option reservation is required")
    return matches[0]


def build_simulated_entry_fill_evidence(
    *,
    account: SimulationAccountV2,
    record: SimulationDecisionRecord,
    inputs: SimulatedEntryFillInputs,
    option_terms: LongOptionReservationTerms | None = None,
) -> SimulatedEntryFillEvidence:
    if account.state.contract_fingerprint != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT:
        raise SimulatedEntryFillError("simulation account-state v2 fingerprint mismatch")
    if record.contract_fingerprint != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT:
        raise SimulatedEntryFillError("decision record contract fingerprint mismatch")
    if inputs.filled_utc < account.state.as_of_utc:
        raise SimulatedEntryFillError("fill timestamp cannot precede account state")

    decision = record.trade_expression_decision
    if decision.selection_kind == SelectionKind.ABSTAIN:
        raise SimulatedEntryFillError("abstention cannot produce simulated fill evidence")

    if decision.selection_kind == SelectionKind.STOCK:
        if option_terms is not None:
            raise SimulatedEntryFillError("stock fill cannot consume option reservation terms")
        candidate = _chosen_candidate(record, InstrumentKind.STOCK)
        economics_candidate = record.stock_economics.candidate
        if economics_candidate is None:
            raise SimulatedEntryFillError("stock economics candidate is missing")
        candidate_fp = economic_candidate_fingerprint(candidate)
        if candidate_fp != economic_candidate_fingerprint(economics_candidate):
            raise SimulatedEntryFillError("stock candidate fingerprint lineage mismatch")
        reservation = _stock_reservation(account, record.record_fingerprint)
        if reservation.candidate_identifier != candidate.identifier:
            raise SimulatedEntryFillError("stock reservation candidate identifier mismatch")
        if (
            reservation.instrument_id != record.forecast.instrument_id
            or reservation.ticker != record.forecast.ticker
            or reservation.direction != record.forecast.direction.value
        ):
            raise SimulatedEntryFillError("stock reservation identity lineage mismatch")

        quantity = reservation.gross_notional / inputs.fill_price_per_unit
        gross_notional = quantity * inputs.fill_price_per_unit
        if not _same(gross_notional, reservation.gross_notional):
            raise SimulatedEntryFillError("stock fill notional must equal reserved economic notional")
        reasons = (
            "EXACT_ACTIVE_STOCK_RESERVATION_BOUND",
            "EXACT_STOCK_CANDIDATE_FINGERPRINT_BOUND",
            "EXPLICIT_FILL_SOURCE_BOUND",
            "COMPLETE_STOCK_ENTRY_NOTIONAL_MATERIALIZED",
            "STOCK_FUNDING_AND_SHORT_PROCEEDS_SEMANTICS_UNRESOLVED",
            "NO_ACCOUNT_OR_BROKER_MUTATION_AUTHORITY_GRANTED",
        )
        return SimulatedEntryFillEvidence(
            contract_version=SIMULATED_ENTRY_FILL_CONTRACT_VERSION,
            contract_fingerprint=SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT,
            account_state_fingerprint=account.state.state_fingerprint,
            decision_record_fingerprint=record.record_fingerprint,
            active_reservation_fingerprint=simulated_reservation_fingerprint(reservation),
            candidate_fingerprint=candidate_fp,
            option_reservation_terms_fingerprint=None,
            option_economics_result_fingerprint=None,
            instrument_kind=InstrumentKind.STOCK,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction,
            candidate_identifier=candidate.identifier,
            option_contract_ticker=None,
            option_contract_type=None,
            fill_source_id=inputs.fill_source_id,
            fill_source_fingerprint=inputs.fill_source_fingerprint,
            filled_utc=inputs.filled_utc,
            quantity=quantity,
            quantity_unit="SHARES",
            fill_price_per_unit=inputs.fill_price_per_unit,
            contract_multiplier=1.0,
            gross_fill_notional_dollars=gross_notional,
            entry_fees_dollars=inputs.explicit_entry_fees_dollars,
            reserved_capital_dollars=reservation.reserved_capital,
            cash_debit_dollars=None,
            unspent_reserved_capital_dollars=None,
            funding_semantics_resolved=False,
            reason_codes=reasons,
        )

    candidate = _chosen_candidate(record, InstrumentKind.OPTION)
    if option_terms is None:
        raise SimulatedEntryFillError("option fill requires exact long-option reservation terms")
    if option_terms.contract_fingerprint != LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT:
        raise SimulatedEntryFillError("long-option reservation contract fingerprint mismatch")
    terms_fp = long_option_reservation_terms_fingerprint(option_terms)
    candidate_fp = economic_candidate_fingerprint(candidate)
    reservation = _option_reservation(account, record.record_fingerprint)
    if option_terms.decision_record_fingerprint != record.record_fingerprint:
        raise SimulatedEntryFillError("option terms decision lineage mismatch")
    if option_terms.chosen_candidate_identifier != candidate.identifier:
        raise SimulatedEntryFillError("option terms candidate identifier mismatch")
    if option_terms.chosen_candidate_fingerprint != candidate_fp:
        raise SimulatedEntryFillError("option terms candidate fingerprint mismatch")
    if reservation.candidate_identifier != candidate.identifier:
        raise SimulatedEntryFillError("option reservation candidate identifier mismatch")
    if reservation.reservation_terms_fingerprint != terms_fp:
        raise SimulatedEntryFillError("option reservation terms lineage mismatch")
    if reservation.option_economics_result_fingerprint != option_terms.option_economics_result_fingerprint:
        raise SimulatedEntryFillError("option economics-result lineage mismatch")
    if reservation.option_contract_ticker != option_terms.option_contract_ticker:
        raise SimulatedEntryFillError("option contract ticker lineage mismatch")
    if (
        reservation.instrument_id != record.forecast.instrument_id
        or reservation.ticker != record.forecast.ticker
        or reservation.direction != record.forecast.direction.value
    ):
        raise SimulatedEntryFillError("option reservation identity lineage mismatch")
    if not _same(reservation.reserved_capital, option_terms.reserved_capital_dollars):
        raise SimulatedEntryFillError("option reserved-capital lineage mismatch")

    quantity = float(option_terms.contracts)
    multiplier = float(option_terms.contract_multiplier)
    premium_debit = inputs.fill_price_per_unit * multiplier * quantity
    if premium_debit > option_terms.entry_cash_debit_dollars + _TOLERANCE:
        raise SimulatedEntryFillError("option fill premium debit exceeds reserved ask debit")
    if inputs.explicit_entry_fees_dollars > option_terms.cash_fee_reserve_dollars + _TOLERANCE:
        raise SimulatedEntryFillError("option entry fees exceed explicit fee reserve")
    cash_debit = premium_debit + inputs.explicit_entry_fees_dollars
    if cash_debit > reservation.reserved_capital + _TOLERANCE:
        raise SimulatedEntryFillError("option fill cash debit exceeds reserved capital")
    unspent = reservation.reserved_capital - cash_debit
    if unspent < 0.0 and abs(unspent) <= _TOLERANCE:
        unspent = 0.0

    reasons = (
        "EXACT_ACTIVE_OPTION_RESERVATION_BOUND",
        "EXACT_OPTION_RESERVATION_TERMS_BOUND",
        "EXACT_OPTION_CANDIDATE_FINGERPRINT_BOUND",
        "EXPLICIT_FILL_SOURCE_BOUND",
        "COMPLETE_OPTION_ENTRY_CONTRACT_COUNT_MATERIALIZED",
        "OPTION_PREMIUM_AND_ENTRY_FEES_WITHIN_SEPARATE_RESERVED_BUCKETS",
        "UNSPENT_OPTION_RESERVATION_RECORDED",
        "NO_ACCOUNT_OR_BROKER_MUTATION_AUTHORITY_GRANTED",
    )
    return SimulatedEntryFillEvidence(
        contract_version=SIMULATED_ENTRY_FILL_CONTRACT_VERSION,
        contract_fingerprint=SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT,
        account_state_fingerprint=account.state.state_fingerprint,
        decision_record_fingerprint=record.record_fingerprint,
        active_reservation_fingerprint=simulated_reservation_fingerprint(reservation),
        candidate_fingerprint=candidate_fp,
        option_reservation_terms_fingerprint=terms_fp,
        option_economics_result_fingerprint=option_terms.option_economics_result_fingerprint,
        instrument_kind=InstrumentKind.OPTION,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction,
        candidate_identifier=candidate.identifier,
        option_contract_ticker=option_terms.option_contract_ticker,
        option_contract_type=option_terms.option_contract_type,
        fill_source_id=inputs.fill_source_id,
        fill_source_fingerprint=inputs.fill_source_fingerprint,
        filled_utc=inputs.filled_utc,
        quantity=quantity,
        quantity_unit="CONTRACTS",
        fill_price_per_unit=inputs.fill_price_per_unit,
        contract_multiplier=multiplier,
        gross_fill_notional_dollars=premium_debit,
        entry_fees_dollars=inputs.explicit_entry_fees_dollars,
        reserved_capital_dollars=reservation.reserved_capital,
        cash_debit_dollars=cash_debit,
        unspent_reserved_capital_dollars=unspent,
        funding_semantics_resolved=True,
        reason_codes=reasons,
    )
