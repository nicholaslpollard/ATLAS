from __future__ import annotations

from datetime import UTC, date, datetime
import json
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_additive_quote_plan_v1 import build_additive_quote_plan
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_option_quote_bridge_v1 import CONTRACT as SELECTION_CONTRACT
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
        assert_external_storage_binding=lambda c:
            None if c == "options" else pytest.fail("wrong storage category"),
    )


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def selected(case_id: str, symbol: str, right: str, *, decision: str, expiration: str):
    original = case_id.rsplit(":", 1)[0]
    return {
        "case_id": case_id,
        "original_case_id": original,
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
        "source_selection_status": "SELECTED_VERIFIED_PIT_CHAIN",
        "not_an_option_fill_or_validated_deliverable": True,
    }


def selection(cases):
    by = {x["case_id"]: x for x in cases}
    coverage = []
    for original in ("one", "two", "three"):
        for right, suffix in (("call", "C"), ("put", "P")):
            cid = f"{original}:{suffix}"
            chosen = by.get(cid)
            coverage.append({
                "case_id": original,
                "signal_year": "2022",
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
        "original_case_denominator": 3,
        "right_policy": "both",
        "original_right_memberships": 6,
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


def request_id(symbol: str, start: str, end: str) -> str:
    return _fingerprint({
        "contract": QUOTE_CONTRACT,
        "query": {
            "option_symbol": symbol,
            "from_inclusive": start,
            "to_exclusive": end,
        },
    })


def root_plan(root_case):
    rid = request_id(root_case["option_symbol"], "2022-01-01", "2022-03-19")
    return signed({
        "contract": QUOTE_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": "2026-09-27T16:00:00+00:00",
        "rolling_five_year_floor": "2021-09-27",
        "last_completed_session": "2026-09-25",
        "requested_case_denominator": 1,
        "unique_physical_quote_queries": 1,
        "memberships": [{
            "case_id": root_case["case_id"],
            "decision_at_utc": root_case["decision_at_utc"],
            "selected_at_utc": root_case["selected_at_utc"],
            "original_accepted_stock_source_sha256":
                root_case["accepted_stock_source_sha256"],
            "ticker": "TEST",
            "option_symbol": root_case["option_symbol"],
            "disposition": "SOURCE_DEMAND_READY",
            "request_identity": rid,
        }],
        "requests": [{
            "option_symbol": root_case["option_symbol"],
            "from_inclusive": "2022-01-01",
            "to_exclusive": "2022-03-19",
            "request_identity": rid,
            "member_case_ids": [root_case["case_id"]],
            "source_only_not_validated_trade": True,
        }],
        "provider_requests": 0,
        "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
    }, "plan_fingerprint")


def persist_selection_and_plan(tmp_path, selected_doc, plan_doc):
    root = tmp_path / "data/options/manifests"
    selection_path = root / (
        "multiyear_pit_selected_option_quotes_v1_"
        + selected_doc["selection_fingerprint"][:16] + ".json"
    )
    plan_path = root / (
        "multiyear_demand_quote_v1_"
        + plan_doc["plan_fingerprint"][:16] + ".json"
    )
    write_json(selection_path, selected_doc)
    write_json(plan_path, plan_doc)
    return selection_path, plan_path


def build_two_day_lineage(tmp_path):
    one = selected(
        "one:C", "TEST220318C00100000", "call",
        decision="2022-03-02T14:35:00+00:00",
        expiration="2022-03-18",
    )
    two = selected(
        "two:P", "TEST220415P00100000", "put",
        decision="2022-03-15T13:35:00+00:00",
        expiration="2022-04-15",
    )
    three = selected(
        "three:C", "TEST220520C00100000", "call",
        decision="2022-04-20T13:35:00+00:00",
        expiration="2022-05-20",
    )
    root_sel = selection([one])
    root = root_plan(one)
    sep30_sel = selection([one, two])
    sep30 = build_additive_quote_plan(
        root_sel, root, sep30_sel,
        asof_utc=datetime(2026, 9, 30, 15, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 29),
        expected_original_cases=3,
    )
    persist_selection_and_plan(tmp_path, sep30_sel, sep30)

    oct1_sel = selection([one, two, three])
    oct1 = build_additive_quote_plan(
        sep30_sel, sep30, oct1_sel,
        asof_utc=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        last_completed_session=date(2026, 9, 30),
        expected_original_cases=3,
    )
    _, oct1_path = persist_selection_and_plan(tmp_path, oct1_sel, oct1)
    return root_sel, root, sep30_sel, sep30, oct1_sel, oct1, oct1_path


def overlay(plan_fp, floor):
    return signed({
        "contract": OVERLAY_CONTRACT,
        "status": "CLIPPED_SOURCE_OVERLAY_NO_ORIGINAL_WINDOW_COMPLETENESS_CLAIM",
        "original_plan_fingerprint": plan_fp,
        "recovery_plan_fingerprint": "r" * 64,
        "recovery_census_fingerprint": "c" * 64,
        "current_floor_et": floor,
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


def test_discovers_chained_oct1_additive_plan_and_overlay(tmp_path):
    root_sel, root, _, _, current, plan, plan_path = build_two_day_lineage(tmp_path)
    found_path, found = _find_additive_plan(
        settings(tmp_path),
        root_sel,
        root,
        current,
        date(2026, 10, 1),
        expected_original_cases=3,
    )
    assert found_path == plan_path
    assert found == plan
    assert plan["base_quote_plan_fingerprint"] != root["plan_fingerprint"]

    ov = overlay(plan["plan_fingerprint"], plan["rolling_five_year_floor"])
    ov_path = (
        tmp_path / "data/options/manifests"
        / f"multiyear_stale_quote_recovery_overlay_v1_{ov['overlay_fingerprint'][:16]}.json"
    )
    write_json(ov_path, ov)
    found_ov_path, found_ov = _find_recovery_overlay(settings(tmp_path), plan)
    assert found_ov_path == ov_path
    assert found_ov == ov


def test_wrong_day_or_selection_cannot_be_silently_substituted(tmp_path):
    root_sel, root, sep30_sel, _, current, _, _ = build_two_day_lineage(tmp_path)
    with pytest.raises(OfflineContinuationError, match="exactly one additive"):
        _find_additive_plan(
            settings(tmp_path),
            root_sel,
            root,
            current,
            date(2026, 9, 29),
            expected_original_cases=3,
        )
    with pytest.raises(OfflineContinuationError, match="exactly one additive"):
        _find_additive_plan(
            settings(tmp_path),
            root_sel,
            root,
            sep30_sel,
            date(2026, 10, 1),
            expected_original_cases=3,
        )


def test_multiple_matching_overlays_fail_closed(tmp_path):
    root_sel, root, _, _, current, plan, _ = build_two_day_lineage(tmp_path)
    found_path, found = _find_additive_plan(
        settings(tmp_path),
        root_sel,
        root,
        current,
        date(2026, 10, 1),
        expected_original_cases=3,
    )
    assert found_path.is_file()
    assert found == plan

    root_dir = tmp_path / "data/options/manifests"
    o1 = overlay(plan["plan_fingerprint"], plan["rolling_five_year_floor"])
    o2 = dict(o1)
    o2["recovery_census_fingerprint"] = "d" * 64
    o2["overlay_fingerprint"] = _fingerprint({
        k: v for k, v in o2.items() if k != "overlay_fingerprint"
    })
    write_json(
        root_dir / f"multiyear_stale_quote_recovery_overlay_v1_{o1['overlay_fingerprint'][:16]}.json",
        o1,
    )
    write_json(
        root_dir / f"multiyear_stale_quote_recovery_overlay_v1_{o2['overlay_fingerprint'][:16]}.json",
        o2,
    )
    with pytest.raises(OfflineContinuationError, match="found 2"):
        _find_recovery_overlay(settings(tmp_path), plan)
