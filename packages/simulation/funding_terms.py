from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum, StrEnum
from typing import Any

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.account_state_v2 import SimulationAccountV2
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
)
from packages.simulation.funding_terms_contract import (
    SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT,
    SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.simulated_fill import (
    SimulatedEntryFillEvidence,
    simulated_entry_fill_fingerprint,
    simulated_reservation_fingerprint,
)
from packages.simulation.simulated_fill_contract import (
    SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT,
)


SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_VERSION = str(
    SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class SimulationFundingTermsError(ValueError):
    pass


class SimulationFundingModel(StrEnum):
    CASH_ONLY_STOCK_LONG = "CASH_ONLY_STOCK_LONG"
    RESERVED_LONG_OPTION_DEBIT = "RESERVED_LONG_OPTION_DEBIT"


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
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
        raise SimulationFundingTermsError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise SimulationFundingTermsError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise SimulationFundingTermsError(f"{label} must be finite and nonnegative")


def _require_positive(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise SimulationFundingTermsError(f"{label} must be finite and positive")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class SimulationFundingCollateralTerms:
    contract_version: str
    contract_fingerprint: str
    account_state_fingerprint: str
    fill_fingerprint: str
    active_reservation_fingerprint: str
    decision_record_fingerprint: str
    candidate_fingerprint: str
    instrument_kind: InstrumentKind
    direction: DiscoveryDirection
    funding_model: SimulationFundingModel
    required_cash_dollars: float
    reserved_capital_dollars: float
    supplemental_unreserved_cash_required_dollars: float
    unspent_reserved_capital_dollars: float
    borrowing_dollars: float
    short_sale_proceeds_dollars: float
    collateral_dollars: float
    projected_unreserved_cash_after_transition_dollars: float
    fully_funded: bool
    reason_codes: tuple[str, ...]
    descriptive_only: bool = True
    borrowing_authority: bool = False
    account_mutation_authority: bool = False
    reservation_release_authority: bool = False
    open_position_authority: bool = False
    mark_to_market_authority: bool = False
    realized_pnl_authority: bool = False
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
        if self.contract_version != SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_VERSION:
            raise SimulationFundingTermsError("funding/collateral contract version mismatch")
        if self.contract_fingerprint != SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT:
            raise SimulationFundingTermsError("funding/collateral contract fingerprint mismatch")
        for label, value in (
            ("account state", self.account_state_fingerprint),
            ("fill", self.fill_fingerprint),
            ("active reservation", self.active_reservation_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("candidate", self.candidate_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        _require_positive(self.required_cash_dollars, label="required cash")
        _require_positive(self.reserved_capital_dollars, label="reserved capital")
        for label, value in (
            ("supplemental unreserved cash", self.supplemental_unreserved_cash_required_dollars),
            ("unspent reserved capital", self.unspent_reserved_capital_dollars),
            ("borrowing", self.borrowing_dollars),
            ("short-sale proceeds", self.short_sale_proceeds_dollars),
            ("collateral", self.collateral_dollars),
            ("projected unreserved cash", self.projected_unreserved_cash_after_transition_dollars),
        ):
            _require_nonnegative(value, label=label)
        if self.supplemental_unreserved_cash_required_dollars > _TOLERANCE and self.unspent_reserved_capital_dollars > _TOLERANCE:
            raise SimulationFundingTermsError("funding terms cannot require supplemental cash and leave reservation unspent")
        if not _same(
            self.required_cash_dollars,
            self.reserved_capital_dollars
            + self.supplemental_unreserved_cash_required_dollars
            - self.unspent_reserved_capital_dollars,
        ):
            raise SimulationFundingTermsError("required cash must reconcile to reservation plus supplemental cash minus unspent reserve")
        if any(
            value > _TOLERANCE
            for value in (
                self.borrowing_dollars,
                self.short_sale_proceeds_dollars,
                self.collateral_dollars,
            )
        ):
            raise SimulationFundingTermsError("v1 funding terms cannot infer borrowing, short proceeds, or collateral")
        if not self.fully_funded:
            raise SimulationFundingTermsError("accepted funding terms must be fully funded")
        if not self.reason_codes:
            raise SimulationFundingTermsError("funding terms require reason codes")
        if not self.descriptive_only:
            raise SimulationFundingTermsError("funding terms must remain descriptive only")

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.direction != DiscoveryDirection.BULLISH:
                raise SimulationFundingTermsError("v1 stock funding supports cash-funded bullish longs only")
            if self.funding_model != SimulationFundingModel.CASH_ONLY_STOCK_LONG:
                raise SimulationFundingTermsError("stock funding model mismatch")
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.direction not in {DiscoveryDirection.BULLISH, DiscoveryDirection.BEARISH}:
                raise SimulationFundingTermsError("long-option funding requires bullish or bearish direction")
            if self.funding_model != SimulationFundingModel.RESERVED_LONG_OPTION_DEBIT:
                raise SimulationFundingTermsError("option funding model mismatch")
            if self.supplemental_unreserved_cash_required_dollars > _TOLERANCE:
                raise SimulationFundingTermsError("long-option funding cannot require supplemental cash")
        else:
            raise SimulationFundingTermsError("unsupported funding instrument kind")

        forbidden = (
            self.borrowing_authority,
            self.account_mutation_authority,
            self.reservation_release_authority,
            self.open_position_authority,
            self.mark_to_market_authority,
            self.realized_pnl_authority,
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
            raise SimulationFundingTermsError(
                "funding terms cannot grant borrowing, mutation, broker, order, P&L, trading, promotion, or confluence authority"
            )

    @property
    def terms_fingerprint(self) -> str:
        return simulation_funding_terms_fingerprint(self)


def simulation_funding_terms_fingerprint(
    terms: SimulationFundingCollateralTerms,
) -> str:
    return _fingerprint_payload(terms)


def _validate_common_lineage(
    *,
    account: SimulationAccountV2,
    fill: SimulatedEntryFillEvidence,
) -> None:
    if account.state.contract_fingerprint != SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT:
        raise SimulationFundingTermsError("simulation account-state v2 fingerprint mismatch")
    if fill.contract_fingerprint != SIMULATED_ENTRY_FILL_CONTRACT_FINGERPRINT:
        raise SimulationFundingTermsError("simulated fill contract fingerprint mismatch")
    if fill.account_state_fingerprint != account.state.state_fingerprint:
        raise SimulationFundingTermsError("fill account-state fingerprint does not match current account state")
    if fill.fill_fingerprint != simulated_entry_fill_fingerprint(fill):
        raise SimulationFundingTermsError("simulated fill fingerprint mismatch")


def _active_stock_reservation(account: SimulationAccountV2, fill: SimulatedEntryFillEvidence):
    matches = tuple(
        item
        for item in account.state.stock_reservations
        if item.decision_record_fingerprint == fill.decision_record_fingerprint
    )
    if len(matches) != 1:
        raise SimulationFundingTermsError("exact active stock reservation is required")
    reservation = matches[0]
    if simulated_reservation_fingerprint(reservation) != fill.active_reservation_fingerprint:
        raise SimulationFundingTermsError("stock reservation fingerprint lineage mismatch")
    if not _same(reservation.reserved_capital, fill.reserved_capital_dollars):
        raise SimulationFundingTermsError("stock reserved-capital lineage mismatch")
    if not _same(reservation.gross_notional, fill.gross_fill_notional_dollars):
        raise SimulationFundingTermsError("stock gross-notional lineage mismatch")
    return reservation


def _active_option_reservation(account: SimulationAccountV2, fill: SimulatedEntryFillEvidence):
    matches = tuple(
        item
        for item in account.state.option_reservations
        if item.decision_record_fingerprint == fill.decision_record_fingerprint
    )
    if len(matches) != 1:
        raise SimulationFundingTermsError("exact active option reservation is required")
    reservation = matches[0]
    if simulated_reservation_fingerprint(reservation) != fill.active_reservation_fingerprint:
        raise SimulationFundingTermsError("option reservation fingerprint lineage mismatch")
    if not _same(reservation.reserved_capital, fill.reserved_capital_dollars):
        raise SimulationFundingTermsError("option reserved-capital lineage mismatch")
    if fill.option_reservation_terms_fingerprint != reservation.reservation_terms_fingerprint:
        raise SimulationFundingTermsError("option reservation-terms lineage mismatch")
    if fill.option_economics_result_fingerprint != reservation.option_economics_result_fingerprint:
        raise SimulationFundingTermsError("option economics lineage mismatch")
    return reservation


def build_simulation_funding_collateral_terms(
    *,
    account: SimulationAccountV2,
    fill: SimulatedEntryFillEvidence,
) -> SimulationFundingCollateralTerms:
    _validate_common_lineage(account=account, fill=fill)

    if fill.instrument_kind == InstrumentKind.STOCK:
        _active_stock_reservation(account, fill)
        if fill.direction != DiscoveryDirection.BULLISH:
            raise SimulationFundingTermsError(
                "stock short funding/collateral semantics are unsupported in v1"
            )
        if fill.funding_semantics_resolved:
            raise SimulationFundingTermsError("stock fill must arrive with unresolved funding semantics")
        required_cash = fill.gross_fill_notional_dollars + fill.entry_fees_dollars
        reserved_capital = fill.reserved_capital_dollars
        supplemental = max(0.0, required_cash - reserved_capital)
        unspent = max(0.0, reserved_capital - required_cash)
        if account.state.cash + _TOLERANCE < supplemental:
            raise SimulationFundingTermsError(
                "insufficient unreserved cash for fully cash-funded stock long"
            )
        projected_cash = account.state.cash - supplemental + unspent
        return SimulationFundingCollateralTerms(
            contract_version=SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_VERSION,
            contract_fingerprint=SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT,
            account_state_fingerprint=account.state.state_fingerprint,
            fill_fingerprint=fill.fill_fingerprint,
            active_reservation_fingerprint=fill.active_reservation_fingerprint,
            decision_record_fingerprint=fill.decision_record_fingerprint,
            candidate_fingerprint=fill.candidate_fingerprint,
            instrument_kind=fill.instrument_kind,
            direction=fill.direction,
            funding_model=SimulationFundingModel.CASH_ONLY_STOCK_LONG,
            required_cash_dollars=required_cash,
            reserved_capital_dollars=reserved_capital,
            supplemental_unreserved_cash_required_dollars=supplemental,
            unspent_reserved_capital_dollars=unspent,
            borrowing_dollars=0.0,
            short_sale_proceeds_dollars=0.0,
            collateral_dollars=0.0,
            projected_unreserved_cash_after_transition_dollars=projected_cash,
            fully_funded=True,
            reason_codes=(
                "EXACT_ACCOUNT_STATE_AND_STOCK_RESERVATION_BOUND",
                "FULLY_CASH_FUNDED_STOCK_LONG",
                "FILL_NOTIONAL_AND_ENTRY_FEES_COVERED",
                "NO_BORROWING_MARGIN_OR_SHORT_PROCEEDS_INFERRED",
            ),
        )

    if fill.instrument_kind == InstrumentKind.OPTION:
        _active_option_reservation(account, fill)
        if not fill.funding_semantics_resolved:
            raise SimulationFundingTermsError("long-option fill must have resolved debit funding")
        if fill.cash_debit_dollars is None or fill.unspent_reserved_capital_dollars is None:
            raise SimulationFundingTermsError("long-option fill is missing debit/unspent reserve")
        required_cash = fill.cash_debit_dollars
        reserved_capital = fill.reserved_capital_dollars
        unspent = fill.unspent_reserved_capital_dollars
        if not _same(required_cash + unspent, reserved_capital):
            raise SimulationFundingTermsError("long-option debit does not reconcile to reservation")
        projected_cash = account.state.cash + unspent
        return SimulationFundingCollateralTerms(
            contract_version=SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_VERSION,
            contract_fingerprint=SIMULATION_FUNDING_COLLATERAL_TERMS_CONTRACT_FINGERPRINT,
            account_state_fingerprint=account.state.state_fingerprint,
            fill_fingerprint=fill.fill_fingerprint,
            active_reservation_fingerprint=fill.active_reservation_fingerprint,
            decision_record_fingerprint=fill.decision_record_fingerprint,
            candidate_fingerprint=fill.candidate_fingerprint,
            instrument_kind=fill.instrument_kind,
            direction=fill.direction,
            funding_model=SimulationFundingModel.RESERVED_LONG_OPTION_DEBIT,
            required_cash_dollars=required_cash,
            reserved_capital_dollars=reserved_capital,
            supplemental_unreserved_cash_required_dollars=0.0,
            unspent_reserved_capital_dollars=unspent,
            borrowing_dollars=0.0,
            short_sale_proceeds_dollars=0.0,
            collateral_dollars=0.0,
            projected_unreserved_cash_after_transition_dollars=projected_cash,
            fully_funded=True,
            reason_codes=(
                "EXACT_ACCOUNT_STATE_AND_OPTION_RESERVATION_BOUND",
                "EXACT_LONG_OPTION_DEBIT_REUSED",
                "UNSPENT_OPTION_RESERVATION_PRESERVED",
                "NO_SUPPLEMENTAL_CASH_OR_BORROWING_INFERRED",
            ),
        )

    raise SimulationFundingTermsError("unsupported funding instrument kind")
