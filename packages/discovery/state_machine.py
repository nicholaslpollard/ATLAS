from __future__ import annotations

from dataclasses import dataclass

from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState


DISCOVERY_STATE_POLICY_VERSION = "discovery-state-v3-locked-absolute-evidence"


@dataclass(frozen=True, slots=True)
class DiscoveryStatePolicy:
    """Locked absolute-evidence thresholds with deterministic coverage guards.

    These are absolute score thresholds, not percentile or population caps. The values were
    calibrated against the real 2026-08-14 8,034-instrument discovery population after the
    cross-sectional relative-strength tail correction. Coverage guards prevent sparse
    evidence from escalating farther than its context can support: zero scored timeframes
    stay NORMAL, one timeframe can reach WATCH, two can reach WARM, and HOT requires all
    three configured timeframes plus non-neutral directional conviction.
    """

    watch_priority: float = 0.35
    warm_priority: float = 0.50
    hot_priority: float = 0.60
    hot_directional_evidence: float = 0.50

    def classify(
        self,
        *,
        priority_score: float,
        bull_evidence: float,
        bear_evidence: float,
        direction: DiscoveryDirection | str,
        scored_timeframes: int = 3,
    ) -> DiscoveryState:
        direction = DiscoveryDirection(direction)
        coverage = int(scored_timeframes)
        if coverage < 0 or coverage > 3:
            raise ValueError("scored_timeframes must be between 0 and 3")
        if coverage == 0:
            return DiscoveryState.NORMAL

        dominant = max(float(bull_evidence), float(bear_evidence))
        priority = float(priority_score)
        if (
            coverage >= 3
            and priority >= self.hot_priority
            and dominant >= self.hot_directional_evidence
            and direction != DiscoveryDirection.NEUTRAL
        ):
            return DiscoveryState.HOT
        if coverage >= 2 and priority >= self.warm_priority:
            return DiscoveryState.WARM
        if priority >= self.watch_priority:
            return DiscoveryState.WATCH
        return DiscoveryState.NORMAL


ACTIVE_DISCOVERY_STATE_POLICY = DiscoveryStatePolicy()
