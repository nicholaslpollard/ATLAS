from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_quote_tail_recovery_v1 import (
    QuoteTailRecoveryError, build_recovery_overlay, build_tail_recovery_plan,
    persist_recovery_overlay, persist_tail_recovery_plan,
)


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def inputs():
    requests = [
        {
            "request_identity": "a" * 64,
            "option_symbol": "TEST211015C00100000",
            "from_inclusive": "2021-09-27",
            "to_exclusive": "2021-10-16",
            "member_case_ids": ["one:C", "two:C"],
            "source_only_not_validated_trade": True,
        },
        {
            "request_identity": "b" * 64,
            "option_symbol": "TEST230318C00100000",
            "from_inclusive": "2023-01-01",
            "to_exclusive": "2023-03-19",
            "member_case_ids": ["three:C"],
            "source_only_not_validated_trade": True,
        },
    ]
    memberships = [
        {
            "case_id": "one:C", "ticker": "TEST",
            "option_symbol": requests[0]["option_symbol"],
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": "a" * 64,
        },
        {
            "case_id": "two:C", "ticker": "TEST",
            "option_symbol": requests[0]["option_symbol"],
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": "a" * 64,
        },
        {
            "case_id": "three:C", "ticker": "TEST",
            "option_symbol": requests[1]["option_symbol"],
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": "b" * 64,
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
            "request_identity": "b" * 64,
            "status": "COMPLETE_SOURCE_ONLY",
            "body_sha256": "c" * 64,
            "cached_observed_rows": 10,
        }],
    }, "report_fingerprint")
    return plan, census


def test_build_tail_recovery_clips_only_pending_stale_exact_request():
    plan, census = inputs()
    recovery = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
    )
    assert recovery["rolling_five_year_floor"] == "2021-09-30"
    assert recovery["original_pending_queries"] == 1
    assert recovery["original_stale_queries"] == 1
    assert recovery["recoverable_stale_queries"] == 1
    assert recovery["distinct_recovery_queries"] == 1
    assert recovery["requested_case_denominator"] == 2
    request = recovery["requests"][0]
    assert request["option_symbol"] == "TEST211015C00100000"
    assert request["from_inclusive"] == "2021-09-30"
    assert request["to_exclusive"] == "2021-10-16"
    assert request["recovery_of_request_identities"] == ["a" * 64]
    assert sorted(request["member_case_ids"]) == ["one:C", "two:C"]
    assert all(m["recovery_of_request_identity"] == "a" * 64
               for m in recovery["memberships"])
    assert recovery["provider_requests"] == 0
    assert recovery["historical_fill_or_pnl_authority"] is False


def test_recovery_plan_does_not_reacquire_completed_or_rewrite_original():
    plan, census = inputs()
    original_fp = plan["plan_fingerprint"]
    recovery = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
    )
    assert plan["plan_fingerprint"] == original_fp
    assert all(r["option_symbol"] != "TEST230318C00100000"
               for r in recovery["requests"])
    assert recovery["recovery_origin_plan_fingerprint"] == original_fp
    assert recovery["missing_prefix_not_reconstructed"] is True


def test_expired_stale_request_is_retained_as_unrecoverable_not_dropped():
    plan, census = inputs()
    plan["requests"][0]["to_exclusive"] = "2021-09-29"
    signed({k: v for k, v in plan.items() if k != "plan_fingerprint"},
           "plan_fingerprint")
    # mutate in place above did not replace fingerprint; resign explicitly
    plan["plan_fingerprint"] = _fingerprint({
        k: v for k, v in plan.items() if k != "plan_fingerprint"
    })
    census["plan_fingerprint"] = plan["plan_fingerprint"]
    census["report_fingerprint"] = _fingerprint({
        k: v for k, v in census.items() if k != "report_fingerprint"
    })
    recovery = build_tail_recovery_plan(
        plan, census,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
    )
    assert recovery["recoverable_stale_queries"] == 0
    assert recovery["expired_before_current_floor_queries"] == 1
    assert recovery["expired_original_request_identities"] == ["a" * 64]
    assert recovery["requests"] == []


def test_verified_overlay_maps_recovery_body_to_original_request_only_as_partial_source():
    plan, census = inputs()
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
    assert row["original_request_identity"] == "a" * 64
    assert row["recovery_request_identity"] == rid
    assert row["source_from_inclusive"] == "2021-09-30"
    assert row["quote_body_sha256"] == "d" * 64
    assert row["missing_original_prefix_is_not_reconstructed"] is True
    assert overlay["original_window_fully_reconstructed"] is False
    assert overlay["historical_fill_or_pnl_authority"] is False


def test_recovery_outputs_are_immutable_and_d_bound(tmp_path):
    plan, census = inputs()
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
