"""Accepted Phase 9 point-in-time threshold-memory policy.

Gate 6 target-machine evidence selected expanding prior-only quantile bands after a
252-session seed.  Frozen bands became structurally stale, while rolling 252-session
bands adapted enough to reduce agreement and alter the 2026-08-14 market direction.

The history origin is deliberately versioned.  Backfilling older data must not silently
rewrite historical regime semantics; changing the origin requires a new policy contract.
"""

from datetime import date


REGIME_THRESHOLD_POLICY_CONTRACT_VERSION = (
    "regime-threshold-policy-v1-expanding-252-prior-only"
)
REGIME_THRESHOLD_POLICY_NAME = "expanding_252"
REGIME_THRESHOLD_TRAINING_SESSIONS = 252
REGIME_THRESHOLD_QUANTILES = (0.25, 0.75, 0.90)
REGIME_HISTORY_ORIGIN_DATE = date(2021, 8, 16)

REGIME_BREADTH_POPULATION_CONTRACT_VERSION = (
    "regime-breadth-population-v1-250k-dollar-volume-complete-1d"
)

POINT_IN_TIME_THRESHOLD_RULE = (
    "For every evaluated session, p25/p75 bands and p90 volatility bands are computed "
    "from all eligible observations strictly before the current session, after at least "
    "252 fully warmed observations."
)
