from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import mean, median, pstdev
from typing import Iterable


STRATEGY_METRICS_CONTRACT_VERSION = "strategy-metrics-v1-return-distribution-no-selection-threshold"


@dataclass(frozen=True, slots=True)
class StrategyReturnMetrics:
    rows: int
    mean_return: float
    median_return: float
    positive_rate: float
    nonnegative_rate: float
    stddev_return: float
    p10_return: float
    p25_return: float
    p75_return: float
    p90_return: float
    worst_return: float
    best_return: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("cannot compute quantile of empty sequence")
    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be between 0 and 1")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def return_metrics(values: Iterable[float]) -> StrategyReturnMetrics:
    data = [float(value) for value in values]
    if not data:
        raise ValueError("strategy metrics require at least one return")
    if not all(math.isfinite(value) for value in data):
        raise ValueError("strategy metrics require finite returns")
    ordered = sorted(data)
    rows = len(data)
    return StrategyReturnMetrics(
        rows=rows,
        mean_return=mean(data),
        median_return=median(data),
        positive_rate=sum(value > 0.0 for value in data) / rows,
        nonnegative_rate=sum(value >= 0.0 for value in data) / rows,
        stddev_return=0.0 if rows == 1 else pstdev(data),
        p10_return=_quantile(ordered, 0.10),
        p25_return=_quantile(ordered, 0.25),
        p75_return=_quantile(ordered, 0.75),
        p90_return=_quantile(ordered, 0.90),
        worst_return=ordered[0],
        best_return=ordered[-1],
    )
