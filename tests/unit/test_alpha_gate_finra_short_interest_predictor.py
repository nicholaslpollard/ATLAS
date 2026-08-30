from datetime import date

from packages.backtesting.alpha_gate_finra_short_interest_predictor import (
    _average_tie_percentiles,
    _candidate,
    frozen_settlement_dates,
)


def test_frozen_finra_settlement_schedule_has_expected_boundaries_and_anchors() -> None:
    dates = frozen_settlement_dates()
    assert len(dates) == 116
    assert len(set(dates)) == 116
    assert dates[0] == date(2021, 6, 30)
    assert dates[-1] == date(2026, 4, 15)
    assert date(2026, 3, 13) in dates
    assert date(2026, 3, 31) in dates
    assert date(2026, 4, 15) in dates


def test_average_tie_percentiles_are_deterministic() -> None:
    assert _average_tie_percentiles([1.0, 2.0, 2.0, 4.0]) == (
        0.0,
        0.5,
        0.5,
        1.0,
    )
    assert _average_tie_percentiles([5.0]) == (0.5,)
    assert _average_tie_percentiles([]) == ()


def test_candidate_classification_uses_exact_frozen_boundaries() -> None:
    assert _candidate(0.90, 0.80) == (
        "rapid_short_build_crowded_short",
        "SHORT",
    )
    assert _candidate(0.90, 0.799999) == (
        "rapid_short_build_non_crowded_short",
        "SHORT",
    )
    assert _candidate(0.10, 0.80) == (
        "rapid_short_cover_crowded_long",
        "LONG",
    )
    assert _candidate(0.10, 0.799999) == (
        "rapid_short_cover_non_crowded_long",
        "LONG",
    )
    assert _candidate(0.100001, 0.95) is None
    assert _candidate(0.899999, 0.95) is None
