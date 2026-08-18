"""Accepted Phase 9 ticker-state persistence policy.

Gate 10 target-machine evidence selected two-session dimensional confirmation over
composite confirmation and three-session alternatives.

Raw ticker-state history was highly chatty:
- transition rate: 48.10%
- median run length: 1 session
- one-session run share: 53.84%
- A->B->A flipbacks: 268,095

Selected two-session dimensional confirmation:
- transition rate: 21.40% (55.50% reduction from raw)
- median run length: 3 sessions
- one-session run share: 15.75%
- A->B->A flipbacks: 2,714 (~98.99% reduction from raw)
- exact raw-state agreement: 62.22%
- directional-family agreement: 90.38%
- opposite UP/DOWN mismatch: 7.71%

Two-session composite confirmation reduced transitions further, but dimensional
confirmation preserved directional-family agreement better and reduced opposite-
direction mismatch. Three-session policies introduced materially more directional lag.

The selected policy confirms daily structure, short-horizon 4h/1h alignment, and daily
momentum independently for two consecutive XNYS sessions, then recomputes the existing
ticker state. Confirmation resets across missing exchange sessions. Gate-9 identity
safety remains authoritative and no ticker-text history is spliced.
"""

TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION = (
    "ticker-persistence-policy-v1-two-session-dimensional-confirmation"
)
TICKER_SELECTED_CONFIRMATION_SESSIONS = 2
TICKER_SELECTED_PERSISTENCE_MODE = "dimensional"
TICKER_SELECTED_PERSISTENCE_POLICY_NAME = "dimensional_confirm_2"
