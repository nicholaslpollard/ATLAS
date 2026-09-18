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
from packages.simulation.recurrent_exit_fill_contract import (
    RECURRENT_EXIT_FILL_CONTRACT,
    RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountStateV1,
    recurrent_lifecycle_account_state_fingerprint,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1


RECURRENT_EXIT_FILL_CONTRACT_VERSION = str(
    RECURRENT_EXIT_FILL_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class RecurrentExitFillError(ValueError):
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
        raise RecurrentExitFillError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise RecurrentExitFillError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentExitFillError(f"{label} must be timezone-aware")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class RecurrentExitFillInputsV1:
    fill_source_id: str
    fill_source_fingerprint: str
    exited_utc: datetime
    exit_price_per_unit: float
    explicit_exit_fees_dollars: float = 0.0

    def __post_init__(self) -> None:
        if not self.fill_source_id.strip():
            raise RecurrentExitFillError(
                "recurrent exit-fill source id cannot be blank"
            )
        _require_fingerprint(
            self.fill_source_fingerprint,
            label="recurrent exit-fill source fingerprint",
        )
        _require_aware(
            self.exited_utc,
            label="recurrent exit-fill timestamp",
        )
        if (
            not math.isfinite(self.exit_price_per_unit)
            or self.exit_price_per_unit < 0.0
        ):
            raise RecurrentExitFillError(
                "exit price must be finite and nonnegative"
            )
        if (
            not math.isfinite(self.explicit_exit_fees_dollars)
            or self.explicit_exit_fees_dollars < 0.0
        ):
            raise RecurrentExitFillError(
                "exit fees must be finite and nonnegative"
            )


@dataclass(frozen=True)
class RecurrentExitFillEvidenceV1:
    contract_version: str
    contract_fingerprint: str
    source_account_contract_fingerprint: str
    source_recurrent_state_fingerprint: str
    position_fingerprint: str

    position_source_account_state_fingerprint: str
    decision_record_fingerprint: str
    candidate_fingerprint: str
    entry_fill_fingerprint: str
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
    exited_utc: datetime
    quantity: float
    quantity_unit: str
    exit_price_per_unit: float
    contract_multiplier: float
    gross_exit_proceeds_dollars: float
    exit_fees_dollars: float
    net_exit_proceeds_dollars: float

    fill_source_id: str
    fill_source_fingerprint: str
    full_close: bool
    reason_codes: tuple[str, ...]

    descriptive_only: bool = True
    position_mutation_authority: bool = False
    account_mutation_authority: bool = False
    realized_pnl_authority: bool = False
    exit_closeout_authority: bool = False
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
        if self.contract_version != RECURRENT_EXIT_FILL_CONTRACT_VERSION:
            raise RecurrentExitFillError(
                "recurrent exit-fill contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT
        ):
            raise RecurrentExitFillError(
                "recurrent exit-fill contract fingerprint mismatch"
            )
        if (
            self.source_account_contract_fingerprint
            != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise RecurrentExitFillError(
                "source recurrent account contract fingerprint mismatch"
            )
        for label, value in (
            ("source recurrent state", self.source_recurrent_state_fingerprint),
            ("position", self.position_fingerprint),
            ("position source account state", self.position_source_account_state_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("candidate", self.candidate_fingerprint),
            ("entry fill", self.entry_fill_fingerprint),
            ("funding terms", self.funding_terms_fingerprint),
            ("reservation", self.reservation_fingerprint),
            ("exit source", self.fill_source_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        for label, value in (
            (
                "option reservation terms",
                self.option_reservation_terms_fingerprint,
            ),
            ("option economics", self.option_economics_result_fingerprint),
        ):
            if value is not None:
                _require_fingerprint(value, label=f"{label} fingerprint")

        _require_aware(self.opened_utc, label="recurrent position opened timestamp")
        _require_aware(self.exited_utc, label="recurrent exit-fill timestamp")
        if self.exited_utc < self.opened_utc:
            raise RecurrentExitFillError(
                "exit-fill timestamp cannot precede position open"
            )
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise RecurrentExitFillError(
                "recurrent exit underlying identity cannot be blank"
            )
        if not self.candidate_identifier.strip():
            raise RecurrentExitFillError(
                "recurrent exit candidate identifier cannot be blank"
            )
        if not self.fill_source_id.strip():
            raise RecurrentExitFillError(
                "recurrent exit source id cannot be blank"
            )
        if not math.isfinite(self.quantity) or self.quantity <= 0.0:
            raise RecurrentExitFillError(
                "recurrent exit quantity must be finite and positive"
            )
        if (
            not math.isfinite(self.contract_multiplier)
            or self.contract_multiplier <= 0.0
        ):
            raise RecurrentExitFillError(
                "recurrent exit multiplier must be finite and positive"
            )
        if (
            not math.isfinite(self.exit_price_per_unit)
            or self.exit_price_per_unit < 0.0
        ):
            raise RecurrentExitFillError(
                "recurrent exit price must be finite and nonnegative"
            )
        if (
            not math.isfinite(self.exit_fees_dollars)
            or self.exit_fees_dollars < 0.0
        ):
            raise RecurrentExitFillError(
                "recurrent exit fees must be finite and nonnegative"
            )

        expected_gross = (
            self.quantity
            * self.exit_price_per_unit
            * self.contract_multiplier
        )
        if not _same(self.gross_exit_proceeds_dollars, expected_gross):
            raise RecurrentExitFillError(
                "gross exit proceeds must match quantity, price, and multiplier"
            )
        if self.exit_fees_dollars > self.gross_exit_proceeds_dollars + _TOLERANCE:
            raise RecurrentExitFillError(
                "exit fees cannot exceed gross exit proceeds"
            )
        if not _same(
            self.net_exit_proceeds_dollars,
            self.gross_exit_proceeds_dollars - self.exit_fees_dollars,
        ):
            raise RecurrentExitFillError(
                "net exit proceeds must equal gross proceeds less exit fees"
            )
        if self.net_exit_proceeds_dollars < -_TOLERANCE:
            raise RecurrentExitFillError(
                "net exit proceeds cannot be negative"
            )
        if not self.full_close:
            raise RecurrentExitFillError(
                "recurrent exit-fill v1 must close the full position"
            )
        if not self.reason_codes:
            raise RecurrentExitFillError(
                "recurrent exit-fill evidence requires reason codes"
            )
        if not self.descriptive_only:
            raise RecurrentExitFillError(
                "recurrent exit-fill evidence must remain descriptive only"
            )

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.quantity_unit != "SHARES":
                raise RecurrentExitFillError(
                    "stock recurrent exit quantity unit must be SHARES"
                )
            if not _same(self.contract_multiplier, 1.0):
                raise RecurrentExitFillError(
                    "stock recurrent exit multiplier must equal one"
                )
            if (
                self.option_contract_ticker is not None
                or self.option_contract_type is not None
                or self.option_reservation_terms_fingerprint is not None
                or self.option_economics_result_fingerprint is not None
            ):
                raise RecurrentExitFillError(
                    "stock recurrent exit cannot carry option lineage"
                )
        elif self.instrument_kind == InstrumentKind.OPTION:
            if self.quantity_unit != "CONTRACTS":
                raise RecurrentExitFillError(
                    "option recurrent exit quantity unit must be CONTRACTS"
                )
            if not _same(self.quantity, round(self.quantity)):
                raise RecurrentExitFillError(
                    "option recurrent exit quantity must be integral contracts"
                )
            if (
                not self.option_contract_ticker
                or self.option_contract_type not in {"call", "put"}
                or self.option_reservation_terms_fingerprint is None
                or self.option_economics_result_fingerprint is None
            ):
                raise RecurrentExitFillError(
                    "option recurrent exit requires complete option lineage"
                )
        else:
            raise RecurrentExitFillError(
                "unsupported recurrent exit instrument kind"
            )

        forbidden = (
            self.position_mutation_authority,
            self.account_mutation_authority,
            self.realized_pnl_authority,
            self.exit_closeout_authority,
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
            raise RecurrentExitFillError(
                "recurrent exit-fill evidence cannot grant mutation, P&L, provider, "
                "broker, order, trading, promotion, or confluence authority"
            )

    @property
    def exit_fill_fingerprint(self) -> str:
        return recurrent_exit_fill_fingerprint(self)


def recurrent_exit_fill_fingerprint(
    fill: RecurrentExitFillEvidenceV1,
) -> str:
    return _fingerprint_payload(fill)


def _active_position(
    source_state: RecurrentLifecycleAccountStateV1,
    position_fingerprint: str,
) -> SimulatedOpenPositionV1:
    _require_fingerprint(
        position_fingerprint,
        label="requested lifecycle position fingerprint",
    )
    matches = tuple(
        position
        for position in source_state.open_positions
        if position.position_fingerprint == position_fingerprint
    )
    if len(matches) != 1:
        raise RecurrentExitFillError(
            "exact active recurrent open position is required"
        )
    return matches[0]


def build_recurrent_exit_fill_evidence(
    *,
    source_state: RecurrentLifecycleAccountStateV1,
    position_fingerprint: str,
    inputs: RecurrentExitFillInputsV1,
) -> RecurrentExitFillEvidenceV1:
    if (
        source_state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentExitFillError(
            "source recurrent lifecycle account contract fingerprint mismatch"
        )
    if (
        source_state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(source_state)
    ):
        raise RecurrentExitFillError(
            "source recurrent lifecycle account state fingerprint mismatch"
        )
    if inputs.exited_utc < source_state.as_of_utc:
        raise RecurrentExitFillError(
            "exit-fill timestamp cannot precede recurrent lifecycle account state"
        )

    position = _active_position(source_state, position_fingerprint)
    if inputs.exited_utc < position.opened_utc:
        raise RecurrentExitFillError(
            "exit-fill timestamp cannot precede position open"
        )
    gross = (
        position.quantity
        * inputs.exit_price_per_unit
        * position.contract_multiplier
    )
    if inputs.explicit_exit_fees_dollars > gross + _TOLERANCE:
        raise RecurrentExitFillError(
            "exit fees cannot exceed gross exit proceeds"
        )
    net = gross - inputs.explicit_exit_fees_dollars

    return RecurrentExitFillEvidenceV1(
        contract_version=RECURRENT_EXIT_FILL_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT,
        source_account_contract_fingerprint=(
            RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
        ),
        source_recurrent_state_fingerprint=source_state.state_fingerprint,
        position_fingerprint=position.position_fingerprint,
        position_source_account_state_fingerprint=(
            position.source_account_state_fingerprint
        ),
        decision_record_fingerprint=position.decision_record_fingerprint,
        candidate_fingerprint=position.candidate_fingerprint,
        entry_fill_fingerprint=position.fill_fingerprint,
        funding_terms_fingerprint=position.funding_terms_fingerprint,
        reservation_fingerprint=position.reservation_fingerprint,
        option_reservation_terms_fingerprint=(
            position.option_reservation_terms_fingerprint
        ),
        option_economics_result_fingerprint=(
            position.option_economics_result_fingerprint
        ),
        instrument_kind=position.instrument_kind,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        direction=position.direction,
        candidate_identifier=position.candidate_identifier,
        option_contract_ticker=position.option_contract_ticker,
        option_contract_type=position.option_contract_type,
        opened_utc=position.opened_utc,
        exited_utc=inputs.exited_utc,
        quantity=position.quantity,
        quantity_unit=position.quantity_unit,
        exit_price_per_unit=inputs.exit_price_per_unit,
        contract_multiplier=position.contract_multiplier,
        gross_exit_proceeds_dollars=gross,
        exit_fees_dollars=inputs.explicit_exit_fees_dollars,
        net_exit_proceeds_dollars=net,
        fill_source_id=inputs.fill_source_id,
        fill_source_fingerprint=inputs.fill_source_fingerprint,
        full_close=True,
        reason_codes=(
            "EXACT_ACTIVE_RECURRENT_POSITION_BOUND",
            "EXACT_FULL_POSITION_QUANTITY_AND_MULTIPLIER_BOUND",
            "EXPLICIT_RECURRENT_EXIT_SOURCE_BOUND",
            "BROKER_NEUTRAL_COMPLETE_RECURRENT_EXIT_MATERIALIZED",
            "NO_POSITION_ACCOUNT_OR_REALIZED_PNL_AUTHORITY_GRANTED",
        ),
    )
