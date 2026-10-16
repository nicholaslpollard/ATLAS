from __future__ import annotations

"""Outcome-blind CALL/PUT demand for the independent options-native pilot.

Only exchange calendars and the versioned specification are read. This module
does not import a provider client, open source files or authorize acquisition.
"""

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import exchange_calendars

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.strategies.options_native_pilot_v1_contract import (
    AUTHORITY, DATA_FINGERPRINT, END_DATE, MAX_DTE, MAX_HOLD_SESSIONS,
    PILOT_ID, SPECIFICATION_FINGERPRINT, START_DATE, pilot_data_contract, pilot_manifest,
)

CONTRACT = "atlas-options-native-pilot-discovery-plan-v1"
EASTERN = ZoneInfo("America/New_York")


class OptionsNativePilotPlanError(ValueError):
    pass


def build_options_native_pilot_plan() -> dict[str, Any]:
    start, end = date.fromisoformat(START_DATE), date.fromisoformat(END_DATE)
    calendar = get_market_calendar("XNYS")
    # Include the preceding week so an interval beginning midweek cannot invent
    # a new first-of-week entry on its first date.
    sessions = calendar.sessions_in_range(start - timedelta(days=7), end)
    first_by_week: dict[tuple[int, int], date] = {}
    for day in sessions:
        iso = day.isocalendar()
        first_by_week.setdefault((iso.year, iso.week), day)
    rows = []
    requests = []
    for day in sorted(first_by_week.values()):
        if day < start:
            continue
        at = datetime.combine(day, time(10), EASTERN).astimezone(UTC)
        order_at = at + timedelta(minutes=1)
        opened, closed = calendar.regular_open_close(day)
        if not opened <= at < order_at < closed:
            raise OptionsNativePilotPlanError("pilot clocks escape the frozen stock planning window")
        row: dict[str, Any] = {
            "symbol": "SPY", "date_et": day.isoformat(),
            "feature_cutoff_utc": at.isoformat(), "order_eligible_utc": order_at.isoformat(),
            "stock_session_open_utc": opened.isoformat(), "stock_session_close_utc": closed.isoformat(),
        }
        if day + timedelta(days=MAX_DTE) > end:
            row["status"] = "EXCLUDED_BY_FROZEN_MATURITY_SCOPE_BUFFER"
        else:
            row["status"] = "PLANNED_DECISION_INPUT_SURFACE"
            request = {
                "endpoint": "/v3/option/at_time/quote",
                "params": {
                    "symbol": "SPY", "expiration": "*", "strike": "*", "right": "both",
                    "start_date": day.strftime("%Y%m%d"), "end_date": day.strftime("%Y%m%d"),
                    "time_of_day": "10:00:00.000", "max_dte": MAX_DTE,
                    "strike_range": 2, "format": "json",
                },
                "role": "DECISION_INPUT", "source_qualified": False,
            }
            query_fp = _fingerprint(request)
            request["query_fingerprint"] = query_fp
            row["quote_query_fingerprint"] = query_fp
            requests.append(request)
        rows.append(row)
    if not requests or len(requests) > 500:
        raise OptionsNativePilotPlanError("weekly pilot exceeds its 500-surface design bound")
    counts = Counter(str(request["params"]["start_date"])[:4] for request in requests)
    anchors = []
    for year in range(2018, 2026):
        eligible = [r for r in requests if r["params"]["start_date"].startswith(str(year))]
        if len(eligible) < 3:
            raise OptionsNativePilotPlanError("pilot year has insufficient qualification anchors")
        for label, request in (("FIRST", eligible[0]), ("MIDDLE", eligible[len(eligible) // 2]),
                               ("LAST", eligible[-1])):
            anchors.append({"reason": f"{year}_{label}",
                            "query_fingerprint": request["query_fingerprint"]})
    body = {
        "contract": CONTRACT, "pilot_id": PILOT_ID,
        "status": "PLANNED_ZERO_PROVIDER_READS_NOT_ACQUISITION_AUTHORITY",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "data_contract_fingerprint": DATA_FINGERPRINT,
        "specification": pilot_manifest(), "data_contract": pilot_data_contract(),
        "calendar": {"exchange": "XNYS", "library": "exchange_calendars",
                     "version": exchange_calendars.__version__,
                     "qualifies_option_trading_hours": False},
        "planned_weekly_clocks": len(rows),
        "scope_buffer_exclusions": sum(r["status"].startswith("EXCLUDED") for r in rows),
        "entry_quote_surface_count": len(requests), "by_year": dict(sorted(counts.items())),
        "rows": rows, "entry_quote_surface_requests": requests,
        "request_semantics": {
            "right": "both", "strike_range": "two above/two below provider spot plus ATM",
            "provider_overfetch": "max_dte includes 0-29 DTE; eligibility remains 30-45 DTE",
            "minimum_dte_filter": "local causal contract selection, not provider coverage claim",
            "scope": "SPY weekly surfaces only; independent of stock BUY signals",
            "outside_strike_band_fallback": False,
            "missing_common_call_put_strike": "ABSTAIN_WITH_SOURCE_COVERAGE_REASON",
            "option_hours_and_timestamp_qualification": "still required for SPY calls and puts",
            "maximum_response_bytes_per_quote": 4 * 1024 * 1024,
        },
        "qualification_design": {
            "quote_anchor_count": len(anchors), "anchors": anchors,
            "repeat_query_fingerprint": requests[0]["query_fingerprint"],
            "quote_requests_including_repeat": len(anchors) + 1,
            "total_initial_provider_request_design_cap": 64,
            "cap_includes": "quotes/repeat plus bounded exact CALL/PUT OI and IV/model checks",
            "calls_and_puts_both_required": True, "run_authorized": False,
            "no_retries_beyond_counted_cap": True,
        },
        "later_demand": {
            "selected_pair_oi": "two exact contracts after geometric selection; prior-state/publication proof",
            "selected_pair_iv": "same-expiry both-rights calculation after PIT rate/dividend qualification",
            "entry_execution": "original two exact contracts at/after 10:01; full event/fill qualification",
            "daily_management": f"original exact pair at 10:00 for at most {MAX_HOLD_SESSIONS} initial sessions",
            "exit_execution": "10:01 or later after reached exit request; exact original pair/residuals",
            "unresolved_position": "retains exposure; later source demand requires separate bounded scope",
            "management_cadence_is_adaptive_contract_choice": False,
            "fixed_entry_demand_is_full_lifecycle_coverage": False,
            "provider_specific_exact_requests_materialized": False,
        },
        "reuse": {
            "cache": "content-addressed raw responses with original request/receipt identities",
            "legacy_9455_call_surface_plan_modified": False,
            "reuse_requires": "exact clock/query/body lineage and native CALL/PUT qualification",
            "new_source_acceptance_from_file_presence": False,
        },
        "trial_registration": {
            "stage": "SPECIFICATION", "strategy_variant_budget": 1,
            "code_registration": SPECIFICATION_FINGERPRINT,
            "workstation_trial_ledger_appended": False,
            "requirement": "append matching specification draft to existing StrategyTrialLedger before outcomes",
        },
        "authority": dict(AUTHORITY),
    }
    body["plan_fingerprint"] = _fingerprint(body)
    return body


def verify_options_native_pilot_plan(plan: object) -> dict[str, Any]:
    """Reconstruct the full frozen plan; a self-signed policy edit cannot pass."""
    expected = build_options_native_pilot_plan()
    if not isinstance(plan, dict) or plan != expected:
        raise OptionsNativePilotPlanError("pilot specification, calendar, demand or authority drifted")
    return expected
