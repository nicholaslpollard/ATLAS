"""Accepted Phase 9 Gate 11 ticker self-relative risk policy.

Target-machine evidence selected a 126-session primary prior-only window:
- 126 vs 252 risk agreement: 64.22% exact, 99.70% within one level
- 126 vs 252 material understatements (2+ levels): 0.00%
- 126 vs 252 STRESSED -> CALM/NORMAL: 0 / 1,066
- 126-session current coverage: 7,340 instruments

A 60-session prior-only window is accepted only as a provisional fallback for
names with 60-125 prior observations. Against the selected 126-session target
on mature names, 60 sessions produced zero 2+ level understatements and zero
STRESSED -> CALM/NORMAL misses. Remaining 2+ level disagreements were on the
conservative/overstated side.

Twenty sessions is rejected as a production fallback because its material risk
mismatch was too large. The 252-session window remains an audit/reference
horizon rather than a universal production prerequisite.
"""

from __future__ import annotations


TICKER_RISK_POLICY_CONTRACT_VERSION = (
    "ticker-risk-policy-v1-126-primary-60-provisional-prior-only"
)
TICKER_RISK_PRIMARY_WINDOW = 126
TICKER_RISK_PROVISIONAL_WINDOW = 60
TICKER_RISK_REFERENCE_AUDIT_WINDOW = 252

TICKER_RISK_MODE_FULL = "FULL_126"
TICKER_RISK_MODE_PROVISIONAL = "PROVISIONAL_60"
TICKER_RISK_MODE_INSUFFICIENT = "INSUFFICIENT_HISTORY"
TICKER_RISK_MODE_NO_CURRENT_METRICS = "NO_CURRENT_METRICS"
TICKER_RISK_MODE_IDENTITY_BLOCKED = "IDENTITY_BLOCKED"


def ticker_risk_history_mode(
    *,
    identity_safe: bool,
    has_current_metrics: bool,
    prior_sessions: int,
) -> str:
    """Return the accepted Gate 11 production history/confidence mode."""

    if not identity_safe:
        return TICKER_RISK_MODE_IDENTITY_BLOCKED
    if not has_current_metrics:
        return TICKER_RISK_MODE_NO_CURRENT_METRICS
    if prior_sessions >= TICKER_RISK_PRIMARY_WINDOW:
        return TICKER_RISK_MODE_FULL
    if prior_sessions >= TICKER_RISK_PROVISIONAL_WINDOW:
        return TICKER_RISK_MODE_PROVISIONAL
    return TICKER_RISK_MODE_INSUFFICIENT


def ticker_risk_selected_window(mode: str) -> int | None:
    """Map a production risk mode to its prior-only lookback window."""

    if mode == TICKER_RISK_MODE_FULL:
        return TICKER_RISK_PRIMARY_WINDOW
    if mode == TICKER_RISK_MODE_PROVISIONAL:
        return TICKER_RISK_PROVISIONAL_WINDOW
    return None
