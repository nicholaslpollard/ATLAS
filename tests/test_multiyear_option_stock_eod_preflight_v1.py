from __future__ import annotations

"""Synthetic source-only native-close needs and original 2025 pilot reuse tests."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

import packages.data.multiyear_option_stock_eod_preflight_v1 as m
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import (
    CONTRACT as PILOT_CONTRACT, PLAN_REL as PILOT_PLAN_REL,
)
from packages.data.multiyear_observed_option_quote_timeline_v1 import CONTRACT as TIME_CONTRACT


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def sources(monkeypatch):
    native = signed({
        "case_denominator": 2, "provider_requests": 0, "protected_outcomes_read": 0,
        "rows": [
            {"case_id": name, "instrument_id": "UUID-1", "ticker": "TEST",
             "signal_session": "2022-03-01", "entry_session": "2022-03-02"}
            for name in ("one", "two")
        ],
    }, "source_fingerprint")
    monkeypatch.setattr(m, "NATIVE_FP", native["source_fingerprint"])
    call = "TEST220318C00100000"
    put = "TEST220318P00100000"
    selection = signed({
        "original_case_denominator": 2, "right_policy": "both",
        "cases": [
            {"case_id": "one:C", "original_case_id": "one",
             "option_symbol": call, "right": "call", "expiration": "2022-03-18",
             "decision_at_utc": "2022-03-02T14:35:00+00:00"},
            {"case_id": "one:P", "original_case_id": "one",
             "option_symbol": put, "right": "put", "expiration": "2022-03-18",
             "decision_at_utc": "2022-03-02T14:35:00+00:00"},
            {"case_id": "two:C", "original_case_id": "two",
             "option_symbol": call, "right": "call", "expiration": "2022-03-18",
             "decision_at_utc": "2022-03-02T14:35:00+00:00"},
        ],
    }, "selection_fingerprint")
    q1 = {
        "session_et": "2022-03-03", "provider_updated_at_utc": "2022-03-03T21:00:00+00:00",
        "two_sided_source": True, "observed_bid_per_share": "1.0",
        "observed_ask_per_share": "1.2",
    }
    q2 = {
        "session_et": "2022-03-07", "provider_updated_at_utc": "2022-03-07T21:00:00+00:00",
        "two_sided_source": True, "observed_bid_per_share": "1.3",
        "observed_ask_per_share": "1.5",
    }
    timeline = signed({
        "contract": TIME_CONTRACT,
        "status": "OFFLINE_OBSERVED_QUOTE_SOURCE_TIMELINES_ONLY",
        "selection_fingerprint": selection["selection_fingerprint"],
        "original_case_denominator": 2, "original_right_memberships": 4,
        "selected_case_right_memberships": 3, "provider_requests": 0,
        "account_pnl_authority": False, "protected_2026_outcomes_read": 0,
        "rows": [
            dict(case_right_id="one:C", original_case_id="one", year="2022",
                 option_symbol=call, timeline_status="TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES",
                 first_later_observed_quote=q1, next_later_observed_quote=q2),
            dict(case_right_id="one:P", original_case_id="one", year="2022",
                 option_symbol=put, timeline_status="FIRST_LATER_TWO_SIDED_SOURCE_ONLY",
                 first_later_observed_quote=q1, next_later_observed_quote=None),
            dict(case_right_id="two:C", original_case_id="two", year="2022",
                 option_symbol=call, timeline_status="TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES",
                 first_later_observed_quote=q1, next_later_observed_quote=q2),
            dict(case_right_id="two:P", original_case_id="two", year="2022",
                 option_symbol=None, timeline_status="NO_PIT_SELECTED_CONTRACT",
                 first_later_observed_quote=None, next_later_observed_quote=None),
        ],
    }, "timeline_fingerprint")
    return native, selection, timeline


def test_deduplicate_raw_stock_close_needs_and_keep_every_original_slot(monkeypatch, tmp_path):
    native, selection, timeline = sources(monkeypatch)
    r = m.build_native_eod_needs(native, selection, timeline, expected_original_cases=2)
    assert r["unique_native_raw_eod_close_requests"] == 2
    assert r["case_rights_with_two_later_option_quote_dates"] == 2
    assert r["original_right_memberships"] == 4
    assert r["provider_requests"] == r["native_raw_closes_read"] == 0
    assert all(x["native_close_verified"] is False for x in r["rows"])
    assert [x["session_et"] for x in sorted(r["requests"], key=lambda x: x["session_et"])] == [
        "2022-03-03", "2022-03-07",
    ]
    first = next(x for x in r["requests"] if x["session_et"] == "2022-03-03")
    assert first["case_right_ids"] == ["one:C", "one:P", "two:C"]
    settings = SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda x:
            None if x == "options" else pytest.fail("wrong category"),
    )
    path, status = m.persist_source_needs(settings, r)
    assert status == "WRITTEN_IMMUTABLE_STOCK_EOD_SOURCE_DEMAND"
    assert m.persist_source_needs(settings, r)[1] == "REUSED_IDENTICAL_STOCK_EOD_SOURCE_DEMAND"
    path.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError):
        m.persist_source_needs(settings, r)


def test_stock_dates_and_original_identity_fail_closed(monkeypatch):
    native, selection, timeline = sources(monkeypatch)
    timeline["rows"][0]["first_later_observed_quote"]["session_et"] = "2022-03-02"
    timeline = signed({k: v for k, v in timeline.items() if k != "timeline_fingerprint"},
                      "timeline_fingerprint")
    with pytest.raises(m.OptionStockEodNeedsError, match="chronology"):
        m.build_native_eod_needs(native, selection, timeline, expected_original_cases=2)
    native, selection, timeline = sources(monkeypatch)
    native["rows"][0]["ticker"] = "CHANGED"
    with pytest.raises(ValueError, match="fingerprint"):
        m.build_native_eod_needs(native, selection, timeline, expected_original_cases=2)


def test_pilot_full_and_partial_exact_symbol_overlap_not_unverified_reuse(tmp_path):
    reqs = [
        dict(request_identity="a" * 64, option_symbol="TEST251017C00100000",
             from_inclusive="2025-01-01", to_exclusive="2025-10-18"),
        dict(request_identity="b" * 64, option_symbol="TEST251017P00100000",
             from_inclusive="2025-09-01", to_exclusive="2025-10-18"),
    ]
    plan = signed({"requests": reqs}, "plan_fingerprint")
    handoff = signed({
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "rows": [
            {"quote_request_identity": x["request_identity"],
             "quote_history_status": "QUOTE_HISTORY_NOT_ACQUIRED"}
            for x in reqs
        ],
    }, "handoff_fingerprint")
    old = [
        dict(option_symbol=x["option_symbol"], request_identity=str(i) * 64,
             from_inclusive=("2025-08-01" if i == 1 else "2025-01-01"),
             to_exclusive="2025-10-18")
        for i, x in enumerate(reqs, 1)
    ]
    old.extend(
        {"option_symbol": f"NONE{i}251017C00100000", "request_identity": str(i) * 64,
         "from_inclusive": "2025-01-01", "to_exclusive": "2025-10-18"}
        for i in range(3, 12)
    )
    pilot = signed({
        "contract": PILOT_CONTRACT, "status": "FROZEN_SELECTED_EOD_QUOTE_SOURCE_PLAN",
        "request_count": 11, "requests": old,
    }, "plan_fingerprint")
    path = tmp_path / PILOT_PLAN_REL
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(pilot), encoding="utf-8")
    settings = SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda x:
            None if x == "options" else pytest.fail("wrong category"),
    )
    called = []
    def receipt(item, fingerprint):
        called.append(item["option_symbol"])
        assert fingerprint == pilot["plan_fingerprint"]
        return {"status": "COMPLETE_SOURCE_ONLY", "body_sha256": "f" * 64,
                "safe_summary": {"observed_rows": 20}}
    result = m.preview_pilot_quote_overlap(
        settings, plan, handoff, read_verified_pilot=receipt,
    )
    assert len(called) == 2
    assert result["pending_unique_exact_requests"] == 2
    assert result["candidate_full_coverage_sources"] == 1
    assert result["candidate_partial_overlap_sources"] == 1
    assert result["provider_requests"] == 0
    assert all(x["not_a_historical_fill_or_full_reuse_if_partial"] for x in result["rows"])
    path, status = m.persist_pilot_overlap(settings, result)
    assert status == "WRITTEN_IMMUTABLE_PILOT_QUOTE_OVERLAP"
    assert m.persist_pilot_overlap(settings, result)[0] == path


def test_pilot_missing_plan_is_not_claimed_as_reused(tmp_path):
    plan = signed({"requests": [{"request_identity": "a" * 64,
                 "option_symbol": "TEST251017C00100000"}]}, "plan_fingerprint")
    handoff = signed({
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "rows": [{"quote_request_identity": "a" * 64,
                  "quote_history_status": "QUOTE_HISTORY_NOT_ACQUIRED"}],
    }, "handoff_fingerprint")
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p,
                               assert_external_storage_binding=lambda x: None)
    result = m.preview_pilot_quote_overlap(settings, plan, handoff)
    assert result["status"] == "NO_LOCAL_PILOT_PLAN_NO_REUSE_CLAIM"
    assert result["candidate_full_coverage_sources"] == 0
    _, action = m.persist_pilot_overlap(settings, result)
    assert action == "WRITTEN_IMMUTABLE_PILOT_QUOTE_OVERLAP"


def test_2025_option_sources_crossing_into_2026_keep_native_requests_but_mark_them_protected(monkeypatch):
    native, selection, timeline = sources(monkeypatch)
    native["rows"][0]["signal_session"] = "2025-12-29"
    native["rows"][0]["entry_session"] = "2025-12-30"
    native = signed({k: v for k, v in native.items() if k != "source_fingerprint"},
                    "source_fingerprint")
    monkeypatch.setattr(m, "NATIVE_FP", native["source_fingerprint"])
    for picked in selection["cases"]:
        if picked["original_case_id"] == "one":
            picked["expiration"] = "2026-01-16"
            picked["decision_at_utc"] = "2025-12-30T14:35:00+00:00"
    selection = signed(
        {k: v for k, v in selection.items() if k != "selection_fingerprint"},
        "selection_fingerprint",
    )
    q1 = {
        "session_et": "2026-01-02",
        "provider_updated_at_utc": "2026-01-02T21:00:00+00:00",
        "two_sided_source": True,
        "observed_bid_per_share": "1.0",
        "observed_ask_per_share": "1.2",
    }
    q2 = {
        "session_et": "2026-01-05",
        "provider_updated_at_utc": "2026-01-05T21:00:00+00:00",
        "two_sided_source": True,
        "observed_bid_per_share": "1.1",
        "observed_ask_per_share": "1.3",
    }
    for candidate in timeline["rows"]:
        if candidate["original_case_id"] == "one":
            candidate["year"] = "2025"
    row = timeline["rows"][0]
    row["first_later_observed_quote"] = q1
    row["next_later_observed_quote"] = q2
    for other in timeline["rows"][1:]:
        other["first_later_observed_quote"] = None
        other["next_later_observed_quote"] = None
        other["timeline_status"] = "NO_VALID_LATER_TWO_SIDED_SOURCE"
    timeline["selection_fingerprint"] = selection["selection_fingerprint"]
    timeline = signed(
        {k: v for k, v in timeline.items() if k != "timeline_fingerprint"},
        "timeline_fingerprint",
    )
    report = m.build_native_eod_needs(
        native, selection, timeline, expected_original_cases=2,
    )
    protected_row = next(x for x in report["rows"] if x["case_right_id"] == "one:C")
    assert protected_row["status"] == m.PROTECTED_2026
    assert protected_row["protected_2026_native_entry_withheld"] is True
    assert protected_row["protected_2026_native_next_withheld"] is True
    assert report["case_rights_with_protected_2026_native_close_withheld"] == 1
    protected_requests = [
        x for x in report["requests"]
        if x["session_et"].startswith("2026-")
    ]
    assert len(protected_requests) == 2
    assert all(x["protected_2026_native_read_forbidden"] is True
               for x in protected_requests)
    assert report["protected_2026_outcomes_read"] == 0
