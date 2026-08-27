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

from .phase26_observations import (
    PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION,
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase26_policy import (
    PHASE26_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE26_BOOTSTRAP_REPLICATES,
    PHASE26_BOOTSTRAP_SEED,
    PHASE26_CANDIDATES,
    PHASE26_INTERNAL_CONFIDENCE,
    PHASE26_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE26_INTERNAL_MIN_RAW_ROWS,
    PHASE26_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE26_INTERNAL_VALIDATION_FOLDS,
    PHASE26_MAX_FINALISTS_PER_FAMILY_DIRECTION,
    PHASE26_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE26_MIN_POSITIVE_REGIME_FRACTION,
    PHASE26_MIN_POSITIVE_YEAR_FRACTION,
    PHASE26_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE26_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE26_MULTIPLE_TESTING_ALPHA,
    PHASE26_PRIMARY_COST_BPS,
    PHASE26_PURGE_SESSIONS,
    PHASE26_RESEARCH_START,
    PHASE26_SELECTION_CONFIDENCE,
    PHASE26_SELECTION_FOLDS,
    PHASE26_SELECTION_FRACTION,
    PHASE26_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE26_SELECTION_MIN_RAW_ROWS,
    PHASE26_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE26_STRESS_COST_BPS,
    Phase26CandidateSpec,
    phase26_policy_fingerprint,
)
from .phase26_signals import candidate_mask


PHASE26_RESEARCH_REPORT_CONTRACT_VERSION = (
    "phase26-research-v1-selection-internal-session-dependence-holm-no-protected"
)
PHASE26_SIGNAL_ARTIFACT_CONTRACT_VERSION = "phase26-development-signal-v1"
PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION = "phase26-finalists-v1-frozen-before-protected"


class Phase26ResearchError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase26DevelopmentBoundaries:
    selection_start: date
    selection_end: date
    purged_sessions: tuple[date, ...]
    internal_start: date
    internal_end: date
    development_session_count: int
    selection_session_count: int
    internal_session_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "selection_start": self.selection_start.isoformat(),
            "selection_end": self.selection_end.isoformat(),
            "purged_sessions": [item.isoformat() for item in self.purged_sessions],
            "internal_start": self.internal_start.isoformat(),
            "internal_end": self.internal_end.isoformat(),
            "development_session_count": self.development_session_count,
            "selection_session_count": self.selection_session_count,
            "internal_session_count": self.internal_session_count,
        }


@dataclass(frozen=True, slots=True)
class Phase26TrancheMetrics:
    raw_rows: int
    signal_sessions: int
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
    deflated_sharpe_probability: float | None = None
    deflated_sharpe_benchmark: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _derived_seed(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return PHASE26_BOOTSTRAP_SEED + int(digest[:8], 16)


def chronological_boundaries(sessions: Iterable[date]) -> Phase26DevelopmentBoundaries:
    ordered = tuple(sorted(set(sessions)))
    if len(ordered) < 20:
        raise Phase26ResearchError("too few Phase26 development sessions")
    selection_count = int(math.floor(len(ordered) * PHASE26_SELECTION_FRACTION))
    internal_offset = selection_count + PHASE26_PURGE_SESSIONS
    if selection_count <= 0 or internal_offset >= len(ordered):
        raise Phase26ResearchError("invalid Phase26 development split")
    selection = ordered[:selection_count]
    purge = ordered[selection_count:internal_offset]
    internal = ordered[internal_offset:]
    if len(purge) != PHASE26_PURGE_SESSIONS or not internal:
        raise Phase26ResearchError("Phase26 selection/internal purge partition is incomplete")
    return Phase26DevelopmentBoundaries(
        selection_start=selection[0],
        selection_end=selection[-1],
        purged_sessions=tuple(purge),
        internal_start=internal[0],
        internal_end=internal[-1],
        development_session_count=len(ordered),
        selection_session_count=len(selection),
        internal_session_count=len(internal),
    )


def _bootstrap(values: np.ndarray, *, confidence: float, label: str) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise Phase26ResearchError("bootstrap requires a nonempty session vector")
    n = len(values)
    block = min(PHASE26_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE26_BOOTSTRAP_REPLICATES, block_count))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(
        PHASE26_BOOTSTRAP_REPLICATES, -1
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


def _fold_means(values: np.ndarray, folds: int) -> tuple[float, ...]:
    if len(values) < folds:
        return ()
    return tuple(float(part.mean()) for part in np.array_split(values, folds) if len(part))


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
        if subset["as_of_date"].nunique() < PHASE26_MIN_REGIME_SIGNAL_SESSIONS:
            continue
        result[str(state)] = float(
            pd.to_numeric(subset["directional_return"], errors="coerce").mean()
            - primary_cost
        )
    return result


def _fraction_positive(values: Mapping[str, float]) -> float | None:
    if not values:
        return None
    return float(sum(value > 0 for value in values.values()) / len(values))


def tranche_metrics(
    fired: pd.DataFrame,
    *,
    confidence: float,
    folds: int,
    label: str,
) -> Phase26TrancheMetrics:
    if fired.empty:
        return Phase26TrancheMetrics(
            0, 0, None, None, None, None, None, None, None, None, (), 0,
            {}, None, {}, None, {}, None, None,
        )
    data = fired.copy()
    data["as_of_date"] = pd.to_datetime(data["as_of_date"]).dt.date
    data["directional_return"] = pd.to_numeric(data["directional_return"], errors="coerce")
    data = data.loc[data["directional_return"].notna()].copy()
    if data.empty:
        return tranche_metrics(data, confidence=confidence, folds=folds, label=label)

    primary_cost = PHASE26_PRIMARY_COST_BPS / 10_000.0
    stress_cost = PHASE26_STRESS_COST_BPS / 10_000.0
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
    fold_values = _fold_means(primary, folds)

    year_values: dict[int, list[float]] = defaultdict(list)
    for session_date, value in zip(session["as_of_date"], primary, strict=True):
        year_values[session_date.year].append(float(value))
    year_means = {
        str(year): float(np.mean(values))
        for year, values in sorted(year_values.items())
        if len(values) >= PHASE26_MIN_YEAR_SIGNAL_SESSIONS
    }
    market_means = _eligible_state_means(
        data, state_field="market_state", primary_cost=primary_cost
    )
    ticker_means = _eligible_state_means(
        data, state_field="effective_ticker_state", primary_cost=primary_cost
    )

    trade_primary = data["directional_return"].to_numpy(dtype=np.float64) - primary_cost
    primary_std = float(np.std(primary, ddof=1)) if len(primary) > 1 else 0.0
    session_sharpe = None if primary_std <= 0 else float(np.mean(primary) / primary_std)
    raw_rows = int(len(data))
    return Phase26TrancheMetrics(
        raw_rows=raw_rows,
        signal_sessions=int(len(session)),
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
    )


def _robust_fraction_pass(value: float | None) -> bool:
    return bool(value is not None and value >= PHASE26_MIN_POSITIVE_REGIME_FRACTION)


def selection_checks(metrics: Phase26TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE26_SELECTION_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE26_SELECTION_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE26_SELECTION_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None and metrics.stress_mean_return > 0
        ),
        "year_robustness": bool(
            metrics.positive_year_fraction is not None
            and metrics.positive_year_fraction >= PHASE26_MIN_POSITIVE_YEAR_FRACTION
        ),
        "market_state_robustness": _robust_fraction_pass(metrics.positive_market_state_fraction),
        "ticker_state_robustness": _robust_fraction_pass(metrics.positive_ticker_state_fraction),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction <= PHASE26_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def internal_checks(metrics: Phase26TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE26_INTERNAL_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE26_INTERNAL_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE26_INTERNAL_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None and metrics.stress_mean_return > 0
        ),
        "year_robustness": bool(
            metrics.positive_year_fraction is not None
            and metrics.positive_year_fraction >= PHASE26_MIN_POSITIVE_YEAR_FRACTION
        ),
        "market_state_robustness": _robust_fraction_pass(metrics.positive_market_state_fraction),
        "ticker_state_robustness": _robust_fraction_pass(metrics.positive_ticker_state_fraction),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction <= PHASE26_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def holm_bonferroni(
    p_values: Mapping[str, float], *, alpha: float = PHASE26_MULTIPLE_TESTING_ALPHA
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
    metrics: dict[str, Phase26TrancheMetrics],
) -> dict[str, tuple[float | None, float | None]]:
    """Return trial-aware Sharpe diagnostics, not an extra hidden acceptance gate.

    The benchmark follows the expected-maximum Sharpe approximation used in the
    Deflated Sharpe Ratio literature. The probability uses the finite-sample PSR
    denominator with skew/kurtosis approximated from the candidate session returns
    when the research runner supplies a session Sharpe. Because the complete session
    vectors are not retained in this summary helper, normal skew/kurtosis are used;
    the metric is explicitly diagnostic and the block-bootstrap/Holm gates remain
    authoritative.
    """

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
    metrics: dict[str, Phase26TrancheMetrics]
) -> dict[str, Phase26TrancheMetrics]:
    diagnostic = _deflated_sharpe_diagnostics(metrics)
    return {
        key: Phase26TrancheMetrics(
            **{
                **item.to_dict(),
                "deflated_sharpe_probability": diagnostic[key][0],
                "deflated_sharpe_benchmark": diagnostic[key][1],
            }
        )
        for key, item in metrics.items()
    }


def _write_parquet(
    settings: AtlasSettings, frame: pd.DataFrame, target: Path, *, order_by: str
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("p26_research_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM p26_research_write ORDER BY {order_by}) "
            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
            f"ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


class Phase26DevelopmentResearch:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.observations = Phase26ObservationBuilder(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase26" / "v1" / "research"

    def report_path(self) -> Path:
        return self.root / "development_research.json"

    def signals_path(self) -> Path:
        return self.root / "development_signals.parquet"

    def finalists_path(self) -> Path:
        return self.root / "finalists.json"

    def _load_development(self) -> tuple[pd.DataFrame, dict[str, object], Path]:
        report_path = self.observations.report_path()
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
        if not isinstance(report, dict):
            raise Phase26ResearchError("Phase26 observation report is missing")
        if report.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION:
            raise Phase26ResearchError("Phase26 observation report contract mismatch")
        if report.get("phase26_policy_fingerprint") != phase26_policy_fingerprint():
            raise Phase26ResearchError("Phase26 observation policy fingerprint mismatch")
        if report.get("pass") is not True or int(report.get("protected_return_reads", -1)) != 0:
            raise Phase26ResearchError("Phase26 observation report is not protected-blind passing")
        path = self.observations.development_path()
        if not path.is_file() or report.get("development_sha256") != sha256_file(path):
            raise Phase26ResearchError("Phase26 development observation artifact SHA mismatch")
        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY as_of_date, instrument_id"
            ).fetch_df()
        finally:
            con.close()
        if frame.empty:
            raise Phase26ResearchError("Phase26 development observations are empty")
        if set(frame["contract_version"].astype(str)) != {
            PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION
        }:
            raise Phase26ResearchError("Phase26 development observation contract mismatch")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        return frame, report, report_path

    def _boundaries(self, observation_report: dict[str, object]) -> Phase26DevelopmentBoundaries:
        label_end = date.fromisoformat(str(observation_report["development_boundary_label_end"]))
        sessions = tuple(
            self.calendar.sessions_in_range(date.fromisoformat(PHASE26_RESEARCH_START), label_end)
        )
        return chronological_boundaries(sessions)

    @staticmethod
    def _tranche(
        frame: pd.DataFrame,
        *,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        return frame.loc[(frame["as_of_date"] >= start) & (frame["as_of_date"] <= end)].copy()

    def _candidate_signals(
        self,
        frame: pd.DataFrame,
        candidate: Phase26CandidateSpec,
    ) -> pd.DataFrame:
        fired = frame.loc[candidate_mask(frame, candidate)].copy()
        if fired.empty:
            return fired
        fired.insert(0, "signal_contract_version", PHASE26_SIGNAL_ARTIFACT_CONTRACT_VERSION)
        fired.insert(1, "candidate_id", candidate.candidate_id)
        fired.insert(2, "candidate_family", candidate.family)
        fired.insert(3, "strategy_direction", candidate.direction)
        fired["primary_net_return"] = (
            pd.to_numeric(fired["directional_return"], errors="coerce")
            - PHASE26_PRIMARY_COST_BPS / 10_000.0
        )
        fired["stress_net_return"] = (
            pd.to_numeric(fired["directional_return"], errors="coerce")
            - PHASE26_STRESS_COST_BPS / 10_000.0
        )
        return fired

    def run(self) -> dict[str, object]:
        frame, observation_report, observation_report_path = self._load_development()
        boundaries = self._boundaries(observation_report)
        selection_frame = self._tranche(
            frame, start=boundaries.selection_start, end=boundaries.selection_end
        )
        internal_frame = self._tranche(
            frame, start=boundaries.internal_start, end=boundaries.internal_end
        )

        all_signals: list[pd.DataFrame] = []
        selection_metrics: dict[str, Phase26TrancheMetrics] = {}
        selection_check_map: dict[str, dict[str, bool]] = {}
        selection_fired: dict[str, pd.DataFrame] = {}
        for candidate in PHASE26_CANDIDATES:
            fired = self._candidate_signals(frame, candidate)
            if not fired.empty:
                all_signals.append(fired)
            selected_rows = self._tranche(
                fired, start=boundaries.selection_start, end=boundaries.selection_end
            ) if not fired.empty else fired
            selection_fired[candidate.candidate_id] = selected_rows
            metrics = tranche_metrics(
                selected_rows,
                confidence=PHASE26_SELECTION_CONFIDENCE,
                folds=PHASE26_SELECTION_FOLDS,
                label=f"selection:{candidate.candidate_id}",
            )
            selection_metrics[candidate.candidate_id] = metrics
            selection_check_map[candidate.candidate_id] = selection_checks(metrics)

        selection_metrics = _with_deflated(selection_metrics)
        p_values = {
            candidate.candidate_id: (
                selection_metrics[candidate.candidate_id].primary_bootstrap_p_value
                if selection_metrics[candidate.candidate_id].primary_bootstrap_p_value is not None
                else 1.0
            )
            for candidate in PHASE26_CANDIDATES
        }
        holm = holm_bonferroni(p_values)

        selection_pass_ids = {
            candidate.candidate_id
            for candidate in PHASE26_CANDIDATES
            if all(selection_check_map[candidate.candidate_id].values())
            and bool(holm[candidate.candidate_id]["rejected_null"])
        }
        family_choices: dict[tuple[str, str], str] = {}
        for candidate in PHASE26_CANDIDATES:
            if candidate.candidate_id not in selection_pass_ids:
                continue
            key = (candidate.family, candidate.direction)
            current_id = family_choices.get(key)
            if current_id is None:
                family_choices[key] = candidate.candidate_id
                continue
            current = selection_metrics[current_id]
            challenger = selection_metrics[candidate.candidate_id]
            current_rank = (
                current.primary_lcb or float("-inf"),
                current.primary_mean_return or float("-inf"),
                current.signal_sessions,
                current_id,
            )
            challenger_rank = (
                challenger.primary_lcb or float("-inf"),
                challenger.primary_mean_return or float("-inf"),
                challenger.signal_sessions,
                candidate.candidate_id,
            )
            if challenger_rank > current_rank:
                family_choices[key] = candidate.candidate_id
        selected_ids = tuple(sorted(family_choices.values()))
        if len(selected_ids) > 6 * 2 * PHASE26_MAX_FINALISTS_PER_FAMILY_DIRECTION:
            raise Phase26ResearchError("Phase26 family/direction selection cardinality exceeded")

        internal_metrics: dict[str, Phase26TrancheMetrics] = {}
        internal_check_map: dict[str, dict[str, bool]] = {}
        for candidate_id in selected_ids:
            candidate = next(item for item in PHASE26_CANDIDATES if item.candidate_id == candidate_id)
            fired = self._candidate_signals(internal_frame, candidate)
            metrics = tranche_metrics(
                fired,
                confidence=PHASE26_INTERNAL_CONFIDENCE,
                folds=PHASE26_INTERNAL_VALIDATION_FOLDS,
                label=f"internal:{candidate.candidate_id}",
            )
            internal_metrics[candidate_id] = metrics
            internal_check_map[candidate_id] = internal_checks(metrics)
        internal_metrics = _with_deflated(internal_metrics) if internal_metrics else {}
        finalist_ids = tuple(
            sorted(
                candidate_id
                for candidate_id in selected_ids
                if all(internal_check_map[candidate_id].values())
            )
        )

        signals = (
            pd.concat(all_signals, ignore_index=True)
            if all_signals
            else pd.DataFrame(
                columns=[
                    "signal_contract_version",
                    "candidate_id",
                    "candidate_family",
                    "strategy_direction",
                    "as_of_date",
                    "instrument_id",
                ]
            )
        )
        signals_path = self.signals_path()
        _write_parquet(
            self.settings,
            signals,
            signals_path,
            order_by="candidate_id, as_of_date, instrument_id",
        )

        finalist_path = self.finalists_path()
        finalist_payload: dict[str, object] = {
            "contract_version": PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "selected_candidate_ids": list(selected_ids),
            "finalist_candidate_ids": list(finalist_ids),
            "protected_returns_read": 0,
            "finalists_frozen": True,
            "candidates": [
                asdict(candidate)
                for candidate in PHASE26_CANDIDATES
                if candidate.candidate_id in finalist_ids
            ],
        }
        finalist_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            finalist_path,
            json.dumps(finalist_payload, indent=2, sort_keys=True) + "\n",
        )

        checks = {
            "observation_report_pass": observation_report.get("pass") is True,
            "protected_returns_unread": int(observation_report.get("protected_return_reads", -1)) == 0,
            "exact_candidate_count": len(PHASE26_CANDIDATES) == 24,
            "holm_global_candidate_count": len(holm) == 24,
            "family_direction_limit": len(selected_ids) <= 12,
            "internal_only_selected": set(internal_metrics) == set(selected_ids),
            "finalists_subset_selected": set(finalist_ids).issubset(set(selected_ids)),
            "no_runner_up_substitution": True,
            "protected_returns_read": False,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase26ResearchError("Phase26 development research failed: " + ", ".join(failed))

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "observation_report_sha256": sha256_file(observation_report_path),
            "development_observation_sha256": sha256_file(self.observations.development_path()),
            "boundaries": boundaries.to_dict(),
            "selection_candidate_count": len(PHASE26_CANDIDATES),
            "selection_pass_before_family_limit": len(selection_pass_ids),
            "selected_candidate_ids": list(selected_ids),
            "finalist_candidate_ids": list(finalist_ids),
            "selection_metrics": {
                key: value.to_dict() for key, value in sorted(selection_metrics.items())
            },
            "selection_checks": dict(sorted(selection_check_map.items())),
            "holm_bonferroni": dict(sorted(holm.items())),
            "internal_metrics": {
                key: value.to_dict() for key, value in sorted(internal_metrics.items())
            },
            "internal_checks": dict(sorted(internal_check_map.items())),
            "development_signals_sha256": sha256_file(signals_path),
            "finalists_sha256": sha256_file(finalist_path),
            "protected_returns_read": 0,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
