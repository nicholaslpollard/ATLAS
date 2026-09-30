from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_quote_tail_recovery_v1 import (
    build_recovery_overlay, build_tail_recovery_plan,
    persist_recovery_overlay, persist_tail_recovery_plan,
)


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def request_id(symbol: str, start: str, end: str) -> str:
    return _fingerprint({
        "contract": QUOTE_CONTRACT,
        "query": {
            "option_symbol": symbol,
            "from_inclusive": start,
            "to_exclusive": end,
        },
    })


def inputs():
    old_symbol = "TEST211015C00100000"
    newer_symbol = "TEST230318C00100000"
    old_id = request_id(old_symbol, "2021-09-27", "2021-10-16")
    newer_id = request_id(newer_symbol, "2023-01-01", "2023-03-19")
    requests = [
        {
            "request_identity": old_id,
            "option_symbol": old_symbol,
            "from_inclusive": "2021-09-27",
            "to_exclusive": "2021-10-16",
            "member_case_ids": ["one:C", "two:C"],
            "source_only_not_validated_trade": True,
        },
        {
            "request_identity": newer_id,
            "option_symbol": newer_symbol,
            "from_inclusive": "2023-01-01",
            "to_exclusive": "2023-03-19",
            "member_case_ids": ["three:C"],
            "source_only_not_validated_trade": True,
        },
    ]
    memberships = [
        {
            "case_id": "one:C", "ticker": "TEST",
            "option_symbol": old_symbol,
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": old_id,
        },
        {
            "case_id": "two:C", "ticker": "TEST",
            "option_symbol": old_symbol,
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": old_id,
        },
        {
            "case_id": "three:C", "ticker": "TEST",
            "option_symbol": newer_symbol,
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": newer_id,
        },
    ]
    plan = signed({
        "contract": QUOTE_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": "2026-09-27T20:00:00+00:00",
        "rolling_five_year_floor": "2021-09-27",
        "last_completed_session": "2026-09-25",
        "requested_case_denominator": 3,
        "unique_physical_quote_queries": 2,
        "memberships": memberships,
        "requests": requests,
        "provider_requests": 0,
        "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
    }, "plan_fingerprint")
    census = signed({
        "contract": QUOTE_CONTRACT,
        "plan_fingerprint": plan["plan_fingerprint"],
        "status": "PREVIEW_ONLY_NO_PROVIDER_GETS",
        "original_requested_case_denominator": 3,
        "unique_physical_quote_queries": 2,
        "ineligible_original_cases": 0,
        "reused_original_2022": 0,
        "new_cache_complete": 1,
        "exact_source_gaps": 0,
        "pending": 1,
        "rolling_floor_stale_pending": 0,
        "current_paid_rolling_floor_et": None,
        "new_provider_attempts": 0,
        "observed_credits": 0,
        "last_observed_provider_remaining": None,
        "provider_read_authority_only_not_strategy_or_pnl": True,
        "source_entries": [{
            "request_identity": newer_id,
            "status": "COMPLETE_SOURCE_ONLY",
            "body_sha256": "c" * 64,
            "cached_observed_rows": 10,
        }],
    }, "report_fingerprint")
    return plan, census, old_id, newer_id


def test_build_tail_recovery_clips_only_pending_stale_exact_request():
    plan, census, old_id, _ = inputs()
    recovery = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
    )
    assert recovery["rolling_five_year_floor"] == "2021-09-30"
    assert recovery["recovery_asof_day_et"] == "2026-09-30"
    assert recovery["original_pending_queries"] == 1
    assert recovery["original_stale_queries"] == 1
    assert recovery["recoverable_stale_queries"] == 1
    assert recovery["distinct_recovery_queries"] == 1
    assert recovery["requested_case_denominator"] == 2
    request = recovery["requests"][0]
    assert request["option_symbol"] == "TEST211015C00100000"
    assert request["from_inclusive"] == "2021-09-30"
    assert request["to_exclusive"] == "2021-10-16"
    assert request["recovery_of_request_identities"] == [old_id]
    assert sorted(request["member_case_ids"]) == ["one:C", "two:C"]
    assert all(m["recovery_of_request_identity"] == old_id
               for m in recovery["memberships"])
    assert recovery["provider_requests"] == 0
    assert recovery["historical_fill_or_pnl_authority"] is False


def test_recovery_plan_same_day_is_deterministic_and_does_not_reacquire_completed():
    plan, census, _, newer_id = inputs()
    original_fp = plan["plan_fingerprint"]
    a = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    b = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 22, 0, tzinfo=UTC),
    )
    assert a == b
    assert plan["plan_fingerprint"] == original_fp
    assert all(r["request_identity"] != newer_id for r in a["requests"])
    assert a["recovery_origin_plan_fingerprint"] == original_fp
    assert a["missing_prefix_not_reconstructed"] is True


def test_verified_overlay_maps_recovery_body_to_original_request_only_as_partial_source():
    plan, census, old_id, _ = inputs()
    recovery = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
    )
    rid = recovery["requests"][0]["request_identity"]
    recovered_census = signed({
        "contract": QUOTE_CONTRACT,
        "plan_fingerprint": recovery["plan_fingerprint"],
        "status": "ALL_ELIGIBLE_SOURCE_QUERIES_ACCOUNTED",
        "original_requested_case_denominator": 2,
        "unique_physical_quote_queries": 1,
        "ineligible_original_cases": 0,
        "reused_original_2022": 0,
        "new_cache_complete": 1,
        "exact_source_gaps": 0,
        "pending": 0,
        "rolling_floor_stale_pending": 0,
        "current_paid_rolling_floor_et": None,
        "new_provider_attempts": 0,
        "observed_credits": 0,
        "last_observed_provider_remaining": None,
        "provider_read_authority_only_not_strategy_or_pnl": True,
        "source_entries": [{
            "request_identity": rid,
            "status": "COMPLETE_SOURCE_ONLY",
            "body_sha256": "d" * 64,
            "cached_observed_rows": 7,
        }],
    }, "report_fingerprint")
    overlay = build_recovery_overlay(plan, recovery, recovered_census)
    assert overlay["recoverable_original_requests"] == 1
    assert overlay["complete_recovery_queries"] == 1
    row = overlay["rows"][0]
    assert row["original_request_identity"] == old_id
    assert row["recovery_request_identity"] == rid
    assert row["source_from_inclusive"] == "2021-09-30"
    assert row["quote_body_sha256"] == "d" * 64
    assert row["missing_original_prefix_is_not_reconstructed"] is True
    assert overlay["original_window_fully_reconstructed"] is False
    assert overlay["historical_fill_or_pnl_authority"] is False


def test_recovery_outputs_are_immutable_and_d_bound(tmp_path):
    plan, census, _, _ = inputs()
    recovery = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
    )
    settings = SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda c:
            None if c == "options" else pytest.fail("wrong storage category"),
    )
    path, action = persist_tail_recovery_plan(settings, recovery)
    assert action == "WRITTEN_IMMUTABLE_TAIL_RECOVERY_PLAN"
    assert persist_tail_recovery_plan(settings, recovery)[0] == path
    rid = recovery["requests"][0]["request_identity"]
    rc = signed({
        "plan_fingerprint": recovery["plan_fingerprint"],
        "status": "ALL_ELIGIBLE_SOURCE_QUERIES_ACCOUNTED",
        "new_provider_attempts": 0, "observed_credits": 0,
        "source_entries": [{
            "request_identity": rid, "status": "COMPLETE_SOURCE_ONLY",
            "body_sha256": "d" * 64, "cached_observed_rows": 5,
        }],
    }, "report_fingerprint")
    overlay = build_recovery_overlay(plan, recovery, rc)
    opath, oaction = persist_recovery_overlay(settings, overlay)
    assert oaction == "WRITTEN_IMMUTABLE_TAIL_RECOVERY_OVERLAY"
    assert persist_recovery_overlay(settings, overlay)[0] == opath


def test_resigned_but_wrong_original_request_identity_is_rejected():
    plan, census, _, _ = inputs()
    plan["requests"][0]["request_identity"] = "0" * 64
    plan["memberships"][0]["request_identity"] = "0" * 64
    plan["memberships"][1]["request_identity"] = "0" * 64
    plan["plan_fingerprint"] = _fingerprint({
        k: v for k, v in plan.items() if k != "plan_fingerprint"
    })
    census["plan_fingerprint"] = plan["plan_fingerprint"]
    census["report_fingerprint"] = _fingerprint({
        k: v for k, v in census.items() if k != "report_fingerprint"
    })
    with pytest.raises(ValueError, match="partition"):
        build_tail_recovery_plan(
            plan, census,
            asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        )
