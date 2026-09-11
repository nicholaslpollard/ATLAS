from __future__ import annotations

import hashlib
import itertools
import json
import math
import time
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Iterable

import duckdb
import exchange_calendars as xcals
import numpy as np
import pandas as pd

from packages.backtesting.b35_development_replay import _sha256_file
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.strategies.b35_conditional_evidence_contract import (
    ALL_IN_ROUND_TRIP_COST_GRID_BPS,
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
    PBO_CSCV_PARTITIONS,
    PRIMARY_FDR_Q,
    ROBUSTNESS_PERTURBATIONS,
)


B35_ROBUSTNESS_CONTRACT = "atlas-b35-development-robustness-v1-post-profile-no-promotion"
EXPECTED_ANALYSIS_CONTRACT = "atlas-b35-development-evidence-selector-analysis-v1"
EXPECTED_ANALYSIS_FINGERPRINT = (
    "8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f"
)
SESSION_BOOTSTRAP_DRAWS = 10_000
SESSION_BOOTSTRAP_CHUNK = 250
PROFILE_IDS = (*B34_STRATEGY_IDS, "b35_frozen_selector_v1")


class B35RobustnessError(RuntimeError):
    pass


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


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _progress(
    path: Path,
    *,
    started: float,
    phase: str,
    detail: str,
    completed: int | None = None,
    total: int | None = None,
    state: str = "RUNNING",
) -> None:
    elapsed = time.monotonic() - started
    payload: dict[str, object] = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "phase": phase,
        "detail": detail,
        "elapsed_seconds": elapsed,
        "state": state,
    }
    if completed is not None:
        payload["completed"] = int(completed)
    if total is not None:
        payload["total"] = int(total)
    _write_json(path, payload)
    count_text = ""
    if completed is not None and total is not None:
        count_text = f" {completed}/{total}"
    print(
        f"[{payload['timestamp_utc']}] B35 ROBUSTNESS {phase}{count_text} | "
        f"{detail} | elapsed={elapsed / 60.0:.1f}m | state={state}",
        flush=True,
    )


def _validate_analysis_artifact(
    path: Path,
    *,
    phase: str,
    analysis_fingerprint: str,
) -> None:
    receipt_path = path.with_suffix(path.suffix + ".receipt.json")
    if not path.is_file() or not receipt_path.is_file():
        raise B35RobustnessError(f"required B35 analysis artifact/receipt is missing: {path.name}")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise B35RobustnessError(f"invalid B35 analysis receipt: {receipt_path}") from exc
    expected_receipt_id = _stable_hash(
        {key: value for key, value in receipt.items() if key != "receipt_id"}
    )
    required = {
        "contract": EXPECTED_ANALYSIS_CONTRACT,
        "phase": phase,
        "analysis_fingerprint": analysis_fingerprint,
        "artifact_path": str(path.resolve()),
    }
    if str(receipt.get("receipt_id") or "") != expected_receipt_id:
        raise B35RobustnessError(f"B35 analysis receipt self-hash drifted: {path.name}")
    if any(receipt.get(key) != value for key, value in required.items()):
        raise B35RobustnessError(f"B35 analysis receipt identity drifted: {path.name}")
    if receipt.get("artifact_sha256") != _sha256_file(path):
        raise B35RobustnessError(f"B35 analysis artifact SHA-256 drifted: {path.name}")


def validate_analysis_root(analysis_root: Path) -> dict[str, object]:
    analysis_root = analysis_root.resolve()
    summary_path = analysis_root / "analysis_summary.json"
    if not summary_path.is_file():
        raise B35RobustnessError("B35 analysis_summary.json is missing")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise B35RobustnessError("B35 analysis_summary.json is invalid") from exc
    required = {
        "status": "COMPLETE",
        "contract": EXPECTED_ANALYSIS_CONTRACT,
        "analysis_fingerprint": EXPECTED_ANALYSIS_FINGERPRINT,
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
    }
    if any(summary.get(key) != value for key, value in required.items()):
        raise B35RobustnessError("B35 analysis summary identity/status drifted")
    if int(summary.get("normalized_opportunities") or 0) != 20_171_286:
        raise B35RobustnessError("B35 normalized opportunity count drifted")
    authority = summary.get("authority")
    if not isinstance(authority, dict):
        raise B35RobustnessError("B35 analysis authority block is missing")
    for field in ("provider_calls", "broker_reads", "broker_writes"):
        if authority.get(field) != 0:
            raise B35RobustnessError(f"B35 analysis {field} is nonzero")
    for field in ("paper_authority", "live_authority", "strategy_promotion", "selector_promotion"):
        if authority.get(field) is not False:
            raise B35RobustnessError(f"B35 analysis {field} changed authority")
    notes = summary.get("scientific_notes")
    if not isinstance(notes, dict) or notes.get("future_blind_read") is not False or notes.get("consumed_master_read") is not False:
        raise B35RobustnessError("B35 analysis protected-read state drifted")

    artifact_phases = {
        "opportunities.parquet": "NORMALIZE",
        "strategy_summary.parquet": "STRATEGY_SUMMARY",
        "condition_cells.parquet": "CONDITION_CELLS",
        "selector_scores.parquet": "SELECTOR_SCORES",
        "selector_assignments.parquet": "SELECTOR_ASSIGNMENTS",
    }
    for filename, phase in artifact_phases.items():
        _validate_analysis_artifact(
            analysis_root / filename,
            phase=phase,
            analysis_fingerprint=EXPECTED_ANALYSIS_FINGERPRINT,
        )
    return summary


def _complete_test_sessions(summary: dict[str, object]) -> tuple[date, ...]:
    folds = summary.get("walk_forward_folds")
    if not isinstance(folds, list) or len(folds) != 33:
        raise B35RobustnessError("B35 walk-forward fold count drifted")
    calendar = xcals.get_calendar("XNYS")
    sessions: list[date] = []
    for item in folds:
        if not isinstance(item, dict):
            raise B35RobustnessError("B35 walk-forward fold schema drifted")
        start = date.fromisoformat(str(item["test_start"])[:10])
        end = date.fromisoformat(str(item["test_end"])[:10])
        fold_sessions = [
            stamp.date()
            for stamp in calendar.sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
        ]
        if len(fold_sessions) != 63:
            raise B35RobustnessError("B35 frozen test fold no longer contains exactly 63 XNYS sessions")
        sessions.extend(fold_sessions)
    if len(sessions) != 33 * 63 or len(set(sessions)) != len(sessions):
        raise B35RobustnessError("B35 test-session folds overlap or drifted")
    return tuple(sessions)


def _atomic_copy_query(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    target: Path,
) -> None:
    temp = unique_temp_path(target)
    try:
        conn.execute(
            f"COPY ({query}) TO '{_sql_path(temp)}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        replace_with_retry(temp, target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _artifact_receipt_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".receipt.json")


def _publish_robustness_receipt(
    path: Path,
    *,
    robustness_fingerprint: str,
    phase: str,
    row_count: int,
) -> None:
    payload: dict[str, object] = {
        "contract": B35_ROBUSTNESS_CONTRACT,
        "phase": phase,
        "robustness_fingerprint": robustness_fingerprint,
        "artifact_path": str(path.resolve()),
        "artifact_sha256": _sha256_file(path),
        "row_count": int(row_count),
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    payload["receipt_id"] = _stable_hash(payload)
    _write_json(_artifact_receipt_path(path), payload)


def _reusable_robustness_artifact(
    path: Path,
    *,
    robustness_fingerprint: str,
    phase: str,
) -> bool:
    receipt_path = _artifact_receipt_path(path)
    if not path.is_file() or not receipt_path.is_file():
        return False
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    expected_id = _stable_hash({key: value for key, value in receipt.items() if key != "receipt_id"})
    return (
        receipt.get("receipt_id") == expected_id
        and receipt.get("contract") == B35_ROBUSTNESS_CONTRACT
        and receipt.get("phase") == phase
        and receipt.get("robustness_fingerprint") == robustness_fingerprint
        and receipt.get("artifact_path") == str(path.resolve())
        and receipt.get("artifact_sha256") == _sha256_file(path)
    )


def _build_session_profiles(
    conn: duckdb.DuckDBPyConnection,
    *,
    sessions: tuple[date, ...],
    assignments_path: Path,
    target: Path,
) -> int:
    session_df = pd.DataFrame({"session_date": pd.to_datetime(sessions)})
    conn.register("robustness_sessions", session_df)
    source = _sql_path(assignments_path)
    pieces: list[str] = []
    return_columns = ", ".join(
        f"coalesce(avg(a.net_return_{cost}) FILTER (WHERE a.comparable), 0.0) AS net_return_{cost}"
        for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS
    )
    for strategy_id in B34_STRATEGY_IDS:
        pieces.append(
            f"""
            SELECT s.session_date,
                   '{strategy_id}' AS profile_id,
                   {return_columns},
                   coalesce(avg(a.net_r_50) FILTER (WHERE a.comparable), 0.0) AS net_r_50,
                   count(a.strategy_id) FILTER (WHERE a.comparable) AS comparable_opportunities,
                   count(a.strategy_id) AS fired_opportunities
            FROM robustness_sessions s
            LEFT JOIN read_parquet('{source}') a
              ON a.session_date = s.session_date
             AND a.strategy_id = '{strategy_id}'
            GROUP BY s.session_date
            """
        )
    selected_returns = ", ".join(
        f"coalesce(avg(a.net_return_{cost}) FILTER (WHERE a.selected AND a.comparable), 0.0) AS net_return_{cost}"
        for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS
    )
    pieces.append(
        f"""
        SELECT s.session_date,
               'b35_frozen_selector_v1' AS profile_id,
               {selected_returns},
               coalesce(avg(a.net_r_50) FILTER (WHERE a.selected AND a.comparable), 0.0) AS net_r_50,
               count(a.strategy_id) FILTER (WHERE a.selected AND a.comparable) AS comparable_opportunities,
               count(a.strategy_id) FILTER (WHERE a.selected) AS fired_opportunities
        FROM robustness_sessions s
        LEFT JOIN read_parquet('{source}') a
          ON a.session_date = s.session_date
        GROUP BY s.session_date
        """
    )
    _atomic_copy_query(
        conn,
        " UNION ALL ".join(pieces) + " ORDER BY session_date, profile_id",
        target,
    )
    count = int(conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(target)}')").fetchone()[0])
    expected = len(sessions) * len(PROFILE_IDS)
    if count != expected:
        raise B35RobustnessError(f"session profile row count {count} != expected {expected}")
    return count


def _session_series(
    conn: duckdb.DuckDBPyConnection,
    path: Path,
    profile_id: str,
    column: str,
) -> np.ndarray:
    rows = conn.execute(
        f"SELECT {column} FROM read_parquet('{_sql_path(path)}') "
        "WHERE profile_id=? ORDER BY session_date",
        [profile_id],
    ).fetchall()
    return np.asarray([float(row[0]) for row in rows], dtype=float)


def _sharpe(values: np.ndarray) -> float | None:
    if values.size < 2:
        return None
    std = float(np.std(values, ddof=1))
    if std <= 0 or not math.isfinite(std):
        return None
    return float(np.mean(values) / std)


def _annualized_sharpe(values: np.ndarray) -> float | None:
    value = _sharpe(values)
    return None if value is None else value * math.sqrt(252.0)


def _max_drawdown(values: np.ndarray) -> float | None:
    if values.size == 0 or np.any(values <= -1.0):
        return None
    wealth = np.cumprod(1.0 + values)
    peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[:-1]
    drawdown = wealth / peaks - 1.0
    return float(np.min(drawdown))


def _max_negative_streak(values: np.ndarray, *, ignore_flat: bool) -> int:
    sequence = values[np.abs(values) > 1e-15] if ignore_flat else values
    best = current = 0
    for value in sequence:
        if value < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _concentration(values: np.ndarray) -> dict[str, float | None]:
    abs_values = np.abs(values)
    abs_total = float(abs_values.sum())
    positives = np.sort(values[values > 0.0])[::-1]
    positive_total = float(positives.sum())

    def positive_share(k: int) -> float | None:
        if positive_total <= 0:
            return None
        return float(positives[:k].sum() / positive_total)

    return {
        "top_1_positive_session_share": positive_share(1),
        "top_5_positive_session_share": positive_share(5),
        "top_10_positive_session_share": positive_share(10),
        "largest_absolute_session_share": None if abs_total <= 0 else float(abs_values.max() / abs_total),
        "absolute_session_hhi": None if abs_total <= 0 else float(np.square(abs_values / abs_total).sum()),
    }


def _bootstrap_profile(
    values: np.ndarray,
    *,
    seed_material: str,
    draws: int = SESSION_BOOTSTRAP_DRAWS,
) -> dict[str, object]:
    if values.size == 0:
        raise ValueError("bootstrap requires a nonempty session series")
    seed = int.from_bytes(hashlib.sha256(seed_material.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    means = np.empty(draws, dtype=float)
    sharpes = np.empty(draws, dtype=float)
    terminals = np.empty(draws, dtype=float)
    drawdowns = np.empty(draws, dtype=float)
    cursor = 0
    while cursor < draws:
        width = min(SESSION_BOOTSTRAP_CHUNK, draws - cursor)
        indices = rng.integers(0, values.size, size=(width, values.size))
        sampled = values[indices]
        means[cursor : cursor + width] = sampled.mean(axis=1)
        std = sampled.std(axis=1, ddof=1)
        sharpes[cursor : cursor + width] = np.divide(
            sampled.mean(axis=1) * math.sqrt(252.0),
            std,
            out=np.full(width, np.nan),
            where=std > 0,
        )
        if np.any(sampled <= -1.0):
            terminals[cursor : cursor + width] = np.nan
            drawdowns[cursor : cursor + width] = np.nan
        else:
            wealth = np.cumprod(1.0 + sampled, axis=1)
            terminals[cursor : cursor + width] = wealth[:, -1] - 1.0
            peaks = np.maximum.accumulate(
                np.concatenate((np.ones((width, 1)), wealth[:, :-1]), axis=1), axis=1
            )
            drawdowns[cursor : cursor + width] = np.min(wealth / peaks - 1.0, axis=1)
        cursor += width

    def q(array: np.ndarray, quantile: float) -> float | None:
        valid = array[np.isfinite(array)]
        if valid.size == 0:
            return None
        return float(np.quantile(valid, quantile))

    return {
        "draws": draws,
        "mean_session_return_q05": q(means, 0.05),
        "mean_session_return_q50": q(means, 0.50),
        "mean_session_return_q95": q(means, 0.95),
        "probability_mean_session_return_gt_zero": float(np.mean(means > 0.0)),
        "annualized_sharpe_q05": q(sharpes, 0.05),
        "annualized_sharpe_q50": q(sharpes, 0.50),
        "annualized_sharpe_q95": q(sharpes, 0.95),
        "terminal_compound_return_q05": q(terminals, 0.05),
        "terminal_compound_return_q50": q(terminals, 0.50),
        "terminal_compound_return_q95": q(terminals, 0.95),
        "max_drawdown_q05": q(drawdowns, 0.05),
        "max_drawdown_q50": q(drawdowns, 0.50),
        "max_drawdown_q95": q(drawdowns, 0.95),
    }


def _centered_bootstrap_pvalue(
    values: np.ndarray,
    *,
    seed_material: str,
    draws: int = SESSION_BOOTSTRAP_DRAWS,
) -> float:
    values = np.asarray(values, dtype=float)
    if values.size < 2 or float(np.mean(values)) <= 0.0:
        return 1.0
    observed = float(np.mean(values))
    centered = values - observed
    seed = int.from_bytes(hashlib.sha256(seed_material.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    exceed = 0
    completed = 0
    chunk = 1000
    while completed < draws:
        width = min(chunk, draws - completed)
        indices = rng.integers(0, centered.size, size=(width, centered.size))
        null_means = centered[indices].mean(axis=1)
        exceed += int(np.count_nonzero(null_means >= observed))
        completed += width
    return float((exceed + 1) / (draws + 1))


def benjamini_hochberg(pvalues: Iterable[float], q: float = PRIMARY_FDR_Q) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(list(pvalues), dtype=float)
    if values.size == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=bool)
    if np.any((values < 0.0) | (values > 1.0) | ~np.isfinite(values)):
        raise ValueError("p-values must be finite and in [0, 1]")
    order = np.argsort(values, kind="stable")
    ranked = values[order]
    m = len(values)
    adjusted_ranked = ranked * m / np.arange(1, m + 1, dtype=float)
    adjusted_ranked = np.minimum.accumulate(adjusted_ranked[::-1])[::-1]
    adjusted_ranked = np.clip(adjusted_ranked, 0.0, 1.0)
    adjusted = np.empty(m, dtype=float)
    adjusted[order] = adjusted_ranked
    return adjusted, adjusted <= q


def _selected_cell_tests(
    conn: duckdb.DuckDBPyConnection,
    *,
    opportunities_path: Path,
    assignments_path: Path,
    robustness_fingerprint: str,
) -> pd.DataFrame:
    opportunities = _sql_path(opportunities_path)
    assignments = _sql_path(assignments_path)
    duplicate_count = int(
        conn.execute(
            f"""
            SELECT count(*) FROM (
                SELECT strategy_id, symbol, session_date, direction, count(*) AS n
                FROM read_parquet('{opportunities}')
                GROUP BY strategy_id, symbol, session_date, direction
                HAVING count(*) > 1
            )
            """
        ).fetchone()[0]
    )
    if duplicate_count:
        raise B35RobustnessError("normalized B35 opportunity key is not unique")
    assignment_count = int(conn.execute(f"SELECT count(*) FROM read_parquet('{assignments}')").fetchone()[0])
    joined_count = int(
        conn.execute(
            f"""
            SELECT count(*)
            FROM read_parquet('{assignments}') a
            JOIN read_parquet('{opportunities}') o
              USING (strategy_id, symbol, session_date, direction)
            """
        ).fetchone()[0]
    )
    if joined_count != assignment_count:
        raise B35RobustnessError("selector assignments do not join one-to-one to normalized opportunities")

    session_cells = conn.execute(
        f"""
        SELECT
            a.fold_id,
            a.strategy_id,
            a.fallback_level,
            CASE a.fallback_level
                WHEN 1 THEN o.selector_key_1
                WHEN 2 THEN o.selector_key_2
                WHEN 3 THEN o.selector_key_3
                WHEN 4 THEN o.selector_key_4
                WHEN 5 THEN o.selector_key_5
            END AS cell_key,
            a.session_date,
            count(*) AS comparable_opportunities,
            avg(a.net_r_50) AS session_mean_net_r_50,
            avg(a.net_return_50) AS session_mean_net_return_50
        FROM read_parquet('{assignments}') a
        JOIN read_parquet('{opportunities}') o
          USING (strategy_id, symbol, session_date, direction)
        WHERE a.selected AND a.comparable
        GROUP BY a.fold_id, a.strategy_id, a.fallback_level,
                 CASE a.fallback_level
                    WHEN 1 THEN o.selector_key_1
                    WHEN 2 THEN o.selector_key_2
                    WHEN 3 THEN o.selector_key_3
                    WHEN 4 THEN o.selector_key_4
                    WHEN 5 THEN o.selector_key_5
                 END,
                 a.session_date
        ORDER BY a.fold_id, a.strategy_id, a.fallback_level, cell_key, a.session_date
        """
    ).fetchdf()
    records: list[dict[str, object]] = []
    group_columns = ["fold_id", "strategy_id", "fallback_level", "cell_key"]
    for keys, group in session_cells.groupby(group_columns, dropna=False, sort=True):
        fold_id, strategy_id, fallback_level, cell_key = keys
        values = group["session_mean_net_r_50"].to_numpy(dtype=float)
        pvalue = _centered_bootstrap_pvalue(
            values,
            seed_material=(
                f"{robustness_fingerprint}|CELL_FDR|{fold_id}|{strategy_id}|"
                f"{fallback_level}|{cell_key}"
            ),
        )
        records.append(
            {
                "fold_id": int(fold_id),
                "strategy_id": str(strategy_id),
                "fallback_level": int(fallback_level),
                "cell_key": str(cell_key),
                "sessions": int(group["session_date"].nunique()),
                "comparable_opportunities": int(group["comparable_opportunities"].sum()),
                "mean_session_net_r_50": float(values.mean()),
                "mean_session_net_return_50": float(group["session_mean_net_return_50"].mean()),
                "one_sided_centered_session_bootstrap_p": pvalue,
            }
        )
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    adjusted, rejected = benjamini_hochberg(
        frame["one_sided_centered_session_bootstrap_p"].to_numpy(dtype=float),
        PRIMARY_FDR_Q,
    )
    frame["bh_adjusted_p"] = adjusted
    frame["bh_reject_at_q_0_05"] = rejected
    return frame.sort_values(group_columns, kind="stable").reset_index(drop=True)


def _deflated_sharpe(profile_series: dict[str, np.ndarray]) -> dict[str, object]:
    raw_sharpes = {
        profile_id: _sharpe(values)
        for profile_id, values in profile_series.items()
    }
    finite = np.asarray(
        [value for value in raw_sharpes.values() if value is not None and math.isfinite(value)],
        dtype=float,
    )
    n_trials = len(profile_series)
    if finite.size < 2:
        benchmark = 0.0
    else:
        sigma_sr = float(np.std(finite, ddof=1))
        gamma = 0.5772156649015329
        normal = NormalDist()
        benchmark = sigma_sr * (
            (1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / n_trials)
            + gamma * normal.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
        )
    result: dict[str, object] = {
        "candidate_profile_count": n_trials,
        "expected_max_daily_sharpe_benchmark": benchmark,
        "expected_max_annualized_sharpe_benchmark": benchmark * math.sqrt(252.0),
        "profiles": [],
    }
    profiles: list[dict[str, object]] = []
    for profile_id in PROFILE_IDS:
        values = profile_series[profile_id]
        sr = raw_sharpes[profile_id]
        if sr is None:
            profiles.append(
                {
                    "profile_id": profile_id,
                    "annualized_sharpe": None,
                    "deflated_sharpe_probability": None,
                }
            )
            continue
        mean = float(np.mean(values))
        std0 = float(np.std(values, ddof=0))
        if std0 <= 0:
            skew = 0.0
            kurtosis = 3.0
        else:
            centered = (values - mean) / std0
            skew = float(np.mean(centered**3))
            kurtosis = float(np.mean(centered**4))
        denominator = math.sqrt(
            max(1e-15, 1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr)
        )
        z = (sr - benchmark) * math.sqrt(max(1, values.size - 1)) / denominator
        probability = NormalDist().cdf(z)
        profiles.append(
            {
                "profile_id": profile_id,
                "annualized_sharpe": sr * math.sqrt(252.0),
                "daily_sharpe": sr,
                "skew": skew,
                "pearson_kurtosis": kurtosis,
                "deflated_sharpe_probability": probability,
            }
        )
    result["profiles"] = profiles
    result["method_note"] = (
        "Bailey/Lopez-de-Prado-style probabilistic/deflated Sharpe diagnostic using the "
        "five declared B35 session profiles as the candidate family; descriptive only, "
        "not a promotion gate by itself."
    )
    return result


def _pbo_cscv(profile_series: dict[str, np.ndarray]) -> dict[str, object]:
    matrix = np.column_stack([profile_series[profile_id] for profile_id in PROFILE_IDS])
    n_sessions = matrix.shape[0]
    partitions = np.array_split(np.arange(n_sessions), PBO_CSCV_PARTITIONS)
    if any(part.size == 0 for part in partitions):
        raise B35RobustnessError("not enough sessions for frozen PBO/CSCV partitions")

    def sharpes(rows: np.ndarray) -> np.ndarray:
        block = matrix[rows]
        means = block.mean(axis=0)
        std = block.std(axis=0, ddof=1)
        return np.divide(means, std, out=np.full(matrix.shape[1], -np.inf), where=std > 0)

    lambdas: list[float] = []
    chosen_counts = {profile_id: 0 for profile_id in PROFILE_IDS}
    test_ranks: list[int] = []
    indices = range(PBO_CSCV_PARTITIONS)
    half = PBO_CSCV_PARTITIONS // 2
    all_partition_ids = set(indices)
    for train_parts in itertools.combinations(indices, half):
        train_rows = np.concatenate([partitions[index] for index in train_parts])
        test_parts = sorted(all_partition_ids.difference(train_parts))
        test_rows = np.concatenate([partitions[index] for index in test_parts])
        train_sr = sharpes(train_rows)
        selected_index = int(np.argmax(train_sr))
        chosen_counts[PROFILE_IDS[selected_index]] += 1
        test_sr = sharpes(test_rows)
        selected_test = test_sr[selected_index]
        rank = 1 + int(np.count_nonzero(test_sr < selected_test))
        test_ranks.append(rank)
        omega = rank / (len(PROFILE_IDS) + 1.0)
        lambdas.append(math.log(omega / (1.0 - omega)))
    lambda_array = np.asarray(lambdas, dtype=float)
    return {
        "partitions": PBO_CSCV_PARTITIONS,
        "train_partitions_per_split": half,
        "combinations": len(lambdas),
        "candidate_profiles": list(PROFILE_IDS),
        "probability_of_backtest_overfitting": float(np.mean(lambda_array <= 0.0)),
        "median_logit_oos_rank": float(np.median(lambda_array)),
        "median_oos_rank": float(np.median(np.asarray(test_ranks, dtype=float))),
        "in_sample_winner_counts": chosen_counts,
        "cash_is_benchmark_not_candidate": True,
    }


def _profile_fdr(
    profile_series: dict[str, np.ndarray],
    *,
    robustness_fingerprint: str,
) -> list[dict[str, object]]:
    pvalues = []
    records = []
    for profile_id in PROFILE_IDS:
        values = profile_series[profile_id]
        pvalue = _centered_bootstrap_pvalue(
            values,
            seed_material=f"{robustness_fingerprint}|PROFILE_FDR|{profile_id}",
        )
        pvalues.append(pvalue)
        records.append(
            {
                "profile_id": profile_id,
                "mean_session_return_50": float(np.mean(values)),
                "one_sided_centered_session_bootstrap_p": pvalue,
            }
        )
    adjusted, rejected = benjamini_hochberg(pvalues, PRIMARY_FDR_Q)
    for index, record in enumerate(records):
        record["bh_adjusted_p"] = float(adjusted[index])
        record["bh_reject_at_q_0_05"] = bool(rejected[index])
    return records


def _profile_metrics(
    conn: duckdb.DuckDBPyConnection,
    *,
    session_profiles_path: Path,
    robustness_fingerprint: str,
) -> tuple[list[dict[str, object]], dict[str, np.ndarray]]:
    metrics: list[dict[str, object]] = []
    profile_series: dict[str, np.ndarray] = {}
    for profile_id in PROFILE_IDS:
        values_50 = _session_series(conn, session_profiles_path, profile_id, "net_return_50")
        profile_series[profile_id] = values_50
        cost_grid: dict[str, object] = {}
        for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS:
            values = _session_series(conn, session_profiles_path, profile_id, f"net_return_{cost}")
            cost_grid[str(cost)] = {
                "mean_session_return": float(np.mean(values)),
                "median_session_return": float(np.median(values)),
                "annualized_sharpe": _annualized_sharpe(values),
                "active_session_fraction": float(np.mean(np.abs(values) > 1e-15)),
                "max_drawdown_research_profile": _max_drawdown(values),
            }
        active = np.abs(values_50) > 1e-15
        row: dict[str, object] = {
            "profile_id": profile_id,
            "sessions": int(values_50.size),
            "active_sessions_50bps": int(np.count_nonzero(active)),
            "cost_grid": cost_grid,
            "max_consecutive_losing_sessions": _max_negative_streak(values_50, ignore_flat=False),
            "max_consecutive_active_losses_ignoring_cash_gaps": _max_negative_streak(values_50, ignore_flat=True),
            "concentration_50bps": _concentration(values_50),
            "bootstrap_50bps": _bootstrap_profile(
                values_50,
                seed_material=f"{robustness_fingerprint}|PROFILE_BOOTSTRAP|{profile_id}|50",
            ),
        }
        metrics.append(row)
    return metrics, profile_series


def _perturbation_audit() -> dict[str, object]:
    exact = {
        "all_in_round_trip_cost_bps": {
            "status": "EXACT_FROM_RETAINED_OUTCOMES",
            "values": list(ALL_IN_ROUND_TRIP_COST_GRID_BPS),
        }
    }
    targeted = {}
    for name, values in ROBUSTNESS_PERTURBATIONS.items():
        if name == "all_in_round_trip_cost_bps":
            continue
        targeted[name] = {
            "status": "REQUIRES_TARGETED_MINUTE_REPLAY",
            "values": list(values),
            "reason": (
                "the compact B35 fired-opportunity outcomes do not contain the counterfactual "
                "minute path/setup state required to recompute this perturbation exactly"
            ),
        }
    return {
        "exact_from_retained_artifacts": exact,
        "requires_targeted_minute_replay": targeted,
        "all_preregistered_perturbations_complete": False,
        "approximation_used": False,
    }


def run_b35_robustness_analysis(
    output_root: Path,
    *,
    duckdb_threads: int = 8,
) -> dict[str, object]:
    started = time.monotonic()
    output_root = output_root.resolve()
    analysis_root = output_root / "analysis_v1"
    robustness_root = analysis_root / "robustness_v1"
    robustness_root.mkdir(parents=True, exist_ok=True)
    progress_path = robustness_root / "progress.json"

    _progress(
        progress_path,
        started=started,
        phase="VERIFY",
        detail="validating accepted B35 analysis summary and hash-receipted artifacts",
    )
    summary = validate_analysis_root(analysis_root)
    sessions = _complete_test_sessions(summary)
    robustness_identity = {
        "contract": B35_ROBUSTNESS_CONTRACT,
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "analysis_fingerprint": EXPECTED_ANALYSIS_FINGERPRINT,
        "fdr_q": PRIMARY_FDR_Q,
        "pbo_cscv_partitions": PBO_CSCV_PARTITIONS,
        "session_bootstrap_draws": SESSION_BOOTSTRAP_DRAWS,
        "profile_ids": PROFILE_IDS,
        "profile_unit": "complete_XNYS_test_session_mean_return_with_cash_zero",
    }
    robustness_fingerprint = _stable_hash(robustness_identity)

    conn = duckdb.connect()
    conn.execute(f"PRAGMA threads={max(1, int(duckdb_threads))}")
    conn.execute("PRAGMA preserve_insertion_order=false")
    assignments_path = analysis_root / "selector_assignments.parquet"
    opportunities_path = analysis_root / "opportunities.parquet"
    session_profiles_path = robustness_root / "session_profiles.parquet"
    cell_tests_path = robustness_root / "selected_cell_fdr.parquet"

    if _reusable_robustness_artifact(
        session_profiles_path,
        robustness_fingerprint=robustness_fingerprint,
        phase="SESSION_PROFILES",
    ):
        _progress(
            progress_path,
            started=started,
            phase="PROFILES",
            detail="reusing hash-validated complete-session profile table",
        )
    else:
        _progress(
            progress_path,
            started=started,
            phase="PROFILES",
            detail=f"building five aligned research profiles across {len(sessions)} frozen test sessions",
        )
        row_count = _build_session_profiles(
            conn,
            sessions=sessions,
            assignments_path=assignments_path,
            target=session_profiles_path,
        )
        _publish_robustness_receipt(
            session_profiles_path,
            robustness_fingerprint=robustness_fingerprint,
            phase="SESSION_PROFILES",
            row_count=row_count,
        )

    _progress(
        progress_path,
        started=started,
        phase="TAIL",
        detail=f"running deterministic {SESSION_BOOTSTRAP_DRAWS:,}-draw session bootstrap, cost, streak, and concentration diagnostics",
    )
    profiles, profile_series = _profile_metrics(
        conn,
        session_profiles_path=session_profiles_path,
        robustness_fingerprint=robustness_fingerprint,
    )

    _progress(
        progress_path,
        started=started,
        phase="MULTIPLICITY",
        detail="computing selected-cell/profile BH-FDR and Deflated-Sharpe diagnostics",
    )
    cell_tests = _selected_cell_tests(
        conn,
        opportunities_path=opportunities_path,
        assignments_path=assignments_path,
        robustness_fingerprint=robustness_fingerprint,
    )
    conn.register("selected_cell_fdr_publish", cell_tests)
    _atomic_copy_query(
        conn,
        "SELECT * FROM selected_cell_fdr_publish ORDER BY fold_id, strategy_id, fallback_level, cell_key",
        cell_tests_path,
    )
    _publish_robustness_receipt(
        cell_tests_path,
        robustness_fingerprint=robustness_fingerprint,
        phase="SELECTED_CELL_FDR",
        row_count=len(cell_tests),
    )
    profile_fdr = _profile_fdr(profile_series, robustness_fingerprint=robustness_fingerprint)
    deflated_sharpe = _deflated_sharpe(profile_series)

    _progress(
        progress_path,
        started=started,
        phase="PBO",
        detail=f"running {PBO_CSCV_PARTITIONS}-partition CSCV/PBO across the five declared B35 profiles",
    )
    pbo = _pbo_cscv(profile_series)

    perturbations = _perturbation_audit()
    cell_records = [] if cell_tests.empty else json.loads(cell_tests.to_json(orient="records"))
    report: dict[str, object] = {
        **robustness_identity,
        "robustness_fingerprint": robustness_fingerprint,
        "status": "COMPLETE_PROFILE_WITH_TARGETED_PERTURBATIONS_PENDING",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "complete_test_sessions": len(sessions),
        "profiles": profiles,
        "profile_fdr": profile_fdr,
        "selected_cell_fdr": cell_records,
        "selected_cell_fdr_summary": {
            "hypotheses": int(len(cell_tests)),
            "bh_rejections_q_0_05": int(cell_tests["bh_reject_at_q_0_05"].sum()) if not cell_tests.empty else 0,
        },
        "deflated_sharpe": deflated_sharpe,
        "pbo_cscv": pbo,
        "perturbation_audit": perturbations,
        "benchmarks": {
            "cash": {
                "same_unit_comparable": True,
                "session_return": 0.0,
                "note": "cash is the abstention benchmark and not a CSCV candidate profile",
            },
            "a34_stable_nonlearned_long_only_reference": {
                "same_unit_comparable": False,
                "accepted_development_account_return": -0.17912608,
                "accepted_development_max_drawdown": -0.20803073,
                "note": (
                    "context only: A34 uses a different daily strategy set, account construction, "
                    "date scope and cost geometry; no false direct statistical comparison is made"
                ),
            },
        },
        "scientific_notes": {
            "session_profile_definition": (
                "mean comparable opportunity return within each complete XNYS test session; "
                "sessions with no comparable activity are zero/cash"
            ),
            "dependence_control": "session is the primary bootstrap/test cluster",
            "bh_fdr_scope": (
                "out-of-sample selected fold x strategy x fallback-level x condition-cell hypotheses; "
                "one-sided centered session-cluster bootstrap p-values"
            ),
            "profile_fdr_scope": "five declared same-session research profiles at 50 bps",
            "pbo_scope": "five declared research profiles; cash is a benchmark, not a candidate",
            "account_equivalence": False,
            "future_blind_read": False,
            "consumed_master_read": False,
            "new_minute_outcome_replay": False,
            "robustness_gate_complete": False,
            "reason_robustness_gate_incomplete": (
                "preregistered entry/setup-threshold perturbations require an exact targeted minute replay"
            ),
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
        "artifacts": {
            "session_profiles_parquet": str(session_profiles_path.resolve()),
            "selected_cell_fdr_parquet": str(cell_tests_path.resolve()),
        },
    }
    _write_json(robustness_root / "robustness_summary.json", report)
    _progress(
        progress_path,
        started=started,
        phase="COMPLETE",
        detail="retained-artifact robustness profile completed; targeted minute perturbations remain explicit",
        completed=len(sessions),
        total=len(sessions),
        state="COMPLETE",
    )
    conn.close()
    return report
