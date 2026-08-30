from __future__ import annotations

from packages.backtesting.alpha_gate_beneficial_ownership_predictor import (
    candidate_for,
    extract_percent_of_class_values,
    maximum_percent_of_class,
)
from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
    BENEFICIAL_OWNERSHIP_AMENDMENTS_PERFORMANCE_ELIGIBLE,
    BENEFICIAL_OWNERSHIP_HYPOTHESES,
    BENEFICIAL_OWNERSHIP_MULTIPLE_TESTING_METHOD,
    BENEFICIAL_OWNERSHIP_PROTECTED_RETURNS_BEFORE_FINALIST_ALLOWED,
    BENEFICIAL_OWNERSHIP_RUNNER_UP_SUBSTITUTION_ALLOWED,
    BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
    beneficial_ownership_scientific_fingerprint,
)


def test_scientific_fingerprint_is_exact() -> None:
    assert beneficial_ownership_scientific_fingerprint() == BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT
    assert BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT == (
        "4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c"
    )


def test_exactly_four_nonoverlapping_initial_long_hypotheses() -> None:
    assert [spec.candidate_id for spec in BENEFICIAL_OWNERSHIP_HYPOTHESES] == [
        "initial_13d_5_to_10_long",
        "initial_13d_10_plus_long",
        "initial_13g_5_to_10_long",
        "initial_13g_10_plus_long",
    ]
    assert {spec.direction for spec in BENEFICIAL_OWNERSHIP_HYPOTHESES} == {"LONG"}
    assert BENEFICIAL_OWNERSHIP_AMENDMENTS_PERFORMANCE_ELIGIBLE is False
    assert BENEFICIAL_OWNERSHIP_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_4"
    assert BENEFICIAL_OWNERSHIP_RUNNER_UP_SUBSTITUTION_ALLOWED is False
    assert BENEFICIAL_OWNERSHIP_PROTECTED_RETURNS_BEFORE_FINALIST_ALLOWED is False


def test_structured_13d_percent_parser_uses_max_not_sum() -> None:
    text = """
    <reportingPersonInfo><percentOfClass>6.2</percentOfClass></reportingPersonInfo>
    <reportingPersonInfo><percentOfClass>6.2</percentOfClass></reportingPersonInfo>
    <reportingPersonInfo><percentOfClass>12.4</percentOfClass></reportingPersonInfo>
    """
    assert extract_percent_of_class_values(text) == (6.2, 12.4)
    assert maximum_percent_of_class(text) == 12.4
    assert candidate_for(form_family="13D_INITIAL", percent_of_class=12.4) == (
        "initial_13d_10_plus_long"
    )


def test_structured_13g_class_percent_parser() -> None:
    text = "<coverPageHeaderReportingPersonDetails><classPercent>7.4</classPercent></coverPageHeaderReportingPersonDetails>"
    assert maximum_percent_of_class(text) == 7.4
    assert candidate_for(form_family="13G_INITIAL", percent_of_class=7.4) == (
        "initial_13g_5_to_10_long"
    )


def test_legacy_percent_parser_handles_13d_and_13g_cover_labels() -> None:
    text = """
    <table><tr><td>Percent of class represented by amount in Row (11)</td><td>9.8%</td></tr></table>
    <table><tr><td>Percent of class represented by amount in row (9)</td><td>10.1 %</td></tr></table>
    """
    assert extract_percent_of_class_values(text) == (9.8, 10.1)


def test_invalid_percentages_and_below_five_do_not_create_signal() -> None:
    text = "<percentOfClass>0</percentOfClass><percentOfClass>101</percentOfClass>"
    assert extract_percent_of_class_values(text) == ()
    assert candidate_for(form_family="13D_INITIAL", percent_of_class=4.99) is None
    assert candidate_for(form_family="13G_AMENDMENT", percent_of_class=12.0) is None
