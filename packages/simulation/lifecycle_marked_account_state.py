from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from packages.simulation.closeout_account_state import (
    CloseoutAccountStateV1,
    closeout_account_state_fingerprint,
)
from packages.simulation.closeout_account_state_contract import (
    SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.lifecycle_marked_account_state_contract import (
    LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT,
    LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.marked_account_state import MarkedOpenPositionV1
from packages.simulation.market_mark_evidence import (
    MarketMarkFreshness,
    SimulatedMarketMarkEvidence,
    simulated_market_mark_fingerprint,
)
from packages.simulation.market_mark_evidence_contract import (
    MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.simulation.open_position_state import (
    SimulatedOpenPositionV1,
    simulated_open_position_fingerprint,
)


LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_VERSION = str(
    LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class LifecycleMarkedAccountStateError(ValueError):
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
        raise LifecycleMarkedAccountStateError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise LifecycleMarkedAccountStateError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise LifecycleMarkedAccountStateError(
            f"{label} must be timezone-aware"
        )


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise LifecycleMarkedAccountStateError(
            f"{label} must be finite and nonnegative"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class LifecycleMarkedAccountStateV1:
    contract_version: str
    contract_fingerprint: str
    source_closeout_contract_fingerprint: str
    source_closeout_state_fingerprint: str
    valuation_utc: datetime

    initial_equity: float
    source_entry_book_equity: float
    cumulative_entry_fees_dollars: float
    cumulative_exit_fees_dollars: float
    cumulative_account_realized_pnl_dollars: float
    cumulative_lifetime_trade_net_pnl_dollars: float

    cash: float
    account_book_equity: float
    remaining_stock_reserved_capital: float
    remaining_option_reserved_capital: float
    open_entry_book_value_dollars: float

    marked_open_position_value_dollars: float
    aggregate_unrealized_pnl_dollars: float
    marked_equity: float
    closed_trade_count: int
    complete_mark_coverage: bool
    marked_positions: tuple[MarkedOpenPositionV1, ...]

    simulation_mark_to_market_computation: bool = True
    simulation_unrealized_pnl_computation: bool = True
    account_mutation_authority: bool = False
    new_realized_pnl_authority: bool = False
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
        if (
            self.contract_version
            != LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_VERSION
        ):
            raise LifecycleMarkedAccountStateError(
                "lifecycle marked-account contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ):
            raise LifecycleMarkedAccountStateError(
                "lifecycle marked-account contract fingerprint mismatch"
            )
        if (
            self.source_closeout_contract_fingerprint
            != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ):
            raise LifecycleMarkedAccountStateError(
                "source closeout contract fingerprint mismatch"
            )
        _require_fingerprint(
            self.source_closeout_state_fingerprint,
            label="source closeout state fingerprint",
        )
        _require_aware(
            self.valuation_utc,
            label="lifecycle valuation timestamp",
        )
        if not math.isfinite(self.initial_equity) or self.initial_equity <= 0.0:
            raise LifecycleMarkedAccountStateError(
                "initial equity must be finite and positive"
            )
        for label, value in (
            ("source entry-book equity", self.source_entry_book_equity),
            ("cumulative entry fees", self.cumulative_entry_fees_dollars),
            ("cumulative exit fees", self.cumulative_exit_fees_dollars),
            ("cash", self.cash),
            ("account book equity", self.account_book_equity),
            (
                "remaining stock reserved capital",
                self.remaining_stock_reserved_capital,
            ),
            (
                "remaining option reserved capital",
                self.remaining_option_reserved_capital,
            ),
            ("open entry book value", self.open_entry_book_value_dollars),
            (
                "marked open-position value",
                self.marked_open_position_value_dollars,
            ),
            ("marked equity", self.marked_equity),
        ):
            _require_nonnegative(value, label=label)
        for label, value in (
            (
                "cumulative account realized P&L",
                self.cumulative_account_realized_pnl_dollars,
            ),
            (
                "cumulative lifetime trade net P&L",
                self.cumulative_lifetime_trade_net_pnl_dollars,
            ),
            ("aggregate unrealized P&L", self.aggregate_unrealized_pnl_dollars),
        ):
            if not math.isfinite(value):
                raise LifecycleMarkedAccountStateError(
                    f"{label} must be finite"
                )
        if self.closed_trade_count < 0:
            raise LifecycleMarkedAccountStateError(
                "closed-trade count cannot be negative"
            )
        if not self.complete_mark_coverage:
            raise LifecycleMarkedAccountStateError(
                "accepted lifecycle valuation requires complete fresh mark coverage"
            )
        if (
            not self.simulation_mark_to_market_computation
            or not self.simulation_unrealized_pnl_computation
        ):
            raise LifecycleMarkedAccountStateError(
                "lifecycle valuation must identify simulation mark-to-market computations"
            )

        ordered = tuple(
            sorted(
                self.marked_positions,
                key=lambda item: item.decision_record_fingerprint,
            )
        )
        if self.marked_positions != ordered:
            raise LifecycleMarkedAccountStateError(
                "lifecycle marked positions must be ordered by decision fingerprint"
            )
        decision_ids = [
            item.decision_record_fingerprint for item in self.marked_positions
        ]
        if len(decision_ids) != len(set(decision_ids)):
            raise LifecycleMarkedAccountStateError(
                "lifecycle marked positions cannot duplicate a decision fingerprint"
            )
        if any(
            item.valuation_utc != self.valuation_utc
            for item in self.marked_positions
        ):
            raise LifecycleMarkedAccountStateError(
                "all lifecycle marked positions must share the valuation timestamp"
            )

        if not _same(
            self.marked_open_position_value_dollars,
            sum(
                item.marked_value_dollars
                for item in self.marked_positions
            ),
        ):
            raise LifecycleMarkedAccountStateError(
                "marked open-position value must equal constituent sum"
            )
        if not _same(
            self.aggregate_unrealized_pnl_dollars,
            sum(
                item.unrealized_pnl_dollars
                for item in self.marked_positions
            ),
        ):
            raise LifecycleMarkedAccountStateError(
                "aggregate unrealized P&L must equal constituent sum"
            )
        if not _same(
            self.source_entry_book_equity,
            self.initial_equity - self.cumulative_entry_fees_dollars,
        ):
            raise LifecycleMarkedAccountStateError(
                "source entry-book equity must preserve already-expensed entry fees"
            )
        if not _same(
            self.account_book_equity,
            self.initial_equity
            - self.cumulative_entry_fees_dollars
            + self.cumulative_account_realized_pnl_dollars,
        ):
            raise LifecycleMarkedAccountStateError(
                "account book equity must preserve closeout realized-P&L semantics"
            )
        if not _same(
            self.marked_equity,
            self.account_book_equity
            + self.aggregate_unrealized_pnl_dollars,
        ):
            raise LifecycleMarkedAccountStateError(
                "marked equity must equal account book equity plus current unrealized P&L"
            )
        if not _same(
            self.marked_equity,
            self.cash
            + self.remaining_stock_reserved_capital
            + self.remaining_option_reserved_capital
            + self.marked_open_position_value_dollars,
        ):
            raise LifecycleMarkedAccountStateError(
                "lifecycle marked equity must reconcile cash, reservations, and marked positions"
            )

        forbidden = (
            self.account_mutation_authority,
            self.new_realized_pnl_authority,
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
            raise LifecycleMarkedAccountStateError(
                "lifecycle valuation cannot grant mutation, new realized-P&L, "
                "exit, provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def state_fingerprint(self) -> str:
        return lifecycle_marked_account_state_fingerprint(self)


def lifecycle_marked_account_state_fingerprint(
    state: LifecycleMarkedAccountStateV1,
) -> str:
    return _fingerprint_payload(state)


def _validate_mark_for_current_position(
    *,
    position: SimulatedOpenPositionV1,
    mark: SimulatedMarketMarkEvidence,
    valuation_utc: datetime,
) -> None:
    if mark.contract_fingerprint != MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT:
        raise LifecycleMarkedAccountStateError(
            "market-mark contract fingerprint mismatch"
        )
    if mark.mark_fingerprint != simulated_market_mark_fingerprint(mark):
        raise LifecycleMarkedAccountStateError(
            "market-mark fingerprint mismatch"
        )
    if (
        mark.position_fingerprint
        != simulated_open_position_fingerprint(position)
    ):
        raise LifecycleMarkedAccountStateError(
            "mark does not bind the exact current open position"
        )
    if (
        mark.decision_record_fingerprint
        != position.decision_record_fingerprint
    ):
        raise LifecycleMarkedAccountStateError(
            "mark decision lineage mismatch"
        )
    if (
        mark.source_account_state_fingerprint
        != position.source_account_state_fingerprint
    ):
        raise LifecycleMarkedAccountStateError(
            "mark source account-state lineage mismatch"
        )
    if mark.fill_fingerprint != position.fill_fingerprint:
        raise LifecycleMarkedAccountStateError(
            "mark fill lineage mismatch"
        )
    if mark.funding_terms_fingerprint != position.funding_terms_fingerprint:
        raise LifecycleMarkedAccountStateError(
            "mark funding lineage mismatch"
        )
    if mark.instrument_kind != position.instrument_kind:
        raise LifecycleMarkedAccountStateError(
            "mark instrument kind mismatch"
        )
    if (
        mark.instrument_id != position.instrument_id
        or mark.ticker != position.ticker
    ):
        raise LifecycleMarkedAccountStateError(
            "mark underlying identity mismatch"
        )
    if (
        mark.option_contract_ticker != position.option_contract_ticker
        or mark.option_contract_type != position.option_contract_type
    ):
        raise LifecycleMarkedAccountStateError(
            "mark option identity mismatch"
        )
    if mark.valuation_utc != valuation_utc:
        raise LifecycleMarkedAccountStateError(
            "all marks must share the requested lifecycle valuation timestamp"
        )
    if mark.market_timestamp_utc < position.opened_utc:
        raise LifecycleMarkedAccountStateError(
            "market mark cannot predate the position open"
        )
    if (
        mark.freshness != MarketMarkFreshness.FRESH
        or not mark.valuation_eligible
    ):
        raise LifecycleMarkedAccountStateError(
            "stale or ineligible mark cannot create current lifecycle valuation"
        )


def _mark_current_position(
    *,
    position: SimulatedOpenPositionV1,
    mark: SimulatedMarketMarkEvidence,
    valuation_utc: datetime,
) -> MarkedOpenPositionV1:
    _validate_mark_for_current_position(
        position=position,
        mark=mark,
        valuation_utc=valuation_utc,
    )
    marked_value = (
        position.quantity
        * mark.selected_mark_price_per_unit
        * position.contract_multiplier
    )
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
        unrealized_return=(
            unrealized_pnl / position.entry_book_value_dollars
        ),
        stock_gross_entry_exposure_dollars=(
            position.stock_gross_entry_exposure_dollars
        ),
        option_premium_at_risk_dollars=(
            position.option_premium_at_risk_dollars
        ),
        option_signed_delta_equivalent_entry_reference_dollars=(
            position.option_signed_delta_equivalent_entry_reference_dollars
        ),
        option_abs_delta_equivalent_entry_reference_dollars=(
            position.option_abs_delta_equivalent_entry_reference_dollars
        ),
        reason_codes=(
            "EXACT_POST_CLOSE_OPEN_POSITION_AND_FRESH_MARK_BOUND",
            "MARKED_VALUE_USES_FROZEN_SELECTED_MARK",
            "UNREALIZED_PNL_RELATIVE_TO_ENTRY_BOOK_VALUE",
            "CLOSEOUT_REALIZED_PNL_CARRIED_FORWARD_IMMUTABLY",
            "ENTRY_AND_EXIT_FEE_ACCOUNTING_NOT_RECOMPUTED",
            "OPTION_ENTRY_DELTA_REMAINS_REFERENCE_ONLY",
        ),
    )


def build_lifecycle_marked_account_state(
    *,
    source_state: CloseoutAccountStateV1,
    marks: Sequence[SimulatedMarketMarkEvidence],
    valuation_utc: datetime,
) -> LifecycleMarkedAccountStateV1:
    if (
        source_state.contract_fingerprint
        != SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
    ):
        raise LifecycleMarkedAccountStateError(
            "closeout state contract fingerprint mismatch"
        )
    if (
        source_state.state_fingerprint
        != closeout_account_state_fingerprint(source_state)
    ):
        raise LifecycleMarkedAccountStateError(
            "closeout state fingerprint mismatch"
        )
    _require_aware(
        valuation_utc,
        label="requested lifecycle valuation timestamp",
    )
    if valuation_utc < source_state.as_of_utc:
        raise LifecycleMarkedAccountStateError(
            "valuation timestamp cannot predate closeout account state"
        )

    positions = tuple(source_state.open_positions)
    mark_by_decision: dict[str, SimulatedMarketMarkEvidence] = {}
    for mark in marks:
        key = mark.decision_record_fingerprint
        if key in mark_by_decision:
            raise LifecycleMarkedAccountStateError(
                "one current open position cannot receive multiple marks in one lifecycle valuation"
            )
        mark_by_decision[key] = mark

    expected_ids = {
        item.decision_record_fingerprint for item in positions
    }
    provided_ids = set(mark_by_decision)
    if provided_ids != expected_ids:
        missing = sorted(expected_ids - provided_ids)
        extra = sorted(provided_ids - expected_ids)
        raise LifecycleMarkedAccountStateError(
            "complete current open-position mark coverage required; "
            f"missing={missing}, extra={extra}"
        )

    marked_positions = tuple(
        sorted(
            (
                _mark_current_position(
                    position=position,
                    mark=mark_by_decision[
                        position.decision_record_fingerprint
                    ],
                    valuation_utc=valuation_utc,
                )
                for position in positions
            ),
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    marked_value = sum(
        item.marked_value_dollars for item in marked_positions
    )
    unrealized_pnl = sum(
        item.unrealized_pnl_dollars for item in marked_positions
    )
    marked_equity = source_state.account_book_equity + unrealized_pnl

    return LifecycleMarkedAccountStateV1(
        contract_version=LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_VERSION,
        contract_fingerprint=(
            LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_closeout_contract_fingerprint=(
            SIMULATION_CLOSEOUT_ACCOUNT_STATE_CONTRACT_FINGERPRINT
        ),
        source_closeout_state_fingerprint=source_state.state_fingerprint,
        valuation_utc=valuation_utc,
        initial_equity=source_state.initial_equity,
        source_entry_book_equity=source_state.source_entry_book_equity,
        cumulative_entry_fees_dollars=(
            source_state.cumulative_entry_fees_dollars
        ),
        cumulative_exit_fees_dollars=(
            source_state.cumulative_exit_fees_dollars
        ),
        cumulative_account_realized_pnl_dollars=(
            source_state.cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            source_state.cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=source_state.cash,
        account_book_equity=source_state.account_book_equity,
        remaining_stock_reserved_capital=(
            source_state.remaining_stock_reserved_capital
        ),
        remaining_option_reserved_capital=(
            source_state.remaining_option_reserved_capital
        ),
        open_entry_book_value_dollars=(
            source_state.open_entry_book_value_dollars
        ),
        marked_open_position_value_dollars=marked_value,
        aggregate_unrealized_pnl_dollars=unrealized_pnl,
        marked_equity=marked_equity,
        closed_trade_count=len(source_state.closed_trades),
        complete_mark_coverage=True,
        marked_positions=marked_positions,
    )
