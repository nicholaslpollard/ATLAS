from __future__ import annotations

from dataclasses import dataclass

from packages.core.enums import Timeframe


@dataclass(frozen=True, slots=True)
class FeaturePersistencePolicy:
    """Phase 6 persistence policy selected from measured target-machine behavior."""

    permanently_materialized: tuple[Timeframe, ...]
    current_state_only: tuple[Timeframe, ...]
    on_demand_history: tuple[Timeframe, ...]
    rationale: str


# No full historical feature matrix is declared permanent before the Phase 6D
# benchmark. This is intentional, not a missing implementation. The old Chart
# Monitor proved that blindly materializing large indicator matrices can create
# unacceptable RAM/storage/maintenance costs. Phase 6D will replace this pending
# policy with a measured selection.
PENDING_BENCHMARK_POLICY = FeaturePersistencePolicy(
    permanently_materialized=(),
    current_state_only=(Timeframe.MINUTE_1,),
    on_demand_history=(
        Timeframe.MINUTE_15,
        Timeframe.HOUR_1,
        Timeframe.HOUR_4,
        Timeframe.DAY_1,
    ),
    rationale="Pending real 4h/1h/15m feature benchmark on the target ATLAS machine.",
)
