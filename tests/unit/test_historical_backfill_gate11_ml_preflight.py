from __future__ import annotations

from datetime import date

from packages.ml.historical_backfill_long_history_preflight import (
    GATE11_ACCEPTED_MODEL_REPLACEMENT_ALLOWED,
    GATE11_FINAL_HOLDOUT_USED_FOR_SELECTION,
    GATE11_INTRADAY_SYNTHESIS_ALLOWED,
    GATE11_LONG_HISTORY_COMPARISON_POLICY,
    GATE11_LONG_HISTORY_ORIGIN_DATE,
    GATE11_PRESEAM_END_DATE,
    OUTCOME_END,
    OUTCOME_PROVIDER_SEAM,
    OUTCOME_SAME_SYMBOL_MISSING,
    OUTCOME_SPLIT,
    OUTCOME_USABLE,
    classify_preseam_outcome,
    three_way_comparison_contract,
)


def test_gate11_comparison_contract_separates_lineage_from_added_history() -> None:
    policy = three_way_comparison_contract()
    assert policy["policy"] == GATE11_LONG_HISTORY_COMPARISON_POLICY
    assert policy["A"] == "FROZEN_ACCEPTED_PHASE10_DATASET_AND_MODEL"
    assert policy["B"] == "NEW_FEATURE_LINEAGE_PHASE10_ORIGIN_REBASE"
    assert policy["C"] == "NEW_FEATURE_LINEAGE_2016_HISTORY_EXTENSION"
    assert policy["A_to_B_effect"] == "FEATURE_LINEAGE_WARMUP_POPULATION_AND_LABEL_REBASE"
    assert policy["B_to_C_effect"] == "MARGINAL_PRE2021_HISTORY_AFTER_GATE11_STRUCTURAL_RECONCILIATION"


def test_gate11_preflight_cannot_replace_model_or_synthesize_intraday() -> None:
    assert GATE11_ACCEPTED_MODEL_REPLACEMENT_ALLOWED is False
    assert GATE11_FINAL_HOLDOUT_USED_FOR_SELECTION is False
    assert GATE11_INTRADAY_SYNTHESIS_ALLOWED is False
    policy = three_way_comparison_contract()
    assert policy["accepted_model_replacement_allowed_by_preflight"] is False
    assert policy["final_holdout_used_for_model_selection"] is False
    assert policy["synthetic_pre2021_intraday_allowed"] is False


def test_gate11_history_boundaries_are_explicit() -> None:
    assert GATE11_LONG_HISTORY_ORIGIN_DATE == date(2016, 1, 4)
    assert GATE11_PRESEAM_END_DATE == date(2021, 8, 13)


def test_preseam_outcome_classification_is_fail_closed() -> None:
    assert (
        classify_preseam_outcome(
            future_date=None,
            future_close_present=False,
            split_crossing=False,
        )
        == OUTCOME_END
    )
    assert (
        classify_preseam_outcome(
            future_date=date(2021, 8, 16),
            future_close_present=True,
            split_crossing=False,
        )
        == OUTCOME_PROVIDER_SEAM
    )
    assert (
        classify_preseam_outcome(
            future_date=date(2021, 8, 13),
            future_close_present=False,
            split_crossing=False,
        )
        == OUTCOME_SAME_SYMBOL_MISSING
    )
    assert (
        classify_preseam_outcome(
            future_date=date(2021, 8, 13),
            future_close_present=True,
            split_crossing=True,
        )
        == OUTCOME_SPLIT
    )


def test_preseam_outcome_usable_only_after_all_censors_clear() -> None:
    assert (
        classify_preseam_outcome(
            future_date=date(2021, 8, 13),
            future_close_present=True,
            split_crossing=False,
        )
        == OUTCOME_USABLE
    )
