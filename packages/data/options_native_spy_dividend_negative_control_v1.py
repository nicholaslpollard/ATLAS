from __future__ import annotations

"""Retrospective negative control: a real SPY dividend absent from the frozen archive.

This source-discrepancy review has zero authority to repair original records,
backfill pricing, accept as-of features, or change a registered option trial.
"""

from datetime import date, datetime
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_archival_action_timeline_v1 import (
    COVERAGE,
    PinnedSource,
    SpyArchivalTimelineError,
    _load_pinned,
    _require,
)
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-options-native-spy-external-dividend-negative-control-v1"

ARCHIVE = PinnedSource(
    "data/research/options_native_spy_archival_action_timeline_v1/6aaf6b09006443d0.json",
    "0010728cd99394834434555042ead745e4d12420050dcaa81396e277baa7546d",
    "6aaf6b09006443d01dceb38b67c4e25ad496db165964411cddafebdc13d2a7a6",
)

# Retrospective comparison evidence, sourced 2026-10-16. State Street's
# Australia-listed CDI historical table gives a June 2018 distribution
# equivalent to USD 1.24557 but is NOT a source of the US SPY ex-date.
# Independent US SPY dividend-history sites give the US ex-date and USD value.
# None of these URLs is a 2018 PIT publication snapshot.
WITNESS = {
    "symbol": "SPY",
    "event_type": "cash_dividends",
    "ex_date": "2018-06-15",
    "cash_per_share_usd_retrospective": "1.245568",
    "state_street_related_distribution_url": (
        "https://www.ssga.com/au/en_gb/institutional/etfs/state-street-spdr-sp-500-etf-spy"
    ),
    "us_ex_date_source_urls": [
        "https://dividendhistory.org/payout/SPY/",
        "https://www.slickcharts.com/symbol/SPY/dividend",
    ],
    "source_checked_on": "2026-10-16",
    "historical_pit_publication_proved": False,
    "historical_action_revisions_proved": False,
    "economic_input_authorized": False,
}


def _case_end_dates(case: dict[str, Any]) -> set[date]:
    keys = case.get("prior_close_keys")
    _require(isinstance(keys, list) and len(keys) == 21 and len(set(keys)) == 21,
             "frozen case has unexpected historical closing-clock population")
    # Prior close #0 is a log-return baseline, NOT a return-ending observation.
    try:
        return {datetime.fromisoformat(key).date() for key in keys[1:]}
    except (ValueError, TypeError) as exc:
        raise SpyArchivalTimelineError("invalid frozen prior closing clock") from exc


def reconcile_dividend_negative_control(
    coverage: dict[str, Any], archive: dict[str, Any],
) -> dict[str, Any]:
    """Witness one known archive omission; do not infer other coverage."""
    _require(coverage.get("report_fingerprint") == COVERAGE.fingerprint
             and coverage.get("target_weekly_cases") == 411
             and coverage.get("raw_complete_weekly_cases") == 407
             and coverage.get("observed_exact_clocks") == 2406
             and coverage.get("pilot_input_acceptance") is False,
             "frozen price coverage report authority changed")
    _require(archive.get("report_fingerprint") == ARCHIVE.fingerprint
             and archive.get("contract") == "atlas-options-native-spy-archival-action-timeline-v1"
             and archive.get("status") == "ARCHIVAL_SPY_ACTION_INDEX_ONLY_PIT_AND_COVERAGE_UNQUALIFIED"
             and archive.get("specification_fingerprint") == SPECIFICATION_FINGERPRINT
             and archive.get("native_ledger_records_reconciled") == 378362
             and archive.get("physical_input_complete_weekly_decisions") == 407
             and archive.get("historical_asof_publication_revisions_qualified") is False
             and archive.get("complete_historical_action_coverage_qualified") is False
             and archive.get("forecast_total_variance") is None
             and archive.get("economic_log_returns") is None
             and archive.get("authority") == dict(AUTHORITY),
             "pinned archived action source report content or authority changed")
    candidates = archive.get("action_candidates")
    cases = coverage.get("cases")
    indexed = archive.get("weekly_case_action_index")
    _require(isinstance(candidates, list) and len(candidates) == 32
             and archive.get("action_candidates_by_type") == {"cash_dividends": 32}
             and archive.get("archival_candidates_with_unknown_effective_date") == 0,
             "archived cash-dividend candidate count/type changed")
    _require(isinstance(cases, list) and isinstance(indexed, list)
             and len(cases) == len(indexed) == 411, "frozen weekly cases changed")
    archived_ex_dates = []
    for action in candidates:
        payload = action.get("payload")
        _require(action.get("action_type") == "cash_dividends"
                 and isinstance(payload, dict) and payload.get("symbol") == "SPY"
                 and isinstance(payload.get("ex_date"), str)
                 and action.get("point_in_time_qualified") is False,
                 "archived cash-dividend action source identity drifted")
        archived_ex_dates.append(payload["ex_date"])
    _require(len(set(archived_ex_dates)) == 32, "archived ex-date identities duplicated")
    witness_date = date.fromisoformat(WITNESS["ex_date"])
    _require(WITNESS["ex_date"] not in archived_ex_dates,
             "known external negative-control event was added to the frozen archive")

    implicated: list[dict[str, Any]] = []
    archive_empty = 0
    for original, record in zip(cases, indexed, strict=True):
        _require(original.get("decision_date") == record.get("decision_date")
                 and original.get("quote_query_fingerprint") == record.get("quote_query_fingerprint")
                 and original.get("missing_clocks") == record.get("missing_raw_clocks")
                 and record.get("historical_economic_returns_accepted") is False
                 and record.get("archival_zero_action_coverage_proved") is False
                 and record.get("forecast_total_variance") is None,
                 "frozen weekly archive index no longer agrees with source cases")
        raw_indexes = record.get("archived_dated_action_candidate_indices")
        _require(isinstance(raw_indexes, list)
                 and all(type(i) is int and 0 <= i < 32 for i in raw_indexes),
                 "invalid archive candidate index")
        if not raw_indexes:
            archive_empty += 1
        if witness_date in _case_end_dates(original):
            _require(not raw_indexes,
                     "external negative control intersected an archived event; inspect before classification")
            implicated.append({
                "decision_date": original["decision_date"],
                "quote_query_fingerprint": original["quote_query_fingerprint"],
                "physical_prior_and_spot_present": record["physical_prior_and_spot_present"],
                "archived_dated_action_candidate_count": 0,
                "independent_retrospective_dividend_witness": True,
                "historical_price_adjustment": None,
                "historical_forecast_variance": None,
                "historical_economic_input_accepted": False,
            })
    _require(archive_empty == 267, "frozen archive-empty decision population changed")
    _require([x["decision_date"] for x in implicated] == [
        "2018-06-18", "2018-06-25", "2018-07-02", "2018-07-09", "2018-07-16",
    ], "2018 omitted dividend overlaps unexpected frozen decisions")
    _require(all(x["physical_prior_and_spot_present"] for x in implicated),
             "negative-control affected a price-incomplete window")
    return {
        "contract": CONTRACT,
        "status": "EXTERNAL_NEGATIVE_CONTROL_CONFIRMS_ACTION_ARCHIVE_INCOMPLETE",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "frozen_coverage_report_raw_sha256": COVERAGE.sha256,
        "frozen_coverage_report_fingerprint": COVERAGE.fingerprint,
        "frozen_archival_timeline_raw_sha256": ARCHIVE.sha256,
        "frozen_archival_timeline_fingerprint": ARCHIVE.fingerprint,
        "retrospective_external_witness": WITNESS,
        "archived_cash_dividends": len(candidates),
        "archive_empty_weekly_windows": archive_empty,
        "definitively_affected_archivally_empty_weekly_windows": implicated,
        "affected_weekly_case_count": len(implicated),
        "frozen_weekly_cases": len(cases),
        "known_missing_2018_06_archive_record": True,
        "frozen_archival_action_source_repaired": False,
        "historical_source_coverage_qualified": False,
        "historical_pit_publication_qualified": False,
        "retrospective_cash_amount_is_historical_feature": False,
        "blank_window_no_action_defaults_authorized": False,
        "economic_log_returns": None,
        "forecast_total_variance": None,
        "historical_option_prices": None,
        "pilot_input_acceptance": False,
        "historical_performance_evidence": False,
        "source_reads": {"pinned_json_reports": 2, "native_action_ledgers": 0,
                         "source_pages": 0, "stock_minutes": 0, "options": 0,
                         "provider_requests": 0, "outcomes": 0},
        "authority": dict(AUTHORITY),
    }


def review_spy_dividend_negative_control(settings: AtlasSettings) -> dict[str, Any]:
    coverage = _load_pinned(settings, COVERAGE)
    archived = _load_pinned(settings, ARCHIVE)
    report = reconcile_dividend_negative_control(coverage, archived)
    report["report_fingerprint"] = _fingerprint(report)
    return report
