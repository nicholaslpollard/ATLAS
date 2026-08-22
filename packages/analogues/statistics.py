from __future__ import annotations

import math

import numpy as np
import pandas as pd

from packages.analogues.policy import (
    PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION,
    PHASE12_MIN_UNIQUE_INSTRUMENTS,
    PHASE12_ROBUST_ANALOGUE_COUNT,
    PHASE12_ROBUST_PATH_COVERAGE,
    PHASE12_ROBUST_UNIQUE_INSTRUMENTS,
)
from packages.schemas.deep_research import AnalogueDistribution, AnalogueQuality


class AnalogueStatisticsError(ValueError):
    pass


def _finite(values: pd.Series) -> np.ndarray:
    array = pd.to_numeric(values, errors="coerce").to_numpy(dtype="float64")
    return array[np.isfinite(array)]


def summarize_distribution(frame: pd.DataFrame) -> AnalogueDistribution:
    required = {"instrument_id", "distance", "direction_adjusted_return"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise AnalogueStatisticsError("analogue frame missing columns: " + ", ".join(missing))
    values = _finite(frame["direction_adjusted_return"])
    if len(values) != len(frame):
        raise AnalogueStatisticsError("analogue returns must all be finite")
    if not len(values):
        return AnalogueDistribution(rows=0, unique_instruments=0)

    distances = _finite(frame["distance"])
    if len(distances) != len(frame) or np.any(distances < 0.0):
        raise AnalogueStatisticsError("analogue distances must be finite and non-negative")
    weights = 1.0 / (1.0 + distances)
    weighted_mean = float(np.average(values, weights=weights))
    quantiles = np.quantile(values, [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    return AnalogueDistribution(
        rows=int(len(values)),
        unique_instruments=int(frame["instrument_id"].astype(str).nunique()),
        weighted_mean_return=weighted_mean,
        mean_return=float(np.mean(values)),
        median_return=float(quantiles[3]),
        positive_rate=float(np.mean(values > 0.0)),
        stddev_return=float(np.std(values, ddof=0)),
        p05_return=float(quantiles[0]),
        p10_return=float(quantiles[1]),
        p25_return=float(quantiles[2]),
        p75_return=float(quantiles[4]),
        p90_return=float(quantiles[5]),
        p95_return=float(quantiles[6]),
        worst_return=float(np.min(values)),
        best_return=float(np.max(values)),
    )


def classify_quality(analogue_frame: pd.DataFrame, path_frame: pd.DataFrame) -> AnalogueQuality:
    required = {"instrument_id", "session_date", "distance"}
    missing = sorted(required.difference(analogue_frame.columns))
    if missing:
        raise AnalogueStatisticsError("analogue quality frame missing columns: " + ", ".join(missing))
    rows = int(len(analogue_frame))
    unique_instruments = int(analogue_frame["instrument_id"].astype(str).nunique()) if rows else 0
    path_rows = int(len(path_frame))
    coverage = 0.0 if rows == 0 else float(path_rows / rows)

    if rows:
        distances = _finite(analogue_frame["distance"])
        if len(distances) != rows or np.any(distances < 0.0):
            raise AnalogueStatisticsError("quality distances must be finite and non-negative")
        dates = pd.to_datetime(analogue_frame["session_date"], errors="raise").dt.date
        mean_distance = float(np.mean(distances))
        median_distance = float(np.median(distances))
        p90_distance = float(np.quantile(distances, 0.90))
        first_date = min(dates)
        last_date = max(dates)
    else:
        mean_distance = median_distance = p90_distance = None
        first_date = last_date = None

    reasons: list[str] = []
    if rows < PHASE12_MIN_ANALOGUES_FOR_DISTRIBUTION:
        status = "INSUFFICIENT"
        reasons.append("ANALOGUE_COUNT_BELOW_PREREGISTERED_MINIMUM")
    elif unique_instruments < PHASE12_MIN_UNIQUE_INSTRUMENTS:
        status = "INSUFFICIENT"
        reasons.append("UNIQUE_INSTRUMENT_COUNT_BELOW_PREREGISTERED_MINIMUM")
    elif (
        rows >= PHASE12_ROBUST_ANALOGUE_COUNT
        and unique_instruments >= PHASE12_ROBUST_UNIQUE_INSTRUMENTS
        and coverage >= PHASE12_ROBUST_PATH_COVERAGE
    ):
        status = "ROBUST"
        reasons.append("ANALOGUE_AND_PATH_COVERAGE_MEET_ROBUST_DIAGNOSTIC")
    else:
        status = "LIMITED"
        reasons.append("MINIMUM_ANALOGUE_SUPPORT_MET_BUT_ROBUST_DIAGNOSTIC_NOT_MET")
    if coverage < PHASE12_ROBUST_PATH_COVERAGE:
        reasons.append("PATH_COVERAGE_BELOW_ROBUST_DIAGNOSTIC")
    if not reasons:
        reasons.append("ANALOGUE_QUALITY_CLASSIFIED")

    return AnalogueQuality(
        status=status,
        analogue_count=rows,
        unique_instruments=unique_instruments,
        first_session_date=first_date,
        last_session_date=last_date,
        mean_distance=mean_distance,
        median_distance=median_distance,
        p90_distance=p90_distance,
        path_rows=path_rows,
        path_coverage=coverage,
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


def close_enough(left: float | None, right: float | None, *, tolerance: float = 1e-12) -> bool:
    if left is None or right is None:
        return left is right
    if not math.isfinite(left) or not math.isfinite(right):
        return False
    return abs(left - right) <= tolerance
