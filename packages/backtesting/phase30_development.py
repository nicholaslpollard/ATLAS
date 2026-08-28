from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_observations import (
    PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION,
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase26_policy import PHASE26_OUTCOME_HORIZON_SESSIONS
from .phase30_policy import (
    PHASE30_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE30_BOOTSTRAP_REPLICATES,
    PHASE30_BOOTSTRAP_SEED,
    PHASE30_CANDIDATES,
    PHASE30_COST_GRID_BPS,
    PHASE30_CURRENT_REACTION_FIELD,
    PHASE30_DEVELOPMENT_END,
    PHASE30_INTERNAL_CONFIDENCE,
    PHASE30_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE30_INTERNAL_MIN_RAW_ROWS,
    PHASE30_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE30_INTERNAL_VALIDATION_FOLDS,
    PHASE30_MAX_SELECTION_WINNERS_PER_DIRECTION,
    PHASE30_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE30_MAX_SINGLE_TICKER_ROW_FRACTION,
    PHASE30_MIN_DIRECTION_ROWS_PER_SESSION,
    PHASE30_MIN_POSITIVE_REGIME_FRACTION,
    PHASE30_MIN_POSITIVE_YEAR_FRACTION,
    PHASE30_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE30_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE30_MULTIPLE_TESTING_ALPHA,
    PHASE30_MULTIPLE_TESTING_METHOD,
    PHASE30_OUTCOME_HORIZON_SESSIONS,
    PHASE30_PRIMARY_COST_BPS,
    PHASE30_PURGE_SESSIONS,
    PHASE30_RESEARCH_START,
    PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE30_SELECTION_CONFIDENCE,
    PHASE30_SELECTION_FOLDS,
    PHASE30_SELECTION_FRACTION,
    PHASE30_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE30_SELECTION_MIN_RAW_ROWS,
    PHASE30_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE30_SIGNAL_TAIL_FRACTION,
    PHASE30_STRESS_COST_BPS,
    Phase30CandidateSpec,
    phase30_policy_fingerprint,
)
from .phase30_predictors import (
    PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION,
    PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION,
    Phase30NewsPredictorBuilder,
)


PHASE30_DEVELOPMENT_STUDY_CONTRACT_VERSION = (
    "phase30-development-study-v1-exact-news-phase26-join-four-hypothesis-selection-internal-protected-blind"
)
PHASE30_DEVELOPMENT_POPULATION_CONTRACT_VERSION = (
    "phase30-development-population-v1-exact-ticker-session-news-phase26-t3"
)
PHASE30_PREDICTION_ARTIFACT_CONTRACT_VERSION = "phase30-development-prediction-v1"
PHASE30_SIGNAL_ARTIFACT_CONTRACT_VERSION = "phase30-development-signal-v1"
PHASE30_FINALIST_ARTIFACT_CONTRACT_VERSION = (
    "phase30-finalists-v1-selection-internal-protected-unread"
)


class Phase30DevelopmentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase30DevelopmentBoundaries:
    selection_start: date
    selection_end: date
    purge_sessions: tuple[date, ...]
    internal_start: date
    internal_end: date
    development_session_count: int
    selection_session_count: int
    internal_session_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "selection_start": self.selection_start.isoformat(),
            "selection_end": self.selection_end.isoformat(),
            "purge_sessions": [item.isoformat() for item in self.purge_sessions],
            "internal_start": self.internal_start.isoformat(),
            "internal_end": self.internal_end.isoformat(),
            "development_session_count": self.development_session_count,
            "selection_session_count": self.selection_session_count,
            "internal_session_count": self.internal_session_count,
        }


@dataclass(frozen=True, slots=True)
class Phase30TrancheMetrics:
    raw_rows: int
    signal_sessions: int
    cost_mean_returns: dict[str, float]
    primary_mean_return: float | None
    primary_median_trade_return: float | None
    primary_trade_win_rate: float | None
    primary_session_win_rate: float | None
    primary_lcb: float | None
    primary_bootstrap_p_value: float | None
    stress_mean_return: float | None
    max_single_session_row_fraction: float | None
    max_single_ticker_row_fraction: float | None
    fold_means: tuple[float, ...]
    positive_folds: int
    eligible_year_means: dict[str, float]
    positive_year_fraction: float | None
    eligible_market_state_means: dict[str, float]
    positive_market_state_fraction: float | None
    eligible_ticker_state_means: dict[str, float]
    positive_ticker_state_fraction: float | None
    session_sharpe: float | None
    mean_session_spearman_ic: float | None
    fold_session_spearman_ics: tuple[float, ...]
    broad_comparator_primary_mean: float | None
    deflated_sharpe_probability: float | None = None
    deflated_sharpe_benchmark: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def chronological_boundaries(sessions: Iterable[date]) -> Phase30DevelopmentBoundaries:
    ordered = tuple(sorted(set(sessions)))
    if len(ordered) < 20:
        raise Phase30DevelopmentError("too few frozen Phase30 development sessions")
    selection_count = int(math.floor(len(ordered) * PHASE30_SELECTION_FRACTION))
    internal_offset = selection_count + PHASE30_PURGE_SESSIONS
    if selection_count <= 0 or internal_offset >= len(ordered):
        raise Phase30DevelopmentError("invalid Phase30 development split")
    selection = ordered[:selection_count]
    purge = ordered[selection_count:internal_offset]
    internal = ordered[internal_offset:]
    if len(purge) != PHASE30_PURGE_SESSIONS or not internal:
        raise Phase30DevelopmentError("Phase30 selection/internal purge partition is incomplete")
    return Phase30DevelopmentBoundaries(
        selection_start=selection[0],
        selection_end=selection[-1],
        purge_sessions=tuple(purge),
        internal_start=internal[0],
        internal_end=internal[-1],
        development_session_count=len(ordered),
        selection_session_count=len(selection),
        internal_session_count=len(internal),
    )


def _derived_seed(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return PHASE30_BOOTSTRAP_SEED + int(digest[:8], 16)


def _bootstrap(values: np.ndarray, *, confidence: float, label: str) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise Phase30DevelopmentError("bootstrap requires a nonempty session vector")
    n = len(values)
    block = min(PHASE30_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE30_BOOTSTRAP_REPLICATES, block_count))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(
        PHASE30_BOOTSTRAP_REPLICATES, -1
    )[:, :n]
    sample_means = values[indices].mean(axis=1)
    lower = float(np.quantile(sample_means, 1.0 - confidence))
    observed = float(values.mean())
    centered = values - observed
    null_means = centered[indices].mean(axis=1)
    p_value = float(
        (1 + np.count_nonzero(null_means >= observed)) / (len(null_means) + 1)
    )
    return lower, p_value


def _fraction_positive(values: Mapping[str, float]) -> float | None:
    if not values:
        return None
    return float(sum(value > 0 for value in values.values()) / len(values))


def _eligible_state_means(
    fired: pd.DataFrame, *, state_field: str, primary_cost: float
) -> dict[str, float]:
    data = fired[["as_of_date", state_field, "directional_return"]].copy()
    data[state_field] = data[state_field].astype("string").fillna("<UNAVAILABLE>")
    grouped = (
        data.groupby([state_field, "as_of_date"], sort=True, observed=True)[
            "directional_return"
        ]
        .mean()
        .reset_index()
    )
    result: dict[str, float] = {}
    for state, subset in grouped.groupby(state_field, sort=True, observed=True):
        if subset["as_of_date"].nunique() < PHASE30_MIN_REGIME_SIGNAL_SESSIONS:
            continue
        result[str(state)] = float(
            pd.to_numeric(subset["directional_return"], errors="coerce").mean()
            - primary_cost
        )
    return result


def _mean_session_spearman(frame: pd.DataFrame) -> float | None:
    if frame.empty or "phase30_score" not in frame.columns:
        return None
    values: list[float] = []
    for _, group in frame.groupby("as_of_date", sort=True, observed=True):
        if len(group) < 3:
            continue
        scores = pd.to_numeric(group["phase30_score"], errors="coerce").rank(
            method="average"
        )
        returns = pd.to_numeric(group["directional_return"], errors="coerce").rank(
            method="average"
        )
        if scores.isna().any() or returns.isna().any():
            continue
        x = scores.to_numpy(dtype=float)
        y = returns.to_numpy(dtype=float)
        if np.std(x) <= 0 or np.std(y) <= 0:
            continue
        correlation = float(np.corrcoef(x, y)[0, 1])
        if math.isfinite(correlation):
            values.append(correlation)
    return None if not values else float(np.mean(values))


def _fold_ic_values(predictions: pd.DataFrame, fold_field: str) -> tuple[float, ...]:
    if predictions.empty or fold_field not in predictions.columns:
        return ()
    values: list[float] = []
    for _, group in predictions.groupby(fold_field, sort=True, observed=True):
        value = _mean_session_spearman(group)
        if value is not None:
            values.append(value)
    return tuple(values)


def _fold_economic_means(
    session: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    fold_field: str,
    primary_cost: float,
) -> tuple[float, ...]:
    if signals.empty or fold_field not in signals.columns:
        return ()
    mapping = signals[["as_of_date", fold_field]].drop_duplicates()
    if mapping.duplicated(["as_of_date"], keep=False).any():
        raise Phase30DevelopmentError("Phase30 signal session belongs to multiple folds")
    merged = session.merge(mapping, on="as_of_date", how="left", validate="one_to_one")
    if merged[fold_field].isna().any():
        raise Phase30DevelopmentError("Phase30 signal session is missing fold attribution")
    return tuple(
        float(group["mean"].mean() - primary_cost)
        for _, group in merged.groupby(fold_field, sort=True, observed=True)
    )


def tranche_metrics(
    signals: pd.DataFrame,
    *,
    predictions: pd.DataFrame,
    confidence: float,
    fold_field: str,
    label: str,
) -> Phase30TrancheMetrics:
    if signals.empty:
        return Phase30TrancheMetrics(
            0,
            0,
            {},
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (),
            0,
            {},
            None,
            {},
            None,
            {},
            None,
            None,
            _mean_session_spearman(predictions),
            _fold_ic_values(predictions, fold_field),
            None,
        )

    data = signals.copy()
    data["as_of_date"] = pd.to_datetime(data["as_of_date"]).dt.date
    data["directional_return"] = pd.to_numeric(
        data["directional_return"], errors="coerce"
    )
    data = data.loc[data["directional_return"].notna()].copy()
    if data.empty:
        return tranche_metrics(
            data,
            predictions=predictions,
            confidence=confidence,
            fold_field=fold_field,
            label=label,
        )

    primary_cost = PHASE30_PRIMARY_COST_BPS / 10_000.0
    stress_cost = PHASE30_STRESS_COST_BPS / 10_000.0
    session = (
        data.groupby("as_of_date", sort=True, observed=True)["directional_return"]
        .agg(["mean", "size"])
        .reset_index()
        .sort_values("as_of_date", kind="stable")
    )
    gross = session["mean"].to_numpy(dtype=float)
    primary = gross - primary_cost
    stress = gross - stress_cost
    lower, p_value = _bootstrap(primary, confidence=confidence, label=label)
    fold_values = _fold_economic_means(
        session, data, fold_field=fold_field, primary_cost=primary_cost
    )

    year_values: dict[int, list[float]] = defaultdict(list)
    for session_date, value in zip(session["as_of_date"], primary, strict=True):
        year_values[session_date.year].append(float(value))
    year_means = {
        str(year): float(np.mean(values))
        for year, values in sorted(year_values.items())
        if len(values) >= PHASE30_MIN_YEAR_SIGNAL_SESSIONS
    }
    market_means = _eligible_state_means(
        data, state_field="market_state", primary_cost=primary_cost
    )
    ticker_means = _eligible_state_means(
        data, state_field="effective_ticker_state", primary_cost=primary_cost
    )
    cost_means = {
        f"{float(cost):g}": float(np.mean(gross - float(cost) / 10_000.0))
        for cost in PHASE30_COST_GRID_BPS
    }
    trade_primary = data["directional_return"].to_numpy(dtype=float) - primary_cost
    primary_std = float(np.std(primary, ddof=1)) if len(primary) > 1 else 0.0
    session_sharpe = (
        None if primary_std <= 0 else float(np.mean(primary) / primary_std)
    )

    prediction_data = predictions.copy()
    if not prediction_data.empty:
        prediction_data["as_of_date"] = pd.to_datetime(
            prediction_data["as_of_date"]
        ).dt.date
        comparator_session = (
            prediction_data.groupby("as_of_date", sort=True, observed=True)[
                "directional_return"
            ]
            .mean()
            .to_numpy(dtype=float)
        )
        broad_comparator = (
            None
            if len(comparator_session) == 0
            else float(np.mean(comparator_session - primary_cost))
        )
    else:
        broad_comparator = None

    raw_rows = int(len(data))
    ticker_counts = data.groupby("ticker", sort=True, observed=True).size()
    max_ticker_fraction = (
        None
        if raw_rows == 0 or ticker_counts.empty
        else float(ticker_counts.max() / raw_rows)
    )
    return Phase30TrancheMetrics(
        raw_rows=raw_rows,
        signal_sessions=int(len(session)),
        cost_mean_returns=cost_means,
        primary_mean_return=float(np.mean(primary)),
        primary_median_trade_return=float(np.median(trade_primary)),
        primary_trade_win_rate=float(np.mean(trade_primary > 0)),
        primary_session_win_rate=float(np.mean(primary > 0)),
        primary_lcb=lower,
        primary_bootstrap_p_value=p_value,
        stress_mean_return=float(np.mean(stress)),
        max_single_session_row_fraction=float(session["size"].max() / raw_rows),
        max_single_ticker_row_fraction=max_ticker_fraction,
        fold_means=fold_values,
        positive_folds=sum(value > 0 for value in fold_values),
        eligible_year_means=year_means,
        positive_year_fraction=_fraction_positive(year_means),
        eligible_market_state_means=market_means,
        positive_market_state_fraction=_fraction_positive(market_means),
        eligible_ticker_state_means=ticker_means,
        positive_ticker_state_fraction=_fraction_positive(ticker_means),
        session_sharpe=session_sharpe,
        mean_session_spearman_ic=_mean_session_spearman(prediction_data),
        fold_session_spearman_ics=_fold_ic_values(prediction_data, fold_field),
        broad_comparator_primary_mean=broad_comparator,
    )


def selection_checks(metrics: Phase30TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE30_SELECTION_MIN_RAW_ROWS,
        "min_signal_sessions": (
            metrics.signal_sessions >= PHASE30_SELECTION_MIN_SIGNAL_SESSIONS
        ),
        "positive_folds": (
            metrics.positive_folds >= PHASE30_SELECTION_MIN_POSITIVE_FOLDS
        ),
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None
            and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(
            metrics.primary_lcb is not None and metrics.primary_lcb > 0
        ),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None
            and metrics.stress_mean_return > 0
        ),
        "year_robustness": bool(
            metrics.positive_year_fraction is not None
            and metrics.positive_year_fraction >= PHASE30_MIN_POSITIVE_YEAR_FRACTION
        ),
        "market_state_robustness": bool(
            metrics.positive_market_state_fraction is not None
            and metrics.positive_market_state_fraction
            >= PHASE30_MIN_POSITIVE_REGIME_FRACTION
        ),
        "ticker_state_robustness": bool(
            metrics.positive_ticker_state_fraction is not None
            and metrics.positive_ticker_state_fraction
            >= PHASE30_MIN_POSITIVE_REGIME_FRACTION
        ),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction
            <= PHASE30_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
        "ticker_concentration": bool(
            metrics.max_single_ticker_row_fraction is not None
            and metrics.max_single_ticker_row_fraction
            <= PHASE30_MAX_SINGLE_TICKER_ROW_FRACTION
        ),
    }


def internal_checks(metrics: Phase30TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE30_INTERNAL_MIN_RAW_ROWS,
        "min_signal_sessions": (
            metrics.signal_sessions >= PHASE30_INTERNAL_MIN_SIGNAL_SESSIONS
        ),
        "positive_folds": (
            metrics.positive_folds >= PHASE30_INTERNAL_MIN_POSITIVE_FOLDS
        ),
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None
            and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(
            metrics.primary_lcb is not None and metrics.primary_lcb > 0
        ),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None
            and metrics.stress_mean_return > 0
        ),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction
            <= PHASE30_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
        "ticker_concentration": bool(
            metrics.max_single_ticker_row_fraction is not None
            and metrics.max_single_ticker_row_fraction
            <= PHASE30_MAX_SINGLE_TICKER_ROW_FRACTION
        ),
    }


def holm_bonferroni(
    p_values: Mapping[str, float], *, alpha: float = PHASE30_MULTIPLE_TESTING_ALPHA
) -> dict[str, dict[str, object]]:
    ordered = sorted((float(value), str(key)) for key, value in p_values.items())
    result: dict[str, dict[str, object]] = {}
    active = True
    total = len(ordered)
    for index, (p_value, key) in enumerate(ordered):
        threshold = alpha / (total - index) if total else 0.0
        reject = bool(active and p_value <= threshold)
        result[key] = {
            "p_value": p_value,
            "threshold": threshold,
            "rejected_null": reject,
        }
        if not reject:
            active = False
    return result


def _with_deflated(
    metrics: dict[str, Phase30TrancheMetrics],
) -> dict[str, Phase30TrancheMetrics]:
    sharpe_values = np.asarray(
        [
            item.session_sharpe
            for item in metrics.values()
            if item.session_sharpe is not None
        ],
        dtype=float,
    )
    if len(sharpe_values) < 2 or float(np.std(sharpe_values, ddof=1)) <= 0:
        return metrics
    sigma = float(np.std(sharpe_values, ddof=1))
    trials = max(2, len(metrics))
    normal = NormalDist()
    gamma = 0.5772156649015329
    benchmark = sigma * (
        (1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / trials)
        + gamma * normal.inv_cdf(1.0 - 1.0 / (trials * math.e))
    )
    result: dict[str, Phase30TrancheMetrics] = {}
    for key, item in metrics.items():
        probability = None
        if item.session_sharpe is not None and item.signal_sessions >= 3:
            denominator = math.sqrt(
                max(1e-12, 1.0 + 0.5 * item.session_sharpe**2)
            )
            z = (
                (item.session_sharpe - benchmark)
                * math.sqrt(item.signal_sessions - 1)
                / denominator
            )
            probability = float(normal.cdf(z))
        result[key] = Phase30TrancheMetrics(
            **{
                **item.to_dict(),
                "deflated_sharpe_probability": probability,
                "deflated_sharpe_benchmark": float(benchmark),
            }
        )
    return result


def _fold_mapping(sessions: tuple[date, ...], folds: int) -> dict[date, int]:
    if len(sessions) < folds:
        raise Phase30DevelopmentError("too few Phase30 sessions for fold attribution")
    blocks = [
        tuple(block.tolist())
        for block in np.array_split(np.asarray(sessions, dtype=object), folds)
    ]
    return {
        session: index for index, block in enumerate(blocks) for session in block
    }


def _assign_fold(
    frame: pd.DataFrame, *, mapping: Mapping[date, int], field: str
) -> pd.DataFrame:
    result = frame.copy()
    result["as_of_date"] = pd.to_datetime(result["as_of_date"]).dt.date
    if result.empty:
        result[field] = pd.Series(dtype="int64")
        return result
    result[field] = result["as_of_date"].map(mapping)
    if result[field].isna().any():
        raise Phase30DevelopmentError("Phase30 fold attribution is incomplete")
    result[field] = result[field].astype(int)
    return result


def _reaction_mask(frame: pd.DataFrame, candidate: Phase30CandidateSpec) -> pd.Series:
    reaction = pd.to_numeric(frame[PHASE30_CURRENT_REACTION_FIELD], errors="coerce")
    if candidate.required_reaction_sign == "POSITIVE":
        return reaction.gt(0)
    if candidate.required_reaction_sign == "NEGATIVE":
        return reaction.lt(0)
    raise Phase30DevelopmentError(
        f"unsupported frozen reaction sign: {candidate.required_reaction_sign}"
    )


def direction_tail_frame(
    frame: pd.DataFrame, candidate: Phase30CandidateSpec
) -> pd.DataFrame:
    """Rank within exact session+direction before the frozen reaction-sign split.

    Sessions with fewer than five direction-eligible rows are excluded. Ties use
    larger news_surprise first, then instrument_id ascending; no outcome is used.
    """
    direction_label = "bullish" if candidate.direction == "LONG" else "bearish"
    result = frame.loc[frame["direction"].astype(str) == direction_label].copy()
    result["phase30_score"] = pd.to_numeric(result["news_surprise"], errors="coerce")
    finite = np.isfinite(result["phase30_score"].to_numpy(dtype=float))
    result = result.loc[finite].copy()
    if result.empty:
        result["phase30_tail_selected"] = pd.Series(dtype=bool)
        return result

    selected_parts: list[pd.DataFrame] = []
    for _, group in result.groupby("as_of_date", sort=True, observed=True):
        if len(group) < PHASE30_MIN_DIRECTION_ROWS_PER_SESSION:
            continue
        ordered = group.sort_values(
            ["phase30_score", "instrument_id"],
            ascending=[False, True],
            kind="stable",
        ).copy()
        count = max(
            1, int(math.ceil(PHASE30_SIGNAL_TAIL_FRACTION * len(ordered)))
        )
        ordered["phase30_tail_selected"] = False
        ordered.iloc[
            :count, ordered.columns.get_loc("phase30_tail_selected")
        ] = True
        selected_parts.append(ordered)
    if not selected_parts:
        empty = result.iloc[0:0].copy()
        empty["phase30_tail_selected"] = pd.Series(dtype=bool)
        return empty
    return (
        pd.concat(selected_parts, ignore_index=True)
        .sort_values(["as_of_date", "instrument_id"], kind="stable")
        .reset_index(drop=True)
    )


def candidate_views(
    frame: pd.DataFrame, candidate: Phase30CandidateSpec
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranked = direction_tail_frame(frame, candidate)
    if ranked.empty:
        return ranked.copy(), ranked.copy()
    predictions = ranked.loc[_reaction_mask(ranked, candidate)].copy()
    signals = predictions.loc[
        predictions["phase30_tail_selected"].fillna(False).astype(bool)
    ].copy()
    return predictions, signals


def _write_parquet(
    settings: AtlasSettings, frame: pd.DataFrame, target: Path, *, order_by: str
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase30_development_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM phase30_development_write ORDER BY {order_by}) "
            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
            f"ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


class Phase30DevelopmentStudy:
    """First Phase30 stage allowed to read development outcomes, never protected ones."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase26 = Phase26ObservationBuilder(settings)
        self.news = Phase30NewsPredictorBuilder(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase30" / "v1" / "development"

    def population_path(self) -> Path:
        return self.root / "development_population.parquet"

    def predictions_path(self) -> Path:
        return self.root / "development_predictions.parquet"

    def signals_path(self) -> Path:
        return self.root / "development_signals.parquet"

    def finalists_path(self) -> Path:
        return self.root / "finalists.json"

    def report_path(self) -> Path:
        return self.root / "development_study.json"

    @staticmethod
    def _read_json(path: Path, *, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise Phase30DevelopmentError(f"missing {label}: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Phase30DevelopmentError(f"invalid {label}: {path}") from exc
        if not isinstance(payload, dict):
            raise Phase30DevelopmentError(f"{label} must be a JSON object")
        return payload

    def _load_sources(
        self,
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
        news_report = self._read_json(
            self.news.report_path(), label="Phase30 predictor report"
        )
        if news_report.get("contract_version") != PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION:
            raise Phase30DevelopmentError("Phase30 predictor report contract mismatch")
        if news_report.get("phase30_policy_fingerprint") != phase30_policy_fingerprint():
            raise Phase30DevelopmentError("Phase30 predictor report policy mismatch")
        if news_report.get("pass") is not True:
            raise Phase30DevelopmentError("Phase30 predictor report is not passing")
        if int(news_report.get("target_outcome_rows_read", -1)) != 0:
            raise Phase30DevelopmentError("Phase30 predictor stage already read target outcomes")
        if int(news_report.get("protected_return_rows_read", -1)) != 0:
            raise Phase30DevelopmentError("Phase30 predictor stage consumed protected returns")
        news_path = self.news.development_path()
        if (
            not news_path.is_file()
            or news_report.get("development_sha256") != sha256_file(news_path)
        ):
            raise Phase30DevelopmentError("Phase30 development predictor SHA mismatch")

        phase26_report = self._read_json(
            self.phase26.report_path(), label="Phase26 observation report"
        )
        if (
            phase26_report.get("contract_version")
            != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION
        ):
            raise Phase30DevelopmentError("Phase26 observation report contract mismatch")
        if phase26_report.get("pass") is not True:
            raise Phase30DevelopmentError("Phase26 observation report is not passing")
        if int(phase26_report.get("protected_return_reads", -1)) != 0:
            raise Phase30DevelopmentError("Phase26 protected returns were consumed")
        if (
            str(phase26_report.get("development_boundary_label_end"))
            != PHASE30_DEVELOPMENT_END
        ):
            raise Phase30DevelopmentError("Phase26/Phase30 development boundary mismatch")
        if PHASE26_OUTCOME_HORIZON_SESSIONS != PHASE30_OUTCOME_HORIZON_SESSIONS:
            raise Phase30DevelopmentError("Phase26/Phase30 outcome horizon mismatch")
        phase26_path = self.phase26.development_path()
        if (
            not phase26_path.is_file()
            or phase26_report.get("development_sha256") != sha256_file(phase26_path)
        ):
            raise Phase30DevelopmentError("Phase26 development observation SHA mismatch")

        con = connect_utc(":memory:")
        try:
            news = con.execute(
                f"SELECT * FROM read_parquet({sql_string(news_path)}) "
                "ORDER BY session_date, ticker"
            ).fetch_df()
            phase26 = con.execute(
                f"SELECT * FROM read_parquet({sql_string(phase26_path)}) "
                "ORDER BY as_of_date, instrument_id"
            ).fetch_df()
        finally:
            con.close()

        if news.empty or phase26.empty:
            raise Phase30DevelopmentError("Phase30 development source is empty")
        if set(news["contract_version"].astype(str)) != {
            PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION
        }:
            raise Phase30DevelopmentError("Phase30 development predictor row contract mismatch")
        if set(phase26["contract_version"].astype(str)) != {
            PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION
        }:
            raise Phase30DevelopmentError("Phase26 development row contract mismatch")
        return news, phase26, news_report, phase26_report

    def _join_population(
        self, news: pd.DataFrame, phase26: pd.DataFrame
    ) -> pd.DataFrame:
        con = connect_utc(":memory:")
        try:
            con.register("p30_news", news)
            con.register("p30_phase26", phase26)
            joined = con.execute(
                """
                SELECT
                    ? AS phase30_contract_version,
                    ? AS phase30_policy_fingerprint,
                    CAST(p.as_of_date AS DATE) AS as_of_date,
                    p.instrument_id,
                    p.ticker,
                    p.direction,
                    p.effective_state,
                    p.top_setup,
                    CAST(p.priority_score AS DOUBLE) AS priority_score,
                    p.market_state,
                    p.sector_state,
                    p.raw_ticker_state,
                    p.effective_ticker_state,
                    CAST(p.persistence_depth AS BIGINT) AS persistence_depth,
                    p.identity_quality,
                    CAST(p.safe_start_date AS DATE) AS safe_start_date,
                    CAST(p.safe_end_date AS DATE) AS safe_end_date,
                    p.interval_key,
                    CAST(p.d1_return_1 AS DOUBLE) AS d1_return_1,
                    CAST(p.daily_close AS DOUBLE) AS daily_close,
                    CAST(p.future_date AS DATE) AS future_date,
                    CAST(p.future_close AS DOUBLE) AS future_close,
                    CAST(p.forward_return AS DOUBLE) AS forward_return,
                    CAST(p.directional_return AS DOUBLE) AS directional_return,
                    CAST(n.session_close_utc AS VARCHAR) AS news_session_close_utc,
                    CAST(n.decision_cutoff_utc AS VARCHAR) AS news_decision_cutoff_utc,
                    CAST(n.current_unique_article_count AS BIGINT) AS current_unique_article_count,
                    CAST(n.previous_20_log1p_mean AS DOUBLE) AS previous_20_log1p_mean,
                    CAST(n.news_surprise AS DOUBLE) AS news_surprise
                FROM p30_phase26 p
                INNER JOIN p30_news n
                  ON n.ticker = p.ticker
                 AND CAST(n.session_date AS DATE) = CAST(p.as_of_date AS DATE)
                ORDER BY p.as_of_date, p.instrument_id
                """,
                [
                    PHASE30_DEVELOPMENT_POPULATION_CONTRACT_VERSION,
                    phase30_policy_fingerprint(),
                ],
            ).fetch_df()
        finally:
            con.close()

        if joined.empty:
            raise Phase30DevelopmentError("Phase30 exact development join is empty")
        for field in ("as_of_date", "future_date", "safe_start_date", "safe_end_date"):
            joined[field] = pd.to_datetime(joined[field]).dt.date
        if joined.duplicated(["as_of_date", "instrument_id"], keep=False).any():
            raise Phase30DevelopmentError("Phase30 joined population has duplicate candidate keys")
        if joined.duplicated(["as_of_date", "ticker"], keep=False).any():
            raise Phase30DevelopmentError(
                "Phase30 exact ticker/session join is not one-to-one in candidate population"
            )
        if max(joined["as_of_date"]) > date.fromisoformat(PHASE30_DEVELOPMENT_END):
            raise Phase30DevelopmentError("Phase30 development join crossed frozen boundary")
        if not set(joined["direction"].astype(str)).issubset({"bullish", "bearish"}):
            raise Phase30DevelopmentError("Phase30 source contains unknown direction")
        for field in (
            "d1_return_1",
            "future_close",
            "forward_return",
            "directional_return",
            "news_surprise",
        ):
            values = pd.to_numeric(joined[field], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(values).all():
                raise Phase30DevelopmentError(
                    f"Phase30 joined population contains nonfinite {field}"
                )
        expected = np.where(
            joined["direction"].astype(str).to_numpy() == "bullish",
            joined["forward_return"].to_numpy(dtype=float),
            -joined["forward_return"].to_numpy(dtype=float),
        )
        if not np.allclose(
            expected,
            joined["directional_return"].to_numpy(dtype=float),
            rtol=0.0,
            atol=1e-12,
        ):
            raise Phase30DevelopmentError("Phase30 source directional return geometry drifted")
        return joined

    def _boundaries(self) -> Phase30DevelopmentBoundaries:
        sessions = tuple(
            self.calendar.sessions_in_range(
                date.fromisoformat(PHASE30_RESEARCH_START),
                date.fromisoformat(PHASE30_DEVELOPMENT_END),
            )
        )
        if not sessions:
            raise Phase30DevelopmentError("Phase30 frozen development calendar is empty")
        return chronological_boundaries(sessions)

    @staticmethod
    def _decorate(
        frame: pd.DataFrame,
        candidate: Phase30CandidateSpec,
        *,
        stage: str,
        signal: bool,
    ) -> pd.DataFrame:
        result = frame.copy()
        contract = (
            PHASE30_SIGNAL_ARTIFACT_CONTRACT_VERSION
            if signal
            else PHASE30_PREDICTION_ARTIFACT_CONTRACT_VERSION
        )
        field = "signal_contract_version" if signal else "prediction_contract_version"
        result.insert(0, field, contract)
        result.insert(1, "candidate_id", candidate.candidate_id)
        result.insert(2, "candidate_family", candidate.family)
        result.insert(3, "strategy_direction", candidate.direction)
        result.insert(4, "required_reaction_sign", candidate.required_reaction_sign)
        result.insert(5, "research_stage", stage)
        return result

    def run(self) -> dict[str, object]:
        if PHASE30_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_4":
            raise Phase30DevelopmentError("Phase30 global Holm contract drifted")
        if len(PHASE30_CANDIDATES) != 4:
            raise Phase30DevelopmentError("Phase30 candidate family drifted from exactly four")
        if PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED:
            raise Phase30DevelopmentError("Phase30 runner-up substitution unexpectedly enabled")

        news, phase26, news_report, phase26_report = self._load_sources()
        population = self._join_population(news, phase26)
        population_path = self.population_path()
        _write_parquet(
            self.settings,
            population,
            population_path,
            order_by="as_of_date, instrument_id",
        )

        boundaries = self._boundaries()
        selection_frame = population.loc[
            (population["as_of_date"] >= boundaries.selection_start)
            & (population["as_of_date"] <= boundaries.selection_end)
        ].copy()
        internal_frame = population.loc[
            (population["as_of_date"] >= boundaries.internal_start)
            & (population["as_of_date"] <= boundaries.internal_end)
        ].copy()
        if selection_frame.empty or internal_frame.empty:
            raise Phase30DevelopmentError(
                "Phase30 exact joined population does not cover both development tranches"
            )
        if selection_frame["as_of_date"].isin(boundaries.purge_sessions).any() or internal_frame[
            "as_of_date"
        ].isin(boundaries.purge_sessions).any():
            raise Phase30DevelopmentError("Phase30 purge sessions leaked into research tranches")

        selection_sessions = tuple(
            self.calendar.sessions_in_range(
                boundaries.selection_start, boundaries.selection_end
            )
        )
        internal_sessions = tuple(
            self.calendar.sessions_in_range(
                boundaries.internal_start, boundaries.internal_end
            )
        )
        selection_fold_map = _fold_mapping(
            selection_sessions, PHASE30_SELECTION_FOLDS
        )
        internal_fold_map = _fold_mapping(
            internal_sessions, PHASE30_INTERNAL_VALIDATION_FOLDS
        )

        prediction_artifacts: list[pd.DataFrame] = []
        signal_artifacts: list[pd.DataFrame] = []
        selection_metrics: dict[str, Phase30TrancheMetrics] = {}
        selection_check_map: dict[str, dict[str, bool]] = {}

        for candidate in PHASE30_CANDIDATES:
            predictions, signals = candidate_views(selection_frame, candidate)
            predictions = _assign_fold(
                predictions,
                mapping=selection_fold_map,
                field="selection_fold",
            )
            signals = _assign_fold(
                signals,
                mapping=selection_fold_map,
                field="selection_fold",
            )
            decorated_predictions = self._decorate(
                predictions, candidate, stage="SELECTION", signal=False
            )
            decorated_signals = self._decorate(
                signals, candidate, stage="SELECTION", signal=True
            )
            prediction_artifacts.append(decorated_predictions)
            signal_artifacts.append(decorated_signals)
            metrics = tranche_metrics(
                decorated_signals,
                predictions=decorated_predictions,
                confidence=PHASE30_SELECTION_CONFIDENCE,
                fold_field="selection_fold",
                label=f"selection:{candidate.candidate_id}",
            )
            selection_metrics[candidate.candidate_id] = metrics
            selection_check_map[candidate.candidate_id] = selection_checks(metrics)

        selection_metrics = _with_deflated(selection_metrics)
        p_values = {
            candidate.candidate_id: (
                selection_metrics[candidate.candidate_id].primary_bootstrap_p_value
                if selection_metrics[candidate.candidate_id].primary_bootstrap_p_value
                is not None
                else 1.0
            )
            for candidate in PHASE30_CANDIDATES
        }
        holm = holm_bonferroni(p_values)
        if len(holm) != 4:
            raise Phase30DevelopmentError("Phase30 Holm family is incomplete")

        survivor_ids = {
            candidate.candidate_id
            for candidate in PHASE30_CANDIDATES
            if all(selection_check_map[candidate.candidate_id].values())
            and bool(holm[candidate.candidate_id]["rejected_null"])
        }

        winner_ids: list[str] = []
        for direction in ("LONG", "SHORT"):
            eligible = [
                candidate
                for candidate in PHASE30_CANDIDATES
                if candidate.direction == direction
                and candidate.candidate_id in survivor_ids
            ]
            eligible.sort(
                key=lambda candidate: (
                    -float(
                        selection_metrics[candidate.candidate_id].primary_lcb
                        if selection_metrics[candidate.candidate_id].primary_lcb
                        is not None
                        else -math.inf
                    ),
                    -float(
                        selection_metrics[candidate.candidate_id].primary_mean_return
                        if selection_metrics[candidate.candidate_id].primary_mean_return
                        is not None
                        else -math.inf
                    ),
                    candidate.candidate_id,
                )
            )
            if eligible:
                winner_ids.append(eligible[0].candidate_id)
        if len(winner_ids) > 2 * PHASE30_MAX_SELECTION_WINNERS_PER_DIRECTION:
            raise Phase30DevelopmentError(
                "Phase30 selected more than one winner per direction"
            )

        internal_metrics: dict[str, Phase30TrancheMetrics] = {}
        internal_check_map: dict[str, dict[str, bool]] = {}
        finalist_ids: list[str] = []
        for candidate_id in winner_ids:
            candidate = next(
                item for item in PHASE30_CANDIDATES if item.candidate_id == candidate_id
            )
            predictions, signals = candidate_views(internal_frame, candidate)
            predictions = _assign_fold(
                predictions,
                mapping=internal_fold_map,
                field="internal_fold",
            )
            signals = _assign_fold(
                signals,
                mapping=internal_fold_map,
                field="internal_fold",
            )
            decorated_predictions = self._decorate(
                predictions,
                candidate,
                stage="INTERNAL_VALIDATION",
                signal=False,
            )
            decorated_signals = self._decorate(
                signals,
                candidate,
                stage="INTERNAL_VALIDATION",
                signal=True,
            )
            prediction_artifacts.append(decorated_predictions)
            signal_artifacts.append(decorated_signals)
            metrics = tranche_metrics(
                decorated_signals,
                predictions=decorated_predictions,
                confidence=PHASE30_INTERNAL_CONFIDENCE,
                fold_field="internal_fold",
                label=f"internal:{candidate.candidate_id}",
            )
            internal_metrics[candidate_id] = metrics
            internal_check_map[candidate_id] = internal_checks(metrics)
            if all(internal_check_map[candidate_id].values()):
                finalist_ids.append(candidate_id)

        finalist_directions = [
            next(
                item.direction
                for item in PHASE30_CANDIDATES
                if item.candidate_id == candidate_id
            )
            for candidate_id in finalist_ids
        ]
        if len(finalist_directions) != len(set(finalist_directions)):
            raise Phase30DevelopmentError(
                "Phase30 created more than one finalist in a direction"
            )

        all_predictions = pd.concat(
            prediction_artifacts, ignore_index=True, sort=False
        )
        all_signals = pd.concat(signal_artifacts, ignore_index=True, sort=False)
        predictions_path = self.predictions_path()
        signals_path = self.signals_path()
        _write_parquet(
            self.settings,
            all_predictions,
            predictions_path,
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )
        _write_parquet(
            self.settings,
            all_signals,
            signals_path,
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )

        finalists = []
        for candidate_id in finalist_ids:
            candidate = next(
                item for item in PHASE30_CANDIDATES if item.candidate_id == candidate_id
            )
            finalists.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "family": candidate.family,
                    "direction": candidate.direction,
                    "required_reaction_sign": candidate.required_reaction_sign,
                    "score_field": candidate.score_field,
                    "score_orientation": candidate.score_orientation,
                    "signal_tail_fraction": PHASE30_SIGNAL_TAIL_FRACTION,
                    "same_session_direction_min_rows": PHASE30_MIN_DIRECTION_ROWS_PER_SESSION,
                    "tie_break": "news_surprise_desc_then_instrument_id_asc",
                    "development_population_sha256": sha256_file(population_path),
                }
            )
        finalists_path = self.finalists_path()
        finalist_payload: dict[str, object] = {
            "contract_version": PHASE30_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase30_policy_fingerprint": phase30_policy_fingerprint(),
            "selection_survivor_ids": sorted(survivor_ids),
            "selection_winner_ids": winner_ids,
            "finalist_ids": finalist_ids,
            "finalists": finalists,
            "frozen": True,
            "runner_up_substitution_allowed": False,
            "protected_candidate_rows_read": 0,
            "protected_returns_read": 0,
            "protected_holdout_consumed": False,
            "development_predictions_sha256": sha256_file(predictions_path),
            "development_signals_sha256": sha256_file(signals_path),
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }
        finalists_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            finalists_path,
            json.dumps(finalist_payload, indent=2, sort_keys=True) + "\n",
        )

        checks = {
            "source_predictor_pass": news_report.get("pass") is True,
            "source_predictor_outcome_blind": (
                int(news_report.get("target_outcome_rows_read", -1)) == 0
                and int(news_report.get("protected_return_rows_read", -1)) == 0
            ),
            "source_phase26_pass": phase26_report.get("pass") is True,
            "source_phase26_protected_unread": (
                int(phase26_report.get("protected_return_reads", -1)) == 0
            ),
            "exact_ticker_session_join_nonempty": len(population) > 0,
            "development_boundary_exact": (
                str(phase26_report.get("development_boundary_label_end"))
                == PHASE30_DEVELOPMENT_END
            ),
            "outcome_horizon_exact": (
                PHASE26_OUTCOME_HORIZON_SESSIONS
                == PHASE30_OUTCOME_HORIZON_SESSIONS
                == 3
            ),
            "current_reaction_exact": PHASE30_CURRENT_REACTION_FIELD == "d1_return_1",
            "exact_candidate_count": len(PHASE30_CANDIDATES) == 4,
            "holm_global_candidate_count": len(holm) == 4,
            "winner_direction_limit": len(winner_ids) <= 2,
            "internal_only_winners": set(internal_metrics) == set(winner_ids),
            "finalists_subset_winners": set(finalist_ids).issubset(set(winner_ids)),
            "runner_up_substitution_disabled": not PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED,
            "protected_candidate_rows_unread": True,
            "protected_returns_unread": True,
            "protected_holdout_unconsumed": True,
        }
        report: dict[str, object] = {
            "contract_version": PHASE30_DEVELOPMENT_STUDY_CONTRACT_VERSION,
            "phase30_policy_fingerprint": phase30_policy_fingerprint(),
            "status": (
                "DEVELOPMENT_STUDY_PASS"
                if all(checks.values())
                else "DEVELOPMENT_STUDY_FAIL"
            ),
            "source_phase30_predictor_report_path": str(self.news.report_path().resolve()),
            "source_phase30_development_sha256": news_report["development_sha256"],
            "source_phase26_observation_report_path": str(self.phase26.report_path().resolve()),
            "source_phase26_development_sha256": phase26_report["development_sha256"],
            "development_population_rows": int(len(population)),
            "development_population_tickers": int(population["ticker"].nunique()),
            "development_population_sessions": int(population["as_of_date"].nunique()),
            "development_population_sha256": sha256_file(population_path),
            "development_target_rows_read": int(len(population)),
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "boundaries": boundaries.to_dict(),
            "selection_metrics": {
                key: value.to_dict() for key, value in selection_metrics.items()
            },
            "selection_checks": selection_check_map,
            "holm_bonferroni": holm,
            "selection_survivor_ids": sorted(survivor_ids),
            "selection_winner_ids": winner_ids,
            "internal_metrics": {
                key: value.to_dict() for key, value in internal_metrics.items()
            },
            "internal_checks": internal_check_map,
            "finalist_ids": finalist_ids,
            "predictions_rows": int(len(all_predictions)),
            "signals_rows": int(len(all_signals)),
            "predictions_sha256": sha256_file(predictions_path),
            "signals_sha256": sha256_file(signals_path),
            "finalists_sha256": sha256_file(finalists_path),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(self.report_path().resolve()),
            "pass": all(checks.values()),
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.report_path(),
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase30DevelopmentError(
                "Phase30 development study failed: " + ", ".join(failed)
            )
        return report
