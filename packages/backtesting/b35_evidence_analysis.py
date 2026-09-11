from __future__ import annotations

import bisect
import hashlib
import json
import math
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable

import duckdb
import exchange_calendars as xcals
import numpy as np
import pandas as pd

from packages.backtesting.b35_development_replay import _receipt_id, _sha256_file
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.strategies.b35_conditional_evidence_contract import (
    ALL_IN_ROUND_TRIP_COST_GRID_BPS,
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
    DEVELOPMENT_LAST_SCORING_SESSION,
    MIN_CELL_OPPORTUNITIES,
    MIN_CELL_UNIQUE_INSTRUMENTS,
    MIN_CELL_UNIQUE_SESSIONS,
    SELECTOR_FALLBACK_HIERARCHY,
    SELECTOR_LCB_QUANTILE,
    SELECTOR_SCORING_COST_BPS,
    SESSION_CLUSTER_BOOTSTRAP_DRAWS,
    WALK_FORWARD_EMBARGO_SESSIONS,
    WALK_FORWARD_STEP_SESSIONS,
    WALK_FORWARD_TEST_SESSIONS,
    ROLLING_TRAIN_SESSIONS,
    CONDITION_DIMENSIONS,
    PRIMARY_CONDITION_INTERACTIONS,
)


B35_EVIDENCE_ANALYSIS_CONTRACT = "atlas-b35-development-evidence-selector-analysis-v1"


class B35EvidenceAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_id: int
    train_start: date
    train_end: date
    embargo_session: date
    test_start: date
    test_end: date


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def _write_json(path: Path, payload: object) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n",
        fsync=True,
    )


def _artifact_receipt_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".receipt.json")


def _reusable_artifact(
    path: Path,
    *,
    phase: str,
    analysis_fingerprint: str,
) -> bool:
    receipt_path = _artifact_receipt_path(path)
    if not path.exists() and not receipt_path.exists():
        return False
    if not path.is_file() or not receipt_path.is_file():
        path.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        path.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        return False
    required = {
        "contract": B35_EVIDENCE_ANALYSIS_CONTRACT,
        "phase": phase,
        "analysis_fingerprint": analysis_fingerprint,
        "artifact_path": str(path.resolve()),
    }
    actual_receipt_id = str(receipt.get("receipt_id") or "")
    expected_receipt_id = _stable_hash(
        {key: value for key, value in receipt.items() if key != "receipt_id"}
    )
    if actual_receipt_id != expected_receipt_id:
        path.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        return False
    if any(receipt.get(key) != value for key, value in required.items()):
        path.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        return False
    if receipt.get("artifact_sha256") != _sha256_file(path):
        path.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        return False
    return True


def _publish_artifact_receipt(
    path: Path,
    *,
    phase: str,
    analysis_fingerprint: str,
    row_count: int | None = None,
) -> None:
    payload: dict[str, object] = {
        "contract": B35_EVIDENCE_ANALYSIS_CONTRACT,
        "phase": phase,
        "analysis_fingerprint": analysis_fingerprint,
        "artifact_path": str(path.resolve()),
        "artifact_sha256": _sha256_file(path),
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    if row_count is not None:
        payload["row_count"] = int(row_count)
    payload["receipt_id"] = _stable_hash(payload)
    _write_json(_artifact_receipt_path(path), payload)


def _copy_query_atomic(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    target: Path,
    *,
    copy_options: str = "FORMAT PARQUET, COMPRESSION ZSTD",
) -> None:
    temp = unique_temp_path(target)
    try:
        conn.execute(f"COPY ({query}) TO '{_sql_path(temp)}' ({copy_options})")
        replace_with_retry(temp, target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _clean_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []
    for record in records:
        item: dict[str, object] = {}
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                item[key] = None
            elif isinstance(value, pd.Timestamp):
                item[key] = value.isoformat()
            elif isinstance(value, np.generic):
                item[key] = value.item()
            else:
                item[key] = value
        cleaned.append(item)
    return cleaned


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _progress(
    progress_path: Path,
    *,
    started: float,
    phase: str,
    detail: str,
    completed: int | None = None,
    total: int | None = None,
    state: str = "RUNNING",
) -> None:
    elapsed = max(0.0, time.monotonic() - started)
    payload = {
        "contract": B35_EVIDENCE_ANALYSIS_CONTRACT,
        "state": state,
        "phase": phase,
        "detail": detail,
        "completed": completed,
        "total": total,
        "elapsed_seconds": round(elapsed, 3),
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "authority": "NON_AUTHORITATIVE_OPERATIONAL",
    }
    _write_json(progress_path, payload)
    amount = ""
    if completed is not None and total is not None:
        amount = f" {completed}/{total}"
    print(
        f"[{payload['updated_at_utc']}] B35 ANALYSIS {phase}{amount} | "
        f"{detail} | elapsed={elapsed / 60.0:.1f}m | state={state}",
        flush=True,
    )


def _validate_summary(summary_path: Path) -> dict[str, object]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    required = {
        "status": "COMPLETE",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "start_session": "2016-01-04",
        "end_session": DEVELOPMENT_LAST_SCORING_SESSION.isoformat(),
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
        "compact_group_outputs_only": True,
        "permanent_minute_feature_lake_created": False,
    }
    for field, expected in required.items():
        if summary.get(field) != expected:
            raise B35EvidenceAnalysisError(
                f"B35 replay summary {field} does not match the frozen completed trial"
            )
    group_count = summary.get("group_count")
    receipt_ids = summary.get("group_receipt_ids")
    if not isinstance(group_count, int) or group_count <= 0:
        raise B35EvidenceAnalysisError("B35 replay summary group count is invalid")
    if not isinstance(receipt_ids, list) or len(receipt_ids) != group_count:
        raise B35EvidenceAnalysisError("B35 replay summary receipt ids do not reconcile")
    if len(set(map(str, receipt_ids))) != group_count:
        raise B35EvidenceAnalysisError("B35 replay summary receipt ids are not unique")
    run_fingerprint = str(summary.get("run_fingerprint") or "")
    if len(run_fingerprint) != 64:
        raise B35EvidenceAnalysisError("B35 replay summary run fingerprint is invalid")
    return summary


def validate_replay_artifacts(output_root: Path) -> tuple[dict[str, object], tuple[Path, ...]]:
    output_root = output_root.resolve()
    summary_path = output_root / "summary.json"
    if not summary_path.is_file():
        raise B35EvidenceAnalysisError("completed B35 summary.json is missing")
    summary = _validate_summary(summary_path)
    groups_root = output_root / "groups"
    receipt_paths = tuple(sorted(groups_root.glob("*.receipt.json")))
    output_paths = tuple(sorted(groups_root.glob("*.jsonl")))
    expected_count = int(summary["group_count"])
    if len(receipt_paths) != expected_count or len(output_paths) != expected_count:
        raise B35EvidenceAnalysisError(
            "B35 analysis requires exactly one receipt and one JSONL output per completed group"
        )

    expected_ids = set(map(str, summary["group_receipt_ids"]))
    actual_ids: set[str] = set()
    validated_outputs: list[Path] = []
    for receipt_path in receipt_paths:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_id = str(receipt.get("receipt_id") or "")
        if receipt_id != _receipt_id(receipt) or receipt_id not in expected_ids:
            raise B35EvidenceAnalysisError("B35 group receipt identity drifted before analysis")
        for field in (
            "b35_preoutcome_fingerprint",
            "source_fingerprint",
            "split_evidence_fingerprint",
            "authorization_id",
        ):
            if receipt.get(field) != summary.get(field):
                raise B35EvidenceAnalysisError(f"B35 group receipt {field} drifted before analysis")
        for field in (
            "consumed_master_rows_read",
            "future_blind_rows_read",
            "provider_calls",
            "broker_reads",
            "broker_writes",
        ):
            if receipt.get(field) != 0:
                raise B35EvidenceAnalysisError(f"B35 group receipt {field} is nonzero")
        for field in ("paper_authority", "live_authority", "strategy_promotion", "selector_promotion"):
            if receipt.get(field) is not False:
                raise B35EvidenceAnalysisError(f"B35 group receipt {field} changed authority")
        output_path = Path(str(receipt.get("output_path") or "")).resolve()
        if output_path.parent != groups_root:
            raise B35EvidenceAnalysisError("B35 group output escaped the completed groups directory")
        if not output_path.is_file():
            raise B35EvidenceAnalysisError("B35 group output is missing")
        if receipt.get("output_sha256") != _sha256_file(output_path):
            raise B35EvidenceAnalysisError("B35 group output SHA-256 drifted before analysis")
        actual_ids.add(receipt_id)
        validated_outputs.append(output_path)

    if actual_ids != expected_ids:
        raise B35EvidenceAnalysisError("B35 validated receipt set differs from the final summary")
    if set(validated_outputs) != set(output_paths):
        raise B35EvidenceAnalysisError("B35 groups directory contains unreceipted/orphan JSONL")
    return summary, tuple(sorted(validated_outputs))


def build_walk_forward_folds(start_session: date, end_session: date) -> tuple[WalkForwardFold, ...]:
    calendar = xcals.get_calendar("XNYS")
    sessions = [
        stamp.date()
        for stamp in calendar.sessions_in_range(
            pd.Timestamp(start_session), pd.Timestamp(end_session)
        )
    ]
    folds: list[WalkForwardFold] = []
    test_start_index = ROLLING_TRAIN_SESSIONS + WALK_FORWARD_EMBARGO_SESSIONS
    fold_id = 1
    while test_start_index + WALK_FORWARD_TEST_SESSIONS <= len(sessions):
        train_end_index = test_start_index - WALK_FORWARD_EMBARGO_SESSIONS - 1
        train_start_index = train_end_index - ROLLING_TRAIN_SESSIONS + 1
        embargo_index = train_end_index + 1
        test_end_index = test_start_index + WALK_FORWARD_TEST_SESSIONS - 1
        folds.append(
            WalkForwardFold(
                fold_id=fold_id,
                train_start=sessions[train_start_index],
                train_end=sessions[train_end_index],
                embargo_session=sessions[embargo_index],
                test_start=sessions[test_start_index],
                test_end=sessions[test_end_index],
            )
        )
        fold_id += 1
        test_start_index += WALK_FORWARD_STEP_SESSIONS
    if not folds:
        raise B35EvidenceAnalysisError("B35 DEVELOPMENT span cannot form a frozen walk-forward fold")
    return tuple(folds)


def _selector_columns(level: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        "setup_intensity_bucket" if item == "setup_intensity" else item for item in level
    )


def _cell_key(values: Iterable[object]) -> str:
    return "|".join(str(value) for value in values)


def _empirical_lower_quantile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        raise ValueError("quantile requires at least one value")
    ordered = np.sort(values.astype(float, copy=False))
    rank = max(1, math.ceil(q * ordered.size))
    return float(ordered[rank - 1])


def _bootstrap_lcb(
    session_sums: np.ndarray,
    session_counts: np.ndarray,
    *,
    seed_material: str,
) -> float | None:
    if session_sums.size == 0 or session_counts.size == 0:
        return None
    if session_sums.size != session_counts.size:
        raise ValueError("bootstrap session sums/counts mismatch")
    if np.any(session_counts <= 0):
        raise ValueError("bootstrap comparable session counts must be positive")
    seed = int.from_bytes(hashlib.sha256(seed_material.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    n = session_sums.size
    indices = rng.integers(0, n, size=(SESSION_CLUSTER_BOOTSTRAP_DRAWS, n))
    sampled_sums = session_sums[indices].sum(axis=1)
    sampled_counts = session_counts[indices].sum(axis=1)
    means = sampled_sums / sampled_counts
    return _empirical_lower_quantile(means, SELECTOR_LCB_QUANTILE)


def _normalization_query(group_glob: Path) -> str:
    source = _sql_path(group_glob)
    cost_exprs: list[str] = []
    net_r_exprs: list[str] = []
    for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS:
        cost_exprs.append(
            f'CAST(outcome.net_directional_returns_by_cost_bps."{cost}" AS DOUBLE) '
            f"AS net_return_{cost}"
        )
        net_r_exprs.append(
            "CASE WHEN outcome.comparable "
            "AND CAST(outcome.entry_price AS DOUBLE) > 0 "
            "AND CAST(outcome.stop_price AS DOUBLE) IS NOT NULL "
            "AND abs(CAST(outcome.entry_price AS DOUBLE) - CAST(outcome.stop_price AS DOUBLE)) > 0 "
            f'THEN CAST(outcome.net_directional_returns_by_cost_bps."{cost}" AS DOUBLE) '
            "/ (abs(CAST(outcome.entry_price AS DOUBLE) - CAST(outcome.stop_price AS DOUBLE)) "
            "/ CAST(outcome.entry_price AS DOUBLE)) ELSE NULL END "
            f"AS net_r_{cost}"
        )
    selector_key_exprs: list[str] = []
    for index, hierarchy in enumerate(SELECTOR_FALLBACK_HIERARCHY, start=1):
        cols = _selector_columns(hierarchy)
        joined = ", ".join(cols)
        selector_key_exprs.append(
            f"concat_ws('|', {joined}) AS selector_key_{index}"
        )
    return f"""
        SELECT
            CAST(context.strategy_id AS VARCHAR) AS strategy_id,
            CAST(context.symbol AS VARCHAR) AS symbol,
            CAST(context.session_date AS DATE) AS session_date,
            CAST(outcome.direction AS VARCHAR) AS direction,
            CAST(context.prior_market_regime AS VARCHAR) AS prior_market_regime,
            CAST(context.prior_close_price AS VARCHAR) AS prior_close_price,
            CAST(context.median_dollar_volume_20 AS VARCHAR) AS median_dollar_volume_20,
            CAST(context.realized_volatility_20 AS VARCHAR) AS realized_volatility_20,
            CAST(context.prior_trend_20_50 AS VARCHAR) AS prior_trend_20_50,
            CAST(context.absolute_gap_pct AS VARCHAR) AS absolute_gap_pct,
            CAST(context.premarket_relvol_20 AS VARCHAR) AS premarket_relvol_20,
            CAST(context.premarket_dollar_volume AS VARCHAR) AS premarket_dollar_volume,
            CAST(context.opening_range_width_pct AS VARCHAR) AS opening_range_width_pct,
            CAST(context.signal_time_et AS VARCHAR) AS signal_time_et,
            CAST(context.hvd_volume_ratio AS VARCHAR) AS hvd_volume_ratio,
            CAST(context.setup_intensity_bucket AS VARCHAR) AS setup_intensity_bucket,
            CAST(outcome.comparable AS BOOLEAN) AS comparable,
            CAST(outcome.status AS VARCHAR) AS status,
            CAST(outcome.entry_bar_timestamp_utc AS TIMESTAMPTZ) AS entry_time_utc,
            CAST(outcome.exit_bar_timestamp_utc AS TIMESTAMPTZ) AS exit_time_utc,
            CAST(outcome.entry_price AS DOUBLE) AS entry_price,
            CAST(outcome.stop_price AS DOUBLE) AS stop_price,
            CAST(outcome.target_price AS DOUBLE) AS target_price,
            CAST(outcome.exit_price AS DOUBLE) AS exit_price,
            CAST(outcome.exit_reason AS VARCHAR) AS exit_reason,
            CAST(outcome.risk_multiple AS DOUBLE) AS gross_r_multiple,
            CAST(outcome.maximum_favorable_excursion AS DOUBLE) AS mfe,
            CAST(outcome.maximum_adverse_excursion AS DOUBLE) AS mae,
            CASE WHEN outcome.comparable
                 THEN date_diff('minute',
                     CAST(outcome.entry_bar_timestamp_utc AS TIMESTAMPTZ),
                     CAST(outcome.exit_bar_timestamp_utc AS TIMESTAMPTZ))
                 ELSE NULL END AS holding_minutes,
            {", ".join(cost_exprs)},
            {", ".join(net_r_exprs)},
            {", ".join(selector_key_exprs)}
        FROM read_json_auto(
            '{source}',
            format='newline_delimited',
            union_by_name=true,
            maximum_object_size=67108864
        )
    """


def _metrics_sql(group_cols: tuple[str, ...]) -> str:
    prefix = ""
    group = ""
    if group_cols:
        prefix = ", ".join(group_cols) + ", "
        group = " GROUP BY " + ", ".join(str(index + 1) for index in range(len(group_cols)))
    means = []
    medians = []
    for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS:
        means.append(
            f"avg(net_return_{cost}) FILTER (WHERE comparable) AS mean_net_return_{cost}"
        )
        medians.append(
            f"median(net_return_{cost}) FILTER (WHERE comparable) AS median_net_return_{cost}"
        )
    return f"""
        SELECT
            {prefix}
            count(*) AS opportunities,
            count(*) FILTER (WHERE comparable) AS comparable,
            count(*) FILTER (WHERE NOT comparable) AS noncomparable,
            count(DISTINCT session_date) AS unique_sessions,
            count(DISTINCT symbol) AS unique_instruments,
            avg(CASE WHEN comparable THEN CASE WHEN net_return_50 > 0 THEN 1.0 ELSE 0.0 END END)
                AS win_rate_50bps,
            {", ".join(means)},
            {", ".join(medians)},
            avg(net_r_50) FILTER (WHERE comparable) AS mean_net_r_50,
            median(net_r_50) FILTER (WHERE comparable) AS median_net_r_50,
            sum(CASE WHEN comparable AND net_r_50 > 0 THEN net_r_50 ELSE 0 END)
                / nullif(abs(sum(CASE WHEN comparable AND net_r_50 < 0 THEN net_r_50 ELSE 0 END)), 0)
                AS profit_factor_net_r_50,
            avg(mfe) FILTER (WHERE comparable) AS mean_mfe,
            avg(mae) FILTER (WHERE comparable) AS mean_mae,
            avg(holding_minutes) FILTER (WHERE comparable) AS mean_holding_minutes,
            median(holding_minutes) FILTER (WHERE comparable) AS median_holding_minutes,
            avg(net_return_0 - net_return_50) FILTER (WHERE comparable) AS mean_cost_drag_50bps,
            avg(net_return_0 - net_return_100) FILTER (WHERE comparable) AS mean_cost_drag_100bps,
            avg(CASE WHEN status='NONCOMPARABLE_UNRESOLVED_EXIT_AFTER_ENTRY' THEN 1.0 ELSE 0.0 END)
                AS unresolved_exit_rate,
            avg(CASE WHEN NOT comparable THEN 1.0 ELSE 0.0 END) AS noncomparable_rate
        FROM opportunities
        {group}
    """


def _materialize_condition_cells(conn: duckdb.DuckDBPyConnection, target: Path) -> None:
    queries: list[str] = []
    for dimension in CONDITION_DIMENSIONS:
        name = dimension.condition_id
        metrics = _metrics_sql(("strategy_id", name))
        queries.append(
            "SELECT strategy_id, "
            f"'{name}' AS condition_name, CAST({name} AS VARCHAR) AS condition_value, "
            "opportunities, comparable, noncomparable, unique_sessions, unique_instruments, "
            "win_rate_50bps, mean_net_return_0, mean_net_return_10, mean_net_return_25, "
            "mean_net_return_50, mean_net_return_100, median_net_return_0, median_net_return_10, "
            "median_net_return_25, median_net_return_50, median_net_return_100, "
            "mean_net_r_50, median_net_r_50, profit_factor_net_r_50, mean_mfe, mean_mae, "
            "mean_holding_minutes, median_holding_minutes, mean_cost_drag_50bps, "
            "mean_cost_drag_100bps, unresolved_exit_rate, noncomparable_rate "
            f"FROM ({metrics})"
        )
    for interaction in PRIMARY_CONDITION_INTERACTIONS:
        label = "__x__".join(interaction)
        expression = "concat_ws('|', " + ", ".join(interaction) + ")"
        group_cols = ("strategy_id",) + tuple(interaction)
        metrics = _metrics_sql(group_cols)
        queries.append(
            "SELECT strategy_id, "
            f"'{label}' AS condition_name, {expression} AS condition_value, "
            "opportunities, comparable, noncomparable, unique_sessions, unique_instruments, "
            "win_rate_50bps, mean_net_return_0, mean_net_return_10, mean_net_return_25, "
            "mean_net_return_50, mean_net_return_100, median_net_return_0, median_net_return_10, "
            "median_net_return_25, median_net_return_50, median_net_return_100, "
            "mean_net_r_50, median_net_r_50, profit_factor_net_r_50, mean_mfe, mean_mae, "
            "mean_holding_minutes, median_holding_minutes, mean_cost_drag_50bps, "
            "mean_cost_drag_100bps, unresolved_exit_rate, noncomparable_rate "
            f"FROM ({metrics})"
        )
    union = " UNION ALL ".join(queries)
    query = f"""
        SELECT *,
            opportunities >= {MIN_CELL_OPPORTUNITIES}
            AND unique_sessions >= {MIN_CELL_UNIQUE_SESSIONS}
            AND unique_instruments >= {MIN_CELL_UNIQUE_INSTRUMENTS}
            AS minimum_support
        FROM ({union})
        ORDER BY strategy_id, condition_name, condition_value
    """
    _copy_query_atomic(conn, query, target)


def _rows_to_cell_maps(
    session_rows: list[tuple],
    symbol_rows: list[tuple],
    key_count: int,
) -> tuple[dict[tuple[str, ...], list[tuple]], dict[tuple[str, ...], list[tuple[str, tuple[date, ...]]]]]:
    session_map: dict[tuple[str, ...], list[tuple]] = defaultdict(list)
    for row in session_rows:
        key = tuple(str(item) for item in row[:key_count])
        session_day = row[key_count]
        if isinstance(session_day, datetime):
            session_day = session_day.date()
        session_map[key].append(
            (
                session_day,
                int(row[key_count + 1]),
                int(row[key_count + 2]),
                float(row[key_count + 3] or 0.0),
            )
        )
    for values in session_map.values():
        values.sort(key=lambda item: item[0])

    symbol_map: dict[tuple[str, ...], list[tuple[str, tuple[date, ...]]]] = defaultdict(list)
    for row in symbol_rows:
        key = tuple(str(item) for item in row[:key_count])
        symbol = str(row[key_count])
        raw_sessions = row[key_count + 1] or []
        sessions = tuple(
            item.date() if isinstance(item, datetime) else item for item in raw_sessions
        )
        symbol_map[key].append((symbol, sessions))
    return dict(session_map), dict(symbol_map)


def _slice_session_rows(rows: list[tuple], start: date, end: date) -> list[tuple]:
    dates = [item[0] for item in rows]
    left = bisect.bisect_left(dates, start)
    right = bisect.bisect_right(dates, end)
    return rows[left:right]


def _symbol_present(sessions: tuple[date, ...], start: date, end: date) -> bool:
    index = bisect.bisect_left(sessions, start)
    return index < len(sessions) and sessions[index] <= end


def _build_selector_scores(
    conn: duckdb.DuckDBPyConnection,
    *,
    folds: tuple[WalkForwardFold, ...],
    run_fingerprint: str,
    progress_path: Path,
    started: float,
) -> pd.DataFrame:
    score_rows: list[dict[str, object]] = []
    for level_index, hierarchy in enumerate(SELECTOR_FALLBACK_HIERARCHY, start=1):
        columns = _selector_columns(hierarchy)
        col_sql = ", ".join(columns)
        session_rows = conn.execute(
            f"""
            SELECT {col_sql}, session_date,
                   count(*) AS opportunities,
                   count(*) FILTER (WHERE comparable) AS comparable,
                   coalesce(sum(net_r_{SELECTOR_SCORING_COST_BPS})
                            FILTER (WHERE comparable), 0.0) AS sum_net_r
            FROM opportunities
            GROUP BY {col_sql}, session_date
            ORDER BY {col_sql}, session_date
            """
        ).fetchall()
        symbol_rows = conn.execute(
            f"""
            SELECT {col_sql}, symbol,
                   list(session_date ORDER BY session_date) AS sessions
            FROM (
                SELECT DISTINCT {col_sql}, symbol, session_date
                FROM opportunities
            )
            GROUP BY {col_sql}, symbol
            ORDER BY {col_sql}, symbol
            """
        ).fetchall()
        session_map, symbol_map = _rows_to_cell_maps(
            session_rows, symbol_rows, len(columns)
        )
        for fold_position, fold in enumerate(folds, start=1):
            for key, rows in session_map.items():
                test_rows = _slice_session_rows(rows, fold.test_start, fold.test_end)
                if not test_rows:
                    continue
                train_rows = _slice_session_rows(rows, fold.train_start, fold.train_end)
                opportunities = sum(item[1] for item in train_rows)
                comparable = sum(item[2] for item in train_rows)
                unique_sessions = len(train_rows)
                unique_instruments = sum(
                    1
                    for _symbol, sessions in symbol_map.get(key, [])
                    if _symbol_present(sessions, fold.train_start, fold.train_end)
                )
                supported = (
                    opportunities >= MIN_CELL_OPPORTUNITIES
                    and unique_sessions >= MIN_CELL_UNIQUE_SESSIONS
                    and unique_instruments >= MIN_CELL_UNIQUE_INSTRUMENTS
                )
                score: float | None = None
                if supported and comparable > 0:
                    comparable_rows = [item for item in train_rows if item[2] > 0]
                    sums = np.asarray([item[3] for item in comparable_rows], dtype=float)
                    counts = np.asarray([item[2] for item in comparable_rows], dtype=np.int64)
                    seed_material = (
                        f"{B35_PREOUTCOME_FINGERPRINT}|{run_fingerprint}|"
                        f"fold={fold.fold_id}|level={level_index}|cell={_cell_key(key)}"
                    )
                    score = _bootstrap_lcb(sums, counts, seed_material=seed_material)
                score_rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "hierarchy_level": level_index,
                        "cell_key": _cell_key(key),
                        "training_opportunities": opportunities,
                        "training_comparable": comparable,
                        "training_unique_sessions": unique_sessions,
                        "training_unique_instruments": unique_instruments,
                        "minimum_support": supported,
                        "score_lcb_net_r_50": score,
                        "eligible_positive": bool(supported and score is not None and score > 0.0),
                    }
                )
            _progress(
                progress_path,
                started=started,
                phase=f"SELECTOR_L{level_index}",
                detail=f"completed walk-forward fold {fold.fold_id}",
                completed=fold_position,
                total=len(folds),
            )
        del session_rows, symbol_rows, session_map, symbol_map
    return pd.DataFrame.from_records(score_rows)


def _selector_assignments_sql(opportunities_path: Path) -> str:
    joins = []
    support_cases = []
    score_cases = []
    for level in range(1, len(SELECTOR_FALLBACK_HIERARCHY) + 1):
        joins.append(
            f"""
            LEFT JOIN selector_scores s{level}
              ON s{level}.fold_id = f.fold_id
             AND s{level}.hierarchy_level = {level}
             AND s{level}.cell_key = o.selector_key_{level}
            """
        )
        prior_support = " AND ".join(
            f"coalesce(s{prior}.minimum_support, false)=false"
            for prior in range(1, level)
        )
        condition = f"coalesce(s{level}.minimum_support, false)=true"
        if prior_support:
            condition = f"({prior_support}) AND ({condition})"
        support_cases.append(f"WHEN {condition} THEN {level}")
        score_cases.append(f"WHEN {condition} THEN s{level}.score_lcb_net_r_50")
    return f"""
        WITH assigned AS (
            SELECT
                f.fold_id,
                o.session_date,
                o.strategy_id,
                o.symbol,
                o.direction,
                o.comparable,
                o.status,
                o.entry_time_utc,
                o.exit_time_utc,
                o.net_return_0,
                o.net_return_10,
                o.net_return_25,
                o.net_return_50,
                o.net_return_100,
                o.net_r_50,
                CASE {' '.join(support_cases)} ELSE NULL END AS fallback_level,
                CASE {' '.join(score_cases)} ELSE NULL END AS selector_score
            FROM read_parquet('{_sql_path(opportunities_path)}') o
            JOIN folds f
              ON o.session_date BETWEEN f.test_start AND f.test_end
            {' '.join(joins)}
        ),
        classified AS (
            SELECT *,
                   selector_score IS NOT NULL AND selector_score > 0.0 AS selected
            FROM assigned
        )
        SELECT *,
               row_number() OVER (
                   PARTITION BY fold_id, session_date
                   ORDER BY selected DESC, selector_score DESC NULLS LAST,
                            strategy_id ASC, symbol ASC,
                            entry_time_utc ASC NULLS LAST
               ) AS stable_session_rank
        FROM classified
    """


def _selector_summary(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    overall_records = conn.execute(
        """
        SELECT
            count(*) AS test_opportunities,
            count(*) FILTER (WHERE selected) AS selected_opportunities,
            count(*) FILTER (WHERE selected AND comparable) AS selected_comparable,
            count(*) FILTER (WHERE comparable) AS standalone_comparable,
            count(DISTINCT session_date) AS test_sessions,
            count(DISTINCT symbol) AS test_instruments,
            avg(CASE WHEN selected THEN 1.0 ELSE 0.0 END) AS selection_rate,
            avg(CASE WHEN NOT selected THEN 1.0 ELSE 0.0 END) AS abstention_rate,
            avg(net_return_50) FILTER (WHERE comparable) AS standalone_mean_net_return_50,
            avg(net_r_50) FILTER (WHERE comparable) AS standalone_mean_net_r_50,
            avg(net_return_0) FILTER (WHERE selected AND comparable) AS mean_net_return_0,
            avg(net_return_10) FILTER (WHERE selected AND comparable) AS mean_net_return_10,
            avg(net_return_25) FILTER (WHERE selected AND comparable) AS mean_net_return_25,
            avg(net_return_50) FILTER (WHERE selected AND comparable) AS mean_net_return_50,
            avg(net_return_100) FILTER (WHERE selected AND comparable) AS mean_net_return_100,
            median(net_return_50) FILTER (WHERE selected AND comparable) AS median_net_return_50,
            avg(net_r_50) FILTER (WHERE selected AND comparable) AS mean_net_r_50,
            median(net_r_50) FILTER (WHERE selected AND comparable) AS median_net_r_50,
            avg(CASE WHEN selected AND comparable
                     THEN CASE WHEN net_return_50 > 0 THEN 1.0 ELSE 0.0 END END)
                AS win_rate_50bps
        FROM selector_assignments
        """
    ).fetchdf().to_dict(orient="records")
    overall = _clean_records(overall_records)[0]
    by_strategy = conn.execute(
        """
        SELECT strategy_id,
               count(*) AS test_opportunities,
               count(*) FILTER (WHERE selected) AS selected_opportunities,
               count(*) FILTER (WHERE selected AND comparable) AS selected_comparable,
               count(*) FILTER (WHERE comparable) AS standalone_comparable,
               avg(net_r_50) FILTER (WHERE comparable) AS standalone_mean_net_r_50,
               avg(net_return_50) FILTER (WHERE comparable) AS standalone_mean_net_return_50,
               avg(net_r_50) FILTER (WHERE selected AND comparable) AS mean_net_r_50,
               avg(net_return_50) FILTER (WHERE selected AND comparable) AS mean_net_return_50
        FROM selector_assignments
        GROUP BY strategy_id
        ORDER BY strategy_id
        """
    ).fetchdf().to_dict(orient="records")
    by_fold = conn.execute(
        """
        SELECT fold_id,
               min(session_date) AS test_start,
               max(session_date) AS test_end,
               count(*) AS opportunities,
               count(*) FILTER (WHERE selected) AS selected,
               count(*) FILTER (WHERE selected AND comparable) AS comparable,
               avg(net_r_50) FILTER (WHERE selected AND comparable) AS mean_net_r_50,
               avg(net_return_50) FILTER (WHERE selected AND comparable) AS mean_net_return_50
        FROM selector_assignments
        GROUP BY fold_id
        ORDER BY fold_id
        """
    ).fetchdf().to_dict(orient="records")
    fallback = conn.execute(
        """
        SELECT fallback_level, count(*) AS opportunities
        FROM selector_assignments
        GROUP BY fallback_level
        ORDER BY fallback_level NULLS LAST
        """
    ).fetchdf().to_dict(orient="records")
    return {
        "overall": overall,
        "by_strategy": _clean_records(by_strategy),
        "by_fold": _clean_records(by_fold),
        "fallback_usage": _clean_records(fallback),
    }


def run_b35_evidence_analysis(
    output_root: Path,
    *,
    duckdb_threads: int = 8,
) -> dict[str, object]:
    started = time.monotonic()
    output_root = output_root.resolve()
    analysis_root = output_root / "analysis_v1"
    analysis_root.mkdir(parents=True, exist_ok=True)
    progress_path = analysis_root / "progress.json"

    _progress(
        progress_path,
        started=started,
        phase="VERIFY",
        detail="validating final replay summary, receipts, and output hashes",
    )
    summary, group_outputs = validate_replay_artifacts(output_root)
    run_fingerprint = str(summary["run_fingerprint"])
    analysis_identity = {
        "contract": B35_EVIDENCE_ANALYSIS_CONTRACT,
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "run_fingerprint": run_fingerprint,
        "source_fingerprint": summary["source_fingerprint"],
        "split_evidence_fingerprint": summary["split_evidence_fingerprint"],
        "authorization_id": summary["authorization_id"],
        "selector_scoring_cost_bps": SELECTOR_SCORING_COST_BPS,
        "selector_bootstrap_draws": SESSION_CLUSTER_BOOTSTRAP_DRAWS,
        "selector_lcb_quantile": SELECTOR_LCB_QUANTILE,
    }
    analysis_fingerprint = _stable_hash(analysis_identity)

    normalized_path = analysis_root / "opportunities.parquet"
    strategy_path = analysis_root / "strategy_summary.parquet"
    condition_path = analysis_root / "condition_cells.parquet"
    score_path = analysis_root / "selector_scores.parquet"
    assignments_path = analysis_root / "selector_assignments.parquet"

    conn = duckdb.connect()
    conn.execute(f"PRAGMA threads={max(1, int(duckdb_threads))}")
    conn.execute("PRAGMA preserve_insertion_order=false")
    group_glob = output_root / "groups" / "*.jsonl"

    normalized_reused = _reusable_artifact(
        normalized_path,
        phase="NORMALIZE",
        analysis_fingerprint=analysis_fingerprint,
    )
    if normalized_reused:
        _progress(
            progress_path,
            started=started,
            phase="NORMALIZE",
            detail="reusing hash-validated normalized opportunity parquet",
        )
    else:
        _progress(
            progress_path,
            started=started,
            phase="NORMALIZE",
            detail=f"flattening {len(group_outputs)} validated compact group outputs",
        )
        _copy_query_atomic(
            conn,
            _normalization_query(group_glob),
            normalized_path,
            copy_options="FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 250000",
        )
    normalized_count = int(
        conn.execute(
            f"SELECT count(*) FROM read_parquet('{_sql_path(normalized_path)}')"
        ).fetchone()[0]
    )
    if normalized_count != int(summary["fired_opportunity_records"]):
        raise B35EvidenceAnalysisError(
            "normalized opportunity count does not equal the authoritative replay summary"
        )
    if not normalized_reused:
        _publish_artifact_receipt(
            normalized_path,
            phase="NORMALIZE",
            analysis_fingerprint=analysis_fingerprint,
            row_count=normalized_count,
        )
    conn.execute(
        f"CREATE OR REPLACE TEMP VIEW opportunities AS "
        f"SELECT * FROM read_parquet('{_sql_path(normalized_path)}')"
    )
    strategy_ids = {
        str(item[0]) for item in conn.execute("SELECT DISTINCT strategy_id FROM opportunities").fetchall()
    }
    if strategy_ids != set(B34_STRATEGY_IDS):
        raise B35EvidenceAnalysisError("normalized B35 strategy ids drifted")

    _progress(
        progress_path,
        started=started,
        phase="DESCRIPTIVE",
        detail="computing standalone strategy and frozen condition-cell evidence",
    )
    strategy_reused = _reusable_artifact(
        strategy_path,
        phase="STRATEGY_SUMMARY",
        analysis_fingerprint=analysis_fingerprint,
    )
    if not strategy_reused:
        _copy_query_atomic(
            conn,
            f"{_metrics_sql(('strategy_id',))} ORDER BY strategy_id",
            strategy_path,
        )
        strategy_count = int(
            conn.execute(
                f"SELECT count(*) FROM read_parquet('{_sql_path(strategy_path)}')"
            ).fetchone()[0]
        )
        _publish_artifact_receipt(
            strategy_path,
            phase="STRATEGY_SUMMARY",
            analysis_fingerprint=analysis_fingerprint,
            row_count=strategy_count,
        )

    condition_reused = _reusable_artifact(
        condition_path,
        phase="CONDITION_CELLS",
        analysis_fingerprint=analysis_fingerprint,
    )
    if not condition_reused:
        _materialize_condition_cells(conn, condition_path)
        condition_count = int(
            conn.execute(
                f"SELECT count(*) FROM read_parquet('{_sql_path(condition_path)}')"
            ).fetchone()[0]
        )
        _publish_artifact_receipt(
            condition_path,
            phase="CONDITION_CELLS",
            analysis_fingerprint=analysis_fingerprint,
            row_count=condition_count,
        )

    folds = build_walk_forward_folds(date(2016, 1, 4), DEVELOPMENT_LAST_SCORING_SESSION)
    folds_df = pd.DataFrame([asdict(fold) for fold in folds])
    conn.register("folds", folds_df)

    score_reused = _reusable_artifact(
        score_path,
        phase="SELECTOR_SCORES",
        analysis_fingerprint=analysis_fingerprint,
    )
    if score_reused:
        _progress(
            progress_path,
            started=started,
            phase="SELECTOR",
            detail="reusing hash-validated frozen selector score table",
        )
        scores_df = conn.execute(
            f"SELECT * FROM read_parquet('{_sql_path(score_path)}')"
        ).fetchdf()
    else:
        _progress(
            progress_path,
            started=started,
            phase="SELECTOR",
            detail=f"building frozen training-only cell scores across {len(folds)} folds",
        )
        scores_df = _build_selector_scores(
            conn,
            folds=folds,
            run_fingerprint=run_fingerprint,
            progress_path=progress_path,
            started=started,
        )
        if scores_df.empty:
            raise B35EvidenceAnalysisError("selector score table is unexpectedly empty")
        conn.register("selector_scores_publish", scores_df)
        _copy_query_atomic(
            conn,
            "SELECT * FROM selector_scores_publish ORDER BY fold_id, hierarchy_level, cell_key",
            score_path,
        )
        _publish_artifact_receipt(
            score_path,
            phase="SELECTOR_SCORES",
            analysis_fingerprint=analysis_fingerprint,
            row_count=len(scores_df),
        )

    conn.register("selector_scores", scores_df)

    assignment_reused = _reusable_artifact(
        assignments_path,
        phase="SELECTOR_ASSIGNMENTS",
        analysis_fingerprint=analysis_fingerprint,
    )
    if assignment_reused:
        _progress(
            progress_path,
            started=started,
            phase="ASSIGN",
            detail="reusing hash-validated selector assignment table",
        )
    else:
        _progress(
            progress_path,
            started=started,
            phase="ASSIGN",
            detail="applying frozen fallback hierarchy to out-of-sample test opportunities",
        )
        _copy_query_atomic(
            conn,
            _selector_assignments_sql(normalized_path),
            assignments_path,
            copy_options="FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 250000",
        )
        assignment_count = int(
            conn.execute(
                f"SELECT count(*) FROM read_parquet('{_sql_path(assignments_path)}')"
            ).fetchone()[0]
        )
        _publish_artifact_receipt(
            assignments_path,
            phase="SELECTOR_ASSIGNMENTS",
            analysis_fingerprint=analysis_fingerprint,
            row_count=assignment_count,
        )
    conn.execute(
        f"CREATE OR REPLACE TEMP VIEW selector_assignments AS "
        f"SELECT * FROM read_parquet('{_sql_path(assignments_path)}')"
    )

    strategy_rows = _clean_records(
        conn.execute(
            f"SELECT * FROM read_parquet('{_sql_path(strategy_path)}') ORDER BY strategy_id"
        ).fetchdf().to_dict(orient="records")
    )
    condition_support = _clean_records(conn.execute(
        f"""
        SELECT strategy_id, condition_name,
               count(*) AS cells,
               count(*) FILTER (WHERE minimum_support) AS supported_cells,
               max(opportunities) AS max_cell_opportunities
        FROM read_parquet('{_sql_path(condition_path)}')
        GROUP BY strategy_id, condition_name
        ORDER BY strategy_id, condition_name
        """
    ).fetchdf().to_dict(orient="records"))
    selector_summary = _selector_summary(conn)

    folds_payload = [asdict(fold) for fold in folds]
    report: dict[str, object] = {
        **analysis_identity,
        "analysis_fingerprint": analysis_fingerprint,
        "status": "COMPLETE",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "authoritative_replay_summary": str((output_root / "summary.json").resolve()),
        "validated_group_outputs": len(group_outputs),
        "normalized_opportunities": normalized_count,
        "walk_forward_folds": folds_payload,
        "strategy_summary": strategy_rows,
        "condition_support_summary": condition_support,
        "selector_summary": selector_summary,
        "artifacts": {
            "opportunities_parquet": str(normalized_path.resolve()),
            "strategy_summary_parquet": str(strategy_path.resolve()),
            "condition_cells_parquet": str(condition_path.resolve()),
            "selector_scores_parquet": str(score_path.resolve()),
            "selector_assignments_parquet": str(assignments_path.resolve()),
        },
        "scientific_notes": {
            "bootstrap_cluster": "XNYS session",
            "bootstrap_draws": SESSION_CLUSTER_BOOTSTRAP_DRAWS,
            "bootstrap_quantile": "empirical lower order statistic at frozen 5th percentile",
            "fallback_semantics": (
                "back off only when a more-specific cell lacks frozen minimum support; "
                "a supported cell with nonpositive/undefined score abstains and is not rescued by broader cells"
            ),
            "selector_is_profile_only": True,
            "portfolio_promotion": False,
            "future_blind_read": False,
            "consumed_master_read": False,
            "multiplicity_robustness_promotion_gate_complete": False,
        },
        "authority": {
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "paper_authority": False,
            "live_authority": False,
            "strategy_promotion": False,
            "selector_promotion": False,
        },
    }
    _write_json(analysis_root / "analysis_summary.json", report)
    _write_json(analysis_root / "folds.json", folds_payload)
    _progress(
        progress_path,
        started=started,
        phase="COMPLETE",
        detail="strategy x condition evidence and frozen walk-forward selector profile completed",
        completed=normalized_count,
        total=normalized_count,
        state="COMPLETE",
    )
    conn.close()
    return report
