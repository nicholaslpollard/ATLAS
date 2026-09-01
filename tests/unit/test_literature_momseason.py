from __future__ import annotations

from packages.backtesting.literature_momseason_feasibility import MomSeasonSourceFeasibility
from packages.backtesting.literature_momseason_policy import (
    LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS,
    MOMSEASON_HYPOTHESES,
    formation_months,
    literature_momseason_source_fingerprint,
    required_lag_reference_dates,
    temporal_capacity,
)
from packages.backtesting.literature_momseason_source import MomSeasonSourceAcquirer


def test_literature_family_is_externally_predeclared_before_outcomes() -> None:
    assert [item.hypothesis_id for item in MOMSEASON_HYPOTHESES] == [
        "momseason_short_year1",
        "momseason_years2_5",
    ]
    assert [item.external_signal for item in MOMSEASON_HYPOTHESES] == [
        "MomSeasonShort",
        "MomSeason",
    ]
    assert MOMSEASON_HYPOTHESES[0].lag_years == (1,)
    assert MOMSEASON_HYPOTHESES[1].lag_years == (2, 3, 4, 5)
    assert all(item.portfolio_period_months == 1 for item in MOMSEASON_HYPOTHESES)
    assert all(item.direction == "POSITIVE" for item in MOMSEASON_HYPOTHESES)


def test_current_master_holdout_has_only_two_complete_months() -> None:
    capacity = temporal_capacity()
    assert capacity["formation_months"] == 60
    assert capacity["development_complete_months"] == 56
    assert capacity["purge_boundary_months"] == 1
    assert capacity["protected_predictor_months"] == 3
    assert capacity["protected_complete_target_months"] == 2
    assert capacity["protected_complete_month_keys"] == ["2026-06", "2026-07"]
    assert capacity["protected_predictor_month_keys"] == [
        "2026-06",
        "2026-07",
        "2026-08",
    ]
    assert capacity["minimum_protected_complete_months"] == 12
    assert LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS == 12
    assert capacity["current_protected_temporal_capacity_sufficient"] is False


def test_boundary_months_are_classified_without_reading_returns() -> None:
    months = {item.month_start.strftime("%Y-%m"): item for item in formation_months()}
    assert months["2026-04"].scope == "DEVELOPMENT"
    assert months["2026-05"].scope == "PURGE_BOUNDARY"
    assert months["2026-06"].scope == "PROTECTED_COMPLETE"
    assert months["2026-07"].scope == "PROTECTED_COMPLETE"
    assert months["2026-08"].scope == "PROTECTED_PREDICTOR_ONLY"
    assert months["2026-08"].protected_target_complete is False


def test_lag_reference_plan_covers_only_predictor_history() -> None:
    dates = required_lag_reference_dates()
    assert len(dates) == 109
    assert dates[0].isoformat() == "2016-08-31"
    assert dates[-1].isoformat() == "2025-08-29"
    # The source-only reference plan stops before every 2026 target month.
    assert all(item.year <= 2025 for item in dates)


def test_source_modules_import_and_fingerprint_is_stable_shape() -> None:
    assert MomSeasonSourceAcquirer is not None
    assert MomSeasonSourceFeasibility is not None
    fingerprint = literature_momseason_source_fingerprint()
    assert len(fingerprint) == 64
    assert set(fingerprint).issubset(set("0123456789abcdef"))
