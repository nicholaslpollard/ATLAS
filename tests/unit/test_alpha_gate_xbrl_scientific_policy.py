from __future__ import annotations

from datetime import date

import exchange_calendars as xcals

from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
    XBRL_DEVELOPMENT_LAST_SIGNAL,
    XBRL_HYPOTHESES,
    XBRL_MULTIPLE_TESTING_METHOD,
    XBRL_PRIMARY_COST_BPS,
    XBRL_PRIMARY_HORIZON_SESSIONS,
    XBRL_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    XBRL_PROTECTED_START,
    XBRL_RUNNER_UP_SUBSTITUTION_ALLOWED,
    XBRL_SCIENTIFIC_FINGERPRINT,
    XBRL_STRESS_COST_BPS,
    xbrl_scientific_fingerprint,
)


def test_scientific_fingerprint_is_exact() -> None:
    assert xbrl_scientific_fingerprint() == XBRL_SCIENTIFIC_FINGERPRINT
    assert XBRL_SCIENTIFIC_FINGERPRINT == (
        "239215aad3c151200c77d214d5723e446877fcb014fb2280b9cd909b3ea379ef"
    )


def test_exactly_six_finite_hypotheses_are_frozen() -> None:
    assert [spec.candidate_id for spec in XBRL_HYPOTHESES] == [
        "gross_profitability_improvement_long",
        "gross_profitability_deterioration_short",
        "cash_profitability_improvement_long",
        "cash_profitability_deterioration_short",
        "accrual_quality_improvement_long",
        "accrual_quality_deterioration_short",
    ]
    assert [spec.direction for spec in XBRL_HYPOTHESES].count("LONG") == 3
    assert [spec.direction for spec in XBRL_HYPOTHESES].count("SHORT") == 3


def test_primary_horizon_and_outer_embargo_do_not_overlap() -> None:
    assert XBRL_PRIMARY_HORIZON_SESSIONS == 63
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range(XBRL_DEVELOPMENT_LAST_SIGNAL, XBRL_PROTECTED_START)
    # Index 0 is the final development signal. Index 63 is its primary exit;
    # protected starts on index 64, so the windows cannot overlap.
    assert len(sessions) == 65
    assert sessions[63].date() == date(2025, 4, 3)
    assert sessions[64].date() == date(2025, 4, 4)


def test_short_costs_include_more_friction_than_longs() -> None:
    assert XBRL_PRIMARY_COST_BPS == {"LONG": 10.0, "SHORT": 35.0}
    assert XBRL_STRESS_COST_BPS == {"LONG": 25.0, "SHORT": 100.0}
    assert XBRL_PRIMARY_COST_BPS["SHORT"] > XBRL_PRIMARY_COST_BPS["LONG"]
    assert XBRL_STRESS_COST_BPS["SHORT"] > XBRL_STRESS_COST_BPS["LONG"]


def test_selection_is_global_and_protected_cannot_be_shopped() -> None:
    assert XBRL_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_6"
    assert XBRL_RUNNER_UP_SUBSTITUTION_ALLOWED is False
    assert XBRL_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is False
