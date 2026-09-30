from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_additive_quote_plan_v1 import (
    AdditiveQuotePlanError, build_additive_quote_plan, persist_additive_quote_plan,
)
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_option_quote_bridge_v1 import CONTRACT as SELECTION_CONTRACT


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def selected(
    case_id: str, symbol: str, right: str, status: str, *,
    expiration: str = "2022-03-18",
    decision: str = "2022-03-02T14:35:00+00:00",
):
    return {
        "case_id": case_id,
        "original_case_id": case_id.rsplit(":", 1)[0],
        "ticker": "TEST",
        "option_symbol": symbol,
        "right": right,
        "expiration": expiration,
        "decision_at_utc": decision,
        "selected_at_utc": decision,
        "accepted_stock_source_sha256": "a" * 64,
        "frozen_native_raw_open": "100",
        "frozen_structural_strike": "100",
        "source_request_identity": "chain-" + case_id,
        "source_body_sha256": "b" * 64,
        "prior_24h_news_count": 1,
        "prior_7d_news_count": 2,
        "source_selection_status": status,
        "not_an_option_fill_or_validated_deliverable": True,
    }


def selection(cases, *, years=None):
    by = {x["case_id"]: x for x in cases}
    years = years or {"one": "2022", "two": "2022"}
    coverage = []
    for original in ("one", "two"):
        for right, suffix in (("call", "C"), ("put", "P")):
            cid = f"{original}:{suffix}"
            chosen = by.get(cid)
            coverage.append({
                "case_id": original,
                "signal_year": years[original],
                "right": right,
                "status": (
                    chosen["source_selection_status"]
                    if chosen else "MISSING_CHAIN_SOURCE"
                ),
                "option_symbol": chosen["option_symbol"] if chosen else None,
                "source_request_identity": (
                    chosen["source_request_identity"] if chosen else None
                ),
            })
    return signed({
        "contract": SELECTION_CONTRACT,
        "status": "OFFLINE_PIT_CONTRACT_IDENTITIES_ONLY",
        "original_case_denominator": 2,
        "right_policy": "both",
        "original_right_memberships": 4,
        "signed_native_source": "n" * 64,
        "signed_original_crosswalk": "x" * 64,
        "signed_physical_source_demand": "d" * 64,
        "signed_original_global_overlap": "o" * 64,
        "source_only_selection_policy": "NEAREST_RAW_STOCK_OPEN_ATM_TIE_OTM",
        "selected_case_right_memberships": len(cases),
        "by_status": {},
        "cases": cases,
        "coverage": coverage,
        "provider_requests": 0,
        "historical_0935_option_bid_ask_verified": False,
        "verified_standard_deliverable_or_option_pnl": False,
        "2026_protected_outcomes_read": 0,
        "strategy_authority": False,
    }, "selection_fingerprint")


def req_id(symbol, start="2022-01-01", end="2022-03-19"):
    return _fingerprint({
        "contract": QUOTE_CONTRACT,
        "query": {
            "option_symbol": symbol,
            "from_inclusive": start,
            "to_exclusive": end,
        },
    })


def base_plan(base_case):
    rid = req_id(base_case["option_symbol"])
    return signed({
        "contract": QUOTE_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": "2026-09-27T16:00:00+00:00",
        "rolling_five_year_floor": "2021-09-27",
        "last_completed_session": "2026-09-25",
        "requested_case_denominator": 1,
        "unique_physical_quote_queries": 1,
        "memberships": [{
            "case_id": base_case["case_id"],
            "decision_at_utc": base_case["decision_at_utc"],
            "selected_at_utc": base_case["selected_at_utc"],
            "original_accepted_stock_source_sha256":
                base_case["accepted_stock_source_sha256"],
            "ticker": "TEST",
            "option_symbol": base_case["option_symbol"],
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": rid,
        }],
        "requests": [{
            "option_symbol": base_case["option_symbol"],
            "from_inclusive": "2022-01-01",
            "to_exclusive": "2022-03-19",
            "request_identity": rid,
            "member_case_ids": [base_case["case_id"]],
            "source_only_not_validated_trade": True,
        }],
        "provider_requests": 0,
        "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
    }, "plan_fingerprint")


def test_additive_plan_preserves_prior_query_and_only_adds_new_selected_slot():
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    new = selected(
        "two:P", "TEST220318P00100000", "put",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    before = selection([old])
    after = selection([old, new])
    plan = base_plan(old)
    out = build_additive_quote_plan(
        before, plan, after,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    assert out["base_quote_plan_fingerprint"] == plan["plan_fingerprint"]
    assert out["preserved_selected_case_rights"] == 1
    assert out["newly_selected_case_rights"] == 1
    assert out["base_exact_windows_preserved"] is True
    assert out["requested_case_denominator"] == 2
    old_member = next(x for x in out["memberships"] if x["case_id"] == "one:C")
    assert old_member == plan["memberships"][0]
    old_request = next(
        x for x in out["requests"]
        if x["request_identity"] == plan["requests"][0]["request_identity"]
    )
    assert old_request["from_inclusive"] == "2022-01-01"
    assert old_request["to_exclusive"] == "2022-03-19"
    new_request = next(
        x for x in out["requests"]
        if x["option_symbol"] == new["option_symbol"]
    )
    assert new_request["from_inclusive"] == "2022-01-01"
    assert new_request["member_case_ids"] == ["two:P"]
    assert out["provider_requests"] == 0
    assert out["historical_fill_or_pnl_authority"] is False


def test_same_physical_exact_query_merges_membership_without_duplicate_get():
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    new = selected(
        "two:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    out = build_additive_quote_plan(
        selection([old]), base_plan(old), selection([old, new]),
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    assert out["unique_physical_quote_queries"] == 1
    assert out["added_physical_quote_queries"] == 0
    assert out["requests"][0]["member_case_ids"] == ["one:C", "two:C"]


def test_prior_selected_contract_cannot_change_after_chain_acquisition():
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    changed = selected(
        "one:C", "TEST220318C00105000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    with pytest.raises(AdditiveQuotePlanError, match="previously selected"):
        build_additive_quote_plan(
            selection([old]), base_plan(old), selection([changed]),
            asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
            last_completed_session=date(2026, 9, 29),
            expected_original_cases=2,
        )


def test_no_new_selected_contract_returns_identical_base_plan():
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    before = selection([old])
    after = selection([old])
    # An unselected coverage status may improve without changing quote demand.
    after["coverage"][-1]["status"] = "VERIFIED_CHAIN_NO_MATCHING_RIGHT"
    after["selection_fingerprint"] = _fingerprint({
        k: v for k, v in after.items() if k != "selection_fingerprint"
    })
    plan = base_plan(old)
    out = build_additive_quote_plan(
        before, plan, after,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    assert out == plan


def test_persist_additive_plan_is_immutable_and_d_bound(tmp_path):
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    new = selected(
        "two:P", "TEST220318P00100000", "put",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    out = build_additive_quote_plan(
        selection([old]), base_plan(old), selection([old, new]),
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    settings = SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda c:
            None if c == "options" else pytest.fail("wrong storage category"),
    )
    path, action = persist_additive_quote_plan(settings, out)
    assert action == "WRITTEN_IMMUTABLE_ADDITIVE_QUOTE_PLAN"
    assert persist_additive_quote_plan(settings, out)[0] == path
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(AdditiveQuotePlanError):
        persist_additive_quote_plan(settings, out)


def test_newly_selected_2021_contract_outside_current_floor_is_retained_without_paid_request():
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    rolled = selected(
        "two:P", "TEST211015P00100000", "put",
        "SELECTED_VERIFIED_PIT_CHAIN",
        expiration="2021-10-15",
        decision="2021-09-28T13:35:00+00:00",
    )
    before = selection([old], years={"one": "2022", "two": "2021"})
    after = selection([old, rolled], years={"one": "2022", "two": "2021"})
    out = build_additive_quote_plan(
        before, base_plan(old), after,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    member = next(x for x in out["memberships"] if x["case_id"] == "two:P")
    assert member["disposition"] == (
        "ORIGINAL_DECISION_OUTSIDE_STARTER_FIVE_YEAR_WINDOW"
    )
    assert member["request_identity"] is None
    assert out["newly_selected_case_rights"] == 1
    assert out["new_selected_outside_current_quote_window"] == 1
    assert out["added_physical_quote_queries"] == 0
    assert out["unique_physical_quote_queries"] == 1
