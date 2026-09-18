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
from packages.simulation.option_reservation import (
    LongOptionReservationTerms,
    long_option_reservation_terms_fingerprint,
)
from packages.simulation.option_reservation_contract import (
    LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_entry_evidence_contract import (
    RECURRENT_ENTRY_FILL_CONTRACT,
    RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT,
    RECURRENT_FUNDING_TERMS_CONTRACT,
    RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    recurrent_lifecycle_account_state_fingerprint,
)
from packages.simulation.simulated_fill import (
    SimulatedEntryFillInputs,
    simulated_reservation_fingerprint,
)


RECURRENT_ENTRY_FILL_CONTRACT_VERSION = str(
    RECURRENT_ENTRY_FILL_CONTRACT["contract_id"]
)
RECURRENT_FUNDING_TERMS_CONTRACT_VERSION = str(
    RECURRENT_FUNDING_TERMS_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class RecurrentEntryEvidenceError(ValueError):
    pass


class RecurrentFundingModel(StrEnum):
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
        raise RecurrentEntryEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise RecurrentEntryEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentEntryEvidenceError(
            f"{label} must be timezone-aware"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _validate_account(account: RecurrentLifecycleAccountV1) -> None:
    if (
        account.state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentEntryEvidenceError(
            "recurrent lifecycle account contract fingerprint mismatch"
        )
    if (
        account.state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(account.state)
    ):
        raise RecurrentEntryEvidenceError(
            "recurrent lifecycle account state fingerprint mismatch"
        )


@dataclass(frozen=True)
class RecurrentEntryFillEvidenceV1:
    contract_version: str
    contract_fingerprint: str
    recurrent_state_fingerprint: str
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
        if self.contract_version != RECURRENT_ENTRY_FILL_CONTRACT_VERSION:
            raise RecurrentEntryEvidenceError(
                "recurrent entry-fill contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT
        ):
            raise RecurrentEntryEvidenceError(
                "recurrent entry-fill contract fingerprint mismatch"
            )
        for label, value in (
            ("recurrent state", self.recurrent_state_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("active reservation", self.active_reservation_fingerprint),
            ("candidate", self.candidate_fingerprint),
            ("fill source", self.fill_source_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_aware(self.filled_utc, label="recurrent fill timestamp")
        if not self.fill_source_id.strip():
            raise RecurrentEntryEvidenceError(
                "recurrent fill source id cannot be blank"
            )
        if (
            not self.instrument_id.strip()
            or not self.ticker.strip()
            or not self.candidate_identifier.strip()
        ):
            raise RecurrentEntryEvidenceError(
                "recurrent fill identity cannot be blank"
            )
        for label, value in (
            ("quantity", self.quantity),
            ("fill price", self.fill_price_per_unit),
            ("contract multiplier", self.contract_multiplier),
            ("gross fill notional", self.gross_fill_notional_dollars),
            ("reserved capital", self.reserved_capital_dollars),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise RecurrentEntryEvidenceError(
                    f"{label} must be finite and positive"
                )
        if (
            not math.isfinite(self.entry_fees_dollars)
            or self.entry_fees_dollars < 0.0
        ):
            raise RecurrentEntryEvidenceError(
                "entry fees must be finite and nonnegative"
            )
        if not _same(
            self.gross_fill_notional_dollars,
            self.quantity
            * self.fill_price_per_unit
            * self.contract_multiplier,
        ):
            raise RecurrentEntryEvidenceError(
                "gross fill notional mismatch"
            )
        if not self.reason_codes:
            raise RecurrentEntryEvidenceError(
                "recurrent entry-fill evidence requires reason codes"
            )
        if not self.descriptive_only:
            raise RecurrentEntryEvidenceError(
                "recurrent entry-fill evidence must remain descriptive only"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES":
                raise RecurrentEntryEvidenceError(
                    "stock recurrent fill quantity unit must be SHARES"
                )
            if not _same(self.contract_multiplier, 1.0):
                raise RecurrentEntryEvidenceError(
                    "stock recurrent fill multiplier must equal one"
                )
            if (
                self.option_contract_ticker is not None
                or self.option_contract_type is not None
                or self.option_reservation_terms_fingerprint is not None
                or self.option_economics_result_fingerprint is not None
            ):
                raise RecurrentEntryEvidenceError(
                    "stock recurrent fill cannot carry option lineage"
                )
            if (
                self.cash_debit_dollars is not None
                or self.unspent_reserved_capital_dollars is not None
                or self.funding_semantics_resolved
            ):
                raise RecurrentEntryEvidenceError(
                    "stock recurrent fill cannot infer funding semantics"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS":
                raise RecurrentEntryEvidenceError(
                    "option recurrent fill quantity unit must be CONTRACTS"
                )
            if not _same(self.quantity, round(self.quantity)):
                raise RecurrentEntryEvidenceError(
                    "option recurrent fill quantity must be integral"
                )
            if (
                not self.option_contract_ticker
                or self.option_contract_type not in {"call", "put"}
                or self.option_reservation_terms_fingerprint is None
                or self.option_economics_result_fingerprint is None
            ):
                raise RecurrentEntryEvidenceError(
                    "option recurrent fill requires complete option lineage"
                )
            if (
                self.cash_debit_dollars is None
                or self.unspent_reserved_capital_dollars is None
                or not self.funding_semantics_resolved
            ):
                raise RecurrentEntryEvidenceError(
                    "option recurrent fill requires resolved reserved debit"
                )
            if (
                self.cash_debit_dollars <= 0.0
                or self.unspent_reserved_capital_dollars < -_TOLERANCE
            ):
                raise RecurrentEntryEvidenceError(
                    "option recurrent debit/unspent reserve is invalid"
                )
            if not _same(
                self.cash_debit_dollars
                + self.unspent_reserved_capital_dollars,
                self.reserved_capital_dollars,
            ):
                raise RecurrentEntryEvidenceError(
                    "option debit plus unspent reserve must equal reserved capital"
                )
        else:
            raise RecurrentEntryEvidenceError(
                "unsupported recurrent fill instrument kind"
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
            raise RecurrentEntryEvidenceError(
                "recurrent entry-fill evidence cannot grant mutation, provider, "
                "broker, order, trading, promotion, or confluence authority"
            )

    @property
    def fill_fingerprint(self) -> str:
        return recurrent_entry_fill_fingerprint(self)


@dataclass(frozen=True)
class RecurrentFundingTermsV1:
    contract_version: str
    contract_fingerprint: str
    recurrent_state_fingerprint: str
    fill_fingerprint: str
    active_reservation_fingerprint: str
    decision_record_fingerprint: str
    candidate_fingerprint: str
    instrument_kind: InstrumentKind
    direction: DiscoveryDirection
    funding_model: RecurrentFundingModel

    required_cash_dollars: float
    reserved_capital_dollars: float
    supplemental_unreserved_cash_required_dollars: float
    unspent_reserved_capital_dollars: float
    projected_unreserved_cash_after_entry_dollars: float
    fully_funded: bool
    reason_codes: tuple[str, ...]

    descriptive_only: bool = True
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
        if self.contract_version != RECURRENT_FUNDING_TERMS_CONTRACT_VERSION:
            raise RecurrentEntryEvidenceError(
                "recurrent funding contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT
        ):
            raise RecurrentEntryEvidenceError(
                "recurrent funding contract fingerprint mismatch"
            )
        for label, value in (
            ("recurrent state", self.recurrent_state_fingerprint),
            ("fill", self.fill_fingerprint),
            ("active reservation", self.active_reservation_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("candidate", self.candidate_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        for label, value in (
            ("required cash", self.required_cash_dollars),
            ("reserved capital", self.reserved_capital_dollars),
            (
                "supplemental cash",
                self.supplemental_unreserved_cash_required_dollars,
            ),
            ("unspent reserve", self.unspent_reserved_capital_dollars),
            (
                "projected unreserved cash",
                self.projected_unreserved_cash_after_entry_dollars,
            ),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise RecurrentEntryEvidenceError(
                    f"{label} must be finite and nonnegative"
                )
        if not self.fully_funded:
            raise RecurrentEntryEvidenceError(
                "recurrent funding terms must be fully funded"
            )
        if not self.reason_codes:
            raise RecurrentEntryEvidenceError(
                "recurrent funding terms require reason codes"
            )
        if not self.descriptive_only:
            raise RecurrentEntryEvidenceError(
                "recurrent funding terms must remain descriptive only"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.direction != DiscoveryDirection.BULLISH:
                raise RecurrentEntryEvidenceError(
                    "recurrent stock funding v1 supports bullish long only"
                )
            if (
                self.funding_model
                != RecurrentFundingModel.CASH_ONLY_STOCK_LONG
            ):
                raise RecurrentEntryEvidenceError(
                    "recurrent stock funding model mismatch"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if (
                self.funding_model
                != RecurrentFundingModel.RESERVED_LONG_OPTION_DEBIT
            ):
                raise RecurrentEntryEvidenceError(
                    "recurrent option funding model mismatch"
                )
            if (
                self.supplemental_unreserved_cash_required_dollars
                > _TOLERANCE
            ):
                raise RecurrentEntryEvidenceError(
                    "long-option recurrent funding cannot require supplemental cash"
                )
        else:
            raise RecurrentEntryEvidenceError(
                "unsupported recurrent funding instrument kind"
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
            raise RecurrentEntryEvidenceError(
                "recurrent funding terms cannot grant borrowing, mutation, provider, "
                "broker, order, trading, promotion, or confluence authority"
            )

    @property
    def terms_fingerprint(self) -> str:
        return recurrent_funding_terms_fingerprint(self)


def recurrent_entry_fill_fingerprint(
    fill: RecurrentEntryFillEvidenceV1,
) -> str:
    return _fingerprint_payload(fill)


def recurrent_funding_terms_fingerprint(
    terms: RecurrentFundingTermsV1,
) -> str:
    return _fingerprint_payload(terms)


def _stock_reservation(
    account: RecurrentLifecycleAccountV1,
    decision_record_fingerprint: str,
):
    matches = tuple(
        item
        for item in account.state.stock_reservations
        if item.decision_record_fingerprint == decision_record_fingerprint
    )
    if len(matches) != 1:
        raise RecurrentEntryEvidenceError(
            "exact active recurrent stock reservation is required"
        )
    return matches[0]


def _option_reservation(
    account: RecurrentLifecycleAccountV1,
    decision_record_fingerprint: str,
):
    matches = tuple(
        item
        for item in account.state.option_reservations
        if item.decision_record_fingerprint == decision_record_fingerprint
    )
    if len(matches) != 1:
        raise RecurrentEntryEvidenceError(
            "exact active recurrent option reservation is required"
        )
    return matches[0]


def _candidate(
    record: SimulationDecisionRecord,
    expected: InstrumentKind,
):
    selection = (
        SelectionKind.STOCK
        if expected == InstrumentKind.STOCK
        else SelectionKind.OPTION
    )
    decision = record.trade_expression_decision
    if decision.selection_kind != selection:
        raise RecurrentEntryEvidenceError(
            "decision selection kind does not match requested fill"
        )
    candidate = decision.chosen_candidate
    if candidate is None or candidate.kind != expected:
        raise RecurrentEntryEvidenceError(
            "decision is missing expected economic candidate"
        )
    return candidate


def build_recurrent_entry_fill_evidence(
    *,
    account: RecurrentLifecycleAccountV1,
    record: SimulationDecisionRecord,
    inputs: SimulatedEntryFillInputs,
    option_terms: LongOptionReservationTerms | None = None,
) -> RecurrentEntryFillEvidenceV1:
    _validate_account(account)
    if (
        record.contract_fingerprint
        != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT
    ):
        raise RecurrentEntryEvidenceError(
            "decision-record contract fingerprint mismatch"
        )
    if inputs.filled_utc < account.state.as_of_utc:
        raise RecurrentEntryEvidenceError(
            "fill timestamp cannot precede current recurrent account state"
        )

    if record.trade_expression_decision.selection_kind == SelectionKind.STOCK:
        if option_terms is not None:
            raise RecurrentEntryEvidenceError(
                "stock fill cannot consume option reservation terms"
            )
        candidate = _candidate(record, InstrumentKind.STOCK)
        stock_candidate = record.stock_economics.candidate
        candidate_fp = economic_candidate_fingerprint(candidate)
        if (
            candidate.identifier != stock_candidate.identifier
            or candidate_fp != economic_candidate_fingerprint(stock_candidate)
        ):
            raise RecurrentEntryEvidenceError(
                "stock economic candidate lineage mismatch"
            )
        reservation = _stock_reservation(
            account,
            record.record_fingerprint,
        )
        if (
            reservation.candidate_identifier != candidate.identifier
            or reservation.instrument_id != record.forecast.instrument_id
            or reservation.ticker != record.forecast.ticker
            or reservation.direction != record.forecast.direction.value
        ):
            raise RecurrentEntryEvidenceError(
                "recurrent stock reservation lineage mismatch"
            )
        quantity = reservation.gross_notional / inputs.fill_price_per_unit
        gross = quantity * inputs.fill_price_per_unit
        if not _same(gross, reservation.gross_notional):
            raise RecurrentEntryEvidenceError(
                "stock fill notional must equal reserved economic notional"
            )
        return RecurrentEntryFillEvidenceV1(
            contract_version=RECURRENT_ENTRY_FILL_CONTRACT_VERSION,
            contract_fingerprint=RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT,
            recurrent_state_fingerprint=account.state.state_fingerprint,
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
            gross_fill_notional_dollars=gross,
            entry_fees_dollars=inputs.explicit_entry_fees_dollars,
            reserved_capital_dollars=reservation.reserved_capital,
            cash_debit_dollars=None,
            unspent_reserved_capital_dollars=None,
            funding_semantics_resolved=False,
            reason_codes=(
                "EXACT_ACTIVE_RECURRENT_STOCK_RESERVATION_BOUND",
                "EXACT_STOCK_CANDIDATE_FINGERPRINT_BOUND",
                "EXPLICIT_FILL_SOURCE_BOUND",
                "COMPLETE_STOCK_ENTRY_NOTIONAL_MATERIALIZED",
                "STOCK_FUNDING_SEMANTICS_UNRESOLVED",
            ),
        )

    candidate = _candidate(record, InstrumentKind.OPTION)
    if option_terms is None:
        raise RecurrentEntryEvidenceError(
            "option fill requires exact long-option reservation terms"
        )
    if (
        option_terms.contract_fingerprint
        != LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT
    ):
        raise RecurrentEntryEvidenceError(
            "long-option reservation contract fingerprint mismatch"
        )
    terms_fp = long_option_reservation_terms_fingerprint(option_terms)
    candidate_fp = economic_candidate_fingerprint(candidate)
    reservation = _option_reservation(
        account,
        record.record_fingerprint,
    )
    if (
        option_terms.decision_record_fingerprint != record.record_fingerprint
        or option_terms.chosen_candidate_identifier != candidate.identifier
        or option_terms.chosen_candidate_fingerprint != candidate_fp
    ):
        raise RecurrentEntryEvidenceError(
            "option terms decision/candidate lineage mismatch"
        )
    if (
        reservation.candidate_identifier != candidate.identifier
        or reservation.reservation_terms_fingerprint != terms_fp
        or reservation.option_economics_result_fingerprint
        != option_terms.option_economics_result_fingerprint
        or reservation.option_contract_ticker
        != option_terms.option_contract_ticker
    ):
        raise RecurrentEntryEvidenceError(
            "recurrent option reservation lineage mismatch"
        )
    if (
        reservation.instrument_id != record.forecast.instrument_id
        or reservation.ticker != record.forecast.ticker
        or reservation.direction != record.forecast.direction.value
    ):
        raise RecurrentEntryEvidenceError(
            "recurrent option underlying lineage mismatch"
        )

    quantity = float(option_terms.contracts)
    multiplier = float(option_terms.contract_multiplier)
    premium_debit = inputs.fill_price_per_unit * multiplier * quantity
    if premium_debit > option_terms.entry_cash_debit_dollars + _TOLERANCE:
        raise RecurrentEntryEvidenceError(
            "option fill premium exceeds reserved ask debit"
        )
    if (
        inputs.explicit_entry_fees_dollars
        > option_terms.cash_fee_reserve_dollars + _TOLERANCE
    ):
        raise RecurrentEntryEvidenceError(
            "option entry fees exceed reserved fee bucket"
        )
    cash_debit = premium_debit + inputs.explicit_entry_fees_dollars
    if cash_debit > reservation.reserved_capital + _TOLERANCE:
        raise RecurrentEntryEvidenceError(
            "option cash debit exceeds reserved capital"
        )
    unspent = reservation.reserved_capital - cash_debit
    if unspent < 0.0 and abs(unspent) <= _TOLERANCE:
        unspent = 0.0

    return RecurrentEntryFillEvidenceV1(
        contract_version=RECURRENT_ENTRY_FILL_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT,
        recurrent_state_fingerprint=account.state.state_fingerprint,
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
            "EXACT_ACTIVE_RECURRENT_OPTION_RESERVATION_BOUND",
            "EXACT_OPTION_RESERVATION_TERMS_BOUND",
            "EXPLICIT_FILL_SOURCE_BOUND",
            "COMPLETE_OPTION_ENTRY_CONTRACT_COUNT_MATERIALIZED",
            "OPTION_PREMIUM_AND_ENTRY_FEES_WITHIN_RESERVED_BUCKET",
            "UNSPENT_OPTION_RESERVATION_RECORDED",
        ),
    )


def build_recurrent_funding_terms(
    *,
    account: RecurrentLifecycleAccountV1,
    fill: RecurrentEntryFillEvidenceV1,
) -> RecurrentFundingTermsV1:
    _validate_account(account)
    if fill.contract_fingerprint != RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT:
        raise RecurrentEntryEvidenceError(
            "recurrent entry-fill contract fingerprint mismatch"
        )
    if fill.fill_fingerprint != recurrent_entry_fill_fingerprint(fill):
        raise RecurrentEntryEvidenceError(
            "recurrent entry-fill fingerprint mismatch"
        )
    if fill.recurrent_state_fingerprint != account.state.state_fingerprint:
        raise RecurrentEntryEvidenceError(
            "entry fill does not bind current recurrent account state"
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
        raise RecurrentEntryEvidenceError(
            "active recurrent reservation fingerprint mismatch"
        )

    if fill.instrument_kind == InstrumentKind.STOCK:
        if fill.direction != DiscoveryDirection.BULLISH:
            raise RecurrentEntryEvidenceError(
                "recurrent stock funding v1 supports bullish long only"
            )
        if fill.funding_semantics_resolved:
            raise RecurrentEntryEvidenceError(
                "stock fill must arrive with unresolved funding semantics"
            )
        required = fill.gross_fill_notional_dollars + fill.entry_fees_dollars
        reserved = fill.reserved_capital_dollars
        supplemental = max(0.0, required - reserved)
        unspent = max(0.0, reserved - required)
        if account.state.cash + _TOLERANCE < supplemental:
            raise RecurrentEntryEvidenceError(
                "insufficient current recurrent cash for stock funding"
            )
        projected = account.state.cash - supplemental + unspent
        return RecurrentFundingTermsV1(
            contract_version=RECURRENT_FUNDING_TERMS_CONTRACT_VERSION,
            contract_fingerprint=RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT,
            recurrent_state_fingerprint=account.state.state_fingerprint,
            fill_fingerprint=fill.fill_fingerprint,
            active_reservation_fingerprint=fill.active_reservation_fingerprint,
            decision_record_fingerprint=fill.decision_record_fingerprint,
            candidate_fingerprint=fill.candidate_fingerprint,
            instrument_kind=fill.instrument_kind,
            direction=fill.direction,
            funding_model=RecurrentFundingModel.CASH_ONLY_STOCK_LONG,
            required_cash_dollars=required,
            reserved_capital_dollars=reserved,
            supplemental_unreserved_cash_required_dollars=supplemental,
            unspent_reserved_capital_dollars=unspent,
            projected_unreserved_cash_after_entry_dollars=projected,
            fully_funded=True,
            reason_codes=(
                "EXACT_RECURRENT_STOCK_RESERVATION_AND_FILL_BOUND",
                "FULLY_CASH_FUNDED_STOCK_LONG",
                "CURRENT_RECURRENT_UNRESERVED_CASH_ONLY",
                "NO_BORROWING_MARGIN_OR_SHORT_PROCEEDS_INFERRED",
            ),
        )

    if (
        fill.cash_debit_dollars is None
        or fill.unspent_reserved_capital_dollars is None
        or not fill.funding_semantics_resolved
    ):
        raise RecurrentEntryEvidenceError(
            "recurrent option fill requires resolved reserved debit"
        )
    if (
        fill.option_reservation_terms_fingerprint
        != reservation.reservation_terms_fingerprint
        or fill.option_economics_result_fingerprint
        != reservation.option_economics_result_fingerprint
    ):
        raise RecurrentEntryEvidenceError(
            "recurrent option funding reservation lineage mismatch"
        )
    required = fill.cash_debit_dollars
    reserved = fill.reserved_capital_dollars
    unspent = fill.unspent_reserved_capital_dollars
    if not _same(required + unspent, reserved):
        raise RecurrentEntryEvidenceError(
            "recurrent option debit does not reconcile to reservation"
        )
    return RecurrentFundingTermsV1(
        contract_version=RECURRENT_FUNDING_TERMS_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT,
        recurrent_state_fingerprint=account.state.state_fingerprint,
        fill_fingerprint=fill.fill_fingerprint,
        active_reservation_fingerprint=fill.active_reservation_fingerprint,
        decision_record_fingerprint=fill.decision_record_fingerprint,
        candidate_fingerprint=fill.candidate_fingerprint,
        instrument_kind=fill.instrument_kind,
        direction=fill.direction,
        funding_model=RecurrentFundingModel.RESERVED_LONG_OPTION_DEBIT,
        required_cash_dollars=required,
        reserved_capital_dollars=reserved,
        supplemental_unreserved_cash_required_dollars=0.0,
        unspent_reserved_capital_dollars=unspent,
        projected_unreserved_cash_after_entry_dollars=(
            account.state.cash + unspent
        ),
        fully_funded=True,
        reason_codes=(
            "EXACT_RECURRENT_OPTION_RESERVATION_AND_FILL_BOUND",
            "EXACT_RESERVED_LONG_OPTION_DEBIT_REUSED",
            "UNSPENT_OPTION_RESERVATION_PRESERVED",
            "NO_SUPPLEMENTAL_CASH_OR_BORROWING_INFERRED",
        ),
    )
