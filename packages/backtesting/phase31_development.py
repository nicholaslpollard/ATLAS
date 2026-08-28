from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.outcome_probe import MLOutcomeFeasibilityProbe
from packages.regimes.ticker_persistence_policy import TICKER_SELECTED_CONFIRMATION_SESSIONS

from .phase25_gate7 import Phase25Gate7RouteContextReplay, persist_exact_interval_ticker_states
from .phase25_policy import PHASE25_ROUTE_REPLAY_ORIGIN
from .phase26_observations import (
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    PHASE26_OUTCOME_EVIDENCE_END,
    Phase26ObservationBuilder,
)
from .phase31_policy import (
    PHASE31_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE31_BOOTSTRAP_REPLICATES,
    PHASE31_BOOTSTRAP_SEED,
    PHASE31_CANDIDATES,
    PHASE31_COST_GRID_BPS,
    PHASE31_DEVELOPMENT_LAST_SIGNAL,
    PHASE31_INTERNAL_CONFIDENCE,
    PHASE31_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE31_INTERNAL_MIN_RAW_ROWS,
    PHASE31_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE31_INTERNAL_MIN_UNIQUE_TICKERS,
    PHASE31_INTERNAL_PURGE_SESSIONS,
    PHASE31_INTERNAL_VALIDATION_FOLDS,
    PHASE31_MAX_SELECTION_WINNERS_PER_DIRECTION,
    PHASE31_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE31_MAX_SINGLE_TICKER_ROW_FRACTION,
    PHASE31_MIN_POSITIVE_REGIME_FRACTION,
    PHASE31_MIN_POSITIVE_YEAR_FRACTION,
    PHASE31_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE31_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE31_MULTIPLE_TESTING_ALPHA,
    PHASE31_MULTIPLE_TESTING_METHOD,
    PHASE31_OUTCOME_HORIZON_SESSIONS,
    PHASE31_PRIMARY_COST_BPS,
    PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE31_PROTECTED_START,
    PHASE31_RESEARCH_SIGNAL_START,
    PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE31_SELECTION_CONFIDENCE,
    PHASE31_SELECTION_FOLDS,
    PHASE31_SELECTION_FRACTION,
    PHASE31_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE31_SELECTION_MIN_RAW_ROWS,
    PHASE31_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE31_SELECTION_MIN_UNIQUE_TICKERS,
    PHASE31_SELECTION_WINNER_RULE,
    PHASE31_STRESS_COST_BPS,
    Phase31CandidateSpec,
    phase31_policy_fingerprint,
)
from .phase31_predictor_evidence import (
    PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS,
    PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
    PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
    validate_phase31_predictor_report,
)
from .phase31_predictors import (
    PHASE31_DEVELOPMENT_PREDICTOR_CONTRACT_VERSION,
    PHASE31_FORBIDDEN_MARKET_FIELDS,
    PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION,
    Phase31Form4PredictorBuilder,
)

PHASE31_DEVELOPMENT_STUDY_CONTRACT_VERSION = "phase31-development-study-v1-open-t20-spy-relative-four-hypothesis-protected-blind"
PHASE31_DEVELOPMENT_OUTCOME_CONTRACT_VERSION = "phase31-development-outcome-v1-exact-open-t20-close-spy-relative-split-censored"
PHASE31_DEVELOPMENT_SIGNAL_CONTRACT_VERSION = "phase31-development-signal-v1-frozen-form4-membership"
PHASE31_FINALIST_ARTIFACT_CONTRACT_VERSION = "phase31-finalists-v1-selection-internal-protected-unread"
PHASE31_DEVELOPMENT_BOUNDARY_EXIT = date(2026, 5, 11)


class Phase31DevelopmentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase31DevelopmentBoundaries:
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
            "purge_sessions": [x.isoformat() for x in self.purge_sessions],
            "internal_start": self.internal_start.isoformat(),
            "internal_end": self.internal_end.isoformat(),
            "development_session_count": self.development_session_count,
            "selection_session_count": self.selection_session_count,
            "internal_session_count": self.internal_session_count,
        }


@dataclass(frozen=True, slots=True)
class Phase31TrancheMetrics:
    raw_rows: int
    signal_sessions: int
    unique_tickers: int
    cost_mean_returns: dict[str, float]
    primary_mean_return: float | None
    unhedged_primary_mean_return: float | None
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
    deflated_sharpe_probability: float | None = None
    deflated_sharpe_benchmark: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def chronological_boundaries(sessions: Iterable[date]) -> Phase31DevelopmentBoundaries:
    ordered = tuple(sorted(set(sessions)))
    if len(ordered) < 40:
        raise Phase31DevelopmentError("too few frozen Phase31 development sessions")
    selection_count = int(math.floor(len(ordered) * PHASE31_SELECTION_FRACTION))
    internal_offset = selection_count + PHASE31_INTERNAL_PURGE_SESSIONS
    if selection_count <= 0 or internal_offset >= len(ordered):
        raise Phase31DevelopmentError("invalid Phase31 development split")
    selection = ordered[:selection_count]
    purge = ordered[selection_count:internal_offset]
    internal = ordered[internal_offset:]
    if len(purge) != PHASE31_INTERNAL_PURGE_SESSIONS or not internal:
        raise Phase31DevelopmentError("Phase31 selection/internal purge partition is incomplete")
    return Phase31DevelopmentBoundaries(selection[0], selection[-1], tuple(purge), internal[0], internal[-1], len(ordered), len(selection), len(internal))


def _derived_seed(label: str) -> int:
    return PHASE31_BOOTSTRAP_SEED + int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def _bootstrap(values: np.ndarray, *, confidence: float, label: str) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise Phase31DevelopmentError("bootstrap requires a nonempty session vector")
    n = len(values)
    block = min(PHASE31_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE31_BOOTSTRAP_REPLICATES, block_count))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(PHASE31_BOOTSTRAP_REPLICATES, -1)[:, :n]
    sample_means = values[indices].mean(axis=1)
    lower = float(np.quantile(sample_means, 1.0 - confidence))
    observed = float(values.mean())
    null_means = (values - observed)[indices].mean(axis=1)
    p_value = float((1 + np.count_nonzero(null_means >= observed)) / (len(null_means) + 1))
    return lower, p_value


def _fraction_positive(values: Mapping[str, float]) -> float | None:
    return None if not values else float(sum(v > 0 for v in values.values()) / len(values))


def _fold_mapping(sessions: tuple[date, ...], folds: int) -> dict[date, int]:
    if len(sessions) < folds:
        raise Phase31DevelopmentError("too few Phase31 sessions for fold attribution")
    blocks = [tuple(block.tolist()) for block in np.array_split(np.asarray(sessions, dtype=object), folds)]
    return {session: index for index, block in enumerate(blocks) for session in block}


def _assign_fold(frame: pd.DataFrame, *, mapping: Mapping[date, int], field: str) -> pd.DataFrame:
    result = frame.copy()
    result["decision_session"] = pd.to_datetime(result["decision_session"]).dt.date
    if result.empty:
        result[field] = pd.Series(dtype="int64")
        return result
    result[field] = result["decision_session"].map(mapping)
    if result[field].isna().any():
        raise Phase31DevelopmentError("Phase31 fold attribution is incomplete")
    result[field] = result[field].astype(int)
    return result


def holm_bonferroni(p_values: Mapping[str, float], *, alpha: float = PHASE31_MULTIPLE_TESTING_ALPHA) -> dict[str, dict[str, object]]:
    ordered = sorted((float(value), str(key)) for key, value in p_values.items())
    result: dict[str, dict[str, object]] = {}
    active = True
    total = len(ordered)
    for index, (p_value, key) in enumerate(ordered):
        threshold = alpha / (total - index) if total else 0.0
        reject = bool(active and p_value <= threshold)
        result[key] = {"p_value": p_value, "threshold": threshold, "rejected_null": reject}
        if not reject:
            active = False
    return result


def _eligible_state_means(data: pd.DataFrame, *, state_field: str, primary_cost: float) -> dict[str, float]:
    subset = data.loc[data[state_field].notna(), ["decision_session", state_field, "primary_gross_return"]].copy()
    if subset.empty:
        return {}
    subset[state_field] = subset[state_field].astype(str)
    grouped = subset.groupby([state_field, "decision_session"], sort=True, observed=True)["primary_gross_return"].mean().reset_index()
    result: dict[str, float] = {}
    for state, state_rows in grouped.groupby(state_field, sort=True, observed=True):
        if state_rows["decision_session"].nunique() >= PHASE31_MIN_REGIME_SIGNAL_SESSIONS:
            result[str(state)] = float(pd.to_numeric(state_rows["primary_gross_return"], errors="coerce").mean() - primary_cost)
    return result


def _fold_economic_means(session: pd.DataFrame, signals: pd.DataFrame, *, fold_field: str, primary_cost: float) -> tuple[float, ...]:
    if signals.empty or fold_field not in signals.columns:
        return ()
    mapping = signals[["decision_session", fold_field]].drop_duplicates()
    if mapping.duplicated(["decision_session"], keep=False).any():
        raise Phase31DevelopmentError("Phase31 signal session belongs to multiple folds")
    merged = session.merge(mapping, on="decision_session", how="left", validate="one_to_one")
    if merged[fold_field].isna().any():
        raise Phase31DevelopmentError("Phase31 signal session is missing fold attribution")
    return tuple(float(group["primary_gross_return"].mean() - primary_cost) for _, group in merged.groupby(fold_field, sort=True, observed=True))


def tranche_metrics(signals: pd.DataFrame, *, confidence: float, fold_field: str, label: str) -> Phase31TrancheMetrics:
    if signals.empty:
        return Phase31TrancheMetrics(0, 0, 0, {}, None, None, None, None, None, None, None, None, None, None, (), 0, {}, None, {}, None, {}, None, None)
    data = signals.copy()
    data["decision_session"] = pd.to_datetime(data["decision_session"]).dt.date
    for field in ("primary_gross_return", "unhedged_gross_return"):
        data[field] = pd.to_numeric(data[field], errors="coerce")
    finite = np.isfinite(data["primary_gross_return"].to_numpy(dtype=float)) & np.isfinite(data["unhedged_gross_return"].to_numpy(dtype=float))
    data = data.loc[finite].copy()
    if data.empty:
        return tranche_metrics(data, confidence=confidence, fold_field=fold_field, label=label)
    primary_cost = PHASE31_PRIMARY_COST_BPS / 10_000.0
    stress_cost = PHASE31_STRESS_COST_BPS / 10_000.0
    session = data.groupby("decision_session", sort=True, observed=True).agg(
        primary_gross_return=("primary_gross_return", "mean"),
        unhedged_gross_return=("unhedged_gross_return", "mean"),
        row_count=("ticker", "size"),
    ).reset_index().sort_values("decision_session", kind="stable")
    gross = session["primary_gross_return"].to_numpy(dtype=float)
    primary = gross - primary_cost
    unhedged = session["unhedged_gross_return"].to_numpy(dtype=float) - primary_cost
    stress = gross - stress_cost
    lower, p_value = _bootstrap(primary, confidence=confidence, label=label)
    fold_values = _fold_economic_means(session, data, fold_field=fold_field, primary_cost=primary_cost)
    year_values: dict[int, list[float]] = defaultdict(list)
    for session_date, value in zip(session["decision_session"], primary, strict=True):
        year_values[session_date.year].append(float(value))
    year_means = {str(year): float(np.mean(values)) for year, values in sorted(year_values.items()) if len(values) >= PHASE31_MIN_YEAR_SIGNAL_SESSIONS}
    market_means = _eligible_state_means(data, state_field="prior_market_state", primary_cost=primary_cost)
    ticker_means = _eligible_state_means(data, state_field="prior_ticker_state", primary_cost=primary_cost)
    cost_means = {f"{float(cost):g}": float(np.mean(gross - float(cost) / 10_000.0)) for cost in PHASE31_COST_GRID_BPS}
    trade_primary = data["primary_gross_return"].to_numpy(dtype=float) - primary_cost
    primary_std = float(np.std(primary, ddof=1)) if len(primary) > 1 else 0.0
    session_sharpe = None if primary_std <= 0 else float(np.mean(primary) / primary_std)
    raw_rows = int(len(data))
    ticker_counts = data.groupby("ticker", sort=True, observed=True).size()
    max_ticker_fraction = None if ticker_counts.empty else float(ticker_counts.max() / raw_rows)
    return Phase31TrancheMetrics(
        raw_rows, int(len(session)), int(data["ticker"].nunique()), cost_means,
        float(np.mean(primary)), float(np.mean(unhedged)), float(np.median(trade_primary)),
        float(np.mean(trade_primary > 0)), float(np.mean(primary > 0)), lower, p_value,
        float(np.mean(stress)), float(session["row_count"].max() / raw_rows), max_ticker_fraction,
        fold_values, sum(value > 0 for value in fold_values), year_means, _fraction_positive(year_means),
        market_means, _fraction_positive(market_means), ticker_means, _fraction_positive(ticker_means), session_sharpe,
    )


def _with_deflated(metrics: dict[str, Phase31TrancheMetrics], *, reference_metrics: Mapping[str, Phase31TrancheMetrics] | None = None) -> dict[str, Phase31TrancheMetrics]:
    reference = reference_metrics if reference_metrics is not None else metrics
    sharpes = np.asarray([item.session_sharpe for item in reference.values() if item.session_sharpe is not None], dtype=float)
    if len(sharpes) < 2 or float(np.std(sharpes, ddof=1)) <= 0:
        return metrics
    sigma = float(np.std(sharpes, ddof=1))
    trials = max(2, len(reference))
    normal = NormalDist()
    gamma = 0.5772156649015329
    benchmark = sigma * ((1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / trials) + gamma * normal.inv_cdf(1.0 - 1.0 / (trials * math.e)))
    result: dict[str, Phase31TrancheMetrics] = {}
    for key, item in metrics.items():
        probability = None
        if item.session_sharpe is not None and item.signal_sessions >= 3:
            denominator = math.sqrt(max(1e-12, 1.0 + 0.5 * item.session_sharpe**2))
            z = (item.session_sharpe - benchmark) * math.sqrt(item.signal_sessions - 1) / denominator
            probability = float(normal.cdf(z))
        result[key] = Phase31TrancheMetrics(**{**item.to_dict(), "deflated_sharpe_probability": probability, "deflated_sharpe_benchmark": float(benchmark)})
    return result


def _stage_checks(metrics: Phase31TrancheMetrics, *, min_raw_rows: int, min_signal_sessions: int, min_unique_tickers: int, min_positive_folds: int) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= min_raw_rows,
        "min_signal_sessions": metrics.signal_sessions >= min_signal_sessions,
        "min_unique_tickers": metrics.unique_tickers >= min_unique_tickers,
        "positive_folds": metrics.positive_folds >= min_positive_folds,
        "primary_mean_positive": bool(metrics.primary_mean_return is not None and metrics.primary_mean_return > 0),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(metrics.stress_mean_return is not None and metrics.stress_mean_return > 0),
        "unhedged_primary_mean_positive": bool(metrics.unhedged_primary_mean_return is not None and metrics.unhedged_primary_mean_return > 0),
        "year_robustness": bool(metrics.positive_year_fraction is not None and metrics.positive_year_fraction >= PHASE31_MIN_POSITIVE_YEAR_FRACTION),
        "market_state_robustness": bool(metrics.positive_market_state_fraction is not None and metrics.positive_market_state_fraction >= PHASE31_MIN_POSITIVE_REGIME_FRACTION),
        "ticker_state_robustness": bool(metrics.positive_ticker_state_fraction is not None and metrics.positive_ticker_state_fraction >= PHASE31_MIN_POSITIVE_REGIME_FRACTION),
        "session_concentration": bool(metrics.max_single_session_row_fraction is not None and metrics.max_single_session_row_fraction <= PHASE31_MAX_SINGLE_SESSION_ROW_FRACTION),
        "ticker_concentration": bool(metrics.max_single_ticker_row_fraction is not None and metrics.max_single_ticker_row_fraction <= PHASE31_MAX_SINGLE_TICKER_ROW_FRACTION),
    }


def selection_checks(metrics: Phase31TrancheMetrics) -> dict[str, bool]:
    return _stage_checks(metrics, min_raw_rows=PHASE31_SELECTION_MIN_RAW_ROWS, min_signal_sessions=PHASE31_SELECTION_MIN_SIGNAL_SESSIONS, min_unique_tickers=PHASE31_SELECTION_MIN_UNIQUE_TICKERS, min_positive_folds=PHASE31_SELECTION_MIN_POSITIVE_FOLDS)


def internal_checks(metrics: Phase31TrancheMetrics) -> dict[str, bool]:
    return _stage_checks(metrics, min_raw_rows=PHASE31_INTERNAL_MIN_RAW_ROWS, min_signal_sessions=PHASE31_INTERNAL_MIN_SIGNAL_SESSIONS, min_unique_tickers=PHASE31_INTERNAL_MIN_UNIQUE_TICKERS, min_positive_folds=PHASE31_INTERNAL_MIN_POSITIVE_FOLDS)


def candidate_view(frame: pd.DataFrame, candidate: Phase31CandidateSpec) -> pd.DataFrame:
    if candidate.requires_cluster:
        mask = frame["cluster_candidate_id"].astype("string").eq(candidate.candidate_id)
    else:
        mask = frame["broad_candidate_id"].astype("string").eq(candidate.candidate_id)
    result = frame.loc[mask.fillna(False)].copy()
    if not result.empty and set(result["direction"].astype(str)) != {candidate.direction}:
        raise Phase31DevelopmentError(f"Phase31 candidate direction drifted: {candidate.candidate_id}")
    return result


def apply_return_geometry(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for field in ("entry_open", "exit_close", "spy_entry_open", "spy_exit_close"):
        result[field] = pd.to_numeric(result[field], errors="coerce")
        values = result[field].to_numpy(dtype=float)
        if not np.isfinite(values).all() or bool((values <= 0).any()):
            raise Phase31DevelopmentError(f"Phase31 return geometry requires finite positive {field}")
    result["stock_return"] = result["exit_close"] / result["entry_open"] - 1.0
    result["spy_return"] = result["spy_exit_close"] / result["spy_entry_open"] - 1.0
    direction = np.where(result["direction"].astype(str).eq("LONG"), 1.0, -1.0)
    result["primary_gross_return"] = direction * (result["stock_return"] - result["spy_return"])
    result["unhedged_gross_return"] = direction * result["stock_return"]
    for field in ("stock_return", "spy_return", "primary_gross_return", "unhedged_gross_return"):
        if not np.isfinite(result[field].to_numpy(dtype=float)).all():
            raise Phase31DevelopmentError(f"Phase31 development contains nonfinite {field}")
    return result


def _write_parquet(settings: AtlasSettings, frame: pd.DataFrame, target: Path, *, order_by: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase31_development_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(f"COPY (SELECT * FROM phase31_development_write ORDER BY {order_by}) TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})")
        promote(temp, target)
    finally:
        con.close()


class Phase31DevelopmentStudy:
    """First Phase31 stage allowed to read development outcomes, never protected ones."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.predictors = Phase31Form4PredictorBuilder(settings)
        self.phase26 = Phase26ObservationBuilder(settings)
        self.gate7 = Phase25Gate7RouteContextReplay(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase31" / "v1" / "development"

    def outcomes_path(self) -> Path:
        return self.root / "development_outcomes.parquet"

    def signals_path(self) -> Path:
        return self.root / "development_signals.parquet"

    def finalists_path(self) -> Path:
        return self.root / "finalists.json"

    def report_path(self) -> Path:
        return self.root / "development_study.json"

    @staticmethod
    def _read_json(path: Path, *, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise Phase31DevelopmentError(f"missing {label}: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Phase31DevelopmentError(f"invalid {label}: {path}") from exc
        if not isinstance(payload, dict):
            raise Phase31DevelopmentError(f"{label} must be a JSON object")
        return payload

    def _load_development_predictors(self) -> tuple[pd.DataFrame, dict[str, Any]]:
        report = self._read_json(self.predictors.report_path(), label="Phase31 predictor report")
        if report.get("contract_version") != PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION:
            raise Phase31DevelopmentError("Phase31 predictor report contract mismatch")
        try:
            validate_phase31_predictor_report(report)
        except ValueError as exc:
            raise Phase31DevelopmentError(str(exc)) from exc
        if report.get("phase31_policy_fingerprint") != phase31_policy_fingerprint():
            raise Phase31DevelopmentError("Phase31 predictor policy fingerprint mismatch")
        development_path = self.predictors.development_path()
        protected_path = self.predictors.protected_path()
        if not development_path.is_file() or sha256_file(development_path) != PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256:
            raise Phase31DevelopmentError("Phase31 frozen development predictor SHA mismatch")
        if not protected_path.is_file() or sha256_file(protected_path) != PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256:
            raise Phase31DevelopmentError("Phase31 frozen protected predictor SHA mismatch")
        con = connect_utc(":memory:")
        try:
            frame = con.execute(f"SELECT * FROM read_parquet({sql_string(development_path)}) ORDER BY decision_session, ticker").fetch_df()
        finally:
            con.close()
        if len(frame) != PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS:
            raise Phase31DevelopmentError("Phase31 frozen development predictor row count drifted")
        if set(frame["contract_version"].astype(str)) != {PHASE31_DEVELOPMENT_PREDICTOR_CONTRACT_VERSION}:
            raise Phase31DevelopmentError("Phase31 development predictor row contract mismatch")
        if set(frame["phase31_policy_fingerprint"].astype(str)) != {phase31_policy_fingerprint()}:
            raise Phase31DevelopmentError("Phase31 development predictor row policy mismatch")
        forbidden = [field for field in PHASE31_FORBIDDEN_MARKET_FIELDS if field in frame.columns]
        if forbidden:
            raise Phase31DevelopmentError("Phase31 development predictor unexpectedly contains market outcomes: " + ", ".join(forbidden))
        frame["decision_session"] = pd.to_datetime(frame["decision_session"]).dt.date
        frame["exit_session"] = pd.to_datetime(frame["exit_session"]).dt.date
        if frame.duplicated(["ticker", "decision_session"], keep=False).any():
            raise Phase31DevelopmentError("Phase31 development predictors duplicate ticker/session")
        if frame["decision_session"].max() > date.fromisoformat(PHASE31_DEVELOPMENT_LAST_SIGNAL):
            raise Phase31DevelopmentError("Phase31 development predictor crossed signal boundary")
        if frame["exit_session"].max() >= date.fromisoformat(PHASE31_PROTECTED_START):
            raise Phase31DevelopmentError("Phase31 development predictor exit crossed protected start")
        return frame, report

    def _split_evidence(self) -> tuple[pd.DataFrame, str]:
        report = self._read_json(self.phase26.report_path(), label="accepted Phase26 observation report")
        if report.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION or report.get("pass") is not True:
            raise Phase31DevelopmentError("Phase26 observation evidence is not accepted")
        if int(report.get("protected_return_reads", -1)) != 0:
            raise Phase31DevelopmentError("accepted split lineage is attached to consumed protected returns")
        path = MLOutcomeFeasibilityProbe(self.settings).split_evidence_path(PHASE26_OUTCOME_EVIDENCE_END)
        expected_sha = str(report.get("split_evidence_sha256") or "")
        if not path.is_file() or len(expected_sha) != 64 or sha256_file(path) != expected_sha:
            raise Phase31DevelopmentError("accepted split evidence SHA mismatch")
        records: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    continue
                ticker = str(payload.get("ticker") or "").strip()
                raw_date = str(payload.get("execution_date") or "").strip()
                if not ticker or not raw_date:
                    continue
                try:
                    execution_date = date.fromisoformat(raw_date)
                except ValueError:
                    continue
                records.append({"ticker": ticker, "execution_date": execution_date})
        return pd.DataFrame.from_records(records, columns=["ticker", "execution_date"]), expected_sha

    def _development_outcomes(self, predictors: pd.DataFrame, splits: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        con = connect_utc(":memory:")
        try:
            con.execute("SET preserve_insertion_order=false")
            con.register("p31_predictors", predictors)
            con.register("p31_splits", splits)
            result = con.execute(f"""
                WITH needed AS (
                    SELECT ticker AS symbol, CAST(decision_session AS DATE) AS session_date FROM p31_predictors
                    UNION SELECT ticker, CAST(exit_session AS DATE) FROM p31_predictors
                    UNION SELECT 'SPY', CAST(decision_session AS DATE) FROM p31_predictors
                    UNION SELECT 'SPY', CAST(exit_session AS DATE) FROM p31_predictors
                ), bars AS (
                    SELECT b.symbol, CAST(b.session_date AS DATE) AS session_date,
                           CAST(b.open AS DOUBLE) AS session_open, CAST(b.close AS DOUBLE) AS session_close
                    FROM read_parquet({sql_string(bar_glob)}, union_by_name=true, hive_partitioning=false) b
                    INNER JOIN needed n ON n.symbol = b.symbol AND n.session_date = CAST(b.session_date AS DATE)
                )
                SELECT p.*, se.session_open AS entry_open, sx.session_close AS exit_close,
                       pe.session_open AS spy_entry_open, px.session_close AS spy_exit_close,
                       EXISTS (SELECT 1 FROM p31_splits s WHERE s.ticker = p.ticker
                               AND CAST(s.execution_date AS DATE) > CAST(p.decision_session AS DATE)
                               AND CAST(s.execution_date AS DATE) <= CAST(p.exit_session AS DATE)) AS split_crossing
                FROM p31_predictors p
                LEFT JOIN bars se ON se.symbol = p.ticker AND se.session_date = CAST(p.decision_session AS DATE)
                LEFT JOIN bars sx ON sx.symbol = p.ticker AND sx.session_date = CAST(p.exit_session AS DATE)
                LEFT JOIN bars pe ON pe.symbol = 'SPY' AND pe.session_date = CAST(p.decision_session AS DATE)
                LEFT JOIN bars px ON px.symbol = 'SPY' AND px.session_date = CAST(p.exit_session AS DATE)
                ORDER BY p.decision_session, p.ticker
            """).fetch_df()
        finally:
            con.close()
        if len(result) != len(predictors):
            raise Phase31DevelopmentError("Phase31 exact outcome join cardinality drifted; duplicate/missing daily keys suspected")
        result["decision_session"] = pd.to_datetime(result["decision_session"]).dt.date
        result["exit_session"] = pd.to_datetime(result["exit_session"]).dt.date
        for field in ("entry_open", "exit_close", "spy_entry_open", "spy_exit_close"):
            result[field] = pd.to_numeric(result[field], errors="coerce")
        spy_missing = result["spy_entry_open"].isna() | result["spy_exit_close"].isna() | ~np.isfinite(result["spy_entry_open"].to_numpy(dtype=float)) | ~np.isfinite(result["spy_exit_close"].to_numpy(dtype=float)) | result["spy_entry_open"].le(0) | result["spy_exit_close"].le(0)
        if bool(spy_missing.any()):
            raise Phase31DevelopmentError("Phase31 SPY benchmark is missing an exact frozen entry/exit session")
        stock_missing = result["entry_open"].isna() | result["exit_close"].isna() | ~np.isfinite(result["entry_open"].to_numpy(dtype=float)) | ~np.isfinite(result["exit_close"].to_numpy(dtype=float)) | result["entry_open"].le(0) | result["exit_close"].le(0)
        split_crossing = result["split_crossing"].fillna(False).astype(bool)
        usable = result.loc[~stock_missing & ~split_crossing].copy()
        if usable.empty:
            raise Phase31DevelopmentError("Phase31 development outcomes are empty after path-quality censoring")
        usable = apply_return_geometry(usable)
        usable.insert(0, "outcome_contract_version", PHASE31_DEVELOPMENT_OUTCOME_CONTRACT_VERSION)
        usable = usable.drop(columns=["split_crossing"])
        return usable, {
            "exact_stock_path_missing_rows": int(stock_missing.sum()),
            "split_crossing_censored_rows": int(split_crossing.sum()),
            "usable_development_rows": int(len(usable)),
        }

    def _prior_regime_states(self, predictors: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        research_start = date.fromisoformat(PHASE31_RESEARCH_SIGNAL_START)
        development_last = date.fromisoformat(PHASE31_DEVELOPMENT_LAST_SIGNAL)
        prior_grid = tuple(self.calendar.sessions_in_range(research_start - timedelta(days=10), development_last))
        previous = {prior_grid[i]: prior_grid[i - 1] for i in range(1, len(prior_grid))}
        result = predictors.copy()
        result["prior_state_session"] = result["decision_session"].map(previous)
        if result["prior_state_session"].isna().any():
            raise Phase31DevelopmentError("Phase31 previous-session mapping is incomplete")
        if not all(prior < decision for prior, decision in zip(result["prior_state_session"], result["decision_session"], strict=True)):
            raise Phase31DevelopmentError("Phase31 regime state timing is not prior-session-only")
        market = self.gate7._market_states(development_last).rename(columns={"trading_date": "prior_state_session", "market_state": "prior_market_state"})
        result = result.merge(market[["prior_state_session", "prior_market_state"]], on="prior_state_session", how="left", validate="many_to_one")
        if result["prior_market_state"].isna().any():
            raise Phase31DevelopmentError("Phase31 accepted prior-session market state is incomplete")
        ticker_sessions = tuple(self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, development_last))
        session_ordinals = {session: index for index, session in enumerate(ticker_sessions)}
        pairs = result[["instrument_id", "ticker"]].drop_duplicates().copy()
        intervals = self.gate7._exact_intervals(population=pairs, sessions=ticker_sessions)
        raw = self.gate7._raw_ticker_state_history(intervals)
        persisted = persist_exact_interval_ticker_states(raw, session_ordinals=session_ordinals)
        if TICKER_SELECTED_CONFIRMATION_SESSIONS != 2:
            raise Phase31DevelopmentError("accepted ticker persistence policy drifted")
        if persisted.empty:
            states = pd.DataFrame(columns=["instrument_id", "ticker", "prior_state_session", "prior_ticker_state"])
        else:
            persisted["trading_date"] = pd.to_datetime(persisted["trading_date"]).dt.date
            states = persisted[["instrument_id", "ticker", "trading_date", "effective_ticker_state"]].rename(columns={"trading_date": "prior_state_session", "effective_ticker_state": "prior_ticker_state"})
            if states.duplicated(["instrument_id", "ticker", "prior_state_session"], keep=False).any():
                raise Phase31DevelopmentError("Phase31 reconstructed prior ticker state is not unique")
        result = result.merge(states, on=["instrument_id", "ticker", "prior_state_session"], how="left", validate="many_to_one")
        return result, {
            "prior_market_state_missing_rows": int(result["prior_market_state"].isna().sum()),
            "prior_ticker_state_missing_rows": int(result["prior_ticker_state"].isna().sum()),
            "ticker_regime_interval_count": int(len(intervals)),
            "ticker_regime_raw_rows": int(len(raw)),
            "ticker_regime_persisted_rows": int(len(persisted)),
        }

    def _boundaries(self) -> Phase31DevelopmentBoundaries:
        start = date.fromisoformat(PHASE31_RESEARCH_SIGNAL_START)
        end = date.fromisoformat(PHASE31_DEVELOPMENT_LAST_SIGNAL)
        sessions = tuple(self.calendar.sessions_in_range(start, end))
        if not sessions or sessions[0] != start or sessions[-1] != end:
            raise Phase31DevelopmentError("Phase31 frozen development calendar scope mismatch")
        return chronological_boundaries(sessions)

    def _validate_outer_boundary(self) -> None:
        development_last = date.fromisoformat(PHASE31_DEVELOPMENT_LAST_SIGNAL)
        extended = tuple(self.calendar.sessions_in_range(development_last, PHASE31_DEVELOPMENT_BOUNDARY_EXIT))
        if len(extended) != PHASE31_OUTCOME_HORIZON_SESSIONS + 1 or extended[0] != development_last or extended[-1] != PHASE31_DEVELOPMENT_BOUNDARY_EXIT:
            raise Phase31DevelopmentError("Phase31 frozen outer development t+20 boundary drifted")

    @staticmethod
    def _decorate(frame: pd.DataFrame, candidate: Phase31CandidateSpec, *, stage: str, fold_field: str) -> pd.DataFrame:
        result = frame.copy()
        result.insert(0, "signal_contract_version", PHASE31_DEVELOPMENT_SIGNAL_CONTRACT_VERSION)
        result.insert(1, "candidate_id", candidate.candidate_id)
        result.insert(2, "candidate_family", candidate.family)
        result.insert(3, "strategy_direction", candidate.direction)
        result.insert(4, "research_stage", stage)
        if fold_field not in result.columns:
            raise Phase31DevelopmentError("Phase31 decorated signal is missing fold")
        return result

    def run(self) -> dict[str, object]:
        if phase31_policy_fingerprint() != "e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67":
            raise Phase31DevelopmentError("Phase31 scientific policy fingerprint drifted")
        if len(PHASE31_CANDIDATES) != 4 or PHASE31_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_4":
            raise Phase31DevelopmentError("Phase31 frozen global hypothesis family drifted")
        if PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED or PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED:
            raise Phase31DevelopmentError("Phase31 forbidden fallback/protected authority is enabled")
        if PHASE31_SELECTION_WINNER_RULE != "highest_primary_selection_LCB_then_candidate_id":
            raise Phase31DevelopmentError("Phase31 selection winner rule drifted")
        self._validate_outer_boundary()
        predictors, predictor_report = self._load_development_predictors()
        splits, split_sha = self._split_evidence()
        states, state_diagnostics = self._prior_regime_states(predictors)
        outcomes, outcome_exclusions = self._development_outcomes(states, splits)
        boundaries = self._boundaries()
        selection_frame = outcomes.loc[(outcomes["decision_session"] >= boundaries.selection_start) & (outcomes["decision_session"] <= boundaries.selection_end)].copy()
        internal_frame = outcomes.loc[(outcomes["decision_session"] >= boundaries.internal_start) & (outcomes["decision_session"] <= boundaries.internal_end)].copy()
        if selection_frame.empty or internal_frame.empty:
            raise Phase31DevelopmentError("Phase31 outcome population does not cover both development tranches")
        purge_set = set(boundaries.purge_sessions)
        if selection_frame["decision_session"].isin(purge_set).any() or internal_frame["decision_session"].isin(purge_set).any():
            raise Phase31DevelopmentError("Phase31 purge sessions leaked into research tranches")
        selection_sessions = tuple(self.calendar.sessions_in_range(boundaries.selection_start, boundaries.selection_end))
        internal_sessions = tuple(self.calendar.sessions_in_range(boundaries.internal_start, boundaries.internal_end))
        selection_fold_map = _fold_mapping(selection_sessions, PHASE31_SELECTION_FOLDS)
        internal_fold_map = _fold_mapping(internal_sessions, PHASE31_INTERNAL_VALIDATION_FOLDS)
        signal_artifacts: list[pd.DataFrame] = []
        selection_metrics: dict[str, Phase31TrancheMetrics] = {}
        selection_check_map: dict[str, dict[str, bool]] = {}
        for candidate in PHASE31_CANDIDATES:
            signals = _assign_fold(candidate_view(selection_frame, candidate), mapping=selection_fold_map, field="selection_fold")
            decorated = self._decorate(signals, candidate, stage="SELECTION", fold_field="selection_fold")
            signal_artifacts.append(decorated)
            metrics = tranche_metrics(decorated, confidence=PHASE31_SELECTION_CONFIDENCE, fold_field="selection_fold", label=f"selection:{candidate.candidate_id}")
            selection_metrics[candidate.candidate_id] = metrics
            selection_check_map[candidate.candidate_id] = selection_checks(metrics)
        selection_metrics = _with_deflated(selection_metrics)
        p_values = {candidate.candidate_id: (selection_metrics[candidate.candidate_id].primary_bootstrap_p_value if selection_metrics[candidate.candidate_id].primary_bootstrap_p_value is not None else 1.0) for candidate in PHASE31_CANDIDATES}
        holm = holm_bonferroni(p_values)
        if set(holm) != {candidate.candidate_id for candidate in PHASE31_CANDIDATES}:
            raise Phase31DevelopmentError("Phase31 Holm family is incomplete")
        survivor_ids = {candidate.candidate_id for candidate in PHASE31_CANDIDATES if all(selection_check_map[candidate.candidate_id].values()) and bool(holm[candidate.candidate_id]["rejected_null"])}
        winner_ids: list[str] = []
        for direction in ("LONG", "SHORT"):
            eligible = [candidate for candidate in PHASE31_CANDIDATES if candidate.direction == direction and candidate.candidate_id in survivor_ids]
            eligible.sort(key=lambda candidate: (-float(selection_metrics[candidate.candidate_id].primary_lcb if selection_metrics[candidate.candidate_id].primary_lcb is not None else -math.inf), candidate.candidate_id))
            if eligible:
                winner_ids.append(eligible[0].candidate_id)
        if len(winner_ids) > 2 * PHASE31_MAX_SELECTION_WINNERS_PER_DIRECTION:
            raise Phase31DevelopmentError("Phase31 selected more than one winner per direction")
        internal_metrics: dict[str, Phase31TrancheMetrics] = {}
        internal_check_map: dict[str, dict[str, bool]] = {}
        finalist_ids: list[str] = []
        for candidate_id in winner_ids:
            candidate = next(item for item in PHASE31_CANDIDATES if item.candidate_id == candidate_id)
            signals = _assign_fold(candidate_view(internal_frame, candidate), mapping=internal_fold_map, field="internal_fold")
            decorated = self._decorate(signals, candidate, stage="INTERNAL_VALIDATION", fold_field="internal_fold")
            signal_artifacts.append(decorated)
            metrics = tranche_metrics(decorated, confidence=PHASE31_INTERNAL_CONFIDENCE, fold_field="internal_fold", label=f"internal:{candidate.candidate_id}")
            internal_metrics[candidate_id] = metrics
            internal_check_map[candidate_id] = internal_checks(metrics)
            if all(internal_check_map[candidate_id].values()):
                finalist_ids.append(candidate_id)
        internal_metrics = _with_deflated(internal_metrics, reference_metrics=selection_metrics)
        selection_deflated_complete = all(item.raw_rows == 0 or item.deflated_sharpe_probability is not None for item in selection_metrics.values())
        internal_deflated_complete = all(item.raw_rows == 0 or item.deflated_sharpe_probability is not None for item in internal_metrics.values())
        finalist_directions = [next(item.direction for item in PHASE31_CANDIDATES if item.candidate_id == candidate_id) for candidate_id in finalist_ids]
        if len(finalist_directions) != len(set(finalist_directions)):
            raise Phase31DevelopmentError("Phase31 created more than one finalist in a direction")
        outcomes_path = self.outcomes_path()
        signals_path = self.signals_path()
        _write_parquet(self.settings, outcomes, outcomes_path, order_by="decision_session, ticker")
        all_signals = pd.concat(signal_artifacts, ignore_index=True, sort=False) if signal_artifacts else outcomes.iloc[0:0].copy()
        _write_parquet(self.settings, all_signals, signals_path, order_by="research_stage, candidate_id, decision_session, ticker")
        finalists = []
        for candidate_id in finalist_ids:
            candidate = next(item for item in PHASE31_CANDIDATES if item.candidate_id == candidate_id)
            finalists.append({
                "candidate_id": candidate.candidate_id,
                "family": candidate.family,
                "direction": candidate.direction,
                "requires_cluster": candidate.requires_cluster,
                "development_predictor_sha256": PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
                "protected_predictor_sha256": PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
                "development_outcomes_sha256": sha256_file(outcomes_path),
            })
        finalist_payload: dict[str, object] = {
            "contract_version": PHASE31_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase31_policy_fingerprint": phase31_policy_fingerprint(),
            "selection_survivor_ids": sorted(survivor_ids),
            "selection_winner_ids": winner_ids,
            "finalist_ids": finalist_ids,
            "finalists": finalists,
            "frozen": True,
            "runner_up_substitution_allowed": False,
            "protected_predictor_sha256": PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
            "protected_candidate_rows_read": 0,
            "protected_returns_read": 0,
            "protected_holdout_consumed": False,
            "development_outcomes_sha256": sha256_file(outcomes_path),
            "development_signals_sha256": sha256_file(signals_path),
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }
        self.finalists_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.finalists_path(), json.dumps(finalist_payload, indent=2, sort_keys=True) + "\n")
        checks = {
            "frozen_predictor_evidence_exact": predictor_report.get("development_sha256") == PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
            "protected_predictor_hash_exact_without_row_parse": True,
            "development_only_predictor_rows": len(predictors) == PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS,
            "outer_t20_boundary_exact": True,
            "split_evidence_accepted": len(split_sha) == 64,
            "prior_market_state_complete": state_diagnostics["prior_market_state_missing_rows"] == 0,
            "previous_session_state_timing": bool((pd.to_datetime(outcomes["prior_state_session"]) < pd.to_datetime(outcomes["decision_session"])).all()),
            "exact_candidate_count": len(PHASE31_CANDIDATES) == 4,
            "holm_global_candidate_count": len(holm) == 4,
            "selection_deflated_diagnostic_complete": selection_deflated_complete,
            "internal_deflated_diagnostic_complete": internal_deflated_complete,
            "winner_direction_limit": len(winner_ids) <= 2,
            "internal_only_winners": set(internal_metrics) == set(winner_ids),
            "finalists_subset_winners": set(finalist_ids).issubset(set(winner_ids)),
            "runner_up_substitution_disabled": not PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED,
            "protected_candidate_rows_unread": True,
            "protected_returns_unread": True,
            "protected_holdout_unconsumed": True,
            "external_activity_zero": True,
        }
        report: dict[str, object] = {
            "contract_version": PHASE31_DEVELOPMENT_STUDY_CONTRACT_VERSION,
            "phase31_policy_fingerprint": phase31_policy_fingerprint(),
            "status": "DEVELOPMENT_STUDY_PASS" if all(checks.values()) else "DEVELOPMENT_STUDY_FAIL",
            "source_predictor_report_path": str(self.predictors.report_path().resolve()),
            "source_development_predictor_sha256": PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
            "source_protected_predictor_sha256": PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
            "source_split_evidence_sha256": split_sha,
            "development_target_rows_read": int(len(predictors)),
            "development_usable_outcome_rows": int(len(outcomes)),
            "outcome_path_exclusions": outcome_exclusions,
            "state_diagnostics": state_diagnostics,
            "development_outcomes_sha256": sha256_file(outcomes_path),
            "boundaries": boundaries.to_dict(),
            "selection_metrics": {key: value.to_dict() for key, value in selection_metrics.items()},
            "selection_checks": selection_check_map,
            "holm_bonferroni": holm,
            "selection_survivor_ids": sorted(survivor_ids),
            "selection_winner_ids": winner_ids,
            "internal_metrics": {key: value.to_dict() for key, value in internal_metrics.items()},
            "internal_checks": internal_check_map,
            "finalist_ids": finalist_ids,
            "development_signal_rows": int(len(all_signals)),
            "development_signals_sha256": sha256_file(signals_path),
            "finalists_sha256": sha256_file(self.finalists_path()),
            "protected_artifact_hash_reads": 1,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
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
        atomic_write_text(self.report_path(), json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31DevelopmentError("Phase31 development study failed: " + ", ".join(failed))
        return report
