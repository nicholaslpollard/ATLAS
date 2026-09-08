from __future__ import annotations

from datetime import date, time

import pytest

from packages.strategies.b35_conditional_evidence_contract import (
    A34_PORTFOLIO_POLICY_FINGERPRINT,
    B34_PACK_FINGERPRINT,
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_CONTRACT,
    B35_PREOUTCOME_FINGERPRINT,
    CONSUMED_MASTER_END,
    CONSUMED_MASTER_START,
    DEVELOPMENT_LAST_SCORING_SESSION,
    EvidenceWindow,
    EXIT_POLICIES,
    FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS,
    FUTURE_BLIND_START_ON_OR_AFTER,
    RowUse,
    SELECTOR_SCORING_COST_BPS,
    bucket_absolute_gap_pct,
    bucket_hvd_volume_ratio,
    bucket_median_dollar_volume_20,
    bucket_opening_range_width_pct,
    bucket_premarket_relvol_20,
    bucket_prior_close_price,
    bucket_realized_volatility_20,
    bucket_signal_time_et,
    classify_session,
    frozen_contract_manifest,
    future_blind_unblind_permitted,
    validate_row_use,
)


def test_contract_is_frozen_pre_outcome_and_bound_to_b34() -> None:
    manifest = frozen_contract_manifest()
    assert manifest["contract"] == B35_PREOUTCOME_CONTRACT
    assert manifest["fingerprint"] == B35_PREOUTCOME_FINGERPRINT
    assert len(B35_PREOUTCOME_FINGERPRINT) == 64
    assert manifest["bound_b34_pack"]["fingerprint"] == B34_PACK_FINGERPRINT
    assert tuple(manifest["bound_b34_pack"]["strategy_ids"]) == B34_STRATEGY_IDS
    assert manifest["authority"] == {
        "performance_outcomes_opened": False,
        "development_outcome_access_permitted": False,
        "future_blind_outcome_access_permitted": False,
        "minute_replay_read_authority": False,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "broad_minute_materialization_authority": False,
        "promotion_authority": False,
        "next_gate": (
            "exact-head acceptance of this contract, followed by a separate hash-bound finite DEVELOPMENT "
            "replay authorization that still excludes the consumed master and future blind windows"
        ),
    }


def test_scoring_windows_exclude_everything_after_april_until_new_blind() -> None:
    assert classify_session(DEVELOPMENT_LAST_SCORING_SESSION) == EvidenceWindow.DEVELOPMENT
    assert classify_session(date(2026, 5, 1)) == EvidenceWindow.NONSCORING_WARMUP
    assert classify_session(CONSUMED_MASTER_START) == EvidenceWindow.CONSUMED_MASTER
    assert classify_session(CONSUMED_MASTER_END) == EvidenceWindow.CONSUMED_MASTER
    assert classify_session(date(2026, 8, 12)) == EvidenceWindow.NONSCORING_WARMUP
    assert classify_session(date(2026, 9, 7)) == EvidenceWindow.NONSCORING_WARMUP
    assert classify_session(FUTURE_BLIND_START_ON_OR_AFTER) == EvidenceWindow.FUTURE_BLIND


@pytest.mark.parametrize("use", [RowUse.SELECTOR_FIT, RowUse.DEVELOPMENT_OUTCOME])
def test_consumed_master_can_never_fit_or_score(use: RowUse) -> None:
    with pytest.raises(ValueError, match="through 2026-04-30"):
        validate_row_use(date(2026, 6, 15), use)


def test_future_signal_may_use_prior_rows_only_as_counted_warmup() -> None:
    validate_row_use(
        date(2026, 7, 15),
        RowUse.FUTURE_SIGNAL_WARMUP,
        blind_signal_session=date(2026, 9, 8),
    )
    with pytest.raises(ValueError, match="must precede"):
        validate_row_use(
            date(2026, 9, 8),
            RowUse.FUTURE_SIGNAL_WARMUP,
            blind_signal_session=date(2026, 9, 8),
        )


def test_future_blind_outcomes_cannot_open_early() -> None:
    with pytest.raises(ValueError, match="2026-09-08"):
        validate_row_use(date(2026, 9, 7), RowUse.FUTURE_BLIND_OUTCOME)
    validate_row_use(date(2026, 9, 8), RowUse.FUTURE_BLIND_OUTCOME)


def test_future_blind_requires_minimum_sessions_and_one_time_receipt_state() -> None:
    assert not future_blind_unblind_permitted(
        complete_xnys_sessions=FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS - 1,
        consumption_receipt_absent=True,
        contract_fingerprint_matches=True,
        strategy_pack_fingerprint_matches=True,
    )
    assert not future_blind_unblind_permitted(
        complete_xnys_sessions=FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS,
        consumption_receipt_absent=False,
        contract_fingerprint_matches=True,
        strategy_pack_fingerprint_matches=True,
    )
    assert future_blind_unblind_permitted(
        complete_xnys_sessions=FUTURE_BLIND_MIN_COMPLETE_XNYS_SESSIONS,
        consumption_receipt_absent=True,
        contract_fingerprint_matches=True,
        strategy_pack_fingerprint_matches=True,
    )


def test_all_four_exit_geometries_are_frozen_before_outcomes() -> None:
    by_strategy = {policy.strategy_id: policy for policy in EXIT_POLICIES}
    assert set(by_strategy) == set(B34_STRATEGY_IDS)
    assert by_strategy["b34_gap_continuation_v1"].stop_anchor == "prior_regular_close"
    assert (
        by_strategy["b34_opening_range_breakout_15m_v1"].stop_anchor
        == "opposite_opening_range_boundary"
    )
    assert (
        by_strategy["b34_premarket_relvol_consolidation_v1"].stop_anchor
        == "premarket_consolidation_low"
    )
    assert by_strategy["b34_highest_volume_day_style_v1"].target_r_multiple == 2.0


def test_selector_is_deliberately_cost_conservative_and_long_only_at_portfolio_layer() -> None:
    manifest = frozen_contract_manifest()
    assert SELECTOR_SCORING_COST_BPS == 50
    assert manifest["costs"]["execution_stress_cost_bps"] == 100
    assert manifest["portfolio"]["bound_a34_policy_fingerprint"] == A34_PORTFOLIO_POLICY_FINGERPRINT
    assert manifest["portfolio"]["short_portfolio_admission"] is False
    assert manifest["portfolio"]["short_blocker"] == "borrow/locate/recall economics remain unavailable"


def test_market_regime_clock_is_prior_close_not_same_day_close() -> None:
    manifest = frozen_contract_manifest()
    market_regime = next(
        item for item in manifest["conditions"] if item["condition_id"] == "prior_market_regime"
    )
    assert "PRIOR regular-session close" in market_regime["asof_rule"]
    assert "never same-day close" in market_regime["asof_rule"]


def test_selector_training_uses_only_training_fold_and_abstains_without_positive_lcb() -> None:
    selector = frozen_contract_manifest()["selector"]
    assert selector["same_session_outcomes_forbidden"] is True
    assert selector["eligible_score"] == "strictly greater than zero; otherwise abstain/cash"
    assert selector["minimum_cell"] == {
        "opportunities": 60,
        "unique_sessions": 30,
        "unique_instruments": 20,
    }
    assert "training-fold outcomes only" in selector["score"]


def test_multiplicity_and_robustness_cannot_silently_select_a_perturbation() -> None:
    manifest = frozen_contract_manifest()
    assert manifest["multiplicity"]["all_primary_trials_ledgered"] is True
    assert manifest["multiplicity"]["unadjusted_condition_p_values_cannot_promote"] is True
    assert manifest["multiplicity"]["deflated_sharpe_required_as_diagnostic"] is True
    assert manifest["multiplicity"]["pbo_required_as_diagnostic_when_evaluable"] is True
    assert manifest["robustness"]["perturbations_are_diagnostic_only"] is True
    assert manifest["robustness"]["perturbation_cannot_replace_primary_frozen_strategy"] is True


def test_condition_bucket_boundaries_are_explicit_and_deterministic() -> None:
    assert bucket_prior_close_price(4.99) == "LT_5"
    assert bucket_prior_close_price(5.0) == "5_TO_20"
    assert bucket_prior_close_price(100.0) == "GE_100"
    assert bucket_median_dollar_volume_20(None) == "UNAVAILABLE"
    assert bucket_median_dollar_volume_20(10_000_000) == "10M_TO_50M"
    assert bucket_realized_volatility_20(0.50) == "50_TO_100PCT"
    assert bucket_absolute_gap_pct(-0.10) == "GE_10PCT"
    assert bucket_premarket_relvol_20(4.0) == "4_TO_8"
    assert bucket_opening_range_width_pct(0.04) == "GE_4PCT"
    assert bucket_hvd_volume_ratio(1.5) == "1_5_TO_2"
    assert bucket_signal_time_et(time(9, 44)) == "0931_TO_0944"
    assert bucket_signal_time_et(time(9, 45)) == "0945_TO_1000"
    assert bucket_signal_time_et(time(11, 30)) == "1031_TO_1130"
    with pytest.raises(ValueError, match="09:31..11:30"):
        bucket_signal_time_et(time(11, 31))
