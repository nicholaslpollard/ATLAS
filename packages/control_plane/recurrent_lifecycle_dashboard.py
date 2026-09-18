from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from packages.simulation.recurrent_engine import RecurrentLifecycleCoordinatorV1
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    recurrent_lifecycle_account_state_fingerprint,
    recurrent_lifecycle_ledger_fingerprint,
)
from packages.simulation.recurrent_marked_contract import (
    RECURRENT_MARKED_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_marked_state import (
    RecurrentMarkedAccountStateV1,
    recurrent_marked_account_state_fingerprint,
)


RECURRENT_LIFECYCLE_DASHBOARD_CONTRACT_VERSION = (
    "track-a-recurrent-simulation-lifecycle-dashboard-v1-engine-owned-readonly"
)
RECURRENT_LIFECYCLE_RECORD_LIMIT = 100
_TOLERANCE = 1e-9


class RecurrentLifecycleDashboardError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecurrentLifecycleDashboardSource:
    account: RecurrentLifecycleAccountV1
    marked_state: RecurrentMarkedAccountStateV1


def source_provider_from_recurrent_coordinator(
    coordinator: RecurrentLifecycleCoordinatorV1,
) -> Callable[[], RecurrentLifecycleDashboardSource | None]:
    def provider() -> RecurrentLifecycleDashboardSource | None:
        pair = coordinator.current_dashboard_pair()
        if pair is None:
            return None
        account, marked_state = pair
        return RecurrentLifecycleDashboardSource(
            account=account,
            marked_state=marked_state,
        )

    return provider


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _validate_source(source: RecurrentLifecycleDashboardSource) -> None:
    account = source.account
    state = account.state
    marked = source.marked_state

    if (
        state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(state)
    ):
        raise RecurrentLifecycleDashboardError(
            "recurrent account-state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != recurrent_lifecycle_ledger_fingerprint(account.ledger)
    ):
        raise RecurrentLifecycleDashboardError(
            "recurrent ledger fingerprint mismatch"
        )
    expected = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected != state.state_fingerprint:
        raise RecurrentLifecycleDashboardError(
            "recurrent ledger does not terminate at current state"
        )

    if (
        marked.contract_fingerprint
        != RECURRENT_MARKED_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentLifecycleDashboardError(
            "recurrent marked-state contract fingerprint mismatch"
        )
    if (
        marked.state_fingerprint
        != recurrent_marked_account_state_fingerprint(marked)
    ):
        raise RecurrentLifecycleDashboardError(
            "recurrent marked-state fingerprint mismatch"
        )
    if marked.source_account_state_fingerprint != state.state_fingerprint:
        raise RecurrentLifecycleDashboardError(
            "marked state does not bind current recurrent account"
        )
    if marked.valuation_utc < state.as_of_utc:
        raise RecurrentLifecycleDashboardError(
            "marked state predates current recurrent account"
        )

    copied = (
        (marked.initial_equity, state.initial_equity, "initial equity"),
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
            marked.stock_reserved_capital,
            state.stock_reserved_capital,
            "stock reserved capital",
        ),
        (
            marked.option_reserved_capital,
            state.option_reserved_capital,
            "option reserved capital",
        ),
        (
            marked.open_entry_book_value_dollars,
            state.open_entry_book_value_dollars,
            "open entry book value",
        ),
    )
    for left, right, label in copied:
        if not _same(left, right):
            raise RecurrentLifecycleDashboardError(
                f"recurrent dashboard {label} drifted from account state"
            )
    if marked.closed_trade_count != len(state.closed_trades):
        raise RecurrentLifecycleDashboardError(
            "recurrent closed-trade count drifted from account state"
        )

    positions = {
        item.position_fingerprint: item
        for item in state.open_positions
    }
    marks = {
        item.position_fingerprint: item
        for item in marked.marked_positions
    }
    if set(positions) != set(marks):
        raise RecurrentLifecycleDashboardError(
            "recurrent dashboard requires exact current mark coverage"
        )
    for fingerprint, position in positions.items():
        mark = marks[fingerprint]
        if (
            mark.decision_record_fingerprint
            != position.decision_record_fingerprint
            or mark.instrument_kind != position.instrument_kind
            or mark.instrument_id != position.instrument_id
            or mark.ticker != position.ticker
            or mark.option_contract_ticker
            != position.option_contract_ticker
            or mark.option_contract_type
            != position.option_contract_type
        ):
            raise RecurrentLifecycleDashboardError(
                "recurrent marked/open position lineage mismatch"
            )
        if not _same(mark.quantity, position.quantity):
            raise RecurrentLifecycleDashboardError(
                "recurrent marked/open quantity mismatch"
            )
        if not _same(
            mark.contract_multiplier,
            position.contract_multiplier,
        ):
            raise RecurrentLifecycleDashboardError(
                "recurrent marked/open multiplier mismatch"
            )
        if not _same(
            mark.entry_book_value_dollars,
            position.entry_book_value_dollars,
        ):
            raise RecurrentLifecycleDashboardError(
                "recurrent marked/open book-value mismatch"
            )
        if not _same(mark.entry_fees_dollars, position.entry_fees_dollars):
            raise RecurrentLifecycleDashboardError(
                "recurrent marked/open entry-fee mismatch"
            )


def _open_positions(
    source: RecurrentLifecycleDashboardSource,
) -> list[dict[str, object]]:
    state = source.account.state
    marks = {
        item.position_fingerprint: item
        for item in source.marked_state.marked_positions
    }
    rows: list[dict[str, object]] = []
    for position in state.open_positions[:RECURRENT_LIFECYCLE_RECORD_LIMIT]:
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
                "entry_book_value_dollars": (
                    position.entry_book_value_dollars
                ),
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
                "position_state": "OPEN_RECURRENT_SIMULATION_MARKED",
            }
        )
    return rows


def _closed_trades(
    source: RecurrentLifecycleDashboardSource,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    closed = source.account.state.closed_trades
    for trade in reversed(closed[-RECURRENT_LIFECYCLE_RECORD_LIMIT:]):
        rows.append(
            {
                "closed_trade_fingerprint": trade.history_fingerprint,
                "origin": trade.origin.value,
                "source_state_contract_fingerprint": (
                    trade.source_state_contract_fingerprint
                ),
                "source_state_fingerprint": (
                    trade.source_state_fingerprint
                ),
                "source_record_fingerprint": (
                    trade.source_record_fingerprint
                ),
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
                "entry_book_value_dollars": (
                    trade.entry_book_value_dollars
                ),
                "entry_fees_dollars": trade.entry_fees_dollars,
                "gross_exit_proceeds_dollars": (
                    trade.gross_exit_proceeds_dollars
                ),
                "exit_fees_dollars": trade.exit_fees_dollars,
                "net_exit_proceeds_dollars": (
                    trade.net_exit_proceeds_dollars
                ),
                "account_realized_pnl_delta_dollars": (
                    trade.account_realized_pnl_delta_dollars
                ),
                "lifetime_trade_net_pnl_dollars": (
                    trade.lifetime_trade_net_pnl_dollars
                ),
            }
        )
    return rows


class RecurrentLifecycleDashboardService:
    """Read-only projection over an injected recurrent engine-owned pair."""

    def __init__(
        self,
        *,
        source_provider: (
            Callable[[], RecurrentLifecycleDashboardSource | None] | None
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
                RECURRENT_LIFECYCLE_DASHBOARD_CONTRACT_VERSION
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
                "source": "RECURRENT_ENGINE_OWNED_INJECTED_STATE",
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
                "reason": "RECURRENT_LIFECYCLE_SOURCE_NOT_INJECTED",
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
                    "reason": "RECURRENT_LIFECYCLE_SOURCE_NOT_AVAILABLE",
                }
                return payload
            if not isinstance(source, RecurrentLifecycleDashboardSource):
                raise RecurrentLifecycleDashboardError(
                    "source provider returned unsupported recurrent object"
                )
            _validate_source(source)
        except Exception as exc:
            payload = self._base(now_utc=now_utc, status="INVALID")
            payload["error"] = type(exc).__name__
            payload["health"] = {
                "engine_source_connected": True,
                "source_valid": False,
                "reason": "RECURRENT_LIFECYCLE_SOURCE_FAILED_VALIDATION",
            }
            return payload

        account = source.account
        state = account.state
        marked = source.marked_state
        open_rows = _open_positions(source)
        closed_rows = _closed_trades(source)

        payload = self._base(now_utc=now_utc, status="AVAILABLE")
        payload.update(
            {
                "source": {
                    "account_state_fingerprint": state.state_fingerprint,
                    "account_ledger_fingerprint": (
                        account.ledger.ledger_fingerprint
                    ),
                    "marked_state_fingerprint": marked.state_fingerprint,
                    "book_as_of_utc": state.as_of_utc.isoformat(),
                    "valuation_utc": marked.valuation_utc.isoformat(),
                    "complete_mark_coverage": (
                        marked.complete_mark_coverage
                    ),
                    "source_kind": "RECURRENT_LIFECYCLE_ACCOUNT",
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
                        state.stock_reserved_capital
                    ),
                    "remaining_option_reserved_capital": (
                        state.option_reserved_capital
                    ),
                    "open_entry_book_value_dollars": (
                        state.open_entry_book_value_dollars
                    ),
                    "marked_open_position_value_dollars": (
                        marked.marked_open_position_value_dollars
                    ),
                    "snapshot_kind": (
                        "ENGINE_OWNED_RECURRENT_SIMULATION_LIFECYCLE_CURRENT"
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


__all__ = [
    "RECURRENT_LIFECYCLE_DASHBOARD_CONTRACT_VERSION",
    "RecurrentLifecycleDashboardError",
    "RecurrentLifecycleDashboardService",
    "RecurrentLifecycleDashboardSource",
    "source_provider_from_recurrent_coordinator",
]
