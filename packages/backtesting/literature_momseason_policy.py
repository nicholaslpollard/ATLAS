from __future__ import annotations

import calendar as calendar_module
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable

from packages.core.market_calendar import get_market_calendar


LITERATURE_MOMSEASON_SOURCE_CONTRACT = (
    "literature-momseason-source-feasibility-v1-two-external-hypotheses-no-target-outcomes"
)
LITERATURE_MOMSEASON_BASE_MAIN_SHA = "34343fff92de87241c20f57f0c783fa8409fc6a1"
LITERATURE_MOMSEASON_FAMILY = "HESTON_SADKA_CALENDAR_MONTH_RETURN_SEASONALITY"
LITERATURE_MOMSEASON_FORMATION_START = date(2021, 9, 1)
LITERATURE_MOMSEASON_FORMATION_END = date(2026, 8, 1)
LITERATURE_MOMSEASON_PROTECTED_START = date(2026, 5, 12)
LITERATURE_MOMSEASON_PROTECTED_END = date(2026, 8, 11)

# One complete calendar cycle is the minimum defensible independent protected
# evidence for a signal whose mechanism is explicitly calendar-month seasonal.
# This is frozen before any LIT-01 target return is opened.
LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS = 12

LITERATURE_MOMSEASON_TARGET_OUTCOME_READS_ALLOWED = False
LITERATURE_MOMSEASON_PROTECTED_OUTCOME_READS_ALLOWED = False
LITERATURE_MOMSEASON_PROVIDER_WRITES = 0
LITERATURE_MOMSEASON_BROKER_READS = 0
LITERATURE_MOMSEASON_BROKER_WRITES = 0
LITERATURE_MOMSEASON_ORDER_WRITES = 0
LITERATURE_MOMSEASON_PAPER_SUBMITS = 0
LITERATURE_MOMSEASON_LIVE_WRITES = 0
LITERATURE_MOMSEASON_AUTOMATION_WRITES = 0


@dataclass(frozen=True, slots=True)
class MomSeasonHypothesis:
    hypothesis_id: str
    external_signal: str
    lag_years: tuple[int, ...]
    direction: str = "POSITIVE"
    portfolio_period_months: int = 1
    evidence_class: str = "OpenSourceAP: original=1_clear; replication=1_good"


# Both formulas are externally specified in Heston-Sadka/OpenSourceAP before
# ATLAS performance access.  Neither was selected from ATLAS returns.
MOMSEASON_HYPOTHESES: tuple[MomSeasonHypothesis, ...] = (
    MomSeasonHypothesis(
        hypothesis_id="momseason_short_year1",
        external_signal="MomSeasonShort",
        lag_years=(1,),
    ),
    MomSeasonHypothesis(
        hypothesis_id="momseason_years2_5",
        external_signal="MomSeason",
        lag_years=(2, 3, 4, 5),
    ),
)


@dataclass(frozen=True, slots=True)
class FormationMonth:
    month_start: date
    first_session: date
    last_session: date
    scope: str
    protected_target_complete: bool


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def literature_momseason_source_fingerprint() -> str:
    payload = {
        "contract_version": LITERATURE_MOMSEASON_SOURCE_CONTRACT,
        "base_main_sha": LITERATURE_MOMSEASON_BASE_MAIN_SHA,
        "family": LITERATURE_MOMSEASON_FAMILY,
        "formation_start": LITERATURE_MOMSEASON_FORMATION_START.isoformat(),
        "formation_end": LITERATURE_MOMSEASON_FORMATION_END.isoformat(),
        "protected_start": LITERATURE_MOMSEASON_PROTECTED_START.isoformat(),
        "protected_end": LITERATURE_MOMSEASON_PROTECTED_END.isoformat(),
        "min_protected_complete_months": LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS,
        "hypotheses": [asdict(item) for item in MOMSEASON_HYPOTHESES],
        "target_outcome_reads_allowed": LITERATURE_MOMSEASON_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": LITERATURE_MOMSEASON_PROTECTED_OUTCOME_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": LITERATURE_MOMSEASON_PROVIDER_WRITES,
            "broker_reads": LITERATURE_MOMSEASON_BROKER_READS,
            "broker_writes": LITERATURE_MOMSEASON_BROKER_WRITES,
            "order_writes": LITERATURE_MOMSEASON_ORDER_WRITES,
            "paper_submits": LITERATURE_MOMSEASON_PAPER_SUBMITS,
            "live_writes": LITERATURE_MOMSEASON_LIVE_WRITES,
            "automation_writes": LITERATURE_MOMSEASON_AUTOMATION_WRITES,
        },
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def iter_month_starts(start: date, end: date) -> Iterable[date]:
    current = date(start.year, start.month, 1)
    finish = date(end.year, end.month, 1)
    while current <= finish:
        yield current
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def same_month_years_back(month_start: date, years_back: int) -> date:
    return date(month_start.year - int(years_back), month_start.month, 1)


def previous_month(month_start: date) -> date:
    if month_start.month == 1:
        return date(month_start.year - 1, 12, 1)
    return date(month_start.year, month_start.month - 1, 1)


def month_sessions(market_calendar: Any, month_start: date) -> tuple[date, ...]:
    last_day = calendar_module.monthrange(month_start.year, month_start.month)[1]
    sessions = tuple(
        market_calendar.sessions_in_range(
            month_start,
            date(month_start.year, month_start.month, last_day),
        )
    )
    if not sessions:
        raise ValueError(f"no XNYS sessions in calendar month {month_start:%Y-%m}")
    return sessions


def formation_months(market_calendar: Any | None = None) -> tuple[FormationMonth, ...]:
    calendar = market_calendar or get_market_calendar()
    result: list[FormationMonth] = []
    for month_start in iter_month_starts(
        LITERATURE_MOMSEASON_FORMATION_START,
        LITERATURE_MOMSEASON_FORMATION_END,
    ):
        sessions = month_sessions(calendar, month_start)
        first_session = sessions[0]
        last_session = sessions[-1]
        if last_session < LITERATURE_MOMSEASON_PROTECTED_START:
            scope = "DEVELOPMENT"
            complete = False
        elif first_session < LITERATURE_MOMSEASON_PROTECTED_START <= last_session:
            scope = "PURGE_BOUNDARY"
            complete = False
        elif (
            first_session >= LITERATURE_MOMSEASON_PROTECTED_START
            and first_session <= LITERATURE_MOMSEASON_PROTECTED_END
        ):
            complete = last_session <= LITERATURE_MOMSEASON_PROTECTED_END
            scope = "PROTECTED_COMPLETE" if complete else "PROTECTED_PREDICTOR_ONLY"
        else:
            scope = "OUTSIDE_ACCEPTED_WINDOW"
            complete = False
        result.append(
            FormationMonth(
                month_start=month_start,
                first_session=first_session,
                last_session=last_session,
                scope=scope,
                protected_target_complete=complete,
            )
        )
    return tuple(result)


def required_lag_reference_dates(
    market_calendar: Any | None = None,
) -> tuple[date, ...]:
    calendar = market_calendar or get_market_calendar()
    dates: set[date] = set()
    for formation in formation_months(calendar):
        for hypothesis in MOMSEASON_HYPOTHESES:
            for years_back in hypothesis.lag_years:
                lag_month = same_month_years_back(formation.month_start, years_back)
                dates.add(month_sessions(calendar, previous_month(lag_month))[-1])
                dates.add(month_sessions(calendar, lag_month)[-1])
    return tuple(sorted(dates))


def temporal_capacity(market_calendar: Any | None = None) -> dict[str, object]:
    months = formation_months(market_calendar)
    counts = Counter(item.scope for item in months)
    complete = [item for item in months if item.protected_target_complete]
    protected_predictor = [
        item
        for item in months
        if item.scope in {"PROTECTED_COMPLETE", "PROTECTED_PREDICTOR_ONLY"}
    ]
    return {
        "formation_months": len(months),
        "development_complete_months": int(counts["DEVELOPMENT"]),
        "purge_boundary_months": int(counts["PURGE_BOUNDARY"]),
        "protected_predictor_months": len(protected_predictor),
        "protected_complete_target_months": len(complete),
        "minimum_protected_complete_months": LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS,
        "current_protected_temporal_capacity_sufficient": (
            len(complete) >= LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS
        ),
        "protected_complete_month_keys": [
            item.month_start.strftime("%Y-%m") for item in complete
        ],
        "protected_predictor_month_keys": [
            item.month_start.strftime("%Y-%m") for item in protected_predictor
        ],
    }


assert len(MOMSEASON_HYPOTHESES) == 2
assert LITERATURE_MOMSEASON_TARGET_OUTCOME_READS_ALLOWED is False
assert LITERATURE_MOMSEASON_PROTECTED_OUTCOME_READS_ALLOWED is False
assert LITERATURE_MOMSEASON_PROVIDER_WRITES == 0
assert LITERATURE_MOMSEASON_BROKER_READS == 0
assert LITERATURE_MOMSEASON_BROKER_WRITES == 0
assert LITERATURE_MOMSEASON_ORDER_WRITES == 0
assert LITERATURE_MOMSEASON_PAPER_SUBMITS == 0
assert LITERATURE_MOMSEASON_LIVE_WRITES == 0
assert LITERATURE_MOMSEASON_AUTOMATION_WRITES == 0
