from __future__ import annotations

import numpy as np

from packages.backtesting.b35_robustness_analysis import (
    PROFILE_IDS,
    _bootstrap_profile,
    _centered_bootstrap_pvalue,
    _concentration,
    _deflated_sharpe,
    _max_negative_streak,
    _pbo_cscv,
    _perturbation_audit,
    benjamini_hochberg,
)


def test_benjamini_hochberg_adjusts_monotonically_and_rejects_expected() -> None:
    adjusted, rejected = benjamini_hochberg([0.001, 0.01, 0.04, 0.20], q=0.05)
    assert np.allclose(adjusted, [0.004, 0.02, 0.05333333333333334, 0.20])
    assert rejected.tolist() == [True, True, False, False]


def test_centered_session_bootstrap_is_deterministic_and_directional() -> None:
    positive = np.array([0.02, 0.01, 0.03, 0.015, 0.025] * 10, dtype=float)
    p1 = _centered_bootstrap_pvalue(positive, seed_material="same-seed", draws=2000)
    p2 = _centered_bootstrap_pvalue(positive, seed_material="same-seed", draws=2000)
    assert p1 == p2
    assert p1 < 0.05
    assert _centered_bootstrap_pvalue(-positive, seed_material="negative", draws=2000) == 1.0


def test_loss_streak_distinguishes_cash_gaps() -> None:
    values = np.array([-0.01, 0.0, -0.02, -0.03, 0.01, -0.01], dtype=float)
    assert _max_negative_streak(values, ignore_flat=False) == 2
    assert _max_negative_streak(values, ignore_flat=True) == 3


def test_concentration_reports_positive_and_absolute_shares() -> None:
    result = _concentration(np.array([0.4, 0.3, 0.2, 0.1, -0.5], dtype=float))
    assert abs(float(result["top_1_positive_session_share"]) - 0.4) < 1e-12
    assert abs(float(result["top_5_positive_session_share"]) - 1.0) < 1e-12
    assert abs(float(result["largest_absolute_session_share"]) - (0.5 / 1.5)) < 1e-12


def test_profile_bootstrap_is_deterministic() -> None:
    values = np.array([0.01, -0.005, 0.004, 0.0, 0.008, -0.002] * 20, dtype=float)
    first = _bootstrap_profile(values, seed_material="bootstrap", draws=500)
    second = _bootstrap_profile(values, seed_material="bootstrap", draws=500)
    assert first == second
    assert first["draws"] == 500
    assert 0.0 <= float(first["probability_mean_session_return_gt_zero"]) <= 1.0


def test_deflated_sharpe_profiles_are_finite_or_explicit() -> None:
    base = np.linspace(-0.01, 0.015, 128)
    profiles = {
        profile_id: base + index * 0.0002
        for index, profile_id in enumerate(PROFILE_IDS)
    }
    result = _deflated_sharpe(profiles)
    assert result["candidate_profile_count"] == len(PROFILE_IDS)
    assert len(result["profiles"]) == len(PROFILE_IDS)
    for item in result["profiles"]:
        probability = item["deflated_sharpe_probability"]
        assert probability is None or 0.0 <= float(probability) <= 1.0


def test_pbo_cscv_returns_valid_probability() -> None:
    rng = np.random.default_rng(7)
    n = 16 * 12
    common = rng.normal(0.0, 0.01, size=n)
    profiles = {}
    for index, profile_id in enumerate(PROFILE_IDS):
        profiles[profile_id] = common + (0.0004 * index)
    result = _pbo_cscv(profiles)
    assert result["partitions"] == 16
    assert result["combinations"] == 12870
    assert 0.0 <= float(result["probability_of_backtest_overfitting"]) <= 1.0
    assert set(result["in_sample_winner_counts"]) == set(PROFILE_IDS)


def test_perturbation_audit_never_approximates_missing_minute_path() -> None:
    result = _perturbation_audit()
    assert result["all_preregistered_perturbations_complete"] is False
    assert result["approximation_used"] is False
    assert "all_in_round_trip_cost_bps" in result["exact_from_retained_artifacts"]
    pending = result["requires_targeted_minute_replay"]
    assert "entry_delay_minutes" in pending
    assert "opening_range_minutes" in pending
    assert "gap_threshold_multiplier" in pending
    assert "premarket_relvol_threshold_multiplier" in pending
    assert "premarket_consolidation_range_multiplier" in pending
