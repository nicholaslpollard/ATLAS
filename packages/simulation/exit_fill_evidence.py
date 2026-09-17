from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.exit_fill_evidence_contract import (
    EXIT_FILL_EVIDENCE_CONTRACT,
    EXIT_FILL_EVIDENCE_CONTRACT_FINGERPRINT,
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


EXIT_FILL_EVIDENCE_CONTRACT_VERSION = str(EXIT_FILL_EVIDENCE_CONTRACT["contract_id"])
_TOLERANCE = 1e-9


class ExitFillEvidenceError(ValueError):
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
        raise ExitFillEvidenceError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ExitFillEvidenceError(f"{label} must be a SHA-256 fingerprint") from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExitFillEvidenceError(f"{label} must be timezone-aware")


def _require_positive(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ExitFillEvidenceError(f"{label} must be finite and positive")


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ExitFillEvidenceError(f"{label} must be finite and nonnegative")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class SimulatedExitFillInputs:
    source_id: str
    source_fingerprint: str
    filled_utc: datetime
    fill_price_per_unit: float
    explicit_exit_fees_dollars: float = 0.0

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ExitFillEvidenceError("exit-fill source id cannot be blank")
        _require_fingerprint(self.source_fingerprint, label="exit-fill source fingerprint")
        _require_aware(self.filled_utc, label="exit-fill timestamp")
        _require_nonnegative(self.fill_price_per_unit, label="exit-fill price")
        _require_nonnegative(self.explicit_exit_fees_dollars, label="exit fees")


@dataclass(frozen=True)
class SimulatedExitFillEvidence:
    contract_version: str
    contract_fingerprint: str
    open_position_contract_fingerprint: str
    source_open_position_state_fingerprint: str
    position_fingerprint: str
    source_account_state_fingerprint: str
    decision_record_fingerprint: str
    candidate_fingerprint: str
    entry_fill_fingerprint: str
    funding_terms_fingerprint: str
    instrument_kind: InstrumentKind
    instrument_id: str
    ticker: str
    direction: DiscoveryDirection
    candidate_identifier: str
    option_contract_ticker: str | None
    option_contract_type: str | None
    source_id: str
    source_fingerprint: str
    filled_utc: datetime
    quantity: float
    quantity_unit: str
    fill_price_per_unit: float
    contract_multiplier: float
    gross_exit_value_dollars: float
    exit_fees_dollars: float
    complete_close: bool
    reason_codes: tuple[str, ...]
    descriptive_only: bool = True
    position_mutation_authority: bool = False
    realized_pnl_authority: bool = False
    mark_to_market_authority: bool = False
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
        if self.contract_version != EXIT_FILL_EVIDENCE_CONTRACT_VERSION:
            raise ExitFillEvidenceError("exit-fill contract version mismatch")
        if self.contract_fingerprint != EXIT_FILL_EVIDENCE_CONTRACT_FINGERPRINT:
            raise ExitFillEvidenceError("exit-fill contract fingerprint mismatch")
        if self.open_position_contract_fingerprint != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise ExitFillEvidenceError("open-position contract fingerprint mismatch")
        for label, value in (
            ("source open-position state", self.source_open_position_state_fingerprint),
            ("position", self.position_fingerprint),
            ("source account state", self.source_account_state_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("candidate", self.candidate_fingerprint),
            ("entry fill", self.entry_fill_fingerprint),
            ("funding terms", self.funding_terms_fingerprint),
            ("source", self.source_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise ExitFillEvidenceError("exit-fill identity cannot be blank")
        if not self.candidate_identifier.strip():
            raise ExitFillEvidenceError("exit-fill candidate identifier cannot be blank")
        if not self.source_id.strip():
            raise ExitFillEvidenceError("exit-fill source id cannot be blank")
        _require_aware(self.filled_utc, label="exit-fill timestamp")
        _require_positive(self.quantity, label="exit quantity")
        _require_positive(self.contract_multiplier, label="exit contract multiplier")
        _require_nonnegative(self.fill_price_per_unit, label="exit-fill price")
        _require_nonnegative(self.gross_exit_value_dollars, label="gross exit value")
        _require_nonnegative(self.exit_fees_dollars, label="exit fees")
        expected_value = self.quantity * self.fill_price_per_unit * self.contract_multiplier
        if not _same(self.gross_exit_value_dollars, expected_value):
            raise ExitFillEvidenceError("gross exit value must match quantity, price, and multiplier")
        if not self.complete_close:
            raise ExitFillEvidenceError("v1 exit-fill evidence supports complete closes only")
        if not self.reason_codes:
            raise ExitFillEvidenceError("exit-fill evidence requires reason codes")
        if not self.descriptive_only:
            raise ExitFillEvidenceError("exit-fill evidence must remain descriptive only")

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES" or not _same(self.contract_multiplier, 1.0):
                raise ExitFillEvidenceError("stock exit quantity/multiplier mismatch")
            _require_positive(self.fill_price_per_unit, label="stock exit-fill price")
            if self.option_contract_ticker is not None or self.option_contract_type is not None:
                raise ExitFillEvidenceError("stock exit cannot carry option identity")
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS" or not _same(self.quantity, round(self.quantity)):
                raise ExitFillEvidenceError("option exit quantity must be integral contracts")
            if not self.option_contract_ticker or self.option_contract_type not in {"call", "put"}:
                raise ExitFillEvidenceError("option exit requires call/put identity")
        else:
            raise ExitFillEvidenceError("unsupported exit-fill instrument kind")

        forbidden = (
            self.position_mutation_authority,
            self.realized_pnl_authority,
            self.mark_to_market_authority,
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
            raise ExitFillEvidenceError(
                "exit-fill evidence cannot grant position mutation, P&L, provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def exit_fill_fingerprint(self) -> str:
        return simulated_exit_fill_fingerprint(self)


def simulated_exit_fill_fingerprint(fill: SimulatedExitFillEvidence) -> str:
    return _fingerprint_payload(fill)


def _validate_exact_active_position(
    *,
    source_state: OpenPositionAccountStateV1,
    position: SimulatedOpenPositionV1,
) -> tuple[str, str]:
    if source_state.contract_fingerprint != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
        raise ExitFillEvidenceError("source open-position contract fingerprint mismatch")
    source_state_fingerprint = open_position_account_state_fingerprint(source_state)
    position_fingerprint = simulated_open_position_fingerprint(position)
    matches = tuple(
        item
        for item in source_state.open_positions
        if simulated_open_position_fingerprint(item) == position_fingerprint
    )
    if len(matches) != 1:
        raise ExitFillEvidenceError("exact active open position is required")
    active = matches[0]
    if active.decision_record_fingerprint != position.decision_record_fingerprint:
        raise ExitFillEvidenceError("active position decision lineage mismatch")
    if active.source_account_state_fingerprint != source_state.source_account_state_fingerprint:
        raise ExitFillEvidenceError("active position source account lineage mismatch")
    if active != position:
        raise ExitFillEvidenceError("active position payload mismatch")
    return source_state_fingerprint, position_fingerprint


def build_simulated_exit_fill_evidence(
    *,
    source_state: OpenPositionAccountStateV1,
    position: SimulatedOpenPositionV1,
    inputs: SimulatedExitFillInputs,
) -> SimulatedExitFillEvidence:
    source_state_fingerprint, position_fingerprint = _validate_exact_active_position(
        source_state=source_state,
        position=position,
    )
    if inputs.filled_utc < position.opened_utc:
        raise ExitFillEvidenceError("exit-fill timestamp cannot predate position open")
    if inputs.filled_utc < source_state.as_of_utc:
        raise ExitFillEvidenceError("exit-fill timestamp cannot predate source open-position state")
    if position.instrument_kind == InstrumentKind.STOCK and inputs.fill_price_per_unit <= 0.0:
        raise ExitFillEvidenceError("stock exit-fill price must be positive")

    gross_exit_value = (
        position.quantity * inputs.fill_price_per_unit * position.contract_multiplier
    )
    reason_codes = [
        "EXACT_OPEN_POSITION_ACCOUNT_STATE_BOUND",
        "EXACT_ACTIVE_POSITION_FINGERPRINT_BOUND",
        "COMPLETE_POSITION_CLOSE_QUANTITY_COPIED_FROM_POSITION",
        "SOURCE_ID_AND_SHA256_BOUND",
        "NO_REALIZED_PNL_OR_ACCOUNT_MUTATION_AUTHORITY",
    ]
    if position.instrument_kind == InstrumentKind.OPTION and inputs.fill_price_per_unit == 0.0:
        reason_codes.append("LONG_OPTION_ZERO_VALUE_EXIT_ALLOWED")

    return SimulatedExitFillEvidence(
        contract_version=EXIT_FILL_EVIDENCE_CONTRACT_VERSION,
        contract_fingerprint=EXIT_FILL_EVIDENCE_CONTRACT_FINGERPRINT,
        open_position_contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        source_open_position_state_fingerprint=source_state_fingerprint,
        position_fingerprint=position_fingerprint,
        source_account_state_fingerprint=position.source_account_state_fingerprint,
        decision_record_fingerprint=position.decision_record_fingerprint,
        candidate_fingerprint=position.candidate_fingerprint,
        entry_fill_fingerprint=position.fill_fingerprint,
        funding_terms_fingerprint=position.funding_terms_fingerprint,
        instrument_kind=position.instrument_kind,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        direction=position.direction,
        candidate_identifier=position.candidate_identifier,
        option_contract_ticker=position.option_contract_ticker,
        option_contract_type=position.option_contract_type,
        source_id=inputs.source_id,
        source_fingerprint=inputs.source_fingerprint,
        filled_utc=inputs.filled_utc,
        quantity=position.quantity,
        quantity_unit=position.quantity_unit,
        fill_price_per_unit=float(inputs.fill_price_per_unit),
        contract_multiplier=position.contract_multiplier,
        gross_exit_value_dollars=float(gross_exit_value),
        exit_fees_dollars=float(inputs.explicit_exit_fees_dollars),
        complete_close=True,
        reason_codes=tuple(reason_codes),
    )
