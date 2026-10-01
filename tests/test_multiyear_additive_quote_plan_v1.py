from __future__ import annotations

from datetime import UTC, date, datetime
import json
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_additive_quote_plan_v1 import (
    AdditiveQuotePlanError, build_additive_quote_plan,
    discover_additive_quote_lineage, persist_additive_quote_plan,
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


def test_additive_plan_is_stable_across_same_et_day_restarts():
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
    morning = build_additive_quote_plan(
        before, plan, after,
        asof_utc=datetime(2026, 9, 30, 13, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    evening = build_additive_quote_plan(
        before, plan, after,
        asof_utc=datetime(2026, 9, 30, 22, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    assert morning == evening
    assert morning["additive_planning_day_et"] == "2026-09-30"


def lineage_settings(tmp_path):
    return SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda c:
            None if c == "options" else pytest.fail("wrong storage category"),
    )


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_discover_lineage_carries_sep30_additive_exact_window_into_oct1(tmp_path):
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    rolled = selected(
        "two:P", "TEST211015P00100000", "put",
        "SELECTED_VERIFIED_PIT_CHAIN",
        expiration="2021-10-15",
        decision="2021-09-30T13:35:00+00:00",
    )
    years = {"one": "2022", "two": "2021"}
    root_selection = selection([old], years=years)
    root_plan = base_plan(old)
    sep30_selection = selection([old, rolled], years=years)
    sep30_plan = build_additive_quote_plan(
        root_selection,
        root_plan,
        sep30_selection,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    rolled_request = next(
        x for x in sep30_plan["requests"]
        if x["option_symbol"] == rolled["option_symbol"]
    )
    assert rolled_request["from_inclusive"] == "2021-09-30"

    root = tmp_path / "data/options/manifests"
    selection_path = root / (
        "multiyear_pit_selected_option_quotes_v1_"
        + sep30_selection["selection_fingerprint"][:16] + ".json"
    )
    plan_path = root / (
        "multiyear_demand_quote_v1_"
        + sep30_plan["plan_fingerprint"][:16] + ".json"
    )
    write_json(selection_path, sep30_selection)
    write_json(plan_path, sep30_plan)

    lineage = discover_additive_quote_lineage(
        lineage_settings(tmp_path),
        root_selection,
        root_plan,
        root_plan_path=tmp_path / "root-plan.json",
        expected_original_cases=2,
    )
    assert len(lineage) == 2
    assert lineage[-1].plan_path == plan_path
    assert lineage[-1].selection_path == selection_path
    assert lineage[-1].plan == sep30_plan
    assert lineage[-1].selection == sep30_selection

    # October 1 must not re-freeze the September 30 case against the newer floor.
    oct1 = build_additive_quote_plan(
        lineage[-1].selection,
        lineage[-1].plan,
        sep30_selection,
        asof_utc=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 30),
        expected_original_cases=2,
    )
    assert oct1 == sep30_plan
    assert next(
        x for x in oct1["requests"]
        if x["option_symbol"] == rolled["option_symbol"]
    )["from_inclusive"] == "2021-09-30"

    # Demonstrate why restarting from the root would be scientifically wrong.
    naive = build_additive_quote_plan(
        root_selection,
        root_plan,
        sep30_selection,
        asof_utc=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 30),
        expected_original_cases=2,
    )
    naive_member = next(
        x for x in naive["memberships"] if x["case_id"] == "two:P"
    )
    assert naive_member["disposition"] == (
        "ORIGINAL_DECISION_OUTSIDE_STARTER_FIVE_YEAR_WINDOW"
    )
    assert naive_member["request_identity"] is None


def test_discover_lineage_rejects_fork_from_same_parent(tmp_path):
    old = selected(
        "one:C", "TEST220318C00100000", "call",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    new = selected(
        "two:P", "TEST220318P00100000", "put",
        "SELECTED_VERIFIED_PIT_CHAIN",
    )
    root_selection = selection([old])
    root_plan = base_plan(old)
    expanded = selection([old, new])
    child = build_additive_quote_plan(
        root_selection,
        root_plan,
        expanded,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=2,
    )
    fork = dict(child)
    fork["last_completed_session"] = "2026-09-30"
    fork["plan_fingerprint"] = _fingerprint({
        k: v for k, v in fork.items() if k != "plan_fingerprint"
    })

    root = tmp_path / "data/options/manifests"
    write_json(
        root / (
            "multiyear_pit_selected_option_quotes_v1_"
            + expanded["selection_fingerprint"][:16] + ".json"
        ),
        expanded,
    )
    write_json(
        root / (
            "multiyear_demand_quote_v1_"
            + child["plan_fingerprint"][:16] + ".json"
        ),
        child,
    )
    write_json(
        root / (
            "multiyear_demand_quote_v1_"
            + fork["plan_fingerprint"][:16] + ".json"
        ),
        fork,
    )
    with pytest.raises(AdditiveQuotePlanError, match="lineage fork"):
        discover_additive_quote_lineage(
            lineage_settings(tmp_path),
            root_selection,
            root_plan,
            expected_original_cases=2,
        )
