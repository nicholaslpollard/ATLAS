from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import NormalDist
from typing import Any, Callable, Iterable, Mapping

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
from .phase32_policy import (
    PHASE32_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE32_BOOTSTRAP_REPLICATES,
    PHASE32_BOOTSTRAP_SEED,
    PHASE32_CANDIDATES,
    PHASE32_COST_GRID_BPS,
    PHASE32_DEVELOPMENT_LAST_SIGNAL,
    PHASE32_INTERNAL_CONFIDENCE,
    PHASE32_INTERNAL_MIN_EVENT_ROWS,
    PHASE32_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
    PHASE32_INTERNAL_PURGE_SESSIONS,
    PHASE32_INTERNAL_VALIDATION_FOLDS,
    PHASE32_MAX_FINALISTS_PER_DIRECTION,
    PHASE32_MAX_SELECTION_WINNERS_PER_DIRECTION,
    PHASE32_MAX_SINGLE_INSTRUMENT_ROW_FRACTION,
    PHASE32_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE32_MIN_POSITIVE_REGIME_FRACTION,
    PHASE32_MIN_POSITIVE_YEAR_FRACTION,
    PHASE32_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE32_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE32_MULTIPLE_TESTING_ALPHA,
    PHASE32_MULTIPLE_TESTING_METHOD,
    PHASE32_OUTCOME_HORIZON_SESSIONS,
    PHASE32_PRIMARY_COST_BPS,
    PHASE32_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED,
    PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE32_PROTECTED_START,
    PHASE32_RESEARCH_SIGNAL_START,
    PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE32_SELECTION_CONFIDENCE,
    PHASE32_SELECTION_FOLDS,
    PHASE32_SELECTION_FRACTION,
    PHASE32_SELECTION_MIN_EVENT_ROWS,
    PHASE32_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE32_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS,
    PHASE32_SELECTION_WINNER_RULE,
    PHASE32_STRESS_COST_BPS,
    Phase32CandidateSpec,
    phase32_policy_fingerprint,
)
from .phase32_predictor_acceptance import (
    PHASE32_ACCEPTANCE_RELATIVE,
    PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT,
    PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
    PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
)
from .phase32_predictor_acquisition import (
    PHASE32_EVIDENCE_RELATIVE,
    PHASE32_FROZEN_POLICY_FINGERPRINT,
    PHASE32_PREDICTORS_RELATIVE,
    PHASE32_REPORT_RELATIVE,
)

PHASE32_DEVELOPMENT_STUDY_CONTRACT_VERSION = "phase32-development-study-v1-open-t5-spy-relative-five-hypothesis-protected-blind"
PHASE32_DEVELOPMENT_OUTCOME_CONTRACT_VERSION = "phase32-development-outcome-v1-exact-open-t5-close-spy-relative-split-censored"
PHASE32_DEVELOPMENT_SIGNAL_CONTRACT_VERSION = "phase32-development-signal-v1-frozen-sec8k-membership"
PHASE32_FINALIST_ARTIFACT_CONTRACT_VERSION = "phase32-finalists-v1-selection-internal-protected-returns-unread"
PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT = "531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde"
PHASE32_DEVELOPMENT_BOUNDARY_EXIT = date(2026, 5, 11)

_FORBIDDEN_PREDICTOR_OUTCOME_FIELDS = {
    "entry_open", "exit_close", "spy_entry_open", "spy_exit_close",
    "stock_return", "spy_return", "primary_gross_return", "unhedged_gross_return",
}


class Phase32DevelopmentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase32DevelopmentBoundaries:
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
class Phase32TrancheMetrics:
    raw_rows: int
    signal_sessions: int
    unique_instruments: int
    cost_mean_returns: dict[str, float]
    primary_mean_return: float | None
    unhedged_primary_mean_return: float | None
    primary_median_event_return: float | None
    primary_event_win_rate: float | None
    primary_session_win_rate: float | None
    primary_lcb: float | None
    primary_bootstrap_p_value: float | None
    stress_mean_return: float | None
    max_single_session_row_fraction: float | None
    max_single_instrument_row_fraction: float | None
    fold_means: tuple[float | None, ...]
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


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise Phase32DevelopmentError(f"missing local JSONL artifact: {path}") from exc
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Phase32DevelopmentError(f"invalid JSONL row: {path}:{line_number}") from exc
        if not isinstance(value, dict):
            raise Phase32DevelopmentError(f"JSONL row is not an object: {path}:{line_number}")
        rows.append(value)
    return tuple(rows)


def chronological_boundaries(sessions: Iterable[date]) -> Phase32DevelopmentBoundaries:
    ordered = tuple(sorted(set(sessions)))
    if len(ordered) < 40:
        raise Phase32DevelopmentError("too few frozen Phase32 development sessions")
    selection_count = int(math.floor(len(ordered) * PHASE32_SELECTION_FRACTION))
    internal_offset = selection_count + PHASE32_INTERNAL_PURGE_SESSIONS
    if selection_count <= 0 or internal_offset >= len(ordered):
        raise Phase32DevelopmentError("invalid Phase32 development split")
    selection = ordered[:selection_count]
    purge = ordered[selection_count:internal_offset]
    internal = ordered[internal_offset:]
    if len(purge) != PHASE32_INTERNAL_PURGE_SESSIONS or not internal:
        raise Phase32DevelopmentError("Phase32 selection/internal purge partition is incomplete")
    return Phase32DevelopmentBoundaries(
        selection[0], selection[-1], tuple(purge), internal[0], internal[-1],
        len(ordered), len(selection), len(internal),
    )


def _derived_seed(label: str) -> int:
    return PHASE32_BOOTSTRAP_SEED + int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)


def _bootstrap(values: np.ndarray, *, confidence: float, label: str) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise Phase32DevelopmentError("bootstrap requires a nonempty session vector")
    n = len(values)
    block = min(PHASE32_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE32_BOOTSTRAP_REPLICATES, block_count))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(PHASE32_BOOTSTRAP_REPLICATES, -1)[:, :n]
    sample_means = values[indices].mean(axis=1)
    lower = float(np.quantile(sample_means, 1.0 - confidence))
    observed = float(values.mean())
    null_means = (values - observed)[indices].mean(axis=1)
    p_value = float((1 + np.count_nonzero(null_means >= observed)) / (len(null_means) + 1))
    return lower, p_value


def _fraction_positive(values: Mapping[str, float]) -> float | None:
    return None if not values else float(sum(value > 0 for value in values.values()) / len(values))


def _fold_mapping(sessions: tuple[date, ...], folds: int) -> dict[date, int]:
    if len(sessions) < folds:
        raise Phase32DevelopmentError("too few Phase32 sessions for fold attribution")
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
        raise Phase32DevelopmentError("Phase32 fold attribution is incomplete")
    result[field] = result[field].astype(int)
    return result


def holm_bonferroni(p_values: Mapping[str, float], *, alpha: float = PHASE32_MULTIPLE_TESTING_ALPHA) -> dict[str, dict[str, object]]:
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
        if state_rows["decision_session"].nunique() >= PHASE32_MIN_REGIME_SIGNAL_SESSIONS:
            result[str(state)] = float(pd.to_numeric(state_rows["primary_gross_return"], errors="coerce").mean() - primary_cost)
    return result


def _fold_economic_means(
    session: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    fold_field: str,
    fold_count: int,
    primary_cost: float,
) -> tuple[float | None, ...]:
    if fold_count <= 0:
        raise Phase32DevelopmentError("Phase32 fold count must be positive")
    if signals.empty or fold_field not in signals.columns:
        return tuple(None for _ in range(fold_count))
    mapping = signals[["decision_session", fold_field]].drop_duplicates()
    if mapping.duplicated(["decision_session"], keep=False).any():
        raise Phase32DevelopmentError("Phase32 signal session belongs to multiple folds")
    merged = session.merge(mapping, on="decision_session", how="left", validate="one_to_one")
    if merged[fold_field].isna().any():
        raise Phase32DevelopmentError("Phase32 signal session is missing fold attribution")
    values: list[float | None] = []
    for fold in range(fold_count):
        group = merged.loc[merged[fold_field] == fold]
        values.append(None if group.empty else float(group["primary_gross_return"].mean() - primary_cost))
    return tuple(values)


def tranche_metrics(
    signals: pd.DataFrame,
    *,
    confidence: float,
    fold_field: str,
    fold_count: int,
    label: str,
) -> Phase32TrancheMetrics:
    if signals.empty:
        return Phase32TrancheMetrics(
            0, 0, 0, {}, None, None, None, None, None, None, None, None, None, None,
            tuple(None for _ in range(fold_count)), 0, {}, None, {}, None, {}, None, None,
        )
    data = signals.copy()
    data["decision_session"] = pd.to_datetime(data["decision_session"]).dt.date
    for field in ("primary_gross_return", "unhedged_gross_return"):
        data[field] = pd.to_numeric(data[field], errors="coerce")
    finite = np.isfinite(data["primary_gross_return"].to_numpy(dtype=float)) & np.isfinite(data["unhedged_gross_return"].to_numpy(dtype=float))
    data = data.loc[finite].copy()
    if data.empty:
        return tranche_metrics(data, confidence=confidence, fold_field=fold_field, fold_count=fold_count, label=label)
    primary_cost = PHASE32_PRIMARY_COST_BPS / 10_000.0
    stress_cost = PHASE32_STRESS_COST_BPS / 10_000.0
    session = data.groupby("decision_session", sort=True, observed=True).agg(
        primary_gross_return=("primary_gross_return", "mean"),
        unhedged_gross_return=("unhedged_gross_return", "mean"),
        row_count=("instrument_id", "size"),
    ).reset_index().sort_values("decision_session", kind="stable")
    gross = session["primary_gross_return"].to_numpy(dtype=float)
    primary = gross - primary_cost
    unhedged = session["unhedged_gross_return"].to_numpy(dtype=float) - primary_cost
    stress = gross - stress_cost
    lower, p_value = _bootstrap(primary, confidence=confidence, label=label)
    fold_values = _fold_economic_means(session, data, fold_field=fold_field, fold_count=fold_count, primary_cost=primary_cost)
    year_values: dict[int, list[float]] = defaultdict(list)
    for session_date, value in zip(session["decision_session"], primary, strict=True):
        year_values[session_date.year].append(float(value))
    year_means = {str(year): float(np.mean(values)) for year, values in sorted(year_values.items()) if len(values) >= PHASE32_MIN_YEAR_SIGNAL_SESSIONS}
    market_means = _eligible_state_means(data, state_field="prior_market_state", primary_cost=primary_cost)
    ticker_means = _eligible_state_means(data, state_field="prior_ticker_state", primary_cost=primary_cost)
    cost_means = {f"{float(cost):g}": float(np.mean(gross - float(cost) / 10_000.0)) for cost in PHASE32_COST_GRID_BPS}
    event_primary = data["primary_gross_return"].to_numpy(dtype=float) - primary_cost
    primary_std = float(np.std(primary, ddof=1)) if len(primary) > 1 else 0.0
    session_sharpe = None if primary_std <= 0 else float(np.mean(primary) / primary_std)
    raw_rows = int(len(data))
    instrument_counts = data.groupby("instrument_id", sort=True, observed=True).size()
    max_instrument_fraction = None if instrument_counts.empty else float(instrument_counts.max() / raw_rows)
    return Phase32TrancheMetrics(
        raw_rows,
        int(len(session)),
        int(data["instrument_id"].nunique()),
        cost_means,
        float(np.mean(primary)),
        float(np.mean(unhedged)),
        float(np.median(event_primary)),
        float(np.mean(event_primary > 0)),
        float(np.mean(primary > 0)),
        lower,
        p_value,
        float(np.mean(stress)),
        float(session["row_count"].max() / raw_rows),
        max_instrument_fraction,
        fold_values,
        sum(value is not None and value > 0 for value in fold_values),
        year_means,
        _fraction_positive(year_means),
        market_means,
        _fraction_positive(market_means),
        ticker_means,
        _fraction_positive(ticker_means),
        session_sharpe,
    )


def _with_deflated(
    metrics: dict[str, Phase32TrancheMetrics],
    *,
    reference_metrics: Mapping[str, Phase32TrancheMetrics] | None = None,
) -> dict[str, Phase32TrancheMetrics]:
    reference = reference_metrics if reference_metrics is not None else metrics
    sharpes = np.asarray([item.session_sharpe for item in reference.values() if item.session_sharpe is not None], dtype=float)
    if len(sharpes) < 2 or float(np.std(sharpes, ddof=1)) <= 0:
        return metrics
    sigma = float(np.std(sharpes, ddof=1))
    trials = max(2, len(reference))
    normal = NormalDist()
    gamma = 0.5772156649015329
    benchmark = sigma * ((1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / trials) + gamma * normal.inv_cdf(1.0 - 1.0 / (trials * math.e)))
    result: dict[str, Phase32TrancheMetrics] = {}
    for key, item in metrics.items():
        probability = None
        if item.session_sharpe is not None and item.signal_sessions >= 3:
            denominator = math.sqrt(max(1e-12, 1.0 + 0.5 * item.session_sharpe**2))
            z = (item.session_sharpe - benchmark) * math.sqrt(item.signal_sessions - 1) / denominator
            probability = float(normal.cdf(z))
        result[key] = Phase32TrancheMetrics(**{
            **item.to_dict(),
            "deflated_sharpe_probability": probability,
            "deflated_sharpe_benchmark": float(benchmark),
        })
    return result


def _stage_checks(
    metrics: Phase32TrancheMetrics,
    *,
    min_event_rows: int,
    min_signal_sessions: int,
    min_unique_instruments: int,
    min_positive_folds: int,
) -> dict[str, bool]:
    return {
        "min_event_rows": metrics.raw_rows >= min_event_rows,
        "min_signal_sessions": metrics.signal_sessions >= min_signal_sessions,
        "min_unique_instruments": metrics.unique_instruments >= min_unique_instruments,
        "positive_folds": metrics.positive_folds >= min_positive_folds,
        "primary_mean_positive": bool(metrics.primary_mean_return is not None and metrics.primary_mean_return > 0),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(metrics.stress_mean_return is not None and metrics.stress_mean_return > 0),
        "unhedged_primary_mean_positive": bool(metrics.unhedged_primary_mean_return is not None and metrics.unhedged_primary_mean_return > 0),
        "year_robustness": bool(metrics.positive_year_fraction is not None and metrics.positive_year_fraction >= PHASE32_MIN_POSITIVE_YEAR_FRACTION),
        "market_state_robustness": bool(metrics.positive_market_state_fraction is not None and metrics.positive_market_state_fraction >= PHASE32_MIN_POSITIVE_REGIME_FRACTION),
        "ticker_state_robustness": bool(metrics.positive_ticker_state_fraction is not None and metrics.positive_ticker_state_fraction >= PHASE32_MIN_POSITIVE_REGIME_FRACTION),
        "session_concentration": bool(metrics.max_single_session_row_fraction is not None and metrics.max_single_session_row_fraction <= PHASE32_MAX_SINGLE_SESSION_ROW_FRACTION),
        "instrument_concentration": bool(metrics.max_single_instrument_row_fraction is not None and metrics.max_single_instrument_row_fraction <= PHASE32_MAX_SINGLE_INSTRUMENT_ROW_FRACTION),
    }


def selection_checks(metrics: Phase32TrancheMetrics) -> dict[str, bool]:
    return _stage_checks(
        metrics,
        min_event_rows=PHASE32_SELECTION_MIN_EVENT_ROWS,
        min_signal_sessions=PHASE32_SELECTION_MIN_SIGNAL_SESSIONS,
        min_unique_instruments=PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS,
        min_positive_folds=PHASE32_SELECTION_MIN_POSITIVE_FOLDS,
    )


def internal_checks(metrics: Phase32TrancheMetrics) -> dict[str, bool]:
    return _stage_checks(
        metrics,
        min_event_rows=PHASE32_INTERNAL_MIN_EVENT_ROWS,
        min_signal_sessions=PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS,
        min_unique_instruments=PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
        min_positive_folds=PHASE32_INTERNAL_MIN_POSITIVE_FOLDS,
    )


def candidate_view(frame: pd.DataFrame, candidate: Phase32CandidateSpec) -> pd.DataFrame:
    mask = frame["candidate_id"].astype("string").eq(candidate.candidate_id)
    result = frame.loc[mask.fillna(False)].copy()
    if not result.empty and set(result["direction"].astype(str)) != {candidate.direction}:
        raise Phase32DevelopmentError(f"Phase32 candidate direction drifted: {candidate.candidate_id}")
    return result


def apply_return_geometry(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for field in ("entry_open", "exit_close", "spy_entry_open", "spy_exit_close"):
        result[field] = pd.to_numeric(result[field], errors="coerce")
        values = result[field].to_numpy(dtype=float)
        if not np.isfinite(values).all() or bool((values <= 0).any()):
            raise Phase32DevelopmentError(f"Phase32 return geometry requires finite positive {field}")
    result["stock_return"] = result["exit_close"] / result["entry_open"] - 1.0
    result["spy_return"] = result["spy_exit_close"] / result["spy_entry_open"] - 1.0
    direction = np.where(result["direction"].astype(str).eq("LONG"), 1.0, -1.0)
    result["primary_gross_return"] = direction * (result["stock_return"] - result["spy_return"])
    result["unhedged_gross_return"] = direction * result["stock_return"]
    for field in ("stock_return", "spy_return", "primary_gross_return", "unhedged_gross_return"):
        if not np.isfinite(result[field].to_numpy(dtype=float)).all():
            raise Phase32DevelopmentError(f"Phase32 development contains nonfinite {field}")
    return result


def resolve_execution_tickers(
    predictor_rows: Iterable[dict[str, Any]],
    filing_entity_rows: Iterable[dict[str, Any]],
) -> dict[tuple[str, str, str], str]:
    predictor_keys = {
        (str(row.get("instrument_id") or ""), str(row.get("decision_session") or ""), str(row.get("candidate_id") or ""))
        for row in predictor_rows
        if str(row.get("stage") or "") == "development"
    }
    if any(not all(key) for key in predictor_keys):
        raise Phase32DevelopmentError("Phase32 development predictor key is incomplete")
    ticker_sets: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in filing_entity_rows:
        if row.get("eligibility") != "eligible" or str(row.get("stage") or "") != "development":
            continue
        instrument = row.get("instrument")
        if not isinstance(instrument, dict):
            raise Phase32DevelopmentError("eligible Phase32 filing entity lacks instrument evidence")
        instrument_id = str(instrument.get("instrument_id") or "").strip()
        ticker = str(instrument.get("ticker") or "").strip()
        decision_session = str(row.get("decision_session") or "").strip()
        if not instrument_id or not ticker or not decision_session:
            raise Phase32DevelopmentError("eligible Phase32 filing entity has incomplete execution identity")
        for candidate_id in row.get("candidate_ids") or []:
            key = (instrument_id, decision_session, str(candidate_id))
            if key in predictor_keys:
                ticker_sets[key].add(ticker)
    missing = sorted(predictor_keys - set(ticker_sets))
    if missing:
        raise Phase32DevelopmentError("Phase32 development predictor lacks execution-ticker lineage: " + repr(missing[:3]))
    ambiguous = sorted((key, sorted(values)) for key, values in ticker_sets.items() if key in predictor_keys and len(values) != 1)
    if ambiguous:
        raise Phase32DevelopmentError("Phase32 development execution ticker is ambiguous before outcomes: " + repr(ambiguous[:3]))
    return {key: next(iter(ticker_sets[key])) for key in sorted(predictor_keys)}


def _write_parquet(settings: AtlasSettings, frame: pd.DataFrame, target: Path, *, order_by: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase32_development_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            "COPY (SELECT * FROM phase32_development_write "
            f"ORDER BY {order_by}) TO {sql_string(temp)} "
            f"(FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


class Phase32DevelopmentStudy:
    """First Phase32 stage allowed to read development outcomes; protected returns stay closed."""

    def __init__(self, settings: AtlasSettings, *, progress_callback: Callable[[str], None] | None = None) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.phase26 = Phase26ObservationBuilder(settings)
        self.gate7 = Phase25Gate7RouteContextReplay(settings)
        self.progress_callback = progress_callback
        self.provider_root = settings.resolved_path(settings.data.paths.provider)
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.predictor_path = self.derived_root / PHASE32_PREDICTORS_RELATIVE
        self.acquisition_report_path = self.derived_root / PHASE32_REPORT_RELATIVE
        self.acceptance_path = self.derived_root / PHASE32_ACCEPTANCE_RELATIVE
        self.filing_entity_path = self.provider_root / PHASE32_EVIDENCE_RELATIVE / "candidate_filing_entity_records.jsonl"
        self.root = self.derived_root / "strategy_evaluation" / "phase32" / "v1" / "development"

    def _progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

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
            raise Phase32DevelopmentError(f"missing {label}: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Phase32DevelopmentError(f"invalid {label}: {path}") from exc
        if not isinstance(payload, dict):
            raise Phase32DevelopmentError(f"{label} must be a JSON object")
        return payload

    def _verify_independent_acceptance(self) -> dict[str, Any]:
        acceptance = self._read_json(self.acceptance_path, label="Phase32 independent predictor/source acceptance")
        if acceptance.get("contract_version") != PHASE32_PREDICTOR_INDEPENDENT_ACCEPTANCE_CONTRACT:
            raise Phase32DevelopmentError("Phase32 independent acceptance contract mismatch")
        if acceptance.get("pass") is not True:
            raise Phase32DevelopmentError("Phase32 independent predictor/source acceptance is not PASS")
        fingerprint = str(acceptance.get("acceptance_fingerprint") or "")
        if fingerprint != PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT:
            raise Phase32DevelopmentError("Phase32 independent acceptance fingerprint differs from accepted target-machine PASS")
        payload = dict(acceptance)
        payload.pop("acceptance_fingerprint", None)
        payload.pop("pass", None)
        if _sha256_text(_canonical_json(payload)) != fingerprint:
            raise Phase32DevelopmentError("Phase32 independent acceptance fingerprint is not internally reproducible")
        if acceptance.get("policy_fingerprint") != PHASE32_FROZEN_POLICY_FINGERPRINT:
            raise Phase32DevelopmentError("Phase32 independent acceptance policy fingerprint mismatch")
        if acceptance.get("candidate_filing_entity_evidence_sha256") != PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256:
            raise Phase32DevelopmentError("Phase32 accepted filing-entity evidence hash mismatch")
        if acceptance.get("predictor_rows_sha256") != PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256:
            raise Phase32DevelopmentError("Phase32 accepted predictor hash mismatch")
        for field in (
            "independent_network_reads", "target_outcome_rows_read", "protected_return_rows_read",
            "stock_price_rows_read", "spy_price_rows_read", "options_rows_read", "provider_writes",
            "broker_reads", "broker_writes", "order_writes", "paper_submits", "live_writes", "automation_writes",
        ):
            if int(acceptance.get(field, -1)) != 0:
                raise Phase32DevelopmentError(f"Phase32 independent acceptance has forbidden activity: {field}={acceptance.get(field)!r}")
        return acceptance

    def _load_development_predictors(self) -> tuple[pd.DataFrame, dict[str, Any], dict[str, int]]:
        acceptance = self._verify_independent_acceptance()
        source_report_sha = str(acceptance.get("source_report_sha256") or "")
        if not self.acquisition_report_path.is_file() or len(source_report_sha) != 64 or sha256_file(self.acquisition_report_path) != source_report_sha:
            raise Phase32DevelopmentError("Phase32 acquisition report differs from independently accepted source report")
        if not self.predictor_path.is_file() or sha256_file(self.predictor_path) != PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256:
            raise Phase32DevelopmentError("Phase32 frozen predictor artifact SHA mismatch")
        if not self.filing_entity_path.is_file() or sha256_file(self.filing_entity_path) != PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256:
            raise Phase32DevelopmentError("Phase32 frozen filing-entity evidence SHA mismatch")
        predictor_rows = _load_jsonl(self.predictor_path)
        filing_rows = _load_jsonl(self.filing_entity_path)
        if len(predictor_rows) != int(acceptance.get("eligible_predictor_rows", -1)):
            raise Phase32DevelopmentError("Phase32 predictor row count differs from independent acceptance")
        for row in predictor_rows:
            if row.get("policy_fingerprint") != PHASE32_FROZEN_POLICY_FINGERPRINT:
                raise Phase32DevelopmentError("Phase32 predictor row policy fingerprint drifted")
            forbidden = _FORBIDDEN_PREDICTOR_OUTCOME_FIELDS.intersection(row)
            if forbidden:
                raise Phase32DevelopmentError("Phase32 predictor artifact contains forbidden market outcomes: " + ", ".join(sorted(forbidden)))
        development_rows = [dict(row) for row in predictor_rows if str(row.get("stage") or "") == "development"]
        protected_rows = [row for row in predictor_rows if str(row.get("stage") or "") == "protected_predictor_only"]
        expected_stage_counts = acceptance.get("stage_predictor_counts")
        if not isinstance(expected_stage_counts, dict):
            raise Phase32DevelopmentError("Phase32 independent acceptance lacks stage predictor counts")
        if len(development_rows) != int(expected_stage_counts.get("development", -1)):
            raise Phase32DevelopmentError("Phase32 development predictor count drifted")
        if len(protected_rows) != int(expected_stage_counts.get("protected_predictor_only", -1)):
            raise Phase32DevelopmentError("Phase32 protected predictor count drifted")
        if not development_rows:
            raise Phase32DevelopmentError("Phase32 accepted development predictor population is empty")
        execution = resolve_execution_tickers(development_rows, filing_rows)
        for row in development_rows:
            key = (str(row["instrument_id"]), str(row["decision_session"]), str(row["candidate_id"]))
            ticker = execution[key]
            provider_tickers = {str(value) for value in row.get("provider_tickers") or []}
            if ticker not in provider_tickers:
                raise Phase32DevelopmentError("Phase32 execution ticker is absent from frozen provider-ticker lineage")
            row["execution_ticker"] = ticker
        frame = pd.DataFrame.from_records(development_rows)
        frame["decision_session"] = pd.to_datetime(frame["decision_session"]).dt.date
        frame["exit_session"] = pd.to_datetime(frame["exit_session"]).dt.date
        if frame.duplicated(["instrument_id", "decision_session", "candidate_id"], keep=False).any():
            raise Phase32DevelopmentError("Phase32 development predictors duplicate the frozen event unit")
        if frame["decision_session"].max() > date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL):
            raise Phase32DevelopmentError("Phase32 development predictor crossed signal boundary")
        if frame["exit_session"].max() >= date.fromisoformat(PHASE32_PROTECTED_START):
            raise Phase32DevelopmentError("Phase32 development predictor exit crossed protected start")
        diagnostics = {
            "development_predictor_rows_read": int(len(frame)),
            "protected_predictor_rows_read_for_partition_validation": int(len(protected_rows)),
            "execution_ticker_ambiguous_predictors": 0,
        }
        return frame, acceptance, diagnostics

    def _split_evidence(self) -> tuple[pd.DataFrame, str]:
        report = self._read_json(self.phase26.report_path(), label="accepted Phase26 observation report")
        if report.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION or report.get("pass") is not True:
            raise Phase32DevelopmentError("Phase26 observation evidence is not accepted")
        if int(report.get("protected_return_reads", -1)) != 0:
            raise Phase32DevelopmentError("accepted split lineage is attached to consumed protected returns")
        path = MLOutcomeFeasibilityProbe(self.settings).split_evidence_path(PHASE26_OUTCOME_EVIDENCE_END)
        expected_sha = str(report.get("split_evidence_sha256") or "")
        if not path.is_file() or len(expected_sha) != 64 or sha256_file(path) != expected_sha:
            raise Phase32DevelopmentError("accepted split evidence SHA mismatch")
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
        self._progress(f"reading exact daily entry/exit paths for {len(predictors)} development predictor rows")
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        con = connect_utc(":memory:")
        try:
            con.execute("SET preserve_insertion_order=false")
            query_predictors = predictors.copy()
            for field in ("identity_key", "accession_numbers", "provider_tickers", "taxonomy_triples", "acceptance_datetimes", "source_lineage_sha256"):
                if field in query_predictors.columns:
                    query_predictors[field] = query_predictors[field].map(_canonical_json)
            con.register("p32_predictors", query_predictors)
            con.register("p32_splits", splits)
            result = con.execute(f"""
                WITH needed AS (
                    SELECT execution_ticker AS symbol, CAST(decision_session AS DATE) AS session_date FROM p32_predictors
                    UNION SELECT execution_ticker, CAST(exit_session AS DATE) FROM p32_predictors
                    UNION SELECT 'SPY', CAST(decision_session AS DATE) FROM p32_predictors
                    UNION SELECT 'SPY', CAST(exit_session AS DATE) FROM p32_predictors
                ), bars AS (
                    SELECT b.symbol, CAST(b.session_date AS DATE) AS session_date,
                           CAST(b.open AS DOUBLE) AS session_open, CAST(b.close AS DOUBLE) AS session_close
                    FROM read_parquet({sql_string(bar_glob)}, union_by_name=true, hive_partitioning=false) b
                    INNER JOIN needed n ON n.symbol = b.symbol AND n.session_date = CAST(b.session_date AS DATE)
                )
                SELECT p.*, se.session_open AS entry_open, sx.session_close AS exit_close,
                       pe.session_open AS spy_entry_open, px.session_close AS spy_exit_close,
                       EXISTS (
                           SELECT 1 FROM p32_splits s
                           WHERE s.ticker = p.execution_ticker
                             AND CAST(s.execution_date AS DATE) > CAST(p.decision_session AS DATE)
                             AND CAST(s.execution_date AS DATE) <= CAST(p.exit_session AS DATE)
                       ) AS split_crossing
                FROM p32_predictors p
                LEFT JOIN bars se ON se.symbol = p.execution_ticker AND se.session_date = CAST(p.decision_session AS DATE)
                LEFT JOIN bars sx ON sx.symbol = p.execution_ticker AND sx.session_date = CAST(p.exit_session AS DATE)
                LEFT JOIN bars pe ON pe.symbol = 'SPY' AND pe.session_date = CAST(p.decision_session AS DATE)
                LEFT JOIN bars px ON px.symbol = 'SPY' AND px.session_date = CAST(p.exit_session AS DATE)
                ORDER BY p.decision_session, p.instrument_id, p.candidate_id
            """).fetch_df()
        finally:
            con.close()
        if len(result) != len(predictors):
            raise Phase32DevelopmentError("Phase32 exact outcome join cardinality drifted; duplicate/missing daily keys suspected")
        result["decision_session"] = pd.to_datetime(result["decision_session"]).dt.date
        result["exit_session"] = pd.to_datetime(result["exit_session"]).dt.date
        for field in ("entry_open", "exit_close", "spy_entry_open", "spy_exit_close"):
            result[field] = pd.to_numeric(result[field], errors="coerce")
        spy_missing = (
            result["spy_entry_open"].isna() | result["spy_exit_close"].isna()
            | ~np.isfinite(result["spy_entry_open"].to_numpy(dtype=float))
            | ~np.isfinite(result["spy_exit_close"].to_numpy(dtype=float))
            | result["spy_entry_open"].le(0) | result["spy_exit_close"].le(0)
        )
        if bool(spy_missing.any()):
            raise Phase32DevelopmentError("Phase32 SPY benchmark is missing an exact frozen entry/exit session")
        stock_missing = (
            result["entry_open"].isna() | result["exit_close"].isna()
            | ~np.isfinite(result["entry_open"].to_numpy(dtype=float))
            | ~np.isfinite(result["exit_close"].to_numpy(dtype=float))
            | result["entry_open"].le(0) | result["exit_close"].le(0)
        )
        split_crossing = result["split_crossing"].fillna(False).astype(bool)
        usable = result.loc[~stock_missing & ~split_crossing].copy()
        if usable.empty:
            raise Phase32DevelopmentError("Phase32 development outcomes are empty after path-quality censoring")
        usable = apply_return_geometry(usable)
        usable.insert(0, "outcome_contract_version", PHASE32_DEVELOPMENT_OUTCOME_CONTRACT_VERSION)
        usable = usable.drop(columns=["split_crossing"])
        return usable, {
            "exact_stock_path_missing_rows": int(stock_missing.sum()),
            "split_crossing_censored_rows": int(split_crossing.sum()),
            "usable_development_rows": int(len(usable)),
        }

    def _prior_regime_states(self, predictors: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
        self._progress("reconstructing previous-session accepted market/ticker states")
        research_start = date.fromisoformat(PHASE32_RESEARCH_SIGNAL_START)
        development_last = date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL)
        prior_grid = tuple(self.calendar.sessions_in_range(research_start - timedelta(days=10), development_last))
        previous = {prior_grid[index]: prior_grid[index - 1] for index in range(1, len(prior_grid))}
        result = predictors.copy()
        result["prior_state_session"] = result["decision_session"].map(previous)
        if result["prior_state_session"].isna().any():
            raise Phase32DevelopmentError("Phase32 previous-session mapping is incomplete")
        if not all(prior < decision for prior, decision in zip(result["prior_state_session"], result["decision_session"], strict=True)):
            raise Phase32DevelopmentError("Phase32 regime state timing is not prior-session-only")
        market = self.gate7._market_states(development_last).rename(columns={"trading_date": "prior_state_session", "market_state": "prior_market_state"})
        result = result.merge(market[["prior_state_session", "prior_market_state"]], on="prior_state_session", how="left", validate="many_to_one")
        if result["prior_market_state"].isna().any():
            raise Phase32DevelopmentError("Phase32 accepted prior-session market state is incomplete")
        ticker_sessions = tuple(self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, development_last))
        session_ordinals = {session: index for index, session in enumerate(ticker_sessions)}
        pairs = result[["instrument_id", "execution_ticker"]].drop_duplicates().rename(columns={"execution_ticker": "ticker"})
        intervals = self.gate7._exact_intervals(population=pairs, sessions=ticker_sessions)
        raw = self.gate7._raw_ticker_state_history(intervals)
        persisted = persist_exact_interval_ticker_states(raw, session_ordinals=session_ordinals)
        if TICKER_SELECTED_CONFIRMATION_SESSIONS != 2:
            raise Phase32DevelopmentError("accepted ticker persistence policy drifted")
        if persisted.empty:
            states = pd.DataFrame(columns=["instrument_id", "execution_ticker", "prior_state_session", "prior_ticker_state"])
        else:
            persisted["trading_date"] = pd.to_datetime(persisted["trading_date"]).dt.date
            states = persisted[["instrument_id", "ticker", "trading_date", "effective_ticker_state"]].rename(columns={
                "ticker": "execution_ticker", "trading_date": "prior_state_session", "effective_ticker_state": "prior_ticker_state",
            })
            if states.duplicated(["instrument_id", "execution_ticker", "prior_state_session"], keep=False).any():
                raise Phase32DevelopmentError("Phase32 reconstructed prior ticker state is not unique")
        result = result.merge(states, on=["instrument_id", "execution_ticker", "prior_state_session"], how="left", validate="many_to_one")
        return result, {
            "prior_market_state_missing_rows": int(result["prior_market_state"].isna().sum()),
            "prior_ticker_state_missing_rows": int(result["prior_ticker_state"].isna().sum()),
            "ticker_regime_interval_count": int(len(intervals)),
            "ticker_regime_raw_rows": int(len(raw)),
            "ticker_regime_persisted_rows": int(len(persisted)),
        }

    def _boundaries(self) -> Phase32DevelopmentBoundaries:
        start = date.fromisoformat(PHASE32_RESEARCH_SIGNAL_START)
        end = date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL)
        sessions = tuple(self.calendar.sessions_in_range(start, end))
        if not sessions or sessions[0] != start or sessions[-1] != end:
            raise Phase32DevelopmentError("Phase32 frozen development calendar scope mismatch")
        return chronological_boundaries(sessions)

    def _validate_outer_boundary(self) -> None:
        development_last = date.fromisoformat(PHASE32_DEVELOPMENT_LAST_SIGNAL)
        extended = tuple(self.calendar.sessions_in_range(development_last, PHASE32_DEVELOPMENT_BOUNDARY_EXIT))
        if len(extended) != PHASE32_OUTCOME_HORIZON_SESSIONS + 1 or extended[0] != development_last or extended[-1] != PHASE32_DEVELOPMENT_BOUNDARY_EXIT:
            raise Phase32DevelopmentError("Phase32 frozen outer development t+5 boundary drifted")

    @staticmethod
    def _decorate(frame: pd.DataFrame, candidate: Phase32CandidateSpec, *, stage: str, fold_field: str) -> pd.DataFrame:
        result = frame.copy()
        result.insert(0, "signal_contract_version", PHASE32_DEVELOPMENT_SIGNAL_CONTRACT_VERSION)
        result.insert(1, "candidate_family", candidate.family)
        result.insert(2, "strategy_direction", candidate.direction)
        result.insert(3, "research_stage", stage)
        if fold_field not in result.columns:
            raise Phase32DevelopmentError("Phase32 decorated signal is missing fold")
        return result

    def run(self) -> dict[str, object]:
        if phase32_policy_fingerprint() != PHASE32_FROZEN_POLICY_FINGERPRINT:
            raise Phase32DevelopmentError("Phase32 scientific policy fingerprint drifted")
        if len(PHASE32_CANDIDATES) != 5 or PHASE32_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_GLOBAL_5":
            raise Phase32DevelopmentError("Phase32 frozen global hypothesis family drifted")
        if PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED or PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED:
            raise Phase32DevelopmentError("Phase32 forbidden fallback/protected-return authority is enabled")
        if not PHASE32_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED:
            raise Phase32DevelopmentError("Phase32 frozen predictor-blindness authority drifted")
        if PHASE32_SELECTION_WINNER_RULE != "highest_primary_selection_LCB_then_candidate_id":
            raise Phase32DevelopmentError("Phase32 selection winner rule drifted")
        self._validate_outer_boundary()
        self._progress("validating independently accepted predictor/source lineage")
        predictors, acceptance, predictor_diagnostics = self._load_development_predictors()
        self._progress(f"execution-ticker preflight passed for {len(predictors)} development predictor rows")
        splits, split_sha = self._split_evidence()
        states, state_diagnostics = self._prior_regime_states(predictors)
        outcomes, outcome_exclusions = self._development_outcomes(states, splits)
        boundaries = self._boundaries()
        selection_frame = outcomes.loc[(outcomes["decision_session"] >= boundaries.selection_start) & (outcomes["decision_session"] <= boundaries.selection_end)].copy()
        internal_frame = outcomes.loc[(outcomes["decision_session"] >= boundaries.internal_start) & (outcomes["decision_session"] <= boundaries.internal_end)].copy()
        if selection_frame.empty or internal_frame.empty:
            raise Phase32DevelopmentError("Phase32 outcome population does not cover both development tranches")
        purge_set = set(boundaries.purge_sessions)
        if selection_frame["decision_session"].isin(purge_set).any() or internal_frame["decision_session"].isin(purge_set).any():
            raise Phase32DevelopmentError("Phase32 purge sessions leaked into research tranches")
        selection_sessions = tuple(self.calendar.sessions_in_range(boundaries.selection_start, boundaries.selection_end))
        internal_sessions = tuple(self.calendar.sessions_in_range(boundaries.internal_start, boundaries.internal_end))
        selection_fold_map = _fold_mapping(selection_sessions, PHASE32_SELECTION_FOLDS)
        internal_fold_map = _fold_mapping(internal_sessions, PHASE32_INTERNAL_VALIDATION_FOLDS)
        signal_artifacts: list[pd.DataFrame] = []
        selection_metrics: dict[str, Phase32TrancheMetrics] = {}
        selection_check_map: dict[str, dict[str, bool]] = {}
        self._progress("evaluating frozen selection family: 0 / 5 candidates completed")
        for index, candidate in enumerate(PHASE32_CANDIDATES, start=1):
            signals = _assign_fold(candidate_view(selection_frame, candidate), mapping=selection_fold_map, field="selection_fold")
            decorated = self._decorate(signals, candidate, stage="SELECTION", fold_field="selection_fold")
            signal_artifacts.append(decorated)
            metrics = tranche_metrics(
                decorated,
                confidence=PHASE32_SELECTION_CONFIDENCE,
                fold_field="selection_fold",
                fold_count=PHASE32_SELECTION_FOLDS,
                label=f"selection:{candidate.candidate_id}",
            )
            selection_metrics[candidate.candidate_id] = metrics
            selection_check_map[candidate.candidate_id] = selection_checks(metrics)
            self._progress(f"evaluating frozen selection family: {index} / 5 candidates completed")
        selection_metrics = _with_deflated(selection_metrics)
        p_values = {
            candidate.candidate_id: (
                selection_metrics[candidate.candidate_id].primary_bootstrap_p_value
                if selection_metrics[candidate.candidate_id].primary_bootstrap_p_value is not None
                else 1.0
            )
            for candidate in PHASE32_CANDIDATES
        }
        holm = holm_bonferroni(p_values)
        if set(holm) != {candidate.candidate_id for candidate in PHASE32_CANDIDATES}:
            raise Phase32DevelopmentError("Phase32 Holm family is incomplete")
        survivor_ids = {
            candidate.candidate_id
            for candidate in PHASE32_CANDIDATES
            if all(selection_check_map[candidate.candidate_id].values())
            and bool(holm[candidate.candidate_id]["rejected_null"])
        }
        winner_ids: list[str] = []
        for direction in ("LONG", "SHORT"):
            eligible = [
                candidate for candidate in PHASE32_CANDIDATES
                if candidate.direction == direction and candidate.candidate_id in survivor_ids
            ]
            eligible.sort(key=lambda candidate: (
                -float(selection_metrics[candidate.candidate_id].primary_lcb if selection_metrics[candidate.candidate_id].primary_lcb is not None else -math.inf),
                candidate.candidate_id,
            ))
            if eligible:
                winner_ids.append(eligible[0].candidate_id)
        if len(winner_ids) > 2 * PHASE32_MAX_SELECTION_WINNERS_PER_DIRECTION:
            raise Phase32DevelopmentError("Phase32 selected more than one winner per direction")
        internal_metrics: dict[str, Phase32TrancheMetrics] = {}
        internal_check_map: dict[str, dict[str, bool]] = {}
        finalist_ids: list[str] = []
        for candidate_id in winner_ids:
            candidate = next(item for item in PHASE32_CANDIDATES if item.candidate_id == candidate_id)
            signals = _assign_fold(candidate_view(internal_frame, candidate), mapping=internal_fold_map, field="internal_fold")
            decorated = self._decorate(signals, candidate, stage="INTERNAL_VALIDATION", fold_field="internal_fold")
            signal_artifacts.append(decorated)
            metrics = tranche_metrics(
                decorated,
                confidence=PHASE32_INTERNAL_CONFIDENCE,
                fold_field="internal_fold",
                fold_count=PHASE32_INTERNAL_VALIDATION_FOLDS,
                label=f"internal:{candidate.candidate_id}",
            )
            internal_metrics[candidate_id] = metrics
            internal_check_map[candidate_id] = internal_checks(metrics)
            if all(internal_check_map[candidate_id].values()):
                finalist_ids.append(candidate_id)
        internal_metrics = _with_deflated(internal_metrics, reference_metrics=selection_metrics)
        selection_deflated_complete = all(item.raw_rows == 0 or item.deflated_sharpe_probability is not None for item in selection_metrics.values())
        internal_deflated_complete = all(item.raw_rows == 0 or item.deflated_sharpe_probability is not None for item in internal_metrics.values())
        finalist_directions = [next(item.direction for item in PHASE32_CANDIDATES if item.candidate_id == candidate_id) for candidate_id in finalist_ids]
        if len(finalist_directions) != len(set(finalist_directions)):
            raise Phase32DevelopmentError("Phase32 created more than one finalist in a direction")
        if any(finalist_directions.count(direction) > PHASE32_MAX_FINALISTS_PER_DIRECTION for direction in set(finalist_directions)):
            raise Phase32DevelopmentError("Phase32 finalist direction limit drifted")

        outcomes_path = self.outcomes_path()
        signals_path = self.signals_path()
        _write_parquet(self.settings, outcomes, outcomes_path, order_by="decision_session, instrument_id, candidate_id")
        all_signals = pd.concat(signal_artifacts, ignore_index=True, sort=False) if signal_artifacts else outcomes.iloc[0:0].copy()
        _write_parquet(self.settings, all_signals, signals_path, order_by="research_stage, candidate_id, decision_session, instrument_id")
        finalists = []
        for candidate_id in finalist_ids:
            candidate = next(item for item in PHASE32_CANDIDATES if item.candidate_id == candidate_id)
            finalists.append({
                "candidate_id": candidate.candidate_id,
                "family": candidate.family,
                "direction": candidate.direction,
                "predictor_sha256": PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
                "filing_entity_evidence_sha256": PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
                "independent_acceptance_fingerprint": PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
                "development_outcomes_sha256": sha256_file(outcomes_path),
            })
        finalist_payload: dict[str, object] = {
            "contract_version": PHASE32_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase32_policy_fingerprint": phase32_policy_fingerprint(),
            "independent_acceptance_fingerprint": PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
            "selection_survivor_ids": sorted(survivor_ids),
            "selection_winner_ids": winner_ids,
            "finalist_ids": finalist_ids,
            "finalists": finalists,
            "frozen": True,
            "runner_up_substitution_allowed": False,
            "protected_predictor_rows_observed": int(predictor_diagnostics["protected_predictor_rows_read_for_partition_validation"]),
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "development_outcomes_sha256": sha256_file(outcomes_path),
            "development_signals_sha256": sha256_file(signals_path),
        }
        self.finalists_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.finalists_path(), json.dumps(finalist_payload, indent=2, sort_keys=True) + "\n")
        checks = {
            "independent_source_acceptance_exact": acceptance.get("acceptance_fingerprint") == PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
            "frozen_predictor_evidence_exact": True,
            "frozen_filing_entity_evidence_exact": True,
            "execution_ticker_preflight_unambiguous": predictor_diagnostics["execution_ticker_ambiguous_predictors"] == 0,
            "development_only_predictor_rows": len(predictors) == int(acceptance["stage_predictor_counts"]["development"]),
            "outer_t5_boundary_exact": True,
            "split_evidence_accepted": len(split_sha) == 64,
            "prior_market_state_complete": state_diagnostics["prior_market_state_missing_rows"] == 0,
            "previous_session_state_timing": bool((pd.to_datetime(outcomes["prior_state_session"]) < pd.to_datetime(outcomes["decision_session"])).all()),
            "exact_candidate_count": len(PHASE32_CANDIDATES) == 5,
            "holm_global_candidate_count": len(holm) == 5,
            "selection_deflated_diagnostic_complete": selection_deflated_complete,
            "internal_deflated_diagnostic_complete": internal_deflated_complete,
            "winner_direction_limit": len(winner_ids) <= 2,
            "internal_only_winners": set(internal_metrics) == set(winner_ids),
            "finalists_subset_winners": set(finalist_ids).issubset(set(winner_ids)),
            "finalist_direction_limit": len(finalist_directions) == len(set(finalist_directions)),
            "runner_up_substitution_disabled": not PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
            "protected_predictor_metadata_allowed": PHASE32_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED,
            "protected_returns_unread": True,
            "protected_holdout_unconsumed": True,
            "external_activity_zero": True,
        }
        report: dict[str, object] = {
            "contract_version": PHASE32_DEVELOPMENT_STUDY_CONTRACT_VERSION,
            "phase32_policy_fingerprint": phase32_policy_fingerprint(),
            "status": "DEVELOPMENT_STUDY_PASS" if all(checks.values()) else "DEVELOPMENT_STUDY_FAIL",
            "source_acquisition_report_path": str(self.acquisition_report_path.resolve()),
            "source_predictor_sha256": PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
            "source_filing_entity_evidence_sha256": PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
            "source_independent_acceptance_fingerprint": PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
            "source_split_evidence_sha256": split_sha,
            "predictor_diagnostics": predictor_diagnostics,
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
            "protected_predictor_rows_read_for_partition_validation": int(predictor_diagnostics["protected_predictor_rows_read_for_partition_validation"]),
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
            "report_path": str(self.report_path().resolve()),
            "pass": all(checks.values()),
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase32DevelopmentError("Phase32 development study failed: " + ", ".join(failed))
        return report
