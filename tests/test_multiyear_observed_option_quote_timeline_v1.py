from __future__ import annotations

"""No-network chronology, duplicate-physical and immutable-evidence tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    ObservedOptionTimelineError, _observation, build_observed_option_timeline,
    persist_observed_option_timeline,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import CONTRACT as HANDOFF_CONTRACT


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def make_inputs():
    symbol = "TEST220318C00100000"
    put = "TEST220318P00100000"
    chosen = [
        dict(case_id=c, original_case_id=o, option_symbol=opt, right=side,
             expiration="2022-03-18",
             decision_at_utc="2022-03-02T14:35:00+00:00",
             source_selection_status="SELECTED_VERIFIED_PIT_CHAIN")
        for c, o, opt, side in (
            ("one:C", "one", symbol, "call"),
            ("one:P", "one", put, "put"),
            ("two:C", "two", symbol, "call"),
        )
    ]
    selection = signed({
        "original_case_denominator": 2, "right_policy": "both",
        "cases": chosen,
    }, "selection_fingerprint")
    reqs = [
        dict(request_identity=i, option_symbol=opt,
             from_inclusive="2022-01-01", to_exclusive="2022-03-19",
             member_case_ids=members)
        for i, opt, members in (
            ("a" * 64, symbol, ["one:C", "two:C"]),
            ("b" * 64, put, ["one:P"]),
        )
    ]
    plan = signed({"requests": reqs}, "plan_fingerprint")
    slots = [
        dict(case_right_id=c, original_case_id=o, year="2022", right=side,
             source_selection_status="SELECTED_VERIFIED_PIT_CHAIN",
             quote_history_status=state,
             option_symbol=opt, quote_request_identity=req,
             quote_source_request_identity=src, quote_body_sha256=body,
             observed_quote_rows=n)
        for c, o, side, state, opt, req, src, body, n in (
            ("one:C", "one", "call", "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
             symbol, "a" * 64, "c" * 64, "d" * 64, 4),
            ("one:P", "one", "put", "QUOTE_HISTORY_NOT_ACQUIRED",
             put, "b" * 64, None, None, None),
            ("two:C", "two", "call", "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
             symbol, "a" * 64, "c" * 64, "d" * 64, 4),
            ("two:P", "two", "put", "NO_PIT_SELECTED_CONTRACT",
             None, None, None, None, None),
        )
    ]
    handoff = signed({
        "contract": HANDOFF_CONTRACT,
        "status": "OFFLINE_SOURCE_REUSE_HANDOFF_NO_TRADE_AUTHORITY",
        "selection_fingerprint": selection["selection_fingerprint"],
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "original_case_denominator": 2, "original_right_memberships": 4,
        "selected_case_right_memberships": 3,
        "unique_quote_queries": 2,
        "reused_original_2022_queries": 1,
        "verified_demand_cache_queries": 0,
        "provider_requests": 0, "portfolio_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
        "rows": slots,
    }, "handoff_fingerprint")
    return selection, plan, handoff


def source(session, bid, ask):
    stamp = datetime.fromisoformat(session + "T21:00:00+00:00")
    return {
        "day": stamp.date(), "updated_at_utc": stamp.isoformat(),
        "bid": Decimal(str(bid)), "ask": Decimal(str(ask)),
        "two_sided": bid > 0 and ask >= bid, "positive_volume": True,
    }


def records():
    return [
        source("2022-03-02", 1, 1.2),  # SAME day, never a 09:35 option fill
        source("2022-03-03", 1.1, 1.3),
        source("2022-03-04", 1.4, 1.2),  # CROSSED; no assumed fill
        source("2022-03-07", 0.8, 1.0),
    ]


def test_shared_physical_series_decoded_once_and_future_source_only():
    selection, plan, handoff = make_inputs()
    calls = []
    def reader(request, row):
        calls.append((request["request_identity"], row["quote_body_sha256"]))
        return records()
    out = build_observed_option_timeline(
        selection, plan, handoff, read_verified_observations=reader,
        expected_original_cases=2,
    )
    assert calls == [("a" * 64, "d" * 64)]
    assert out["original_right_memberships"] == 4
    assert out["unique_verified_physical_histories_decoded"] == 1
    assert out["by_status"] == {
        "NO_PIT_SELECTED_CONTRACT": 1,
        "QUOTE_HISTORY_NOT_ACQUIRED": 1,
        "TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES": 2,
    }
    for row in out["rows"]:
        if row["timeline_status"] == "TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES":
            assert row["later_two_sided_session_count"] == 2
            assert row["first_later_observed_quote"]["session_et"] == "2022-03-03"
            assert row["next_later_observed_quote"]["session_et"] == "2022-03-07"
            assert row["first_later_observed_quote"]["observed_ask_per_share"] == "1.3"
            assert row["next_later_observed_quote"]["observed_bid_per_share"] == "0.8"
    assert out["option_fills_verified"] == 0 and out["account_pnl_authority"] is False


def test_source_refuses_stamp_mismatch_duplicate_sessions_and_tampering():
    selection, plan, handoff = make_inputs()
    bad = records()
    bad[1]["updated_at_utc"] = "2022-03-04T21:00:00+00:00"
    with pytest.raises(ObservedOptionTimelineError, match="timing"):
        build_observed_option_timeline(
            selection, plan, handoff,
            read_verified_observations=lambda *_: bad,
            expected_original_cases=2,
        )
    bad = records()
    bad[2]["day"] = date(2022, 3, 3)
    bad[2]["updated_at_utc"] = "2022-03-03T22:00:00+00:00"
    with pytest.raises(ObservedOptionTimelineError, match="duplicate"):
        build_observed_option_timeline(
            selection, plan, handoff,
            read_verified_observations=lambda *_: bad,
            expected_original_cases=2,
        )
    wrong = dict(handoff, provider_requests=1)
    with pytest.raises(ValueError, match="fingerprint"):
        build_observed_option_timeline(
            selection, plan, wrong,
            read_verified_observations=lambda *_: pytest.fail("must not read"),
            expected_original_cases=2,
        )


def test_missing_exact_source_never_invokes_reader_and_prior_work_immutable(tmp_path):
    selection, plan, handoff = make_inputs()
    slots = handoff["rows"]
    for row in slots:
        if row["quote_history_status"] == "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY":
            row["quote_history_status"] = "QUOTE_HISTORY_NOT_ACQUIRED"
            row["quote_body_sha256"] = None
            row["quote_source_request_identity"] = None
            row["observed_quote_rows"] = None
    handoff = signed(
        {k: v for k, v in handoff.items() if k != "handoff_fingerprint"}
        | {"reused_original_2022_queries": 0},
        "handoff_fingerprint",
    )
    out = build_observed_option_timeline(
        selection, plan, handoff,
        read_verified_observations=lambda *_: pytest.fail("no raw read"),
        expected_original_cases=2,
    )
    assert out["unique_verified_physical_histories_decoded"] == 0
    settings = SimpleNamespace(
        assert_external_storage_binding=lambda c:
            None if c == "options" else pytest.fail("wrong D: category"),
        resolved_path=lambda path: tmp_path / path,
    )
    path, status = persist_observed_option_timeline(settings, out)
    assert status == "WRITTEN_IMMUTABLE_OBSERVED_TIMELINE"
    assert persist_observed_option_timeline(settings, out) == (
        path, "REUSED_IDENTICAL_OBSERVED_TIMELINE"
    )
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError):
        persist_observed_option_timeline(settings, out)

def test_covering_original_history_filters_older_rows_only_after_full_validation():
    """Original 2022 source can contain legitimate rows before selected demand."""
    selection, plan, handoff = make_inputs()
    plan["requests"][0]["from_inclusive"] = "2022-03-03"
    plan = signed(
        {k: v for k, v in plan.items() if k != "plan_fingerprint"},
        "plan_fingerprint",
    )
    handoff = signed(
        {k: v for k, v in handoff.items() if k != "handoff_fingerprint"}
        | {"quote_plan_fingerprint": plan["plan_fingerprint"]},
        "handoff_fingerprint",
    )
    calls = []
    def covering_reader(request, slot):
        calls.append(slot["quote_source_request_identity"])
        return records()  # first original row predates the narrower demand
    out = build_observed_option_timeline(
        selection, plan, handoff, read_verified_observations=covering_reader,
        expected_original_cases=2,
    )
    assert calls == ["c" * 64]
    valid = [r for r in out["rows"] if r["timeline_status"] ==
             "TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES"]
    assert len(valid) == 2
    assert all(r["first_later_observed_quote"]["session_et"] == "2022-03-03"
               for r in valid)
    bad = records()
    # Original source validity is checked before requested-range filtering:
    # a bad timestamp from the earlier covering period still fails closed.
    bad[0]["updated_at_utc"] = "2022-03-03T21:00:00+00:00"
    with pytest.raises(ObservedOptionTimelineError, match="timing"):
        build_observed_option_timeline(
            selection, plan, handoff,
            read_verified_observations=lambda *_: bad,
            expected_original_cases=2,
        )


def test_original_2022_full_series_can_cover_2023_exact_demand():
    """The three accepted 2023 memberships follow this original-source shape."""
    selection, plan, handoff = make_inputs()
    for c in selection["cases"]:
        c["option_symbol"] = c["option_symbol"].replace("220318", "230318")
        c["decision_at_utc"] = "2023-03-02T14:35:00+00:00"
        c["expiration"] = "2023-03-18"
    selection = signed(
        {k: v for k, v in selection.items() if k != "selection_fingerprint"},
        "selection_fingerprint",
    )
    for req in plan["requests"]:
        req["option_symbol"] = req["option_symbol"].replace("220318", "230318")
        req["from_inclusive"] = "2023-01-01"
        req["to_exclusive"] = "2023-03-19"
    plan = signed(
        {k: v for k, v in plan.items() if k != "plan_fingerprint"},
        "plan_fingerprint",
    )
    for row in handoff["rows"]:
        row["year"] = "2023"
        if row["option_symbol"]:
            row["option_symbol"] = row["option_symbol"].replace("220318", "230318")
    handoff = signed(
        {k: v for k, v in handoff.items() if k != "handoff_fingerprint"}
        | {"selection_fingerprint": selection["selection_fingerprint"],
           "quote_plan_fingerprint": plan["plan_fingerprint"]},
        "handoff_fingerprint",
    )
    source_rows = [
        source("2022-03-04", 1, 1.2),  # verified original, before requested year
        source("2023-03-02", 1, 1.2),  # decision-day EOD, not 09:35
        source("2023-03-03", 1.1, 1.3),
        source("2023-03-07", 0.8, 1.0),
    ]
    out = build_observed_option_timeline(
        selection, plan, handoff,
        read_verified_observations=lambda *_: source_rows,
        expected_original_cases=2,
    )
    assert out["unique_verified_physical_histories_decoded"] == 1
    assert out["by_year"]["2023"]["TWO_OR_MORE_LATER_TWO_SIDED_SOURCE_DATES"] == 2
    relevant = [r for r in out["rows"] if r["option_symbol"] ==
                "TEST230318C00100000"]
    assert len(relevant) == 2
    assert all(r["first_later_observed_quote"]["session_et"] == "2023-03-03"
               for r in relevant)
    assert out["provider_requests"] == 0 and out["account_pnl_authority"] is False
