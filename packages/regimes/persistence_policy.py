"""Accepted Phase 9 market/sector persistence policy.

Gate 5 target-machine evidence selected two-session dimensional confirmation:
- market transition rate 15.07% (51.67% reduction from raw)
- market family agreement 86.27%
- market opposite-direction lag 0.47%
- sector mean transition rate 15.94% (58.34% reduction from raw)
- sector family agreement 75.61%
- sector opposite-direction lag 2.16%

Three-session confirmation reduced chatter further but materially increased divergence
and opposite-direction lag, so it was not selected.  The selected confirmation is
applied independently to regime dimensions before the composite state is recomputed.
"""

REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION = (
    "regime-persistence-policy-v1-two-session-dimensional-confirmation"
)
REGIME_SELECTED_CONFIRMATION_SESSIONS = 2
