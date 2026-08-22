from __future__ import annotations

import math
from dataclasses import dataclass

from packages.schemas.strategy import StrategyDirection


STRATEGY_OUTCOME_CONTRACT_VERSION = "strategy-outcome-v1-direction-adjusted-three-session-return"
DEFAULT_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0)


@dataclass(frozen=True, slots=True)
class StrategyOutcome:
    forward_return: float
    direction: StrategyDirection
    directional_return: float

    def net_return(self, round_trip_cost_bps: float) -> float:
        cost = float(round_trip_cost_bps) / 10_000.0
        if cost < 0.0 or not math.isfinite(cost):
            raise ValueError("round_trip_cost_bps must be finite and non-negative")
        return self.directional_return - cost


def strategy_outcome(forward_return: float, direction: StrategyDirection) -> StrategyOutcome:
    value = float(forward_return)
    if not math.isfinite(value):
        raise ValueError("forward_return must be finite")
    directional = value if direction == StrategyDirection.LONG else -value
    return StrategyOutcome(
        forward_return=value,
        direction=direction,
        directional_return=directional,
    )
