from __future__ import annotations

"""Synthetic zero-network tests for complete PIT case/right reuse lineage."""

from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    QuoteReuseHandoffError, assemble_quote_reuse_handoff,
    persist_quote_reuse_handoff,
)


def _signed(value, field):
    value[field] = _fingerprint(value)
    return value


def _fixtures():
    cases = [
        dict(original_case_id="one", case_id="one:C", ticker="TEST",
             option_symbol="TEST220318C00100000", right="call",
             source_selection_status="SELECTED_ACCEPTED_ORIGINAL_PIT_CALL_POINTER"),
        dict(original_case_id="one", case_id="one:P", ticker="TEST",
             option_symbol="TEST220318P00100000", right="put",
             source_selection_status="SELECTED_VERIFIED_PIT_CHAIN"),
        dict(original_case_id="two", case_id="two:C", ticker="TEST",
             option_symbol="TEST220318C00100000", right="call",
             source_selection_status="SELECTED_VERIFIED_ORIGINAL_PIT_CHAIN"),
    ]
    coverage = [
        dict(case_id="one", signal_year="2022", right="call",
             status=cases[0]["source_selection_status"],
             option_symbol=cases[0]["option_symbol"]),
        dict(case_id="one", signal_year="2022", right="put",
             status=cases[1]["source_selection_status"],
             option_symbol=cases[1]["option_symbol"]),
        dict(case_id="two", signal_year="2022", right="call",
             status=cases[2]["source_selection_status"],
             option_symbol=cases[2]["option_symbol"]),
        dict(case_id="two", signal_year="2022", right="put",
             status="EXACT_QUERY_NO_DATA", option_symbol=None),
    ]
    selection = _signed({
        "original_case_denominator": 2, "right_policy": "both",
        "original_right_memberships": 4, "selected_case_right_memberships": 3,
        "coverage": coverage, "cases": cases,
    }, "selection_fingerprint")
    requests = [
        dict(request_identity="a" * 64, option_symbol=cases[0]["option_symbol"],
             from_inclusive="2022-01-01", to_exclusive="2022-03-19",
             member_case_ids=["one:C", "two:C"]),
        dict(request_identity="b" * 64, option_symbol=cases[1]["option_symbol"],
             from_inclusive="2022-01-01", to_exclusive="2022-03-19",
             member_case_ids=["one:P"]),
    ]
    memberships = [
        dict(case_id=item["case_id"], ticker="TEST",
             option_symbol=item["option_symbol"], disposition="SOURCE_DEMAND_READY",
             request_identity=("b" * 64 if item["right"] == "put" else "a" * 64))
        for item in cases
    ]
    plan = _signed({
        "contract": QUOTE_CONTRACT, "requested_case_denominator": 3,
        "unique_physical_quote_queries": 2,
        "memberships": memberships, "requests": requests,
    }, "plan_fingerprint")
    census = _signed({
        "plan_fingerprint": plan["plan_fingerprint"],
        "original_requested_case_denominator": 3,
        "unique_physical_quote_queries": 2,
        "status": "PREVIEW_ONLY_NO_PROVIDER_GETS", "new_provider_attempts": 0,
        "observed_credits": 0, "reused_original_2022": 1,
        "new_cache_complete": 0, "exact_source_gaps": 0, "pending": 1,
        "source_entries": [
            dict(request_identity="a" * 64,
                 status="REUSED_ACCEPTED_2022_FULL_SERIES",
                 source_request_identity="c" * 64,
                 body_sha256="d" * 64, cached_observed_rows=55),
        ],
    }, "report_fingerprint")
    return selection, plan, census


def test_full_case_reuse_map_distinguishes_shared_source_and_missing_quote():
    selection, plan, census = _fixtures()
    out = assemble_quote_reuse_handoff(
        selection, plan, census, expected_original_cases=2,
    )
    assert out["original_right_memberships"] == 4
    assert out["selected_case_right_memberships"] == 3
    assert out["pending_unique_quote_queries"] == 1
    assert out["by_status"] == {
        "NO_PIT_SELECTED_CONTRACT": 1,
        "QUOTE_HISTORY_NOT_ACQUIRED": 1,
        "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY": 2,
    }
    assert out["by_year"]["2022"] == out["by_status"]
    same = [r for r in out["rows"] if r["option_symbol"] == "TEST220318C00100000"]
    assert len(same) == 2 and all(
        r["quote_source_request_identity"] == "c" * 64 for r in same
    )
    assert all(r["observed_quote_rows"] == 55 for r in same)
    assert out["provider_requests"] == 0 and out["portfolio_pnl_authority"] is False


def test_changed_plan_census_selection_and_membership_fail_closed():
    selection, plan, census = _fixtures()
    wrong = dict(census, observed_credits=1)
    with pytest.raises(QuoteReuseHandoffError, match="fingerprint"):
        assemble_quote_reuse_handoff(selection, plan, wrong, expected_original_cases=2)
    wrong = _signed({k: v for k, v in census.items()
                     if k != "report_fingerprint"} | {"observed_credits": 1},
                    "report_fingerprint")
    with pytest.raises(QuoteReuseHandoffError, match="zero-GET"):
        assemble_quote_reuse_handoff(selection, plan, wrong, expected_original_cases=2)
    wrong = dict(selection, selected_case_right_memberships=2)
    with pytest.raises(QuoteReuseHandoffError, match="fingerprint"):
        assemble_quote_reuse_handoff(wrong, plan, census, expected_original_cases=2)
    selection, plan, census = _fixtures()
    bad_plan = _signed({k: v for k, v in plan.items() if k != "plan_fingerprint"} |
                       {"memberships": [{**plan["memberships"][0],
                                         "option_symbol": "CHANGED"}] + plan["memberships"][1:]},
                       "plan_fingerprint")
    matching_census = _signed(
        {k: v for k, v in census.items() if k != "report_fingerprint"} |
        {"plan_fingerprint": bad_plan["plan_fingerprint"]},
        "report_fingerprint",
    )
    with pytest.raises(QuoteReuseHandoffError, match="membership"):
        assemble_quote_reuse_handoff(selection, bad_plan, matching_census, expected_original_cases=2)


def test_persist_immutable_and_no_duplicate_write(tmp_path):
    selection, plan, census = _fixtures()
    handoff = assemble_quote_reuse_handoff(selection, plan, census, expected_original_cases=2)
    settings = SimpleNamespace(
        resolved_path=lambda path: tmp_path / path,
        assert_external_storage_binding=lambda category:
            None if category == "options" else pytest.fail("wrong category"),
    )
    first, action = persist_quote_reuse_handoff(settings, handoff)
    assert action == "WRITTEN_IMMUTABLE_SOURCE_REUSE_HANDOFF"
    second, action = persist_quote_reuse_handoff(settings, handoff)
    assert first == second and action == "REUSED_IDENTICAL_SOURCE_REUSE_HANDOFF"
    first.write_text("tampered", encoding="utf-8")
    with pytest.raises((QuoteReuseHandoffError, ValueError)):
        persist_quote_reuse_handoff(settings, handoff)


def test_clipped_recovery_can_supply_missing_original_without_claiming_full_window():
    selection, plan, census = _fixtures()
    overlay = _signed({
        "contract": "atlas-multiyear-stale-exact-quote-recovery-overlay-v1",
        "status": "CLIPPED_SOURCE_OVERLAY_NO_ORIGINAL_WINDOW_COMPLETENESS_CLAIM",
        "original_plan_fingerprint": plan["plan_fingerprint"],
        "recovery_plan_fingerprint": "e" * 64,
        "recovery_census_fingerprint": "f" * 64,
        "current_floor_et": "2022-02-01",
        "recoverable_original_requests": 1,
        "distinct_recovery_queries": 1,
        "complete_recovery_queries": 1,
        "recovery_query_gaps": 0,
        "pending_recovery_queries": 0,
        "rows": [{
            "original_request_identity": "b" * 64,
            "recovery_request_identity": "e" * 64,
            "option_symbol": "TEST220318P00100000",
            "source_from_inclusive": "2022-02-01",
            "source_to_exclusive": "2022-03-19",
            "status": "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY",
            "quote_body_sha256": "f" * 64,
            "observed_quote_rows": 22,
            "missing_original_prefix_is_not_reconstructed": True,
            "historical_fill_or_pnl_authority": False,
        }],
        "provider_requests": 0,
        "original_window_fully_reconstructed": False,
        "historical_fill_or_pnl_authority": False,
    }, "overlay_fingerprint")
    out = assemble_quote_reuse_handoff(
        selection, plan, census, recovery_overlay=overlay,
        expected_original_cases=2,
    )
    recovered = next(x for x in out["rows"] if x["case_right_id"] == "one:P")
    assert recovered["quote_history_status"] == (
        "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY"
    )
    assert recovered["quote_request_identity"] == "b" * 64
    assert recovered["quote_source_request_identity"] == "e" * 64
    assert recovered["quote_source_from_inclusive"] == "2022-02-01"
    assert recovered["quote_source_to_exclusive"] == "2022-03-19"
    assert recovered["quote_source_is_clipped_recovery"] is True
    assert recovered["original_quote_window_fully_reconstructed"] is False
    assert out["recovered_original_quote_queries"] == 1
    assert out["verified_clipped_recovery_queries"] == 1
    assert out["pending_unique_quote_queries"] == 0
    assert out["provider_requests"] == 0


def test_selected_contract_outside_current_quote_window_stays_explicit_without_request():
    selection, plan, census = _fixtures()
    target = next(x for x in plan["memberships"] if x["case_id"] == "one:P")
    target["disposition"] = "ORIGINAL_DECISION_OUTSIDE_STARTER_FIVE_YEAR_WINDOW"
    target["request_identity"] = None
    plan["requests"] = [
        x for x in plan["requests"] if x["request_identity"] != "b" * 64
    ]
    plan["unique_physical_quote_queries"] = 1
    plan["plan_fingerprint"] = _fingerprint({
        k: v for k, v in plan.items() if k != "plan_fingerprint"
    })
    census["plan_fingerprint"] = plan["plan_fingerprint"]
    census["unique_physical_quote_queries"] = 1
    census["pending"] = 0
    census["report_fingerprint"] = _fingerprint({
        k: v for k, v in census.items() if k != "report_fingerprint"
    })
    out = assemble_quote_reuse_handoff(
        selection, plan, census, expected_original_cases=2,
    )
    row = next(x for x in out["rows"] if x["case_right_id"] == "one:P")
    assert row["option_symbol"] == "TEST220318P00100000"
    assert row["quote_request_identity"] is None
    assert row["quote_history_status"] == (
        "QUOTE_HISTORY_OUTSIDE_CURRENT_PROVIDER_WINDOW"
    )
    assert row["quote_body_sha256"] is None
    assert out["ineligible_selected_case_right_memberships"] == 1
    assert out["pending_unique_quote_queries"] == 0
    assert out["portfolio_pnl_authority"] is False
