from __future__ import annotations

"""A real six-calendar-year research scope, not a 2022-only simulation claim.

The first run contract makes missing source coverage visible rather than
silently excluding years. Provider work is a separate, explicitly authorized
prepare operation; tuning/replay modes MUST use frozen local evidence.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-2021-through-2026-integrated-research-scope-v1"
START = date(2021, 1, 1)
STOP_YEAR = 2026
MIN_REMAINING_PROVIDER_CREDITS = 500
MAX_NEW_CREDITS_PER_PREPARATION_RUN = 250
PAPER_LIVE_AUTHORITY = False
ACCEPTED_2022_QUOTE_PLAN = (
    "017805741349c5bd93eead00123282cee8a3980fcf9d3c368147b0ed4bbe6786"
)
ACCEPTED_2022_EOD_REFERENCE = (
    "15901045e456335638714e1f0259f5dc5ada519a168801f3676eb8582a3e7598"
)


class MultiYearScopeError(ValueError):
    pass


@dataclass(frozen=True)
class CoverageYear:
    year: int
    research_start: str
    research_end: str
    starter_option_start: str
    starter_option_end: str
    starter_coverage: str
    known_local_option_scope: str
    news_scope: str
    simulation_authority: str


def _five_year_floor(as_of: date) -> date:
    try:
        return as_of.replace(year=as_of.year - 5)
    except ValueError:
        # Feb 29 five-year anniversary lands on Feb 28 in a nonleap year.
        return as_of.replace(year=as_of.year - 5, day=28)


def latest_completed_regular_session(as_of_utc: datetime) -> date:
    if not isinstance(as_of_utc, datetime) or as_of_utc.tzinfo is None:
        raise MultiYearScopeError("as_of_utc must be timezone-aware")
    calendar = get_market_calendar()
    current = as_of_utc.astimezone(UTC)
    sessions = calendar.sessions_in_range(
        current.date() - timedelta(days=15), current.date()
    )
    completed = [
        day for day in sessions
        if calendar.regular_open_close(day)[1] <= current
    ]
    if not completed:
        raise MultiYearScopeError("no completed regular session in lookback")
    return completed[-1]


def plan_multiyear_scope(
    *, as_of_utc: datetime,
    research_start: date = START,
    research_end: date | None = None,
    max_new_provider_requests: int = 0,
    max_observed_provider_credits: int = 0,
    remaining_provider_credits: int | None = None,
    authorize_paid_preparation: bool = False,
) -> dict[str, Any]:
    """Plan known/unknown years without a single external request.

    User-supplied remaining is informational; *actual* acquisition must check
    authoritative credit headers at dispatch and reserve the whole in-flight
    wave. This planner itself can never authorize or perform provider GETs.
    """
    if (
        not isinstance(research_start, date)
        or research_start != START
        or not isinstance(as_of_utc, datetime)
        or as_of_utc.tzinfo is None
    ):
        raise MultiYearScopeError("frozen 2021 start and aware as-of time required")
    last_close = latest_completed_regular_session(as_of_utc)
    end = research_end or last_close
    if not isinstance(end, date) or not date(2026, 1, 1) <= end <= last_close:
        raise MultiYearScopeError("end must be inside 2026 YTD through last full session")
    if (
        type(max_new_provider_requests) is not int
        or type(max_observed_provider_credits) is not int
        or not 0 <= max_new_provider_requests <= MAX_NEW_CREDITS_PER_PREPARATION_RUN
        or not 0 <= max_observed_provider_credits <= MAX_NEW_CREDITS_PER_PREPARATION_RUN
        or (max_new_provider_requests == 0) != (max_observed_provider_credits == 0)
    ):
        raise MultiYearScopeError("preparation request/credit caps outside 0..250")
    if max_new_provider_requests:
        if (
            not authorize_paid_preparation
            or remaining_provider_credits is None
            or type(remaining_provider_credits) is not int
            or remaining_provider_credits
                < max_observed_provider_credits + MIN_REMAINING_PROVIDER_CREDITS
        ):
            raise MultiYearScopeError(
                "paid prepare requires explicit authorization, fresh credit evidence "
                "and an entire 500-credit reserve"
            )
    elif authorize_paid_preparation:
        raise MultiYearScopeError("paid authorization without a budget is invalid")
    first_starter = _five_year_floor(as_of_utc.astimezone(UTC).date())
    # This scope only covers whole or partial calendar-year research slices.
    years: list[CoverageYear] = []
    for year in range(research_start.year, STOP_YEAR + 1):
        start = date(year, 1, 1)
        finish = min(date(year, 12, 31), end)
        accessible_start = max(start, first_starter)
        accessible_end = finish
        covered = accessible_start <= accessible_end
        starter = (
            "UNAVAILABLE_OUTSIDE_ROLLING_WINDOW" if not covered else
            "PARTIAL_ROLLING_FIVE_YEAR_WINDOW" if accessible_start > start else
            "ELIGIBLE_SOURCE_ONLY_NOT_PROVEN_COMPLETE"
        )
        known = (
            "ACCEPTED_2022_6398_CALL_EOD_SERIES_SELECTED_EXPIRY_ENVELOPE"
            if year == 2022 else
            "SOME_2025_PILOT_ONLY_NOT_FULL_UNIVERSE"
            if year == 2025 else
            "NOT_YET_ACCEPTED_FOR_THIS_SIX_YEAR_COMPARATOR"
        )
        years.append(CoverageYear(
            year=year, research_start=start.isoformat(), research_end=finish.isoformat(),
            starter_option_start=accessible_start.isoformat() if covered else "",
            starter_option_end=accessible_end.isoformat() if covered else "",
            starter_coverage=starter, known_local_option_scope=known,
            news_scope=(
                "ACCEPTED_HISTORICAL_ALPACA_CORPUS_WITH_PIT_CHRONOLOGY_LIMITATIONS"
                if year <= 2025 else
                "ACCEPTED_NEWS_THROUGH_2026_09_19_ONLY_RECENT_GAP_REMAINS"
            ),
            simulation_authority="NO_COMMON_CLOCK_TRADE_PNL_UNTIL_MATCHED_INPUTS",
        ))
    result: dict[str, Any] = {
        "contract": CONTRACT,
        "requested_calendar_years": [y.year for y in years],
        "as_of_utc": as_of_utc.astimezone(UTC).isoformat(),
        "research_start": research_start.isoformat(),
        "research_end": end.isoformat(),
        "starter_five_year_floor": first_starter.isoformat(),
        "accepted_2022_quote_plan_fingerprint": ACCEPTED_2022_QUOTE_PLAN,
        "accepted_2022_eod_reference_fingerprint": ACCEPTED_2022_EOD_REFERENCE,
        "year_slices": [vars(y) for y in years],
        "default_tuning_mode": "STRICT_LOCAL_OFFLINE_FROZEN_INPUTS",
        "historical_trade_modes": [
            "MATCHED_LATER_EOD_STOCK_AND_OPTION_OBSERVATIONS",
            "ORIGINAL_0935_ONLY_WITH_INDEPENDENT_INTRADAY_QUOTE_EVIDENCE",
        ],
        "paid_preparation_authorized_by_this_plan": False,
        "requested_preparation_max_new_requests": max_new_provider_requests,
        "requested_preparation_max_observed_credits": max_observed_provider_credits,
        "provider_remaining_asserted_by_caller_not_verified": remaining_provider_credits,
        "provider_minimum_remaining_reserve": MIN_REMAINING_PROVIDER_CREDITS,
        "provider_requests_executed": 0,
        "no_automatic_provider_retry_or_budget_rollover": True,
        "missing_scenario_rows_never_silently_excluded": True,
        "option_greeks_are_model_derived_not_historical_provider_greeks": True,
        "protected_outcomes_read": 0,
        "paper": PAPER_LIVE_AUTHORITY,
        "live": PAPER_LIVE_AUTHORITY,
    }
    result["plan_fingerprint"] = _fingerprint(result)
    return result
