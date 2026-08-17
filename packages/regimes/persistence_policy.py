"""Accepted Phase 9 market/sector persistence policy.

The raw Gate 4 state definitions remain unchanged. Gate 5 target-machine evidence
selected two-session dimensional confirmation as the stability/lag trade-off to carry
into point-in-time threshold validation.
"""

REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION = (
    "regime-persistence-policy-v1-two-session-dimensional-confirmation"
)
REGIME_SELECTED_CONFIRMATION_SESSIONS = 2
