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


# Target-machine evidence, captured 2026-08-16 from the real ATLAS historical lake.
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
# 1h sample: 20 sessions / 1,903,874 rows / 13,110 symbols / all 33 core features
#   wall time              7.1 minutes
#   rows/second            4,490
#   peak process RSS       2,419.6 MiB
#   compact feature RAM    589.6 MiB
#   feature Parquet        336.1 MiB
#   compressed bytes/row   185.1
#   output/source ratio    8.39x
#   1,255-session estimate 119,468,094 rows / 21,088.6 MiB / 443.4 minutes
#
# The machine had approximately 206 GiB free after the benchmarks. Storage and peak
# memory are therefore acceptable for permanent 1h/4h history. Full rebuild time is
# the controlling cost, so normal maintenance relies on state-dependent manifests,
# exact recursive checkpoints, and month-end replay anchors instead of routine full
# recomputation. 1d is smaller than 4h and strategically important, so it also stays
# permanent. 15m remains cache/on-demand; 1m remains live/current-state only.
ACTIVE_FEATURE_PERSISTENCE_POLICY = FeaturePersistencePolicy(
    permanently_materialized=(Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1),
    current_state_only=(Timeframe.MINUTE_1,),
    on_demand_history=(Timeframe.MINUTE_15,),
    benchmark_candidates=(),
    rationale=(
        "Measured target-machine benchmarks project about 6.14 GiB for 4h and "
        "20.59 GiB for 1h compact feature Parquet across 1,255 sessions. The 1h "
        "sample peaked at about 2.36 GiB RSS, which is comfortable on the 24 GiB "
        "target machine, while free disk was about 206 GiB. Therefore 1d/4h/1h are "
        "permanent historical core-feature layers; 15m remains on-demand/cache and "
        "1m remains current/live state only."
    ),
)

# Compatibility alias for code/tests written during the pre-benchmark slice. New
# code should use ACTIVE_FEATURE_PERSISTENCE_POLICY.
PENDING_BENCHMARK_POLICY = ACTIVE_FEATURE_PERSISTENCE_POLICY
