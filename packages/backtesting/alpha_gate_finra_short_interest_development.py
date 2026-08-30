from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from packages.backtesting.alpha_gate_finra_short_interest_predictor import (
    FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
    FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE,
    FINRA_SHORT_INTEREST_PREDICTOR_ROWS_RELATIVE,
)
from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
    FINRA_SHORT_INTEREST_BOOTSTRAP_BLOCK_SESSIONS,
    FINRA_SHORT_INTEREST_BOOTSTRAP_REPLICATES,
    FINRA_SHORT_INTEREST_BOOTSTRAP_SEED,
    FINRA_SHORT_INTEREST_DEVELOPMENT_LAST_SIGNAL,
    FINRA_SHORT_INTEREST_DEVELOPMENT_SELECTION_FRACTION,
    FINRA_SHORT_INTEREST_HYPOTHESES,
    FINRA_SHORT_INTEREST_INTERNAL_CONFIDENCE,
    FINRA_SHORT_INTEREST_INTERNAL_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_INTERNAL_MIN_POSITIVE_FOLDS,
    FINRA_SHORT_INTEREST_INTERNAL_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
    FINRA_SHORT_INTEREST_INTERNAL_PURGE_SESSIONS,
    FINRA_SHORT_INTEREST_INTERNAL_VALIDATION_FOLDS,
    FINRA_SHORT_INTEREST_MAX_SINGLE_INSTRUMENT_ROW_FRACTION,
    FINRA_SHORT_INTEREST_MAX_SINGLE_SESSION_ROW_FRACTION,
    FINRA_SHORT_INTEREST_MIN_POSITIVE_YEAR_FRACTION,
    FINRA_SHORT_INTEREST_MIN_YEAR_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_MULTIPLE_TESTING_ALPHA,
    FINRA_SHORT_INTEREST_MULTIPLE_TESTING_METHOD,
    FINRA_SHORT_INTEREST_OUTER_EMBARGO_END,
    FINRA_SHORT_INTEREST_PERFORMANCE_SIGNAL_START,
    FINRA_SHORT_INTEREST_PRIMARY_COST_BPS,
    FINRA_SHORT_INTEREST_PRIMARY_HORIZON_SESSIONS,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
    FINRA_SHORT_INTEREST_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    FINRA_SHORT_INTEREST_PROTECTED_START,
    FINRA_SHORT_INTEREST_RUNNER_UP_SUBSTITUTION_ALLOWED,
    FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
    FINRA_SHORT_INTEREST_SELECTION_CONFIDENCE,
    FINRA_SHORT_INTEREST_SELECTION_FOLDS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_POSITIVE_FOLDS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_SELECTION_MIN_UNIQUE_INSTRUMENTS,
    FINRA_SHORT_INTEREST_SELECTION_WINNER_RULE,
    FINRA_SHORT_INTEREST_STRESS_COST_BPS,
    finra_short_interest_scientific_fingerprint,
)
from packages.backtesting.phase26_observations import (
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    PHASE26_OUTCOME_EVIDENCE_END,
    Phase26ObservationBuilder,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.outcome_probe import MLOutcomeFeasibilityProbe


FINRA_SHORT_INTEREST_DEVELOPMENT_CONTRACT = (
    "alpha-gate-finra-short-interest-development-v1-63-session-spy-relative-protected-blind"
)
FINRA_SHORT_INTEREST_OUTCOME_CONTRACT = (
    "alpha-gate-finra-short-interest-outcome-v1-exact-open-t63-close-spy-relative-split-censored"
)
FINRA_SHORT_INTEREST_FINALIST_CONTRACT = (
    "alpha-gate-finra-short-interest-finalists-v1-selection-internal-protected-source-precheck-returns-unread"
)
FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT = (
    "f5b99a52bf0e9d101b53493e0012a7a60d24b301f904d4b9958dc03638432a5f"
)
FINRA_SHORT_INTEREST_DEVELOPMENT_ROOT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/finra_short_interest_development_v1"
)
FINRA_SHORT_INTEREST_DEVELOPMENT_OUTCOMES_RELATIVE = (
    FINRA_SHORT_INTEREST_DEVELOPMENT_ROOT_RELATIVE / "development_outcomes.jsonl"
)
FINRA_SHORT_INTEREST_FINALISTS_RELATIVE = (
    FINRA_SHORT_INTEREST_DEVELOPMENT_ROOT_RELATIVE / "finalists.json"
)
FINRA_SHORT_INTEREST_DEVELOPMENT_REPORT_RELATIVE = (
    FINRA_SHORT_INTEREST_DEVELOPMENT_ROOT_RELATIVE / "development_study.json"
)

_FORBIDDEN_PREDICTOR_FIELDS = {
    "entry_open",
    "exit_close",
    "spy_entry_open",
    "spy_exit_close",
    "stock_return",
    "spy_return",
    "primary_gross_return",
    "unhedged_gross_return",
}


class FINRAShortInterestDevelopmentError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FINRAShortInterestDevelopmentBoundaries:
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
            "purge_sessions": [value.isoformat() for value in self.purge_sessions],
            "internal_start": self.internal_start.isoformat(),
            "internal_end": self.internal_end.isoformat(),
            "development_session_count": self.development_session_count,
            "selection_session_count": self.selection_session_count,
            "internal_session_count": self.internal_session_count,
        }


@dataclass(frozen=True, slots=True)
class FINRAShortInterestTrancheMetrics:
    raw_rows: int
    signal_sessions: int
    unique_instruments: int
    primary_mean_return: float | None
    unhedged_primary_mean_return: float | None
    primary_lcb: float | None
    primary_bootstrap_p_value: float | None
    stress_mean_return: float | None
    fold_means: tuple[float | None, ...]
    positive_folds: int
    eligible_year_means: dict[str, float]
    positive_year_fraction: float | None
    max_single_session_row_fraction: float | None
    max_single_instrument_row_fraction: float | None
    session_sharpe: float | None
    deflated_sharpe_probability: float | None = None
    deflated_sharpe_benchmark: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def development_implementation_fingerprint() -> str:
    payload = {
        "scientific_fingerprint": FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
        "predictor_contract": FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT,
        "development_contract": FINRA_SHORT_INTEREST_DEVELOPMENT_CONTRACT,
        "outcome_contract": FINRA_SHORT_INTEREST_OUTCOME_CONTRACT,
        "finalist_contract": FINRA_SHORT_INTEREST_FINALIST_CONTRACT,
        "split_policy": "accepted_phase26_split_evidence_censor_decision_open_to_t63_close",
        "selection_rule": (
            "selection_only_global_holm_then_one_direction_winner_internal_confirm"
        ),
        "protected_rule": "source_only_counts_no_return_read",
    }
    return _sha256_text(_canonical_json(payload))


def _load_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        raise FINRAShortInterestDevelopmentError(f"missing JSONL artifact: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FINRAShortInterestDevelopmentError(
                f"invalid JSONL row: {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise FINRAShortInterestDevelopmentError(
                f"JSONL row is not an object: {path}:{line_number}"
            )
        rows.append(value)
    return tuple(rows)


def chronological_boundaries(
    sessions: Iterable[date],
) -> FINRAShortInterestDevelopmentBoundaries:
    ordered = tuple(sorted(set(sessions)))
    if len(ordered) < 200:
        raise FINRAShortInterestDevelopmentError(
            "too few FINRA short-interest development sessions"
        )
    selection_count = int(
        math.floor(len(ordered) * FINRA_SHORT_INTEREST_DEVELOPMENT_SELECTION_FRACTION)
    )
    internal_offset = selection_count + FINRA_SHORT_INTEREST_INTERNAL_PURGE_SESSIONS
    if selection_count <= 0 or internal_offset >= len(ordered):
        raise FINRAShortInterestDevelopmentError(
            "invalid FINRA short-interest selection/internal chronology"
        )
    selection = ordered[:selection_count]
    purge = ordered[selection_count:internal_offset]
    internal = ordered[internal_offset:]
    if len(purge) != FINRA_SHORT_INTEREST_INTERNAL_PURGE_SESSIONS or not internal:
        raise FINRAShortInterestDevelopmentError(
            "FINRA short-interest internal purge partition is incomplete"
        )
    return FINRAShortInterestDevelopmentBoundaries(
        selection_start=selection[0],
        selection_end=selection[-1],
        purge_sessions=purge,
        internal_start=internal[0],
        internal_end=internal[-1],
        development_session_count=len(ordered),
        selection_session_count=len(selection),
        internal_session_count=len(internal),
    )


def holm_bonferroni(
    p_values: Mapping[str, float],
    *,
    alpha: float = FINRA_SHORT_INTEREST_MULTIPLE_TESTING_ALPHA,
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


def _fold_mapping(sessions: tuple[date, ...], folds: int) -> dict[date, int]:
    if len(sessions) < folds:
        raise FINRAShortInterestDevelopmentError(
            "too few sessions for FINRA short-interest fold attribution"
        )
    blocks = [
        tuple(block.tolist())
        for block in np.array_split(np.asarray(sessions, dtype=object), folds)
    ]
    return {
        session: index
        for index, block in enumerate(blocks)
        for session in block
    }


def _derived_seed(label: str) -> int:
    return FINRA_SHORT_INTEREST_BOOTSTRAP_SEED + int(
        hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16
    )


def _bootstrap(
    values: np.ndarray, *, confidence: float, label: str
) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise FINRAShortInterestDevelopmentError(
            "bootstrap requires a nonempty session vector"
        )
    n = len(values)
    block = min(FINRA_SHORT_INTEREST_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(
        0,
        n,
        size=(FINRA_SHORT_INTEREST_BOOTSTRAP_REPLICATES, block_count),
    )
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(
        FINRA_SHORT_INTEREST_BOOTSTRAP_REPLICATES, -1
    )[:, :n]
    sample_means = values[indices].mean(axis=1)
    lower = float(np.quantile(sample_means, 1.0 - confidence))
    observed = float(values.mean())
    null_means = (values - observed)[indices].mean(axis=1)
    p_value = float(
        (1 + np.count_nonzero(null_means >= observed))
        / (len(null_means) + 1)
    )
    return lower, p_value


def _empty_metrics(folds: int) -> FINRAShortInterestTrancheMetrics:
    return FINRAShortInterestTrancheMetrics(
        raw_rows=0,
        signal_sessions=0,
        unique_instruments=0,
        primary_mean_return=None,
        unhedged_primary_mean_return=None,
        primary_lcb=None,
        primary_bootstrap_p_value=None,
        stress_mean_return=None,
        fold_means=tuple(None for _ in range(folds)),
        positive_folds=0,
        eligible_year_means={},
        positive_year_fraction=None,
        max_single_session_row_fraction=None,
        max_single_instrument_row_fraction=None,
        session_sharpe=None,
    )


def tranche_metrics(
    signals: pd.DataFrame,
    *,
    direction: str,
    confidence: float,
    fold_mapping: Mapping[date, int],
    fold_count: int,
    label: str,
) -> FINRAShortInterestTrancheMetrics:
    if signals.empty:
        return _empty_metrics(fold_count)
    if direction not in {"LONG", "SHORT"}:
        raise FINRAShortInterestDevelopmentError(
            f"invalid FINRA short-interest direction {direction!r}"
        )
    data = signals.copy()
    data["decision_session"] = pd.to_datetime(
        data["decision_session"]
    ).dt.date
    if set(data["direction"].astype(str)) != {direction}:
        raise FINRAShortInterestDevelopmentError(
            "candidate direction drifted inside FINRA short-interest tranche"
        )
    for field in ("primary_gross_return", "unhedged_gross_return"):
        data[field] = pd.to_numeric(data[field], errors="coerce")
    finite = np.isfinite(
        data["primary_gross_return"].to_numpy(dtype=float)
    ) & np.isfinite(data["unhedged_gross_return"].to_numpy(dtype=float))
    data = data.loc[finite].copy()
    if data.empty:
        return _empty_metrics(fold_count)

    primary_cost = FINRA_SHORT_INTEREST_PRIMARY_COST_BPS[direction] / 10_000.0
    stress_cost = FINRA_SHORT_INTEREST_STRESS_COST_BPS[direction] / 10_000.0
    session = (
        data.groupby("decision_session", sort=True, observed=True)
        .agg(
            primary_gross_return=("primary_gross_return", "mean"),
            unhedged_gross_return=("unhedged_gross_return", "mean"),
            row_count=("instrument_id", "size"),
        )
        .reset_index()
        .sort_values("decision_session", kind="stable")
    )
    gross = session["primary_gross_return"].to_numpy(dtype=float)
    primary = gross - primary_cost
    unhedged = (
        session["unhedged_gross_return"].to_numpy(dtype=float)
        - primary_cost
    )
    stress = gross - stress_cost
    lower, p_value = _bootstrap(
        primary, confidence=confidence, label=label
    )

    fold_values: list[float | None] = []
    session["fold"] = session["decision_session"].map(fold_mapping)
    if session["fold"].isna().any():
        raise FINRAShortInterestDevelopmentError(
            "FINRA signal session is missing fold attribution"
        )
    for fold in range(fold_count):
        group = session.loc[
            session["fold"] == fold, "primary_gross_return"
        ]
        fold_values.append(
            None if group.empty else float(group.mean() - primary_cost)
        )

    year_values: dict[int, list[float]] = defaultdict(list)
    for session_date, value in zip(
        session["decision_session"], primary, strict=True
    ):
        year_values[session_date.year].append(float(value))
    year_means = {
        str(year): float(np.mean(values))
        for year, values in sorted(year_values.items())
        if len(values) >= FINRA_SHORT_INTEREST_MIN_YEAR_SIGNAL_SESSIONS
    }
    positive_year_fraction = (
        None
        if not year_means
        else float(
            sum(value > 0 for value in year_means.values())
            / len(year_means)
        )
    )
    raw_rows = int(len(data))
    instrument_counts = data.groupby(
        "instrument_id", sort=True, observed=True
    ).size()
    session_std = (
        float(np.std(primary, ddof=1)) if len(primary) > 1 else 0.0
    )
    return FINRAShortInterestTrancheMetrics(
        raw_rows=raw_rows,
        signal_sessions=int(len(session)),
        unique_instruments=int(data["instrument_id"].nunique()),
        primary_mean_return=float(np.mean(primary)),
        unhedged_primary_mean_return=float(np.mean(unhedged)),
        primary_lcb=lower,
        primary_bootstrap_p_value=p_value,
        stress_mean_return=float(np.mean(stress)),
        fold_means=tuple(fold_values),
        positive_folds=sum(
            value is not None and value > 0 for value in fold_values
        ),
        eligible_year_means=year_means,
        positive_year_fraction=positive_year_fraction,
        max_single_session_row_fraction=float(
            session["row_count"].max() / raw_rows
        ),
        max_single_instrument_row_fraction=(
            None
            if instrument_counts.empty
            else float(instrument_counts.max() / raw_rows)
        ),
        session_sharpe=(
            None
            if session_std <= 0
            else float(np.mean(primary) / session_std)
        ),
    )


def with_deflated_diagnostic(
    metrics: Mapping[str, FINRAShortInterestTrancheMetrics],
) -> dict[str, FINRAShortInterestTrancheMetrics]:
    sharpes = np.asarray(
        [
            item.session_sharpe
            for item in metrics.values()
            if item.session_sharpe is not None
        ],
        dtype=float,
    )
    if len(sharpes) < 2 or float(np.std(sharpes, ddof=1)) <= 0:
        return dict(metrics)
    sigma = float(np.std(sharpes, ddof=1))
    trials = max(2, len(metrics))
    normal = NormalDist()
    gamma = 0.5772156649015329
    benchmark = sigma * (
        (1.0 - gamma) * normal.inv_cdf(1.0 - 1.0 / trials)
        + gamma * normal.inv_cdf(1.0 - 1.0 / (trials * math.e))
    )
    result: dict[str, FINRAShortInterestTrancheMetrics] = {}
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
        result[key] = replace(
            item,
            deflated_sharpe_probability=probability,
            deflated_sharpe_benchmark=float(benchmark),
        )
    return result


def _stage_checks(
    metrics: FINRAShortInterestTrancheMetrics,
    *,
    min_event_rows: int,
    min_signal_sessions: int,
    min_unique_instruments: int,
    min_positive_folds: int,
) -> dict[str, bool]:
    return {
        "min_event_rows": metrics.raw_rows >= min_event_rows,
        "min_signal_sessions": (
            metrics.signal_sessions >= min_signal_sessions
        ),
        "min_unique_instruments": (
            metrics.unique_instruments >= min_unique_instruments
        ),
        "positive_folds": metrics.positive_folds >= min_positive_folds,
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
        "unhedged_primary_mean_positive": bool(
            metrics.unhedged_primary_mean_return is not None
            and metrics.unhedged_primary_mean_return > 0
        ),
        "year_robustness": bool(
            metrics.positive_year_fraction is not None
            and metrics.positive_year_fraction
            >= FINRA_SHORT_INTEREST_MIN_POSITIVE_YEAR_FRACTION
        ),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction
            <= FINRA_SHORT_INTEREST_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
        "instrument_concentration": bool(
            metrics.max_single_instrument_row_fraction is not None
            and metrics.max_single_instrument_row_fraction
            <= FINRA_SHORT_INTEREST_MAX_SINGLE_INSTRUMENT_ROW_FRACTION
        ),
    }


def selection_checks(
    metrics: FINRAShortInterestTrancheMetrics,
) -> dict[str, bool]:
    return _stage_checks(
        metrics,
        min_event_rows=FINRA_SHORT_INTEREST_SELECTION_MIN_EVENT_ROWS,
        min_signal_sessions=(
            FINRA_SHORT_INTEREST_SELECTION_MIN_SIGNAL_SESSIONS
        ),
        min_unique_instruments=(
            FINRA_SHORT_INTEREST_SELECTION_MIN_UNIQUE_INSTRUMENTS
        ),
        min_positive_folds=FINRA_SHORT_INTEREST_SELECTION_MIN_POSITIVE_FOLDS,
    )


def internal_checks(
    metrics: FINRAShortInterestTrancheMetrics,
) -> dict[str, bool]:
    return _stage_checks(
        metrics,
        min_event_rows=FINRA_SHORT_INTEREST_INTERNAL_MIN_EVENT_ROWS,
        min_signal_sessions=(
            FINRA_SHORT_INTEREST_INTERNAL_MIN_SIGNAL_SESSIONS
        ),
        min_unique_instruments=(
            FINRA_SHORT_INTEREST_INTERNAL_MIN_UNIQUE_INSTRUMENTS
        ),
        min_positive_folds=FINRA_SHORT_INTEREST_INTERNAL_MIN_POSITIVE_FOLDS,
    )


def protected_source_precheck(
    rows: pd.DataFrame, candidate_id: str
) -> dict[str, object]:
    subset = rows.loc[
        rows["candidate_id"].astype(str).eq(candidate_id)
    ].copy()
    if subset.empty:
        raw_rows = signal_sessions = unique_instruments = 0
        max_session_fraction = max_instrument_fraction = None
    else:
        subset["decision_session"] = pd.to_datetime(
            subset["decision_session"]
        ).dt.date
        raw_rows = int(len(subset))
        signal_sessions = int(subset["decision_session"].nunique())
        unique_instruments = int(subset["instrument_id"].nunique())
        max_session_fraction = float(
            subset.groupby("decision_session", observed=True).size().max()
            / raw_rows
        )
        max_instrument_fraction = float(
            subset.groupby("instrument_id", observed=True).size().max()
            / raw_rows
        )
    gates = {
        "min_event_rows": (
            raw_rows >= FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS
        ),
        "min_signal_sessions": (
            signal_sessions
            >= FINRA_SHORT_INTEREST_PROTECTED_MIN_SIGNAL_SESSIONS
        ),
        "min_unique_instruments": (
            unique_instruments
            >= FINRA_SHORT_INTEREST_PROTECTED_MIN_UNIQUE_INSTRUMENTS
        ),
    }
    return {
        "candidate_id": candidate_id,
        "raw_rows": raw_rows,
        "signal_sessions": signal_sessions,
        "unique_instruments": unique_instruments,
        "max_single_session_row_fraction_diagnostic": max_session_fraction,
        "max_single_instrument_row_fraction_diagnostic": (
            max_instrument_fraction
        ),
        "gates": gates,
        "pass": all(gates.values()),
        "protected_return_rows_read": 0,
    }


class FINRAShortInterestDevelopmentStudy:
    """Open development returns only; protected returns remain unread."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        progress_callback: Any | None = None,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(
            settings.data.calendar.exchange
        )
        self.phase26 = Phase26ObservationBuilder(settings)
        self.progress_callback = progress_callback
        self.derived_root = settings.resolved_path(
            settings.data.paths.derived
        )
        self.predictor_rows_path = (
            self.derived_root
            / FINRA_SHORT_INTEREST_PREDICTOR_ROWS_RELATIVE
        )
        self.predictor_report_path = (
            self.derived_root
            / FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE
        )

    def _progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _read_json(self, path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise FINRAShortInterestDevelopmentError(
                f"missing {label}: {path}"
            )
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise FINRAShortInterestDevelopmentError(
                f"{label} must be a JSON object"
            )
        return value

    def _load_predictors(
        self,
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        report = self._read_json(
            self.predictor_report_path,
            "FINRA short-interest predictor report",
        )
        if (
            report.get("contract_version")
            != FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT
        ):
            raise FINRAShortInterestDevelopmentError(
                "FINRA predictor contract mismatch"
            )
        if (
            report.get("scientific_fingerprint")
            != FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT
        ):
            raise FINRAShortInterestDevelopmentError(
                "FINRA predictor scientific fingerprint mismatch"
            )
        if report.get("status") != "SOURCE_ONLY_PREDICTOR_PASS":
            raise FINRAShortInterestDevelopmentError(
                "source-only predictor population did not PASS"
            )
        if report.get("pass") is not True:
            raise FINRAShortInterestDevelopmentError(
                "source-only predictor pass flag is false"
            )
        if int(report.get("target_outcome_rows_read", -1)) != 0:
            raise FINRAShortInterestDevelopmentError(
                "FINRA predictor artifact was not outcome-blind"
            )
        if int(report.get("protected_return_rows_read", -1)) != 0:
            raise FINRAShortInterestDevelopmentError(
                "FINRA predictor artifact consumed protected returns"
            )
        if report.get("protected_holdout_consumed") is not False:
            raise FINRAShortInterestDevelopmentError(
                "FINRA predictor artifact consumed protected holdout"
            )

        rows = _load_jsonl(self.predictor_rows_path)
        if sha256_file(self.predictor_rows_path) != str(
            report.get("predictor_rows_sha256") or ""
        ):
            raise FINRAShortInterestDevelopmentError(
                "FINRA predictor rows SHA differs from source-only report"
            )
        if len(rows) != int(report.get("predictor_rows", -1)):
            raise FINRAShortInterestDevelopmentError(
                "FINRA predictor row count differs from report"
            )
        candidate_ids = {
            spec.candidate_id for spec in FINRA_SHORT_INTEREST_HYPOTHESES
        }
        for row in rows:
            if (
                row.get("scientific_fingerprint")
                != FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT
            ):
                raise FINRAShortInterestDevelopmentError(
                    "FINRA predictor row scientific fingerprint drifted"
                )
            if str(row.get("candidate_id") or "") not in candidate_ids:
                raise FINRAShortInterestDevelopmentError(
                    "FINRA predictor row contains unknown candidate"
                )
            forbidden = _FORBIDDEN_PREDICTOR_FIELDS.intersection(row)
            if forbidden:
                raise FINRAShortInterestDevelopmentError(
                    "FINRA predictor contains forbidden outcome fields: "
                    + ", ".join(sorted(forbidden))
                )
        development = pd.DataFrame.from_records(
            [
                dict(row)
                for row in rows
                if str(row.get("stage") or "") == "DEVELOPMENT"
            ]
        )
        protected = pd.DataFrame.from_records(
            [
                dict(row)
                for row in rows
                if str(row.get("stage") or "") == "PROTECTED"
            ]
        )
        if development.empty:
            raise FINRAShortInterestDevelopmentError(
                "FINRA development predictor population is empty"
            )
        development["decision_session"] = pd.to_datetime(
            development["decision_session"]
        ).dt.date
        if (
            development["decision_session"].max()
            > date.fromisoformat(
                FINRA_SHORT_INTEREST_DEVELOPMENT_LAST_SIGNAL
            )
        ):
            raise FINRAShortInterestDevelopmentError(
                "FINRA development predictor crossed frozen boundary"
            )
        if not protected.empty:
            protected["decision_session"] = pd.to_datetime(
                protected["decision_session"]
            ).dt.date
            if (
                protected["decision_session"].min()
                < date.fromisoformat(FINRA_SHORT_INTEREST_PROTECTED_START)
            ):
                raise FINRAShortInterestDevelopmentError(
                    "FINRA protected predictor crossed frozen start"
                )
        return development, protected, report

    def _split_evidence(self) -> tuple[pd.DataFrame, str]:
        report = self._read_json(
            self.phase26.report_path(),
            "accepted Phase26 observation report",
        )
        if (
            report.get("contract_version")
            != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION
            or report.get("pass") is not True
        ):
            raise FINRAShortInterestDevelopmentError(
                "accepted Phase26 split evidence is unavailable"
            )
        if int(report.get("protected_return_reads", -1)) != 0:
            raise FINRAShortInterestDevelopmentError(
                "accepted split evidence is attached to consumed protected returns"
            )
        path = MLOutcomeFeasibilityProbe(
            self.settings
        ).split_evidence_path(PHASE26_OUTCOME_EVIDENCE_END)
        expected_sha = str(report.get("split_evidence_sha256") or "")
        if (
            not path.is_file()
            or len(expected_sha) != 64
            or sha256_file(path) != expected_sha
        ):
            raise FINRAShortInterestDevelopmentError(
                "accepted split evidence SHA mismatch"
            )
        records: list[dict[str, object]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                continue
            ticker = str(payload.get("ticker") or "").strip()
            raw_date = str(payload.get("execution_date") or "").strip()
            try:
                execution_date = date.fromisoformat(raw_date)
            except ValueError:
                continue
            if ticker:
                records.append(
                    {
                        "ticker": ticker,
                        "execution_date": execution_date,
                    }
                )
        return (
            pd.DataFrame.from_records(
                records, columns=["ticker", "execution_date"]
            ),
            expected_sha,
        )

    def _boundaries_and_exits(
        self, predictors: pd.DataFrame
    ) -> tuple[
        FINRAShortInterestDevelopmentBoundaries,
        pd.DataFrame,
        tuple[date, ...],
        tuple[date, ...],
    ]:
        start = date.fromisoformat(
            FINRA_SHORT_INTEREST_PERFORMANCE_SIGNAL_START
        )
        development_last = date.fromisoformat(
            FINRA_SHORT_INTEREST_DEVELOPMENT_LAST_SIGNAL
        )
        outer_end = date.fromisoformat(
            FINRA_SHORT_INTEREST_OUTER_EMBARGO_END
        )
        development_sessions = tuple(
            self.calendar.sessions_in_range(start, development_last)
        )
        boundary = chronological_boundaries(development_sessions)
        full_grid = tuple(self.calendar.sessions_in_range(start, outer_end))
        positions = {
            session: index for index, session in enumerate(full_grid)
        }
        frame = predictors.copy()
        exits: list[date] = []
        for decision in frame["decision_session"]:
            index = positions.get(decision)
            if (
                index is None
                or index + FINRA_SHORT_INTEREST_PRIMARY_HORIZON_SESSIONS
                >= len(full_grid)
            ):
                raise FINRAShortInterestDevelopmentError(
                    f"cannot resolve frozen 63-session exit for {decision}"
                )
            exits.append(
                full_grid[
                    index + FINRA_SHORT_INTEREST_PRIMARY_HORIZON_SESSIONS
                ]
            )
        frame["exit_session"] = exits
        if frame["exit_session"].max() > outer_end:
            raise FINRAShortInterestDevelopmentError(
                "FINRA development outcome crossed outer embargo end"
            )
        selection_sessions = tuple(
            session
            for session in development_sessions
            if boundary.selection_start
            <= session
            <= boundary.selection_end
        )
        internal_sessions = tuple(
            session
            for session in development_sessions
            if boundary.internal_start
            <= session
            <= boundary.internal_end
        )
        return (
            boundary,
            frame,
            selection_sessions,
            internal_sessions,
        )

    def _development_outcomes(
        self, predictors: pd.DataFrame, splits: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        self._progress(
            "opening development-only exact entry/exit paths for "
            f"{len(predictors)} predictor rows"
        )
        columns = [
            "candidate_id",
            "direction",
            "instrument_id",
            "ticker",
            "decision_session",
            "exit_session",
            "settlement_date",
            "publication_date",
            "current_short_position",
            "previous_short_position",
            "position_change_log_ratio",
            "days_to_cover",
            "change_percentile",
            "crowding_percentile",
        ]
        query = predictors[columns].copy().reset_index(drop=True)
        query.insert(
            0, "row_id", np.arange(len(query), dtype=np.int64)
        )
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        con = connect_utc(":memory:")
        try:
            con.execute("SET preserve_insertion_order=false")
            con.register("finra_predictors", query)
            con.register("finra_splits", splits)
            result = con.execute(
                f"""
                WITH needed AS (
                    SELECT ticker AS symbol,
                           CAST(decision_session AS DATE) AS session_date
                    FROM finra_predictors
                    UNION
                    SELECT ticker, CAST(exit_session AS DATE)
                    FROM finra_predictors
                    UNION
                    SELECT 'SPY', CAST(decision_session AS DATE)
                    FROM finra_predictors
                    UNION
                    SELECT 'SPY', CAST(exit_session AS DATE)
                    FROM finra_predictors
                ), bars AS (
                    SELECT b.symbol,
                           CAST(b.session_date AS DATE) AS session_date,
                           CAST(b.open AS DOUBLE) AS session_open,
                           CAST(b.close AS DOUBLE) AS session_close
                    FROM read_parquet(
                        {sql_string(bar_glob)},
                        union_by_name=true,
                        hive_partitioning=false
                    ) b
                    INNER JOIN needed n
                      ON n.symbol = b.symbol
                     AND n.session_date = CAST(b.session_date AS DATE)
                )
                SELECT p.*,
                       se.session_open AS entry_open,
                       sx.session_close AS exit_close,
                       pe.session_open AS spy_entry_open,
                       px.session_close AS spy_exit_close,
                       EXISTS (
                           SELECT 1
                           FROM finra_splits s
                           WHERE s.ticker = p.ticker
                             AND CAST(s.execution_date AS DATE)
                                 > CAST(p.decision_session AS DATE)
                             AND CAST(s.execution_date AS DATE)
                                 <= CAST(p.exit_session AS DATE)
                       ) AS split_crossing
                FROM finra_predictors p
                LEFT JOIN bars se
                  ON se.symbol = p.ticker
                 AND se.session_date
                     = CAST(p.decision_session AS DATE)
                LEFT JOIN bars sx
                  ON sx.symbol = p.ticker
                 AND sx.session_date
                     = CAST(p.exit_session AS DATE)
                LEFT JOIN bars pe
                  ON pe.symbol = 'SPY'
                 AND pe.session_date
                     = CAST(p.decision_session AS DATE)
                LEFT JOIN bars px
                  ON px.symbol = 'SPY'
                 AND px.session_date
                     = CAST(p.exit_session AS DATE)
                ORDER BY p.row_id
                """
            ).fetch_df()
        finally:
            con.close()
        if len(result) != len(query):
            raise FINRAShortInterestDevelopmentError(
                "FINRA exact outcome join cardinality drifted; "
                "duplicate daily keys suspected"
            )
        result["decision_session"] = pd.to_datetime(
            result["decision_session"]
        ).dt.date
        result["exit_session"] = pd.to_datetime(
            result["exit_session"]
        ).dt.date
        for field in (
            "entry_open",
            "exit_close",
            "spy_entry_open",
            "spy_exit_close",
        ):
            result[field] = pd.to_numeric(
                result[field], errors="coerce"
            )
        spy_missing = (
            result["spy_entry_open"].isna()
            | result["spy_exit_close"].isna()
            | ~np.isfinite(
                result["spy_entry_open"].to_numpy(dtype=float)
            )
            | ~np.isfinite(
                result["spy_exit_close"].to_numpy(dtype=float)
            )
            | result["spy_entry_open"].le(0)
            | result["spy_exit_close"].le(0)
        )
        if bool(spy_missing.any()):
            raise FINRAShortInterestDevelopmentError(
                "SPY benchmark is missing an exact frozen entry/exit session"
            )
        stock_missing = (
            result["entry_open"].isna()
            | result["exit_close"].isna()
            | ~np.isfinite(result["entry_open"].to_numpy(dtype=float))
            | ~np.isfinite(result["exit_close"].to_numpy(dtype=float))
            | result["entry_open"].le(0)
            | result["exit_close"].le(0)
        )
        split_crossing = (
            result["split_crossing"].fillna(False).astype(bool)
        )
        usable = result.loc[
            ~stock_missing & ~split_crossing
        ].copy()
        if usable.empty:
            raise FINRAShortInterestDevelopmentError(
                "FINRA development outcomes are empty after "
                "path-quality censoring"
            )
        usable["stock_return"] = (
            usable["exit_close"] / usable["entry_open"] - 1.0
        )
        usable["spy_return"] = (
            usable["spy_exit_close"] / usable["spy_entry_open"] - 1.0
        )
        direction = np.where(
            usable["direction"].astype(str).eq("LONG"), 1.0, -1.0
        )
        usable["primary_gross_return"] = direction * (
            usable["stock_return"] - usable["spy_return"]
        )
        usable["unhedged_gross_return"] = (
            direction * usable["stock_return"]
        )
        for field in (
            "stock_return",
            "spy_return",
            "primary_gross_return",
            "unhedged_gross_return",
        ):
            if not np.isfinite(
                usable[field].to_numpy(dtype=float)
            ).all():
                raise FINRAShortInterestDevelopmentError(
                    f"nonfinite FINRA development {field}"
                )
        usable.insert(
            0,
            "outcome_contract_version",
            FINRA_SHORT_INTEREST_OUTCOME_CONTRACT,
        )
        usable = usable.drop(columns=["split_crossing"])
        return usable, {
            "development_predictor_rows_opened": int(len(result)),
            "exact_stock_path_missing_rows": int(stock_missing.sum()),
            "split_crossing_censored_rows": int(
                split_crossing.sum()
            ),
            "usable_development_rows": int(len(usable)),
        }

    def run(self) -> dict[str, Any]:
        if (
            finra_short_interest_scientific_fingerprint()
            != FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT
        ):
            raise FINRAShortInterestDevelopmentError(
                "frozen FINRA scientific policy fingerprint drifted"
            )
        if (
            development_implementation_fingerprint()
            != FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
        ):
            raise FINRAShortInterestDevelopmentError(
                "FINRA development implementation fingerprint drifted"
            )
        if FINRA_SHORT_INTEREST_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED:
            raise FINRAShortInterestDevelopmentError(
                "protected-return blindness contract drifted"
            )
        if FINRA_SHORT_INTEREST_RUNNER_UP_SUBSTITUTION_ALLOWED:
            raise FINRAShortInterestDevelopmentError(
                "runner-up substitution contract drifted"
            )
        if (
            FINRA_SHORT_INTEREST_MULTIPLE_TESTING_METHOD
            != "HOLM_BONFERRONI_GLOBAL_4"
        ):
            raise FINRAShortInterestDevelopmentError(
                "FINRA multiplicity method drifted"
            )
        if (
            FINRA_SHORT_INTEREST_SELECTION_WINNER_RULE
            != "highest_primary_selection_LCB_then_candidate_id_within_direction"
        ):
            raise FINRAShortInterestDevelopmentError(
                "FINRA selection winner rule drifted"
            )

        development, protected, predictor_report = (
            self._load_predictors()
        )
        (
            boundary,
            development,
            selection_sessions,
            internal_sessions,
        ) = self._boundaries_and_exits(development)
        splits, split_sha = self._split_evidence()
        outcomes, outcome_diagnostics = self._development_outcomes(
            development, splits
        )

        selection_mapping = _fold_mapping(
            selection_sessions, FINRA_SHORT_INTEREST_SELECTION_FOLDS
        )
        internal_mapping = _fold_mapping(
            internal_sessions,
            FINRA_SHORT_INTEREST_INTERNAL_VALIDATION_FOLDS,
        )
        selection_metrics: dict[
            str, FINRAShortInterestTrancheMetrics
        ] = {}
        selection_gate_results: dict[
            str, dict[str, bool]
        ] = {}
        directions = {
            spec.candidate_id: spec.direction
            for spec in FINRA_SHORT_INTEREST_HYPOTHESES
        }
        for spec in FINRA_SHORT_INTEREST_HYPOTHESES:
            candidate = outcomes.loc[
                outcomes["candidate_id"]
                .astype(str)
                .eq(spec.candidate_id)
                & outcomes["decision_session"].between(
                    boundary.selection_start, boundary.selection_end
                )
            ].copy()
            metrics = tranche_metrics(
                candidate,
                direction=spec.direction,
                confidence=FINRA_SHORT_INTEREST_SELECTION_CONFIDENCE,
                fold_mapping=selection_mapping,
                fold_count=FINRA_SHORT_INTEREST_SELECTION_FOLDS,
                label=f"selection:{spec.candidate_id}",
            )
            selection_metrics[spec.candidate_id] = metrics
            selection_gate_results[spec.candidate_id] = (
                selection_checks(metrics)
            )
        selection_metrics = with_deflated_diagnostic(
            selection_metrics
        )

        p_values = {
            candidate_id: (
                1.0
                if metrics.primary_bootstrap_p_value is None
                else metrics.primary_bootstrap_p_value
            )
            for candidate_id, metrics in selection_metrics.items()
        }
        holm = holm_bonferroni(p_values)
        selection_passers = [
            candidate_id
            for candidate_id in directions
            if all(
                selection_gate_results[candidate_id].values()
            )
            and bool(holm[candidate_id]["rejected_null"])
        ]
        winners: list[str] = []
        for direction_name in ("LONG", "SHORT"):
            eligible = [
                candidate_id
                for candidate_id in selection_passers
                if directions[candidate_id] == direction_name
            ]
            eligible.sort(
                key=lambda candidate_id: (
                    -float(
                        selection_metrics[
                            candidate_id
                        ].primary_lcb
                        or float("-inf")
                    ),
                    candidate_id,
                )
            )
            if eligible:
                winners.append(eligible[0])

        internal_metrics: dict[
            str, FINRAShortInterestTrancheMetrics
        ] = {}
        internal_gate_results: dict[
            str, dict[str, bool]
        ] = {}
        internal_finalists: list[str] = []
        for candidate_id in winners:
            candidate = outcomes.loc[
                outcomes["candidate_id"]
                .astype(str)
                .eq(candidate_id)
                & outcomes["decision_session"].between(
                    boundary.internal_start, boundary.internal_end
                )
            ].copy()
            metrics = tranche_metrics(
                candidate,
                direction=directions[candidate_id],
                confidence=FINRA_SHORT_INTEREST_INTERNAL_CONFIDENCE,
                fold_mapping=internal_mapping,
                fold_count=(
                    FINRA_SHORT_INTEREST_INTERNAL_VALIDATION_FOLDS
                ),
                label=f"internal:{candidate_id}",
            )
            internal_metrics[candidate_id] = metrics
            checks = internal_checks(metrics)
            internal_gate_results[candidate_id] = checks
            if all(checks.values()):
                internal_finalists.append(candidate_id)

        protected_prechecks = {
            candidate_id: protected_source_precheck(
                protected, candidate_id
            )
            for candidate_id in internal_finalists
        }
        protected_return_eligible = [
            candidate_id
            for candidate_id in internal_finalists
            if bool(protected_prechecks[candidate_id]["pass"])
        ]

        outcome_records = []
        for row in outcomes.to_dict(orient="records"):
            outcome_records.append(
                {
                    key: (
                        value.isoformat()
                        if isinstance(value, date)
                        else value
                    )
                    for key, value in row.items()
                }
            )
        outcome_text = "".join(
            _canonical_json(row) + "\n" for row in outcome_records
        )
        outcome_path = (
            self.derived_root
            / FINRA_SHORT_INTEREST_DEVELOPMENT_OUTCOMES_RELATIVE
        )
        atomic_write_text(outcome_path, outcome_text)

        finalist_artifact = {
            "contract_version": (
                FINRA_SHORT_INTEREST_FINALIST_CONTRACT
            ),
            "scientific_fingerprint": (
                FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT
            ),
            "development_implementation_fingerprint": (
                FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
            ),
            "selection_winners": winners,
            "internal_finalists": internal_finalists,
            "protected_source_prechecks": protected_prechecks,
            "protected_return_eligible_finalists": (
                protected_return_eligible
            ),
            "runner_up_substitution_allowed": False,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
        }
        finalist_path = (
            self.derived_root / FINRA_SHORT_INTEREST_FINALISTS_RELATIVE
        )
        atomic_write_text(
            finalist_path,
            json.dumps(
                finalist_artifact, indent=2, sort_keys=True
            )
            + "\n",
        )

        if protected_return_eligible:
            status = "DEVELOPMENT_PASS_FINALISTS_READY_PROTECTED"
        elif internal_finalists:
            status = (
                "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT"
            )
        else:
            status = "ACCEPTED_NEGATIVE_DEVELOPMENT"

        report = {
            "contract_version": (
                FINRA_SHORT_INTEREST_DEVELOPMENT_CONTRACT
            ),
            "scientific_fingerprint": (
                FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT
            ),
            "development_implementation_fingerprint": (
                FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
            ),
            "status": status,
            "pass": True,
            "predictor_contract": (
                FINRA_SHORT_INTEREST_PREDICTOR_CONTRACT
            ),
            "predictor_report_sha256": sha256_file(
                self.predictor_report_path
            ),
            "predictor_rows_sha256": sha256_file(
                self.predictor_rows_path
            ),
            "predictor_source_files_read": int(
                predictor_report.get(
                    "finra_source_files_read", 0
                )
            ),
            "predictor_reference_snapshots_read": int(
                predictor_report.get(
                    "massive_reference_snapshots_read", 0
                )
            ),
            "split_evidence_sha256": split_sha,
            "boundaries": boundary.to_dict(),
            "outcome_diagnostics": outcome_diagnostics,
            "selection_metrics": {
                key: value.to_dict()
                for key, value in sorted(
                    selection_metrics.items()
                )
            },
            "selection_checks": selection_gate_results,
            "holm_bonferroni": holm,
            "selection_passers": selection_passers,
            "selection_winners": winners,
            "internal_metrics": {
                key: value.to_dict()
                for key, value in sorted(
                    internal_metrics.items()
                )
            },
            "internal_checks": internal_gate_results,
            "internal_finalists": internal_finalists,
            "protected_source_prechecks": protected_prechecks,
            "protected_return_eligible_finalists": (
                protected_return_eligible
            ),
            "development_outcomes_path": str(outcome_path),
            "development_outcomes_sha256": _sha256_text(
                outcome_text
            ),
            "finalists_path": str(finalist_path),
            "finalists_sha256": sha256_file(finalist_path),
            "target_outcome_rows_read": int(len(outcomes)),
            "protected_predictor_rows_read_for_source_precheck": int(
                len(protected)
            ),
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "automatic_broker_failover": False,
            "phase33_signal_to_trade_authority": False,
            "next_scientific_action": (
                "If one or more finalists pass the frozen protected "
                "source-only precheck, open protected returns once for only "
                "those finalists; otherwise close this mechanism without support."
            ),
        }
        report_path = (
            self.derived_root
            / FINRA_SHORT_INTEREST_DEVELOPMENT_REPORT_RELATIVE
        )
        atomic_write_text(
            report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        report["report_path"] = str(report_path)
        return report
