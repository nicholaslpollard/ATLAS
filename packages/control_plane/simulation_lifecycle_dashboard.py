from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from packages.simulation.closeout_account_state import (
    CloseoutAccountV1,
    closeout_account_state_fingerprint,
    closeout_ledger_fingerprint,
)
from packages.simulation.lifecycle_marked_account_state import (
    LifecycleMarkedAccountStateV1,
    lifecycle_marked_account_state_fingerprint,
)
from packages.simulation.lifecycle_marked_account_state_contract import (
    LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)
from packages.simulation.engine import SimulationLifecycleCoordinatorV1


SIMULATION_LIFECYCLE_DASHBOARD_CONTRACT_VERSION = (
    "track-a-simulation-lifecycle-dashboard-v1-engine-owned-readonly"
)
SIMULATION_LIFECYCLE_RECORD_LIMIT = 100
_TOLERANCE = 1e-9


class SimulationLifecycleDashboardError(RuntimeError):
    pass


@dataclass(frozen=True)
class SimulationLifecycleDashboardSource:
    closeout_account: CloseoutAccountV1
    marked_state: LifecycleMarkedAccountStateV1


def source_provider_from_coordinator(
    coordinator: SimulationLifecycleCoordinatorV1,
) -> Callable[[], SimulationLifecycleDashboardSource | None]:
    """Adapt one atomic coordinator pair into the read-only dashboard source."""

    def provider() -> SimulationLifecycleDashboardSource | None:
        pair = coordinator.current_dashboard_pair()
        if pair is None:
            return None
        closeout_account, marked_state = pair
        return SimulationLifecycleDashboardSource(
            closeout_account=closeout_account,
            marked_state=marked_state,
        )

    return provider


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _validate_source(source: SimulationLifecycleDashboardSource) -> None:
    closeout = source.closeout_account
    state = closeout.state
    marked = source.marked_state

    if state.state_fingerprint != closeout_account_state_fingerprint(state):
        raise SimulationLifecycleDashboardError(
            "closeout account-state fingerprint mismatch"
        )
    if (
        closeout.ledger.ledger_fingerprint
        != closeout_ledger_fingerprint(closeout.ledger)
    ):
        raise SimulationLifecycleDashboardError(
            "closeout ledger fingerprint mismatch"
        )
    expected_latest = (
        closeout.ledger.events[-1].after_state_fingerprint
        if closeout.ledger.events
        else closeout.ledger.initial_state_fingerprint
    )
    if expected_latest != state.state_fingerprint:
        raise SimulationLifecycleDashboardError(
            "closeout ledger does not terminate at current state"
        )

    if (
        marked.contract_fingerprint
        != LIFECYCLE_MARKED_ACCOUNT_STATE_CONTRACT_FINGERPRINT
    ):
        raise SimulationLifecycleDashboardError(
            "lifecycle marked-state contract fingerprint mismatch"
        )
    if (
        marked.state_fingerprint
        != lifecycle_marked_account_state_fingerprint(marked)
    ):
        raise SimulationLifecycleDashboardError(
            "lifecycle marked-state fingerprint mismatch"
        )
    if marked.source_closeout_state_fingerprint != state.state_fingerprint:
        raise SimulationLifecycleDashboardError(
            "marked state does not bind the current closeout account state"
        )
    if marked.valuation_utc < state.as_of_utc:
        raise SimulationLifecycleDashboardError(
            "marked state predates current closeout account state"
        )

    copied_fields = (
        (
            marked.initial_equity,
            state.initial_equity,
            "initial equity",
        ),
        (
            marked.source_entry_book_equity,
            state.source_entry_book_equity,
            "source entry-book equity",
        ),
        (
            marked.cumulative_entry_fees_dollars,
            state.cumulative_entry_fees_dollars,
            "cumulative entry fees",
        ),
        (
            marked.cumulative_exit_fees_dollars,
            state.cumulative_exit_fees_dollars,
            "cumulative exit fees",
        ),
        (
            marked.cumulative_account_realized_pnl_dollars,
            state.cumulative_account_realized_pnl_dollars,
            "account realized P&L",
        ),
        (
            marked.cumulative_lifetime_trade_net_pnl_dollars,
            state.cumulative_lifetime_trade_net_pnl_dollars,
            "lifetime trade net P&L",
        ),
        (marked.cash, state.cash, "cash"),
        (
            marked.account_book_equity,
            state.account_book_equity,
            "account book equity",
        ),
        (
            marked.remaining_stock_reserved_capital,
            state.remaining_stock_reserved_capital,
            "stock reserved capital",
        ),
        (
            marked.remaining_option_reserved_capital,
            state.remaining_option_reserved_capital,
            "option reserved capital",
        ),
        (
            marked.open_entry_book_value_dollars,
            state.open_entry_book_value_dollars,
            "open entry book value",
        ),
    )
    for left, right, label in copied_fields:
        if not _same(left, right):
            raise SimulationLifecycleDashboardError(
                f"lifecycle projection {label} drifted from closeout state"
            )
    if marked.closed_trade_count != len(state.closed_trades):
        raise SimulationLifecycleDashboardError(
            "lifecycle closed-trade count drifted from closeout state"
        )

    positions_by_fp = {
        position.position_fingerprint: position
        for position in state.open_positions
    }
    marks_by_fp = {
        position.position_fingerprint: position
        for position in marked.marked_positions
    }
    if set(positions_by_fp) != set(marks_by_fp):
        raise SimulationLifecycleDashboardError(
            "lifecycle projection requires exact current open-position coverage"
        )
    for fingerprint, position in positions_by_fp.items():
        mark = marks_by_fp[fingerprint]
        if mark.decision_record_fingerprint != position.decision_record_fingerprint:
            raise SimulationLifecycleDashboardError(
                "marked/open decision lineage mismatch"
            )
        if mark.instrument_kind != position.instrument_kind:
            raise SimulationLifecycleDashboardError(
                "marked/open instrument kind mismatch"
            )
        if mark.instrument_id != position.instrument_id or mark.ticker != position.ticker:
            raise SimulationLifecycleDashboardError(
                "marked/open underlying identity mismatch"
            )
        if (
            mark.option_contract_ticker != position.option_contract_ticker
            or mark.option_contract_type != position.option_contract_type
        ):
            raise SimulationLifecycleDashboardError(
                "marked/open option identity mismatch"
            )
        if not _same(mark.quantity, position.quantity):
            raise SimulationLifecycleDashboardError(
                "marked/open quantity mismatch"
            )
        if not _same(mark.contract_multiplier, position.contract_multiplier):
            raise SimulationLifecycleDashboardError(
                "marked/open multiplier mismatch"
            )
        if not _same(
            mark.entry_book_value_dollars,
            position.entry_book_value_dollars,
        ):
            raise SimulationLifecycleDashboardError(
                "marked/open entry-book value mismatch"
            )
        if not _same(mark.entry_fees_dollars, position.entry_fees_dollars):
            raise SimulationLifecycleDashboardError(
                "marked/open entry-fee mismatch"
            )


def _public_open_positions(
    source: SimulationLifecycleDashboardSource,
) -> list[dict[str, object]]:
    state = source.closeout_account.state
    marked = source.marked_state
    marks = {
        item.position_fingerprint: item
        for item in marked.marked_positions
    }
    rows: list[dict[str, object]] = []
    for position in state.open_positions[:SIMULATION_LIFECYCLE_RECORD_LIMIT]:
        mark = marks[position.position_fingerprint]
        rows.append(
            {
                "position_fingerprint": position.position_fingerprint,
                "mark_fingerprint": mark.mark_fingerprint,
                "decision_record_fingerprint": (
                    position.decision_record_fingerprint
                ),
                "candidate_fingerprint": position.candidate_fingerprint,
                "candidate_identifier": position.candidate_identifier,
                "instrument_kind": position.instrument_kind.value,
                "instrument_id": position.instrument_id,
                "ticker": position.ticker,
                "direction": position.direction.value,
                "option_contract_ticker": position.option_contract_ticker,
                "option_contract_type": position.option_contract_type,
                "opened_utc": position.opened_utc.isoformat(),
                "valuation_utc": mark.valuation_utc.isoformat(),
                "quantity": position.quantity,
                "quantity_unit": position.quantity_unit,
                "entry_price_per_unit": position.entry_price_per_unit,
                "entry_book_value_dollars": position.entry_book_value_dollars,
                "entry_fees_dollars": position.entry_fees_dollars,
                "contract_multiplier": position.contract_multiplier,
                "selected_mark_price_per_unit": (
                    mark.selected_mark_price_per_unit
                ),
                "marked_value_dollars": mark.marked_value_dollars,
                "unrealized_pnl_dollars": mark.unrealized_pnl_dollars,
                "unrealized_return": mark.unrealized_return,
                "option_signed_delta_equivalent_entry_reference_dollars": (
                    position.option_signed_delta_equivalent_entry_reference_dollars
                ),
                "option_abs_delta_equivalent_entry_reference_dollars": (
                    position.option_abs_delta_equivalent_entry_reference_dollars
                ),
                "position_state": "OPEN_SIMULATION_MARKED",
            }
        )
    return rows


def _public_closed_trades(
    source: SimulationLifecycleDashboardSource,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    closed = source.closeout_account.state.closed_trades
    for trade in reversed(closed[-SIMULATION_LIFECYCLE_RECORD_LIMIT:]):
        rows.append(
            {
                "closed_trade_fingerprint": trade.closed_trade_fingerprint,
                "position_fingerprint": trade.position_fingerprint,
                "exit_fill_fingerprint": trade.exit_fill_fingerprint,
                "decision_record_fingerprint": (
                    trade.decision_record_fingerprint
                ),
                "instrument_kind": trade.instrument_kind.value,
                "instrument_id": trade.instrument_id,
                "ticker": trade.ticker,
                "direction": trade.direction.value,
                "candidate_identifier": trade.candidate_identifier,
                "option_contract_ticker": trade.option_contract_ticker,
                "option_contract_type": trade.option_contract_type,
                "opened_utc": trade.opened_utc.isoformat(),
                "exited_utc": trade.exited_utc.isoformat(),
                "hold_seconds": trade.hold_seconds,
                "quantity": trade.quantity,
                "quantity_unit": trade.quantity_unit,
                "entry_price_per_unit": trade.entry_price_per_unit,
                "exit_price_per_unit": trade.exit_price_per_unit,
                "entry_book_value_dollars": trade.entry_book_value_dollars,
                "entry_fees_dollars": trade.entry_fees_dollars,
                "gross_exit_proceeds_dollars": (
                    trade.gross_exit_proceeds_dollars
                ),
                "exit_fees_dollars": trade.exit_fees_dollars,
                "net_exit_proceeds_dollars": trade.net_exit_proceeds_dollars,
                "account_realized_pnl_delta_dollars": (
                    trade.account_realized_pnl_delta_dollars
                ),
                "lifetime_trade_net_pnl_dollars": (
                    trade.lifetime_trade_net_pnl_dollars
                ),
            }
        )
    return rows


class SimulationLifecycleDashboardService:
    """Read-only projection over engine-owned Track A lifecycle state.

    No provider, broker, filesystem, or order object is initialized here. The source
    is injected by the runtime that owns the accepted simulation objects. A missing
    source is explicit NOT_CONNECTED state rather than permission to reconstruct or
    infer trading truth from older artifacts.
    """

    def __init__(
        self,
        *,
        source_provider: (
            Callable[[], SimulationLifecycleDashboardSource | None] | None
        ) = None,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self._source_provider = source_provider
        self._now_utc = now_utc or (lambda: datetime.now(UTC))

    def _base(
        self,
        *,
        now_utc: datetime,
        status: str,
    ) -> dict[str, object]:
        return {
            "contract_version": (
                SIMULATION_LIFECYCLE_DASHBOARD_CONTRACT_VERSION
            ),
            "generated_at_utc": now_utc.isoformat(),
            "status": status,
            "read_only": True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "account": None,
            "open_positions": [],
            "closed_trades": [],
            "statistics": {
                "open_position_count": 0,
                "closed_trade_count": 0,
                "account_realized_pnl": 0.0,
                "lifetime_trade_net_pnl": 0.0,
                "aggregate_unrealized_pnl": 0.0,
            },
            "authority": {
                "source": "ENGINE_OWNED_INJECTED_STATE",
                "browser_mutation_authority": False,
                "provider_read_authority": False,
                "provider_write_authority": False,
                "broker_read_authority": False,
                "broker_write_authority": False,
                "order_creation_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "promotion_authority": False,
                "confluence_authority": False,
            },
        }

    def snapshot(self) -> dict[str, object]:
        now_utc = self._now_utc()
        if now_utc.tzinfo is None or now_utc.utcoffset() is None:
            now_utc = now_utc.replace(tzinfo=UTC)
        now_utc = now_utc.astimezone(UTC)

        if self._source_provider is None:
            payload = self._base(
                now_utc=now_utc,
                status="NOT_CONNECTED",
            )
            payload["health"] = {
                "engine_source_connected": False,
                "reason": "SIMULATION_LIFECYCLE_SOURCE_NOT_INJECTED",
            }
            return payload

        try:
            source = self._source_provider()
            if source is None:
                payload = self._base(
                    now_utc=now_utc,
                    status="NOT_CONNECTED",
                )
                payload["health"] = {
                    "engine_source_connected": False,
                    "reason": "SIMULATION_LIFECYCLE_SOURCE_NOT_AVAILABLE",
                }
                return payload
            if not isinstance(source, SimulationLifecycleDashboardSource):
                raise SimulationLifecycleDashboardError(
                    "source provider returned an unsupported object"
                )
            _validate_source(source)
        except Exception as exc:
            payload = self._base(now_utc=now_utc, status="INVALID")
            payload["error"] = type(exc).__name__
            payload["health"] = {
                "engine_source_connected": True,
                "source_valid": False,
                "reason": "ENGINE_LIFECYCLE_SOURCE_FAILED_VALIDATION",
            }
            return payload

        closeout = source.closeout_account
        state = closeout.state
        marked = source.marked_state
        open_rows = _public_open_positions(source)
        closed_rows = _public_closed_trades(source)

        payload = self._base(now_utc=now_utc, status="AVAILABLE")
        payload.update(
            {
                "source": {
                    "closeout_state_fingerprint": state.state_fingerprint,
                    "closeout_ledger_fingerprint": (
                        closeout.ledger.ledger_fingerprint
                    ),
                    "marked_state_fingerprint": marked.state_fingerprint,
                    "book_as_of_utc": state.as_of_utc.isoformat(),
                    "valuation_utc": marked.valuation_utc.isoformat(),
                    "complete_mark_coverage": (
                        marked.complete_mark_coverage
                    ),
                },
                "account": {
                    "initial_equity": state.initial_equity,
                    "cash": state.cash,
                    "account_book_equity": state.account_book_equity,
                    "marked_equity": marked.marked_equity,
                    "cumulative_entry_fees_dollars": (
                        state.cumulative_entry_fees_dollars
                    ),
                    "cumulative_exit_fees_dollars": (
                        state.cumulative_exit_fees_dollars
                    ),
                    "cumulative_account_realized_pnl_dollars": (
                        state.cumulative_account_realized_pnl_dollars
                    ),
                    "cumulative_lifetime_trade_net_pnl_dollars": (
                        state.cumulative_lifetime_trade_net_pnl_dollars
                    ),
                    "aggregate_unrealized_pnl_dollars": (
                        marked.aggregate_unrealized_pnl_dollars
                    ),
                    "remaining_stock_reserved_capital": (
                        state.remaining_stock_reserved_capital
                    ),
                    "remaining_option_reserved_capital": (
                        state.remaining_option_reserved_capital
                    ),
                    "open_entry_book_value_dollars": (
                        state.open_entry_book_value_dollars
                    ),
                    "marked_open_position_value_dollars": (
                        marked.marked_open_position_value_dollars
                    ),
                    "snapshot_kind": (
                        "ENGINE_OWNED_SIMULATION_LIFECYCLE_CURRENT"
                    ),
                },
                "open_positions": open_rows,
                "closed_trades": closed_rows,
                "statistics": {
                    "open_position_count": len(state.open_positions),
                    "closed_trade_count": len(state.closed_trades),
                    "account_realized_pnl": (
                        state.cumulative_account_realized_pnl_dollars
                    ),
                    "lifetime_trade_net_pnl": (
                        state.cumulative_lifetime_trade_net_pnl_dollars
                    ),
                    "aggregate_unrealized_pnl": (
                        marked.aggregate_unrealized_pnl_dollars
                    ),
                    "winning_closed_trade_count": sum(
                        1
                        for item in state.closed_trades
                        if item.lifetime_trade_net_pnl_dollars > 0.0
                    ),
                    "losing_closed_trade_count": sum(
                        1
                        for item in state.closed_trades
                        if item.lifetime_trade_net_pnl_dollars < 0.0
                    ),
                    "flat_closed_trade_count": sum(
                        1
                        for item in state.closed_trades
                        if _same(
                            item.lifetime_trade_net_pnl_dollars,
                            0.0,
                        )
                    ),
                },
                "health": {
                    "engine_source_connected": True,
                    "source_valid": True,
                    "complete_mark_coverage": (
                        marked.complete_mark_coverage
                    ),
                    "automatic_provider_refresh": False,
                    "automatic_broker_refresh": False,
                    "browser_mutation_authority": False,
                    "live_execution_promoted": False,
                },
            }
        )
        return payload
