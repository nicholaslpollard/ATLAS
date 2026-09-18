from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from packages.execution.trade_expression import InstrumentKind, SelectionKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    economic_candidate_fingerprint,
)
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_entry_evidence_contract import (
    LIFECYCLE_ENTRY_FILL_CONTRACT,
    LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT,
    LIFECYCLE_FUNDING_TERMS_CONTRACT,
    LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_reservation_contract import (
    LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_reservation_state import (
    LifecycleReservationAccountV1,
    lifecycle_reservation_account_state_fingerprint,
    lifecycle_reservation_ledger_fingerprint,
)
from packages.simulation.option_reservation import (
    LongOptionReservationTerms,
    long_option_reservation_terms_fingerprint,
)
from packages.simulation.option_reservation_contract import (
    LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
)
from packages.simulation.simulated_fill import (
    SimulatedEntryFillInputs,
    simulated_reservation_fingerprint,
)


LIFECYCLE_ENTRY_FILL_CONTRACT_VERSION = str(
    LIFECYCLE_ENTRY_FILL_CONTRACT["contract_id"]
)
LIFECYCLE_FUNDING_TERMS_CONTRACT_VERSION = str(
    LIFECYCLE_FUNDING_TERMS_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class LifecycleEntryEvidenceError(ValueError):
    pass


class LifecycleFundingModel(StrEnum):
    CASH_ONLY_STOCK_LONG = "CASH_ONLY_STOCK_LONG"
    RESERVED_LONG_OPTION_DEBIT = "RESERVED_LONG_OPTION_DEBIT"


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
        raise LifecycleEntryEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise LifecycleEntryEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LifecycleEntryEvidenceError(
            f"{label} must be timezone-aware"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _validate_account(account: LifecycleReservationAccountV1) -> None:
    state = account.state
    if (
        state.contract_fingerprint
        != LIFECYCLE_RESERVATION_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise LifecycleEntryEvidenceError(
            "lifecycle reservation account contract fingerprint mismatch"
        )
    if (
        state.state_fingerprint
        != lifecycle_reservation_account_state_fingerprint(state)
    ):
        raise LifecycleEntryEvidenceError(
            "lifecycle reservation account state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != lifecycle_reservation_ledger_fingerprint(account.ledger)
    ):
        raise LifecycleEntryEvidenceError(
            "lifecycle reservation ledger fingerprint mismatch"
        )
    expected = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected != state.state_fingerprint:
        raise LifecycleEntryEvidenceError(
            "lifecycle reservation ledger does not terminate at current state"
        )


@dataclass(frozen=True)
class LifecycleEntryFillEvidenceV1:
    contract_version: str
    contract_fingerprint: str
    lifecycle_reservation_state_fingerprint: str
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
        if self.contract_version != LIFECYCLE_ENTRY_FILL_CONTRACT_VERSION:
            raise LifecycleEntryEvidenceError(
                "lifecycle entry-fill contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT
        ):
            raise LifecycleEntryEvidenceError(
                "lifecycle entry-fill contract fingerprint mismatch"
            )
        for label, value in (
            (
                "lifecycle reservation state",
                self.lifecycle_reservation_state_fingerprint,
            ),
            ("decision record", self.decision_record_fingerprint),
            ("active reservation", self.active_reservation_fingerprint),
            ("candidate", self.candidate_fingerprint),
            ("fill source", self.fill_source_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.filled_utc, label="lifecycle fill timestamp")
        if not self.fill_source_id.strip():
            raise LifecycleEntryEvidenceError(
                "lifecycle fill source id cannot be blank"
            )
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise LifecycleEntryEvidenceError(
                "lifecycle fill underlying identity cannot be blank"
            )
        if not self.candidate_identifier.strip():
            raise LifecycleEntryEvidenceError(
                "lifecycle fill candidate identifier cannot be blank"
            )
        positive = (
            self.quantity,
            self.fill_price_per_unit,
            self.contract_multiplier,
            self.gross_fill_notional_dollars,
            self.reserved_capital_dollars,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in positive):
            raise LifecycleEntryEvidenceError(
                "fill quantity, price, multiplier, notional, and reserve must be positive"
            )
        if (
            not math.isfinite(self.entry_fees_dollars)
            or self.entry_fees_dollars < 0.0
        ):
            raise LifecycleEntryEvidenceError(
                "entry fees must be finite and nonnegative"
            )
        expected_notional = (
            self.quantity
            * self.fill_price_per_unit
            * self.contract_multiplier
        )
        if not _same(
            self.gross_fill_notional_dollars,
            expected_notional,
        ):
            raise LifecycleEntryEvidenceError(
                "gross fill notional does not match quantity, price, and multiplier"
            )
        if not self.reason_codes:
            raise LifecycleEntryEvidenceError(
                "lifecycle entry-fill evidence requires reason codes"
            )
        if not self.descriptive_only:
            raise LifecycleEntryEvidenceError(
                "lifecycle entry-fill evidence must remain descriptive only"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES":
                raise LifecycleEntryEvidenceError(
                    "stock fill quantity unit must be SHARES"
                )
            if not _same(self.contract_multiplier, 1.0):
                raise LifecycleEntryEvidenceError(
                    "stock fill multiplier must equal one"
                )
            if (
                self.option_contract_ticker is not None
                or self.option_contract_type is not None
                or self.option_reservation_terms_fingerprint is not None
                or self.option_economics_result_fingerprint is not None
            ):
                raise LifecycleEntryEvidenceError(
                    "stock fill cannot carry option lineage"
                )
            if (
                self.cash_debit_dollars is not None
                or self.unspent_reserved_capital_dollars is not None
                or self.funding_semantics_resolved
            ):
                raise LifecycleEntryEvidenceError(
                    "stock fill cannot infer funding semantics"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS":
                raise LifecycleEntryEvidenceError(
                    "option fill quantity unit must be CONTRACTS"
                )
            if not _same(self.quantity, round(self.quantity)):
                raise LifecycleEntryEvidenceError(
                    "option fill quantity must be integral contracts"
                )
            if (
                not self.option_contract_ticker
                or self.option_contract_type not in {"call", "put"}
            ):
                raise LifecycleEntryEvidenceError(
                    "option fill requires call/put identity"
                )
            if (
                self.option_reservation_terms_fingerprint is None
                or self.option_economics_result_fingerprint is None
            ):
                raise LifecycleEntryEvidenceError(
                    "option fill requires reservation/economics lineage"
                )
            _require_fingerprint(
                self.option_reservation_terms_fingerprint,
                label="option reservation terms fingerprint",
            )
            _require_fingerprint(
                self.option_economics_result_fingerprint,
                label="option economics fingerprint",
            )
            if (
                self.cash_debit_dollars is None
                or self.unspent_reserved_capital_dollars is None
                or not self.funding_semantics_resolved
            ):
                raise LifecycleEntryEvidenceError(
                    "option fill requires resolved reserved debit"
                )
            if (
                self.cash_debit_dollars <= 0.0
                or self.unspent_reserved_capital_dollars < -_TOLERANCE
            ):
                raise LifecycleEntryEvidenceError(
                    "option debit or unspent reserve is invalid"
                )
            if not _same(
                self.cash_debit_dollars
                + self.unspent_reserved_capital_dollars,
                self.reserved_capital_dollars,
            ):
                raise LifecycleEntryEvidenceError(
                    "option debit plus unspent reserve must equal reserved capital"
                )
        else:
            raise LifecycleEntryEvidenceError(
                "unsupported lifecycle fill instrument kind"
            )

        forbidden = (
            self.account_mutation_authority,
            self.reservation_release_authority,
            self.open_position_authority,
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
            raise LifecycleEntryEvidenceError(
                "lifecycle entry-fill evidence cannot grant mutation, provider, "
                "broker, order, trading, promotion, or confluence authority"
            )

    @property
    def fill_fingerprint(self) -> str:
        return lifecycle_entry_fill_fingerprint(self)


@dataclass(frozen=True)
class LifecycleFundingTermsV1:
    contract_version: str
    contract_fingerprint: str
    lifecycle_reservation_state_fingerprint: str
    fill_fingerprint: str
    active_reservation_fingerprint: str
    decision_record_fingerprint: str
    candidate_fingerprint: str
    instrument_kind: InstrumentKind
    direction: DiscoveryDirection
    funding_model: LifecycleFundingModel

    required_cash_dollars: float
    reserved_capital_dollars: float
    supplemental_unreserved_cash_required_dollars: float
    unspent_reserved_capital_dollars: float
    projected_unreserved_cash_after_entry_dollars: float
    fully_funded: bool
    reason_codes: tuple[str, ...]

    borrowing_authority: bool = False
    account_mutation_authority: bool = False
    reservation_release_authority: bool = False
    open_position_authority: bool = False
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
        if self.contract_version != LIFECYCLE_FUNDING_TERMS_CONTRACT_VERSION:
            raise LifecycleEntryEvidenceError(
                "lifecycle funding contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT
        ):
            raise LifecycleEntryEvidenceError(
                "lifecycle funding contract fingerprint mismatch"
            )
        for label, value in (
            (
                "lifecycle reservation state",
                self.lifecycle_reservation_state_fingerprint,
            ),
            ("fill", self.fill_fingerprint),
            ("active reservation", self.active_reservation_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("candidate", self.candidate_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")

        values = (
            self.required_cash_dollars,
            self.reserved_capital_dollars,
            self.supplemental_unreserved_cash_required_dollars,
            self.unspent_reserved_capital_dollars,
            self.projected_unreserved_cash_after_entry_dollars,
        )
        if not all(math.isfinite(value) and value >= 0.0 for value in values):
            raise LifecycleEntryEvidenceError(
                "lifecycle funding amounts must be finite and nonnegative"
            )
        if not self.fully_funded:
            raise LifecycleEntryEvidenceError(
                "lifecycle funding terms must be fully funded"
            )
        if not self.reason_codes:
            raise LifecycleEntryEvidenceError(
                "lifecycle funding terms require reason codes"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.direction != DiscoveryDirection.BULLISH:
                raise LifecycleEntryEvidenceError(
                    "lifecycle stock funding v1 supports bullish stock long only"
                )
            if self.funding_model != LifecycleFundingModel.CASH_ONLY_STOCK_LONG:
                raise LifecycleEntryEvidenceError(
                    "lifecycle stock funding model mismatch"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.direction not in {
                DiscoveryDirection.BULLISH,
                DiscoveryDirection.BEARISH,
            }:
                raise LifecycleEntryEvidenceError(
                    "long-option lifecycle funding requires directional option"
                )
            if (
                self.funding_model
                != LifecycleFundingModel.RESERVED_LONG_OPTION_DEBIT
            ):
                raise LifecycleEntryEvidenceError(
                    "lifecycle option funding model mismatch"
                )
            if (
                self.supplemental_unreserved_cash_required_dollars
                > _TOLERANCE
            ):
                raise LifecycleEntryEvidenceError(
                    "long-option lifecycle funding cannot require supplemental cash"
                )
        else:
            raise LifecycleEntryEvidenceError(
                "unsupported lifecycle funding instrument kind"
            )

        forbidden = (
            self.borrowing_authority,
            self.account_mutation_authority,
            self.reservation_release_authority,
            self.open_position_authority,
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
            raise LifecycleEntryEvidenceError(
                "lifecycle funding terms cannot grant borrowing, mutation, provider, "
                "broker, order, trading, promotion, or confluence authority"
            )

    @property
    def terms_fingerprint(self) -> str:
        return lifecycle_funding_terms_fingerprint(self)


def lifecycle_entry_fill_fingerprint(
    fill: LifecycleEntryFillEvidenceV1,
) -> str:
    return _fingerprint_payload(fill)


def lifecycle_funding_terms_fingerprint(
    terms: LifecycleFundingTermsV1,
) -> str:
    return _fingerprint_payload(terms)


def _chosen_candidate(
    record: SimulationDecisionRecord,
    expected: InstrumentKind,
):
    decision = record.trade_expression_decision
    expected_selection = (
        SelectionKind.STOCK
        if expected == InstrumentKind.STOCK
        else SelectionKind.OPTION
    )
    if decision.selection_kind != expected_selection:
        raise LifecycleEntryEvidenceError(
            f"decision record did not select {expected.value.lower()}"
        )
    candidate = decision.chosen_candidate
    if candidate is None or candidate.kind != expected:
        raise LifecycleEntryEvidenceError(
            "selected decision is missing its expected candidate"
        )
    return candidate


def _stock_reservation(
    account: LifecycleReservationAccountV1,
    decision_record_fingerprint: str,
):
    matches = tuple(
        item
        for item in account.state.stock_reservations
        if item.decision_record_fingerprint == decision_record_fingerprint
    )
    if len(matches) != 1:
        raise LifecycleEntryEvidenceError(
            "exact active lifecycle stock reservation is required"
        )
    return matches[0]


def _option_reservation(
    account: LifecycleReservationAccountV1,
    decision_record_fingerprint: str,
):
    matches = tuple(
        item
        for item in account.state.option_reservations
        if item.decision_record_fingerprint == decision_record_fingerprint
    )
    if len(matches) != 1:
        raise LifecycleEntryEvidenceError(
            "exact active lifecycle option reservation is required"
        )
    return matches[0]


def build_lifecycle_entry_fill_evidence(
    *,
    account: LifecycleReservationAccountV1,
    record: SimulationDecisionRecord,
    inputs: SimulatedEntryFillInputs,
    option_terms: LongOptionReservationTerms | None = None,
) -> LifecycleEntryFillEvidenceV1:
    _validate_account(account)
    if (
        record.contract_fingerprint
        != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT
    ):
        raise LifecycleEntryEvidenceError(
            "decision record contract fingerprint mismatch"
        )
    if inputs.filled_utc < account.state.as_of_utc:
        raise LifecycleEntryEvidenceError(
            "fill timestamp cannot precede lifecycle reservation state"
        )

    decision = record.trade_expression_decision
    if decision.selection_kind == SelectionKind.ABSTAIN:
        raise LifecycleEntryEvidenceError(
            "abstention cannot produce lifecycle entry-fill evidence"
        )

    if decision.selection_kind == SelectionKind.STOCK:
        if option_terms is not None:
            raise LifecycleEntryEvidenceError(
                "stock fill cannot consume option reservation terms"
            )
        candidate = _chosen_candidate(record, InstrumentKind.STOCK)
        economics_candidate = record.stock_economics.candidate
        if economics_candidate is None:
            raise LifecycleEntryEvidenceError(
                "stock economics candidate is missing"
            )
        candidate_fp = economic_candidate_fingerprint(candidate)
        if (
            candidate_fp
            != economic_candidate_fingerprint(economics_candidate)
        ):
            raise LifecycleEntryEvidenceError(
                "stock candidate fingerprint lineage mismatch"
            )
        reservation = _stock_reservation(
            account,
            record.record_fingerprint,
        )
        if reservation.candidate_identifier != candidate.identifier:
            raise LifecycleEntryEvidenceError(
                "stock reservation candidate identifier mismatch"
            )
        if (
            reservation.instrument_id != record.forecast.instrument_id
            or reservation.ticker != record.forecast.ticker
            or reservation.direction != record.forecast.direction.value
        ):
            raise LifecycleEntryEvidenceError(
                "stock reservation identity lineage mismatch"
            )

        quantity = reservation.gross_notional / inputs.fill_price_per_unit
        gross_notional = quantity * inputs.fill_price_per_unit
        if not _same(gross_notional, reservation.gross_notional):
            raise LifecycleEntryEvidenceError(
                "stock fill notional must equal reserved economic notional"
            )
        return LifecycleEntryFillEvidenceV1(
            contract_version=LIFECYCLE_ENTRY_FILL_CONTRACT_VERSION,
            contract_fingerprint=LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT,
            lifecycle_reservation_state_fingerprint=(
                account.state.state_fingerprint
            ),
            decision_record_fingerprint=record.record_fingerprint,
            active_reservation_fingerprint=(
                simulated_reservation_fingerprint(reservation)
            ),
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
            reason_codes=(
                "EXACT_ACTIVE_LIFECYCLE_STOCK_RESERVATION_BOUND",
                "EXACT_STOCK_CANDIDATE_FINGERPRINT_BOUND",
                "EXPLICIT_FILL_SOURCE_BOUND",
                "COMPLETE_STOCK_ENTRY_NOTIONAL_MATERIALIZED",
                "STOCK_FUNDING_SEMANTICS_UNRESOLVED",
                "NO_ACCOUNT_OR_BROKER_MUTATION_AUTHORITY_GRANTED",
            ),
        )

    candidate = _chosen_candidate(record, InstrumentKind.OPTION)
    if option_terms is None:
        raise LifecycleEntryEvidenceError(
            "option fill requires exact long-option reservation terms"
        )
    if (
        option_terms.contract_fingerprint
        != LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT
    ):
        raise LifecycleEntryEvidenceError(
            "long-option reservation contract fingerprint mismatch"
        )
    terms_fp = long_option_reservation_terms_fingerprint(option_terms)
    candidate_fp = economic_candidate_fingerprint(candidate)
    reservation = _option_reservation(
        account,
        record.record_fingerprint,
    )
    if option_terms.decision_record_fingerprint != record.record_fingerprint:
        raise LifecycleEntryEvidenceError(
            "option terms decision lineage mismatch"
        )
    if option_terms.chosen_candidate_identifier != candidate.identifier:
        raise LifecycleEntryEvidenceError(
            "option terms candidate identifier mismatch"
        )
    if option_terms.chosen_candidate_fingerprint != candidate_fp:
        raise LifecycleEntryEvidenceError(
            "option terms candidate fingerprint mismatch"
        )
    if reservation.candidate_identifier != candidate.identifier:
        raise LifecycleEntryEvidenceError(
            "option reservation candidate identifier mismatch"
        )
    if reservation.reservation_terms_fingerprint != terms_fp:
        raise LifecycleEntryEvidenceError(
            "option reservation terms lineage mismatch"
        )
    if (
        reservation.option_economics_result_fingerprint
        != option_terms.option_economics_result_fingerprint
    ):
        raise LifecycleEntryEvidenceError(
            "option economics-result lineage mismatch"
        )
    if reservation.option_contract_ticker != option_terms.option_contract_ticker:
        raise LifecycleEntryEvidenceError(
            "option contract ticker lineage mismatch"
        )
    if (
        reservation.instrument_id != record.forecast.instrument_id
        or reservation.ticker != record.forecast.ticker
        or reservation.direction != record.forecast.direction.value
    ):
        raise LifecycleEntryEvidenceError(
            "option reservation identity lineage mismatch"
        )
    if not _same(
        reservation.reserved_capital,
        option_terms.reserved_capital_dollars,
    ):
        raise LifecycleEntryEvidenceError(
            "option reserved-capital lineage mismatch"
        )

    quantity = float(option_terms.contracts)
    multiplier = float(option_terms.contract_multiplier)
    premium_debit = (
        inputs.fill_price_per_unit * multiplier * quantity
    )
    if (
        premium_debit
        > option_terms.entry_cash_debit_dollars + _TOLERANCE
    ):
        raise LifecycleEntryEvidenceError(
            "option fill premium debit exceeds reserved ask debit"
        )
    if (
        inputs.explicit_entry_fees_dollars
        > option_terms.cash_fee_reserve_dollars + _TOLERANCE
    ):
        raise LifecycleEntryEvidenceError(
            "option entry fees exceed explicit fee reserve"
        )
    cash_debit = premium_debit + inputs.explicit_entry_fees_dollars
    if cash_debit > reservation.reserved_capital + _TOLERANCE:
        raise LifecycleEntryEvidenceError(
            "option fill cash debit exceeds reserved capital"
        )
    unspent = reservation.reserved_capital - cash_debit
    if unspent < 0.0 and abs(unspent) <= _TOLERANCE:
        unspent = 0.0

    return LifecycleEntryFillEvidenceV1(
        contract_version=LIFECYCLE_ENTRY_FILL_CONTRACT_VERSION,
        contract_fingerprint=LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT,
        lifecycle_reservation_state_fingerprint=account.state.state_fingerprint,
        decision_record_fingerprint=record.record_fingerprint,
        active_reservation_fingerprint=(
            simulated_reservation_fingerprint(reservation)
        ),
        candidate_fingerprint=candidate_fp,
        option_reservation_terms_fingerprint=terms_fp,
        option_economics_result_fingerprint=(
            option_terms.option_economics_result_fingerprint
        ),
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
        reason_codes=(
            "EXACT_ACTIVE_LIFECYCLE_OPTION_RESERVATION_BOUND",
            "EXACT_OPTION_RESERVATION_TERMS_BOUND",
            "EXACT_OPTION_CANDIDATE_FINGERPRINT_BOUND",
            "EXPLICIT_FILL_SOURCE_BOUND",
            "COMPLETE_OPTION_ENTRY_CONTRACT_COUNT_MATERIALIZED",
            "OPTION_PREMIUM_AND_ENTRY_FEES_WITHIN_RESERVED_BUCKET",
            "UNSPENT_OPTION_RESERVATION_RECORDED",
            "NO_ACCOUNT_OR_BROKER_MUTATION_AUTHORITY_GRANTED",
        ),
    )


def _validate_fill_and_reservation(
    *,
    account: LifecycleReservationAccountV1,
    fill: LifecycleEntryFillEvidenceV1,
):
    _validate_account(account)
    if fill.contract_fingerprint != LIFECYCLE_ENTRY_FILL_CONTRACT_FINGERPRINT:
        raise LifecycleEntryEvidenceError(
            "lifecycle entry-fill contract fingerprint mismatch"
        )
    if fill.fill_fingerprint != lifecycle_entry_fill_fingerprint(fill):
        raise LifecycleEntryEvidenceError(
            "lifecycle entry-fill fingerprint mismatch"
        )
    if (
        fill.lifecycle_reservation_state_fingerprint
        != account.state.state_fingerprint
    ):
        raise LifecycleEntryEvidenceError(
            "entry fill does not bind the current lifecycle reservation state"
        )
    reservation = (
        _stock_reservation(account, fill.decision_record_fingerprint)
        if fill.instrument_kind == InstrumentKind.STOCK
        else _option_reservation(account, fill.decision_record_fingerprint)
    )
    if (
        simulated_reservation_fingerprint(reservation)
        != fill.active_reservation_fingerprint
    ):
        raise LifecycleEntryEvidenceError(
            "lifecycle active reservation fingerprint mismatch"
        )
    if not _same(
        reservation.reserved_capital,
        fill.reserved_capital_dollars,
    ):
        raise LifecycleEntryEvidenceError(
            "lifecycle reserved-capital lineage mismatch"
        )
    return reservation


def build_lifecycle_funding_terms(
    *,
    account: LifecycleReservationAccountV1,
    fill: LifecycleEntryFillEvidenceV1,
) -> LifecycleFundingTermsV1:
    reservation = _validate_fill_and_reservation(
        account=account,
        fill=fill,
    )

    if fill.instrument_kind == InstrumentKind.STOCK:
        if fill.direction != DiscoveryDirection.BULLISH:
            raise LifecycleEntryEvidenceError(
                "stock short lifecycle funding is unsupported in v1"
            )
        if fill.funding_semantics_resolved:
            raise LifecycleEntryEvidenceError(
                "stock fill must arrive with unresolved funding semantics"
            )
        if not _same(
            reservation.gross_notional,
            fill.gross_fill_notional_dollars,
        ):
            raise LifecycleEntryEvidenceError(
                "stock reservation gross notional mismatch"
            )
        required = (
            fill.gross_fill_notional_dollars
            + fill.entry_fees_dollars
        )
        reserved = fill.reserved_capital_dollars
        supplemental = max(0.0, required - reserved)
        unspent = max(0.0, reserved - required)
        if (
            account.state.cash + _TOLERANCE < supplemental
        ):
            raise LifecycleEntryEvidenceError(
                "insufficient current unreserved cash for lifecycle stock long"
            )
        projected = account.state.cash - supplemental + unspent
        return LifecycleFundingTermsV1(
            contract_version=LIFECYCLE_FUNDING_TERMS_CONTRACT_VERSION,
            contract_fingerprint=(
                LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT
            ),
            lifecycle_reservation_state_fingerprint=(
                account.state.state_fingerprint
            ),
            fill_fingerprint=fill.fill_fingerprint,
            active_reservation_fingerprint=(
                fill.active_reservation_fingerprint
            ),
            decision_record_fingerprint=fill.decision_record_fingerprint,
            candidate_fingerprint=fill.candidate_fingerprint,
            instrument_kind=fill.instrument_kind,
            direction=fill.direction,
            funding_model=LifecycleFundingModel.CASH_ONLY_STOCK_LONG,
            required_cash_dollars=required,
            reserved_capital_dollars=reserved,
            supplemental_unreserved_cash_required_dollars=supplemental,
            unspent_reserved_capital_dollars=unspent,
            projected_unreserved_cash_after_entry_dollars=projected,
            fully_funded=True,
            reason_codes=(
                "EXACT_LIFECYCLE_STOCK_RESERVATION_AND_FILL_BOUND",
                "FULLY_CASH_FUNDED_STOCK_LONG",
                "CURRENT_UNRESERVED_CASH_ONLY",
                "NO_BORROWING_MARGIN_OR_SHORT_PROCEEDS_INFERRED",
                "PRIOR_REALIZED_HISTORY_NOT_RECOMPUTED",
            ),
        )

    if fill.instrument_kind == InstrumentKind.OPTION:
        if (
            not fill.funding_semantics_resolved
            or fill.cash_debit_dollars is None
            or fill.unspent_reserved_capital_dollars is None
        ):
            raise LifecycleEntryEvidenceError(
                "long-option lifecycle fill requires resolved reserved debit"
            )
        if (
            fill.option_reservation_terms_fingerprint
            != reservation.reservation_terms_fingerprint
        ):
            raise LifecycleEntryEvidenceError(
                "option reservation terms lineage mismatch"
            )
        if (
            fill.option_economics_result_fingerprint
            != reservation.option_economics_result_fingerprint
        ):
            raise LifecycleEntryEvidenceError(
                "option economics lineage mismatch"
            )
        required = fill.cash_debit_dollars
        reserved = fill.reserved_capital_dollars
        unspent = fill.unspent_reserved_capital_dollars
        if not _same(required + unspent, reserved):
            raise LifecycleEntryEvidenceError(
                "long-option lifecycle debit does not reconcile to reservation"
            )
        projected = account.state.cash + unspent
        return LifecycleFundingTermsV1(
            contract_version=LIFECYCLE_FUNDING_TERMS_CONTRACT_VERSION,
            contract_fingerprint=(
                LIFECYCLE_FUNDING_TERMS_CONTRACT_FINGERPRINT
            ),
            lifecycle_reservation_state_fingerprint=(
                account.state.state_fingerprint
            ),
            fill_fingerprint=fill.fill_fingerprint,
            active_reservation_fingerprint=(
                fill.active_reservation_fingerprint
            ),
            decision_record_fingerprint=fill.decision_record_fingerprint,
            candidate_fingerprint=fill.candidate_fingerprint,
            instrument_kind=fill.instrument_kind,
            direction=fill.direction,
            funding_model=(
                LifecycleFundingModel.RESERVED_LONG_OPTION_DEBIT
            ),
            required_cash_dollars=required,
            reserved_capital_dollars=reserved,
            supplemental_unreserved_cash_required_dollars=0.0,
            unspent_reserved_capital_dollars=unspent,
            projected_unreserved_cash_after_entry_dollars=projected,
            fully_funded=True,
            reason_codes=(
                "EXACT_LIFECYCLE_OPTION_RESERVATION_AND_FILL_BOUND",
                "EXACT_RESERVED_LONG_OPTION_DEBIT_REUSED",
                "UNSPENT_OPTION_RESERVATION_PRESERVED",
                "NO_SUPPLEMENTAL_CASH_OR_BORROWING_INFERRED",
                "PRIOR_REALIZED_HISTORY_NOT_RECOMPUTED",
            ),
        )

    raise LifecycleEntryEvidenceError(
        "unsupported lifecycle funding instrument kind"
    )
