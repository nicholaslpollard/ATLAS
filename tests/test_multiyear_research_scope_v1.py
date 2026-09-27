from __future__ import annotations

"""Six-year scope and zero-provider credit preflight contracts."""

from datetime import UTC, date, datetime

import pytest

from packages.simulation.multiyear_research_scope_v1 import (
    MultiYearScopeError, plan_multiyear_scope,
)


ASOF = datetime(2026, 9, 27, 16, 25, tzinfo=UTC)


def test_six_calendar_years_stay_visible_with_partial_2021_and_ytd_2026():
    plan = plan_multiyear_scope(as_of_utc=ASOF)
    assert plan["requested_calendar_years"] == [2021, 2022, 2023, 2024, 2025, 2026]
    assert plan["starter_five_year_floor"] == "2021-09-27"
    assert plan["research_end"] == "2026-09-25"
    assert plan["provider_requests_executed"] == 0
    assert plan["requested_preparation_max_new_requests"] == 0
    assert plan["default_tuning_mode"] == "STRICT_LOCAL_OFFLINE_FROZEN_INPUTS"
    assert plan["year_slices"][0]["starter_coverage"] == "PARTIAL_ROLLING_FIVE_YEAR_WINDOW"
    assert plan["year_slices"][0]["starter_option_start"] == "2021-09-27"
    assert "ACCEPTED_2022_6398" in plan["year_slices"][1]["known_local_option_scope"]
    assert "NOT_FULL_UNIVERSE" in plan["year_slices"][4]["known_local_option_scope"]
    assert "RECENT_GAP" in plan["year_slices"][-1]["news_scope"]
    assert all(year["simulation_authority"] == "NO_COMMON_CLOCK_TRADE_PNL_UNTIL_MATCHED_INPUTS"
               for year in plan["year_slices"])


def test_provider_credit_reserve_refuses_unsafe_request():
    with pytest.raises(MultiYearScopeError, match="paid prepare"):
        plan_multiyear_scope(
            as_of_utc=ASOF, max_new_provider_requests=250,
            max_observed_provider_credits=250, remaining_provider_credits=600,
            authorize_paid_preparation=True,
        )
    with pytest.raises(MultiYearScopeError, match="paid prepare"):
        plan_multiyear_scope(
            as_of_utc=ASOF, max_new_provider_requests=250,
            max_observed_provider_credits=250, remaining_provider_credits=1800,
        )
    accepted = plan_multiyear_scope(
        as_of_utc=ASOF, max_new_provider_requests=200,
        max_observed_provider_credits=250, remaining_provider_credits=1800,
        authorize_paid_preparation=True,
    )
    assert accepted["paid_preparation_authorized_by_this_plan"] is False
    assert accepted["provider_requests_executed"] == 0
    assert accepted["provider_minimum_remaining_reserve"] == 500


def test_invalid_future_research_and_naive_asof_refused():
    with pytest.raises(MultiYearScopeError, match="aware"):
        plan_multiyear_scope(as_of_utc=datetime(2026, 9, 27))
    with pytest.raises(MultiYearScopeError, match="last full session"):
        plan_multiyear_scope(as_of_utc=ASOF, research_end=date(2026, 9, 27))
    with pytest.raises(MultiYearScopeError, match="0..250"):
        plan_multiyear_scope(
            as_of_utc=ASOF, max_new_provider_requests=251,
            max_observed_provider_credits=251,
        )
