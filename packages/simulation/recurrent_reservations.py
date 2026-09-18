from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from packages.execution.trade_expression import InstrumentKind, SelectionKind
from packages.simulation.account_state_v2 import (
    SimulatedOptionReservationV2,
    SimulatedStockReservationV2,
)
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
from packages.simulation.recurrent_lifecycle_state import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION,
    RecurrentLifecycleAccountError,
    RecurrentLifecycleAccountStateV1,
    RecurrentLifecycleAccountV1,
    RecurrentLifecycleEventKind,
    RecurrentLifecycleLedgerEventV1,
    RecurrentLifecycleLedgerV1,
    recurrent_lifecycle_account_state_fingerprint,
    recurrent_lifecycle_ledger_fingerprint,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_reservation_contract import (
    RECURRENT_RESERVATION_TRANSITION_CONTRACT_FINGERPRINT,
)


_TOLERANCE = 1e-9


class RecurrentReservationError(ValueError):
    pass


@dataclass(frozen=True)
class RecurrentReservationTransitionV1:
    account: RecurrentLifecycleAccountV1
    event: RecurrentLifecycleLedgerEventV1 | None
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RecurrentReservationBatchResultV1:
    account: RecurrentLifecycleAccountV1
    ordered_decision_fingerprints: tuple[str, ...]
    transitions: tuple[RecurrentReservationTransitionV1, ...]


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


def _validate_account(account: RecurrentLifecycleAccountV1) -> None:
    if (
        account.state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentReservationError(
            "recurrent lifecycle account contract fingerprint mismatch"
        )
    if (
        account.state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(account.state)
    ):
        raise RecurrentReservationError(
            "recurrent lifecycle account state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != recurrent_lifecycle_ledger_fingerprint(account.ledger)
    ):
        raise RecurrentReservationError(
            "recurrent lifecycle ledger fingerprint mismatch"
        )
    expected = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected != account.state.state_fingerprint:
        raise RecurrentReservationError(
            "recurrent lifecycle ledger does not terminate at current state"
        )


def _build_state(
    *,
    previous: RecurrentLifecycleAccountStateV1,
    as_of_utc,
    cash: float,
    stock_reservations: Sequence[SimulatedStockReservationV2],
    option_reservations: Sequence[SimulatedOptionReservationV2],
) -> RecurrentLifecycleAccountStateV1:
    stocks = tuple(
        sorted(
            stock_reservations,
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    options = tuple(
        sorted(
            option_reservations,
            key=lambda item: item.decision_record_fingerprint,
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
        cumulative_exit_fees_dollars=previous.cumulative_exit_fees_dollars,
        cumulative_account_realized_pnl_dollars=(
            previous.cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            previous.cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=_zero(cash),
        account_book_equity=previous.account_book_equity,
        stock_reserved_capital=_zero(
            sum(item.reserved_capital for item in stocks)
        ),
        option_reserved_capital=_zero(
            sum(item.reserved_capital for item in options)
        ),
        stock_reserved_gross_notional=_zero(
            sum(item.gross_notional for item in stocks)
        ),
        option_reserved_signed_delta_equivalent_notional=_zero(
            sum(item.signed_delta_equivalent_notional for item in options)
        ),
        option_reserved_abs_delta_equivalent_notional=_zero(
            sum(item.abs_delta_equivalent_notional for item in options)
        ),
        option_reserved_max_loss_cash=_zero(
            sum(item.max_loss_cash for item in options)
        ),
        option_reserved_premium_at_risk=_zero(
            sum(item.premium_at_risk for item in options)
        ),
        open_entry_book_value_dollars=previous.open_entry_book_value_dollars,
        open_stock_gross_entry_exposure_dollars=(
            previous.open_stock_gross_entry_exposure_dollars
        ),
        open_option_entry_book_value_dollars=(
            previous.open_option_entry_book_value_dollars
        ),
        open_option_signed_delta_equivalent_entry_reference_dollars=(
            previous.open_option_signed_delta_equivalent_entry_reference_dollars
        ),
        open_option_abs_delta_equivalent_entry_reference_dollars=(
            previous.open_option_abs_delta_equivalent_entry_reference_dollars
        ),
        open_option_premium_at_risk_dollars=(
            previous.open_option_premium_at_risk_dollars
        ),
        stock_reservations=stocks,
        option_reservations=options,
        open_positions=previous.open_positions,
        closed_trades=previous.closed_trades,
    )


def _unchanged_state(
    account: RecurrentLifecycleAccountV1,
    *,
    as_of_utc,
) -> RecurrentLifecycleAccountStateV1:
    return _build_state(
        previous=account.state,
        as_of_utc=as_of_utc,
        cash=account.state.cash,
        stock_reservations=account.state.stock_reservations,
        option_reservations=account.state.option_reservations,
    )


def _prior_decision_event(
    account: RecurrentLifecycleAccountV1,
    decision_record_fingerprint: str,
) -> RecurrentLifecycleLedgerEventV1 | None:
    return next(
        (
            event
            for event in account.ledger.events
            if event.decision_record_fingerprint == decision_record_fingerprint
            and event.kind
            in {
                RecurrentLifecycleEventKind.RESERVE_STOCK,
                RecurrentLifecycleEventKind.RESERVE_OPTION,
                RecurrentLifecycleEventKind.ABSTAIN,
                RecurrentLifecycleEventKind.REJECT_MISSING_OPTION_TERMS,
                RecurrentLifecycleEventKind.REJECT_INSUFFICIENT_CAPITAL,
            }
        ),
        None,
    )


def _state_contains_decision(
    state: RecurrentLifecycleAccountStateV1,
    decision_record_fingerprint: str,
) -> bool:
    return any(
        item.decision_record_fingerprint == decision_record_fingerprint
        for item in (
            *state.stock_reservations,
            *state.option_reservations,
            *state.open_positions,
            *state.closed_trades,
        )
    )


def _append_event(
    *,
    account: RecurrentLifecycleAccountV1,
    next_state: RecurrentLifecycleAccountStateV1,
    kind: RecurrentLifecycleEventKind,
    record: SimulationDecisionRecord,
    reservation_fingerprint: str | None = None,
    reservation_terms_fingerprint: str | None = None,
    option_economics_result_fingerprint: str | None = None,
    candidate_identifier: str | None = None,
    option_contract_ticker: str | None = None,
    cash_delta: float = 0.0,
    stock_capital_delta: float = 0.0,
    option_capital_delta: float = 0.0,
    stock_gross_delta: float = 0.0,
    option_signed_delta: float = 0.0,
    option_abs_delta: float = 0.0,
    option_max_loss_delta: float = 0.0,
    option_premium_delta: float = 0.0,
    reason_codes: tuple[str, ...],
) -> RecurrentReservationTransitionV1:
    event = RecurrentLifecycleLedgerEventV1(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=record.decision_created_utc,
        kind=kind,
        decision_record_fingerprint=record.record_fingerprint,
        reservation_fingerprint=reservation_fingerprint,
        reservation_terms_fingerprint=reservation_terms_fingerprint,
        option_economics_result_fingerprint=(
            option_economics_result_fingerprint
        ),
        fill_fingerprint=None,
        funding_terms_fingerprint=None,
        position_fingerprint=None,
        exit_fill_fingerprint=None,
        closed_trade_fingerprint=None,
        candidate_identifier=candidate_identifier,
        option_contract_ticker=option_contract_ticker,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        cash_delta_dollars=_zero(cash_delta),
        stock_reserved_capital_delta_dollars=_zero(stock_capital_delta),
        option_reserved_capital_delta_dollars=_zero(option_capital_delta),
        stock_reserved_gross_notional_delta_dollars=_zero(stock_gross_delta),
        option_reserved_signed_delta_delta_dollars=_zero(option_signed_delta),
        option_reserved_abs_delta_delta_dollars=_zero(option_abs_delta),
        option_reserved_max_loss_delta_dollars=_zero(option_max_loss_delta),
        option_reserved_premium_at_risk_delta_dollars=_zero(
            option_premium_delta
        ),
        open_entry_book_value_delta_dollars=0.0,
        entry_fee_delta_dollars=0.0,
        exit_fee_delta_dollars=0.0,
        account_realized_pnl_delta_dollars=0.0,
        lifetime_trade_net_pnl_delta_dollars=0.0,
        open_stock_gross_exposure_delta_dollars=0.0,
        open_option_signed_delta_reference_delta_dollars=0.0,
        open_option_abs_delta_reference_delta_dollars=0.0,
        open_option_premium_at_risk_delta_dollars=0.0,
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
        reason_codes=reason_codes,
    )
    ledger = RecurrentLifecycleLedgerV1(
        contract_version=account.ledger.contract_version,
        contract_fingerprint=account.ledger.contract_fingerprint,
        bootstrap_state_fingerprint=account.ledger.bootstrap_state_fingerprint,
        bootstrap_ledger_fingerprint=account.ledger.bootstrap_ledger_fingerprint,
        initial_state_fingerprint=account.ledger.initial_state_fingerprint,
        events=account.ledger.events + (event,),
    )
    next_account = RecurrentLifecycleAccountV1(
        state=next_state,
        ledger=ledger,
    )
    return RecurrentReservationTransitionV1(
        account=next_account,
        event=event,
        idempotent_reuse=False,
        reason_codes=reason_codes,
    )


def _validate_option_terms(
    *,
    record: SimulationDecisionRecord,
    terms: LongOptionReservationTerms,
) -> str:
    if (
        terms.contract_fingerprint
        != LONG_OPTION_RESERVATION_CONTRACT_FINGERPRINT
    ):
        raise RecurrentReservationError(
            "long-option reservation contract fingerprint mismatch"
        )
    if terms.decision_record_fingerprint != record.record_fingerprint:
        raise RecurrentReservationError(
            "option reservation decision lineage mismatch"
        )
    if terms.source_forecast_fingerprint != record.forecast_fingerprint:
        raise RecurrentReservationError(
            "option reservation forecast lineage mismatch"
        )
    decision = record.trade_expression_decision
    candidate = decision.chosen_candidate
    if candidate is None or candidate.kind != InstrumentKind.OPTION:
        raise RecurrentReservationError(
            "option reservation requires selected option candidate"
        )
    if terms.chosen_candidate_identifier != candidate.identifier:
        raise RecurrentReservationError(
            "option reservation candidate identifier mismatch"
        )
    if (
        terms.chosen_candidate_fingerprint
        != economic_candidate_fingerprint(candidate)
    ):
        raise RecurrentReservationError(
            "option reservation candidate fingerprint mismatch"
        )
    if (
        terms.instrument_id != record.forecast.instrument_id
        or terms.ticker != record.forecast.ticker
    ):
        raise RecurrentReservationError(
            "option reservation underlying identity mismatch"
        )
    if terms.direction != record.forecast.direction:
        raise RecurrentReservationError(
            "option reservation direction mismatch"
        )
    return long_option_reservation_terms_fingerprint(terms)


def apply_recurrent_decision_reservation_v1(
    account: RecurrentLifecycleAccountV1,
    record: SimulationDecisionRecord,
    *,
    option_terms: LongOptionReservationTerms | None = None,
) -> RecurrentReservationTransitionV1:
    _validate_account(account)
    if (
        record.contract_fingerprint
        != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT
    ):
        raise RecurrentReservationError(
            "simulation decision-record contract fingerprint mismatch"
        )
    record_fp = record.record_fingerprint

    prior = _prior_decision_event(account, record_fp)
    if prior is not None:
        if (
            prior.kind == RecurrentLifecycleEventKind.RESERVE_OPTION
            and option_terms is not None
        ):
            supplied = long_option_reservation_terms_fingerprint(option_terms)
            if prior.reservation_terms_fingerprint != supplied:
                raise RecurrentReservationError(
                    "duplicate option decision supplied different reservation terms"
                )
        return RecurrentReservationTransitionV1(
            account=account,
            event=None,
            idempotent_reuse=True,
            reason_codes=("RECURRENT_DECISION_ALREADY_APPLIED",),
        )

    if _state_contains_decision(account.state, record_fp):
        return RecurrentReservationTransitionV1(
            account=account,
            event=None,
            idempotent_reuse=True,
            reason_codes=("DECISION_ALREADY_PRESENT_IN_RECURRENT_HISTORY",),
        )

    if record.decision_created_utc < account.state.as_of_utc:
        raise RecurrentReservationError(
            "decision timestamp cannot precede current recurrent account state"
        )

    decision = record.trade_expression_decision
    if decision.selection_kind == SelectionKind.ABSTAIN:
        if option_terms is not None:
            raise RecurrentReservationError(
                "option reservation terms cannot accompany abstention"
            )
        next_state = _unchanged_state(
            account,
            as_of_utc=record.decision_created_utc,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=RecurrentLifecycleEventKind.ABSTAIN,
            record=record,
            reason_codes=(
                "RECURRENT_DECISION_ABSTAINED",
                *decision.reason_codes,
            ),
        )

    candidate = decision.chosen_candidate
    if candidate is None:
        raise RecurrentReservationError(
            "non-abstain decision must carry a chosen candidate"
        )

    if decision.selection_kind == SelectionKind.STOCK:
        if option_terms is not None:
            raise RecurrentReservationError(
                "option reservation terms cannot accompany stock decision"
            )
        if candidate.kind != InstrumentKind.STOCK:
            raise RecurrentReservationError(
                "stock selection does not carry a stock candidate"
            )
        stock_candidate = record.stock_economics.candidate
        if candidate.identifier != stock_candidate.identifier:
            raise RecurrentReservationError(
                "chosen stock candidate identifier mismatch"
            )
        if (
            economic_candidate_fingerprint(candidate)
            != economic_candidate_fingerprint(stock_candidate)
        ):
            raise RecurrentReservationError(
                "chosen stock candidate fingerprint mismatch"
            )
        capital = float(record.stock_economics.capital_required_dollars)
        gross = float(record.stock_economics.position_notional_dollars)
        if not _same(candidate.capital_required, capital):
            raise RecurrentReservationError(
                "stock capital lineage mismatch"
            )
        if capital > account.state.cash and not _same(
            capital,
            account.state.cash,
        ):
            next_state = _unchanged_state(
                account,
                as_of_utc=record.decision_created_utc,
            )
            return _append_event(
                account=account,
                next_state=next_state,
                kind=(
                    RecurrentLifecycleEventKind.REJECT_INSUFFICIENT_CAPITAL
                ),
                record=record,
                candidate_identifier=candidate.identifier,
                reason_codes=(
                    "INSUFFICIENT_CURRENT_RECURRENT_CASH",
                    "STOCK_RESERVATION_REJECTED",
                ),
            )
        reservation = SimulatedStockReservationV2(
            decision_record_fingerprint=record_fp,
            candidate_identifier=candidate.identifier,
            instrument_id=record.forecast.instrument_id,
            ticker=record.forecast.ticker,
            direction=record.forecast.direction.value,
            reserved_capital=capital,
            gross_notional=gross,
            reserved_utc=record.decision_created_utc,
        )
        from packages.simulation.simulated_fill import (
            simulated_reservation_fingerprint,
        )
        reservation_fp = simulated_reservation_fingerprint(reservation)
        next_state = _build_state(
            previous=account.state,
            as_of_utc=record.decision_created_utc,
            cash=account.state.cash - capital,
            stock_reservations=(
                account.state.stock_reservations + (reservation,)
            ),
            option_reservations=account.state.option_reservations,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=RecurrentLifecycleEventKind.RESERVE_STOCK,
            record=record,
            reservation_fingerprint=reservation_fp,
            candidate_identifier=candidate.identifier,
            cash_delta=-capital,
            stock_capital_delta=capital,
            stock_gross_delta=gross,
            reason_codes=(
                "RECURRENT_STOCK_CAPITAL_RESERVED",
                "CURRENT_RECURRENT_CASH_REDUCED",
                "OPEN_AND_CANONICAL_CLOSED_HISTORY_PRESERVED",
            ),
        )

    if (
        decision.selection_kind != SelectionKind.OPTION
        or candidate.kind != InstrumentKind.OPTION
    ):
        raise RecurrentReservationError(
            "unsupported recurrent reservation selection kind"
        )

    if option_terms is None:
        next_state = _unchanged_state(
            account,
            as_of_utc=record.decision_created_utc,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=RecurrentLifecycleEventKind.REJECT_MISSING_OPTION_TERMS,
            record=record,
            candidate_identifier=candidate.identifier,
            reason_codes=("LONG_OPTION_RESERVATION_TERMS_REQUIRED",),
        )

    terms_fp = _validate_option_terms(
        record=record,
        terms=option_terms,
    )
    capital = float(option_terms.reserved_capital_dollars)
    if capital > account.state.cash and not _same(capital, account.state.cash):
        next_state = _unchanged_state(
            account,
            as_of_utc=record.decision_created_utc,
        )
        return _append_event(
            account=account,
            next_state=next_state,
            kind=(
                RecurrentLifecycleEventKind.REJECT_INSUFFICIENT_CAPITAL
            ),
            record=record,
            reservation_terms_fingerprint=terms_fp,
            option_economics_result_fingerprint=(
                option_terms.option_economics_result_fingerprint
            ),
            candidate_identifier=candidate.identifier,
            option_contract_ticker=option_terms.option_contract_ticker,
            reason_codes=(
                "INSUFFICIENT_CURRENT_RECURRENT_CASH",
                "OPTION_RESERVATION_REJECTED",
            ),
        )

    reservation = SimulatedOptionReservationV2(
        decision_record_fingerprint=record_fp,
        reservation_terms_fingerprint=terms_fp,
        option_economics_result_fingerprint=(
            option_terms.option_economics_result_fingerprint
        ),
        candidate_identifier=candidate.identifier,
        option_contract_ticker=option_terms.option_contract_ticker,
        instrument_id=record.forecast.instrument_id,
        ticker=record.forecast.ticker,
        direction=record.forecast.direction.value,
        reserved_capital=capital,
        max_loss_cash=float(option_terms.max_loss_cash_dollars),
        premium_at_risk=float(option_terms.premium_at_risk_dollars),
        signed_delta_equivalent_notional=float(
            option_terms.signed_delta_equivalent_notional_dollars
        ),
        abs_delta_equivalent_notional=float(
            option_terms.abs_delta_equivalent_notional_dollars
        ),
        reserved_utc=record.decision_created_utc,
    )
    from packages.simulation.simulated_fill import (
        simulated_reservation_fingerprint,
    )
    reservation_fp = simulated_reservation_fingerprint(reservation)
    next_state = _build_state(
        previous=account.state,
        as_of_utc=record.decision_created_utc,
        cash=account.state.cash - capital,
        stock_reservations=account.state.stock_reservations,
        option_reservations=(
            account.state.option_reservations + (reservation,)
        ),
    )
    return _append_event(
        account=account,
        next_state=next_state,
        kind=RecurrentLifecycleEventKind.RESERVE_OPTION,
        record=record,
        reservation_fingerprint=reservation_fp,
        reservation_terms_fingerprint=terms_fp,
        option_economics_result_fingerprint=(
            option_terms.option_economics_result_fingerprint
        ),
        candidate_identifier=candidate.identifier,
        option_contract_ticker=option_terms.option_contract_ticker,
        cash_delta=-capital,
        option_capital_delta=capital,
        option_signed_delta=reservation.signed_delta_equivalent_notional,
        option_abs_delta=reservation.abs_delta_equivalent_notional,
        option_max_loss_delta=reservation.max_loss_cash,
        option_premium_delta=reservation.premium_at_risk,
        reason_codes=(
            "RECURRENT_LONG_OPTION_CAPITAL_RESERVED",
            "CURRENT_RECURRENT_CASH_REDUCED",
            "RESERVED_OPTION_EXPOSURE_RECORDED_SEPARATELY",
            "OPEN_AND_CANONICAL_CLOSED_HISTORY_PRESERVED",
        ),
    )


def apply_recurrent_reservation_batch_v1(
    account: RecurrentLifecycleAccountV1,
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
) -> RecurrentReservationBatchResultV1:
    ordered = tuple(
        sorted(
            decisions,
            key=lambda item: (
                item[0].decision_created_utc,
                item[0].record_fingerprint,
            ),
        )
    )
    current = account
    transitions: list[RecurrentReservationTransitionV1] = []
    for record, terms in ordered:
        transition = apply_recurrent_decision_reservation_v1(
            current,
            record,
            option_terms=terms,
        )
        transitions.append(transition)
        current = transition.account
    return RecurrentReservationBatchResultV1(
        account=current,
        ordered_decision_fingerprints=tuple(
            record.record_fingerprint for record, _ in ordered
        ),
        transitions=tuple(transitions),
    )


def verify_recurrent_reservation_replay_v1(
    *,
    initial_account: RecurrentLifecycleAccountV1,
    expected_account: RecurrentLifecycleAccountV1,
    decisions: Sequence[
        tuple[SimulationDecisionRecord, LongOptionReservationTerms | None]
    ],
) -> None:
    replay = apply_recurrent_reservation_batch_v1(
        initial_account,
        decisions,
    ).account
    if replay.state.state_fingerprint != expected_account.state.state_fingerprint:
        raise RecurrentReservationError(
            "recurrent reservation replay state fingerprint mismatch"
        )
    if (
        replay.ledger.ledger_fingerprint
        != expected_account.ledger.ledger_fingerprint
    ):
        raise RecurrentReservationError(
            "recurrent reservation replay ledger fingerprint mismatch"
        )


__all__ = [
    "RECURRENT_RESERVATION_TRANSITION_CONTRACT_FINGERPRINT",
    "RecurrentReservationBatchResultV1",
    "RecurrentReservationError",
    "RecurrentReservationTransitionV1",
    "apply_recurrent_decision_reservation_v1",
    "apply_recurrent_reservation_batch_v1",
    "verify_recurrent_reservation_replay_v1",
]
