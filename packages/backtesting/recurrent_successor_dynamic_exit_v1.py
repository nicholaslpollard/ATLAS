from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from packages.backtesting.recurrent_successor_daily_exit_regime_robustness_contract import (
    RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    DailyPathCase,
    _load_json,
    _stable_hash,
    _write_json,
    _write_jsonl,
    load_daily_exit_cases,
    resolve_daily_exit,
)
from packages.backtesting.recurrent_successor_dynamic_exit_v1_contract import (
    ABSTAIN_ACTION_ID,
    AUTHORITY,
    CONTEXT_FALLBACK_HIERARCHY,
    DEVELOPMENT_SCOPE,
    DYNAMIC_EXIT_ACTIONS,
    LOOKBACK_COMPLETED_FOLDS,
    MIN_ACCEPTABLE_LCB,
    MIN_TRAINING_CASES,
    MIN_TRAINING_INSTRUMENTS,
    MIN_TRAINING_SESSIONS,
    ONE_SIDED_LCB_Z,
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT,
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
    SOURCE_STATIC_REGIME_RUN_FINGERPRINT,
    dynamic_exit_action_id,
)
from packages.strategies.successor_conditioning_contract import DAILY_PRIMARY_COST_BPS


class RecurrentSuccessorDynamicExitV1Error(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DynamicExitActionStats:
    action_id: str
    stop_fraction: float
    target_fraction: float
    training_cases: int
    training_sessions: int
    training_instruments: int
    mean_trade_net_return: float
    mean_session_net_return: float
    session_mean_standard_deviation: float
    lcb_net_return: float
    probability_positive: float


@dataclass(frozen=True, slots=True)
class DynamicExitChoice:
    action_id: str
    stop_fraction: float | None
    target_fraction: float | None
    fallback_level: int | None
    context_dimensions: tuple[str, ...]
    context_key: tuple[str, ...]
    training_cases: int
    training_sessions: int
    training_instruments: int
    training_fold_min: int | None
    training_fold_max: int | None
    training_cutoff_session: date | None
    selected_lcb_net_return: float | None
    selected_mean_trade_net_return: float | None
    selected_probability_positive: float | None
    reason: str


def _source_static_regime_summary(project_root: Path) -> dict[str, object]:
    root = (
        Path(project_root).resolve()
        / "data"
        / "research"
        / "recurrent_successor_daily_exit_regime_robustness"
        / RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT[:16]
        / SOURCE_STATIC_REGIME_RUN_FINGERPRINT[:16]
    )
    path = root / "regime_robustness_summary.json"
    if not path.is_file():
        raise RecurrentSuccessorDynamicExitV1Error(
            "accepted static-exit regime robustness summary is missing"
        )
    summary = _load_json(path)
    if (
        summary.get("status")
        != "COMPLETE_RETROSPECTIVE_DAILY_EXIT_REGIME_ROBUSTNESS"
    ):
        raise RecurrentSuccessorDynamicExitV1Error(
            "static-exit regime robustness is not complete"
        )
    if summary.get("run_fingerprint") != SOURCE_STATIC_REGIME_RUN_FINGERPRINT:
        raise RecurrentSuccessorDynamicExitV1Error(
            "static-exit regime run fingerprint drifted"
        )
    if (
        summary.get("contract_fingerprint")
        != RECURRENT_SUCCESSOR_DAILY_EXIT_REGIME_ROBUSTNESS_CONTRACT_FINGERPRINT
    ):
        raise RecurrentSuccessorDynamicExitV1Error(
            "static-exit regime contract fingerprint drifted"
        )
    return summary


def _context_value(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return "UNKNOWN"
    return text


def _context_mapping(case: DailyPathCase) -> dict[str, str]:
    item = case.opportunity
    return {
        "policy_id": _context_value(item.policy_id),
        "market_volatility_state": _context_value(item.market_volatility_state),
        "higher_timeframe_ticker_trend": _context_value(
            item.higher_timeframe_ticker_trend
        ),
        "realized_volatility_bucket": _context_value(
            item.realized_volatility_bucket
        ),
        "market_direction_alignment": _context_value(
            item.market_direction_alignment
        ),
    }


def _context_key(
    case: DailyPathCase,
    dimensions: Sequence[str],
) -> tuple[str, ...]:
    mapping = _context_mapping(case)
    return tuple(mapping[name] for name in dimensions)


def _net_return_for_action(
    case: DailyPathCase,
    *,
    stop_fraction: float,
    target_fraction: float,
) -> float:
    resolved = resolve_daily_exit(
        case,
        stop_fraction=stop_fraction,
        target_fraction=target_fraction,
    )
    entry = float(case.bars[0].open)
    exit_price = float(resolved.exit_price_per_unit)
    half_cost = float(DAILY_PRIMARY_COST_BPS) / 20_000.0
    return (
        exit_price * (1.0 - half_cost)
        - entry * (1.0 + half_cost)
    ) / entry


def _reveal_action_outcomes(
    cases: Sequence[DailyPathCase],
    indexes: Sequence[int],
    outcomes: dict[tuple[int, str], float],
) -> None:
    for index in indexes:
        case = cases[index]
        for stop_fraction, target_fraction in DYNAMIC_EXIT_ACTIONS:
            action_id = dynamic_exit_action_id(stop_fraction, target_fraction)
            outcomes[(index, action_id)] = _net_return_for_action(
                case,
                stop_fraction=stop_fraction,
                target_fraction=target_fraction,
            )


def _cell_support(
    cases: Sequence[DailyPathCase],
    indexes: Sequence[int],
) -> tuple[int, int, int]:
    return (
        len(indexes),
        len({cases[index].opportunity.signal_session for index in indexes}),
        len({cases[index].opportunity.instrument_id for index in indexes}),
    )


def _supported(
    cases: Sequence[DailyPathCase],
    indexes: Sequence[int],
) -> bool:
    n, sessions, instruments = _cell_support(cases, indexes)
    return (
        n >= MIN_TRAINING_CASES
        and sessions >= MIN_TRAINING_SESSIONS
        and instruments >= MIN_TRAINING_INSTRUMENTS
    )


def _action_stats(
    cases: Sequence[DailyPathCase],
    indexes: Sequence[int],
    outcomes: dict[tuple[int, str], float],
    *,
    stop_fraction: float,
    target_fraction: float,
) -> DynamicExitActionStats:
    action_id = dynamic_exit_action_id(stop_fraction, target_fraction)
    values = [outcomes[(index, action_id)] for index in indexes]
    session_values: dict[date, list[float]] = defaultdict(list)
    for index, value in zip(indexes, values, strict=True):
        session_values[cases[index].opportunity.signal_session].append(value)
    session_means = [
        statistics.fmean(items)
        for _, items in sorted(session_values.items())
    ]
    mean_session = statistics.fmean(session_means)
    std_session = (
        0.0
        if len(session_means) < 2
        else statistics.stdev(session_means)
    )
    standard_error = (
        0.0
        if not session_means
        else std_session / math.sqrt(len(session_means))
    )
    lcb = mean_session - ONE_SIDED_LCB_Z * standard_error
    n, sessions, instruments = _cell_support(cases, indexes)
    return DynamicExitActionStats(
        action_id=action_id,
        stop_fraction=stop_fraction,
        target_fraction=target_fraction,
        training_cases=n,
        training_sessions=sessions,
        training_instruments=instruments,
        mean_trade_net_return=statistics.fmean(values),
        mean_session_net_return=mean_session,
        session_mean_standard_deviation=std_session,
        lcb_net_return=lcb,
        probability_positive=(
            sum(value > 0.0 for value in values) / len(values)
        ),
    )


def _choose_action(
    *,
    cases: Sequence[DailyPathCase],
    current_index: int,
    training_indexes: Sequence[int],
    outcomes: dict[tuple[int, str], float],
) -> DynamicExitChoice:
    current = cases[current_index]
    if any(
        cases[index].opportunity.fold_id >= current.opportunity.fold_id
        for index in training_indexes
    ):
        raise RecurrentSuccessorDynamicExitV1Error(
            "dynamic exit training set includes current/future fold"
        )

    for fallback_level, dimensions in enumerate(
        CONTEXT_FALLBACK_HIERARCHY,
        start=1,
    ):
        key = _context_key(current, dimensions)
        matching = [
            index
            for index in training_indexes
            if _context_key(cases[index], dimensions) == key
        ]
        if not _supported(cases, matching):
            continue

        stats = [
            _action_stats(
                cases,
                matching,
                outcomes,
                stop_fraction=stop_fraction,
                target_fraction=target_fraction,
            )
            for stop_fraction, target_fraction in DYNAMIC_EXIT_ACTIONS
        ]
        ranked = sorted(
            stats,
            key=lambda item: (
                -item.lcb_net_return,
                -item.mean_trade_net_return,
                -item.probability_positive,
                item.action_id,
            ),
        )
        best = ranked[0]
        fold_ids = [cases[index].opportunity.fold_id for index in matching]
        cutoff = max(
            cases[index].opportunity.signal_session for index in matching
        )
        if cutoff >= current.opportunity.signal_session:
            raise RecurrentSuccessorDynamicExitV1Error(
                "dynamic exit training cutoff is not before current signal"
            )
        if (
            best.lcb_net_return <= MIN_ACCEPTABLE_LCB
            or best.mean_trade_net_return <= 0.0
        ):
            return DynamicExitChoice(
                action_id=ABSTAIN_ACTION_ID,
                stop_fraction=None,
                target_fraction=None,
                fallback_level=fallback_level,
                context_dimensions=tuple(dimensions),
                context_key=key,
                training_cases=best.training_cases,
                training_sessions=best.training_sessions,
                training_instruments=best.training_instruments,
                training_fold_min=min(fold_ids),
                training_fold_max=max(fold_ids),
                training_cutoff_session=cutoff,
                selected_lcb_net_return=best.lcb_net_return,
                selected_mean_trade_net_return=best.mean_trade_net_return,
                selected_probability_positive=best.probability_positive,
                reason="NO_SUPPORTED_ACTION_HAS_POSITIVE_ROBUST_LCB",
            )

        return DynamicExitChoice(
            action_id=best.action_id,
            stop_fraction=best.stop_fraction,
            target_fraction=best.target_fraction,
            fallback_level=fallback_level,
            context_dimensions=tuple(dimensions),
            context_key=key,
            training_cases=best.training_cases,
            training_sessions=best.training_sessions,
            training_instruments=best.training_instruments,
            training_fold_min=min(fold_ids),
            training_fold_max=max(fold_ids),
            training_cutoff_session=cutoff,
            selected_lcb_net_return=best.lcb_net_return,
            selected_mean_trade_net_return=best.mean_trade_net_return,
            selected_probability_positive=best.probability_positive,
            reason="HIGHEST_POSITIVE_SUPPORTED_ROBUST_LCB",
        )

    return DynamicExitChoice(
        action_id=ABSTAIN_ACTION_ID,
        stop_fraction=None,
        target_fraction=None,
        fallback_level=None,
        context_dimensions=(),
        context_key=(),
        training_cases=0,
        training_sessions=0,
        training_instruments=0,
        training_fold_min=None,
        training_fold_max=None,
        training_cutoff_session=None,
        selected_lcb_net_return=None,
        selected_mean_trade_net_return=None,
        selected_probability_positive=None,
        reason="INSUFFICIENT_PRIOR_CONTEXT_SUPPORT",
    )


def _year_summary(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[int(str(row["signal_session"])[:4])].append(row)

    result: list[dict[str, object]] = []
    for year, items in sorted(grouped.items()):
        selected = [item for item in items if item["action_id"] != ABSTAIN_ACTION_ID]
        realized = [float(item["realized_net_return"]) for item in selected]
        actions = Counter(str(item["action_id"]) for item in selected)
        reasons = Counter(str(item["reason"]) for item in items if item["action_id"] == ABSTAIN_ACTION_ID)
        result.append(
            {
                "year": year,
                "cases": len(items),
                "selected": len(selected),
                "abstained": len(items) - len(selected),
                "selection_rate": len(selected) / len(items) if items else 0.0,
                "mean_selected_realized_net_return": (
                    None if not realized else statistics.fmean(realized)
                ),
                "median_selected_realized_net_return": (
                    None if not realized else statistics.median(realized)
                ),
                "probability_positive_selected_realized": (
                    None
                    if not realized
                    else sum(value > 0.0 for value in realized) / len(realized)
                ),
                "action_counts": dict(sorted(actions.items())),
                "abstain_reasons": dict(sorted(reasons.items())),
            }
        )
    return result


def run_recurrent_successor_dynamic_exit_v1(
    project_root: Path,
    *,
    policy_ids: Sequence[str] = (),
    output_root: Path | None = None,
    duckdb_threads: int | None = None,
) -> dict[str, object]:
    project = Path(project_root).resolve()
    static_summary = _source_static_regime_summary(project)
    start_session, end_session = DEVELOPMENT_SCOPE

    print(
        "dynamic exit v1: loading accepted daily LONG cases and point-in-time context "
        f"for {start_session} -> {end_session}",
        flush=True,
    )
    cases, source = load_daily_exit_cases(
        project,
        start_session=start_session,
        end_session=end_session,
        policy_ids=policy_ids,
        duckdb_threads=duckdb_threads,
    )
    if not cases:
        raise RecurrentSuccessorDynamicExitV1Error(
            "dynamic exit v1 selected no usable daily LONG cases"
        )

    run_identity = {
        "contract_fingerprint": RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
        "source_static_regime_report_fingerprint": static_summary.get(
            "report_fingerprint"
        ),
        "source": source,
        "policy_ids": sorted(set(str(value) for value in policy_ids)),
        "case_count": len(cases),
    }
    run_fingerprint = _stable_hash(run_identity)
    root = (
        Path(output_root).resolve()
        if output_root is not None
        else (
            project
            / "data"
            / "research"
            / "recurrent_successor_dynamic_exit_v1"
            / RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT[:16]
            / run_fingerprint[:16]
        )
    )
    root.mkdir(parents=True, exist_ok=True)

    known_outcomes: dict[tuple[int, str], float] = {}
    by_fold: dict[int, list[int]] = defaultdict(list)
    for index, case in enumerate(cases):
        by_fold[case.opportunity.fold_id].append(index)
    ordered_folds = sorted(by_fold)

    print(
        "dynamic exit v1: "
        f"{len(cases):,} cases / {len(ordered_folds)} folds / "
        f"{len(DYNAMIC_EXIT_ACTIONS)} actions + ABSTAIN",
        flush=True,
    )

    assignments: list[dict[str, object]] = []
    for fold_position, fold_id in enumerate(ordered_folds, start=1):
        training_folds = [
            prior
            for prior in ordered_folds
            if fold_id - LOOKBACK_COMPLETED_FOLDS <= prior < fold_id
        ]
        training_indexes = [
            index
            for prior in training_folds
            for index in by_fold[prior]
        ]
        current_indexes = by_fold[fold_id]
        selected_count = 0
        for current_index in current_indexes:
            case = cases[current_index]
            choice = _choose_action(
                cases=cases,
                current_index=current_index,
                training_indexes=training_indexes,
                outcomes=known_outcomes,
            )
            assignments.append(
                {
                    "opportunity_id": case.opportunity.opportunity_id,
                    "fold_id": fold_id,
                    "policy_id": case.opportunity.policy_id,
                    "economic_family_id": case.opportunity.economic_family_id,
                    "ticker": case.opportunity.ticker,
                    "instrument_id": case.opportunity.instrument_id,
                    "signal_session": case.opportunity.signal_session,
                    "selector_score": case.opportunity.selector_score,
                    "market_volatility_state": case.opportunity.market_volatility_state,
                    "higher_timeframe_ticker_trend": (
                        case.opportunity.higher_timeframe_ticker_trend
                    ),
                    "realized_volatility_bucket": (
                        case.opportunity.realized_volatility_bucket
                    ),
                    "market_direction_alignment": (
                        case.opportunity.market_direction_alignment
                    ),
                    "action_id": choice.action_id,
                    "stop_fraction": choice.stop_fraction,
                    "target_fraction": choice.target_fraction,
                    "fallback_level": choice.fallback_level,
                    "context_dimensions": choice.context_dimensions,
                    "context_key": choice.context_key,
                    "training_cases": choice.training_cases,
                    "training_sessions": choice.training_sessions,
                    "training_instruments": choice.training_instruments,
                    "training_fold_min": choice.training_fold_min,
                    "training_fold_max": choice.training_fold_max,
                    "training_cutoff_session": choice.training_cutoff_session,
                    "selected_lcb_net_return": choice.selected_lcb_net_return,
                    "selected_mean_trade_net_return": (
                        choice.selected_mean_trade_net_return
                    ),
                    "selected_probability_positive": (
                        choice.selected_probability_positive
                    ),
                    "reason": choice.reason,
                    "realized_net_return": None,
                    "realized_exit_disposition": None,
                }
            )

        # Freeze every decision in this fold before revealing any current-fold
        # counterfactual exit outcome. Only after the fold is fully assigned do
        # these paths become evidence eligible for later completed folds.
        _reveal_action_outcomes(cases, current_indexes, known_outcomes)
        assignment_by_id = {
            str(item["opportunity_id"]): item
            for item in assignments
            if int(item["fold_id"]) == fold_id
        }
        for current_index in current_indexes:
            case = cases[current_index]
            row = assignment_by_id[case.opportunity.opportunity_id]
            if row["action_id"] == ABSTAIN_ACTION_ID:
                continue
            selected_count += 1
            action_id = str(row["action_id"])
            row["realized_net_return"] = known_outcomes[(current_index, action_id)]
            resolved = resolve_daily_exit(
                case,
                stop_fraction=float(row["stop_fraction"]),
                target_fraction=float(row["target_fraction"]),
            )
            row["realized_exit_disposition"] = resolved.disposition

        print(
            f"  fold {fold_position}/{len(ordered_folds)} id={fold_id}: "
            f"training={len(training_indexes):,} current={len(current_indexes):,} "
            f"selected={selected_count:,} abstained="
            f"{len(current_indexes) - selected_count:,}",
            flush=True,
        )

    selected_rows = [
        item for item in assignments if item["action_id"] != ABSTAIN_ACTION_ID
    ]
    realized = [
        float(item["realized_net_return"])
        for item in selected_rows
        if item["realized_net_return"] is not None
    ]
    action_counts = Counter(str(item["action_id"]) for item in selected_rows)
    fallback_counts = Counter(
        str(item["fallback_level"]) for item in selected_rows
    )
    abstain_reasons = Counter(
        str(item["reason"])
        for item in assignments
        if item["action_id"] == ABSTAIN_ACTION_ID
    )
    dispositions = Counter(
        str(item["realized_exit_disposition"])
        for item in selected_rows
        if item["realized_exit_disposition"] is not None
    )

    report: dict[str, object] = {
        "status": "COMPLETE_DYNAMIC_EXIT_V1_SELECTOR_DIAGNOSTIC",
        "contract": RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT,
        "contract_fingerprint": (
            RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT
        ),
        "run_fingerprint": run_fingerprint,
        "source_static_regime_run_fingerprint": (
            SOURCE_STATIC_REGIME_RUN_FINGERPRINT
        ),
        "source_static_regime_report_fingerprint": static_summary.get(
            "report_fingerprint"
        ),
        "source": source,
        "scope": {
            "start_session": start_session,
            "end_session": end_session,
            "policy_ids": sorted(set(str(value) for value in policy_ids)),
        },
        "usable_cases": len(cases),
        "selected_cases": len(selected_rows),
        "abstained_cases": len(assignments) - len(selected_rows),
        "selection_rate": len(selected_rows) / len(assignments),
        "selected_action_counts": dict(sorted(action_counts.items())),
        "selected_fallback_level_counts": dict(sorted(fallback_counts.items())),
        "abstain_reasons": dict(sorted(abstain_reasons.items())),
        "realized_exit_dispositions": dict(sorted(dispositions.items())),
        "selected_realized_trade_diagnostics": {
            "mean_net_return": None if not realized else statistics.fmean(realized),
            "median_net_return": None if not realized else statistics.median(realized),
            "probability_positive": (
                None
                if not realized
                else sum(value > 0.0 for value in realized) / len(realized)
            ),
        },
        "year_summary": _year_summary(assignments),
        "interpretation": {
            "portfolio_return_computed": False,
            "capital_competition_computed": False,
            "compounding_computed": False,
            "current_case_future_path_used_for_selection": False,
            "current_fold_outcomes_used_for_selection": False,
            "diagnostic_only": True,
            "next_gate": (
                "RECURRENT_ACCOUNT_REPLAY_WITH_DECISION_BOUND_DYNAMIC_ACTIONS"
            ),
        },
        "authority": AUTHORITY,
    }
    report["report_fingerprint"] = _stable_hash(report)
    _write_json(root / "dynamic_exit_v1_summary.json", report)
    _write_jsonl(root / "dynamic_exit_assignments.jsonl", assignments)
    return report
