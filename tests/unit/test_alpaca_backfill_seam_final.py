from __future__ import annotations

import pytest

from packages.data.alpaca_backfill_seam_final import (
    ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION,
    BRIDGE_EXACT_LITERAL,
    MASSIVE_DISCONTINUITY_STATUS,
    NO_CONTINUITY_STATUS,
    NO_PRESEAM_STATUS,
    POSTSEAM_ONLY,
    QUARANTINE_SEAM_CONTINUITY,
    RESET_AT_PROVIDER_SEAM,
    SAFE_EXACT_LITERAL_STATUS,
    TERMINATE_PRESEAM_CONTINUITY,
    continuity_allowed,
    promotion_decision,
)


def test_gate7_final_contract_is_explicit_bridge_or_reset() -> None:
    assert ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION.startswith(
        "historical-backfill-seam-final-v1"
    )
    assert "bridge-or-reset" in ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION


def test_gate7_final_safe_exact_literal_bridges_only_exact_status() -> None:
    assert promotion_decision(SAFE_EXACT_LITERAL_STATUS) == BRIDGE_EXACT_LITERAL


def test_gate7_final_massive_discontinuity_resets_at_provider_seam() -> None:
    assert promotion_decision(MASSIVE_DISCONTINUITY_STATUS) == RESET_AT_PROVIDER_SEAM


def test_gate7_final_no_continuity_evidence_terminates_preseam_series() -> None:
    assert promotion_decision(NO_CONTINUITY_STATUS) == TERMINATE_PRESEAM_CONTINUITY


def test_gate7_final_review_status_is_quarantined() -> None:
    assert promotion_decision("REVIEW_CASEFOLD_ANOMALY") == QUARANTINE_SEAM_CONTINUITY
    assert promotion_decision("REVIEW_PRESEAM_IDENTITY_AMBIGUOUS") == QUARANTINE_SEAM_CONTINUITY


def test_gate7_final_postseam_only_has_no_preseam_bridge() -> None:
    assert promotion_decision(NO_PRESEAM_STATUS) == POSTSEAM_ONLY


def test_gate7_final_only_exact_bridge_allows_continuity() -> None:
    assert continuity_allowed(BRIDGE_EXACT_LITERAL) is True
    for decision in (
        RESET_AT_PROVIDER_SEAM,
        TERMINATE_PRESEAM_CONTINUITY,
        QUARANTINE_SEAM_CONTINUITY,
        POSTSEAM_ONLY,
    ):
        assert continuity_allowed(decision) is False


def test_gate7_final_unknown_identity_status_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported Gate 7 identity status"):
        promotion_decision("SILENTLY_INFER_CONTINUITY")
