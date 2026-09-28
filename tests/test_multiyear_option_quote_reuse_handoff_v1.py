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
             member_case_ids=["one:C", "two:C"]),
        dict(request_identity="b" * 64, option_symbol=cases[1]["option_symbol"],
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
    with pytest.raises(QuoteReuseHandoffError, match="membership"):
        assemble_quote_reuse_handoff(selection, bad_plan, census, expected_original_cases=2)


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
