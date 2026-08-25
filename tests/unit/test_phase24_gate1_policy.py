from __future__ import annotations

from collections import Counter

from packages.backtesting.phase24_gate1_policy import (
    PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE24_GATE1_CHALLENGER_VARIANTS,
    PHASE24_GATE1_EXTERNAL_PROVIDER_READS,
    PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION,
    PHASE24_GATE1_INCUMBENT_PROTECTED_EVIDENCE_IS_FRESH,
    PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION,
    PHASE24_GATE1_OUTCOME_HORIZON_SESSIONS,
    PHASE24_GATE1_PHASE11_SUPPORT_WRITES,
    PHASE24_GATE1_PRIMARY_COST_BPS,
    PHASE24_GATE1_PROTECTED_EVIDENCE_READS,
    PHASE24_GATE1_SELECTION_FOLDS,
    PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE24_GATE1_STRESS_COST_BPS,
    phase24_gate1_policy_fingerprint,
)


def test_phase24_gate1_preregistration_is_local_and_cannot_replace_support() -> None:
    assert PHASE24_GATE1_EXTERNAL_PROVIDER_READS is False
    assert PHASE24_GATE1_PROTECTED_EVIDENCE_READS is False
    assert PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION is False
    assert PHASE24_GATE1_INCUMBENT_PROTECTED_EVIDENCE_IS_FRESH is False
    assert PHASE24_GATE1_PHASE11_SUPPORT_WRITES is False


def test_phase24_gate1_dependence_and_robustness_gates_are_stronger_than_v1() -> None:
    assert PHASE24_GATE1_OUTCOME_HORIZON_SESSIONS == 3
    assert PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS >= 6
    assert PHASE24_GATE1_SELECTION_FOLDS == 6
    assert PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS == 5
    assert PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS >= 250
    assert PHASE24_GATE1_PRIMARY_COST_BPS == 10.0
    assert PHASE24_GATE1_STRESS_COST_BPS == 25.0
    assert PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION == 1


def test_phase24_gate1_challenger_space_is_bounded_symmetric_and_unique() -> None:
    variants = PHASE24_GATE1_CHALLENGER_VARIANTS
    assert len(variants) == 28
    ids = [item.variant_id for item in variants]
    assert len(ids) == len(set(ids))
    assert all("_v2_" in item for item in ids)
    assert Counter(item.direction for item in variants) == Counter({"LONG": 14, "SHORT": 14})
    assert Counter((item.family, item.direction) for item in variants) == Counter(
        {
            ("trend_following", "LONG"): 3,
            ("trend_following", "SHORT"): 3,
            ("momentum", "LONG"): 4,
            ("momentum", "SHORT"): 4,
            ("breakout", "LONG"): 4,
            ("breakout", "SHORT"): 4,
            ("pullback", "LONG"): 3,
            ("pullback", "SHORT"): 3,
        }
    )
    assert len(phase24_gate1_policy_fingerprint()) == 64


def test_phase24_gate1_variants_only_tighten_known_incumbent_rules() -> None:
    allowed_added_features = {"rsi_14", "relative_volume_20", "macd_hist_12_26_9"}
    allowed_replace_reasons = {
        "rsi_above_midline",
        "rsi_below_midline",
        "volume_above_20_average",
    }
    for variant in PHASE24_GATE1_CHALLENGER_VARIANTS:
        assert variant.base_strategy_id.endswith("_v1")
        for mutation in variant.mutations:
            if mutation.kind == "add_condition":
                assert mutation.left in allowed_added_features
                assert mutation.comparison in {"GT", "LT"}
                assert mutation.right_value is not None
            else:
                assert mutation.kind == "replace_right_value"
                assert mutation.reason_code in allowed_replace_reasons
                assert mutation.right_value is not None
