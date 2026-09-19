from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import duckdb
import pandas as pd

from packages.backtesting.recurrent_successor_daily_exit_sweep_contract import (
    ACCEPTED_SELECTED_DAILY_PATH_ANALYSIS_FINGERPRINT,
    AUTHORITY,
    GAP_THROUGH_STOP_POLICY,
    GAP_THROUGH_TARGET_POLICY,
    MIN_PRIOR_SELECTED_PATH_CASES,
    RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
    RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
    SAME_SESSION_COLLISION_POLICY,
    STOP_TARGET_POLICY_PAIRS,
)
from packages.backtesting.recurrent_successor_outcome_replay import (
    SelectedReplayOpportunity,
    _canonicalize,
    _liquidity_score,
    _sha256_file,
    _stable_hash,
    _write_json,
    _write_jsonl,
    load_selected_replay_opportunities,
)
from packages.backtesting.recurrent_successor_outcome_replay_contract import (
    INITIAL_POSITION_FRACTION,
    MAX_OPEN_POSITIONS,
    MAX_POSITIONS_PER_FAMILY,
)
from packages.backtesting.successor_selected_daily_path_analysis import (
    _validated_daily_source,
    selected_daily_path_root,
)
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import ActionabilityPolicy, TradeExpressionMode
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
)
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    build_simulation_decision_record,
)
from packages.simulation.forecast_horizon_clock import (
    ForecastHorizonClockPolicyV1,
    SessionHorizonCountingPolicy,
    build_forecast_horizon_clock_v1,
)
from packages.simulation.market_mark_evidence import (
    MarketMarkInputs,
    MarketMarkTransport,
    build_simulated_market_mark_evidence,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RecurrentDecisionStockExitPlanV1,
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_v1,
)
from packages.simulation.recurrent_engine import RecurrentLifecycleCoordinatorV1
from packages.simulation.recurrent_entry_evidence import (
    build_recurrent_entry_fill_evidence,
    build_recurrent_funding_terms,
)
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_genesis import build_empty_recurrent_genesis_account_v1
from packages.simulation.recurrent_lifecycle_state import RecurrentLifecycleEventKind
from packages.simulation.simulated_fill import SimulatedEntryFillInputs
from packages.strategies.successor_conditioning_contract import (
    DAILY_PRIMARY_COST_BPS,
    DAILY_PRIMARY_HORIZON_SESSIONS,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
)
from packages.strategies.successor_selected_daily_path_contract import (
    MOVE_THRESHOLDS,
    SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
)


class RecurrentSuccessorDailyExitSweepError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PriorPathEvidence:
    fold_id: int
    policy_id: str
    direction: str
    sample_size: int
    evidence_cutoff_session: date
    thresholds: tuple[MoveThresholdProbability, ...]
    source_fingerprint: str


@dataclass(frozen=True, slots=True)
class DailyPathBar:
    session_offset: int
    session_date: date
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True, slots=True)
class DailyPathCase:
    opportunity: SelectedReplayOpportunity
    bars: tuple[DailyPathBar, ...]
    prior_path_evidence: PriorPathEvidence


@dataclass(frozen=True, slots=True)
class ResolvedDailyExit:
    disposition: str
    exit_session_offset: int
    exit_session_date: date
    exit_price_per_unit: float
    stop_touched: bool
    target_touched: bool
    same_session_collision: bool
    gap_through_stop: bool
    gap_through_target: bool


@dataclass(slots=True)
class _Slot:
    case: DailyPathCase
    decision: SimulationDecisionRecord
    resolved_exit: ResolvedDailyExit
    position_fingerprint: str | None = None
    exit_plan: RecurrentDecisionStockExitPlanV1 | None = None
    state: str = "RESERVED"


_ACTIONABILITY_POLICY = ActionabilityPolicy(
    min_expected_net_value=0.0,
    min_expected_return_on_capital=0.0,
    min_probability_profit=0.0,
    max_expected_loss_to_gain_ratio=1_000_000.0,
    max_execution_cost_to_expected_gain_ratio=1_000_000.0,
    min_liquidity_score=0.0,
    material_superiority_ratio=1.0,
)


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RecurrentSuccessorDailyExitSweepError(
            f"invalid JSON artifact: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RecurrentSuccessorDailyExitSweepError(
            f"JSON artifact is not an object: {path}"
        )
    return value


def _validated_daily_path_artifacts(
    project_root: Path,
) -> tuple[Path, Path, dict[str, object]]:
    root = selected_daily_path_root(project_root)
    summary_path = root / "analysis_summary.json"
    summary = _load_json(summary_path)
    if summary.get("status") != "COMPLETE_SELECTED_DAILY_PATH_DIAGNOSTICS_ONLY":
        raise RecurrentSuccessorDailyExitSweepError(
            "accepted selected daily path analysis is not complete"
        )
    if (
        summary.get("selected_daily_path_fingerprint")
        != SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT
    ):
        raise RecurrentSuccessorDailyExitSweepError(
            "selected daily path contract fingerprint drifted"
        )
    if (
        summary.get("analysis_fingerprint")
        != ACCEPTED_SELECTED_DAILY_PATH_ANALYSIS_FINGERPRINT
    ):
        raise RecurrentSuccessorDailyExitSweepError(
            "selected daily path accepted analysis fingerprint drifted"
        )
    outputs = summary.get("outputs")
    if not isinstance(outputs, list):
        raise RecurrentSuccessorDailyExitSweepError(
            "selected daily path output inventory is missing"
        )
    lookup = {
        str(item.get("name")): item
        for item in outputs
        if isinstance(item, dict)
    }
    path_item = lookup.get("selected_daily_paths")
    threshold_item = lookup.get("selected_daily_thresholds")
    if not isinstance(path_item, dict) or not isinstance(threshold_item, dict):
        raise RecurrentSuccessorDailyExitSweepError(
            "selected daily path artifacts are missing"
        )
    path_file = Path(str(path_item["path"])).resolve()
    threshold_file = Path(str(threshold_item["path"])).resolve()
    for item, path in ((path_item, path_file), (threshold_item, threshold_file)):
        if not path.is_file():
            raise RecurrentSuccessorDailyExitSweepError(
                f"selected daily path artifact is missing: {path}"
            )
        if _sha256_file(path) != str(item.get("sha256")):
            raise RecurrentSuccessorDailyExitSweepError(
                f"selected daily path artifact hash drifted: {path}"
            )
    return path_file, threshold_file, summary


def _prior_path_evidence(
    *,
    opportunities: Sequence[SelectedReplayOpportunity],
    threshold_file: Path,
) -> dict[tuple[int, str, str], PriorPathEvidence]:
    target_rows = sorted(
        {
            (item.fold_id, item.policy_id, item.direction)
            for item in opportunities
            if item.native_timeframe == "1d" and item.direction == "LONG"
        }
    )
    if not target_rows:
        return {}
    targets = pd.DataFrame(
        target_rows,
        columns=["fold_id", "policy_id", "direction"],
    )
    conn = duckdb.connect()
    try:
        conn.register("target_exit_evidence", targets)
        frame = conn.execute(
            f"""
            SELECT
                t.fold_id,
                t.policy_id,
                t.direction,
                h.move_threshold,
                count(*) AS sample_size,
                max(h.session_date) AS evidence_cutoff_session,
                avg(CASE WHEN h.first_favorable_session IS NOT NULL THEN 1.0 ELSE 0.0 END)
                    AS favorable_touch_probability,
                avg(CASE WHEN h.first_adverse_session IS NOT NULL THEN 1.0 ELSE 0.0 END)
                    AS adverse_touch_probability,
                avg(CASE WHEN h.first_touch_class IN ('FAVORABLE_ONLY','FAVORABLE_FIRST')
                         THEN 1.0 ELSE 0.0 END)
                    AS favorable_before_adverse_probability,
                avg(CASE WHEN h.first_touch_class IN ('ADVERSE_ONLY','ADVERSE_FIRST')
                         THEN 1.0 ELSE 0.0 END)
                    AS adverse_before_favorable_probability,
                avg(CASE WHEN h.first_touch_class='SAME_SESSION_COLLISION_UNORDERED'
                         THEN 1.0 ELSE 0.0 END)
                    AS same_interval_collision_probability,
                median(h.first_favorable_session)
                    FILTER (WHERE h.first_favorable_session IS NOT NULL)
                    AS median_favorable_time
            FROM target_exit_evidence t
            JOIN read_parquet('{_sql_path(threshold_file)}') h
              ON h.policy_id=t.policy_id
             AND h.direction=t.direction
             AND h.fold_id < t.fold_id
            GROUP BY 1,2,3,4
            ORDER BY 1,2,3,4
            """
        ).fetchdf()
    finally:
        conn.unregister("target_exit_evidence")
        conn.close()

    grouped: dict[tuple[int, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in frame.to_dict("records"):
        grouped[
            (int(row["fold_id"]), str(row["policy_id"]), str(row["direction"]))
        ].append(row)

    evidence: dict[tuple[int, str, str], PriorPathEvidence] = {}
    expected_thresholds = tuple(float(value) for value in MOVE_THRESHOLDS)
    for key, rows in grouped.items():
        by_threshold = {
            float(row["move_threshold"]): row
            for row in rows
        }
        if tuple(sorted(by_threshold)) != expected_thresholds:
            continue
        minimum_sample = min(int(row["sample_size"]) for row in rows)
        if minimum_sample < MIN_PRIOR_SELECTED_PATH_CASES:
            continue
        cutoff = max(
            pd.Timestamp(row["evidence_cutoff_session"]).date()
            for row in rows
        )
        threshold_objects: list[MoveThresholdProbability] = []
        for threshold in expected_thresholds:
            row = by_threshold[threshold]
            favorable = float(row["favorable_touch_probability"])
            median_time = (
                None
                if pd.isna(row["median_favorable_time"])
                else float(row["median_favorable_time"])
            )
            if favorable <= 0.0:
                median_time = None
            threshold_objects.append(
                MoveThresholdProbability(
                    threshold_fraction=threshold,
                    favorable_touch_probability=favorable,
                    adverse_touch_probability=float(
                        row["adverse_touch_probability"]
                    ),
                    favorable_before_adverse_probability=float(
                        row["favorable_before_adverse_probability"]
                    ),
                    adverse_before_favorable_probability=float(
                        row["adverse_before_favorable_probability"]
                    ),
                    same_interval_collision_probability=float(
                        row["same_interval_collision_probability"]
                    ),
                    median_favorable_time=median_time,
                )
            )
        source_payload = {
            "accepted_selected_daily_path_analysis_fingerprint": (
                ACCEPTED_SELECTED_DAILY_PATH_ANALYSIS_FINGERPRINT
            ),
            "fold_id": key[0],
            "policy_id": key[1],
            "direction": key[2],
            "sample_size": minimum_sample,
            "evidence_cutoff_session": cutoff,
            "thresholds": threshold_objects,
        }
        evidence[key] = PriorPathEvidence(
            fold_id=key[0],
            policy_id=key[1],
            direction=key[2],
            sample_size=minimum_sample,
            evidence_cutoff_session=cutoff,
            thresholds=tuple(threshold_objects),
            source_fingerprint=_stable_hash(source_payload),
        )
    return evidence


def _load_daily_bars(
    project_root: Path,
    opportunities: Sequence[SelectedReplayOpportunity],
) -> tuple[dict[str, tuple[DailyPathBar, ...]], dict[str, object]]:
    requests = pd.DataFrame(
        [
            {
                "opportunity_id": item.opportunity_id,
                "instrument_id": item.instrument_id,
                "signal_session": item.signal_session,
            }
            for item in opportunities
            if item.native_timeframe == "1d" and item.direction == "LONG"
        ]
    )
    if requests.empty:
        return {}, {}
    conn = duckdb.connect()
    conn.execute(f"PRAGMA threads={max(1, min(8, (os.cpu_count() or 4) - 2))}")
    conn.execute("PRAGMA preserve_insertion_order=false")
    conn.register("daily_exit_requests", requests)
    try:
        print(
            "daily exit sweep source: verifying accepted daily V2 lineage...",
            flush=True,
        )
        source_sql, source_report = _validated_daily_source(conn, project_root)
        print(
            "daily exit sweep source: lineage verified; projecting selected instruments...",
            flush=True,
        )
        conn.execute(
            """
            CREATE TEMP TABLE daily_exit_instruments AS
            SELECT DISTINCT instrument_id FROM daily_exit_requests
            """
        )
        conn.execute(
            f"""
            CREATE TEMP TABLE daily_exit_ordered_bars AS
            SELECT
                b.instrument_id,
                b.session_date,
                b.open,
                b.high,
                b.low,
                b.close,
                row_number() OVER (
                    PARTITION BY b.instrument_id ORDER BY b.session_date
                ) AS rn
            FROM {source_sql} b
            JOIN daily_exit_instruments i
              ON i.instrument_id=b.instrument_id
            WHERE b.session_date BETWEEN DATE '{DEVELOPMENT_START}'
                                     AND DATE '{DEVELOPMENT_END}'
            """
        )
        conn.execute(
            """
            CREATE TEMP TABLE daily_exit_signal_positions AS
            SELECT r.*, b.rn AS signal_rn
            FROM daily_exit_requests r
            JOIN daily_exit_ordered_bars b
              ON b.instrument_id=r.instrument_id
             AND b.session_date=r.signal_session
            """
        )
        joined = int(
            conn.execute(
                "SELECT count(*) FROM daily_exit_signal_positions"
            ).fetchone()[0]
        )
        if joined != len(requests):
            raise RecurrentSuccessorDailyExitSweepError(
                f"daily signal/source join incomplete: {joined} != {len(requests)}"
            )
        frame = conn.execute(
            f"""
            SELECT
                s.opportunity_id,
                b.rn - s.signal_rn AS session_offset,
                b.session_date,
                b.open,
                b.high,
                b.low,
                b.close
            FROM daily_exit_signal_positions s
            JOIN daily_exit_ordered_bars b
              ON b.instrument_id=s.instrument_id
             AND b.rn BETWEEN s.signal_rn + 1
                          AND s.signal_rn + {DAILY_PRIMARY_HORIZON_SESSIONS}
            ORDER BY s.opportunity_id, session_offset
            """
        ).fetchdf()
    finally:
        conn.unregister("daily_exit_requests")
        conn.close()

    grouped: dict[str, list[DailyPathBar]] = defaultdict(list)
    for row in frame.to_dict("records"):
        grouped[str(row["opportunity_id"])].append(
            DailyPathBar(
                session_offset=int(row["session_offset"]),
                session_date=pd.Timestamp(row["session_date"]).date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            )
        )
    result: dict[str, tuple[DailyPathBar, ...]] = {}
    for item in opportunities:
        if item.native_timeframe != "1d" or item.direction != "LONG":
            continue
        bars = tuple(grouped.get(item.opportunity_id, ()))
        if len(bars) != DAILY_PRIMARY_HORIZON_SESSIONS:
            raise RecurrentSuccessorDailyExitSweepError(
                f"daily path coverage incomplete for {item.opportunity_id}: "
                f"{len(bars)} != {DAILY_PRIMARY_HORIZON_SESSIONS}"
            )
        if tuple(bar.session_offset for bar in bars) != tuple(
            range(1, DAILY_PRIMARY_HORIZON_SESSIONS + 1)
        ):
            raise RecurrentSuccessorDailyExitSweepError(
                "daily path offsets are not contiguous"
            )
        for bar in bars:
            values = (bar.open, bar.high, bar.low, bar.close)
            if not all(math.isfinite(value) and value > 0.0 for value in values):
                raise RecurrentSuccessorDailyExitSweepError(
                    "daily path contains invalid OHLC"
                )
            if bar.high < max(bar.open, bar.close) or bar.low > min(
                bar.open, bar.close
            ):
                raise RecurrentSuccessorDailyExitSweepError(
                    "daily path OHLC geometry is invalid"
                )
        result[item.opportunity_id] = bars
    return result, source_report


def load_daily_exit_cases(
    project_root: Path,
    *,
    start_session: date,
    end_session: date,
    policy_ids: Sequence[str] = (),
    duckdb_threads: int | None = None,
) -> tuple[tuple[DailyPathCase, ...], dict[str, object]]:
    path_file, threshold_file, path_summary = _validated_daily_path_artifacts(
        project_root
    )
    opportunities, replay_source = load_selected_replay_opportunities(
        project_root,
        start_session=start_session,
        end_session=end_session,
        policy_ids=policy_ids,
        duckdb_threads=duckdb_threads,
    )
    daily_long = tuple(
        item
        for item in opportunities
        if item.native_timeframe == "1d" and item.direction == "LONG"
    )
    if not daily_long:
        raise RecurrentSuccessorDailyExitSweepError(
            "selected scope contains no supported daily LONG opportunities"
        )
    evidence = _prior_path_evidence(
        opportunities=daily_long,
        threshold_file=threshold_file,
    )
    bars, daily_source = _load_daily_bars(project_root, daily_long)
    cases: list[DailyPathCase] = []
    missing_evidence = 0
    for item in daily_long:
        key = (item.fold_id, item.policy_id, item.direction)
        prior = evidence.get(key)
        if prior is None:
            missing_evidence += 1
            continue
        _, cutoff_utc = __import__(
            "packages.core.market_calendar",
            fromlist=["get_market_calendar"],
        ).get_market_calendar().regular_open_close(prior.evidence_cutoff_session)
        if cutoff_utc >= item.decision_utc:
            raise RecurrentSuccessorDailyExitSweepError(
                "prior path evidence is not strictly before decision time"
            )
        cases.append(
            DailyPathCase(
                opportunity=item,
                bars=bars[item.opportunity_id],
                prior_path_evidence=prior,
            )
        )
    if not cases:
        raise RecurrentSuccessorDailyExitSweepError(
            "no daily LONG cases have sufficient strictly-prior path evidence"
        )
    source = {
        "replay_source": replay_source,
        "selected_daily_path_analysis_fingerprint": path_summary[
            "analysis_fingerprint"
        ],
        "selected_daily_path_file_sha256": _sha256_file(path_file),
        "selected_daily_threshold_file_sha256": _sha256_file(threshold_file),
        "daily_source_report": daily_source,
        "eligible_daily_long_cases": len(daily_long),
        "sufficient_prior_path_cases": len(cases),
        "insufficient_prior_path_evidence_cases": missing_evidence,
    }
    print(
        "daily exit sweep cases: "
        f"{len(cases):,} usable / {len(daily_long):,} selected daily LONG; "
        f"{missing_evidence:,} lack prior path support",
        flush=True,
    )
    return tuple(cases), source


def _forecast_for_case(case: DailyPathCase) -> UnderlyingMoveTimeForecast:
    item = case.opportunity
    prior = case.prior_path_evidence
    calendar = __import__(
        "packages.core.market_calendar",
        fromlist=["get_market_calendar"],
    ).get_market_calendar()
    _, training_cutoff = calendar.regular_open_close(item.training_end)
    _, path_cutoff = calendar.regular_open_close(prior.evidence_cutoff_session)
    evidence_cutoff = max(training_cutoff, path_cutoff)
    source_payload = {
        "training_source": item.source_analysis_fingerprint,
        "fold_id": item.fold_id,
        "policy_id": item.policy_id,
        "training_start": item.training_start,
        "training_end": item.training_end,
        "training_sample_size": item.training_sample_size,
        "training_distribution": {
            "mean": item.training_mean_gross_return,
            "p10": item.training_p10_gross_return,
            "p25": item.training_p25_gross_return,
            "median": item.training_median_gross_return,
            "p75": item.training_p75_gross_return,
            "p90": item.training_p90_gross_return,
            "probability_positive": item.training_probability_positive_gross,
        },
        "prior_path_source_fingerprint": prior.source_fingerprint,
        "prior_path_sample_size": prior.sample_size,
        "prior_path_cutoff": prior.evidence_cutoff_session,
        "thresholds": prior.thresholds,
    }
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=item.instrument_id,
        ticker=item.ticker,
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=item.decision_utc,
        evidence_cutoff_utc=evidence_cutoff,
        horizon_unit=ForecastHorizonUnit.SESSIONS,
        horizon_value=DAILY_PRIMARY_HORIZON_SESSIONS,
        method_id="SUCCESSOR_TRAINING_CELL_PLUS_PRIOR_OOS_DAILY_PATH_V1",
        source_label="TRAINING_RETURN_DISTRIBUTION_AND_PRIOR_SELECTED_PATHS",
        source_fingerprint=_stable_hash(source_payload),
        sample_size=min(item.training_sample_size, prior.sample_size),
        reference_price=100.0,
        mean_signed_return=item.training_mean_gross_return,
        median_signed_return=item.training_median_gross_return,
        p10_signed_return=item.training_p10_gross_return,
        p25_signed_return=item.training_p25_gross_return,
        p75_signed_return=item.training_p75_gross_return,
        p90_signed_return=item.training_p90_gross_return,
        probability_positive_return=item.training_probability_positive_gross,
        mean_mfe=max(0.0, item.training_mean_mfe),
        mean_mae=max(0.0, item.training_mean_mae),
        thresholds=prior.thresholds,
        uncertainty_score=None,
        reason_codes=(
            "RETURN_DISTRIBUTION_FROM_CURRENT_FOLD_TRAINING_CELL_ONLY",
            "THRESHOLD_PATH_PROBABILITIES_FROM_STRICTLY_PRIOR_SELECTED_FOLDS_ONLY",
            "CURRENT_FOLD_OUTCOME_NOT_USED_IN_FORECAST",
            "DAILY_FIVE_SESSION_HORIZON",
        ),
    )


def _build_decision(
    case: DailyPathCase,
    *,
    account_book_equity: float,
) -> SimulationDecisionRecord:
    if not math.isfinite(account_book_equity) or account_book_equity <= 0.0:
        raise RecurrentSuccessorDailyExitSweepError(
            "positive current book equity is required"
        )
    item = case.opportunity
    notional = account_book_equity * INITIAL_POSITION_FRACTION
    half_cost_bps = float(DAILY_PRIMARY_COST_BPS) / 2.0
    entry_fee = notional * half_cost_bps / 10_000.0
    forecast = _forecast_for_case(case)
    return build_simulation_decision_record(
        decision_created_utc=item.decision_utc,
        forecast=forecast,
        stock_inputs=StockEconomicsInputs(
            position_notional_dollars=notional,
            capital_required_dollars=notional + entry_fee,
            entry_slippage_bps=half_cost_bps,
            exit_slippage_bps=half_cost_bps,
            round_trip_commission_dollars=0.0,
            round_trip_fees_dollars=0.0,
            horizon_borrow_cost_dollars=0.0,
            horizon_financing_cost_dollars=0.0,
            net_probability_profit=max(
                0.0,
                min(
                    item.training_probability_positive_net,
                    item.training_probability_positive_gross,
                ),
            ),
            liquidity_score=_liquidity_score(item.liquidity_bucket),
            executable=True,
            risk_budget_ok=True,
            shortable_if_bearish=False,
        ),
        actionability_policy=_ACTIONABILITY_POLICY,
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(),
    )


def _exit_policy(
    stop_fraction: float,
    target_fraction: float,
) -> StockExitPolicyInputsV1:
    payload = {
        "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
        "stop_fraction": stop_fraction,
        "target_fraction": target_fraction,
        "same_session_collision": SAME_SESSION_COLLISION_POLICY,
        "gap_through_stop": GAP_THROUGH_STOP_POLICY,
        "gap_through_target": GAP_THROUGH_TARGET_POLICY,
        "time_exit_sessions": DAILY_PRIMARY_HORIZON_SESSIONS,
    }
    return StockExitPolicyInputsV1(
        policy_id=(
            f"daily_stop_{int(round(stop_fraction * 100)):02d}_"
            f"target_{int(round(target_fraction * 100)):02d}_v1"
        ),
        policy_fingerprint=_stable_hash(payload),
        stop_threshold_fraction=stop_fraction,
        target_threshold_fraction=target_fraction,
        time_exit_enabled=False,
    )


def resolve_daily_exit(
    case: DailyPathCase,
    *,
    stop_fraction: float,
    target_fraction: float,
) -> ResolvedDailyExit:
    entry = case.bars[0].open
    stop = entry * (1.0 - stop_fraction)
    target = entry * (1.0 + target_fraction)
    for bar in case.bars:
        gap_stop = bar.open <= stop
        gap_target = bar.open >= target
        if gap_stop:
            return ResolvedDailyExit(
                disposition="STOP",
                exit_session_offset=bar.session_offset,
                exit_session_date=bar.session_date,
                exit_price_per_unit=bar.open,
                stop_touched=True,
                target_touched=bar.high >= target,
                same_session_collision=bar.high >= target,
                gap_through_stop=True,
                gap_through_target=False,
            )
        if gap_target:
            return ResolvedDailyExit(
                disposition="TARGET",
                exit_session_offset=bar.session_offset,
                exit_session_date=bar.session_date,
                exit_price_per_unit=target,
                stop_touched=bar.low <= stop,
                target_touched=True,
                same_session_collision=bar.low <= stop,
                gap_through_stop=False,
                gap_through_target=True,
            )
        stop_touch = bar.low <= stop
        target_touch = bar.high >= target
        if stop_touch and target_touch:
            return ResolvedDailyExit(
                disposition="STOP",
                exit_session_offset=bar.session_offset,
                exit_session_date=bar.session_date,
                exit_price_per_unit=stop,
                stop_touched=True,
                target_touched=True,
                same_session_collision=True,
                gap_through_stop=False,
                gap_through_target=False,
            )
        if stop_touch:
            return ResolvedDailyExit(
                disposition="STOP",
                exit_session_offset=bar.session_offset,
                exit_session_date=bar.session_date,
                exit_price_per_unit=stop,
                stop_touched=True,
                target_touched=False,
                same_session_collision=False,
                gap_through_stop=False,
                gap_through_target=False,
            )
        if target_touch:
            return ResolvedDailyExit(
                disposition="TARGET",
                exit_session_offset=bar.session_offset,
                exit_session_date=bar.session_date,
                exit_price_per_unit=target,
                stop_touched=False,
                target_touched=True,
                same_session_collision=False,
                gap_through_stop=False,
                gap_through_target=False,
            )
    final_bar = case.bars[-1]
    return ResolvedDailyExit(
        disposition="TIME",
        exit_session_offset=final_bar.session_offset,
        exit_session_date=final_bar.session_date,
        exit_price_per_unit=final_bar.close,
        stop_touched=False,
        target_touched=False,
        same_session_collision=False,
        gap_through_stop=False,
        gap_through_target=False,
    )


def _bar_close_for_session(
    case: DailyPathCase,
    session_date: date,
) -> float | None:
    for bar in case.bars:
        if bar.session_date == session_date:
            return bar.close
    return None


def _event_time(session_date: date, *, which: str) -> datetime:
    calendar = __import__(
        "packages.core.market_calendar",
        fromlist=["get_market_calendar"],
    ).get_market_calendar()
    regular_open, regular_close = calendar.regular_open_close(session_date)
    return regular_open if which == "OPEN" else regular_close


def _simulate_policy(
    cases: Sequence[DailyPathCase],
    *,
    initial_equity: float,
    stop_fraction: float,
    target_fraction: float,
    output_root: Path,
) -> dict[str, object]:
    policy = _exit_policy(stop_fraction, target_fraction)
    policy_root = output_root / policy.policy_id
    policy_root.mkdir(parents=True, exist_ok=True)

    first_event = min(item.opportunity.decision_utc for item in cases)
    genesis_account, genesis_lineage = build_empty_recurrent_genesis_account_v1(
        initial_equity=initial_equity,
        as_of_utc=first_event,
    )
    coordinator = RecurrentLifecycleCoordinatorV1(account=genesis_account)

    resolved = {
        index: resolve_daily_exit(
            case,
            stop_fraction=stop_fraction,
            target_fraction=target_fraction,
        )
        for index, case in enumerate(cases)
    }
    mark_sessions = sorted(
        {bar.session_date for case in cases for bar in case.bars}
    )
    events: list[tuple[datetime, int, float, str, int, str]] = []
    for index, case in enumerate(cases):
        item = case.opportunity
        tie = -item.selector_score
        events.append(
            (item.decision_utc, 3, tie, item.opportunity_id, index, "RESERVE")
        )
        entry_time = _event_time(case.bars[0].session_date, which="OPEN")
        events.append(
            (entry_time, 4, tie, item.opportunity_id, index, "ENTRY")
        )
        exit_time = _event_time(
            resolved[index].exit_session_date,
            which="CLOSE",
        )
        events.append(
            (exit_time, 0, tie, item.opportunity_id, index, "CLOSE")
        )
    for session in mark_sessions:
        events.append(
            (_event_time(session, which="CLOSE"), 1, 0.0, "", -1, "MARK")
        )
    events.sort()

    slots: dict[int, _Slot] = {}
    decision_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []
    rejections: Counter[str] = Counter()
    exits: Counter[str] = Counter()
    collision_count = 0
    gap_stop_count = 0
    gap_target_count = 0
    peak_slots = 0
    peak_marked_equity = initial_equity
    max_marked_drawdown = 0.0
    peak_book_equity = initial_equity
    max_book_drawdown = 0.0

    for event_number, (
        event_utc,
        _priority,
        _tie,
        _identity,
        index,
        kind,
    ) in enumerate(events, start=1):
        if event_number == 1 or event_number % 1000 == 0 or event_number == len(events):
            print(
                f"    {policy.policy_id}: {event_number:,}/{len(events):,} events "
                f"({event_number / len(events):.1%}) closed={len(trade_rows):,} "
                f"active/reserved={len(slots)}",
                flush=True,
            )

        if kind == "MARK":
            account = coordinator.current_account()
            marks = []
            session = event_utc.astimezone(UTC)
            for slot_index, slot in sorted(slots.items()):
                if slot.state != "OPEN" or slot.position_fingerprint is None:
                    continue
                position = next(
                    (
                        pos
                        for pos in account.state.open_positions
                        if pos.position_fingerprint == slot.position_fingerprint
                    ),
                    None,
                )
                if position is None:
                    raise RecurrentSuccessorDailyExitSweepError(
                        "open slot position missing during mark"
                    )
                mark_price = _bar_close_for_session(
                    slot.case,
                    event_utc.astimezone(
                        __import__(
                            "packages.core.market_calendar",
                            fromlist=["get_market_calendar"],
                        ).get_market_calendar().market_tz
                    ).date(),
                )
                if mark_price is None:
                    raise RecurrentSuccessorDailyExitSweepError(
                        "open position lacks selected daily close mark"
                    )
                mark_source = {
                    "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
                    "opportunity_id": slot.case.opportunity.opportunity_id,
                    "session": event_utc.date(),
                    "close": mark_price,
                }
                marks.append(
                    build_simulated_market_mark_evidence(
                        position=position,
                        inputs=MarketMarkInputs(
                            source_id=(
                                "ATLAS_ALPACA_SIP_V2_DAILY_REPLAY_CLOSE:"
                                + slot.case.opportunity.opportunity_id
                            ),
                            source_fingerprint=_stable_hash(mark_source),
                            provider="ALPACA",
                            feed="SIP_V2_DAILY",
                            transport=MarketMarkTransport.REPLAY,
                            feed_quality="HASH_BOUND_HISTORICAL_DAILY_CLOSE",
                            market_timestamp_utc=event_utc,
                            received_utc=event_utc,
                            valuation_utc=event_utc,
                            bid_price_per_unit=mark_price,
                            ask_price_per_unit=mark_price,
                            last_price_per_unit=mark_price,
                        ),
                    )
                )
            if marks:
                publication = coordinator.publish_marks(
                    marks=tuple(marks),
                    valuation_utc=event_utc,
                )
                marked_equity = publication.marked_state.marked_equity
            else:
                marked_equity = account.state.account_book_equity
            peak_marked_equity = max(peak_marked_equity, marked_equity)
            marked_dd = marked_equity / peak_marked_equity - 1.0
            max_marked_drawdown = min(max_marked_drawdown, marked_dd)
            book_equity = coordinator.current_account().state.account_book_equity
            peak_book_equity = max(peak_book_equity, book_equity)
            book_dd = book_equity / peak_book_equity - 1.0
            max_book_drawdown = min(max_book_drawdown, book_dd)
            equity_rows.append(
                {
                    "timestamp_utc": event_utc,
                    "marked_equity": marked_equity,
                    "book_equity": book_equity,
                    "marked_drawdown": marked_dd,
                    "book_drawdown": book_dd,
                    "open_positions": sum(
                        slot.state == "OPEN" for slot in slots.values()
                    ),
                    "reserved_positions": sum(
                        slot.state == "RESERVED" for slot in slots.values()
                    ),
                }
            )
            continue

        case = cases[index]
        item = case.opportunity
        exit_result = resolved[index]

        if kind == "RESERVE":
            active = tuple(slots.values())
            if len(active) >= MAX_OPEN_POSITIONS:
                rejections["MAX_OPEN_POSITIONS"] += 1
                continue
            if any(
                slot.case.opportunity.ticker == item.ticker
                for slot in active
            ):
                rejections["TICKER_ALREADY_ACTIVE_OR_RESERVED"] += 1
                continue
            family_load = sum(
                slot.case.opportunity.economic_family_id
                == item.economic_family_id
                for slot in active
            )
            if family_load >= MAX_POSITIONS_PER_FAMILY:
                rejections["MAX_POSITIONS_PER_FAMILY"] += 1
                continue
            account = coordinator.current_account()
            decision = _build_decision(
                case,
                account_book_equity=account.state.account_book_equity,
            )
            transition, _ = coordinator.apply_reservation(record=decision)
            if (
                transition.event is None
                or transition.event.kind
                != RecurrentLifecycleEventKind.RESERVE_STOCK
            ):
                reason = (
                    transition.event.kind.value
                    if transition.event is not None
                    else "RECURRENT_RESERVATION_NOT_CREATED"
                )
                rejections[reason] += 1
                continue
            slots[index] = _Slot(
                case=case,
                decision=decision,
                resolved_exit=exit_result,
            )
            peak_slots = max(peak_slots, len(slots))
            decision_rows.append(
                {
                    "opportunity_id": item.opportunity_id,
                    "status": "RESERVED",
                    "decision_record_fingerprint": decision.record_fingerprint,
                    "stop_fraction": stop_fraction,
                    "target_fraction": target_fraction,
                }
            )
            continue

        slot = slots.get(index)
        if slot is None:
            continue

        if kind == "ENTRY":
            account = coordinator.current_account()
            notional = float(
                slot.decision.stock_economics.position_notional_dollars
            )
            half_cost_bps = float(DAILY_PRIMARY_COST_BPS) / 2.0
            entry_fee = notional * half_cost_bps / 10_000.0
            entry_price = case.bars[0].open
            fill_source = {
                "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
                "opportunity_id": item.opportunity_id,
                "entry_session": case.bars[0].session_date,
                "entry_price": entry_price,
            }
            fill = build_recurrent_entry_fill_evidence(
                account=account,
                record=slot.decision,
                inputs=SimulatedEntryFillInputs(
                    fill_source_id=(
                        "ATLAS_ALPACA_SIP_V2_DAILY_OPEN:"
                        + item.opportunity_id
                    ),
                    fill_source_fingerprint=_stable_hash(fill_source),
                    filled_utc=event_utc,
                    fill_price_per_unit=entry_price,
                    explicit_entry_fees_dollars=entry_fee,
                ),
            )
            funding = build_recurrent_funding_terms(
                account=account,
                fill=fill,
            )
            transition, _ = coordinator.apply_entry(
                fill=fill,
                funding=funding,
            )
            if transition.position is None:
                raise RecurrentSuccessorDailyExitSweepError(
                    "recurrent entry did not create position"
                )
            slot.position_fingerprint = transition.position.position_fingerprint
            slot.state = "OPEN"
            current_state = coordinator.current_account().state
            plan = build_recurrent_decision_stock_exit_plan_v1(
                source_recurrent_state_fingerprint=current_state.state_fingerprint,
                position=transition.position,
                decision_record=slot.decision,
                exit_policy=policy,
                plan_created_utc=event_utc,
            )
            clock = build_forecast_horizon_clock_v1(
                plan=plan,
                policy=ForecastHorizonClockPolicyV1(
                    session_counting_policy=(
                        SessionHorizonCountingPolicy.ENTRY_SESSION_INCLUDED
                    )
                ),
            )
            if clock.deadline_session_date != case.bars[-1].session_date:
                raise RecurrentSuccessorDailyExitSweepError(
                    "forecast horizon clock does not match five-session daily path"
                )
            slot.exit_plan = plan
            continue

        if kind != "CLOSE" or slot.state != "OPEN":
            continue
        if slot.position_fingerprint is None or slot.exit_plan is None:
            raise RecurrentSuccessorDailyExitSweepError(
                "close requires open position and bound exit plan"
            )
        if exit_result.disposition == "STOP":
            if exit_result.exit_price_per_unit > slot.exit_plan.stop_price_per_unit + 1e-9:
                raise RecurrentSuccessorDailyExitSweepError(
                    "STOP exit price cannot improve above bound stop under frozen policy"
                )
        elif exit_result.disposition == "TARGET":
            if not math.isclose(
                exit_result.exit_price_per_unit,
                slot.exit_plan.target_price_per_unit,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise RecurrentSuccessorDailyExitSweepError(
                    "TARGET exit must use bound target price"
                )
        elif exit_result.disposition != "TIME":
            raise RecurrentSuccessorDailyExitSweepError(
                "unsupported resolved exit disposition"
            )

        account = coordinator.current_account()
        position = next(
            (
                pos
                for pos in account.state.open_positions
                if pos.position_fingerprint == slot.position_fingerprint
            ),
            None,
        )
        if position is None:
            raise RecurrentSuccessorDailyExitSweepError(
                "close cannot find exact recurrent open position"
            )
        gross_exit = (
            position.quantity
            * exit_result.exit_price_per_unit
            * position.contract_multiplier
        )
        exit_fee = (
            gross_exit
            * (float(DAILY_PRIMARY_COST_BPS) / 2.0)
            / 10_000.0
        )
        exit_source = {
            "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
            "policy_fingerprint": policy.policy_fingerprint,
            "exit_plan_fingerprint": slot.exit_plan.plan_fingerprint,
            "opportunity_id": item.opportunity_id,
            "disposition": exit_result.disposition,
            "session": exit_result.exit_session_date,
            "price": exit_result.exit_price_per_unit,
            "collision": exit_result.same_session_collision,
            "gap_stop": exit_result.gap_through_stop,
            "gap_target": exit_result.gap_through_target,
        }
        exit_fill = build_recurrent_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=slot.position_fingerprint,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id=(
                    "ATLAS_DAILY_EXIT_SWEEP:"
                    + policy.policy_id
                    + ":"
                    + item.opportunity_id
                ),
                fill_source_fingerprint=_stable_hash(exit_source),
                exited_utc=event_utc,
                exit_price_per_unit=exit_result.exit_price_per_unit,
                explicit_exit_fees_dollars=exit_fee,
            ),
        )
        transition, _ = coordinator.apply_close(fill=exit_fill)
        trade = transition.closed_trade
        exits[exit_result.disposition] += 1
        collision_count += int(exit_result.same_session_collision)
        gap_stop_count += int(exit_result.gap_through_stop)
        gap_target_count += int(exit_result.gap_through_target)
        trade_rows.append(
            {
                "opportunity_id": item.opportunity_id,
                "policy_id": item.policy_id,
                "economic_family_id": item.economic_family_id,
                "ticker": item.ticker,
                "signal_session": item.signal_session,
                "stop_fraction": stop_fraction,
                "target_fraction": target_fraction,
                "exit_disposition": exit_result.disposition,
                "exit_session_offset": exit_result.exit_session_offset,
                "entry_price": case.bars[0].open,
                "exit_price": exit_result.exit_price_per_unit,
                "same_session_collision": exit_result.same_session_collision,
                "gap_through_stop": exit_result.gap_through_stop,
                "gap_through_target": exit_result.gap_through_target,
                "lifetime_trade_net_pnl_dollars": (
                    trade.lifetime_trade_net_pnl_dollars
                ),
            }
        )
        del slots[index]

    if slots:
        raise RecurrentSuccessorDailyExitSweepError(
            "policy replay ended with unresolved positions/reservations"
        )
    final_account = coordinator.current_account()
    if final_account.state.open_positions or final_account.state.stock_reservations:
        raise RecurrentSuccessorDailyExitSweepError(
            "final recurrent account is not flat"
        )
    final_equity = final_account.state.account_book_equity
    summary = {
        "policy_id": policy.policy_id,
        "policy_fingerprint": policy.policy_fingerprint,
        "stop_fraction": stop_fraction,
        "target_fraction": target_fraction,
        "initial_equity": initial_equity,
        "final_book_equity": final_equity,
        "total_return": final_equity / initial_equity - 1.0,
        "maximum_marked_equity_drawdown": max_marked_drawdown,
        "maximum_book_equity_drawdown": max_book_drawdown,
        "selected_cases": len(cases),
        "admitted_positions": len(trade_rows),
        "completed_positions": len(trade_rows),
        "peak_active_or_reserved_slots": peak_slots,
        "rejections": dict(sorted(rejections.items())),
        "exit_dispositions": dict(sorted(exits.items())),
        "same_session_collision_count": collision_count,
        "gap_through_stop_count": gap_stop_count,
        "gap_through_target_count": gap_target_count,
        "final_recurrent_state_fingerprint": final_account.state.state_fingerprint,
        "final_recurrent_ledger_fingerprint": final_account.ledger.ledger_fingerprint,
        "genesis_lineage": genesis_lineage,
    }
    summary["summary_fingerprint"] = _stable_hash(summary)
    _write_json(policy_root / "summary.json", summary)
    _write_jsonl(policy_root / "trades.jsonl", trade_rows)
    _write_jsonl(policy_root / "equity_curve.jsonl", equity_rows)
    _write_jsonl(policy_root / "decisions.jsonl", decision_rows)
    return summary


def run_recurrent_successor_daily_exit_sweep(
    project_root: Path,
    *,
    initial_equity: float,
    start_session: date,
    end_session: date,
    policy_ids: Sequence[str] = (),
    output_root: Path | None = None,
    duckdb_threads: int | None = None,
) -> dict[str, object]:
    if not math.isfinite(initial_equity) or initial_equity <= 0.0:
        raise RecurrentSuccessorDailyExitSweepError(
            "initial equity must be finite and positive"
        )
    development_start = date.fromisoformat(str(DEVELOPMENT_START))
    development_end = date.fromisoformat(str(DEVELOPMENT_END))
    if not development_start <= start_session <= end_session <= development_end:
        raise RecurrentSuccessorDailyExitSweepError(
            "exit sweep scope must stay inside DEVELOPMENT"
        )

    cases, source = load_daily_exit_cases(
        project_root,
        start_session=start_session,
        end_session=end_session,
        policy_ids=policy_ids,
        duckdb_threads=duckdb_threads,
    )
    run_identity = {
        "contract_fingerprint": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
        "source": source,
        "initial_equity": initial_equity,
        "start_session": start_session,
        "end_session": end_session,
        "policy_ids": sorted(set(str(value) for value in policy_ids)),
    }
    run_fingerprint = _stable_hash(run_identity)
    root = (
        Path(output_root).resolve()
        if output_root is not None
        else (
            Path(project_root).resolve()
            / "data"
            / "research"
            / "recurrent_successor_daily_exit_sweep"
            / RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT[:16]
            / run_fingerprint[:16]
        )
    )
    root.mkdir(parents=True, exist_ok=True)
    _write_json(
        root / "contract.json",
        {
            "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
            "contract_fingerprint": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
            "authority": AUTHORITY,
        },
    )

    print(
        "daily exit sweep: running "
        f"{len(STOP_TARGET_POLICY_PAIRS)} frozen stop/target policies across "
        f"{len(cases):,} daily LONG cases",
        flush=True,
    )
    results: list[dict[str, object]] = []
    for policy_number, (stop_fraction, target_fraction) in enumerate(
        STOP_TARGET_POLICY_PAIRS,
        start=1,
    ):
        print(
            f"  policy {policy_number}/{len(STOP_TARGET_POLICY_PAIRS)}: "
            f"stop={stop_fraction:.0%} target={target_fraction:.0%}",
            flush=True,
        )
        result = _simulate_policy(
            cases,
            initial_equity=initial_equity,
            stop_fraction=stop_fraction,
            target_fraction=target_fraction,
            output_root=root,
        )
        results.append(result)
        print(
            "    complete: "
            f"return={float(result['total_return']):.2%}; "
            f"marked DD={float(result['maximum_marked_equity_drawdown']):.2%}; "
            f"trades={int(result['completed_positions']):,}",
            flush=True,
        )

    results = sorted(
        results,
        key=lambda item: (
            float(item["stop_fraction"]),
            float(item["target_fraction"]),
        ),
    )
    report: dict[str, object] = {
        "status": "COMPLETE_DAILY_EXIT_POLICY_SWEEP_DIAGNOSTIC",
        "contract": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT,
        "contract_fingerprint": RECURRENT_SUCCESSOR_DAILY_EXIT_SWEEP_CONTRACT_FINGERPRINT,
        "run_fingerprint": run_fingerprint,
        "scope": {
            "start_session": start_session,
            "end_session": end_session,
            "policy_ids": sorted(set(str(value) for value in policy_ids)),
        },
        "source": source,
        "initial_equity": initial_equity,
        "usable_daily_long_cases": len(cases),
        "policy_results": results,
        "interpretation": {
            "development_tuning_diagnostic_only": True,
            "automatic_winner_selected": False,
            "current_window_can_generate_hypotheses_but_not_validate_them": True,
            "future_cross_regime_and_prospective_confirmation_required": True,
            "short_side_not_simulated": True,
        },
        "authority": AUTHORITY,
    }
    report["report_fingerprint"] = _stable_hash(report)
    _write_json(root / "sweep_summary.json", report)
    return report
