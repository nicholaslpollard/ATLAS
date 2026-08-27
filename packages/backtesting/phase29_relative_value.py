from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from .phase29_policy import (
    PHASE29_FORMATION_RETURN_SESSIONS,
    PHASE29_PAIR_FORMATION_PRICE_SESSIONS,
    PHASE29_PAIR_MIN_SPREAD_STD,
    PHASE29_PCA_COMPONENTS,
    PHASE29_PCA_MIN_PEERS,
)


class Phase29RelativeValueError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase29PcaDislocation:
    instrument_id: str
    current_standardized_return: float
    factor_reconstruction: float
    residual_dislocation: float
    component_count: int
    peer_count: int


@dataclass(frozen=True, slots=True)
class Phase29PairDislocation:
    instrument_id: str
    peer_instrument_id: str
    formation_distance: float
    formation_spread_mean: float
    formation_spread_std: float
    current_spread: float
    spread_z: float


def _finite_numeric_frame(frame: pd.DataFrame, *, label: str) -> pd.DataFrame:
    if frame.empty or frame.columns.empty:
        raise Phase29RelativeValueError(f"{label} must be nonempty")
    result = frame.apply(pd.to_numeric, errors="coerce").astype(float)
    if not np.isfinite(result.to_numpy(dtype=float)).all():
        raise Phase29RelativeValueError(f"{label} must be complete and finite")
    if len(set(str(column) for column in result.columns)) != len(result.columns):
        raise Phase29RelativeValueError(f"{label} contains duplicate instrument IDs")
    result.columns = [str(column) for column in result.columns]
    return result


def pca_residual_dislocations(
    formation_returns: pd.DataFrame,
    current_returns: pd.Series | Mapping[str, float],
    *,
    components: int = PHASE29_PCA_COMPONENTS,
    min_peers: int = PHASE29_PCA_MIN_PEERS,
) -> dict[str, Phase29PcaDislocation]:
    """Compute frozen leave-focal-out current PCA residual dislocations.

    ``formation_returns`` must contain exactly the frozen formation rows ending at
    t-1. The PCA basis is fitted only to that matrix. For each focal instrument,
    the current factor score is solved from every *other* instrument's current
    standardized return, so the focal current return cannot mechanically explain
    itself.
    """

    formation = _finite_numeric_frame(formation_returns, label="Phase29 formation returns")
    if len(formation) != PHASE29_FORMATION_RETURN_SESSIONS:
        raise Phase29RelativeValueError(
            f"Phase29 PCA requires exactly {PHASE29_FORMATION_RETURN_SESSIONS} formation returns"
        )
    peer_count = len(formation.columns)
    if peer_count < min_peers:
        raise Phase29RelativeValueError("Phase29 PCA peer count is below the frozen minimum")
    if components < 1 or components >= peer_count:
        raise Phase29RelativeValueError("Phase29 PCA component geometry is invalid")

    means = formation.mean(axis=0).to_numpy(dtype=float)
    stds = formation.std(axis=0, ddof=0).to_numpy(dtype=float)
    if not np.isfinite(stds).all() or np.any(stds <= 0.0):
        raise Phase29RelativeValueError("Phase29 PCA formation variance is nonpositive")
    x = (formation.to_numpy(dtype=float) - means[None, :]) / stds[None, :]
    try:
        _, _, vt = np.linalg.svd(x, full_matrices=False)
    except np.linalg.LinAlgError as exc:
        raise Phase29RelativeValueError("Phase29 PCA SVD failed") from exc
    if vt.shape[0] < components:
        raise Phase29RelativeValueError("Phase29 PCA basis is rank-deficient")
    loadings = vt[:components, :].T
    if not np.isfinite(loadings).all():
        raise Phase29RelativeValueError("Phase29 PCA loadings are nonfinite")

    current = pd.Series(current_returns, dtype=float).reindex(formation.columns)
    current_values = pd.to_numeric(current, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(current_values).all():
        raise Phase29RelativeValueError("Phase29 current returns must be complete and finite")
    current_z = (current_values - means) / stds

    result: dict[str, Phase29PcaDislocation] = {}
    ids = list(formation.columns)
    for focal_index, focal_id in enumerate(ids):
        other_mask = np.ones(peer_count, dtype=bool)
        other_mask[focal_index] = False
        other_loadings = loadings[other_mask, :]
        other_current = current_z[other_mask]
        factor_score, _, rank, _ = np.linalg.lstsq(other_loadings, other_current, rcond=None)
        if int(rank) < components or not np.isfinite(factor_score).all():
            raise Phase29RelativeValueError(
                f"Phase29 leave-focal-out PCA factor solve is rank-deficient for {focal_id}"
            )
        reconstruction = float(loadings[focal_index, :] @ factor_score)
        residual = float(current_z[focal_index] - reconstruction)
        if not np.isfinite(reconstruction) or not np.isfinite(residual):
            raise Phase29RelativeValueError("Phase29 PCA dislocation is nonfinite")
        result[focal_id] = Phase29PcaDislocation(
            instrument_id=focal_id,
            current_standardized_return=float(current_z[focal_index]),
            factor_reconstruction=reconstruction,
            residual_dislocation=residual,
            component_count=components,
            peer_count=peer_count,
        )
    return result


def normalized_price_paths(formation_closes: pd.DataFrame) -> pd.DataFrame:
    closes = _finite_numeric_frame(formation_closes, label="Phase29 pair formation closes")
    if len(closes) != PHASE29_PAIR_FORMATION_PRICE_SESSIONS:
        raise Phase29RelativeValueError(
            f"Phase29 pair formation requires exactly {PHASE29_PAIR_FORMATION_PRICE_SESSIONS} closes"
        )
    values = closes.to_numpy(dtype=float)
    if np.any(values <= 0.0):
        raise Phase29RelativeValueError("Phase29 pair formation closes must be positive")
    first = values[0, :]
    normalized = values / first[None, :]
    return pd.DataFrame(normalized, index=closes.index, columns=closes.columns)


def nearest_pair_dislocations(
    formation_closes: pd.DataFrame,
    current_closes: pd.Series | Mapping[str, float],
    *,
    min_spread_std: float = PHASE29_PAIR_MIN_SPREAD_STD,
) -> dict[str, Phase29PairDislocation]:
    """Choose the frozen nearest formation pair, then measure only current dislocation.

    Pair identity and spread mean/std are functions only of formation closes ending
    at t-1. ``current_closes`` is used solely after pair identity/statistics are
    frozen, so changing the current focal/peer prices cannot change which peer was
    selected.
    """

    normalized = normalized_price_paths(formation_closes)
    ids = list(normalized.columns)
    if len(ids) < 2:
        raise Phase29RelativeValueError("Phase29 nearest-pair mechanism needs at least two peers")
    current = pd.Series(current_closes, dtype=float).reindex(ids)
    current_values = pd.to_numeric(current, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(current_values).all() or np.any(current_values <= 0.0):
        raise Phase29RelativeValueError("Phase29 current closes must be complete, finite, and positive")

    formation = _finite_numeric_frame(formation_closes, label="Phase29 pair formation closes")
    first = formation.iloc[0].to_numpy(dtype=float)
    current_normalized = current_values / first
    norm_values = normalized.to_numpy(dtype=float)

    result: dict[str, Phase29PairDislocation] = {}
    for focal_index, focal_id in enumerate(ids):
        choices: list[tuple[float, str, int]] = []
        for peer_index, peer_id in enumerate(ids):
            if peer_index == focal_index:
                continue
            diff = norm_values[:, focal_index] - norm_values[:, peer_index]
            distance = float(np.dot(diff, diff))
            if np.isfinite(distance):
                choices.append((distance, peer_id, peer_index))
        if not choices:
            continue
        choices.sort(key=lambda item: (item[0], item[1]))
        distance, peer_id, peer_index = choices[0]
        formation_spread = norm_values[:, focal_index] - norm_values[:, peer_index]
        spread_mean = float(np.mean(formation_spread))
        spread_std = float(np.std(formation_spread, ddof=0))
        if not np.isfinite(spread_std) or spread_std <= min_spread_std:
            continue
        current_spread = float(current_normalized[focal_index] - current_normalized[peer_index])
        spread_z = float((current_spread - spread_mean) / spread_std)
        if not all(np.isfinite(value) for value in (spread_mean, current_spread, spread_z)):
            continue
        result[focal_id] = Phase29PairDislocation(
            instrument_id=focal_id,
            peer_instrument_id=peer_id,
            formation_distance=float(distance),
            formation_spread_mean=spread_mean,
            formation_spread_std=spread_std,
            current_spread=current_spread,
            spread_z=spread_z,
        )
    return result


def oriented_reversion_score(raw_signal: float, *, orientation: float) -> float:
    value = float(raw_signal)
    multiplier = float(orientation)
    if not np.isfinite(value) or multiplier not in (-1.0, 1.0):
        raise Phase29RelativeValueError("Phase29 score inputs are invalid")
    result = multiplier * value
    if not np.isfinite(result):
        raise Phase29RelativeValueError("Phase29 score is nonfinite")
    return float(result)
