from __future__ import annotations

from datetime import date

from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.universe_probe import (
    ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS,
    ML_HISTORY_ORIGIN_DATE,
    ML_LONG_GAP_CALENDAR_DAYS,
    ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION,
    _count_dict,
    _fraction,
)


def test_phase10_gate1_contract_is_versioned() -> None:
    assert ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION == (
        "ml-training-universe-probe-v1-historical-observation-survivorship-identity-audit"
    )


def test_phase10_history_origin_matches_permanent_feature_history() -> None:
    assert ML_HISTORY_ORIGIN_DATE == date(2021, 8, 16)


def test_phase10_gate1_is_evidence_only_candidate_floor() -> None:
    assert ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS == 250_000.0
    assert ML_LONG_GAP_CALENDAR_DAYS == 30


def test_fraction_is_safe_for_empty_denominator() -> None:
    assert _fraction(0, 0) == 0.0
    assert _fraction(1, 4) == 0.25


def test_gate1_uses_all_33_core_features_and_preserves_null_adjustment_bucket() -> None:
    assert len(CORE_FEATURE_REGISTRY.all()) == 33
    assert _count_dict([(False, 3), (True, 2), (None, 1)]) == {
        "False": 3,
        "True": 2,
        "<NULL>": 1,
    }
