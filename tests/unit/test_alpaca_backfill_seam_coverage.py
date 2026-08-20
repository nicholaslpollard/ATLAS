from __future__ import annotations

from datetime import date

from packages.data.alpaca_backfill_seam_coverage import (
    ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION,
    MASSIVE_COVERAGE_HORIZON_SESSIONS,
    SEAM_RESET_POLICY,
    classify_massive_coverage,
    seam_promotion_policy,
)


def test_gate7c_contract_is_explicit_coverage_horizon() -> None:
    assert ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION.startswith(
        "historical-backfill-seam-v3"
    )
    assert "coverage-horizon" in ALPACA_BACKFILL_SEAM_COVERAGE_CONTRACT_VERSION


def test_gate7c_horizon_is_twenty_massive_sessions() -> None:
    assert MASSIVE_COVERAGE_HORIZON_SESSIONS == 20


def test_gate7c_unique_reference_with_later_bar_is_resumed_coverage() -> None:
    assert classify_massive_coverage(
        reference_identity_count=1,
        first_massive_session=date(2021, 8, 17),
    ) == "MASSIVE_COVERAGE_RESUMES_UNIQUE_REFERENCE"


def test_gate7c_bar_without_seam_reference_is_review() -> None:
    assert classify_massive_coverage(
        reference_identity_count=0,
        first_massive_session=date(2021, 8, 19),
    ) == "REVIEW_MASSIVE_BAR_WITHOUT_SEAM_REFERENCE"


def test_gate7c_unique_reference_without_bar_stays_explicit_gap() -> None:
    assert classify_massive_coverage(
        reference_identity_count=1,
        first_massive_session=None,
    ) == "MASSIVE_REFERENCE_PRESENT_NO_BAR_IN_HORIZON"


def test_gate7c_absent_reference_without_bar_stays_explicit_gap() -> None:
    assert classify_massive_coverage(
        reference_identity_count=0,
        first_massive_session=None,
    ) == "MASSIVE_REFERENCE_ABSENT_NO_BAR_IN_HORIZON"


def test_gate7c_ambiguous_reference_always_requires_review() -> None:
    assert classify_massive_coverage(
        reference_identity_count=2,
        first_massive_session=date(2021, 8, 20),
    ) == "REVIEW_MASSIVE_REFERENCE_IDENTITY_AMBIGUOUS"


def test_gate7c_all_discontinuity_classes_reset_continuity() -> None:
    for coverage_class in (
        "MASSIVE_COVERAGE_RESUMES_UNIQUE_REFERENCE",
        "REVIEW_MASSIVE_BAR_WITHOUT_SEAM_REFERENCE",
        "MASSIVE_REFERENCE_PRESENT_NO_BAR_IN_HORIZON",
        "MASSIVE_REFERENCE_ABSENT_NO_BAR_IN_HORIZON",
        "REVIEW_MASSIVE_REFERENCE_IDENTITY_AMBIGUOUS",
    ):
        assert seam_promotion_policy(coverage_class) == SEAM_RESET_POLICY
