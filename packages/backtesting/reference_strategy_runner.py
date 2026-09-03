from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date

import pandas as pd

from packages.features.reference_daily import (
    compute_reference_daily_features,
    reference_daily_feature_fingerprint,
    reference_signal_mask,
)
from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import (
    REFERENCE_HISTORICAL_RUN_CONTRACT_VERSION,
    OpportunityDisposition,
    OpportunityOutcomeStatus,
    ReferenceExitReason,
    ReferenceHistoricalRun,
    ReferenceOpportunityRecord,
)
from packages.schemas.strategy_policy import (
    IndicatorExitRule,
    InitialStopRule,
    StrategySpecification,
)
from packages.strategies.reference_library import (
    REFERENCE_STRATEGY_CATALOG,
    ReferenceStrategyCatalog,
)


REFERENCE_STRATEGY_RUNNER_CONTRACT_VERSION = (
    "reference-strategy-runner-v1-next-open-adverse-first-independent-overlap-ledger"
)
PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START = date(2026, 5, 12)
PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_END = date(2026, 8, 11)
REFERENCE_STRATEGY_RUNNER_BROKER_WRITES = 0
REFERENCE_STRATEGY_RUNNER_PAPER_SUBMITS = 0
REFERENCE_STRATEGY_RUNNER_LIVE_WRITES = 0


class ReferenceStrategyRunnerError(RuntimeError):
    pass


class ProtectedMasterWindowError(ReferenceStrategyRunnerError):
    pass


@dataclass(frozen=True, slots=True)
class ReferenceTradePlan:
    entry_position: int
    entry_session: date
    entry_price: float
    initial_stop_price: float
    target_price: float | None
    quantity: int
    initial_risk_per_share: float


@dataclass(frozen=True, slots=True)
class ReferenceTradeSimulation:
    outcome_status: OpportunityOutcomeStatus
    exit_position: int | None
    exit_session: date | None
    exit_price: float | None
    exit_reason: ReferenceExitReason | None
    holding_sessions: int | None
    exit_at_session_open: bool
    same_bar_collision_adverse_first: bool
    gross_directional_return: float | None
    net_directional_returns_by_cost_bps: dict[str, float]
    primary_net_directional_return: float | None
    risk_multiple: float | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _cost_key(value: float) -> str:
    return format(float(value), "g")


def reference_input_fingerprint(frame: pd.DataFrame) -> str:
    """Bind the exact caller-supplied rows before any feature or outcome work."""

    required = {"instrument_id", "session_date"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ReferenceStrategyRunnerError(
            "reference input fingerprint requires columns: " + ", ".join(missing)
        )
    input_columns = sorted(str(column) for column in frame.columns)
    input_payload = frame[input_columns].sort_values(
        ["instrument_id", "session_date"], kind="stable"
    ).to_dict(orient="records")
    return _stable_hash(input_payload)


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _universe_decision(row: pd.Series) -> tuple[bool, tuple[str, ...]]:
    checks = (
        ("PIT_ACTIVE", row.get("universe_pit_active_ok") == 1.0),
        ("COMMON_STOCK", row.get("universe_common_stock_ok") == 1.0),
        ("IDENTITY_CLEAR", row.get("universe_identity_ok") == 1.0),
        ("CLOSE_MINIMUM", row.get("universe_close_ok") == 1.0),
        ("PRIOR_LIQUIDITY_MINIMUM", row.get("universe_prior_liquidity_ok") == 1.0),
    )
    reasons = tuple(f"UNIVERSE_{'PASS' if passed else 'FAIL'}:{name}" for name, passed in checks)
    return all(passed for _, passed in checks), reasons


def plan_reference_trade(
    specification: StrategySpecification,
    instrument_features: pd.DataFrame,
    signal_position: int,
) -> tuple[ReferenceTradePlan | None, tuple[str, ...]]:
    """Construct a deterministic next-open plan or return auditable rejection reasons."""

    entry_position = signal_position + 1
    if entry_position >= len(instrument_features):
        return None, ("NO_NEXT_REGULAR_SESSION_ENTRY_BAR",)
    signal = instrument_features.iloc[signal_position]
    entry = instrument_features.iloc[entry_position]
    entry_price = float(entry["open"])
    atr = float(signal["atr_14"])
    if not _finite(entry_price) or entry_price <= 0.0 or not _finite(atr) or atr <= 0.0:
        return None, ("RISK_REJECTED:NONPOSITIVE_ENTRY_OR_ATR",)

    stop_rule = specification.exit.initial_stop_rule
    direction = specification.direction
    atr_distance = specification.exit.initial_atr_multiple * atr
    if stop_rule == InitialStopRule.ATR_FROM_ENTRY:
        stop = entry_price - atr_distance if direction == StrategyDirection.LONG else entry_price + atr_distance
    elif stop_rule == InitialStopRule.PULLBACK_LOW_OR_ATR_FARTHER:
        pullback_low = signal.get("ema_pullback_low_20_50_long")
        if direction != StrategyDirection.LONG or not _finite(pullback_low):
            return None, ("RISK_REJECTED:INVALID_PULLBACK_STOP_REFERENCE",)
        stop = min(float(pullback_low), entry_price - atr_distance)
    elif stop_rule == InitialStopRule.DONCHIAN_BOUNDARY_OR_ATR_CLOSER:
        reference_name = "prior_high_20" if direction == StrategyDirection.LONG else "prior_low_20"
        boundary = signal.get(reference_name)
        if not _finite(boundary):
            return None, ("RISK_REJECTED:INVALID_DONCHIAN_STOP_REFERENCE",)
        stop = (
            max(float(boundary), entry_price - atr_distance)
            if direction == StrategyDirection.LONG
            else min(float(boundary), entry_price + atr_distance)
        )
    elif stop_rule == InitialStopRule.BOLLINGER_MID_OR_ATR_CLOSER:
        middle = signal.get("bb_mid_20")
        if not _finite(middle):
            return None, ("RISK_REJECTED:INVALID_BOLLINGER_STOP_REFERENCE",)
        stop = (
            max(float(middle), entry_price - atr_distance)
            if direction == StrategyDirection.LONG
            else min(float(middle), entry_price + atr_distance)
        )
    else:  # pragma: no cover - enum exhaustiveness guard
        raise ReferenceStrategyRunnerError(f"unsupported initial stop rule: {stop_rule}")

    sign = 1.0 if direction == StrategyDirection.LONG else -1.0
    risk_per_share = (entry_price - float(stop)) * sign
    if not _finite(stop) or stop <= 0.0 or risk_per_share <= 0.0:
        return None, ("RISK_REJECTED:INVALID_ENTRY_STOP_GEOMETRY",)
    stop_fraction = risk_per_share / entry_price
    if stop_fraction > specification.risk.maximum_initial_stop_fraction:
        return None, (
            "RISK_REJECTED:STOP_DISTANCE_EXCEEDS_CAP",
            f"STOP_FRACTION:{stop_fraction:.12g}",
        )

    risk_budget = specification.risk.reference_equity * specification.risk.account_risk_fraction
    notional_budget = specification.risk.reference_equity * specification.risk.maximum_position_fraction
    risk_quantity = math.floor(risk_budget / risk_per_share)
    notional_quantity = math.floor(notional_budget / entry_price)
    quantity = min(risk_quantity, notional_quantity)
    if quantity < specification.risk.minimum_quantity:
        return None, ("RISK_REJECTED:QUANTITY_BELOW_MINIMUM",)

    target = None
    if specification.exit.profit_target_r is not None:
        target = entry_price + sign * specification.exit.profit_target_r * risk_per_share
        if not _finite(target) or target <= 0.0:
            return None, ("RISK_REJECTED:INVALID_TARGET_GEOMETRY",)

    plan = ReferenceTradePlan(
        entry_position=entry_position,
        entry_session=entry["session_date"],
        entry_price=entry_price,
        initial_stop_price=float(stop),
        target_price=None if target is None else float(target),
        quantity=quantity,
        initial_risk_per_share=risk_per_share,
    )
    return plan, (
        "PLAN_NEXT_REGULAR_SESSION_OPEN",
        f"INITIAL_STOP_RULE:{stop_rule.value}",
        "POSITION_SIZE:EQUAL_RISK_WITH_NOTIONAL_CAP",
    )


def _indicator_exit_reason(
    specification: StrategySpecification,
    row: pd.Series,
) -> ReferenceExitReason | None:
    rule = specification.exit.indicator_exit_rule
    direction = specification.direction
    if rule == IndicatorExitRule.NONE:
        return None
    if rule == IndicatorExitRule.SMA_REVERSE_CROSS:
        feature = "sma_cross_50_200_down" if direction == StrategyDirection.LONG else "sma_cross_50_200_up"
        return ReferenceExitReason.SMA_REVERSE_CROSS if row.get(feature) == 1.0 else None
    if rule == IndicatorExitRule.CLOSE_BELOW_EMA_50:
        if direction == StrategyDirection.LONG and _finite(row.get("ema_50")):
            return ReferenceExitReason.CLOSE_BELOW_EMA_50 if float(row["close"]) < float(row["ema_50"]) else None
        return None
    if rule == IndicatorExitRule.MACD_OPPOSITE_CROSS:
        feature = "macd_signal_cross_down" if direction == StrategyDirection.LONG else "macd_signal_cross_up"
        return ReferenceExitReason.MACD_OPPOSITE_CROSS if row.get(feature) == 1.0 else None
    if rule == IndicatorExitRule.RSI_60_OR_EMA_20:
        if _finite(row.get("rsi_14")) and float(row["rsi_14"]) >= 60.0:
            return ReferenceExitReason.RSI_60_OR_EMA_20
        if _finite(row.get("ema_20")) and float(row["close"]) >= float(row["ema_20"]):
            return ReferenceExitReason.RSI_60_OR_EMA_20
        return None
    raise ReferenceStrategyRunnerError(f"unsupported indicator exit rule: {rule}")


def simulate_reference_trade(
    specification: StrategySpecification,
    instrument_features: pd.DataFrame,
    plan: ReferenceTradePlan,
) -> ReferenceTradeSimulation:
    """Simulate one daily trade with gap-aware stops and adverse-first collisions."""

    direction = specification.direction
    sign = 1.0 if direction == StrategyDirection.LONG else -1.0
    stop = plan.initial_stop_price
    target = plan.target_price
    pending_exit: ReferenceExitReason | None = None
    collision = False
    highest = plan.entry_price
    lowest = plan.entry_price

    exit_position: int | None = None
    exit_price: float | None = None
    exit_reason: ReferenceExitReason | None = None
    exit_at_session_open = False

    for position in range(plan.entry_position, len(instrument_features)):
        row = instrument_features.iloc[position]
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])

        if position > plan.entry_position and pending_exit is not None:
            exit_position = position
            exit_price = open_price
            exit_reason = pending_exit
            exit_at_session_open = True
            highest = max(highest, open_price)
            lowest = min(lowest, open_price)
            break

        if direction == StrategyDirection.LONG:
            if open_price <= stop:
                exit_position, exit_price, exit_reason = position, open_price, ReferenceExitReason.INITIAL_OR_TRAILING_STOP
            elif target is not None and open_price >= target:
                exit_position, exit_price, exit_reason = position, open_price, ReferenceExitReason.PROFIT_TARGET
        else:
            if open_price >= stop:
                exit_position, exit_price, exit_reason = position, open_price, ReferenceExitReason.INITIAL_OR_TRAILING_STOP
            elif target is not None and open_price <= target:
                exit_position, exit_price, exit_reason = position, open_price, ReferenceExitReason.PROFIT_TARGET
        if exit_position is not None:
            exit_at_session_open = True
            highest = max(highest, open_price)
            lowest = min(lowest, open_price)
            break

        stop_hit = low <= stop if direction == StrategyDirection.LONG else high >= stop
        target_hit = False
        if target is not None:
            target_hit = high >= target if direction == StrategyDirection.LONG else low <= target
        if stop_hit and target_hit:
            collision = True
            exit_position, exit_price, exit_reason = position, stop, ReferenceExitReason.INITIAL_OR_TRAILING_STOP
            highest = max(highest, open_price, stop)
            lowest = min(lowest, open_price, stop)
            break
        if stop_hit:
            exit_position, exit_price, exit_reason = position, stop, ReferenceExitReason.INITIAL_OR_TRAILING_STOP
            # Under the frozen adverse-first daily-bar path, the stop occurs before
            # any unobservable favorable move later in the bar.
            highest = max(highest, open_price, stop)
            lowest = min(lowest, open_price, stop)
            break
        if target_hit:
            exit_position, exit_price, exit_reason = position, float(target), ReferenceExitReason.PROFIT_TARGET
            # Cap favorable excursion at the executed target; retain the adverse
            # bar extreme because it could have occurred before that target.
            if direction == StrategyDirection.LONG:
                highest = max(highest, open_price, float(target))
                lowest = min(lowest, low)
            else:
                highest = max(highest, high)
                lowest = min(lowest, open_price, float(target))
            break

        highest = max(highest, high)
        lowest = min(lowest, low)
        indicator_reason = _indicator_exit_reason(specification, row)
        held = position - plan.entry_position + 1
        if indicator_reason is not None:
            pending_exit = indicator_reason
        elif held >= specification.exit.maximum_holding_sessions:
            pending_exit = ReferenceExitReason.MAXIMUM_HOLD

        trail_multiple = specification.exit.trailing_atr_multiple
        if trail_multiple is not None and _finite(row.get("atr_14")):
            atr = float(row["atr_14"])
            if atr > 0.0:
                if direction == StrategyDirection.LONG:
                    stop = max(stop, highest - trail_multiple * atr)
                else:
                    stop = min(stop, lowest + trail_multiple * atr)

    if exit_position is None:
        return ReferenceTradeSimulation(
            outcome_status=OpportunityOutcomeStatus.OPEN_UNRESOLVED,
            exit_position=None,
            exit_session=None,
            exit_price=None,
            exit_reason=None,
            holding_sessions=None,
            exit_at_session_open=False,
            same_bar_collision_adverse_first=collision,
            gross_directional_return=None,
            net_directional_returns_by_cost_bps={},
            primary_net_directional_return=None,
            risk_multiple=None,
            maximum_favorable_excursion=None,
            maximum_adverse_excursion=None,
        )

    gross = ((float(exit_price) / plan.entry_price) - 1.0) * sign
    net = {
        _cost_key(cost): gross - float(cost) / 10_000.0
        for cost in specification.costs.round_trip_cost_grid_bps
    }
    if direction == StrategyDirection.LONG:
        mfe = highest / plan.entry_price - 1.0
        mae = lowest / plan.entry_price - 1.0
    else:
        mfe = 1.0 - lowest / plan.entry_price
        mae = 1.0 - highest / plan.entry_price
    return ReferenceTradeSimulation(
        outcome_status=OpportunityOutcomeStatus.EXITED,
        exit_position=exit_position,
        exit_session=instrument_features.iloc[exit_position]["session_date"],
        exit_price=float(exit_price),
        exit_reason=exit_reason,
        holding_sessions=max(
            1,
            exit_position - plan.entry_position + (0 if exit_at_session_open else 1),
        ),
        exit_at_session_open=exit_at_session_open,
        same_bar_collision_adverse_first=collision,
        gross_directional_return=gross,
        net_directional_returns_by_cost_bps=net,
        primary_net_directional_return=net[_cost_key(specification.costs.primary_cost_bps)],
        risk_multiple=((float(exit_price) - plan.entry_price) * sign) / plan.initial_risk_per_share,
        maximum_favorable_excursion=mfe,
        maximum_adverse_excursion=mae,
    )


def _opportunity_id(
    specification: StrategySpecification,
    instrument_id: str,
    signal_session: date,
) -> str:
    return _stable_hash(
        {
            "contract_version": REFERENCE_STRATEGY_RUNNER_CONTRACT_VERSION,
            "strategy_id": specification.strategy_id,
            "strategy_policy_fingerprint": specification.fingerprint(),
            "instrument_id": instrument_id,
            "signal_session": signal_session.isoformat(),
        }
    )


def _context_label(row: pd.Series, *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() and str(value).lower() != "nan":
            return str(value).strip().upper()
    return "UNAVAILABLE"


def _volatility_bucket(row: pd.Series) -> str:
    value = row.get("natr_14")
    if not _finite(value):
        return "UNAVAILABLE"
    natr = float(value)
    if natr < 0.02:
        return "LOW_LT_2PCT"
    if natr < 0.04:
        return "MEDIUM_2_TO_4PCT"
    return "HIGH_GE_4PCT"


def _liquidity_bucket(row: pd.Series) -> str:
    value = row.get("prior_median_dollar_volume_20")
    if not _finite(value):
        return "UNAVAILABLE"
    dollars = float(value)
    if dollars < 20_000_000.0:
        return "RETAIL_5_TO_20M"
    if dollars < 100_000_000.0:
        return "LIQUID_20_TO_100M"
    return "DEEP_GE_100M"


def _record(
    *,
    specification: StrategySpecification,
    signal: pd.Series,
    universe_eligible: bool,
    disposition: OpportunityDisposition,
    reasons: tuple[str, ...],
    selected: bool,
    plan: ReferenceTradePlan | None = None,
    simulation: ReferenceTradeSimulation | None = None,
) -> ReferenceOpportunityRecord:
    simulation = simulation or ReferenceTradeSimulation(
        outcome_status=OpportunityOutcomeStatus.NOT_SIMULATED,
        exit_position=None,
        exit_session=None,
        exit_price=None,
        exit_reason=None,
        holding_sessions=None,
        exit_at_session_open=False,
        same_bar_collision_adverse_first=False,
        gross_directional_return=None,
        net_directional_returns_by_cost_bps={},
        primary_net_directional_return=None,
        risk_multiple=None,
        maximum_favorable_excursion=None,
        maximum_adverse_excursion=None,
    )
    return ReferenceOpportunityRecord(
        opportunity_id=_opportunity_id(
            specification, str(signal["instrument_id"]), signal["session_date"]
        ),
        strategy_id=specification.strategy_id,
        strategy_policy_fingerprint=specification.fingerprint(),
        family=specification.family,
        direction=specification.direction,
        instrument_id=str(signal["instrument_id"]),
        ticker=str(signal["ticker"]),
        signal_session=signal["session_date"],
        signal_timestamp_utc=signal["timestamp_utc"].to_pydatetime(),
        market_regime=_context_label(signal, "market_regime_composite", "market_regime"),
        sector_regime=_context_label(signal, "sector_regime_composite", "sector_regime"),
        ticker_regime=_context_label(signal, "ticker_regime_composite", "ticker_regime"),
        volatility_bucket=_volatility_bucket(signal),
        liquidity_bucket=_liquidity_bucket(signal),
        universe_eligible=universe_eligible,
        disposition=disposition,
        reason_codes=tuple(dict.fromkeys(reasons)),
        selected_for_independent_replay=selected,
        counterfactual_only=not selected,
        entry_session=None if plan is None else plan.entry_session,
        entry_price=None if plan is None else plan.entry_price,
        initial_stop_price=None if plan is None else plan.initial_stop_price,
        target_price=None if plan is None else plan.target_price,
        quantity=None if plan is None else plan.quantity,
        initial_risk_per_share=None if plan is None else plan.initial_risk_per_share,
        outcome_status=simulation.outcome_status,
        exit_session=simulation.exit_session,
        exit_price=simulation.exit_price,
        exit_reason=simulation.exit_reason,
        holding_sessions=simulation.holding_sessions,
        exit_at_session_open=simulation.exit_at_session_open,
        same_bar_collision_adverse_first=simulation.same_bar_collision_adverse_first,
        gross_directional_return=simulation.gross_directional_return,
        net_directional_returns_by_cost_bps=simulation.net_directional_returns_by_cost_bps,
        primary_net_directional_return=simulation.primary_net_directional_return,
        risk_multiple=simulation.risk_multiple,
        maximum_favorable_excursion=simulation.maximum_favorable_excursion,
        maximum_adverse_excursion=simulation.maximum_adverse_excursion,
    )


def _summary(
    catalog: ReferenceStrategyCatalog,
    opportunities: tuple[ReferenceOpportunityRecord, ...],
) -> dict[str, dict[str, int | float | None]]:
    result: dict[str, dict[str, int | float | None]] = {}
    for specification in catalog.all():
        rows = [item for item in opportunities if item.strategy_id == specification.strategy_id]
        selected = [item for item in rows if item.selected_for_independent_replay]
        exited = [item for item in selected if item.outcome_status == OpportunityOutcomeStatus.EXITED]
        returns = [float(item.primary_net_directional_return) for item in exited]
        result[specification.strategy_id] = {
            "signals_fired": len(rows),
            "universe_eligible": sum(item.universe_eligible for item in rows),
            "universe_rejected": sum(item.disposition == OpportunityDisposition.UNIVERSE_REJECTED for item in rows),
            "risk_rejected": sum(item.disposition == OpportunityDisposition.RISK_REJECTED for item in rows),
            "overlap_not_selected": sum(
                item.disposition == OpportunityDisposition.NOT_SELECTED_ACTIVE_POSITION for item in rows
            ),
            "selected_independent_replay": len(selected),
            "exited": len(exited),
            "open_unresolved": sum(
                item.outcome_status == OpportunityOutcomeStatus.OPEN_UNRESOLVED for item in selected
            ),
            "primary_cost_bps": specification.costs.primary_cost_bps,
            "mean_primary_net_return": None if not returns else sum(returns) / len(returns),
        }
    return result


def _condition_slices(
    catalog: ReferenceStrategyCatalog,
    opportunities: tuple[ReferenceOpportunityRecord, ...],
) -> dict[str, dict[str, dict[str, dict[str, int | float | None]]]]:
    result: dict[str, dict[str, dict[str, dict[str, int | float | None]]]] = {}
    dimensions = {
        "market_regime": lambda item: item.market_regime,
        "sector_regime": lambda item: item.sector_regime,
        "ticker_regime": lambda item: item.ticker_regime,
        "volatility_bucket": lambda item: item.volatility_bucket,
        "liquidity_bucket": lambda item: item.liquidity_bucket,
        "direction": lambda item: item.direction.value,
    }
    for specification in catalog.all():
        strategy_rows = [
            item for item in opportunities if item.strategy_id == specification.strategy_id
        ]
        strategy_result: dict[str, dict[str, dict[str, int | float | None]]] = {}
        for dimension, getter in dimensions.items():
            categories: dict[str, dict[str, int | float | None]] = {}
            for category in sorted({getter(item) for item in strategy_rows}):
                rows = [item for item in strategy_rows if getter(item) == category]
                selected = [item for item in rows if item.selected_for_independent_replay]
                exited = [
                    item
                    for item in selected
                    if item.outcome_status == OpportunityOutcomeStatus.EXITED
                ]
                returns = [float(item.primary_net_directional_return) for item in exited]
                categories[category] = {
                    "signals_fired": len(rows),
                    "selected": len(selected),
                    "exited": len(exited),
                    "mean_primary_net_return": (
                        None if not returns else sum(returns) / len(returns)
                    ),
                }
            strategy_result[dimension] = categories
        result[specification.strategy_id] = strategy_result
    return result


class ReferenceStrategyHistoricalRunner:
    """Provider-free A33/B33 runner over caller-supplied development daily bars."""

    def __init__(self, catalog: ReferenceStrategyCatalog = REFERENCE_STRATEGY_CATALOG) -> None:
        self.catalog = catalog

    def run(self, frame: pd.DataFrame) -> ReferenceHistoricalRun:
        if frame.empty:
            raise ReferenceStrategyRunnerError("reference historical runner requires input rows")
        if "session_date" not in frame.columns:
            raise ReferenceStrategyRunnerError("reference historical runner requires session_date")
        session_dates = pd.to_datetime(frame["session_date"], errors="raise").dt.date
        forbidden = session_dates.between(
            PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START,
            PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_END,
        )
        if forbidden.any():
            raise ProtectedMasterWindowError(
                "practitioner replay cannot read the retained master protected window "
                f"{PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_START}.."
                f"{PRACTITIONER_FORBIDDEN_MASTER_PROTECTED_END}"
            )

        features = compute_reference_daily_features(frame)
        input_fingerprint = reference_input_fingerprint(frame)

        records: list[ReferenceOpportunityRecord] = []
        for specification in self.catalog.all():
            for _, instrument in features.groupby("instrument_id", sort=True, observed=True):
                instrument = instrument.reset_index(drop=True)
                fired = reference_signal_mask(instrument, specification)
                active_exit_position: float = -1.0
                for signal_position in fired[fired].index.tolist():
                    signal = instrument.iloc[signal_position]
                    universe_eligible, universe_reasons = _universe_decision(signal)
                    if not universe_eligible:
                        records.append(
                            _record(
                                specification=specification,
                                signal=signal,
                                universe_eligible=False,
                                disposition=OpportunityDisposition.UNIVERSE_REJECTED,
                                reasons=("SIGNAL_FIRED", *universe_reasons),
                                selected=False,
                            )
                        )
                        continue

                    plan, plan_reasons = plan_reference_trade(
                        specification, instrument, signal_position
                    )
                    if plan is None:
                        no_entry = "NO_NEXT_REGULAR_SESSION_ENTRY_BAR" in plan_reasons
                        records.append(
                            _record(
                                specification=specification,
                                signal=signal,
                                universe_eligible=True,
                                disposition=(
                                    OpportunityDisposition.NO_NEXT_ENTRY_BAR
                                    if no_entry
                                    else OpportunityDisposition.RISK_REJECTED
                                ),
                                reasons=("SIGNAL_FIRED", *universe_reasons, *plan_reasons),
                                selected=False,
                            )
                        )
                        continue

                    simulation = simulate_reference_trade(specification, instrument, plan)
                    overlap = signal_position < active_exit_position
                    if overlap:
                        disposition = OpportunityDisposition.NOT_SELECTED_ACTIVE_POSITION
                        selected = False
                        selection_reasons = ("NOT_SELECTED:ACTIVE_STRATEGY_POSITION",)
                    else:
                        disposition = OpportunityDisposition.SELECTED_INDEPENDENT_REPLAY
                        selected = True
                        selection_reasons = ("SELECTED:INDEPENDENT_STRATEGY_REPLAY",)
                        active_exit_position = (
                            float("inf")
                            if simulation.exit_position is None
                            else float(simulation.exit_position)
                        )
                    records.append(
                        _record(
                            specification=specification,
                            signal=signal,
                            universe_eligible=True,
                            disposition=disposition,
                            reasons=(
                                "SIGNAL_FIRED",
                                *universe_reasons,
                                *plan_reasons,
                                *selection_reasons,
                            ),
                            selected=selected,
                            plan=plan,
                            simulation=simulation,
                        )
                    )

        opportunities = tuple(
            sorted(
                records,
                key=lambda item: (
                    item.signal_session,
                    item.instrument_id,
                    item.strategy_id,
                    item.opportunity_id,
                ),
            )
        )
        summary = _summary(self.catalog, opportunities)
        condition_slices = _condition_slices(self.catalog, opportunities)
        run_payload = {
            "contract_version": REFERENCE_HISTORICAL_RUN_CONTRACT_VERSION,
            "runner_contract_version": REFERENCE_STRATEGY_RUNNER_CONTRACT_VERSION,
            "input_fingerprint": input_fingerprint,
            "catalog_fingerprint": self.catalog.fingerprint(),
            "feature_fingerprint": reference_daily_feature_fingerprint(),
            "opportunities": [item.model_dump(mode="json") for item in opportunities],
            "summary_by_strategy": summary,
            "condition_slices": condition_slices,
            "protected_master_return_rows_read": 0,
            "broker_writes": REFERENCE_STRATEGY_RUNNER_BROKER_WRITES,
            "paper_submits": REFERENCE_STRATEGY_RUNNER_PAPER_SUBMITS,
            "live_writes": REFERENCE_STRATEGY_RUNNER_LIVE_WRITES,
        }
        return ReferenceHistoricalRun(
            run_fingerprint=_stable_hash(run_payload),
            input_fingerprint=input_fingerprint,
            catalog_fingerprint=self.catalog.fingerprint(),
            feature_fingerprint=reference_daily_feature_fingerprint(),
            input_rows=len(features),
            input_instruments=int(features["instrument_id"].nunique()),
            first_session=min(features["session_date"]),
            last_session=max(features["session_date"]),
            opportunities=opportunities,
            summary_by_strategy=summary,
            condition_slices=condition_slices,
        )
