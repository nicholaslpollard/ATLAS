from __future__ import annotations

import pandas as pd

from packages.data.alpaca_backfill_seam_final import (
    BRIDGE_EXACT_LITERAL,
    POSTSEAM_ONLY,
    QUARANTINE_SEAM_CONTINUITY,
    RESET_AT_PROVIDER_SEAM,
    TERMINATE_PRESEAM_CONTINUITY,
)
from packages.features.historical_backfill_replay import (
    GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION,
    GATE9_FEATURE_REPLAY_ROLE,
    lifecycle_source_fingerprint,
    seam_requires_state_drop,
)
from packages.features.historical_backfill_replay_validation import (
    feature_keys_equal_after_utc_normalization,
)


def _fingerprint(**overrides: str) -> str:
    values = {
        "gate8_fingerprint": "gate8",
        "gate7_fingerprint": "gate7",
        "gate7_decision_sha256": "decision",
        "identity_segments_sha256": "identity",
        "canonical_inventory_fingerprint": "canonical",
        "production_feature_baseline_fingerprint": "features",
    }
    values.update(overrides)
    return lifecycle_source_fingerprint(**values)


def test_gate9_preflight_contract_is_isolated_daily_replay() -> None:
    assert GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION.startswith(
        "historical-backfill-feature-replay-preflight-v2"
    )
    assert "daily-identity-lifecycle-fresh-postseam" in GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION
    assert GATE9_FEATURE_REPLAY_ROLE == "ISOLATED_DAILY_FEATURE_REPLAY_NOT_PRODUCTION"


def test_gate9_seam_policy_drops_every_nonbridge_identity_at_seam() -> None:
    assert seam_requires_state_drop(RESET_AT_PROVIDER_SEAM) is True
    assert seam_requires_state_drop(TERMINATE_PRESEAM_CONTINUITY) is True
    assert seam_requires_state_drop(QUARANTINE_SEAM_CONTINUITY) is True
    assert seam_requires_state_drop(POSTSEAM_ONLY) is True
    assert seam_requires_state_drop(BRIDGE_EXACT_LITERAL) is False


def test_gate9_validator_normalizes_timezone_aliases_for_exact_keys() -> None:
    expected = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "timestamp_utc": pd.to_datetime(["2021-08-16T13:30:00Z"], utc=True),
        }
    )
    actual = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "timestamp_utc": pd.Series(
                [pd.Timestamp("2021-08-16T13:30:00", tz="Etc/UTC")]
            ),
        }
    )
    assert feature_keys_equal_after_utc_normalization(expected, actual) is True


def test_gate9_preflight_fingerprint_is_deterministic() -> None:
    first = _fingerprint()
    second = _fingerprint()
    assert first == second
    assert len(first) == 64


def test_gate9_preflight_fingerprint_binds_every_parent_evidence_class() -> None:
    baseline = _fingerprint()
    for field in (
        "gate8_fingerprint",
        "gate7_fingerprint",
        "gate7_decision_sha256",
        "identity_segments_sha256",
        "canonical_inventory_fingerprint",
        "production_feature_baseline_fingerprint",
    ):
        assert _fingerprint(**{field: f"changed-{field}"}) != baseline
