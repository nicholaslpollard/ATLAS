from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_additive_quote_plan_v1 import CONTRACT as ADDITIVE_CONTRACT
from packages.data.multiyear_quote_tail_recovery_v1 import OVERLAY_CONTRACT
from scripts.continue_multiyear_source_refresh_offline_v1 import (
    OfflineContinuationError, _find_additive_plan, _find_recovery_overlay,
)


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def settings(tmp_path):
    return SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
    )


def write_json(path, value):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def additive(base_fp="b" * 64, selection_fp="s" * 64):
    return signed({
        "contract": "atlas-multiyear-exact-option-quote-demand-v1",
        "additive_contract": ADDITIVE_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": "2026-09-30T04:00:00+00:00",
        "additive_planning_day_et": "2026-09-30",
        "rolling_five_year_floor": "2021-09-30",
        "last_completed_session": "2026-09-29",
        "requested_case_denominator": 10,
        "unique_physical_quote_queries": 2,
        "memberships": [],
        "requests": [],
        "provider_requests": 0,
        "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
        "base_selection_fingerprint": "x" * 64,
        "expanded_selection_fingerprint": selection_fp,
        "base_quote_plan_fingerprint": base_fp,
        "preserved_selected_case_rights": 1,
        "newly_selected_case_rights": 1,
        "base_physical_quote_queries": 1,
        "added_physical_quote_queries": 1,
        "new_selected_outside_current_quote_window": 0,
        "prior_selected_contracts_changed": 0,
        "base_exact_windows_preserved": True,
        "new_exact_windows_use_current_rolling_floor": True,
        "historical_fill_or_pnl_authority": False,
    }, "plan_fingerprint")


def overlay(plan_fp):
    return signed({
        "contract": OVERLAY_CONTRACT,
        "status": "CLIPPED_SOURCE_OVERLAY_NO_ORIGINAL_WINDOW_COMPLETENESS_CLAIM",
        "original_plan_fingerprint": plan_fp,
        "recovery_plan_fingerprint": "r" * 64,
        "recovery_census_fingerprint": "c" * 64,
        "current_floor_et": "2021-09-30",
        "recoverable_original_requests": 1,
        "distinct_recovery_queries": 1,
        "complete_recovery_queries": 1,
        "recovery_query_gaps": 0,
        "pending_recovery_queries": 0,
        "rows": [],
        "provider_requests": 0,
        "original_window_fully_reconstructed": False,
        "historical_fill_or_pnl_authority": False,
    }, "overlay_fingerprint")


def test_discovers_exact_acquisition_day_additive_plan_and_overlay(tmp_path):
    base = {"plan_fingerprint": "b" * 64}
    selection = {"selection_fingerprint": "s" * 64}
    plan = additive()
    plan_path = (
        tmp_path / "data/options/manifests"
        / f"multiyear_demand_quote_v1_{plan['plan_fingerprint'][:16]}.json"
    )
    write_json(plan_path, plan)
    found_path, found = _find_additive_plan(
        settings(tmp_path), base, selection, date(2026, 9, 30),
    )
    assert found_path == plan_path
    assert found == plan

    ov = overlay(plan["plan_fingerprint"])
    ov_path = (
        tmp_path / "data/options/manifests"
        / f"multiyear_stale_quote_recovery_overlay_v1_{ov['overlay_fingerprint'][:16]}.json"
    )
    write_json(ov_path, ov)
    found_ov_path, found_ov = _find_recovery_overlay(settings(tmp_path), plan)
    assert found_ov_path == ov_path
    assert found_ov == ov


def test_wrong_day_or_selection_cannot_be_silently_substituted(tmp_path):
    plan = additive()
    path = (
        tmp_path / "data/options/manifests"
        / f"multiyear_demand_quote_v1_{plan['plan_fingerprint'][:16]}.json"
    )
    write_json(path, plan)
    with pytest.raises(OfflineContinuationError, match="exactly one additive"):
        _find_additive_plan(
            settings(tmp_path),
            {"plan_fingerprint": "b" * 64},
            {"selection_fingerprint": "s" * 64},
            date(2026, 10, 1),
        )
    with pytest.raises(OfflineContinuationError, match="exactly one additive"):
        _find_additive_plan(
            settings(tmp_path),
            {"plan_fingerprint": "b" * 64},
            {"selection_fingerprint": "z" * 64},
            date(2026, 9, 30),
        )


def test_multiple_matching_plans_or_overlays_fail_closed(tmp_path):
    base = {"plan_fingerprint": "b" * 64}
    selection = {"selection_fingerprint": "s" * 64}
    a = additive()
    b = dict(a)
    b["last_completed_session"] = "2026-09-30"
    b["plan_fingerprint"] = _fingerprint({
        k: v for k, v in b.items() if k != "plan_fingerprint"
    })
    root = tmp_path / "data/options/manifests"
    write_json(root / f"multiyear_demand_quote_v1_{a['plan_fingerprint'][:16]}.json", a)
    write_json(root / f"multiyear_demand_quote_v1_{b['plan_fingerprint'][:16]}.json", b)
    with pytest.raises(OfflineContinuationError, match="found 2"):
        _find_additive_plan(
            settings(tmp_path), base, selection, date(2026, 9, 30),
        )

    # Remove second plan so the overlay branch can be tested independently.
    (root / f"multiyear_demand_quote_v1_{b['plan_fingerprint'][:16]}.json").unlink()
    o1 = overlay(a["plan_fingerprint"])
    o2 = dict(o1)
    o2["recovery_census_fingerprint"] = "d" * 64
    o2["overlay_fingerprint"] = _fingerprint({
        k: v for k, v in o2.items() if k != "overlay_fingerprint"
    })
    write_json(
        root / f"multiyear_stale_quote_recovery_overlay_v1_{o1['overlay_fingerprint'][:16]}.json",
        o1,
    )
    write_json(
        root / f"multiyear_stale_quote_recovery_overlay_v1_{o2['overlay_fingerprint'][:16]}.json",
        o2,
    )
    with pytest.raises(OfflineContinuationError, match="found 2"):
        _find_recovery_overlay(settings(tmp_path), a)
