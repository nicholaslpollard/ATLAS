from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from packages.execution.trade_expression import InstrumentKind
from packages.simulation.account_state_v2 import (
    SimulatedOptionReservationV2,
    SimulatedStockReservationV2,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1
from packages.simulation.recurrent_close_position_contract import (
    RECURRENT_CLOSE_POSITION_TRANSITION_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillEvidenceV1,
    recurrent_exit_fill_fingerprint,
)
from packages.simulation.recurrent_exit_fill_contract import (
    RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION,
    RecurrentClosedTradeOrigin,
    RecurrentClosedTradeV1,
    RecurrentLifecycleAccountStateV1,
    RecurrentLifecycleAccountV1,
    RecurrentLifecycleEventKind,
    RecurrentLifecycleLedgerEventV1,
    RecurrentLifecycleLedgerV1,
    recurrent_closed_trade_fingerprint,
    recurrent_lifecycle_account_state_fingerprint,
    recurrent_lifecycle_ledger_fingerprint,
)


_TOLERANCE = 1e-9


class RecurrentClosePositionError(ValueError):
    pass


@dataclass(frozen=True)
class RecurrentClosePositionTransitionV1:
    account: RecurrentLifecycleAccountV1
    event: RecurrentLifecycleLedgerEventV1 | None
    closed_trade: RecurrentClosedTradeV1
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RecurrentClosePositionBatchResultV1:
    account: RecurrentLifecycleAccountV1
    source_state_fingerprint: str
    ordered_exit_fill_fingerprints: tuple[str, ...]
    transitions: tuple[RecurrentClosePositionTransitionV1, ...]


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


def _validate_account(account: RecurrentLifecycleAccountV1) -> None:
    if (
        account.state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentClosePositionError(
            "recurrent lifecycle account contract fingerprint mismatch"
        )
    if (
        account.state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(account.state)
    ):
        raise RecurrentClosePositionError(
            "recurrent lifecycle account state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != recurrent_lifecycle_ledger_fingerprint(account.ledger)
    ):
        raise RecurrentClosePositionError(
            "recurrent lifecycle ledger fingerprint mismatch"
        )
    expected = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected != account.state.state_fingerprint:
        raise RecurrentClosePositionError(
            "recurrent lifecycle ledger does not terminate at current state"
        )


def _build_state(
    *,
    previous: RecurrentLifecycleAccountStateV1,
    as_of_utc,
    cash: float,
    cumulative_exit_fees_dollars: float,
    cumulative_account_realized_pnl_dollars: float,
    cumulative_lifetime_trade_net_pnl_dollars: float,
    open_positions: Sequence[SimulatedOpenPositionV1],
    closed_trades: Sequence[RecurrentClosedTradeV1],
) -> RecurrentLifecycleAccountStateV1:
    positions = tuple(
        sorted(
            open_positions,
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    closed = tuple(
        sorted(
            closed_trades,
            key=lambda item: (
                item.exited_utc,
                item.exit_fill_fingerprint,
            ),
        )
    )
    return RecurrentLifecycleAccountStateV1(
        contract_version=previous.contract_version,
        contract_fingerprint=previous.contract_fingerprint,
        bootstrap_contract_fingerprint=previous.bootstrap_contract_fingerprint,
        bootstrap_state_fingerprint=previous.bootstrap_state_fingerprint,
        bootstrap_ledger_fingerprint=previous.bootstrap_ledger_fingerprint,
        as_of_utc=as_of_utc,
        initial_equity=previous.initial_equity,
        cumulative_entry_fees_dollars=previous.cumulative_entry_fees_dollars,
        cumulative_exit_fees_dollars=_zero(
            cumulative_exit_fees_dollars
        ),
        cumulative_account_realized_pnl_dollars=_zero(
            cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=_zero(
            cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=_zero(cash),
        account_book_equity=_zero(
            previous.initial_equity
            - previous.cumulative_entry_fees_dollars
            + cumulative_account_realized_pnl_dollars
        ),
        stock_reserved_capital=previous.stock_reserved_capital,
        option_reserved_capital=previous.option_reserved_capital,
        stock_reserved_gross_notional=previous.stock_reserved_gross_notional,
        option_reserved_signed_delta_equivalent_notional=(
            previous.option_reserved_signed_delta_equivalent_notional
        ),
        option_reserved_abs_delta_equivalent_notional=(
            previous.option_reserved_abs_delta_equivalent_notional
        ),
        option_reserved_max_loss_cash=previous.option_reserved_max_loss_cash,
        option_reserved_premium_at_risk=previous.option_reserved_premium_at_risk,
        open_entry_book_value_dollars=_zero(
            sum(item.entry_book_value_dollars for item in positions)
        ),
        open_stock_gross_entry_exposure_dollars=_zero(
            sum(
                item.stock_gross_entry_exposure_dollars
                for item in positions
            )
        ),
        open_option_entry_book_value_dollars=_zero(
            sum(
                item.entry_book_value_dollars
                for item in positions
                if item.instrument_kind == InstrumentKind.OPTION
            )
        ),
        open_option_signed_delta_equivalent_entry_reference_dollars=_zero(
            sum(
                item.option_signed_delta_equivalent_entry_reference_dollars
                for item in positions
            )
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=_zero(
            sum(
                item.option_abs_delta_equivalent_entry_reference_dollars
                for item in positions
            )
        ),
        open_option_premium_at_risk_dollars=_zero(
            sum(item.option_premium_at_risk_dollars for item in positions)
        ),
        stock_reservations=previous.stock_reservations,
        option_reservations=previous.option_reservations,
        open_positions=positions,
        closed_trades=closed,
    )


def _find_position(
    account: RecurrentLifecycleAccountV1,
    fill: RecurrentExitFillEvidenceV1,
) -> SimulatedOpenPositionV1:
    matches = tuple(
        item
        for item in account.state.open_positions
        if item.position_fingerprint == fill.position_fingerprint
    )
    if len(matches) != 1:
        raise RecurrentClosePositionError(
            "exact current recurrent open position is required"
        )
    return matches[0]


def _validate_fill_lineage(
    *,
    evidence_source_state_fingerprint: str,
    fill: RecurrentExitFillEvidenceV1,
    position: SimulatedOpenPositionV1,
) -> None:
    if fill.contract_fingerprint != RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT:
        raise RecurrentClosePositionError(
            "recurrent exit-fill contract fingerprint mismatch"
        )
    if fill.exit_fill_fingerprint != recurrent_exit_fill_fingerprint(fill):
        raise RecurrentClosePositionError(
            "recurrent exit-fill fingerprint mismatch"
        )
    if (
        fill.source_account_contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentClosePositionError(
            "recurrent exit source account contract mismatch"
        )
    if fill.source_recurrent_state_fingerprint != evidence_source_state_fingerprint:
        raise RecurrentClosePositionError(
            "exit fill must bind the recurrent evidence source state"
        )

    pairs = (
        (
            fill.position_source_account_state_fingerprint,
            position.source_account_state_fingerprint,
            "position source account",
        ),
        (
            fill.decision_record_fingerprint,
            position.decision_record_fingerprint,
            "decision",
        ),
        (fill.candidate_fingerprint, position.candidate_fingerprint, "candidate"),
        (fill.entry_fill_fingerprint, position.fill_fingerprint, "entry fill"),
        (
            fill.funding_terms_fingerprint,
            position.funding_terms_fingerprint,
            "funding",
        ),
        (
            fill.reservation_fingerprint,
            position.reservation_fingerprint,
            "reservation",
        ),
        (fill.instrument_kind, position.instrument_kind, "instrument kind"),
        (fill.instrument_id, position.instrument_id, "instrument id"),
        (fill.ticker, position.ticker, "ticker"),
        (fill.direction, position.direction, "direction"),
        (
            fill.candidate_identifier,
            position.candidate_identifier,
            "candidate identifier",
        ),
        (
            fill.option_contract_ticker,
            position.option_contract_ticker,
            "option ticker",
        ),
        (
            fill.option_contract_type,
            position.option_contract_type,
            "option type",
        ),
        (
            fill.option_reservation_terms_fingerprint,
            position.option_reservation_terms_fingerprint,
            "option reservation terms",
        ),
        (
            fill.option_economics_result_fingerprint,
            position.option_economics_result_fingerprint,
            "option economics",
        ),
        (fill.opened_utc, position.opened_utc, "opened timestamp"),
        (fill.quantity_unit, position.quantity_unit, "quantity unit"),
    )
    for left, right, label in pairs:
        if left != right:
            raise RecurrentClosePositionError(
                f"recurrent exit {label} lineage mismatch"
            )
    if not _same(fill.quantity, position.quantity):
        raise RecurrentClosePositionError(
            "recurrent exit quantity lineage mismatch"
        )
    if not _same(fill.contract_multiplier, position.contract_multiplier):
        raise RecurrentClosePositionError(
            "recurrent exit multiplier lineage mismatch"
        )


def _closed_trade(
    *,
    evidence_source_state_fingerprint: str,
    position: SimulatedOpenPositionV1,
    fill: RecurrentExitFillEvidenceV1,
) -> RecurrentClosedTradeV1:
    realized = (
        fill.net_exit_proceeds_dollars
        - position.entry_book_value_dollars
    )
    lifetime = realized - position.entry_fees_dollars
    return RecurrentClosedTradeV1(
        origin=RecurrentClosedTradeOrigin.RECURRENT_ACCOUNT_V1,
        source_state_contract_fingerprint=(
            RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
        ),
        source_state_fingerprint=evidence_source_state_fingerprint,
        source_record_fingerprint=fill.exit_fill_fingerprint,
        position_fingerprint=position.position_fingerprint,
        exit_fill_fingerprint=fill.exit_fill_fingerprint,
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
        exited_utc=fill.exited_utc,
        hold_seconds=(fill.exited_utc - position.opened_utc).total_seconds(),
        quantity=position.quantity,
        quantity_unit=position.quantity_unit,
        entry_price_per_unit=position.entry_price_per_unit,
        exit_price_per_unit=fill.exit_price_per_unit,
        contract_multiplier=position.contract_multiplier,
        entry_book_value_dollars=position.entry_book_value_dollars,
        entry_fees_dollars=position.entry_fees_dollars,
        gross_exit_proceeds_dollars=fill.gross_exit_proceeds_dollars,
        exit_fees_dollars=fill.exit_fees_dollars,
        net_exit_proceeds_dollars=fill.net_exit_proceeds_dollars,
        account_realized_pnl_delta_dollars=realized,
        lifetime_trade_net_pnl_dollars=lifetime,
        reason_codes=(
            "NATIVE_RECURRENT_CLOSE_POSITION",
            "EXACT_RECURRENT_POSITION_EXIT_LINEAGE",
            "ENTRY_FEE_ALREADY_EXPENSED_ACCOUNT_PNL_EXCLUDES_RECHARGE",
            "LIFETIME_TRADE_NET_PNL_INCLUDES_ENTRY_AND_EXIT_FEES_ONCE",
        ),
    )


def _prior_close_event(
    account: RecurrentLifecycleAccountV1,
    fill: RecurrentExitFillEvidenceV1,
) -> RecurrentLifecycleLedgerEventV1 | None:
    return next(
        (
            event
            for event in account.ledger.events
            if event.kind == RecurrentLifecycleEventKind.CLOSE_POSITION
            and (
                event.exit_fill_fingerprint == fill.exit_fill_fingerprint
                or event.position_fingerprint == fill.position_fingerprint
            )
        ),
        None,
    )


def _apply_close(
    account: RecurrentLifecycleAccountV1,
    *,
    evidence_source_state_fingerprint: str,
    fill: RecurrentExitFillEvidenceV1,
) -> RecurrentClosePositionTransitionV1:
    _validate_account(account)

    prior = _prior_close_event(account, fill)
    if prior is not None:
        if prior.exit_fill_fingerprint != fill.exit_fill_fingerprint:
            raise RecurrentClosePositionError(
                "conflicting recurrent close for already-closed position"
            )
        trade = next(
            (
                item
                for item in account.state.closed_trades
                if item.history_fingerprint == prior.closed_trade_fingerprint
            ),
            None,
        )
        if trade is None:
            raise RecurrentClosePositionError(
                "idempotent recurrent close is missing canonical closed trade"
            )
        return RecurrentClosePositionTransitionV1(
            account=account,
            event=None,
            closed_trade=trade,
            idempotent_reuse=True,
            reason_codes=("RECURRENT_CLOSE_ALREADY_APPLIED",),
        )

    if any(
        item.position_fingerprint == fill.position_fingerprint
        for item in account.state.closed_trades
    ):
        raise RecurrentClosePositionError(
            "conflicting recurrent close for position already in closed history"
        )
    if fill.exited_utc < account.state.as_of_utc:
        raise RecurrentClosePositionError(
            "exit timestamp cannot precede current recurrent account state"
        )

    position = _find_position(account, fill)
    _validate_fill_lineage(
        evidence_source_state_fingerprint=evidence_source_state_fingerprint,
        fill=fill,
        position=position,
    )
    trade = _closed_trade(
        evidence_source_state_fingerprint=evidence_source_state_fingerprint,
        position=position,
        fill=fill,
    )
    remaining = tuple(
        item
        for item in account.state.open_positions
        if item.position_fingerprint != position.position_fingerprint
    )
    next_state = _build_state(
        previous=account.state,
        as_of_utc=fill.exited_utc,
        cash=account.state.cash + fill.net_exit_proceeds_dollars,
        cumulative_exit_fees_dollars=(
            account.state.cumulative_exit_fees_dollars
            + fill.exit_fees_dollars
        ),
        cumulative_account_realized_pnl_dollars=(
            account.state.cumulative_account_realized_pnl_dollars
            + trade.account_realized_pnl_delta_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            account.state.cumulative_lifetime_trade_net_pnl_dollars
            + trade.lifetime_trade_net_pnl_dollars
        ),
        open_positions=remaining,
        closed_trades=account.state.closed_trades + (trade,),
    )
    event = RecurrentLifecycleLedgerEventV1(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=fill.exited_utc,
        kind=RecurrentLifecycleEventKind.CLOSE_POSITION,
        decision_record_fingerprint=position.decision_record_fingerprint,
        reservation_fingerprint=position.reservation_fingerprint,
        reservation_terms_fingerprint=(
            position.option_reservation_terms_fingerprint
        ),
        option_economics_result_fingerprint=(
            position.option_economics_result_fingerprint
        ),
        fill_fingerprint=position.fill_fingerprint,
        funding_terms_fingerprint=position.funding_terms_fingerprint,
        position_fingerprint=position.position_fingerprint,
        exit_fill_fingerprint=fill.exit_fill_fingerprint,
        closed_trade_fingerprint=trade.history_fingerprint,
        candidate_identifier=position.candidate_identifier,
        option_contract_ticker=position.option_contract_ticker,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        direction=position.direction.value,
        cash_delta_dollars=fill.net_exit_proceeds_dollars,
        stock_reserved_capital_delta_dollars=0.0,
        option_reserved_capital_delta_dollars=0.0,
        stock_reserved_gross_notional_delta_dollars=0.0,
        option_reserved_signed_delta_delta_dollars=0.0,
        option_reserved_abs_delta_delta_dollars=0.0,
        option_reserved_max_loss_delta_dollars=0.0,
        option_reserved_premium_at_risk_delta_dollars=0.0,
        open_entry_book_value_delta_dollars=-position.entry_book_value_dollars,
        entry_fee_delta_dollars=0.0,
        exit_fee_delta_dollars=fill.exit_fees_dollars,
        account_realized_pnl_delta_dollars=(
            trade.account_realized_pnl_delta_dollars
        ),
        lifetime_trade_net_pnl_delta_dollars=(
            trade.lifetime_trade_net_pnl_dollars
        ),
        open_stock_gross_exposure_delta_dollars=(
            -position.stock_gross_entry_exposure_dollars
        ),
        open_option_signed_delta_reference_delta_dollars=(
            -position.option_signed_delta_equivalent_entry_reference_dollars
        ),
        open_option_abs_delta_reference_delta_dollars=(
            -position.option_abs_delta_equivalent_entry_reference_dollars
        ),
        open_option_premium_at_risk_delta_dollars=(
            -position.option_premium_at_risk_dollars
        ),
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
        reason_codes=(
            "RECURRENT_POSITION_REMOVED_ONCE",
            "NET_EXIT_PROCEEDS_RETURNED_TO_RECURRENT_CASH",
            "CANONICAL_CLOSED_HISTORY_APPENDED",
            "ACCOUNT_AND_LIFETIME_REALIZED_PNL_RECONCILED",
        ),
    )
    ledger = RecurrentLifecycleLedgerV1(
        contract_version=RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION,
        contract_fingerprint=RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
        bootstrap_state_fingerprint=account.ledger.bootstrap_state_fingerprint,
        bootstrap_ledger_fingerprint=account.ledger.bootstrap_ledger_fingerprint,
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = RecurrentLifecycleAccountV1(
        state=next_state,
        ledger=ledger,
    )
    return RecurrentClosePositionTransitionV1(
        account=next_account,
        event=event,
        closed_trade=trade,
        idempotent_reuse=False,
        reason_codes=("RECURRENT_POSITION_CLOSED",),
    )


def apply_recurrent_close_position_v1(
    account: RecurrentLifecycleAccountV1,
    *,
    fill: RecurrentExitFillEvidenceV1,
) -> RecurrentClosePositionTransitionV1:
    _validate_account(account)
    return _apply_close(
        account,
        evidence_source_state_fingerprint=account.state.state_fingerprint,
        fill=fill,
    )


def apply_recurrent_close_position_batch_v1(
    account: RecurrentLifecycleAccountV1,
    fills: Sequence[RecurrentExitFillEvidenceV1],
) -> RecurrentClosePositionBatchResultV1:
    _validate_account(account)
    source_state_fingerprint = account.state.state_fingerprint
    for fill in fills:
        if fill.source_recurrent_state_fingerprint != source_state_fingerprint:
            raise RecurrentClosePositionError(
                "recurrent close batch requires one common source snapshot"
            )
    ordered = tuple(
        sorted(
            fills,
            key=lambda item: (
                item.exited_utc,
                item.exit_fill_fingerprint,
            ),
        )
    )
    current = account
    transitions: list[RecurrentClosePositionTransitionV1] = []
    for fill in ordered:
        transition = _apply_close(
            current,
            evidence_source_state_fingerprint=source_state_fingerprint,
            fill=fill,
        )
        transitions.append(transition)
        current = transition.account
    return RecurrentClosePositionBatchResultV1(
        account=current,
        source_state_fingerprint=source_state_fingerprint,
        ordered_exit_fill_fingerprints=tuple(
            fill.exit_fill_fingerprint for fill in ordered
        ),
        transitions=tuple(transitions),
    )


def verify_recurrent_close_position_replay_v1(
    *,
    initial_account: RecurrentLifecycleAccountV1,
    expected_account: RecurrentLifecycleAccountV1,
    fills: Sequence[RecurrentExitFillEvidenceV1],
) -> None:
    replay = apply_recurrent_close_position_batch_v1(
        initial_account,
        fills,
    ).account
    if replay.state.state_fingerprint != expected_account.state.state_fingerprint:
        raise RecurrentClosePositionError(
            "recurrent close replay state fingerprint mismatch"
        )
    if replay.ledger.ledger_fingerprint != expected_account.ledger.ledger_fingerprint:
        raise RecurrentClosePositionError(
            "recurrent close replay ledger fingerprint mismatch"
        )


__all__ = [
    "RECURRENT_CLOSE_POSITION_TRANSITION_CONTRACT_FINGERPRINT",
    "RecurrentClosePositionBatchResultV1",
    "RecurrentClosePositionError",
    "RecurrentClosePositionTransitionV1",
    "apply_recurrent_close_position_batch_v1",
    "apply_recurrent_close_position_v1",
    "verify_recurrent_close_position_replay_v1",
]
