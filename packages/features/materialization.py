from __future__ import annotations

from dataclasses import dataclass

from packages.core.enums import Timeframe


@dataclass(frozen=True, slots=True)
class FeaturePersistencePolicy:
    """Measured persistence tiers for ATLAS feature history.

    ``benchmark_candidates`` are intentionally outside all three committed tiers.
    A candidate must be promoted only after a target-machine benchmark demonstrates
    that its storage/rebuild cost is acceptable; this prevents an unmeasured
    timeframe from being treated as durable historical state by accident.
    """

    permanently_materialized: tuple[Timeframe, ...]
    current_state_only: tuple[Timeframe, ...]
    on_demand_history: tuple[Timeframe, ...]
    benchmark_candidates: tuple[Timeframe, ...]
    rationale: str

    def __post_init__(self) -> None:
        groups = (
            self.permanently_materialized,
            self.current_state_only,
            self.on_demand_history,
            self.benchmark_candidates,
        )
        flattened = [timeframe for group in groups for timeframe in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError("a timeframe may appear in only one feature persistence tier")

    def tier_for(self, timeframe: Timeframe) -> str:
        if timeframe in self.permanently_materialized:
            return "permanent"
        if timeframe in self.current_state_only:
            return "current_state_only"
        if timeframe in self.on_demand_history:
            return "on_demand"
        if timeframe in self.benchmark_candidates:
            return "benchmark_candidate"
        return "unsupported"


# Target-machine evidence, captured 2026-08-16 from the real ATLAS historical lake:
#
# 4h sample: 20 sessions / 714,562 rows / 13,110 symbols / all 33 core features
#   wall time              6.8 minutes
#   rows/second            1,746
#   compact feature RAM    221.3 MiB
#   feature Parquet        100.2 MiB
#   compressed bytes/row   147.1
#   output/source ratio    6.23x
#   1,255-session estimate 44,838,766 rows / 6,289.8 MiB / 427.9 minutes
#
# The machine had approximately 206 GiB free after the benchmark. Storage is
# therefore not the controlling constraint for 4h history; full rebuild time is.
# 1d is far smaller than 4h and is a high-value research/regime timeframe, so it
# joins 4h as permanent. 15m remains cache/on-demand because extrapolated row count
# and rebuild cost are materially larger. 1m remains live/current-state only.
# 1h is the single unresolved candidate and requires its own measured benchmark.
ACTIVE_FEATURE_PERSISTENCE_POLICY = FeaturePersistencePolicy(
    permanently_materialized=(Timeframe.DAY_1, Timeframe.HOUR_4),
    current_state_only=(Timeframe.MINUTE_1,),
    on_demand_history=(Timeframe.MINUTE_15,),
    benchmark_candidates=(Timeframe.HOUR_1,),
    rationale=(
        "Measured 4h target-machine benchmark projects about 6.14 GiB of compact "
        "Parquet and 427.9 minutes of single-core full-history recomputation across "
        "1,255 sessions. Storage headroom is ample, so 1d/4h are permanent; 15m is "
        "on-demand/cache, 1m is current-state only, and 1h remains benchmark-gated."
    ),
)

# Compatibility alias for code/tests written during the pre-benchmark slice. New
# code should use ACTIVE_FEATURE_PERSISTENCE_POLICY.
PENDING_BENCHMARK_POLICY = ACTIVE_FEATURE_PERSISTENCE_POLICY
