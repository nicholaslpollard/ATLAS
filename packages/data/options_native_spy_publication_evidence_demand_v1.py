from __future__ import annotations

"""SPY 2018-2025 dividend publication evidence *demand*, not source acceptance.

Exactly three already-hashed JSON reports. No raw source, network, option,
outcome, 2026 holdout, or portfolio reads. Contemporary-looking web leads are
NOT original captured publication receipts or qualified 2018-2025 PIT data.
"""

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_archival_action_timeline_v1 import (
    COVERAGE, PinnedSource, _load_pinned,
)
from packages.data.options_native_spy_issuer_dividend_reconciliation_v1 import CONTRACT as ISSUER_CONTRACT
from packages.data.options_native_spy_issuer_dividend_reconciliation_v1 import MIN_EX_DATE, MAX_EX_DATE
from packages.data.options_native_spy_issuer_distributions_receipt_v1 import PREVIOUS_GRID
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-33-event-publication-evidence-demand-v1"
ISSUER = PinnedSource(
    "data/research/options_native_spy_issuer_dividend_reconciliation_v1/eca21b2ebbd6fbf3.json",
    "2cad294694292fec31a8a9f6c6610fde23fa8b6db10bd36257fbe3ec9e856900",
    "eca21b2ebbd6fbf378e905e7a8ef8ec278b6320dc2ba0e9976e1a53491b1ee35",
)
# Web leads surfaced by public research on 2026-10-16, deliberately kept
# separate from source receipts and historical availability qualification.
# Article timestamp displayed today may have been revised; page snapshot,
# original creation, revisions, licensing and independent corroboration remain
# unresolved. Do not convert these into source timestamps used by a strategy.
PUBLICATION_LEADS = (
    {
        "ex_date": "2018-06-15", "cash_usd": "1.245568",
        "page": "https://www.marketscreener.com/quote/stock/SPDR-S-P-500-ETF-TRUST-6501057/news/SPDR-S-P-500-ETF-Trust-Announce-US-and-AUD-Distribution-Payable-on-July-31-2018-and-August-10-201-34677797/",
        "displayed_publication_local": "2018-06-14T19:34:00-04:00",
        "publisher": "S&P Capital IQ via MarketScreener",
    },
    {
        "ex_date": "2025-06-20", "cash_usd": "1.761117",
        "page": "https://www.marketscreener.com/quote/stock/SPDR-S-P-500-ETF-TRUST-6501057/news/SPDR-S-P-500-ETF-CDIs-Declares-distribution-50293299/",
        "displayed_publication_local": "2025-06-20T06:05:00-04:00",
        "publisher": "S&P Capital IQ via MarketScreener",
    },
    {
        "ex_date": "2025-12-19", "cash_usd": "1.993368",
        "page": "https://www.marketscreener.com/news/spdr-s-p-500-etf-announces-a-distribution-payable-on-31-january-2026-for-us-and-13-february-2026-fo-ce7e59dbde81fe20",
        "displayed_publication_local": "2025-12-18T17:35:00-05:00",
        "publisher": "S&P Capital IQ via MarketScreener",
    },
)


class SpyPublicationDemandError(ValueError):
    pass


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise SpyPublicationDemandError(message)


def _utc(value: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise SpyPublicationDemandError("malformed decision/source timestamp") from exc
    _require(stamp.tzinfo is not None and stamp.utcoffset() is not None,
             "source publication and decision times must be aware")
    return stamp.astimezone(UTC)


def crosscheck_and_build_event_demand(
    issuer: dict[str, Any], coverage: dict[str, Any], grid: dict[str, Any],
) -> dict[str, Any]:
    _require(issuer.get("contract") == ISSUER_CONTRACT
             and issuer.get("status") == "FULL_33_SPY_ISSUER_CASH_EVENTS_RECONCILED_RETROSPECTIVE_NO_PIT"
             and issuer.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and issuer.get("issuer_event_count") == 33
             and issuer.get("archived_cash_events_matched_by_ex_date") == 32
             and issuer.get("missing_from_original_action_archive") == ["2018-06-15"]
             and issuer.get("issuer_publication_clock_in_2018_2025_proved") is False
             and issuer.get("issuer_asof_amendment_or_revision_history_proved") is False
             and issuer.get("other_corporate_action_coverage_qualified") is False
             and issuer.get("historical_backtest_authorized") is False
             and issuer.get("pilot_input_acceptance") is False
             and issuer.get("authority") == dict(AUTHORITY),
             "issuer source reconciliation is not the pinned retrospective-only population")
    _require(coverage.get("contract") == "atlas-options-native-spy-development-minute-clock-coverage-v1"
             and coverage.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and coverage.get("target_weekly_cases") == 411
             and coverage.get("raw_complete_weekly_cases") == 407
             and coverage.get("raw_incomplete_weekly_cases") == 4
             and coverage.get("observed_exact_clocks") == 2406
             and coverage.get("pilot_input_acceptance") is False
             and coverage.get("authority") == dict(AUTHORITY),
             "SPY physical decision population changed")
    _require(grid.get("contract") == "atlas-options-native-spy-retrospective-dividend-variance-grid-v1"
             and grid.get("status") == "FULL_PERIOD_RETROSPECTIVE_SENSITIVITY_ONLY_NO_PIT_FEATURES"
             and grid.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and grid.get("fixed_weekly_decision_count") == 411
             and grid.get("physically_price_complete_decisions") == 407
             and grid.get("retrospective_dividend_touched_decisions") == 149
             and grid.get("pilot_input_acceptance") is False
             and grid.get("authority") == dict(AUTHORITY),
             "retrospective sensitivity grid changed")
    original_events = issuer.get("issuer_period_events")
    cases = coverage.get("cases")
    windows = grid.get("weekly_retrospective_sensitivity")
    _require(isinstance(original_events, list) and len(original_events) == 33
             and isinstance(cases, list) and len(cases) == 411
             and isinstance(windows, list) and len(windows) == 411,
             "issuer/weekly source population changed")
    events = {}
    for item in original_events:
        day = item.get("ex_date")
        _require(isinstance(day, str) and MIN_EX_DATE <= day <= MAX_EX_DATE
                 and day not in events and isinstance(item.get("source_row"), int)
                 and isinstance(item.get("cash_per_share_usd"), str),
                 "issuer event source identity/date malformed or duplicated")
        cash = Decimal(item["cash_per_share_usd"])
        _require(cash.is_finite() and cash > 0,
                 "invalid issuer distribution amount")
        events[day] = item
    _require(len(events) == 33 and set(events) == {
                 d["ex_date"] for d in original_events
             }, "issuer source row map changed")

    uses: dict[str, list[dict[str, Any]]] = {ex: [] for ex in sorted(events)}
    result_counts = Counter()
    decisions: list[dict[str, Any]] = []
    for case, window in zip(cases, windows, strict=True):
        day = case.get("decision_date")
        keys = case.get("prior_close_keys")
        missing = case.get("missing_clocks")
        _require(isinstance(day, str) and day == window.get("decision_date")
                 and isinstance(keys, list) and len(keys) == 21
                 and len(set(keys)) == 21 and isinstance(missing, list)
                 and case.get("historical_input_accepted") is False
                 and case.get("forecast_total_variance") is None,
                 "weekly price and retrospective calculation lineage disagree")
        decision = _utc(case["decision_utc"])
        ends = [_utc(x).date().isoformat() for x in keys[1:]]
        _require(len(ends) == len(set(ends)) == 20
                 and all(_utc(x) < decision for x in keys),
                 "prior interval clocks do not precede decision")
        touched = sorted(set(ends).intersection(events))
        raw_hits = window.get("retrospective_dividends_in_return_end_dates", [])
        if missing:
            _require(window.get("status") == "RAW_PRICE_GAP_NO_VARIANCE_DIAGNOSTIC"
                     and raw_hits == [] and len(missing) == 1,
                     "price-gap week was incorrectly assigned a volatility diagnostic")
        else:
            _require(window.get("status") == "RETROSPECTIVE_VARIANCE_SENSITIVITY_ONLY"
                     and isinstance(raw_hits, list)
                     and sorted(x["ex_date"] for x in raw_hits) == touched,
                     "issuer ex-date overlap does not match frozen earlier volatility grid")
            # The two formerly rounded cash amounts cannot change ex-date membership.
            for hit in raw_hits:
                _require(abs(Decimal(hit["retrospective_cash_usd"]) -
                             Decimal(events[hit["ex_date"]]["cash_per_share_usd"]))
                         <= Decimal("0.000005"),
                         "issuer cash differs materially from prior retrospective case")
            result_counts["price_complete"] += 1
            result_counts["price_complete_dividend_touched"] += bool(touched)
        for ex in touched:
            uses[ex].append({
                "decision_date": day, "decision_utc": decision.isoformat(),
                "physical_spy_prices_complete": not missing,
                "issuer_original_row": events[ex]["source_row"],
            })
        decisions.append({
            "decision_date": day, "dividend_ex_dates_in_twenty_completed_prior_returns": touched,
            "physical_prices_complete": not missing,
            "historical_dividend_publication_qualified": False,
            "historical_adjustment_feature_accepted": False,
        })
    _require(result_counts["price_complete"] == 407
             and result_counts["price_complete_dividend_touched"] == 149
             and len(decisions) == 411,
             "weekly issuer overlap population unexpectedly changed")
    leads = {}
    for entry in PUBLICATION_LEADS:
        ex = entry["ex_date"]
        _require(ex not in leads and ex in events and
                 Decimal(entry["cash_usd"]) == Decimal(events[ex]["cash_per_share_usd"])
                 and entry["page"].startswith("https://www.marketscreener.com/")
                 and entry["publisher"] == "S&P Capital IQ via MarketScreener",
                 "unmatched external publication research lead")
        stamp = _utc(entry["displayed_publication_local"])
        _require(stamp.date().isoformat() <= ex, "source lead postdates dividend ex-date")
        leads[ex] = {**entry, "displayed_publication_utc": stamp.isoformat(),
                     "original_2018_2025_page_bytes_retained": False,
                     "publisher_revision_history_verified": False,
                     "historical_source_availability_accepted": False}
    event_demands = []
    for ex, issuer_row in sorted(events.items()):
        dependent = uses[ex]
        first = dependent[0] if dependent else None
        if first:
            _require(all(datetime.fromisoformat(x["decision_utc"]) >=
                         datetime.fromisoformat(first["decision_utc"]) for x in dependent),
                     "date-ordered weekly source demand changed")
        lead = leads.get(ex)
        lead_before_first = (lead is not None and first is not None and
                             _utc(lead["displayed_publication_local"]) <
                             datetime.fromisoformat(first["decision_utc"]))
        event_demands.append({
            "ex_date": ex,
            "issuer_original_source_row": issuer_row["source_row"],
            "issuer_cash_per_share": issuer_row["cash_per_share_usd"],
            "frozen_weekly_lookbacks_using_event": len(dependent),
            "physically_price_complete_weekly_lookbacks": sum(x["physical_spy_prices_complete"] for x in dependent),
            "first_dependent_decision_utc": first["decision_utc"] if first else None,
            "last_dependent_decision_utc": dependent[-1]["decision_utc"] if dependent else None,
            "dependent_weekly_dates": [x["decision_date"] for x in dependent],
            "external_historical_announcement_lead": lead,
            "lead_displayed_earlier_than_first_relevant_decision": lead_before_first,
            "historical_original_page_hashed_and_retained": False,
            "issuer_distribution_asof_publication_qualified": False,
            "economic_return_feature_accepted": False,
        })
    return {
        "events": event_demands, "decision_exposures": decisions,
        "event_count": 33,
        "events_with_research_publication_lead": len(leads),
        "events_with_original_pit_source_receipt": 0,
        "price_complete_cases": result_counts["price_complete"],
        "price_complete_cases_exposed_to_dividends": result_counts["price_complete_dividend_touched"],
        "price_incomplete_cases": [d["decision_date"] for d in decisions if not d["physical_prices_complete"]],
        "events_with_no_registered_lookback_usage": [
            d["ex_date"] for d in event_demands if not d["frozen_weekly_lookbacks_using_event"]
        ],
    }


def build_spy_publication_evidence_demand(settings: AtlasSettings) -> dict[str, Any]:
    issuer = _load_pinned(settings, ISSUER)
    coverage = _load_pinned(settings, COVERAGE)
    grid = _load_pinned(settings, PREVIOUS_GRID)
    audit = crosscheck_and_build_event_demand(issuer, coverage, grid)
    report: dict[str, Any] = {
        "contract": CONTRACT,
        "status": "HISTORICAL_SPY_DIVIDEND_PUBLICATION_PROOF_DEMAND_ONLY",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "pinned_input_reports": {
            "issuer_reconciliation": {"sha256": ISSUER.sha256, "fingerprint": ISSUER.fingerprint},
            "411_week_price_coverage": {"sha256": COVERAGE.sha256, "fingerprint": COVERAGE.fingerprint},
            "407_week_variance_grid": {"sha256": PREVIOUS_GRID.sha256, "fingerprint": PREVIOUS_GRID.fingerprint},
        },
        **audit,
        "historical_publication_revisions_complete": False,
        "complete_action_source_absence_proven": False,
        "all_intervals_split_or_nosplit_qualified": False,
        "no_action_defaults_allowed": False,
        "accepted_economic_log_returns": None,
        "accepted_variance_forecast": None,
        "historical_option_prices_or_fills": None,
        "strategy_backtest_authorized": False,
        "pilot_input_acceptance": False,
        "source_reads": {
            "small_pinned_json_reports": 3, "issuer_gets": 0, "provider_gets": 0,
            "stock_bar_scans": 0, "option_scans": 0,
            "original_action_pages_or_ledgers": 0, "outcomes": 0,
        },
        "authority": dict(AUTHORITY),
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
