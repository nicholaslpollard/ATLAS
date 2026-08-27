from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase29_blindness import (
    PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase29ProtectedBlindnessAudit,
)
from .phase29_confirmation import (
    PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE29_SUPPORT_OVERLAY_CONTRACT_VERSION,
    Phase29ProtectedConfirmation,
)
from .phase29_policy import (
    PHASE29_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE29_BOOTSTRAP_REPLICATES,
    PHASE29_BOOTSTRAP_SEED,
    PHASE29_CANDIDATES,
    PHASE29_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE29_INTERNAL_MIN_RAW_ROWS,
    PHASE29_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE29_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE29_MIN_POSITIVE_REGIME_FRACTION,
    PHASE29_MIN_POSITIVE_YEAR_FRACTION,
    PHASE29_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE29_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE29_MULTIPLE_TESTING_ALPHA,
    PHASE29_PAIR_MIN_SPREAD_STD,
    PHASE29_PCA_COMPONENTS,
    PHASE29_PCA_MIN_PEERS,
    PHASE29_PRIMARY_COST_BPS,
    PHASE29_PROTECTED_CONFIDENCE,
    PHASE29_PROTECTED_MIN_POSITIVE_FOLDS,
    PHASE29_PROTECTED_MIN_RAW_ROWS,
    PHASE29_PROTECTED_MIN_SIGNAL_SESSIONS,
    PHASE29_SELECTION_CONFIDENCE,
    PHASE29_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE29_SELECTION_MIN_RAW_ROWS,
    PHASE29_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE29_SIGNAL_TAIL_FRACTION,
    PHASE29_STRESS_COST_BPS,
    Phase29CandidateSpec,
    phase29_policy_fingerprint,
)
from .phase29_population import (
    PHASE29_DEVELOPMENT_FRAME_CONTRACT_VERSION,
    PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
    PHASE29_PROTECTED_FRAME_CONTRACT_VERSION,
    Phase29PopulationBuilder,
)
from .phase29_research import (
    PHASE29_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase29DevelopmentResearch,
)


PHASE29_VALIDATION_CONTRACT_VERSION = (
    "phase29-independent-validation-v1-raw-relative-value-tail-economics-holm-protected"
)


class Phase29IndependentValidationError(RuntimeError):
    pass


def _json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase29IndependentValidationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase29IndependentValidationError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase29IndependentValidationError(f"{label} must be a JSON object")
    return payload


def _parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase29IndependentValidationError(f"missing parquet artifact: {path}")
    con = connect_utc(":memory:")
    try:
        frame = con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY {order_by}"
        ).fetch_df()
    finally:
        con.close()
    return frame


def _candidate(candidate_id: str) -> Phase29CandidateSpec:
    try:
        return next(item for item in PHASE29_CANDIDATES if item.candidate_id == candidate_id)
    except StopIteration as exc:
        raise Phase29IndependentValidationError(f"unknown Phase29 candidate: {candidate_id}") from exc


def _independent_pca_residuals(
    formation_returns: pd.DataFrame, current_returns: pd.Series
) -> dict[str, tuple[float, float]]:
    formation = formation_returns.apply(pd.to_numeric, errors="coerce").astype(float)
    if len(formation) != 60 or len(formation.columns) < PHASE29_PCA_MIN_PEERS:
        raise Phase29IndependentValidationError("independent PCA geometry mismatch")
    if not np.isfinite(formation.to_numpy(dtype=float)).all():
        raise Phase29IndependentValidationError("independent PCA formation is nonfinite")
    means = formation.mean(axis=0).to_numpy(dtype=float)
    stds = formation.std(axis=0, ddof=0).to_numpy(dtype=float)
    if np.any(stds <= 0.0) or not np.isfinite(stds).all():
        raise Phase29IndependentValidationError("independent PCA variance is invalid")
    x = (formation.to_numpy(dtype=float) - means[None, :]) / stds[None, :]
    _, _, vt = np.linalg.svd(x, full_matrices=False)
    loadings = vt[:PHASE29_PCA_COMPONENTS, :].T
    current = pd.to_numeric(current_returns.reindex(formation.columns), errors="coerce").to_numpy(
        dtype=float
    )
    if not np.isfinite(current).all():
        raise Phase29IndependentValidationError("independent PCA current returns are incomplete")
    current_z = (current - means) / stds
    result: dict[str, tuple[float, float]] = {}
    for index, instrument_id in enumerate(formation.columns.astype(str)):
        mask = np.ones(len(formation.columns), dtype=bool)
        mask[index] = False
        score, _, rank, _ = np.linalg.lstsq(loadings[mask, :], current_z[mask], rcond=None)
        if int(rank) < PHASE29_PCA_COMPONENTS:
            raise Phase29IndependentValidationError("independent leave-focal PCA solve is rank-deficient")
        reconstruction = float(loadings[index, :] @ score)
        result[str(instrument_id)] = (float(current_z[index] - reconstruction), reconstruction)
    return result


def _independent_pairs(
    formation_closes: pd.DataFrame, current_closes: pd.Series
) -> dict[str, tuple[str, float, float]]:
    formation = formation_closes.apply(pd.to_numeric, errors="coerce").astype(float)
    if len(formation) != 60 or not np.isfinite(formation.to_numpy(dtype=float)).all():
        raise Phase29IndependentValidationError("independent pair formation geometry mismatch")
    if np.any(formation.to_numpy(dtype=float) <= 0.0):
        raise Phase29IndependentValidationError("independent pair closes are nonpositive")
    ids = [str(value) for value in formation.columns]
    values = formation.to_numpy(dtype=float)
    normalized = values / values[0, :][None, :]
    current = pd.to_numeric(current_closes.reindex(formation.columns), errors="coerce").to_numpy(
        dtype=float
    )
    current_norm = current / values[0, :]
    result: dict[str, tuple[str, float, float]] = {}
    for focal_index, focal_id in enumerate(ids):
        choices: list[tuple[float, str, int]] = []
        for peer_index, peer_id in enumerate(ids):
            if peer_index == focal_index:
                continue
            diff = normalized[:, focal_index] - normalized[:, peer_index]
            distance = float(np.dot(diff, diff))
            if np.isfinite(distance):
                choices.append((distance, peer_id, peer_index))
        choices.sort(key=lambda item: (item[0], item[1]))
        if not choices:
            continue
        distance, peer_id, peer_index = choices[0]
        spread = normalized[:, focal_index] - normalized[:, peer_index]
        mean = float(np.mean(spread))
        std = float(np.std(spread, ddof=0))
        if not np.isfinite(std) or std <= PHASE29_PAIR_MIN_SPREAD_STD:
            continue
        current_spread = float(current_norm[focal_index] - current_norm[peer_index])
        z_value = float((current_spread - mean) / std)
        result[focal_id] = (peer_id, float(distance), z_value)
    return result


def _independent_tail(frame: pd.DataFrame, candidate: Phase29CandidateSpec) -> pd.DataFrame:
    direction = "bullish" if candidate.direction == "LONG" else "bearish"
    work = frame.loc[frame["direction"].astype(str) == direction].copy()
    work["phase29_score"] = (
        pd.to_numeric(work[candidate.raw_signal_field], errors="coerce") * candidate.orientation
    )
    if not np.isfinite(work["phase29_score"].to_numpy(dtype=float)).all():
        raise Phase29IndependentValidationError("independent Phase29 score is nonfinite")
    selected: list[pd.DataFrame] = []
    for _, group in work.groupby("as_of_date", sort=True, observed=True):
        ordered = group.sort_values(
            ["phase29_score", "instrument_id"], ascending=[False, True], kind="stable"
        )
        count = max(1, int(math.ceil(PHASE29_SIGNAL_TAIL_FRACTION * len(ordered))))
        selected.append(ordered.iloc[:count].copy())
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        if selected
        else work.iloc[0:0].copy()
    )


def _keys(frame: pd.DataFrame) -> tuple[tuple[str, date, str], ...]:
    if frame.empty:
        return ()
    work = frame.copy()
    work["as_of_date"] = pd.to_datetime(work["as_of_date"]).dt.date
    if "candidate_id" not in work.columns:
        raise Phase29IndependentValidationError("candidate_id missing from key artifact")
    return tuple(
        sorted(
            (str(row.candidate_id), row.as_of_date, str(row.instrument_id))
            for row in work.itertuples(index=False)
        )
    )


def _derived_seed(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return PHASE29_BOOTSTRAP_SEED + int(digest[:8], 16)


def _bootstrap(values: np.ndarray, *, confidence: float, label: str) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        raise Phase29IndependentValidationError("independent bootstrap is empty")
    block = min(PHASE29_BOOTSTRAP_BLOCK_SESSIONS, n)
    blocks = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE29_BOOTSTRAP_REPLICATES, blocks))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(PHASE29_BOOTSTRAP_REPLICATES, -1)[
        :, :n
    ]
    sample_means = values[indices].mean(axis=1)
    lower = float(np.quantile(sample_means, 1.0 - confidence))
    observed = float(values.mean())
    centered = values - observed
    null_means = centered[indices].mean(axis=1)
    p_value = float((1 + np.count_nonzero(null_means >= observed)) / (len(null_means) + 1))
    return lower, p_value


def _state_fraction(signals: pd.DataFrame, field: str, primary_cost: float) -> float | None:
    work = signals[["as_of_date", field, "directional_return"]].copy()
    work[field] = work[field].astype("string").fillna("<UNAVAILABLE>")
    grouped = (
        work.groupby([field, "as_of_date"], sort=True, observed=True)["directional_return"]
        .mean()
        .reset_index()
    )
    values: list[float] = []
    for _, group in grouped.groupby(field, sort=True, observed=True):
        if group["as_of_date"].nunique() < PHASE29_MIN_REGIME_SIGNAL_SESSIONS:
            continue
        values.append(float(group["directional_return"].mean() - primary_cost))
    return None if not values else float(sum(value > 0 for value in values) / len(values))


def _metrics(signals: pd.DataFrame, *, confidence: float, fold_field: str, label: str) -> dict[str, object]:
    work = signals.copy()
    work["as_of_date"] = pd.to_datetime(work["as_of_date"]).dt.date
    if work.empty:
        return {
            "raw_rows": 0,
            "signal_sessions": 0,
            "primary_mean_return": None,
            "stress_mean_return": None,
            "primary_lcb": None,
            "primary_bootstrap_p_value": None,
            "positive_folds": 0,
            "positive_year_fraction": None,
            "positive_market_state_fraction": None,
            "positive_ticker_state_fraction": None,
            "max_single_session_row_fraction": None,
        }
    primary_cost = PHASE29_PRIMARY_COST_BPS / 10_000.0
    stress_cost = PHASE29_STRESS_COST_BPS / 10_000.0
    session = (
        work.groupby("as_of_date", sort=True, observed=True)["directional_return"]
        .agg(["mean", "size"])
        .reset_index()
    )
    primary = session["mean"].to_numpy(dtype=float) - primary_cost
    stress = session["mean"].to_numpy(dtype=float) - stress_cost
    lower, p_value = _bootstrap(primary, confidence=confidence, label=label)
    mapping = work[["as_of_date", fold_field]].drop_duplicates()
    merged = session.merge(mapping, on="as_of_date", how="left", validate="one_to_one")
    fold_means = [
        float(group["mean"].mean() - primary_cost)
        for _, group in merged.groupby(fold_field, sort=True, observed=True)
    ]
    by_year: dict[int, list[float]] = {}
    for session_date, value in zip(session["as_of_date"], primary, strict=True):
        by_year.setdefault(session_date.year, []).append(float(value))
    year_means = [
        float(np.mean(values))
        for _, values in sorted(by_year.items())
        if len(values) >= PHASE29_MIN_YEAR_SIGNAL_SESSIONS
    ]
    year_fraction = (
        None if not year_means else float(sum(value > 0 for value in year_means) / len(year_means))
    )
    return {
        "raw_rows": int(len(work)),
        "signal_sessions": int(len(session)),
        "primary_mean_return": float(np.mean(primary)),
        "stress_mean_return": float(np.mean(stress)),
        "primary_lcb": lower,
        "primary_bootstrap_p_value": p_value,
        "positive_folds": int(sum(value > 0 for value in fold_means)),
        "positive_year_fraction": year_fraction,
        "positive_market_state_fraction": _state_fraction(work, "market_state", primary_cost),
        "positive_ticker_state_fraction": _state_fraction(
            work, "effective_ticker_state", primary_cost
        ),
        "max_single_session_row_fraction": float(session["size"].max() / len(work)),
    }


def _selection_checks(metrics: Mapping[str, object]) -> dict[str, bool]:
    return {
        "min_raw_rows": int(metrics["raw_rows"]) >= PHASE29_SELECTION_MIN_RAW_ROWS,
        "min_signal_sessions": int(metrics["signal_sessions"])
        >= PHASE29_SELECTION_MIN_SIGNAL_SESSIONS,
        "positive_folds": int(metrics["positive_folds"]) >= PHASE29_SELECTION_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics["primary_mean_return"] is not None
            and float(metrics["primary_mean_return"]) > 0
        ),
        "primary_lcb_positive": bool(
            metrics["primary_lcb"] is not None and float(metrics["primary_lcb"]) > 0
        ),
        "stress_mean_positive": bool(
            metrics["stress_mean_return"] is not None
            and float(metrics["stress_mean_return"]) > 0
        ),
        "year_robustness": bool(
            metrics["positive_year_fraction"] is not None
            and float(metrics["positive_year_fraction"]) >= PHASE29_MIN_POSITIVE_YEAR_FRACTION
        ),
        "market_state_robustness": bool(
            metrics["positive_market_state_fraction"] is not None
            and float(metrics["positive_market_state_fraction"])
            >= PHASE29_MIN_POSITIVE_REGIME_FRACTION
        ),
        "ticker_state_robustness": bool(
            metrics["positive_ticker_state_fraction"] is not None
            and float(metrics["positive_ticker_state_fraction"])
            >= PHASE29_MIN_POSITIVE_REGIME_FRACTION
        ),
        "session_concentration": bool(
            metrics["max_single_session_row_fraction"] is not None
            and float(metrics["max_single_session_row_fraction"])
            <= PHASE29_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def _internal_checks(metrics: Mapping[str, object]) -> dict[str, bool]:
    return {
        "min_raw_rows": int(metrics["raw_rows"]) >= PHASE29_INTERNAL_MIN_RAW_ROWS,
        "min_signal_sessions": int(metrics["signal_sessions"])
        >= PHASE29_INTERNAL_MIN_SIGNAL_SESSIONS,
        "positive_folds": int(metrics["positive_folds"]) >= PHASE29_INTERNAL_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics["primary_mean_return"] is not None
            and float(metrics["primary_mean_return"]) > 0
        ),
        "primary_lcb_positive": bool(
            metrics["primary_lcb"] is not None and float(metrics["primary_lcb"]) > 0
        ),
        "stress_mean_positive": bool(
            metrics["stress_mean_return"] is not None
            and float(metrics["stress_mean_return"]) > 0
        ),
        "session_concentration": bool(
            metrics["max_single_session_row_fraction"] is not None
            and float(metrics["max_single_session_row_fraction"])
            <= PHASE29_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def _protected_checks(metrics: Mapping[str, object]) -> dict[str, bool]:
    return {
        "min_raw_rows": int(metrics["raw_rows"]) >= PHASE29_PROTECTED_MIN_RAW_ROWS,
        "min_signal_sessions": int(metrics["signal_sessions"])
        >= PHASE29_PROTECTED_MIN_SIGNAL_SESSIONS,
        "positive_folds": int(metrics["positive_folds"]) >= PHASE29_PROTECTED_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics["primary_mean_return"] is not None
            and float(metrics["primary_mean_return"]) > 0
        ),
        "primary_lcb_positive": bool(
            metrics["primary_lcb"] is not None and float(metrics["primary_lcb"]) > 0
        ),
        "stress_mean_positive": bool(
            metrics["stress_mean_return"] is not None
            and float(metrics["stress_mean_return"]) > 0
        ),
        "session_concentration": bool(
            metrics["max_single_session_row_fraction"] is not None
            and float(metrics["max_single_session_row_fraction"])
            <= PHASE29_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def _holm(p_values: Mapping[str, float]) -> dict[str, dict[str, object]]:
    ordered = sorted((float(value), str(key)) for key, value in p_values.items())
    active = True
    result: dict[str, dict[str, object]] = {}
    for index, (p_value, key) in enumerate(ordered):
        threshold = PHASE29_MULTIPLE_TESTING_ALPHA / (len(ordered) - index)
        reject = bool(active and p_value <= threshold)
        result[key] = {"p_value": p_value, "threshold": threshold, "rejected_null": reject}
        if not reject:
            active = False
    return result


def _close_enough(left: object, right: object, *, atol: float = 1e-12) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return bool(np.isclose(float(left), float(right), rtol=1e-10, atol=atol))


class Phase29IndependentValidator:
    """Independent reconstruction of Phase29 relational evidence and decisions."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase29PopulationBuilder(settings)
        self.research = Phase29DevelopmentResearch(settings)
        self.blindness = Phase29ProtectedBlindnessAudit(settings)
        self.confirmation = Phase29ProtectedConfirmation(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase29" / "v1" / "validation"

    def report_path(self) -> Path:
        return self.root / "independent_validation.json"

    def _network_sample_reconciliation(self, development: pd.DataFrame) -> dict[str, object]:
        dates = tuple(sorted(set(pd.to_datetime(development["as_of_date"]).dt.date)))
        if not dates:
            raise Phase29IndependentValidationError("Phase29 validation population has no dates")
        indices = sorted(set((0, len(dates) // 2, len(dates) - 1)))
        sample_dates = tuple(dates[index] for index in indices)

        observation, _, _, _ = self.population._source_evidence()
        source, _ = self.population._source_frames(observation)
        source = source.loc[source["as_of_date"].isin(sample_dates)].copy()
        splits, _, _ = self.population.phase26._split_evidence()
        history, expected_by_date, _, _ = self.population._history_rows(source, splits=splits)
        reconciled_rows = 0
        max_abs_pca_error = 0.0
        max_abs_pair_error = 0.0
        pair_identity_mismatches = 0

        persisted = development.copy()
        persisted["as_of_date"] = pd.to_datetime(persisted["as_of_date"]).dt.date
        for observation_date in sample_dates:
            expected = expected_by_date.get(observation_date)
            h = history.loc[history["observation_date"] == observation_date].copy()
            if expected is None or h.empty:
                continue
            matrix = h.pivot(
                index="history_date", columns="peer_instrument_id", values="close"
            ).reindex(expected)
            numeric = matrix.apply(pd.to_numeric, errors="coerce").astype(float)
            complete = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=0) & (
                numeric.to_numpy(dtype=float) > 0
            ).all(axis=0)
            numeric = numeric.loc[:, complete]
            if len(numeric.columns) < PHASE29_PCA_MIN_PEERS:
                continue
            formation_61 = numeric.iloc[:-1]
            formation_returns = formation_61.pct_change(fill_method=None).iloc[1:]
            current_returns = numeric.iloc[-1] / numeric.iloc[-2] - 1.0
            pca = _independent_pca_residuals(formation_returns, current_returns)
            pairs = _independent_pairs(formation_61.iloc[-60:], numeric.iloc[-1])
            pgroup = persisted.loc[persisted["as_of_date"] == observation_date]
            for row in pgroup.itertuples(index=False):
                focal_id = str(row.instrument_id)
                if focal_id not in pca or focal_id not in pairs:
                    continue
                pca_error = abs(float(row.pca_residual_dislocation) - pca[focal_id][0])
                pair_error = abs(float(row.distance_pair_spread_z) - pairs[focal_id][2])
                max_abs_pca_error = max(max_abs_pca_error, pca_error)
                max_abs_pair_error = max(max_abs_pair_error, pair_error)
                if str(row.phase29_pair_peer_instrument_id) != pairs[focal_id][0]:
                    pair_identity_mismatches += 1
                reconciled_rows += 1
        return {
            "sample_dates": [item.isoformat() for item in sample_dates],
            "reconciled_rows": reconciled_rows,
            "max_abs_pca_error": max_abs_pca_error,
            "max_abs_pair_z_error": max_abs_pair_error,
            "pair_identity_mismatches": pair_identity_mismatches,
            "pass": bool(
                reconciled_rows > 0
                and max_abs_pca_error <= 1e-9
                and max_abs_pair_error <= 1e-9
                and pair_identity_mismatches == 0
            ),
        }

    def run(self) -> dict[str, object]:
        population_path = self.population.report_path()
        research_path = self.research.report_path()
        finalists_path = self.research.finalists_path()
        blindness_path = self.blindness.report_path()
        confirmation_path = self.confirmation.report_path()
        support_path = self.confirmation.support_overlay_path()
        population_report = _json(population_path, "Phase29 population")
        research = _json(research_path, "Phase29 research")
        finalists = _json(finalists_path, "Phase29 finalists")
        blindness = _json(blindness_path, "Phase29 blindness")
        confirmation = _json(confirmation_path, "Phase29 confirmation")
        support = _json(support_path, "Phase29 support overlay")

        development = _parquet(
            self.population.development_path(), order_by="as_of_date, instrument_id"
        )
        protected = _parquet(
            self.population.protected_path(), order_by="as_of_date, instrument_id"
        )
        predictions = _parquet(
            self.research.predictions_path(),
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )
        signals = _parquet(
            self.research.signals_path(),
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )
        development["as_of_date"] = pd.to_datetime(development["as_of_date"]).dt.date
        protected["as_of_date"] = pd.to_datetime(protected["as_of_date"]).dt.date
        predictions["as_of_date"] = pd.to_datetime(predictions["as_of_date"]).dt.date
        signals["as_of_date"] = pd.to_datetime(signals["as_of_date"]).dt.date

        sample = self._network_sample_reconciliation(development)
        boundaries = research.get("boundaries")
        if not isinstance(boundaries, dict):
            raise Phase29IndependentValidationError("Phase29 boundaries are malformed")
        selection_start = date.fromisoformat(str(boundaries["selection_start"]))
        selection_end = date.fromisoformat(str(boundaries["selection_end"]))
        internal_start = date.fromisoformat(str(boundaries["internal_start"]))
        internal_end = date.fromisoformat(str(boundaries["internal_end"]))
        selection_frame = development.loc[
            (development["as_of_date"] >= selection_start)
            & (development["as_of_date"] <= selection_end)
        ].copy()
        internal_frame = development.loc[
            (development["as_of_date"] >= internal_start)
            & (development["as_of_date"] <= internal_end)
        ].copy()

        independent_selection_metrics: dict[str, dict[str, object]] = {}
        independent_selection_checks: dict[str, dict[str, bool]] = {}
        selection_key_match: dict[str, bool] = {}
        for candidate in PHASE29_CANDIDATES:
            fired = _independent_tail(selection_frame, candidate)
            persisted = signals.loc[
                (signals["research_stage"].astype(str) == "SELECTION")
                & (signals["candidate_id"].astype(str) == candidate.candidate_id)
            ].copy()
            candidate_fired = fired.copy()
            candidate_fired.insert(0, "candidate_id", candidate.candidate_id)
            selection_key_match[candidate.candidate_id] = _keys(candidate_fired) == _keys(persisted)
            if "selection_fold" in persisted.columns:
                fold_map = persisted[["as_of_date", "selection_fold"]].drop_duplicates()
                fired = fired.merge(fold_map, on="as_of_date", how="left", validate="many_to_one")
            metrics = _metrics(
                fired,
                confidence=PHASE29_SELECTION_CONFIDENCE,
                fold_field="selection_fold",
                label=f"selection:{candidate.candidate_id}",
            )
            independent_selection_metrics[candidate.candidate_id] = metrics
            independent_selection_checks[candidate.candidate_id] = _selection_checks(metrics)

        p_values = {
            candidate_id: float(metrics["primary_bootstrap_p_value"] or 1.0)
            for candidate_id, metrics in independent_selection_metrics.items()
        }
        independent_holm = _holm(p_values)
        survivors = tuple(
            sorted(
                candidate.candidate_id
                for candidate in PHASE29_CANDIDATES
                if all(independent_selection_checks[candidate.candidate_id].values())
                and bool(independent_holm[candidate.candidate_id]["rejected_null"])
            )
        )
        winner_ids: list[str] = []
        for direction in ("LONG", "SHORT"):
            eligible = [
                candidate
                for candidate in PHASE29_CANDIDATES
                if candidate.direction == direction and candidate.candidate_id in survivors
            ]
            eligible.sort(
                key=lambda candidate: (
                    -float(independent_selection_metrics[candidate.candidate_id]["primary_lcb"]),
                    -float(
                        independent_selection_metrics[candidate.candidate_id]["primary_mean_return"]
                    ),
                    candidate.candidate_id,
                )
            )
            if eligible:
                winner_ids.append(eligible[0].candidate_id)

        independent_internal_checks: dict[str, dict[str, bool]] = {}
        internal_key_match: dict[str, bool] = {}
        for candidate_id in winner_ids:
            candidate = _candidate(candidate_id)
            fired = _independent_tail(internal_frame, candidate)
            persisted = signals.loc[
                (signals["research_stage"].astype(str) == "INTERNAL_VALIDATION")
                & (signals["candidate_id"].astype(str) == candidate_id)
            ].copy()
            keyed = fired.copy()
            keyed.insert(0, "candidate_id", candidate_id)
            internal_key_match[candidate_id] = _keys(keyed) == _keys(persisted)
            fold_map = persisted[["as_of_date", "internal_fold"]].drop_duplicates()
            fired = fired.merge(fold_map, on="as_of_date", how="left", validate="many_to_one")
            metrics = _metrics(
                fired,
                confidence=0.90,
                fold_field="internal_fold",
                label=f"internal:{candidate_id}",
            )
            independent_internal_checks[candidate_id] = _internal_checks(metrics)
        finalist_ids = tuple(
            sorted(
                candidate_id
                for candidate_id in winner_ids
                if all(independent_internal_checks[candidate_id].values())
            )
        )

        reported_survivors = tuple(sorted(str(value) for value in research.get("selection_survivor_ids", [])))
        reported_winners = tuple(str(value) for value in research.get("selection_winner_ids", []))
        reported_finalists = tuple(sorted(str(value) for value in research.get("finalist_ids", [])))
        protected_checks_match = True
        supported_ids: tuple[str, ...]
        protected_tail_match = True
        protected_metric_match = True
        if not finalist_ids:
            supported_ids = ()
            protected_checks_match = bool(
                confirmation.get("status") == "SKIPPED_ZERO_FINALISTS"
                and int(confirmation.get("protected_candidate_rows_read", -1)) == 0
                and int(confirmation.get("protected_returns_read", -1)) == 0
                and confirmation.get("protected_holdout_consumed") is False
                and not self.confirmation.read_plan_path().exists()
                and not self.confirmation.protected_predictions_path().exists()
                and not self.confirmation.protected_score_signals_path().exists()
                and not self.confirmation.protected_signals_path().exists()
            )
        else:
            score_signals = _parquet(
                self.confirmation.protected_score_signals_path(),
                order_by="candidate_id, as_of_date, instrument_id",
            )
            protected_signals = _parquet(
                self.confirmation.protected_signals_path(),
                order_by="candidate_id, as_of_date, instrument_id",
            )
            independent_confirmed: list[str] = []
            for candidate_id in finalist_ids:
                candidate = _candidate(candidate_id)
                fired = _independent_tail(protected, candidate)
                keyed = fired.copy()
                keyed.insert(0, "candidate_id", candidate_id)
                persisted_score = score_signals.loc[
                    score_signals["candidate_id"].astype(str) == candidate_id
                ].copy()
                protected_tail_match = protected_tail_match and _keys(keyed) == _keys(
                    persisted_score
                )
                observed = protected_signals.loc[
                    protected_signals["candidate_id"].astype(str) == candidate_id
                ].copy()
                if observed.empty:
                    checks = _protected_checks(_metrics(
                        observed,
                        confidence=PHASE29_PROTECTED_CONFIDENCE,
                        fold_field="protected_fold",
                        label=f"protected:{candidate_id}",
                    ))
                else:
                    if "protected_fold" not in observed.columns:
                        protected_metric_match = False
                        checks = {}
                    else:
                        metrics = _metrics(
                            observed,
                            confidence=PHASE29_PROTECTED_CONFIDENCE,
                            fold_field="protected_fold",
                            label=f"protected:{candidate_id}",
                        )
                        checks = _protected_checks(metrics)
                protected_checks_match = protected_checks_match and checks == (
                    confirmation.get("protected_checks", {}).get(candidate_id, {})
                    if isinstance(confirmation.get("protected_checks"), dict)
                    else {}
                )
                if checks and all(checks.values()):
                    independent_confirmed.append(candidate_id)
            supported_ids = tuple(sorted(independent_confirmed))

        reported_support = tuple(
            sorted(str(value) for value in support.get("supported_candidate_ids", []))
        )
        report_metrics = research.get("selection_metrics")
        report_checks = research.get("selection_checks")
        metrics_match = isinstance(report_metrics, dict) and isinstance(report_checks, dict)
        if metrics_match:
            for candidate_id, metrics in independent_selection_metrics.items():
                expected = report_metrics.get(candidate_id, {})
                if not isinstance(expected, dict):
                    metrics_match = False
                    break
                for field in (
                    "raw_rows",
                    "signal_sessions",
                    "primary_mean_return",
                    "stress_mean_return",
                    "primary_lcb",
                    "primary_bootstrap_p_value",
                    "positive_folds",
                ):
                    left = metrics.get(field)
                    right = expected.get(field)
                    if field in ("raw_rows", "signal_sessions", "positive_folds"):
                        if left != right:
                            metrics_match = False
                            break
                    elif not _close_enough(left, right):
                        metrics_match = False
                        break
                if not metrics_match or independent_selection_checks[candidate_id] != report_checks.get(
                    candidate_id
                ):
                    metrics_match = False
                    break

        checks = {
            "population_contract": population_report.get("contract_version")
            == PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
            "research_contract": research.get("contract_version")
            == PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
            "finalist_contract": finalists.get("contract_version")
            == PHASE29_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "blindness_contract": blindness.get("contract_version")
            == PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "confirmation_contract": confirmation.get("contract_version")
            == PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "support_contract": support.get("contract_version")
            == PHASE29_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "policy_fingerprint_consistent": all(
                payload.get("phase29_policy_fingerprint") == phase29_policy_fingerprint()
                for payload in (population_report, research, finalists, blindness, confirmation, support)
            ),
            "all_stage_reports_pass": all(
                payload.get("pass") is True
                for payload in (population_report, research, blindness, confirmation)
            ),
            "development_row_contract": set(development["phase29_contract_version"].astype(str))
            == {PHASE29_DEVELOPMENT_FRAME_CONTRACT_VERSION},
            "protected_row_contract": set(protected["phase29_contract_version"].astype(str))
            == {PHASE29_PROTECTED_FRAME_CONTRACT_VERSION},
            "independent_raw_relative_value_sample": sample.get("pass") is True,
            "selection_tail_keys_match": all(selection_key_match.values()),
            "selection_metrics_checks_match": metrics_match,
            "holm_global_four_match": independent_holm == research.get("holm_bonferroni"),
            "selection_survivors_match": survivors == reported_survivors,
            "selection_winners_match": tuple(winner_ids) == reported_winners,
            "internal_tail_keys_match": all(internal_key_match.values()),
            "finalists_match": finalist_ids == reported_finalists,
            "finalists_artifact_match": reported_finalists
            == tuple(sorted(str(value) for value in finalists.get("finalist_ids", []))),
            "protected_tail_match": protected_tail_match,
            "protected_metric_match": protected_metric_match,
            "protected_checks_match": protected_checks_match,
            "supported_ids_match": supported_ids == reported_support,
            "support_historical_only": support.get("authority")
            == "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY",
            "relative_value_confirmation_only": support.get("relative_value_confirmation_only") is True,
            "no_market_neutral_execution_authority": support.get(
                "market_neutral_pair_execution_authority"
            )
            is False,
            "no_paper_authority": support.get("paper_authority") is False,
            "no_live_authority": support.get("live_authority") is False,
            "blindness_pre_read_pass": blindness.get("pass") is True
            and int(blindness.get("protected_returns_read", -1)) == 0
            and blindness.get("protected_holdout_consumed") is False,
            "external_activity_zero": all(
                int(payload.get(field, -1)) == 0
                for payload in (population_report, research, blindness, confirmation)
                for field in (
                    "provider_reads",
                    "provider_writes",
                    "broker_reads",
                    "broker_writes",
                    "order_writes",
                    "paper_submits",
                    "live_writes",
                )
            ),
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase29IndependentValidationError(
                "Phase29 independent validation failed: " + ", ".join(failed)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE29_VALIDATION_CONTRACT_VERSION,
            "phase29_policy_fingerprint": phase29_policy_fingerprint(),
            "population_report_sha256": sha256_file(population_path),
            "research_report_sha256": sha256_file(research_path),
            "finalists_sha256": sha256_file(finalists_path),
            "blindness_audit_sha256": sha256_file(blindness_path),
            "confirmation_report_sha256": sha256_file(confirmation_path),
            "support_overlay_sha256": sha256_file(support_path),
            "raw_relative_value_sample_reconciliation": sample,
            "selection_survivor_ids": list(survivors),
            "selection_winner_ids": list(winner_ids),
            "finalist_ids": list(finalist_ids),
            "supported_candidate_ids": list(supported_ids),
            "protected_candidate_rows_read": int(
                confirmation.get("protected_candidate_rows_read", 0)
            ),
            "protected_returns_read": int(confirmation.get("protected_returns_read", 0)),
            "protected_holdout_consumed": bool(
                confirmation.get("protected_holdout_consumed", False)
            ),
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
