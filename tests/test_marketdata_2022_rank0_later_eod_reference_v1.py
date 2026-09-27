from __future__ import annotations

"""Synthetic no-provider test of accepted 2022 later-EOD price reference paths."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_2022_rank0_later_eod_reference_v1 as m
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint


def _fixture(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda name: None if name == "options"
            else pytest.fail("wrong binding"),
    )
    monkeypatch.setattr(m, "EXPECTED_OPPORTUNITIES", 2)
    monkeypatch.setattr(m, "EXPECTED_UNIQUE_RANK_ZERO", 1)
    monkeypatch.setattr(m, "EXPECTED_FULL_QUOTE_CORPUS", 2)
    ticket = {
        "option_symbol": "TEST220617C00010000",
        "request_identity": "a" * 64,
        "from_inclusive": "2022-01-01",
        "to_exclusive": "2022-06-18",
        "source_shard_memberships": [
            {"rank": 0, "shard_index": 0, "opportunity_id": "one"},
            {"rank": 0, "shard_index": 0, "opportunity_id": "two"},
        ],
    }
    alternate = {
        "option_symbol": "TEST220617C00011000",
        "request_identity": "b" * 64,
        "from_inclusive": "2022-01-01",
        "to_exclusive": "2022-06-18",
        "source_shard_memberships": [
            {"rank": 1, "shard_index": 0, "opportunity_id": "one"},
        ],
    }
    plan = {"requests": [ticket, alternate], "unique_exact_quote_series": 2}
    plan["plan_fingerprint"] = _fingerprint(plan)
    monkeypatch.setattr(m, "EXPECTED_PLAN", plan["plan_fingerprint"])
    plan_path = tmp_path / m.PLAN_REL / "through_shard_070.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps(plan))

    readiness = {
        "contract": m.READINESS_CONTRACT, "status": "RANKED_EOD_SCENARIO_READINESS_ONLY",
        "accepted_original_quote_plan": plan["plan_fingerprint"],
        "provider_requests": 0, "authority": m.READINESS_AUTHORITY,
        "rank_zero_opportunity_memberships": 2,
        "unique_rank_zero_quote_histories": 1,
        "context_only_no_fills_usable_quote_timestamp_or_pnl": True,
        "no_later_eod_observation": 1,
        "later_eod_without_two_sided_context": 0,
        "later_two_sided_eod_context_only": 1,
        "opportunities_with_two_or_more_later_two_sided_context_dates": 1,
        "rows": [
            {
                "shard_index": 0, "opportunity_id": "one", "ticker": "TEST",
                "option_symbol": ticket["option_symbol"], "structural_rank": 0,
                "source_signal_session": "2022-03-01",
                "stock_decision_session_et": "2022-03-02",
                "expiration": "2022-06-17",
                "original_exact_quote_request_identity": ticket["request_identity"],
                "future_eod_never_used_for_structural_selection": True,
                "classification": "LATER_TWO_SIDED_CONTEXT_ONLY",
                "first_later_two_sided_eod_context_session": "2022-03-03",
                "later_two_sided_eod_context_sessions": 2,
            },
            {
                "shard_index": 0, "opportunity_id": "two", "ticker": "TEST",
                "option_symbol": ticket["option_symbol"], "structural_rank": 0,
                "source_signal_session": "2022-03-07",
                "stock_decision_session_et": "2022-03-08",
                "expiration": "2022-06-17",
                "original_exact_quote_request_identity": ticket["request_identity"],
                "future_eod_never_used_for_structural_selection": True,
                "classification": "NO_LATER_EOD_OBSERVATION",
                "first_later_two_sided_eod_context_session": None,
                "later_two_sided_eod_context_sessions": 0,
            },
        ],
    }
    readiness["readiness_fingerprint"] = _fingerprint(readiness)
    monkeypatch.setattr(m, "EXPECTED_READINESS", readiness["readiness_fingerprint"])
    readiness_path = tmp_path / f"{m.READINESS_REL}_{m.EXPECTED_PLAN[:16]}.json"
    readiness_path.parent.mkdir(parents=True, exist_ok=True)
    readiness_path.write_text(json.dumps(readiness))

    def timestamp(day):
        return int(datetime(2022, 3, day, 21, tzinfo=UTC).timestamp())

    raw = json.dumps({
        "s": "ok", "optionSymbol": [ticket["option_symbol"]]*3,
        "updated": [timestamp(2), timestamp(3), timestamp(4)],
        "bid": [0.9, 1.0, 1.1],
        "ask": [1.1, 1.2, 1.3],
        "volume": [0, 12, 0],
    }).encode()
    seen = []
    def receipt(s, t):
        seen.append(t["request_identity"])
        assert s is settings and t["request_identity"] == ticket["request_identity"]
        return {"status": "COMPLETE_SOURCE_ONLY", "safe_summary": {"observed_rows": 3},
                "body_sha256": __import__("hashlib").sha256(raw).hexdigest()}

    def body(s, t):
        assert s is settings and t["request_identity"] == ticket["request_identity"]
        return raw

    kwargs = {"quote_reader": receipt, "raw_reader": body}
    return settings, kwargs, readiness_path, plan_path, seen


def test_hypothetical_reference_is_strictly_post_decision_and_retrospective(tmp_path, monkeypatch):
    s, kw, _, _, seen = _fixture(tmp_path, monkeypatch)
    events = []
    out = m.build_rank0_later_eod_reference(s, progress=events.append, **kw)
    assert out["status"] == "DESCRIPTIVE_LATER_EOD_REFERENCE_ONLY"
    assert out["structural_rank_zero_opportunities"] == 2
    assert out["unique_original_rank_zero_histories"] == 1
    assert out["entry_and_next_reference_available"] == 1
    assert out["no_later_two_sided_reference"] == 1
    assert out["entry_reference_only_no_subsequent_reference"] == 0
    assert out["entry_reference_with_positive_reported_volume"] == 1
    assert out["next_reference_with_positive_reported_volume"] == 0
    assert out["median_hypothetical_ask_to_next_bid_reference_fraction"] == "-0.083333"
    assert out["provider_requests"] == out["original_receipts_modified"] == 0
    assert out["authority"] == m.AUTHORITY
    assert seen == ["a"*64]
    assert events[-1]["provider_requests"] == 0
    one = next(x for x in out["rows"] if x["opportunity_id"] == "one")
    two = next(x for x in out["rows"] if x["opportunity_id"] == "two")
    assert one["first_later_two_sided_session"] == "2022-03-03"
    assert one["subsequent_two_sided_session"] == "2022-03-04"
    assert one["first_later_eod_ask_reference_per_share"] == "1.200000"
    assert one["subsequent_eod_bid_reference_per_share"] == "1.100000"
    assert one["hypothetical_ask_to_next_bid_reference_change_per_share"] == "-0.100000"
    assert one["calendar_days_between_observed_reference_sessions"] == 1
    assert two["reference_status"] == "NO_LATER_TWO_SIDED_REFERENCE"
    assert two["hypothetical_ask_to_next_bid_reference_fraction"] is None
    assert all(x["retrospective_not_executable_or_original_0935_fill"] for x in out["rows"])
    p, action = m.write_rank0_later_eod_reference(s, out)
    assert p.is_file() and action == "WRITTEN_NEW_DERIVED_REFERENCE"
    assert m.write_rank0_later_eod_reference(s, out)[1] == "REUSED_IDENTICAL_DERIVED_REFERENCE"
    assert m.build_rank0_later_eod_reference(s, **kw) == out


def test_immutable_output_and_plan_lineage_fail_closed(tmp_path, monkeypatch):
    s, kw, readiness_path, plan_path, _ = _fixture(tmp_path, monkeypatch)
    out = m.build_rank0_later_eod_reference(s, **kw)
    path, _ = m.write_rank0_later_eod_reference(s, out)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(CandidateChainCacheError, match="differs"):
        m.write_rank0_later_eod_reference(s, out)
    readiness = json.loads(readiness_path.read_text())
    readiness["rank_zero_opportunity_memberships"] = 3
    readiness_path.write_text(json.dumps(readiness))
    with pytest.raises(CandidateChainCacheError, match="ranked readiness changed"):
        m.build_rank0_later_eod_reference(s, **kw)
    readiness["rank_zero_opportunity_memberships"] = 2
    readiness_path.write_text(json.dumps(readiness))
    plan = json.loads(plan_path.read_text())
    plan["unique_exact_quote_series"] = 5
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(CandidateChainCacheError, match="quote plan differs"):
        m.build_rank0_later_eod_reference(s, **kw)


def test_missing_receipt_or_mismatched_readiness_never_chooses_alternate(tmp_path, monkeypatch):
    s, kw, readiness_path, _, seen = _fixture(tmp_path, monkeypatch)
    no_receipt = dict(kw, quote_reader=lambda *a: None)
    with pytest.raises(CandidateChainCacheError, match="receipt missing"):
        m.build_rank0_later_eod_reference(s, **no_receipt)

    accepted = m.build_rank0_later_eod_reference(s, **kw)
    assert accepted["unique_original_rank_zero_histories"] == 1
    assert seen == ["a" * 64]  # never choose the structurally alternate rank-one option
    readiness = json.loads(readiness_path.read_text())
    readiness["rows"][0]["first_later_two_sided_eod_context_session"] = "2022-03-04"
    readiness["readiness_fingerprint"] = _fingerprint({
        k: v for k, v in readiness.items() if k != "readiness_fingerprint"
    })
    monkeypatch.setattr(m, "EXPECTED_READINESS", readiness["readiness_fingerprint"])
    readiness_path.write_text(json.dumps(readiness))
    with pytest.raises(CandidateChainCacheError, match="first later source date differs"):
        m.build_rank0_later_eod_reference(s, **kw)


def test_enter_only_one_valid_later_quote_is_not_a_return(tmp_path, monkeypatch):
    s, kw, readiness_path, _, _ = _fixture(tmp_path, monkeypatch)
    readiness = json.loads(readiness_path.read_text())
    readiness["rows"][0]["later_two_sided_eod_context_sessions"] = 1
    readiness["later_two_sided_eod_context_only"] = 1
    readiness["opportunities_with_two_or_more_later_two_sided_context_dates"] = 0
    readiness["readiness_fingerprint"] = _fingerprint({
        k: v for k, v in readiness.items() if k != "readiness_fingerprint"
    })
    monkeypatch.setattr(m, "EXPECTED_READINESS", readiness["readiness_fingerprint"])
    readiness_path.write_text(json.dumps(readiness))
    def raw(s, ticket):
        return json.dumps({
            "s": "ok", "optionSymbol": [ticket["option_symbol"]]*3,
            "updated": [int(datetime(2022,3,d,21,tzinfo=UTC).timestamp()) for d in (2,3,4)],
            "bid": [0.9, 1.0, 0.0], "ask": [1.1, 1.2, 1.3],
            "volume": [0, 12, 0],
        }).encode()
    kw["raw_reader"] = raw
    output = m.build_rank0_later_eod_reference(s, **kw)
    assert output["entry_reference_only_no_subsequent_reference"] == 1
    assert output["median_hypothetical_ask_to_next_bid_reference_fraction"] is None
    assert all(r["hypothetical_ask_to_next_bid_reference_fraction"] is None for r in output["rows"])
