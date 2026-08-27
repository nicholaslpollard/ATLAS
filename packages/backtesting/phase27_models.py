from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from itertools import product
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge

from .phase27_policy import (
    PHASE27_HGB_L2_REGULARIZATION_GRID,
    PHASE27_HGB_LEARNING_RATE_GRID,
    PHASE27_HGB_MAX_ITER_GRID,
    PHASE27_HGB_MAX_LEAF_NODES_GRID,
    PHASE27_HGB_MIN_SAMPLES_LEAF,
    PHASE27_INNER_TUNING_FOLDS,
    PHASE27_PAIRWISE_C_GRID,
    PHASE27_PAIRWISE_MAX_UNORDERED_PAIRS_PER_SESSION,
    PHASE27_PAIRWISE_SEED,
    PHASE27_PURGE_SESSIONS,
    PHASE27_RIDGE_ALPHA_GRID,
    PHASE27_SIGNAL_TAIL_FRACTION,
    Phase27CandidateSpec,
)
from .phase27_population import transformed_feature_names


class Phase27ModelError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_index: int
    train_sessions: tuple[date, ...]
    purge_sessions: tuple[date, ...]
    validation_sessions: tuple[date, ...]


@dataclass(frozen=True, slots=True)
class Phase27FittedModel:
    family: str
    params: dict[str, object]
    estimator: Any

    def score(self, frame: pd.DataFrame) -> np.ndarray:
        x = frame.loc[:, list(transformed_feature_names())].to_numpy(dtype=np.float64, copy=True)
        if self.family in {"ridge_relative_return", "hgb_relative_return"}:
            values = np.asarray(self.estimator.predict(x), dtype=np.float64)
        elif self.family == "pairwise_logistic_rank":
            values = np.asarray(self.estimator.decision_function(x), dtype=np.float64)
        else:
            raise Phase27ModelError(f"unknown learned model family: {self.family}")
        if values.ndim != 1 or len(values) != len(frame) or not np.isfinite(values).all():
            raise Phase27ModelError("Phase27 model produced invalid scores")
        return values


def direction_label(candidate: Phase27CandidateSpec) -> str:
    return "bullish" if candidate.direction == "LONG" else "bearish"


def candidate_direction_frame(frame: pd.DataFrame, candidate: Phase27CandidateSpec) -> pd.DataFrame:
    return frame.loc[frame["direction"].astype(str) == direction_label(candidate)].copy()


def expanding_walk_forward_folds(
    sessions: Iterable[date], *, validation_folds: int, purge_sessions: int = PHASE27_PURGE_SESSIONS
) -> tuple[WalkForwardFold, ...]:
    ordered = tuple(sorted(set(sessions)))
    if validation_folds < 1:
        raise Phase27ModelError("validation_folds must be positive")
    if len(ordered) < (validation_folds + 1) * 2 + purge_sessions:
        raise Phase27ModelError("too few sessions for Phase27 expanding walk-forward folds")
    blocks = [tuple(block.tolist()) for block in np.array_split(np.asarray(ordered, dtype=object), validation_folds + 1)]
    if any(not block for block in blocks):
        raise Phase27ModelError("Phase27 walk-forward block is empty")
    result: list[WalkForwardFold] = []
    for index in range(1, len(blocks)):
        validation = blocks[index]
        validation_start = validation[0]
        prior = tuple(item for block in blocks[:index] for item in block if item < validation_start)
        if len(prior) <= purge_sessions:
            continue
        purge = prior[-purge_sessions:] if purge_sessions else ()
        train = prior[:-purge_sessions] if purge_sessions else prior
        if not train or not validation:
            continue
        result.append(
            WalkForwardFold(
                fold_index=len(result),
                train_sessions=tuple(train),
                purge_sessions=tuple(purge),
                validation_sessions=tuple(validation),
            )
        )
    if len(result) != validation_folds:
        raise Phase27ModelError(
            f"expected {validation_folds} walk-forward folds, built {len(result)}"
        )
    return tuple(result)


def _slice_sessions(frame: pd.DataFrame, sessions: tuple[date, ...]) -> pd.DataFrame:
    allowed = set(sessions)
    return frame.loc[frame["as_of_date"].isin(allowed)].copy()


def _session_spearman(frame: pd.DataFrame, scores: np.ndarray) -> float | None:
    if len(frame) != len(scores):
        raise Phase27ModelError("score/frame length mismatch")
    data = frame[["as_of_date", "directional_return"]].copy()
    data["score"] = scores
    correlations: list[float] = []
    for _, group in data.groupby("as_of_date", sort=True, observed=True):
        if len(group) < 3:
            continue
        x = group["score"].rank(method="average").to_numpy(dtype=np.float64)
        y = group["directional_return"].rank(method="average").to_numpy(dtype=np.float64)
        if np.std(x) <= 0 or np.std(y) <= 0:
            continue
        correlation = float(np.corrcoef(x, y)[0, 1])
        if math.isfinite(correlation):
            correlations.append(correlation)
    return None if not correlations else float(np.mean(correlations))


def _stable_session_seed(session_date: date) -> int:
    digest = hashlib.sha256(session_date.isoformat().encode("utf-8")).hexdigest()
    return PHASE27_PAIRWISE_SEED + int(digest[:8], 16)


def _pairwise_training_data(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    features = list(transformed_feature_names())
    x_rows: list[np.ndarray] = []
    y_rows: list[int] = []
    for session_date, group in frame.groupby("as_of_date", sort=True, observed=True):
        ordered = group.sort_values(
            ["directional_return", "instrument_id"], ascending=[True, True], kind="stable"
        ).reset_index(drop=True)
        if len(ordered) < 2:
            continue
        values = ordered.loc[:, features].to_numpy(dtype=np.float64, copy=True)
        targets = pd.to_numeric(ordered["directional_return"], errors="coerce").to_numpy(dtype=np.float64)
        pairs = [(lo, hi) for lo in range(len(ordered)) for hi in range(lo + 1, len(ordered)) if targets[hi] > targets[lo]]
        if not pairs:
            continue
        cap = PHASE27_PAIRWISE_MAX_UNORDERED_PAIRS_PER_SESSION
        if len(pairs) > cap:
            rng = np.random.default_rng(_stable_session_seed(session_date))
            chosen = np.sort(rng.choice(len(pairs), size=cap, replace=False))
            pairs = [pairs[int(index)] for index in chosen]
        for lo, hi in pairs:
            difference = values[hi] - values[lo]
            x_rows.append(difference)
            y_rows.append(1)
            x_rows.append(-difference)
            y_rows.append(0)
    if not x_rows:
        raise Phase27ModelError("pairwise ranking produced no training pairs")
    x = np.vstack(x_rows).astype(np.float64, copy=False)
    y = np.asarray(y_rows, dtype=np.int8)
    if not np.isfinite(x).all() or set(np.unique(y)) != {0, 1}:
        raise Phase27ModelError("pairwise ranking training matrix is invalid")
    return x, y


def fit_learned_model(
    frame: pd.DataFrame,
    candidate: Phase27CandidateSpec,
    params: Mapping[str, object],
) -> Phase27FittedModel:
    if not candidate.learned:
        raise Phase27ModelError("priority baseline does not fit a learned model")
    if frame.empty:
        raise Phase27ModelError("cannot fit Phase27 model on empty frame")
    features = list(transformed_feature_names())
    x = frame.loc[:, features].to_numpy(dtype=np.float64, copy=True)
    target = pd.to_numeric(frame["relative_directional_return"], errors="coerce").to_numpy(dtype=np.float64)
    if not np.isfinite(x).all() or not np.isfinite(target).all():
        raise Phase27ModelError("Phase27 training matrix contains non-finite values")

    if candidate.family == "ridge_relative_return":
        estimator = Ridge(alpha=float(params["alpha"]), fit_intercept=True)
        estimator.fit(x, target)
    elif candidate.family == "hgb_relative_return":
        estimator = HistGradientBoostingRegressor(
            loss="squared_error",
            max_leaf_nodes=int(params["max_leaf_nodes"]),
            learning_rate=float(params["learning_rate"]),
            max_iter=int(params["max_iter"]),
            l2_regularization=float(params["l2_regularization"]),
            min_samples_leaf=PHASE27_HGB_MIN_SAMPLES_LEAF,
            early_stopping=False,
            random_state=PHASE27_PAIRWISE_SEED,
        )
        estimator.fit(x, target)
    elif candidate.family == "pairwise_logistic_rank":
        pair_x, pair_y = _pairwise_training_data(frame)
        estimator = LogisticRegression(
            C=float(params["C"]),
            l1_ratio=0.0,
            solver="lbfgs",
            fit_intercept=True,
            max_iter=1000,
            random_state=PHASE27_PAIRWISE_SEED,
        )
        estimator.fit(pair_x, pair_y)
    else:
        raise Phase27ModelError(f"unsupported Phase27 model family: {candidate.family}")
    return Phase27FittedModel(candidate.family, dict(params), estimator)


def candidate_param_grid(candidate: Phase27CandidateSpec) -> tuple[dict[str, object], ...]:
    if candidate.family == "discovery_priority_baseline":
        return ({},)
    if candidate.family == "ridge_relative_return":
        return tuple({"alpha": float(alpha)} for alpha in PHASE27_RIDGE_ALPHA_GRID)
    if candidate.family == "hgb_relative_return":
        return tuple(
            {
                "max_leaf_nodes": int(leaves),
                "learning_rate": float(rate),
                "max_iter": int(iterations),
                "l2_regularization": float(l2),
            }
            for leaves, rate, iterations, l2 in product(
                PHASE27_HGB_MAX_LEAF_NODES_GRID,
                PHASE27_HGB_LEARNING_RATE_GRID,
                PHASE27_HGB_MAX_ITER_GRID,
                PHASE27_HGB_L2_REGULARIZATION_GRID,
            )
        )
    if candidate.family == "pairwise_logistic_rank":
        return tuple({"C": float(value)} for value in PHASE27_PAIRWISE_C_GRID)
    raise Phase27ModelError(f"unknown Phase27 candidate family: {candidate.family}")


def _complexity_key(candidate: Phase27CandidateSpec, params: Mapping[str, object]) -> tuple[object, ...]:
    if candidate.family == "ridge_relative_return":
        # If tuning IC ties, larger alpha is the more regularized/simpler Ridge model.
        return (-float(params["alpha"]),)
    if candidate.family == "hgb_relative_return":
        return (
            int(params["max_leaf_nodes"]),
            int(params["max_iter"]),
            float(params["learning_rate"]),
            -float(params["l2_regularization"]),
        )
    if candidate.family == "pairwise_logistic_rank":
        # Smaller C means stronger regularization for logistic ranking.
        return (float(params["C"]),)
    return ()


def tune_hyperparameters(
    training_frame: pd.DataFrame,
    candidate: Phase27CandidateSpec,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    if not candidate.learned:
        return {}, []
    directional = candidate_direction_frame(training_frame, candidate)
    sessions = tuple(sorted(set(directional["as_of_date"])))
    folds = expanding_walk_forward_folds(
        sessions, validation_folds=PHASE27_INNER_TUNING_FOLDS
    )
    trials: list[dict[str, object]] = []
    for params in candidate_param_grid(candidate):
        fold_ics: list[float] = []
        for fold in folds:
            train = _slice_sessions(directional, fold.train_sessions)
            validation = _slice_sessions(directional, fold.validation_sessions)
            if train.empty or validation.empty:
                raise Phase27ModelError("Phase27 inner tuning fold is empty")
            model = fit_learned_model(train, candidate, params)
            ic = _session_spearman(validation, model.score(validation))
            if ic is not None:
                fold_ics.append(ic)
        mean_ic = None if not fold_ics else float(np.mean(fold_ics))
        trials.append(
            {
                "params": dict(params),
                "fold_ics": fold_ics,
                "mean_session_spearman_ic": mean_ic,
            }
        )
    valid = [item for item in trials if item["mean_session_spearman_ic"] is not None]
    if not valid:
        raise Phase27ModelError(f"no valid tuning trial for {candidate.candidate_id}")
    valid.sort(
        key=lambda item: (
            -float(item["mean_session_spearman_ic"]),
            _complexity_key(candidate, item["params"]),
            json.dumps(item["params"], sort_keys=True),
        )
    )
    return dict(valid[0]["params"]), trials


def score_candidate(
    frame: pd.DataFrame,
    candidate: Phase27CandidateSpec,
    *,
    model: Phase27FittedModel | None = None,
) -> pd.DataFrame:
    directional = candidate_direction_frame(frame, candidate)
    if directional.empty:
        return directional.assign(phase27_score=pd.Series(dtype=float))
    result = directional.copy()
    if candidate.family == "discovery_priority_baseline":
        score = pd.to_numeric(result["priority_score"], errors="coerce").to_numpy(dtype=np.float64)
    else:
        if model is None:
            raise Phase27ModelError(f"learned candidate {candidate.candidate_id} requires model")
        score = model.score(result)
    if not np.isfinite(score).all():
        raise Phase27ModelError("candidate score contains non-finite values")
    result["phase27_score"] = score
    return result


def select_fixed_tail(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return scored.copy()
    selected: list[pd.DataFrame] = []
    for _, group in scored.groupby("as_of_date", sort=True, observed=True):
        ordered = group.sort_values(
            ["phase27_score", "instrument_id"],
            ascending=[False, True],
            kind="stable",
        )
        count = max(1, int(math.ceil(PHASE27_SIGNAL_TAIL_FRACTION * len(ordered))))
        selected.append(ordered.iloc[:count].copy())
    return pd.concat(selected, ignore_index=True).sort_values(
        ["as_of_date", "instrument_id"], kind="stable"
    ).reset_index(drop=True)


def selection_oos_signals(
    selection_frame: pd.DataFrame,
    candidate: Phase27CandidateSpec,
    *,
    outer_folds: int,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    """Create strictly out-of-sample selection predictions and fixed-tail signals.

    Each outer validation block is scored by a model trained only on earlier sessions.
    Learned-model hyperparameters are chosen inside the corresponding training block.
    The returned predictions retain every scored validation row so rank-correlation
    diagnostics can be audited independently of the tail-selection economics.
    """

    directional = candidate_direction_frame(selection_frame, candidate)
    sessions = tuple(sorted(set(directional["as_of_date"])))
    folds = expanding_walk_forward_folds(sessions, validation_folds=outer_folds)
    signals: list[pd.DataFrame] = []
    predictions: list[pd.DataFrame] = []
    fold_evidence: list[dict[str, object]] = []
    for fold in folds:
        train = _slice_sessions(directional, fold.train_sessions)
        validation = _slice_sessions(directional, fold.validation_sessions)
        if candidate.learned:
            params, tuning = tune_hyperparameters(train, candidate)
            model = fit_learned_model(train, candidate, params)
        else:
            params, tuning, model = {}, [], None
        scored = score_candidate(validation, candidate, model=model)
        scored["selection_fold"] = fold.fold_index
        predictions.append(scored)
        validation_ic = _session_spearman(
            scored,
            pd.to_numeric(scored["phase27_score"], errors="coerce").to_numpy(dtype=np.float64),
        )
        fired = select_fixed_tail(scored)
        if not fired.empty:
            fired["selection_fold"] = fold.fold_index
            signals.append(fired)
        fold_evidence.append(
            {
                "fold_index": fold.fold_index,
                "train_start": fold.train_sessions[0].isoformat(),
                "train_end": fold.train_sessions[-1].isoformat(),
                "purge_sessions": [item.isoformat() for item in fold.purge_sessions],
                "validation_start": fold.validation_sessions[0].isoformat(),
                "validation_end": fold.validation_sessions[-1].isoformat(),
                "validation_session_count": len(fold.validation_sessions),
                "validation_mean_session_spearman_ic": validation_ic,
                "chosen_params": params,
                "tuning_trials": tuning,
            }
        )
    combined_signals = pd.concat(signals, ignore_index=True) if signals else directional.iloc[0:0].copy()
    combined_predictions = (
        pd.concat(predictions, ignore_index=True) if predictions else directional.iloc[0:0].copy()
    )
    return combined_signals, combined_predictions, fold_evidence
