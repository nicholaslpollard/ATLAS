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
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingModel,
    RecurrentFundingTermsV1,
    recurrent_entry_fill_fingerprint,
    recurrent_funding_terms_fingerprint,
)
from packages.simulation.recurrent_entry_evidence_contract import (
    RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT,
    RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_VERSION,
    RecurrentLifecycleAccountStateV1,
    RecurrentLifecycleAccountV1,
    RecurrentLifecycleEventKind,
    RecurrentLifecycleLedgerEventV1,
    RecurrentLifecycleLedgerV1,
    recurrent_lifecycle_account_state_fingerprint,
    recurrent_lifecycle_ledger_fingerprint,
)
from packages.simulation.recurrent_position_contract import (
    RECURRENT_POSITION_TRANSITION_CONTRACT_FINGERPRINT,
)
from packages.simulation.simulated_fill import simulated_reservation_fingerprint


_TOLERANCE = 1e-9


class RecurrentPositionTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class RecurrentPositionTransitionV1:
    account: RecurrentLifecycleAccountV1
    event: RecurrentLifecycleLedgerEventV1 | None
    position: SimulatedOpenPositionV1 | None
    position_fingerprint: str
    idempotent_reuse: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RecurrentPositionBatchResultV1:
    account: RecurrentLifecycleAccountV1
    source_state_fingerprint: str
    ordered_fill_fingerprints: tuple[str, ...]
    transitions: tuple[RecurrentPositionTransitionV1, ...]


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


def _zero(value: float) -> float:
    return 0.0 if abs(value) <= _TOLERANCE else value


def _validate_account(account: RecurrentLifecycleAccountV1) -> None:
    if (
        account.state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentPositionTransitionError(
            "recurrent lifecycle account contract fingerprint mismatch"
        )
    if (
        account.state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(account.state)
    ):
        raise RecurrentPositionTransitionError(
            "recurrent lifecycle account state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != recurrent_lifecycle_ledger_fingerprint(account.ledger)
    ):
        raise RecurrentPositionTransitionError(
            "recurrent lifecycle ledger fingerprint mismatch"
        )
    expected = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected != account.state.state_fingerprint:
        raise RecurrentPositionTransitionError(
            "recurrent lifecycle ledger does not terminate at current state"
        )


def _build_state(
    *,
    previous: RecurrentLifecycleAccountStateV1,
    as_of_utc,
    cash: float,
    cumulative_entry_fees_dollars: float,
    stock_reservations: Sequence[SimulatedStockReservationV2],
    option_reservations: Sequence[SimulatedOptionReservationV2],
    open_positions: Sequence[SimulatedOpenPositionV1],
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
    positions = tuple(
        sorted(
            open_positions,
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
        cumulative_entry_fees_dollars=_zero(
            cumulative_entry_fees_dollars
        ),
        cumulative_exit_fees_dollars=previous.cumulative_exit_fees_dollars,
        cumulative_account_realized_pnl_dollars=(
            previous.cumulative_account_realized_pnl_dollars
        ),
        cumulative_lifetime_trade_net_pnl_dollars=(
            previous.cumulative_lifetime_trade_net_pnl_dollars
        ),
        cash=_zero(cash),
        account_book_equity=_zero(
            previous.initial_equity
            - cumulative_entry_fees_dollars
            + previous.cumulative_account_realized_pnl_dollars
        ),
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
        stock_reservations=stocks,
        option_reservations=options,
        open_positions=positions,
        closed_trades=previous.closed_trades,
    )


def _active_reservation(
    account: RecurrentLifecycleAccountV1,
    fill: RecurrentEntryFillEvidenceV1,
):
    source = (
        account.state.stock_reservations
        if fill.instrument_kind == InstrumentKind.STOCK
        else account.state.option_reservations
    )
    matches = tuple(
        item
        for item in source
        if item.decision_record_fingerprint
        == fill.decision_record_fingerprint
    )
    if len(matches) != 1:
        raise RecurrentPositionTransitionError(
            "exact current recurrent reservation is required"
        )
    reservation = matches[0]
    if (
        simulated_reservation_fingerprint(reservation)
        != fill.active_reservation_fingerprint
    ):
        raise RecurrentPositionTransitionError(
            "current recurrent reservation fingerprint mismatch"
        )
    if not _same(
        reservation.reserved_capital,
        fill.reserved_capital_dollars,
    ):
        raise RecurrentPositionTransitionError(
            "current recurrent reserved-capital mismatch"
        )
    return reservation


def _validate_evidence(
    *,
    evidence_source_state_fingerprint: str,
    evidence_source_cash: float,
    current_account: RecurrentLifecycleAccountV1,
    fill: RecurrentEntryFillEvidenceV1,
    funding: RecurrentFundingTermsV1,
):
    if fill.contract_fingerprint != RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT:
        raise RecurrentPositionTransitionError(
            "recurrent entry-fill contract fingerprint mismatch"
        )
    if funding.contract_fingerprint != RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT:
        raise RecurrentPositionTransitionError(
            "recurrent funding contract fingerprint mismatch"
        )
    if fill.fill_fingerprint != recurrent_entry_fill_fingerprint(fill):
        raise RecurrentPositionTransitionError(
            "recurrent entry-fill fingerprint mismatch"
        )
    if funding.terms_fingerprint != recurrent_funding_terms_fingerprint(
        funding
    ):
        raise RecurrentPositionTransitionError(
            "recurrent funding fingerprint mismatch"
        )
    if (
        fill.recurrent_state_fingerprint
        != evidence_source_state_fingerprint
        or funding.recurrent_state_fingerprint
        != evidence_source_state_fingerprint
    ):
        raise RecurrentPositionTransitionError(
            "fill/funding must bind the recurrent evidence source state"
        )

    pairs = (
        (funding.fill_fingerprint, fill.fill_fingerprint, "fill"),
        (
            funding.active_reservation_fingerprint,
            fill.active_reservation_fingerprint,
            "reservation",
        ),
        (
            funding.decision_record_fingerprint,
            fill.decision_record_fingerprint,
            "decision",
        ),
        (
            funding.candidate_fingerprint,
            fill.candidate_fingerprint,
            "candidate",
        ),
        (funding.instrument_kind, fill.instrument_kind, "instrument kind"),
        (funding.direction, fill.direction, "direction"),
    )
    for left, right, label in pairs:
        if left != right:
            raise RecurrentPositionTransitionError(
                f"recurrent funding {label} lineage mismatch"
            )
    if not funding.fully_funded:
        raise RecurrentPositionTransitionError(
            "recurrent funding terms must be fully funded"
        )

    reservation = _active_reservation(current_account, fill)

    if fill.instrument_kind == InstrumentKind.STOCK:
        required = (
            fill.gross_fill_notional_dollars
            + fill.entry_fees_dollars
        )
        expected_supplemental = max(
            0.0,
            required - reservation.reserved_capital,
        )
        expected_unspent = max(
            0.0,
            reservation.reserved_capital - required,
        )
        if funding.funding_model != RecurrentFundingModel.CASH_ONLY_STOCK_LONG:
            raise RecurrentPositionTransitionError(
                "recurrent stock funding model mismatch"
            )
    elif fill.instrument_kind == InstrumentKind.OPTION:
        if (
            fill.cash_debit_dollars is None
            or fill.unspent_reserved_capital_dollars is None
        ):
            raise RecurrentPositionTransitionError(
                "recurrent option fill is missing reserved debit semantics"
            )
        required = fill.cash_debit_dollars
        expected_supplemental = 0.0
        expected_unspent = fill.unspent_reserved_capital_dollars
        if (
            funding.funding_model
            != RecurrentFundingModel.RESERVED_LONG_OPTION_DEBIT
        ):
            raise RecurrentPositionTransitionError(
                "recurrent option funding model mismatch"
            )
        if (
            fill.option_reservation_terms_fingerprint
            != reservation.reservation_terms_fingerprint
            or fill.option_economics_result_fingerprint
            != reservation.option_economics_result_fingerprint
        ):
            raise RecurrentPositionTransitionError(
                "recurrent option reservation lineage mismatch"
            )
    else:
        raise RecurrentPositionTransitionError(
            "unsupported recurrent position instrument kind"
        )

    arithmetic = (
        (funding.required_cash_dollars, required, "required cash"),
        (
            funding.reserved_capital_dollars,
            reservation.reserved_capital,
            "reserved capital",
        ),
        (
            funding.supplemental_unreserved_cash_required_dollars,
            expected_supplemental,
            "supplemental cash",
        ),
        (
            funding.unspent_reserved_capital_dollars,
            expected_unspent,
            "unspent reserve",
        ),
        (
            funding.projected_unreserved_cash_after_entry_dollars,
            evidence_source_cash
            - expected_supplemental
            + expected_unspent,
            "source projected cash",
        ),
    )
    for actual, expected, label in arithmetic:
        if not _same(actual, expected):
            raise RecurrentPositionTransitionError(
                f"recurrent funding {label} mismatch"
            )
    return reservation


def _build_position(
    *,
    fill: RecurrentEntryFillEvidenceV1,
    funding: RecurrentFundingTermsV1,
    reservation: SimulatedStockReservationV2 | SimulatedOptionReservationV2,
) -> SimulatedOpenPositionV1:
    if fill.instrument_kind == InstrumentKind.STOCK:
        stock_exposure = fill.gross_fill_notional_dollars
        option_premium = 0.0
        signed_delta = 0.0
        abs_delta = 0.0
    else:
        if not isinstance(reservation, SimulatedOptionReservationV2):
            raise RecurrentPositionTransitionError(
                "recurrent option entry requires option reservation"
            )
        stock_exposure = 0.0
        option_premium = fill.gross_fill_notional_dollars
        signed_delta = reservation.signed_delta_equivalent_notional
        abs_delta = reservation.abs_delta_equivalent_notional

    return SimulatedOpenPositionV1(
        source_account_state_fingerprint=fill.recurrent_state_fingerprint,
        decision_record_fingerprint=fill.decision_record_fingerprint,
        candidate_fingerprint=fill.candidate_fingerprint,
        fill_fingerprint=fill.fill_fingerprint,
        funding_terms_fingerprint=funding.terms_fingerprint,
        reservation_fingerprint=fill.active_reservation_fingerprint,
        option_reservation_terms_fingerprint=(
            fill.option_reservation_terms_fingerprint
        ),
        option_economics_result_fingerprint=(
            fill.option_economics_result_fingerprint
        ),
        instrument_kind=fill.instrument_kind,
        instrument_id=fill.instrument_id,
        ticker=fill.ticker,
        direction=fill.direction,
        candidate_identifier=fill.candidate_identifier,
        option_contract_ticker=fill.option_contract_ticker,
        option_contract_type=fill.option_contract_type,
        opened_utc=fill.filled_utc,
        quantity=fill.quantity,
        quantity_unit=fill.quantity_unit,
        entry_price_per_unit=fill.fill_price_per_unit,
        contract_multiplier=fill.contract_multiplier,
        entry_book_value_dollars=fill.gross_fill_notional_dollars,
        entry_fees_dollars=fill.entry_fees_dollars,
        all_in_cash_cost_basis_dollars=funding.required_cash_dollars,
        original_reserved_capital_dollars=reservation.reserved_capital,
        supplemental_cash_consumed_dollars=(
            funding.supplemental_unreserved_cash_required_dollars
        ),
        unspent_reserve_returned_dollars=(
            funding.unspent_reserved_capital_dollars
        ),
        stock_gross_entry_exposure_dollars=stock_exposure,
        option_premium_at_risk_dollars=option_premium,
        option_signed_delta_equivalent_entry_reference_dollars=signed_delta,
        option_abs_delta_equivalent_entry_reference_dollars=abs_delta,
        reason_codes=(
            "EXACT_RECURRENT_RESERVATION_FILL_FUNDING_LINEAGE",
            "ENTRY_FEE_EXPENSED_ONCE",
            "RECURRENT_RESERVATION_CONSUMED_ONCE",
            "CANONICAL_CLOSED_HISTORY_PRESERVED",
        ),
    )


def _prior_open_event(
    account: RecurrentLifecycleAccountV1,
    fill: RecurrentEntryFillEvidenceV1,
) -> RecurrentLifecycleLedgerEventV1 | None:
    return next(
        (
            event
            for event in account.ledger.events
            if event.kind == RecurrentLifecycleEventKind.OPEN_POSITION
            and (
                event.fill_fingerprint == fill.fill_fingerprint
                or event.decision_record_fingerprint
                == fill.decision_record_fingerprint
            )
        ),
        None,
    )


def _apply_entry(
    account: RecurrentLifecycleAccountV1,
    *,
    evidence_source_state_fingerprint: str,
    evidence_source_cash: float,
    require_current_source_state: bool,
    fill: RecurrentEntryFillEvidenceV1,
    funding: RecurrentFundingTermsV1,
) -> RecurrentPositionTransitionV1:
    _validate_account(account)

    prior_event = _prior_open_event(account, fill)
    if prior_event is not None:
        if (
            prior_event.fill_fingerprint == fill.fill_fingerprint
            and prior_event.funding_terms_fingerprint
            == funding.terms_fingerprint
        ):
            current_position = next(
                (
                    item
                    for item in account.state.open_positions
                    if item.position_fingerprint
                    == prior_event.position_fingerprint
                ),
                None,
            )
            return RecurrentPositionTransitionV1(
                account=account,
                event=None,
                position=current_position,
                position_fingerprint=prior_event.position_fingerprint or "",
                idempotent_reuse=True,
                reason_codes=(
                    "RECURRENT_ENTRY_ALREADY_APPLIED",
                ),
            )
        raise RecurrentPositionTransitionError(
            "conflicting recurrent fill for already-applied decision"
        )

    if any(
        item.decision_record_fingerprint
        == fill.decision_record_fingerprint
        for item in account.state.closed_trades
    ):
        raise RecurrentPositionTransitionError(
            "recurrent decision is already present in closed history"
        )

    if require_current_source_state and (
        fill.recurrent_state_fingerprint
        != account.state.state_fingerprint
        or funding.recurrent_state_fingerprint
        != account.state.state_fingerprint
    ):
        raise RecurrentPositionTransitionError(
            "fill/funding must bind the recurrent evidence source state"
        )

    reservation = _validate_evidence(
        evidence_source_state_fingerprint=evidence_source_state_fingerprint,
        evidence_source_cash=evidence_source_cash,
        current_account=account,
        fill=fill,
        funding=funding,
    )

    if fill.filled_utc < account.state.as_of_utc:
        raise RecurrentPositionTransitionError(
            "fill timestamp cannot precede current recurrent account state"
        )

    supplemental = funding.supplemental_unreserved_cash_required_dollars
    unspent = funding.unspent_reserved_capital_dollars
    if account.state.cash + _TOLERANCE < supplemental:
        raise RecurrentPositionTransitionError(
            "insufficient current recurrent cash after competing entries"
        )
    new_cash = account.state.cash - supplemental + unspent
    if new_cash < -_TOLERANCE:
        raise RecurrentPositionTransitionError(
            "recurrent entry would create negative cash"
        )

    position = _build_position(
        fill=fill,
        funding=funding,
        reservation=reservation,
    )
    if fill.instrument_kind == InstrumentKind.STOCK:
        stocks = tuple(
            item
            for item in account.state.stock_reservations
            if item.decision_record_fingerprint
            != fill.decision_record_fingerprint
        )
        options = account.state.option_reservations
        stock_capital_delta = -reservation.reserved_capital
        option_capital_delta = 0.0
        stock_gross_delta = -reservation.gross_notional
        option_signed_delta = 0.0
        option_abs_delta = 0.0
        option_max_loss_delta = 0.0
        option_premium_delta = 0.0
    else:
        stocks = account.state.stock_reservations
        options = tuple(
            item
            for item in account.state.option_reservations
            if item.decision_record_fingerprint
            != fill.decision_record_fingerprint
        )
        stock_capital_delta = 0.0
        option_capital_delta = -reservation.reserved_capital
        stock_gross_delta = 0.0
        option_signed_delta = -reservation.signed_delta_equivalent_notional
        option_abs_delta = -reservation.abs_delta_equivalent_notional
        option_max_loss_delta = -reservation.max_loss_cash
        option_premium_delta = -reservation.premium_at_risk

    next_state = _build_state(
        previous=account.state,
        as_of_utc=fill.filled_utc,
        cash=new_cash,
        cumulative_entry_fees_dollars=(
            account.state.cumulative_entry_fees_dollars
            + fill.entry_fees_dollars
        ),
        stock_reservations=stocks,
        option_reservations=options,
        open_positions=account.state.open_positions + (position,),
    )

    event = RecurrentLifecycleLedgerEventV1(
        sequence=len(account.ledger.events) + 1,
        occurred_utc=fill.filled_utc,
        kind=RecurrentLifecycleEventKind.OPEN_POSITION,
        decision_record_fingerprint=fill.decision_record_fingerprint,
        reservation_fingerprint=fill.active_reservation_fingerprint,
        reservation_terms_fingerprint=(
            fill.option_reservation_terms_fingerprint
        ),
        option_economics_result_fingerprint=(
            fill.option_economics_result_fingerprint
        ),
        fill_fingerprint=fill.fill_fingerprint,
        funding_terms_fingerprint=funding.terms_fingerprint,
        position_fingerprint=position.position_fingerprint,
        exit_fill_fingerprint=None,
        closed_trade_fingerprint=None,
        candidate_identifier=fill.candidate_identifier,
        option_contract_ticker=fill.option_contract_ticker,
        instrument_id=fill.instrument_id,
        ticker=fill.ticker,
        direction=fill.direction.value,
        cash_delta_dollars=_zero(new_cash - account.state.cash),
        stock_reserved_capital_delta_dollars=_zero(stock_capital_delta),
        option_reserved_capital_delta_dollars=_zero(option_capital_delta),
        stock_reserved_gross_notional_delta_dollars=_zero(stock_gross_delta),
        option_reserved_signed_delta_delta_dollars=_zero(option_signed_delta),
        option_reserved_abs_delta_delta_dollars=_zero(option_abs_delta),
        option_reserved_max_loss_delta_dollars=_zero(option_max_loss_delta),
        option_reserved_premium_at_risk_delta_dollars=_zero(
            option_premium_delta
        ),
        open_entry_book_value_delta_dollars=(
            position.entry_book_value_dollars
        ),
        entry_fee_delta_dollars=position.entry_fees_dollars,
        exit_fee_delta_dollars=0.0,
        account_realized_pnl_delta_dollars=0.0,
        lifetime_trade_net_pnl_delta_dollars=0.0,
        open_stock_gross_exposure_delta_dollars=(
            position.stock_gross_entry_exposure_dollars
        ),
        open_option_signed_delta_reference_delta_dollars=(
            position.option_signed_delta_equivalent_entry_reference_dollars
        ),
        open_option_abs_delta_reference_delta_dollars=(
            position.option_abs_delta_equivalent_entry_reference_dollars
        ),
        open_option_premium_at_risk_delta_dollars=(
            position.option_premium_at_risk_dollars
        ),
        before_state_fingerprint=account.state.state_fingerprint,
        after_state_fingerprint=next_state.state_fingerprint,
        reason_codes=(
            "RECURRENT_RESERVATION_CONSUMED",
            "RECURRENT_POSITION_CREATED_ENTRY_BOOK_ONLY",
            "ENTRY_FEE_EXPENSED_ONCE",
            "CANONICAL_CLOSED_HISTORY_PRESERVED",
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
    return RecurrentPositionTransitionV1(
        account=next_account,
        event=event,
        position=position,
        position_fingerprint=position.position_fingerprint,
        idempotent_reuse=False,
        reason_codes=("RECURRENT_POSITION_OPENED",),
    )


def apply_recurrent_entry_v1(
    account: RecurrentLifecycleAccountV1,
    *,
    fill: RecurrentEntryFillEvidenceV1,
    funding: RecurrentFundingTermsV1,
) -> RecurrentPositionTransitionV1:
    _validate_account(account)
    return _apply_entry(
        account,
        evidence_source_state_fingerprint=account.state.state_fingerprint,
        evidence_source_cash=account.state.cash,
        require_current_source_state=True,
        fill=fill,
        funding=funding,
    )


def apply_recurrent_entry_batch_v1(
    account: RecurrentLifecycleAccountV1,
    entries: Sequence[
        tuple[RecurrentEntryFillEvidenceV1, RecurrentFundingTermsV1]
    ],
) -> RecurrentPositionBatchResultV1:
    _validate_account(account)
    source_state_fingerprint = account.state.state_fingerprint
    source_cash = account.state.cash

    for fill, funding in entries:
        if (
            fill.recurrent_state_fingerprint != source_state_fingerprint
            or funding.recurrent_state_fingerprint != source_state_fingerprint
        ):
            raise RecurrentPositionTransitionError(
                "recurrent entry batch requires one common source snapshot"
            )

    ordered = tuple(
        sorted(
            entries,
            key=lambda item: (
                item[0].filled_utc,
                item[0].fill_fingerprint,
            ),
        )
    )
    current = account
    transitions: list[RecurrentPositionTransitionV1] = []
    for fill, funding in ordered:
        transition = _apply_entry(
            current,
            evidence_source_state_fingerprint=source_state_fingerprint,
            evidence_source_cash=source_cash,
            require_current_source_state=False,
            fill=fill,
            funding=funding,
        )
        transitions.append(transition)
        current = transition.account
    return RecurrentPositionBatchResultV1(
        account=current,
        source_state_fingerprint=source_state_fingerprint,
        ordered_fill_fingerprints=tuple(
            fill.fill_fingerprint for fill, _ in ordered
        ),
        transitions=tuple(transitions),
    )


def verify_recurrent_entry_replay_v1(
    *,
    initial_account: RecurrentLifecycleAccountV1,
    expected_account: RecurrentLifecycleAccountV1,
    entries: Sequence[
        tuple[RecurrentEntryFillEvidenceV1, RecurrentFundingTermsV1]
    ],
) -> None:
    replay = apply_recurrent_entry_batch_v1(
        initial_account,
        entries,
    ).account
    if replay.state.state_fingerprint != expected_account.state.state_fingerprint:
        raise RecurrentPositionTransitionError(
            "recurrent entry replay state fingerprint mismatch"
        )
    if (
        replay.ledger.ledger_fingerprint
        != expected_account.ledger.ledger_fingerprint
    ):
        raise RecurrentPositionTransitionError(
            "recurrent entry replay ledger fingerprint mismatch"
        )


__all__ = [
    "RECURRENT_POSITION_TRANSITION_CONTRACT_FINGERPRINT",
    "RecurrentPositionBatchResultV1",
    "RecurrentPositionTransitionError",
    "RecurrentPositionTransitionV1",
    "apply_recurrent_entry_batch_v1",
    "apply_recurrent_entry_v1",
    "verify_recurrent_entry_replay_v1",
]
