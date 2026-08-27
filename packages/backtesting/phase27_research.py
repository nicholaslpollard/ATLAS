from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase27_models import (
    candidate_direction_frame,
    fit_learned_model,
    score_candidate,
    select_fixed_tail,
    selection_oos_signals,
    tune_hyperparameters,
)
from .phase27_policy import (
    PHASE27_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE27_BOOTSTRAP_REPLICATES,
    PHASE27_BOOTSTRAP_SEED,
    PHASE27_CANDIDATES,
    PHASE27_COST_GRID_BPS,
    PHASE27_DEVELOPMENT_END,
    PHASE27_INTERNAL_CONFIDENCE,
    PHASE27_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE27_INTERNAL_MIN_RAW_ROWS,
    PHASE27_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE27_INTERNAL_VALIDATION_FOLDS,
    PHASE27_MAX_SELECTION_WINNERS_PER_DIRECTION,
    PHASE27_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE27_MIN_POSITIVE_REGIME_FRACTION,
    PHASE27_MIN_POSITIVE_YEAR_FRACTION,
    PHASE27_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE27_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE27_MULTIPLE_TESTING_ALPHA,
    PHASE27_PREDICTOR_FIELDS,
    PHASE27_PRIMARY_COST_BPS,
    PHASE27_PURGE_SESSIONS,
    PHASE27_RESEARCH_START,
    PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE27_SELECTION_CONFIDENCE,
    PHASE27_SELECTION_FOLDS,
    PHASE27_SELECTION_FRACTION,
    PHASE27_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE27_SELECTION_MIN_RAW_ROWS,
    PHASE27_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE27_STRESS_COST_BPS,
    Phase27CandidateSpec,
    phase27_policy_fingerprint,
)
from .phase27_population import (
    PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION,
    PHASE27_POPULATION_REPORT_CONTRACT_VERSION,
    Phase27PopulationBuilder,
    transformed_feature_names,
)


PHASE27_RESEARCH_REPORT_CONTRACT_VERSION = (
    "phase27-research-v1-nested-walk-forward-holm-internal-protected-blind"
)
PHASE27_PREDICTION_ARTIFACT_CONTRACT_VERSION = "phase27-development-prediction-v1"
PHASE27_SIGNAL_ARTIFACT_CONTRACT_VERSION = "phase27-development-signal-v1"
PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION = (
    "phase27-finalists-v1-selection-only-model-choice-protected-unread"
)


class Phase27ResearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase27DevelopmentBoundaries:
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
class Phase27TrancheMetrics:
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
    tuning_trial_count: int
    deflated_sharpe_probability: float | None = None
    deflated_sharpe_benchmark: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def chronological_boundaries(sessions: Iterable[date]) -> Phase27DevelopmentBoundaries:
    ordered = tuple(sorted(set(sessions)))
    if len(ordered) < 20:
        raise Phase27ResearchError("too few Phase27 development sessions")
    selection_count = int(math.floor(len(ordered) * PHASE27_SELECTION_FRACTION))
    internal_offset = selection_count + PHASE27_PURGE_SESSIONS
    if selection_count <= 0 or internal_offset >= len(ordered):
        raise Phase27ResearchError("invalid Phase27 development split")
    selection = ordered[:selection_count]
    purge = ordered[selection_count:internal_offset]
    internal = ordered[internal_offset:]
    if len(purge) != PHASE27_PURGE_SESSIONS or not internal:
        raise Phase27ResearchError("Phase27 selection/internal purge partition is incomplete")
    return Phase27DevelopmentBoundaries(
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
    return PHASE27_BOOTSTRAP_SEED + int(digest[:8], 16)


def _bootstrap(values: np.ndarray, *, confidence: float, label: str) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise Phase27ResearchError("bootstrap requires a nonempty session vector")
    n = len(values)
    block = min(PHASE27_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE27_BOOTSTRAP_REPLICATES, block_count))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(
        PHASE27_BOOTSTRAP_REPLICATES, -1
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
    fired: pd.DataFrame,
    *,
    state_field: str,
    primary_cost: float,
) -> dict[str, float]:
    data = fired[["as_of_date", state_field, "directional_return"]].copy()
    data[state_field] = data[state_field].astype("string").fillna("<UNAVAILABLE>")
    grouped = (
        data.groupby([state_field, "as_of_date"], sort=True, observed=True)["directional_return"]
        .mean()
        .reset_index()
    )
    result: dict[str, float] = {}
    for state, subset in grouped.groupby(state_field, sort=True, observed=True):
        if subset["as_of_date"].nunique() < PHASE27_MIN_REGIME_SIGNAL_SESSIONS:
            continue
        result[str(state)] = float(
            pd.to_numeric(subset["directional_return"], errors="coerce").mean()
            - primary_cost
        )
    return result


def _mean_session_spearman(frame: pd.DataFrame) -> float | None:
    if frame.empty or "phase27_score" not in frame.columns:
        return None
    correlations: list[float] = []
    for _, group in frame.groupby("as_of_date", sort=True, observed=True):
        if len(group) < 3:
            continue
        scores = pd.to_numeric(group["phase27_score"], errors="coerce").rank(
            method="average"
        )
        returns = pd.to_numeric(group["directional_return"], errors="coerce").rank(
            method="average"
        )
        if scores.isna().any() or returns.isna().any():
            continue
        x = scores.to_numpy(dtype=np.float64)
        y = returns.to_numpy(dtype=np.float64)
        if np.std(x) <= 0 or np.std(y) <= 0:
            continue
        value = float(np.corrcoef(x, y)[0, 1])
        if math.isfinite(value):
            correlations.append(value)
    return None if not correlations else float(np.mean(correlations))


def _fold_ic_values(predictions: pd.DataFrame, fold_field: str) -> tuple[float, ...]:
    if predictions.empty or fold_field not in predictions.columns:
        return ()
    values: list[float] = []
    for _, group in predictions.groupby(fold_field, sort=True, observed=True):
        ic = _mean_session_spearman(group)
        if ic is not None:
            values.append(ic)
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
        raise Phase27ResearchError("Phase27 signal session belongs to multiple folds")
    merged = session.merge(mapping, on="as_of_date", how="left", validate="one_to_one")
    if merged[fold_field].isna().any():
        raise Phase27ResearchError("Phase27 signal session is missing fold attribution")
    result: list[float] = []
    for _, group in merged.groupby(fold_field, sort=True, observed=True):
        result.append(float(group["mean"].mean() - primary_cost))
    return tuple(result)


def tranche_metrics(
    signals: pd.DataFrame,
    *,
    predictions: pd.DataFrame,
    confidence: float,
    fold_field: str,
    label: str,
    tuning_trial_count: int,
) -> Phase27TrancheMetrics:
    if signals.empty:
        return Phase27TrancheMetrics(
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
            tuning_trial_count,
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
            tuning_trial_count=tuning_trial_count,
        )

    primary_cost = PHASE27_PRIMARY_COST_BPS / 10_000.0
    stress_cost = PHASE27_STRESS_COST_BPS / 10_000.0
    session = (
        data.groupby("as_of_date", sort=True, observed=True)["directional_return"]
        .agg(["mean", "size"])
        .reset_index()
        .sort_values("as_of_date", kind="stable")
    )
    gross = session["mean"].to_numpy(dtype=np.float64)
    primary = gross - primary_cost
    stress = gross - stress_cost
    lower, p_value = _bootstrap(primary, confidence=confidence, label=label)
    fold_values = _fold_economic_means(
        session,
        data,
        fold_field=fold_field,
        primary_cost=primary_cost,
    )

    year_values: dict[int, list[float]] = defaultdict(list)
    for session_date, value in zip(session["as_of_date"], primary, strict=True):
        year_values[session_date.year].append(float(value))
    year_means = {
        str(year): float(np.mean(values))
        for year, values in sorted(year_values.items())
        if len(values) >= PHASE27_MIN_YEAR_SIGNAL_SESSIONS
    }
    market_means = _eligible_state_means(
        data, state_field="market_state", primary_cost=primary_cost
    )
    ticker_means = _eligible_state_means(
        data, state_field="effective_ticker_state", primary_cost=primary_cost
    )

    cost_means = {
        f"{float(cost):g}": float(np.mean(gross - float(cost) / 10_000.0))
        for cost in PHASE27_COST_GRID_BPS
    }
    trade_primary = data["directional_return"].to_numpy(dtype=np.float64) - primary_cost
    primary_std = float(np.std(primary, ddof=1)) if len(primary) > 1 else 0.0
    session_sharpe = None if primary_std <= 0 else float(np.mean(primary) / primary_std)

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
            .to_numpy(dtype=np.float64)
        )
        broad_comparator = (
            None
            if len(comparator_session) == 0
            else float(np.mean(comparator_session - primary_cost))
        )
    else:
        broad_comparator = None

    raw_rows = int(len(data))
    return Phase27TrancheMetrics(
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
        tuning_trial_count=tuning_trial_count,
    )


def selection_checks(metrics: Phase27TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE27_SELECTION_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE27_SELECTION_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE27_SELECTION_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(
            metrics.primary_lcb is not None and metrics.primary_lcb > 0
        ),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None and metrics.stress_mean_return > 0
        ),
        "year_robustness": bool(
            metrics.positive_year_fraction is not None
            and metrics.positive_year_fraction >= PHASE27_MIN_POSITIVE_YEAR_FRACTION
        ),
        "market_state_robustness": bool(
            metrics.positive_market_state_fraction is not None
            and metrics.positive_market_state_fraction >= PHASE27_MIN_POSITIVE_REGIME_FRACTION
        ),
        "ticker_state_robustness": bool(
            metrics.positive_ticker_state_fraction is not None
            and metrics.positive_ticker_state_fraction >= PHASE27_MIN_POSITIVE_REGIME_FRACTION
        ),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction
            <= PHASE27_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def internal_checks(metrics: Phase27TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE27_INTERNAL_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE27_INTERNAL_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE27_INTERNAL_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(
            metrics.primary_lcb is not None and metrics.primary_lcb > 0
        ),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None and metrics.stress_mean_return > 0
        ),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction
            <= PHASE27_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def holm_bonferroni(
    p_values: Mapping[str, float], *, alpha: float = PHASE27_MULTIPLE_TESTING_ALPHA
) -> dict[str, dict[str, object]]:
    ordered = sorted((float(value), key) for key, value in p_values.items())
    total = len(ordered)
    result: dict[str, dict[str, object]] = {}
    rejecting = True
    for index, (p_value, key) in enumerate(ordered):
        threshold = alpha / (total - index) if total else 0.0
        reject = bool(rejecting and p_value <= threshold)
        result[key] = {
            "p_value": p_value,
            "threshold": threshold,
            "rejected_null": reject,
        }
        if not reject:
            rejecting = False
    return result


def _deflated_sharpe_diagnostics(
    metrics: Mapping[str, Phase27TrancheMetrics],
) -> dict[str, tuple[float | None, float | None]]:
    sharpe_values = np.asarray(
        [item.session_sharpe for item in metrics.values() if item.session_sharpe is not None],
        dtype=np.float64,
    )
    if len(sharpe_values) < 2:
        return {key: (None, None) for key in metrics}
    sigma = float(np.std(sharpe_values, ddof=1))
    if sigma <= 0:
        return {key: (None, None) for key in metrics}
    trials = max(2, len(metrics))
    normal = NormalDist()
    euler_gamma = 0.5772156649015329
    benchmark = sigma * (
        (1.0 - euler_gamma) * normal.inv_cdf(1.0 - 1.0 / trials)
        + euler_gamma * normal.inv_cdf(1.0 - 1.0 / (trials * math.e))
    )
    result: dict[str, tuple[float | None, float | None]] = {}
    for key, item in metrics.items():
        if item.session_sharpe is None or item.signal_sessions < 3:
            result[key] = (None, benchmark)
            continue
        denominator = math.sqrt(max(1e-12, 1.0 + 0.5 * item.session_sharpe**2))
        z = (
            (item.session_sharpe - benchmark)
            * math.sqrt(float(item.signal_sessions - 1))
            / denominator
        )
        result[key] = (float(normal.cdf(z)), float(benchmark))
    return result


def _with_deflated(
    metrics: dict[str, Phase27TrancheMetrics]
) -> dict[str, Phase27TrancheMetrics]:
    diagnostic = _deflated_sharpe_diagnostics(metrics)
    return {
        key: Phase27TrancheMetrics(
            **{
                **item.to_dict(),
                "deflated_sharpe_probability": diagnostic[key][0],
                "deflated_sharpe_benchmark": diagnostic[key][1],
            }
        )
        for key, item in metrics.items()
    }


def _write_parquet(
    settings: AtlasSettings,
    frame: pd.DataFrame,
    target: Path,
    *,
    order_by: str,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase27_research_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM phase27_research_write ORDER BY {order_by}) "
            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
            f"ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


def _assign_fold(frame: pd.DataFrame, *, folds: int, field: str) -> pd.DataFrame:
    result = frame.copy()
    sessions = tuple(sorted(set(pd.to_datetime(result["as_of_date"]).dt.date)))
    if len(sessions) < folds:
        raise Phase27ResearchError("too few internal sessions for Phase27 fold attribution")
    blocks = [tuple(block.tolist()) for block in np.array_split(np.asarray(sessions, dtype=object), folds)]
    mapping = {session: index for index, block in enumerate(blocks) for session in block}
    result["as_of_date"] = pd.to_datetime(result["as_of_date"]).dt.date
    result[field] = result["as_of_date"].map(mapping)
    if result[field].isna().any():
        raise Phase27ResearchError("Phase27 fold attribution is incomplete")
    result[field] = result[field].astype(int)
    return result


def _tranche(frame: pd.DataFrame, *, start: date, end: date) -> pd.DataFrame:
    return frame.loc[(frame["as_of_date"] >= start) & (frame["as_of_date"] <= end)].copy()


def _winner_sort_key(
    candidate: Phase27CandidateSpec,
    metrics: Phase27TrancheMetrics,
    candidate_index: Mapping[str, int],
) -> tuple[float, float, float, int]:
    return (
        -float(metrics.primary_lcb or -math.inf),
        -float(metrics.stress_mean_return or -math.inf),
        -float(metrics.primary_mean_return or -math.inf),
        candidate_index[candidate.candidate_id],
    )


class Phase27DevelopmentResearch:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase27PopulationBuilder(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase27" / "v1" / "research"

    def report_path(self) -> Path:
        return self.root / "development_research.json"

    def predictions_path(self) -> Path:
        return self.root / "development_predictions.parquet"

    def signals_path(self) -> Path:
        return self.root / "development_signals.parquet"

    def finalists_path(self) -> Path:
        return self.root / "finalists.json"

    def _load_development(self) -> tuple[pd.DataFrame, dict[str, object], Path]:
        report_path = self.population.report_path()
        if not report_path.is_file():
            raise Phase27ResearchError("Phase27 population report is missing")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Phase27ResearchError("Phase27 population report is invalid JSON") from exc
        if not isinstance(report, dict):
            raise Phase27ResearchError("Phase27 population report must be an object")
        if report.get("contract_version") != PHASE27_POPULATION_REPORT_CONTRACT_VERSION:
            raise Phase27ResearchError("Phase27 population report contract mismatch")
        if report.get("phase27_policy_fingerprint") != phase27_policy_fingerprint():
            raise Phase27ResearchError("Phase27 population policy fingerprint mismatch")
        if report.get("pass") is not True or int(report.get("protected_return_reads", -1)) != 0:
            raise Phase27ResearchError("Phase27 population is not protected-blind passing")

        path = self.population.development_path()
        if not path.is_file() or report.get("development_sha256") != sha256_file(path):
            raise Phase27ResearchError("Phase27 development population SHA mismatch")
        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY as_of_date, instrument_id"
            ).fetch_df()
        finally:
            con.close()
        if frame.empty:
            raise Phase27ResearchError("Phase27 development model population is empty")
        if set(frame["phase27_contract_version"].astype(str)) != {
            PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION
        }:
            raise Phase27ResearchError("Phase27 development model row contract mismatch")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        return frame, report, report_path

    def _boundaries(self) -> Phase27DevelopmentBoundaries:
        sessions = tuple(
            self.calendar.sessions_in_range(
                date.fromisoformat(PHASE27_RESEARCH_START),
                date.fromisoformat(PHASE27_DEVELOPMENT_END),
            )
        )
        return chronological_boundaries(sessions)

    @staticmethod
    def _decorate_predictions(
        frame: pd.DataFrame,
        candidate: Phase27CandidateSpec,
        *,
        stage: str,
    ) -> pd.DataFrame:
        result = frame.copy()
        result.insert(0, "prediction_contract_version", PHASE27_PREDICTION_ARTIFACT_CONTRACT_VERSION)
        result.insert(1, "candidate_id", candidate.candidate_id)
        result.insert(2, "candidate_family", candidate.family)
        result.insert(3, "strategy_direction", candidate.direction)
        result.insert(4, "research_stage", stage)
        return result

    @staticmethod
    def _decorate_signals(
        frame: pd.DataFrame,
        candidate: Phase27CandidateSpec,
        *,
        stage: str,
    ) -> pd.DataFrame:
        result = frame.copy()
        result.insert(0, "signal_contract_version", PHASE27_SIGNAL_ARTIFACT_CONTRACT_VERSION)
        result.insert(1, "candidate_id", candidate.candidate_id)
        result.insert(2, "candidate_family", candidate.family)
        result.insert(3, "strategy_direction", candidate.direction)
        result.insert(4, "research_stage", stage)
        result["primary_net_return"] = (
            pd.to_numeric(result["directional_return"], errors="coerce")
            - PHASE27_PRIMARY_COST_BPS / 10_000.0
        )
        result["stress_net_return"] = (
            pd.to_numeric(result["directional_return"], errors="coerce")
            - PHASE27_STRESS_COST_BPS / 10_000.0
        )
        return result

    def run(self) -> dict[str, object]:
        if PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED:
            raise Phase27ResearchError("Phase27 runner-up substitution must remain disabled")

        frame, population_report, population_report_path = self._load_development()
        boundaries = self._boundaries()
        selection_frame = _tranche(
            frame, start=boundaries.selection_start, end=boundaries.selection_end
        )
        internal_frame = _tranche(
            frame, start=boundaries.internal_start, end=boundaries.internal_end
        )
        if selection_frame.empty or internal_frame.empty:
            raise Phase27ResearchError("Phase27 selection/internal population is empty")

        prediction_artifacts: list[pd.DataFrame] = []
        signal_artifacts: list[pd.DataFrame] = []
        selection_metrics: dict[str, Phase27TrancheMetrics] = {}
        selection_check_map: dict[str, dict[str, bool]] = {}
        selection_fold_evidence: dict[str, list[dict[str, object]]] = {}

        for candidate in PHASE27_CANDIDATES:
            signals, predictions, fold_evidence = selection_oos_signals(
                selection_frame,
                candidate,
                outer_folds=PHASE27_SELECTION_FOLDS,
            )
            decorated_predictions = self._decorate_predictions(
                predictions, candidate, stage="SELECTION_OOS"
            )
            decorated_signals = self._decorate_signals(
                signals, candidate, stage="SELECTION_OOS"
            )
            prediction_artifacts.append(decorated_predictions)
            signal_artifacts.append(decorated_signals)
            trial_count = sum(
                len(item.get("tuning_trials", []))
                for item in fold_evidence
                if isinstance(item, dict)
            )
            metrics = tranche_metrics(
                decorated_signals,
                predictions=decorated_predictions,
                confidence=PHASE27_SELECTION_CONFIDENCE,
                fold_field="selection_fold",
                label=f"selection:{candidate.candidate_id}",
                tuning_trial_count=trial_count,
            )
            selection_metrics[candidate.candidate_id] = metrics
            selection_check_map[candidate.candidate_id] = selection_checks(metrics)
            selection_fold_evidence[candidate.candidate_id] = fold_evidence

        selection_metrics = _with_deflated(selection_metrics)
        p_values = {
            candidate.candidate_id: (
                selection_metrics[candidate.candidate_id].primary_bootstrap_p_value
                if selection_metrics[candidate.candidate_id].primary_bootstrap_p_value is not None
                else 1.0
            )
            for candidate in PHASE27_CANDIDATES
        }
        holm = holm_bonferroni(p_values)
        selection_survivors = {
            candidate.candidate_id
            for candidate in PHASE27_CANDIDATES
            if all(selection_check_map[candidate.candidate_id].values())
            and bool(holm[candidate.candidate_id]["rejected_null"])
        }

        candidate_index = {
            candidate.candidate_id: index for index, candidate in enumerate(PHASE27_CANDIDATES)
        }
        selection_winner_ids: list[str] = []
        for direction in ("LONG", "SHORT"):
            eligible = [
                candidate
                for candidate in PHASE27_CANDIDATES
                if candidate.direction == direction
                and candidate.candidate_id in selection_survivors
            ]
            if not eligible:
                continue
            eligible.sort(
                key=lambda candidate: _winner_sort_key(
                    candidate,
                    selection_metrics[candidate.candidate_id],
                    candidate_index,
                )
            )
            selection_winner_ids.append(eligible[0].candidate_id)

        if len(selection_winner_ids) > 2:
            raise Phase27ResearchError("Phase27 selected more than one winner per direction")

        final_selection_params: dict[str, dict[str, object]] = {}
        final_selection_tuning: dict[str, list[dict[str, object]]] = {}
        internal_metrics: dict[str, Phase27TrancheMetrics] = {}
        internal_check_map: dict[str, dict[str, bool]] = {}
        finalist_ids: list[str] = []

        for candidate_id in selection_winner_ids:
            candidate = next(
                item for item in PHASE27_CANDIDATES if item.candidate_id == candidate_id
            )
            if candidate.learned:
                params, tuning = tune_hyperparameters(selection_frame, candidate)
                model = fit_learned_model(
                    candidate_direction_frame(selection_frame, candidate),
                    candidate,
                    params,
                )
            else:
                params, tuning, model = {}, [], None
            final_selection_params[candidate_id] = dict(params)
            final_selection_tuning[candidate_id] = tuning

            internal_predictions = score_candidate(internal_frame, candidate, model=model)
            internal_predictions = _assign_fold(
                internal_predictions,
                folds=PHASE27_INTERNAL_VALIDATION_FOLDS,
                field="internal_fold",
            )
            internal_signals = select_fixed_tail(internal_predictions)
            internal_signals = _assign_fold(
                internal_signals,
                folds=PHASE27_INTERNAL_VALIDATION_FOLDS,
                field="internal_fold",
            )
            decorated_predictions = self._decorate_predictions(
                internal_predictions, candidate, stage="INTERNAL_VALIDATION"
            )
            decorated_signals = self._decorate_signals(
                internal_signals, candidate, stage="INTERNAL_VALIDATION"
            )
            prediction_artifacts.append(decorated_predictions)
            signal_artifacts.append(decorated_signals)
            metrics = tranche_metrics(
                decorated_signals,
                predictions=decorated_predictions,
                confidence=PHASE27_INTERNAL_CONFIDENCE,
                fold_field="internal_fold",
                label=f"internal:{candidate.candidate_id}",
                tuning_trial_count=len(tuning),
            )
            internal_metrics[candidate_id] = metrics
            internal_check_map[candidate_id] = internal_checks(metrics)
            if all(internal_check_map[candidate_id].values()):
                finalist_ids.append(candidate_id)

        if len(finalist_ids) > 2:
            raise Phase27ResearchError("Phase27 created more than one finalist per direction")

        all_predictions = pd.concat(prediction_artifacts, ignore_index=True, sort=False)
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

        finalist_entries = []
        for candidate_id in finalist_ids:
            candidate = next(
                item for item in PHASE27_CANDIDATES if item.candidate_id == candidate_id
            )
            finalist_entries.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "family": candidate.family,
                    "direction": candidate.direction,
                    "learned": candidate.learned,
                    "chosen_hyperparameters": final_selection_params[candidate_id],
                    "feature_fields": list(PHASE27_PREDICTOR_FIELDS),
                    "transformed_feature_fields": list(transformed_feature_names()),
                    "signal_tail_fraction": 0.20,
                    "training_end": PHASE27_DEVELOPMENT_END,
                    "development_population_sha256": sha256_file(
                        self.population.development_path()
                    ),
                }
            )
        finalists_path = self.finalists_path()
        finalist_payload: dict[str, object] = {
            "contract_version": PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "selection_winner_ids": selection_winner_ids,
            "finalist_ids": finalist_ids,
            "finalists": finalist_entries,
            "frozen": True,
            "runner_up_substitution_allowed": False,
            "protected_returns_read": 0,
            "protected_candidate_rows_read": 0,
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
            "population_report_pass": population_report.get("pass") is True,
            "protected_returns_unread": int(
                population_report.get("protected_return_reads", -1)
            )
            == 0,
            "exact_candidate_count": len(PHASE27_CANDIDATES) == 8,
            "holm_global_candidate_count": len(holm) == 8,
            "selection_winner_direction_limit": len(selection_winner_ids)
            <= 2 * PHASE27_MAX_SELECTION_WINNERS_PER_DIRECTION,
            "internal_only_selection_winners": set(internal_metrics)
            == set(selection_winner_ids),
            "finalists_subset_selection_winners": set(finalist_ids).issubset(
                set(selection_winner_ids)
            ),
            "runner_up_substitution_disabled": not PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED,
            "finalist_artifact_protected_unread": int(
                finalist_payload["protected_returns_read"]
            )
            == 0,
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase27ResearchError(
                "Phase27 development research checks failed: " + ", ".join(failed)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE27_RESEARCH_REPORT_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "population_report_sha256": sha256_file(population_report_path),
            "development_population_sha256": sha256_file(
                self.population.development_path()
            ),
            "boundaries": boundaries.to_dict(),
            "candidate_count": len(PHASE27_CANDIDATES),
            "selection_metrics": {
                key: value.to_dict() for key, value in selection_metrics.items()
            },
            "selection_checks": selection_check_map,
            "selection_fold_evidence": selection_fold_evidence,
            "holm_bonferroni": holm,
            "selection_survivor_ids": sorted(selection_survivors),
            "selection_winner_ids": selection_winner_ids,
            "final_selection_hyperparameters": final_selection_params,
            "final_selection_tuning": final_selection_tuning,
            "internal_metrics": {
                key: value.to_dict() for key, value in internal_metrics.items()
            },
            "internal_checks": internal_check_map,
            "finalist_ids": finalist_ids,
            "predictions_sha256": sha256_file(predictions_path),
            "signals_sha256": sha256_file(signals_path),
            "finalists_sha256": sha256_file(finalists_path),
            "protected_return_reads": 0,
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
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
