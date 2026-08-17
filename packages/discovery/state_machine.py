from __future__ import annotations

from dataclasses import dataclass

from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState


DISCOVERY_STATE_POLICY_VERSION = "discovery-state-v1-provisional-absolute-evidence"


@dataclass(frozen=True, slots=True)
class DiscoveryStatePolicy:
    """Initial absolute-evidence thresholds pending real-score calibration.

    These are deliberately not percentile/cap based. Phase 8's real 2026-08-14 score
    distribution will be used to confirm or revise them before persistence semantics are
    locked.
    """

    watch_priority: float = 0.42
    warm_priority: float = 0.58
    hot_priority: float = 0.72
    hot_directional_evidence: float = 0.65

    def classify(
        self,
        *,
        priority_score: float,
        bull_evidence: float,
        bear_evidence: float,
        direction: DiscoveryDirection | str,
    ) -> DiscoveryState:
        direction = DiscoveryDirection(direction)
        dominant = max(float(bull_evidence), float(bear_evidence))
        priority = float(priority_score)
        if (
            priority >= self.hot_priority
            and dominant >= self.hot_directional_evidence
            and direction != DiscoveryDirection.NEUTRAL
        ):
            return DiscoveryState.HOT
        if priority >= self.warm_priority:
            return DiscoveryState.WARM
        if priority >= self.watch_priority:
            return DiscoveryState.WATCH
        return DiscoveryState.NORMAL


ACTIVE_DISCOVERY_STATE_POLICY = DiscoveryStatePolicy()
