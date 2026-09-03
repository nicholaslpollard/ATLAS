from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd

from packages.backtesting.reference_portfolio_policy import (
    REFERENCE_PORTFOLIO_ACCOUNT_RISK_FRACTION,
    REFERENCE_PORTFOLIO_BROKER_WRITES,
    REFERENCE_PORTFOLIO_ENTRY_COST_BPS,
    REFERENCE_PORTFOLIO_INITIAL_EQUITY,
    REFERENCE_PORTFOLIO_LIVE_WRITES,
    REFERENCE_PORTFOLIO_MAX_GROSS_FRACTION,
    REFERENCE_PORTFOLIO_MAX_OPEN_POSITIONS,
    REFERENCE_PORTFOLIO_MAX_POSITION_FRACTION,
    REFERENCE_PORTFOLIO_MAX_POSITIONS_PER_FAMILY,
    REFERENCE_PORTFOLIO_PAPER_SUBMITS,
    REFERENCE_PORTFOLIO_PROVIDER_WRITES,
    REFERENCE_PORTFOLIO_EXIT_COST_BPS,
    reference_portfolio_policy_fingerprint,
)
from packages.backtesting.reference_strategy_runner import (
    PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_END,
    PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START,
    ProtectedMasterWindowError,
    reference_input_fingerprint,
)
from packages.schemas.reference_portfolio import (
    REFERENCE_PORTFOLIO_DECISION_CONTRACT_VERSION,
    REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
    REFERENCE_SIMULATED_ORDER_CONTRACT_VERSION,
    ReferencePortfolioDecision,
    ReferencePortfolioDecisionStatus,
    ReferencePortfolioEquityPoint,
    ReferencePortfolioPositionOutcome,
    ReferencePortfolioReplay,
    ReferenceSimulatedOrderEvent,
    ReferenceSimulatedOrderKind,
    ReferenceSimulatedOrderTiming,
)
from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import (
    OpportunityOutcomeStatus,
    ReferenceHistoricalRun,
    ReferenceOpportunityRecord,
)
from packages.strategies.reference_library import REFERENCE_STRATEGY_CATALOG


REFERENCE_PORTFOLIO_REPLAY_ENGINE_CONTRACT_VERSION = (
    "a34-reference-account-engine-v1-open-exit-entry-intraday-exit-close-mark"
)


class ReferencePortfolioReplayError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _ActivePosition:
    opportunity: ReferenceOpportunityRecord
    decision: ReferencePortfolioDecision
    quantity: int
    entry_transaction_cost: float


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _decision_id(item: ReferenceOpportunityRecord) -> str:
    return _stable_hash(
        {
            "contract_version": REFERENCE_PORTFOLIO_DECISION_CONTRACT_VERSION,
            "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
            "opportunity_id": item.opportunity_id,
        }
    )


def _event_id(
    item: ReferenceOpportunityRecord,
    decision_id: str,
    kind: ReferenceSimulatedOrderKind,
) -> str:
    return _stable_hash(
        {
            "contract_version": REFERENCE_SIMULATED_ORDER_CONTRACT_VERSION,
            "decision_id": decision_id,
            "opportunity_id": item.opportunity_id,
            "kind": kind.value,
        }
    )


def _non_admission(
    item: ReferenceOpportunityRecord,
    status: ReferencePortfolioDecisionStatus,
    reasons: tuple[str, ...],
) -> ReferencePortfolioDecision:
    return ReferencePortfolioDecision(
        decision_id=_decision_id(item),
        opportunity_id=item.opportunity_id,
        strategy_id=item.strategy_id,
        family=item.family,
        direction=item.direction,
        instrument_id=item.instrument_id,
        ticker=item.ticker,
        signal_session=item.signal_session,
        requested_entry_session=item.entry_session,
        status=status,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def _bar_map(frame: pd.DataFrame) -> tuple[dict[tuple[str, date], dict[str, float]], tuple[date, ...]]:
    required = {"instrument_id", "session_date", "open", "close"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ReferencePortfolioReplayError(
            "reference portfolio replay is missing columns: " + ", ".join(missing)
        )
    local = frame.loc[:, sorted(required)].copy()
    local["instrument_id"] = local["instrument_id"].astype(str)
    local["session_date"] = pd.to_datetime(local["session_date"], errors="raise").dt.date
    if local.duplicated(["instrument_id", "session_date"]).any():
        raise ReferencePortfolioReplayError("portfolio replay bars contain duplicate identity sessions")
    result: dict[tuple[str, date], dict[str, float]] = {}
    for row in local.itertuples(index=False):
        open_price = float(row.open)
        close_price = float(row.close)
        if not all(math.isfinite(value) and value > 0.0 for value in (open_price, close_price)):
            raise ReferencePortfolioReplayError("portfolio replay bars contain invalid prices")
        result[(str(row.instrument_id), row.session_date)] = {
            "open": open_price,
            "close": close_price,
        }
    return result, tuple(sorted(set(local["session_date"])))


def _bar_price(
    bars: dict[tuple[str, date], dict[str, float]],
    instrument_id: str,
    session: date,
    field: str,
) -> float:
    try:
        return bars[(instrument_id, session)][field]
    except KeyError as exc:
        raise ReferencePortfolioReplayError(
            f"active portfolio position lacks {field} valuation on {session}: {instrument_id}"
        ) from exc


def _summaries(
    decisions: tuple[ReferencePortfolioDecision, ...],
    outcomes: tuple[ReferencePortfolioPositionOutcome, ...],
) -> tuple[dict[str, dict[str, int | float | None]], dict[str, dict[str, int | float | None]]]:
    def one(key: str, values: tuple[str, ...]) -> dict[str, dict[str, int | float | None]]:
        result: dict[str, dict[str, int | float | None]] = {}
        for value in values:
            selected = [item for item in decisions if str(getattr(item, key)) == value]
            completed = [item for item in outcomes if str(getattr(item, key)) == value]
            net = [item.net_pnl for item in completed]
            result[value] = {
                "signals": len(selected),
                "admitted": sum(
                    item.status == ReferencePortfolioDecisionStatus.ADMITTED
                    for item in selected
                ),
                "rejected": sum(
                    item.status == ReferencePortfolioDecisionStatus.REJECTED
                    for item in selected
                ),
                "not_eligible": sum(
                    item.status == ReferencePortfolioDecisionStatus.NOT_ELIGIBLE
                    for item in selected
                ),
                "completed": len(completed),
                "net_pnl": sum(net),
                "mean_net_pnl": None if not net else sum(net) / len(net),
            }
        return result

    strategy_values = tuple(item.strategy_id for item in REFERENCE_STRATEGY_CATALOG.all())
    family_values = tuple(
        sorted({item.family.value for item in REFERENCE_STRATEGY_CATALOG.all()})
    )
    strategy = one("strategy_id", strategy_values)
    family: dict[str, dict[str, int | float | None]] = {}
    for family_value in family_values:
        selected = [item for item in decisions if item.family.value == family_value]
        completed = [item for item in outcomes if item.family.value == family_value]
        net = [item.net_pnl for item in completed]
        family[family_value] = {
            "signals": len(selected),
            "admitted": sum(
                item.status == ReferencePortfolioDecisionStatus.ADMITTED for item in selected
            ),
            "rejected": sum(
                item.status == ReferencePortfolioDecisionStatus.REJECTED for item in selected
            ),
            "not_eligible": sum(
                item.status == ReferencePortfolioDecisionStatus.NOT_ELIGIBLE
                for item in selected
            ),
            "completed": len(completed),
            "net_pnl": sum(net),
            "mean_net_pnl": None if not net else sum(net) / len(net),
        }
    return strategy, family


class ReferenceAccountPortfolioReplay:
    """Replay the frozen opportunities through a real cash/position constraint layer.

    The same-session selector uses only active family load and stable identifiers.
    Outcome fields are used only when their historical exit session is reached.
    """

    def run(self, frame: pd.DataFrame, independent: ReferenceHistoricalRun) -> ReferencePortfolioReplay:
        if frame.empty:
            raise ReferencePortfolioReplayError("reference portfolio replay requires bars")
        session_dates = pd.to_datetime(frame["session_date"], errors="raise").dt.date
        if session_dates.between(
            PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START,
            PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_END,
        ).any():
            raise ProtectedMasterWindowError(
                "reference portfolio replay cannot read the retained master protected window"
            )
        input_fingerprint = reference_input_fingerprint(frame)
        if input_fingerprint != independent.input_fingerprint:
            raise ReferencePortfolioReplayError(
                "portfolio bars do not match the exact independent replay input fingerprint"
            )
        if independent.catalog_fingerprint != REFERENCE_STRATEGY_CATALOG.fingerprint():
            raise ReferencePortfolioReplayError("independent replay catalog fingerprint drifted")

        bars, sessions = _bar_map(frame)
        decisions: list[ReferencePortfolioDecision] = []
        orders: list[ReferenceSimulatedOrderEvent] = []
        outcomes: list[ReferencePortfolioPositionOutcome] = []
        equity_curve: list[ReferencePortfolioEquityPoint] = []
        candidates_by_entry: dict[date, list[ReferenceOpportunityRecord]] = {}

        for item in independent.opportunities:
            if not item.selected_for_independent_replay:
                decisions.append(
                    _non_admission(
                        item,
                        ReferencePortfolioDecisionStatus.NOT_ELIGIBLE,
                        (
                            "UPSTREAM_NOT_SELECTED_FOR_INDEPENDENT_REPLAY",
                            f"UPSTREAM_DISPOSITION:{item.disposition.value}",
                        ),
                    )
                )
                continue
            if item.entry_session is None:
                raise ReferencePortfolioReplayError("selected upstream opportunity lacks entry")
            candidates_by_entry.setdefault(item.entry_session, []).append(item)

        cash = REFERENCE_PORTFOLIO_INITIAL_EQUITY
        peak_equity = cash
        active: dict[str, _ActivePosition] = {}

        def exit_position(position: _ActivePosition, session: date) -> None:
            nonlocal cash
            item = position.opportunity
            if item.exit_price is None or item.exit_reason is None or item.exit_session != session:
                raise ReferencePortfolioReplayError("resolved portfolio exit evidence is incomplete")
            gross_notional = position.quantity * float(item.exit_price)
            exit_cost = gross_notional * REFERENCE_PORTFOLIO_EXIT_COST_BPS / 10_000.0
            cash += gross_notional - exit_cost
            if cash < -1e-7:
                raise ReferencePortfolioReplayError("long-only replay cash became negative on exit")
            cash = max(0.0, cash)
            timing = (
                ReferenceSimulatedOrderTiming.REGULAR_OPEN
                if item.exit_at_session_open
                else ReferenceSimulatedOrderTiming.INTRADAY_DAILY_BAR
            )
            orders.append(
                ReferenceSimulatedOrderEvent(
                    event_id=_event_id(
                        item, position.decision.decision_id, ReferenceSimulatedOrderKind.EXIT
                    ),
                    opportunity_id=item.opportunity_id,
                    decision_id=position.decision.decision_id,
                    strategy_id=item.strategy_id,
                    instrument_id=item.instrument_id,
                    ticker=item.ticker,
                    kind=ReferenceSimulatedOrderKind.EXIT,
                    timing=timing,
                    session=session,
                    quantity=position.quantity,
                    price=float(item.exit_price),
                    gross_notional=gross_notional,
                    transaction_cost=exit_cost,
                    cash_after=cash,
                )
            )
            entry_gross = position.quantity * float(item.entry_price)
            gross_pnl = position.quantity * (float(item.exit_price) - float(item.entry_price))
            net_pnl = gross_pnl - position.entry_transaction_cost - exit_cost
            outcomes.append(
                ReferencePortfolioPositionOutcome(
                    opportunity_id=item.opportunity_id,
                    decision_id=position.decision.decision_id,
                    strategy_id=item.strategy_id,
                    family=item.family,
                    instrument_id=item.instrument_id,
                    ticker=item.ticker,
                    direction=item.direction,
                    entry_session=item.entry_session,
                    exit_session=session,
                    quantity=position.quantity,
                    entry_price=float(item.entry_price),
                    exit_price=float(item.exit_price),
                    exit_reason=item.exit_reason,
                    entry_transaction_cost=position.entry_transaction_cost,
                    exit_transaction_cost=exit_cost,
                    gross_pnl=gross_pnl,
                    net_pnl=net_pnl,
                    net_return_on_entry_notional=net_pnl / entry_gross,
                    holding_sessions=int(item.holding_sessions or 1),
                )
            )
            del active[item.instrument_id]

        for session in sessions:
            opening_exits = sorted(
                (
                    position
                    for position in active.values()
                    if position.opportunity.exit_session == session
                    and position.opportunity.exit_at_session_open
                ),
                key=lambda position: position.opportunity.opportunity_id,
            )
            for position in opening_exits:
                exit_position(position, session)

            pending = list(candidates_by_entry.get(session, ()))
            while pending:
                family_load = {
                    family.value: sum(
                        position.opportunity.family.value == family.value
                        for position in active.values()
                    )
                    for family in {item.family for item in pending}
                }
                item = min(
                    pending,
                    key=lambda row: (
                        family_load[row.family.value],
                        row.family.value,
                        row.strategy_id,
                        row.instrument_id,
                        row.opportunity_id,
                    ),
                )
                pending.remove(item)

                if item.direction != StrategyDirection.LONG:
                    decisions.append(
                        _non_admission(
                            item,
                            ReferencePortfolioDecisionStatus.REJECTED,
                            ("SHORT_REJECTED:BORROW_AND_LOCATE_NOT_MODELED",),
                        )
                    )
                    continue
                if item.outcome_status != OpportunityOutcomeStatus.EXITED:
                    decisions.append(
                        _non_admission(
                            item,
                            ReferencePortfolioDecisionStatus.REJECTED,
                            ("UNRESOLVED_EXIT_REJECTED:V1_REQUIRES_FLAT_RECONCILIATION",),
                        )
                    )
                    continue
                if item.instrument_id in active:
                    decisions.append(
                        _non_admission(
                            item,
                            ReferencePortfolioDecisionStatus.REJECTED,
                            ("INSTRUMENT_ALREADY_ACTIVE",),
                        )
                    )
                    continue
                if len(active) >= REFERENCE_PORTFOLIO_MAX_OPEN_POSITIONS:
                    decisions.append(
                        _non_admission(
                            item,
                            ReferencePortfolioDecisionStatus.REJECTED,
                            ("MAXIMUM_OPEN_POSITIONS_REACHED",),
                        )
                    )
                    continue
                active_family = sum(
                    position.opportunity.family == item.family for position in active.values()
                )
                if active_family >= REFERENCE_PORTFOLIO_MAX_POSITIONS_PER_FAMILY:
                    decisions.append(
                        _non_admission(
                            item,
                            ReferencePortfolioDecisionStatus.REJECTED,
                            ("MAXIMUM_ACTIVE_FAMILY_POSITIONS_REACHED",),
                        )
                    )
                    continue
                if item.entry_price is None or item.initial_risk_per_share is None:
                    raise ReferencePortfolioReplayError("portfolio candidate lacks entry risk geometry")
                entry_price = float(item.entry_price)
                bar_open = _bar_price(bars, item.instrument_id, session, "open")
                if not math.isclose(entry_price, bar_open, rel_tol=0.0, abs_tol=1e-10):
                    raise ReferencePortfolioReplayError("candidate entry does not match canonical open")

                opening_market_value = sum(
                    position.quantity
                    * _bar_price(bars, position.opportunity.instrument_id, session, "open")
                    for position in active.values()
                )
                sizing_equity = cash + opening_market_value
                if sizing_equity <= 0.0:
                    decisions.append(
                        _non_admission(
                            item,
                            ReferencePortfolioDecisionStatus.REJECTED,
                            ("NONPOSITIVE_ACCOUNT_EQUITY",),
                        )
                    )
                    continue
                risk_budget = sizing_equity * REFERENCE_PORTFOLIO_ACCOUNT_RISK_FRACTION
                cost_risk = (
                    entry_price
                    * (REFERENCE_PORTFOLIO_ENTRY_COST_BPS + REFERENCE_PORTFOLIO_EXIT_COST_BPS)
                    / 10_000.0
                )
                effective_risk = float(item.initial_risk_per_share) + cost_risk
                remaining_gross = max(
                    0.0,
                    sizing_equity * REFERENCE_PORTFOLIO_MAX_GROSS_FRACTION
                    - opening_market_value,
                )
                entry_multiplier = 1.0 + REFERENCE_PORTFOLIO_ENTRY_COST_BPS / 10_000.0
                limits = {
                    "risk": math.floor(risk_budget / effective_risk),
                    "position": math.floor(
                        sizing_equity * REFERENCE_PORTFOLIO_MAX_POSITION_FRACTION / entry_price
                    ),
                    "gross": math.floor(remaining_gross / entry_price),
                    "cash": math.floor(cash / (entry_price * entry_multiplier)),
                }
                quantity = min(limits.values())
                if quantity < 1:
                    limiting = tuple(
                        f"{name.upper()}_CAP_QUANTITY:{value}"
                        for name, value in limits.items()
                        if value == quantity
                    )
                    decisions.append(
                        _non_admission(
                            item,
                            ReferencePortfolioDecisionStatus.REJECTED,
                            ("QUANTITY_BELOW_ONE", *limiting),
                        )
                    )
                    continue

                admitted_notional = quantity * entry_price
                entry_cost = admitted_notional * REFERENCE_PORTFOLIO_ENTRY_COST_BPS / 10_000.0
                cash -= admitted_notional + entry_cost
                if cash < -1e-7:
                    raise ReferencePortfolioReplayError("long-only entry overspent cash")
                cash = max(0.0, cash)
                decision = ReferencePortfolioDecision(
                    decision_id=_decision_id(item),
                    opportunity_id=item.opportunity_id,
                    strategy_id=item.strategy_id,
                    family=item.family,
                    direction=item.direction,
                    instrument_id=item.instrument_id,
                    ticker=item.ticker,
                    signal_session=item.signal_session,
                    requested_entry_session=item.entry_session,
                    status=ReferencePortfolioDecisionStatus.ADMITTED,
                    reason_codes=(
                        "UPSTREAM_FROZEN_POLICY_SIGNAL",
                        "FAMILY_LOAD_BALANCED_STABLE_SELECTOR",
                        "LONG_ONLY_BORROW_SAFE_BASELINE",
                        "RISK_SIZE_PASS",
                        "POSITION_NOTIONAL_PASS",
                        "GROSS_EXPOSURE_PASS",
                        "CASH_PASS",
                        "SIMULATED_ORDER_ONLY_NO_EXECUTION_AUTHORITY",
                    ),
                    admitted_quantity=quantity,
                    entry_price=entry_price,
                    initial_stop_price=item.initial_stop_price,
                    target_price=item.target_price,
                    sizing_equity=sizing_equity,
                    risk_budget=risk_budget,
                    effective_risk_per_share=effective_risk,
                    admitted_notional=admitted_notional,
                )
                decisions.append(decision)
                orders.append(
                    ReferenceSimulatedOrderEvent(
                        event_id=_event_id(
                            item, decision.decision_id, ReferenceSimulatedOrderKind.ENTRY
                        ),
                        opportunity_id=item.opportunity_id,
                        decision_id=decision.decision_id,
                        strategy_id=item.strategy_id,
                        instrument_id=item.instrument_id,
                        ticker=item.ticker,
                        kind=ReferenceSimulatedOrderKind.ENTRY,
                        timing=ReferenceSimulatedOrderTiming.REGULAR_OPEN,
                        session=session,
                        quantity=quantity,
                        price=entry_price,
                        gross_notional=admitted_notional,
                        transaction_cost=entry_cost,
                        cash_after=cash,
                    )
                )
                active[item.instrument_id] = _ActivePosition(
                    opportunity=item,
                    decision=decision,
                    quantity=quantity,
                    entry_transaction_cost=entry_cost,
                )

            intraday_exits = sorted(
                (
                    position
                    for position in active.values()
                    if position.opportunity.exit_session == session
                    and not position.opportunity.exit_at_session_open
                ),
                key=lambda position: position.opportunity.opportunity_id,
            )
            for position in intraday_exits:
                exit_position(position, session)

            market_value = sum(
                position.quantity
                * _bar_price(bars, position.opportunity.instrument_id, session, "close")
                for position in active.values()
            )
            equity = cash + market_value
            peak_equity = max(peak_equity, equity)
            drawdown = 0.0 if peak_equity == 0.0 else equity / peak_equity - 1.0
            equity_curve.append(
                ReferencePortfolioEquityPoint(
                    session=session,
                    cash=cash,
                    market_value=market_value,
                    equity=equity,
                    gross_exposure_fraction=(0.0 if equity == 0.0 else market_value / equity),
                    open_positions=len(active),
                    peak_equity=peak_equity,
                    drawdown=drawdown,
                )
            )

        if active:
            raise ReferencePortfolioReplayError(
                "v1 resolved-exit admission must finish flat; active positions remain"
            )

        decision_rows = tuple(
            sorted(
                decisions,
                key=lambda item: (
                    item.requested_entry_session or item.signal_session,
                    item.instrument_id,
                    item.strategy_id,
                    item.opportunity_id,
                ),
            )
        )
        # The append order is the frozen event clock: opening exits, opening
        # entries, then intraday exits. Preserve it in the evidence ledger.
        order_rows = tuple(orders)
        outcome_rows = tuple(sorted(outcomes, key=lambda item: (item.exit_session, item.opportunity_id)))
        equity_rows = tuple(equity_curve)
        final_equity = cash
        wins = sum(item.net_pnl > 0.0 for item in outcome_rows)
        losses = sum(item.net_pnl < 0.0 for item in outcome_rows)
        positive = sum(item.net_pnl for item in outcome_rows if item.net_pnl > 0.0)
        negative = -sum(item.net_pnl for item in outcome_rows if item.net_pnl < 0.0)
        total_cost = sum(item.transaction_cost for item in order_rows)
        strategy_summary, family_summary = _summaries(decision_rows, outcome_rows)
        replay_payload = {
            "contract_version": REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
            "engine_contract_version": REFERENCE_PORTFOLIO_REPLAY_ENGINE_CONTRACT_VERSION,
            "independent_run_fingerprint": independent.run_fingerprint,
            "input_fingerprint": input_fingerprint,
            "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
            "initial_equity": REFERENCE_PORTFOLIO_INITIAL_EQUITY,
            "final_equity": final_equity,
            "decisions": [item.model_dump(mode="json") for item in decision_rows],
            "simulated_orders": [item.model_dump(mode="json") for item in order_rows],
            "position_outcomes": [item.model_dump(mode="json") for item in outcome_rows],
            "equity_curve": [item.model_dump(mode="json") for item in equity_rows],
            "summary_by_strategy": strategy_summary,
            "summary_by_family": family_summary,
            "protected_master_return_rows_read": 0,
            "provider_writes": REFERENCE_PORTFOLIO_PROVIDER_WRITES,
            "broker_writes": REFERENCE_PORTFOLIO_BROKER_WRITES,
            "paper_submits": REFERENCE_PORTFOLIO_PAPER_SUBMITS,
            "live_writes": REFERENCE_PORTFOLIO_LIVE_WRITES,
        }
        completed = len(outcome_rows)
        return ReferencePortfolioReplay(
            replay_fingerprint=_stable_hash(replay_payload),
            independent_run_fingerprint=independent.run_fingerprint,
            input_fingerprint=input_fingerprint,
            portfolio_policy_fingerprint=reference_portfolio_policy_fingerprint(),
            initial_equity=REFERENCE_PORTFOLIO_INITIAL_EQUITY,
            final_equity=final_equity,
            total_return=final_equity / REFERENCE_PORTFOLIO_INITIAL_EQUITY - 1.0,
            maximum_drawdown=min((item.drawdown for item in equity_rows), default=0.0),
            signals_fired=len(independent.opportunities),
            upstream_independent_candidates=sum(
                item.selected_for_independent_replay for item in independent.opportunities
            ),
            admitted_positions=sum(
                item.status == ReferencePortfolioDecisionStatus.ADMITTED
                for item in decision_rows
            ),
            completed_positions=completed,
            winning_positions=wins,
            losing_positions=losses,
            win_rate=None if completed == 0 else wins / completed,
            profit_factor=None if negative == 0.0 else positive / negative,
            total_transaction_cost=total_cost,
            decisions=decision_rows,
            simulated_orders=order_rows,
            position_outcomes=outcome_rows,
            equity_curve=equity_rows,
            summary_by_strategy=strategy_summary,
            summary_by_family=family_summary,
        )
