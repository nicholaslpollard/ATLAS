from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
    FINRA_SHORT_INTEREST_BUILD_PERCENTILE_MIN,
    FINRA_SHORT_INTEREST_COVER_PERCENTILE_MAX,
    FINRA_SHORT_INTEREST_CROWDED_PERCENTILE_MIN,
    FINRA_SHORT_INTEREST_HYPOTHESES,
    FINRA_SHORT_INTEREST_MAX_ROWS_PER_CANDIDATE_PER_SETTLEMENT,
    FINRA_SHORT_INTEREST_PRIMARY_COST_BPS,
    FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
    FINRA_SHORT_INTEREST_SELECTION_MIN_SIGNAL_SESSIONS,
    FINRA_SHORT_INTEREST_STRESS_COST_BPS,
    finra_short_interest_scientific_fingerprint,
)


def test_finra_scientific_fingerprint_is_frozen() -> None:
    assert finra_short_interest_scientific_fingerprint() == FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT


def test_finra_science_has_exactly_four_predeclared_hypotheses() -> None:
    assert [spec.candidate_id for spec in FINRA_SHORT_INTEREST_HYPOTHESES] == [
        "rapid_short_build_crowded_short",
        "rapid_short_build_non_crowded_short",
        "rapid_short_cover_crowded_long",
        "rapid_short_cover_non_crowded_long",
    ]
    assert [spec.direction for spec in FINRA_SHORT_INTEREST_HYPOTHESES] == [
        "SHORT", "SHORT", "LONG", "LONG"
    ]


def test_finra_source_only_thresholds_and_sampling_are_frozen() -> None:
    assert FINRA_SHORT_INTEREST_COVER_PERCENTILE_MAX == 0.10
    assert FINRA_SHORT_INTEREST_BUILD_PERCENTILE_MIN == 0.90
    assert FINRA_SHORT_INTEREST_CROWDED_PERCENTILE_MIN == 0.80
    assert FINRA_SHORT_INTEREST_MAX_ROWS_PER_CANDIDATE_PER_SETTLEMENT == 75


def test_finra_costs_are_direction_specific_and_conservative_for_shorts() -> None:
    assert FINRA_SHORT_INTEREST_PRIMARY_COST_BPS == {"LONG": 10.0, "SHORT": 35.0}
    assert FINRA_SHORT_INTEREST_STRESS_COST_BPS == {"LONG": 25.0, "SHORT": 100.0}
    assert FINRA_SHORT_INTEREST_PRIMARY_COST_BPS["SHORT"] > FINRA_SHORT_INTEREST_PRIMARY_COST_BPS["LONG"]


def test_finra_signal_session_minimum_matches_biweekly_design() -> None:
    assert FINRA_SHORT_INTEREST_SELECTION_MIN_SIGNAL_SESSIONS == 30
