from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from packages.execution.option_economics import OptionEconomicsResult
from packages.execution.option_economics_contract import (
    OPTION_ECONOMICS_CONTRACT_FINGERPRINT,
)
from packages.execution.trade_expression import InstrumentKind, SelectionKind
from packages.schemas.case_file import OptionCandidateEvidence
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    economic_candidate_fingerprint,
)
from packages.simulation.option_reservation_contract import (
    LONG_OPTION_RESERVATION_CONTRACT,
    LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
)


LONG_OPTION_RESERVATION_CONTRACT_VERSION = str(
    LONG_OPTION_RESERVATION_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class LongOptionReservationError(ValueError):
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


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise LongOptionReservationError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise LongOptionReservationError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def option_economics_result_fingerprint(result: OptionEconomicsResult) -> str:
    return _fingerprint_payload(result)


def option_evidence_fingerprint(option: OptionCandidateEvidence) -> str:
    return _fingerprint_payload(option)


@dataclass(frozen=True)
class LongOptionReservationInputs:
    """Broker-neutral cash reserve assumptions for one accepted long option.

    `cash_fee_reserve_dollars` is an explicit conservative cash reserve for fixed
    charges that are not embedded in the ask premium debit. It is not inferred from
    provider or broker state.
    """

    cash_fee_reserve_dollars: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.cash_fee_reserve_dollars):
            raise LongOptionReservationError("cash fee reserve must be finite")
        if self.cash_fee_reserve_dollars < 0.0:
            raise LongOptionReservationError("cash fee reserve cannot be negative")


@dataclass(frozen=True)
class LongOptionReservationTerms:
    contract_version: str
    contract_fingerprint: str
    decision_record_fingerprint: str
    option_economics_contract_fingerprint: str
    option_economics_result_fingerprint: str
    chosen_candidate_identifier: str
    chosen_candidate_fingerprint: str
    option_evidence_fingerprint: str
    source_forecast_fingerprint: str

    instrument_id: str
    ticker: str
    direction: DiscoveryDirection
    option_contract_ticker: str
    option_contract_type: str

    contracts: int
    contract_multiplier: float
    underlying_reference_price: float
    option_delta: float
    entry_ask_per_share: float
    entry_cash_debit_dollars: float
    cash_fee_reserve_dollars: float
    reserved_capital_dollars: float
    max_loss_cash_dollars: float
    premium_at_risk_dollars: float
    signed_delta_equivalent_notional_dollars: float
    abs_delta_equivalent_notional_dollars: float

    reason_codes: tuple[str, ...]
    account_mutation_authority: bool = False
    fill_simulation_authority: bool = False
    realized_pnl_authority: bool = False
    mark_to_market_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != LONG_OPTION_RESERVATION_CONTRACT_VERSION:
            raise LongOptionReservationError("long-option reservation contract version mismatch")
        if self.contract_fingerprint != LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT:
            raise LongOptionReservationError("long-option reservation contract fingerprint mismatch")
        for label, value in (
            ("decision record", self.decision_record_fingerprint),
            ("option economics contract", self.option_economics_contract_fingerprint),
            ("option economics result", self.option_economics_result_fingerprint),
            ("chosen candidate", self.chosen_candidate_fingerprint),
            ("option evidence", self.option_evidence_fingerprint),
            ("source forecast", self.source_forecast_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        if not self.chosen_candidate_identifier.strip():
            raise LongOptionReservationError("chosen candidate identifier cannot be blank")
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise LongOptionReservationError("underlying identity cannot be blank")
        if not self.option_contract_ticker.strip():
            raise LongOptionReservationError("option contract ticker cannot be blank")
        if self.option_contract_type not in {"call", "put"}:
            raise LongOptionReservationError("option contract type must be call or put")
        if isinstance(self.contracts, bool) or not isinstance(self.contracts, int) or self.contracts < 1:
            raise LongOptionReservationError("contracts must be a positive integer")

        positive = (
            self.contract_multiplier,
            self.underlying_reference_price,
            self.entry_ask_per_share,
            self.entry_cash_debit_dollars,
            self.reserved_capital_dollars,
            self.max_loss_cash_dollars,
            self.premium_at_risk_dollars,
            self.abs_delta_equivalent_notional_dollars,
        )
        if not all(math.isfinite(value) and value > 0.0 for value in positive):
            raise LongOptionReservationError("reservation amounts must be finite and positive")
        if not math.isfinite(self.option_delta) or not -1.0 <= self.option_delta <= 1.0:
            raise LongOptionReservationError("option delta must be finite and in [-1, 1]")
        if not math.isfinite(self.signed_delta_equivalent_notional_dollars):
            raise LongOptionReservationError("signed delta-equivalent notional must be finite")
        if not math.isfinite(self.cash_fee_reserve_dollars) or self.cash_fee_reserve_dollars < 0.0:
            raise LongOptionReservationError("cash fee reserve must be finite and nonnegative")

        if self.option_contract_type == "call" and self.option_delta <= 0.0:
            raise LongOptionReservationError("long call delta must be positive")
        if self.option_contract_type == "put" and self.option_delta >= 0.0:
            raise LongOptionReservationError("long put delta must be negative")
        if self.direction == DiscoveryDirection.BULLISH and self.option_contract_type != "call":
            raise LongOptionReservationError("bullish reservation requires a call")
        if self.direction == DiscoveryDirection.BEARISH and self.option_contract_type != "put":
            raise LongOptionReservationError("bearish reservation requires a put")
        if self.direction == DiscoveryDirection.NEUTRAL:
            raise LongOptionReservationError("neutral forecast cannot create option reservation terms")

        expected_reserved = self.entry_cash_debit_dollars + self.cash_fee_reserve_dollars
        if not _same(self.reserved_capital_dollars, expected_reserved):
            raise LongOptionReservationError("reserved capital must equal ask debit plus cash fee reserve")
        if not _same(self.max_loss_cash_dollars, self.reserved_capital_dollars):
            raise LongOptionReservationError("long-option max loss cash must equal reserved capital")
        if not _same(self.premium_at_risk_dollars, self.entry_cash_debit_dollars):
            raise LongOptionReservationError("premium at risk must equal entry ask debit")
        if not _same(
            self.abs_delta_equivalent_notional_dollars,
            abs(self.signed_delta_equivalent_notional_dollars),
        ):
            raise LongOptionReservationError("absolute delta-equivalent notional mismatch")
        if not self.reason_codes:
            raise LongOptionReservationError("reservation terms require reason codes")

        forbidden = (
            self.account_mutation_authority,
            self.fill_simulation_authority,
            self.realized_pnl_authority,
            self.mark_to_market_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden):
            raise LongOptionReservationError(
                "reservation terms cannot grant account, fill, P&L, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def terms_fingerprint(self) -> str:
        return long_option_reservation_terms_fingerprint(self)


def long_option_reservation_terms_fingerprint(terms: LongOptionReservationTerms) -> str:
    return _fingerprint_payload(terms)


def build_long_option_reservation_terms(
    *,
    record: SimulationDecisionRecord,
    option_economics: OptionEconomicsResult,
    option: OptionCandidateEvidence,
    inputs: LongOptionReservationInputs = LongOptionReservationInputs(),
) -> LongOptionReservationTerms:
    decision = record.trade_expression_decision
    if decision.selection_kind != SelectionKind.OPTION:
        raise LongOptionReservationError("decision record did not select an option")
    chosen = decision.chosen_candidate
    if chosen is None or chosen.kind != InstrumentKind.OPTION:
        raise LongOptionReservationError("selected option decision is missing its candidate")

    if option_economics.contract_fingerprint != OPTION_ECONOMICS_CONTRACT_FINGERPRINT:
        raise LongOptionReservationError("option economics contract fingerprint mismatch")
    if option_economics.candidate is None:
        raise LongOptionReservationError("option economics result has no candidate")
    if option_economics.candidate.identifier != chosen.identifier:
        raise LongOptionReservationError("selected option and economics candidate identifiers differ")
    economics_candidate_fp = economic_candidate_fingerprint(option_economics.candidate)
    chosen_candidate_fp = economic_candidate_fingerprint(chosen)
    if economics_candidate_fp != chosen_candidate_fp:
        raise LongOptionReservationError("selected option and economics candidate fingerprints differ")

    matching_record_candidates = tuple(
        candidate
        for candidate in record.option_candidates
        if candidate.identifier == chosen.identifier
    )
    if len(matching_record_candidates) != 1:
        raise LongOptionReservationError("selected option candidate is not uniquely bound in decision record")
    if economic_candidate_fingerprint(matching_record_candidates[0]) != chosen_candidate_fp:
        raise LongOptionReservationError("decision-record option candidate lineage mismatch")

    if option_economics.source_forecast_fingerprint != record.forecast_fingerprint:
        raise LongOptionReservationError("option economics forecast lineage mismatch")
    current_option_evidence_fp = option_evidence_fingerprint(option)
    if option_economics.source_option_evidence_fingerprint != current_option_evidence_fp:
        raise LongOptionReservationError("option evidence fingerprint lineage mismatch")
    if option.contract_ticker != option_economics.option_contract_ticker:
        raise LongOptionReservationError("option contract ticker lineage mismatch")
    if option.contract_type not in {"call", "put"}:
        raise LongOptionReservationError("unsupported option contract type")
    if not option.eligible:
        raise LongOptionReservationError("option evidence must remain upstream-eligible")
    if option.delta is None:
        raise LongOptionReservationError("option delta is required for reservation exposure")
    if not option_economics.scenario_complete:
        raise LongOptionReservationError("option economics scenario must be complete")
    if not chosen.executable or not chosen.risk_budget_ok:
        raise LongOptionReservationError("selected option must remain executable and risk-budget accepted")

    expected_entry_cash_debit = (
        option.ask
        * option_economics.contract_multiplier
        * float(option_economics.contracts)
    )
    if not _same(option.mid, option_economics.entry_mid_per_share):
        raise LongOptionReservationError("option midpoint lineage mismatch")
    if not _same(option.ask, option_economics.entry_ask_per_share):
        raise LongOptionReservationError("option ask lineage mismatch")
    if not _same(expected_entry_cash_debit, option_economics.entry_cash_debit_dollars):
        raise LongOptionReservationError("option ask-debit lineage mismatch")

    reserved_capital = (
        option_economics.entry_cash_debit_dollars
        + inputs.cash_fee_reserve_dollars
    )
    if chosen.capital_required + _TOLERANCE < reserved_capital:
        raise LongOptionReservationError(
            "selected option economic capital does not cover reservation cash at risk"
        )

    reference_price = record.forecast.reference_price
    if reference_price is None or not math.isfinite(reference_price) or reference_price <= 0.0:
        raise LongOptionReservationError("positive underlying reference price is required")
    signed_delta_notional = (
        float(option.delta)
        * reference_price
        * option_economics.contract_multiplier
        * float(option_economics.contracts)
    )

    expected_type = (
        "call"
        if record.forecast.direction == DiscoveryDirection.BULLISH
        else "put"
        if record.forecast.direction == DiscoveryDirection.BEARISH
        else None
    )
    if expected_type is None or option.contract_type != expected_type:
        raise LongOptionReservationError("option type is not aligned to forecast direction")
    if option.contract_type == "call" and option.delta <= 0.0:
        raise LongOptionReservationError("long call delta must be positive")
    if option.contract_type == "put" and option.delta >= 0.0:
        raise LongOptionReservationError("long put delta must be negative")

    reasons = (
        "SELECTED_OPTION_DECISION_BOUND",
        "OPTION_ECONOMICS_RESULT_BOUND",
        "EXACT_OPTION_EVIDENCE_FINGERPRINT_BOUND",
        "OPTION_QUOTE_AND_DELTA_EVIDENCE_BOUND",
        "LONG_OPTION_ASK_DEBIT_RESERVED_AS_PREMIUM_AT_RISK",
        "EXPLICIT_CASH_FEE_RESERVE_INCLUDED",
        "LONG_OPTION_MAX_LOSS_EQUALS_RESERVED_CASH",
        "DELTA_EQUIVALENT_EXPOSURE_RECORDED_SEPARATELY_FROM_STOCK_GROSS_EXPOSURE",
        "NO_ACCOUNT_MUTATION_OR_EXECUTION_AUTHORITY_GRANTED",
    )

    return LongOptionReservationTerms(
        contract_version=LONG_OPTION_RESERVATION_CONTRACT_VERSION,
        contract_fingerprint=LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT,
        decision_record_fingerprint=record.record_fingerprint,
        option_economics_contract_fingerprint=option_economics.contract_fingerprint,
        option_economics_result_fingerprint=option_economics_result_fingerprint(
            option_economics
        ),
        chosen_candidate_identifier=chosen.identifier,
        chosen_candidate_fingerprint=chosen_candidate_fp,
        option_evidence_fingerprint=current_option_evidence_fp,
        source_forecast_fingerprint=record.forecast_fingerprint,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction,
        option_contract_ticker=option.contract_ticker,
        option_contract_type=option.contract_type,
        contracts=option_economics.contracts,
        contract_multiplier=option_economics.contract_multiplier,
        underlying_reference_price=reference_price,
        option_delta=float(option.delta),
        entry_ask_per_share=option.ask,
        entry_cash_debit_dollars=option_economics.entry_cash_debit_dollars,
        cash_fee_reserve_dollars=inputs.cash_fee_reserve_dollars,
        reserved_capital_dollars=reserved_capital,
        max_loss_cash_dollars=reserved_capital,
        premium_at_risk_dollars=option_economics.entry_cash_debit_dollars,
        signed_delta_equivalent_notional_dollars=signed_delta_notional,
        abs_delta_equivalent_notional_dollars=abs(signed_delta_notional),
        reason_codes=reasons,
    )
