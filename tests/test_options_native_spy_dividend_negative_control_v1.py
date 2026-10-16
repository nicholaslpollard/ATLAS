from __future__ import annotations

from datetime import date, timedelta

import pytest

from packages.data import options_native_spy_dividend_negative_control_v1 as mod
from packages.data.options_native_spy_archival_action_timeline_v1 import SpyArchivalTimelineError
from packages.strategies.options_native_pilot_v1_contract import AUTHORITY, SPECIFICATION_FINGERPRINT


AFFECTED = ["2018-06-18", "2018-06-25", "2018-07-02", "2018-07-09", "2018-07-16"]


def _keys(with_dividend: bool) -> list[str]:
    # Fixed fake clock windows, to test only date matching, not market sessions.
    first = date(2018, 5, 26) if with_dividend else date(2018, 5, 1)
    return [(first + timedelta(days=i)).isoformat() + "T19:59:00+00:00"
            for i in range(21)]


def fixture():
    cases, indexed = [], []
    witness_cases = [("2018-" + x[-5:], True, False) for x in AFFECTED]
    others = [(str(date(2020, 1, 6) + timedelta(days=i * 7)), False, i < 144)
              for i in range(406)]
    for number, (day, with_dividend, indexed_action) in enumerate(
        others[:144] + witness_cases + others[144:]
    ):
        query = f"{number:064x}"
        case = {"decision_date": day, "quote_query_fingerprint": query,
                "prior_close_keys": _keys(with_dividend), "missing_clocks": []}
        cases.append(case)
        indexed.append({
            "decision_date": day, "quote_query_fingerprint": query,
            "missing_raw_clocks": [], "physical_prior_and_spot_present": True,
            "archived_dated_action_candidate_indices": [0] if indexed_action else [],
            "historical_economic_returns_accepted": False,
            "archival_zero_action_coverage_proved": False,
            "forecast_total_variance": None,
        })
    dividend_dates = [(date(2019, 1, 1) + timedelta(days=30 * i)).isoformat()
                      for i in range(32)]
    candidates = [
        {"action_type": "cash_dividends",
         "payload": {"symbol": "SPY", "ex_date": day},
         "point_in_time_qualified": False}
        for day in dividend_dates
    ]
    coverage = {
        "report_fingerprint": mod.COVERAGE.fingerprint,
        "target_weekly_cases": 411,
        "raw_complete_weekly_cases": 407,
        "observed_exact_clocks": 2406,
        "pilot_input_acceptance": False,
        "cases": cases,
    }
    archive = {
        "report_fingerprint": mod.ARCHIVE.fingerprint,
        "contract": "atlas-options-native-spy-archival-action-timeline-v1",
        "status": "ARCHIVAL_SPY_ACTION_INDEX_ONLY_PIT_AND_COVERAGE_UNQUALIFIED",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "native_ledger_records_reconciled": 378362,
        "physical_input_complete_weekly_decisions": 407,
        "historical_asof_publication_revisions_qualified": False,
        "complete_historical_action_coverage_qualified": False,
        "forecast_total_variance": None,
        "economic_log_returns": None,
        "authority": dict(AUTHORITY),
        "action_candidates": candidates,
        "action_candidates_by_type": {"cash_dividends": 32},
        "archival_candidates_with_unknown_effective_date": 0,
        "weekly_case_action_index": indexed,
    }
    return coverage, archive


def test_external_negative_control_finds_five_overlap_windows_without_repairs():
    coverage, archive = fixture()
    output = mod.reconcile_dividend_negative_control(coverage, archive)
    assert output["known_missing_2018_06_archive_record"] is True
    assert output["frozen_weekly_cases"] == 411
    assert output["archive_empty_weekly_windows"] == 267
    assert output["affected_weekly_case_count"] == 5
    assert [x["decision_date"] for x in output["definitively_affected_archivally_empty_weekly_windows"]] == AFFECTED
    assert all(x["physical_prior_and_spot_present"] for x in output["definitively_affected_archivally_empty_weekly_windows"])
    assert output["retrospective_cash_amount_is_historical_feature"] is False
    assert output["historical_source_coverage_qualified"] is False
    assert output["historical_pit_publication_qualified"] is False
    assert output["frozen_archival_action_source_repaired"] is False
    assert output["economic_log_returns"] is None
    assert output["forecast_total_variance"] is None
    assert output["authority"] == dict(AUTHORITY)
    assert output["source_reads"]["provider_requests"] == 0


@pytest.mark.parametrize("change", ["added_event", "new_authority", "changed_case",
                                    "changed_overlap", "lost_case", "changed_index"])
def test_changed_pinned_archive_or_case_blocks_rather_than_making_new_facts(change):
    coverage, archive = fixture()
    if change == "added_event":
        archive["action_candidates"][1]["payload"]["ex_date"] = "2018-06-15"
    elif change == "new_authority":
        archive["authority"]["historical_replay_authority"] = True
    elif change == "changed_case":
        coverage["cases"][0]["quote_query_fingerprint"] = "other"
    elif change == "changed_overlap":
        # False date coverage: one previously affected 21-close span drops dividend.
        coverage["cases"][144]["prior_close_keys"] = _keys(False)
    elif change == "lost_case":
        archive["weekly_case_action_index"].pop()
    elif change == "changed_index":
        archive["weekly_case_action_index"][145]["archived_dated_action_candidate_indices"] = [0]
    with pytest.raises(SpyArchivalTimelineError):
        mod.reconcile_dividend_negative_control(coverage, archive)


def test_underlying_2019_single_missing_clock_remains_separate():
    coverage, archive = fixture()
    coverage["cases"][0]["missing_clocks"] = ["2019-08-12T19:59:00+00:00"]
    archive["weekly_case_action_index"][0]["missing_raw_clocks"] = ["2019-08-12T19:59:00+00:00"]
    # This synthetic fact does not make a 2018 dividend adjustment or accepted input.
    output = mod.reconcile_dividend_negative_control(coverage, archive)
    assert output["affected_weekly_case_count"] == 5
    assert output["pilot_input_acceptance"] is False
