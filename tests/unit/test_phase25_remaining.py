from __future__ import annotations

from packages.backtesting.phase24_gate2 import TrancheMetrics, holm_bonferroni
from packages.backtesting.phase25_gate10 import protected_checks
from packages.backtesting.phase25_gate8_policy import (
    ACCEPTED_GATE7_POLICY_FINGERPRINT,
    PHASE25_GATE8_DEVELOPMENT_END,
    PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE8_PROTECTED_START,
    PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED,
    PHASE25_GATE9_MULTIPLE_TESTING_METHOD,
    PHASE25_GATE9_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE9_SUPPORT_REPLACEMENT_ALLOWED,
    PHASE25_GATE10_FINALISTS_ONLY,
    PHASE25_GATE10_PROTECTED_EVIDENCE_ALLOWED,
    PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH,
    PHASE25_GATE10_SUPPORT_REPLACEMENT_ALLOWED,
    PHASE25_GATE10_ZERO_FINALISTS_ZERO_PROTECTED_READS,
    PHASE25_GATE11_FUTURE_PROSPECTIVE_REQUIRED_FOR_AUTHORITY,
    PHASE25_GATE11_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate8_policy_fingerprint,
    phase25_gate9_policy_fingerprint,
    phase25_gate10_policy_fingerprint,
    phase25_gate11_policy_fingerprint,
)
from packages.backtesting.phase25_gate7_policy import phase25_gate7_policy_fingerprint


def _metrics(*, lcb: float = 0.001, positive_folds: int = 3) -> TrancheMetrics:
    return TrancheMetrics(
        raw_rows=120,
        signal_sessions=30,
        primary_mean_return=0.004,
        primary_median_return=0.003,
        primary_positive_rate=0.60,
        primary_lcb=lcb,
        primary_bootstrap_p_value=0.01,
        stress_mean_return=0.002,
        max_single_session_row_fraction=0.05,
        fold_means=(0.003, 0.004, 0.005),
        positive_folds=positive_folds,
        eligible_year_means={},
        positive_year_fraction=None,
        eligible_regime_means={},
        positive_regime_fraction=None,
    )


def test_remaining_gate_policies_are_preregistered_and_no_support_write() -> None:
    assert ACCEPTED_GATE7_POLICY_FINGERPRINT == "2800bd82670b8f763a9c5f5c080301e20ab6462f82dd949f7cec0a800e989c31"
    assert phase25_gate7_policy_fingerprint() == ACCEPTED_GATE7_POLICY_FINGERPRINT
    assert PHASE25_GATE8_DEVELOPMENT_END < PHASE25_GATE8_PROTECTED_START
    assert PHASE25_GATE8_PROTECTED_EVIDENCE_ALLOWED is False
    assert PHASE25_GATE8_SUPPORT_REPLACEMENT_ALLOWED is False
    assert PHASE25_GATE9_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_8_INCUMBENTS"
    assert PHASE25_GATE9_PROTECTED_EVIDENCE_ALLOWED is False
    assert PHASE25_GATE9_SUPPORT_REPLACEMENT_ALLOWED is False
    assert PHASE25_GATE10_PROTECTED_EVIDENCE_ALLOWED is True
    assert PHASE25_GATE10_PROTECTED_EVIDENCE_FRESH is False
    assert PHASE25_GATE10_FINALISTS_ONLY is True
    assert PHASE25_GATE10_ZERO_FINALISTS_ZERO_PROTECTED_READS is True
    assert PHASE25_GATE10_SUPPORT_REPLACEMENT_ALLOWED is False
    assert PHASE25_GATE11_SUPPORT_REPLACEMENT_ALLOWED is False
    assert PHASE25_GATE11_FUTURE_PROSPECTIVE_REQUIRED_FOR_AUTHORITY is True
    assert all(
        len(value()) == 64
        for value in (
            phase25_gate8_policy_fingerprint,
            phase25_gate9_policy_fingerprint,
            phase25_gate10_policy_fingerprint,
            phase25_gate11_policy_fingerprint,
        )
    )


def test_gate10_protected_checks_require_robust_positive_evidence() -> None:
    checks = protected_checks(_metrics())
    assert all(checks.values())
    failed = protected_checks(_metrics(lcb=-0.0001))
    assert failed["primary_lcb_positive"] is False
    failed_folds = protected_checks(_metrics(positive_folds=1))
    assert failed_folds["positive_folds"] is False


def test_gate9_global_holm_applies_across_all_eight_incumbents() -> None:
    p_values = {
        f"s{i}": value
        for i, value in enumerate((0.001, 0.002, 0.003, 0.004, 0.006, 0.01, 0.03, 0.20), start=1)
    }
    decisions = holm_bonferroni(p_values, alpha=0.05)
    assert len(decisions) == 8
    assert decisions["s1"]["threshold"] == 0.05 / 8
    assert decisions["s1"]["rejected_null"] is True
    assert decisions["s7"]["rejected_null"] is False
    assert decisions["s8"]["rejected_null"] is False
