from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase24_gate1_policy import (
    PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE24_GATE1_CHALLENGER_VARIANTS,
    PHASE24_GATE1_EXTERNAL_PROVIDER_READS,
    PHASE24_GATE1_EXTERNAL_PROVIDER_WRITES,
    PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION,
    PHASE24_GATE1_INCUMBENT_PROTECTED_EVIDENCE_IS_FRESH,
    PHASE24_GATE1_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE24_GATE1_LIVE_WRITES,
    PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION,
    PHASE24_GATE1_MULTIPLE_TESTING_METHOD,
    PHASE24_GATE1_ORDER_WRITES,
    PHASE24_GATE1_OUTCOME_HORIZON_SESSIONS,
    PHASE24_GATE1_PAPER_SUBMITS,
    PHASE24_GATE1_PHASE11_SUPPORT_WRITES,
    PHASE24_GATE1_PRIMARY_COST_BPS,
    PHASE24_GATE1_PROTECTED_EVIDENCE_READS,
    PHASE24_GATE1_SELECTION_FOLDS,
    PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE24_GATE1_STRESS_COST_BPS,
    phase24_gate1_policy_fingerprint,
    phase24_gate1_policy_payload,
)


def main() -> None:
    variants = PHASE24_GATE1_CHALLENGER_VARIANTS
    ids = [item.variant_id for item in variants]
    family_direction = Counter((item.family, item.direction) for item in variants)
    directions = Counter(item.direction for item in variants)
    allowed_features = {
        "rsi_14",
        "relative_volume_20",
        "macd_hist_12_26_9",
    }
    allowed_comparisons = {"GT", "LT"}
    mutation_shapes_ok = True
    for item in variants:
        for mutation in item.mutations:
            if mutation.kind == "replace_right_value":
                mutation_shapes_ok = mutation_shapes_ok and mutation.left is None
                mutation_shapes_ok = mutation_shapes_ok and mutation.comparison is None
                mutation_shapes_ok = mutation_shapes_ok and mutation.right_value is not None
            elif mutation.kind == "add_condition":
                mutation_shapes_ok = mutation_shapes_ok and mutation.left in allowed_features
                mutation_shapes_ok = mutation_shapes_ok and mutation.comparison in allowed_comparisons
                mutation_shapes_ok = mutation_shapes_ok and mutation.right_value is not None
            else:
                mutation_shapes_ok = False

    expected_family_direction = {
        ("trend_following", "LONG"): 3,
        ("trend_following", "SHORT"): 3,
        ("momentum", "LONG"): 4,
        ("momentum", "SHORT"): 4,
        ("breakout", "LONG"): 4,
        ("breakout", "SHORT"): 4,
        ("pullback", "LONG"): 3,
        ("pullback", "SHORT"): 3,
    }
    policy = phase24_gate1_policy_payload()
    checks = {
        "policy_fingerprint_present": len(phase24_gate1_policy_fingerprint()) == 64,
        "bounded_challenger_count_28": len(variants) == 28,
        "challenger_ids_unique": len(ids) == len(set(ids)),
        "challengers_are_new_v2_only": all("_v2_" in value for value in ids),
        "symmetric_long_short_counts": directions == Counter({"LONG": 14, "SHORT": 14}),
        "family_direction_counts_locked": family_direction == Counter(expected_family_direction),
        "mutation_shapes_locked": mutation_shapes_ok,
        "three_session_outcome_horizon_preserved": PHASE24_GATE1_OUTCOME_HORIZON_SESSIONS == 3,
        "bootstrap_block_exceeds_outcome_horizon": PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS >= 2 * PHASE24_GATE1_OUTCOME_HORIZON_SESSIONS,
        "primary_cost_10bps": PHASE24_GATE1_PRIMARY_COST_BPS == 10.0,
        "stress_cost_25bps": PHASE24_GATE1_STRESS_COST_BPS == 25.0,
        "selection_has_six_chronological_folds": PHASE24_GATE1_SELECTION_FOLDS == 6,
        "selection_requires_five_positive_folds": PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS == 5,
        "selection_min_signal_sessions_stronger_than_v1": PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS >= 250,
        "internal_validation_min_signal_sessions_locked": PHASE24_GATE1_INTERNAL_MIN_SIGNAL_SESSIONS >= 80,
        "one_finalist_per_family_direction": PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION == 1,
        "multiple_testing_is_holm_within_family_direction": PHASE24_GATE1_MULTIPLE_TESTING_METHOD.startswith("HOLM_BONFERRONI"),
        "gate0_current_evidence_excluded_from_selection": PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION is False,
        "incumbent_protected_not_fresh": PHASE24_GATE1_INCUMBENT_PROTECTED_EVIDENCE_IS_FRESH is False,
        "protected_reads_disabled_in_gate1": PHASE24_GATE1_PROTECTED_EVIDENCE_READS is False,
        "provider_reads_disabled": PHASE24_GATE1_EXTERNAL_PROVIDER_READS is False,
        "provider_writes_disabled": PHASE24_GATE1_EXTERNAL_PROVIDER_WRITES is False,
        "order_writes_disabled": PHASE24_GATE1_ORDER_WRITES is False,
        "paper_submits_disabled": PHASE24_GATE1_PAPER_SUBMITS is False,
        "live_writes_disabled": PHASE24_GATE1_LIVE_WRITES is False,
        "phase11_support_writes_disabled": PHASE24_GATE1_PHASE11_SUPPORT_WRITES is False,
        "policy_declares_protected_gate_but_does_not_enable_reads": policy["protected_final_confirmation"]["reads_enabled_in_gate1"] is False,
    }

    print(f"Phase 24 Gate 1 policy fingerprint: {phase24_gate1_policy_fingerprint()}")
    print(f"Phase 24 Gate 1 challenger variants: {len(variants)}")
    print(f"Phase 24 Gate 1 family/direction counts: {dict(sorted(family_direction.items()))}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 24 Gate 1 preregistration validation failed: " + ", ".join(failed))
    print("Phase 24 Gate 1 preregistered challenger methodology: PASS")


if __name__ == "__main__":
    main()
