from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd

from .phase28_policy import (
    PHASE28_COMMON_RETURN_MIN_PEERS,
    PHASE28_LEAD_LAG_PAIRS,
    PHASE28_MAX_LEADERS,
    PHASE28_MIN_LEADERS,
    PHASE28_MIN_VALID_LAG_PAIRS,
    PHASE28_PEER_MOMENTUM_SESSIONS,
    PHASE28_RESIDUAL_MOMENTUM_SESSIONS,
)


class Phase28NetworkError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase28LeaderEdge:
    peer_id: str
    forward_corr: float
    reverse_corr: float
    asymmetry: float
    valid_pairs: int
    weight: float = 0.0


@dataclass(frozen=True, slots=True)
class Phase28SignalValues:
    residual_momentum_20d: float
    peer_lead_1d: float
    peer_lead_5d: float
    peer_diffusion_gap_1d: float

    def to_dict(self) -> dict[str, float]:
        return {
            "residual_momentum_20d": self.residual_momentum_20d,
            "peer_lead_1d": self.peer_lead_1d,
            "peer_lead_5d": self.peer_lead_5d,
            "peer_diffusion_gap_1d": self.peer_diffusion_gap_1d,
        }


def cross_sectional_residuals(
    raw_returns: pd.DataFrame,
    *,
    min_peers: int = PHASE28_COMMON_RETURN_MIN_PEERS,
) -> pd.DataFrame:
    """Remove the same-session median common move from a peer return matrix.

    Rows are exchange sessions and columns are exact PIT peer instrument IDs. Sessions
    with fewer than ``min_peers`` finite returns are unavailable for every peer. No
    forward/backward filling is permitted.
    """

    if min_peers < 1:
        raise Phase28NetworkError("minimum peer count must be positive")
    if raw_returns.empty or raw_returns.columns.empty:
        raise Phase28NetworkError("Phase28 residualization requires a nonempty return matrix")
    values = raw_returns.apply(pd.to_numeric, errors="coerce").astype(float)
    finite = np.isfinite(values.to_numpy(dtype=float))
    counts = finite.sum(axis=1)
    common = values.median(axis=1, skipna=True)
    common.loc[counts < min_peers] = np.nan
    result = values.sub(common, axis=0)
    result.loc[counts < min_peers, :] = np.nan
    return result


def _correlation(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        return None
    if float(np.std(x)) <= 0.0 or float(np.std(y)) <= 0.0:
        return None
    value = float(np.corrcoef(x, y)[0, 1])
    return value if np.isfinite(value) else None


def lead_lag_edge(
    residuals: pd.DataFrame,
    *,
    focal_id: str,
    peer_id: str,
    estimation_end: date,
    lag_pairs: int = PHASE28_LEAD_LAG_PAIRS,
    min_valid_pairs: int = PHASE28_MIN_VALID_LAG_PAIRS,
) -> Phase28LeaderEdge | None:
    """Estimate one frozen asymmetric peer->focal residual-return edge.

    Only rows through ``estimation_end`` are used. The latest ``lag_pairs + 1``
    exchange-session rows define the frozen lag grid; missing values reduce the valid
    aligned-pair count rather than causing the window to reach further backward.
    """

    if focal_id == peer_id:
        return None
    if lag_pairs < 2 or min_valid_pairs < 2 or min_valid_pairs > lag_pairs:
        raise Phase28NetworkError("invalid Phase28 lag-pair requirements")
    missing = [column for column in (focal_id, peer_id) if column not in residuals.columns]
    if missing:
        raise Phase28NetworkError("missing residual columns: " + ", ".join(missing))

    work = residuals.loc[
        pd.to_datetime(residuals.index).date <= estimation_end,
        [focal_id, peer_id],
    ].tail(lag_pairs + 1)
    if len(work) < min_valid_pairs + 1:
        return None

    focal = pd.to_numeric(work[focal_id], errors="coerce").to_numpy(dtype=float)
    peer = pd.to_numeric(work[peer_id], errors="coerce").to_numpy(dtype=float)
    aligned = (
        np.isfinite(peer[:-1])
        & np.isfinite(focal[1:])
        & np.isfinite(focal[:-1])
        & np.isfinite(peer[1:])
    )
    valid_pairs = int(aligned.sum())
    if valid_pairs < min_valid_pairs:
        return None

    forward = _correlation(peer[:-1][aligned], focal[1:][aligned])
    reverse = _correlation(focal[:-1][aligned], peer[1:][aligned])
    if forward is None or reverse is None:
        return None
    asymmetry = float(forward - reverse)
    if forward <= 0.0 or asymmetry <= 0.0:
        return None
    return Phase28LeaderEdge(
        peer_id=str(peer_id),
        forward_corr=forward,
        reverse_corr=reverse,
        asymmetry=asymmetry,
        valid_pairs=valid_pairs,
    )


def select_leaders(
    residuals: pd.DataFrame,
    *,
    focal_id: str,
    peer_ids: Iterable[str],
    estimation_end: date,
    max_leaders: int = PHASE28_MAX_LEADERS,
    min_leaders: int = PHASE28_MIN_LEADERS,
) -> tuple[Phase28LeaderEdge, ...]:
    if max_leaders < 1 or min_leaders < 1 or min_leaders > max_leaders:
        raise Phase28NetworkError("invalid Phase28 leader cardinality")
    edges: list[Phase28LeaderEdge] = []
    for peer_id in sorted(set(str(value) for value in peer_ids)):
        edge = lead_lag_edge(
            residuals,
            focal_id=focal_id,
            peer_id=peer_id,
            estimation_end=estimation_end,
        )
        if edge is not None:
            edges.append(edge)
    edges.sort(key=lambda edge: (-edge.asymmetry, edge.peer_id))
    chosen = edges[:max_leaders]
    if len(chosen) < min_leaders:
        return ()
    total = float(sum(edge.asymmetry for edge in chosen))
    if not np.isfinite(total) or total <= 0.0:
        raise Phase28NetworkError("qualifying leader asymmetry sum is invalid")
    return tuple(replace(edge, weight=float(edge.asymmetry / total)) for edge in chosen)


def _latest_exact_values(
    residuals: pd.DataFrame,
    *,
    instrument_id: str,
    observation_date: date,
    sessions: int,
) -> np.ndarray | None:
    if instrument_id not in residuals.columns:
        return None
    work = residuals.loc[
        pd.to_datetime(residuals.index).date <= observation_date,
        instrument_id,
    ].tail(sessions)
    if len(work) != sessions:
        return None
    values = pd.to_numeric(work, errors="coerce").to_numpy(dtype=float)
    return values if np.isfinite(values).all() else None


def compute_signal_values(
    residuals: pd.DataFrame,
    *,
    focal_id: str,
    leaders: tuple[Phase28LeaderEdge, ...],
    observation_date: date,
) -> Phase28SignalValues | None:
    """Compute the four frozen Phase28 signals from an already-frozen leader set."""

    if len(leaders) < PHASE28_MIN_LEADERS or len(leaders) > PHASE28_MAX_LEADERS:
        return None
    if any(edge.weight <= 0.0 or not np.isfinite(edge.weight) for edge in leaders):
        return None
    if not np.isclose(sum(edge.weight for edge in leaders), 1.0, rtol=1e-12, atol=1e-12):
        return None

    focal_20 = _latest_exact_values(
        residuals,
        instrument_id=focal_id,
        observation_date=observation_date,
        sessions=PHASE28_RESIDUAL_MOMENTUM_SESSIONS,
    )
    if focal_20 is None:
        return None

    peer_1d = 0.0
    peer_5d = 0.0
    for edge in leaders:
        values = _latest_exact_values(
            residuals,
            instrument_id=edge.peer_id,
            observation_date=observation_date,
            sessions=PHASE28_PEER_MOMENTUM_SESSIONS,
        )
        if values is None:
            return None
        peer_1d += edge.weight * float(values[-1])
        peer_5d += edge.weight * float(values.sum())

    focal_current = float(focal_20[-1])
    signals = Phase28SignalValues(
        residual_momentum_20d=float(focal_20.sum()),
        peer_lead_1d=float(peer_1d),
        peer_lead_5d=float(peer_5d),
        peer_diffusion_gap_1d=float(peer_1d - focal_current),
    )
    return signals if all(np.isfinite(value) for value in signals.to_dict().values()) else None


def oriented_score(raw_signal: float, *, direction: str) -> float:
    value = float(raw_signal)
    if not np.isfinite(value):
        raise Phase28NetworkError("Phase28 score input must be finite")
    if direction == "LONG":
        return value
    if direction == "SHORT":
        return -value
    raise Phase28NetworkError(f"unsupported Phase28 strategy direction: {direction}")
