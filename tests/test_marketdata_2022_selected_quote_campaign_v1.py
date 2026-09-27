from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_2022_selected_quote_campaign_v1 as q
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
from packages.providers.marketdata_app.client import MarketDataResponse


def _fixture(tmp_path, *, status=200):
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    chain_body = tmp_path / "chain.json"
    chain = {
        "s": "ok", "optionSymbol": [
            "ABC220318C00095000", "ABC220318C00100000",
            "ABC220318C00105000", "ABC220318P00100000"],
        "side": ["call", "call", "call", "put"],
        "strike": [95, 100, 105, 100],
    }
    chain_body.write_text(json.dumps(chain))
    source_file = tmp_path / "source.json"
    source = {
        "year": 2022, "shard_index": 0,
        "global": "x", "protected_master_return_rows_read": 0,
        "original_prior_plan_fingerprint": "old-plan",
        "all_additive_query_keys_fingerprint": "a" * 64,
        "chosen_key_member_ids": [{
            "ticker": "ABC", "snapshot_date": "2022-01-03",
            "expiration": "2022-03-18",
            "all_accepted_member_ids": ["test-1", "test-1-alt-policy"],
        }],
        "rows": [
            {"opportunity_id": "test-1", "ticker": "ABC", "snapshot_date": "2022-01-03",
             "expiration": "2022-03-18", "raw_underlying_price": "100"},
        ],
    }
    source_file.write_text(json.dumps(source))
    digest = q._sha(source_file)
    request = {"request_identity": "b" * 64, "ticker": "ABC",
               "params": {"date": "2022-01-03", "expiration": "2022-03-18"},
               "opportunity_ids": ["test-1"]}
    plan = {
        "opportunities": 1, "shared_chain_requests": 1,
        "plan_fingerprint": "c" * 64, "requests": [request],
        "source_bindings": {"test-1": {
            "stock_source_sha256": digest, "raw_underlying_price": "100",
            "side": "call",
        }},
    }
    binding = {"source_sha256": digest}
    paths = SimpleNamespace(body=chain_body)
    monkey = {
        "preparer": lambda *a, **kw: (plan, source_file, binding, "REUSED"),
        "chain_paths": lambda *a, **kw: paths,
        "receipt": lambda *a, **kw: {"status": "COMPLETE", "body_sha256": "d" * 64},
    }
    return settings, monkey


def test_atm_selection_no_future_liquidity_and_otm_tie():
    rows = [
        {"optionSymbol": "ABC220318C00105000", "side": "call", "strike": 105, "volume": 9999},
        {"optionSymbol": "ABC220318C00095000", "side": "call", "strike": 95, "volume": 0},
        {"optionSymbol": "ABC220318C00100000", "side": "call", "strike": 100, "volume": 0},
        {"optionSymbol": "ABC220318P00100000", "side": "put", "strike": 100, "volume": 100},
    ]
    chosen = q._clean_call_candidates(tuple(rows), "100")
    assert [x["option_symbol"] for x in chosen] == [
        "ABC220318C00100000", "ABC220318C00105000", "ABC220318C00095000",
    ]
    tie = q._clean_call_candidates(tuple(rows), "102.5")
    assert tie[0]["option_symbol"] == "ABC220318C00105000"


def test_frozen_plan_uses_original_chain_receipt_and_three_exact_quote_series(tmp_path, monkeypatch):
    settings, fake = _fixture(tmp_path)
    monkeypatch.setattr(q, "chain_paths", fake["chain_paths"])
    monkeypatch.setattr(q, "intact_chain_receipt", fake["receipt"])
    plan = q.freeze_quote_plan(settings, last_shard_inclusive=0, preparer=fake["preparer"])
    assert plan["unique_exact_quote_series"] == 3
    assert plan["selected_candidate_memberships"] == 3
    assert plan["provider_reads_in_planning"] == 0
    assert {r["from_inclusive"] for r in plan["requests"]} == {"2022-01-01"}
    assert {r["to_exclusive"] for r in plan["requests"]} == {"2022-03-19"}
    assert all(len(r["source_shard_memberships"]) == 1 for r in plan["requests"])
    assert all(r["source_shard_memberships"][0]["all_accepted_same_key_opportunity_ids"] == ["test-1", "test-1-alt-policy"] for r in plan["requests"])


def _fake_quote_raw(symbol, *, s="ok"):
    if s != "ok":
        return b'{"s":"no_data"}'
    return json.dumps({
        "s": "ok", "optionSymbol": [symbol], "updated": [1645128000],
        "bid": [1.2], "ask": [1.4], "last": [1.3],
        "volume": [20], "openInterest": [50], "underlyingPrice": [100],
    }).encode()


def _bare_quote_plan(symbols):
    requests = []
    for sym in symbols:
        query = {"option_symbol": sym, "from_inclusive": "2022-01-01",
                 "to_exclusive": "2022-03-19"}
        requests.append({**query, "request_identity": q._fingerprint({
            "contract": q.CONTRACT, "query": query,
        }), "source_shard_memberships": [], "historical_eod_only": True})
    plan = {"contract": q.CONTRACT, "status": "SOURCE_ONLY_SELECTED_CALL_QUOTE_HISTORIES_FROZEN",
            "requests": requests, "unique_exact_quote_series": len(requests)}
    plan["plan_fingerprint"] = q._fingerprint(plan)
    return plan


def test_live_quote_cache_dedup_and_full_resume_at_zero_cost(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "_require_external", lambda *_: None)
    monkeypatch.setattr(q, "assert_category_acquisition_allowed", lambda *a, **kw: None)
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    plan = _bare_quote_plan(["ABC220318C00100000", "ABC220318C00105000"])
    called = []
    def transport(ticket, token):
        called.append(ticket["option_symbol"])
        return 203, _fake_quote_raw(ticket["option_symbol"]), {
            "X-Api-Ratelimit-Consumed": "1", "X-Api-Ratelimit-Remaining": str(9000-len(called)),
        }
    first = q.run_selected_quote_histories(
        settings, plan, max_new_requests=2, max_observed_credits=10, workers=2,
        authorize=True, paid=True, private=True, token="synthetic", transport=transport,
    )
    assert len(called) == 2 and first["complete_source_series"] == 2
    assert first["pending"] == 0 and first["observed_credits_this_invocation"] == 2
    second = q.run_selected_quote_histories(
        settings, plan, max_new_requests=2, max_observed_credits=10, workers=2,
        authorize=True, paid=True, private=True, token="synthetic",
        transport=lambda *a: pytest.fail("original receipt must never be re-requested"),
    )
    assert second["new_provider_attempts"] == 0 and second["pending"] == 0


def test_uncertain_quote_attempt_is_not_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "_require_external", lambda *_: None)
    monkeypatch.setattr(q, "assert_category_acquisition_allowed", lambda *a, **kw: None)
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    plan = _bare_quote_plan(["ABC220318C00100000"])
    def fail(ticket, token):
        raise TimeoutError("uncertain original")
    with pytest.raises(CandidateChainCacheError, match="uncertain/quarantined"):
        q.run_selected_quote_histories(
            settings, plan, max_new_requests=1, max_observed_credits=2,
            authorize=True, paid=True, private=True, token="synthetic", transport=fail,
        )
    with pytest.raises(CandidateChainCacheError, match="unresolved quote"):
        q.run_selected_quote_histories(
            settings, plan, max_new_requests=1, max_observed_credits=2,
            authorize=True, paid=True, private=True, token="synthetic",
            transport=lambda *a: pytest.fail("do not reissue ambiguous billable quote"),
        )


def test_no_data_quote_is_exactly_scoped_and_zero_credit(tmp_path, monkeypatch):
    monkeypatch.setattr(q, "_require_external", lambda *_: None)
    monkeypatch.setattr(q, "assert_category_acquisition_allowed", lambda *a, **kw: None)
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    plan = _bare_quote_plan(["ABC220318C00100000"])
    report = q.run_selected_quote_histories(
        settings, plan, max_new_requests=1, max_observed_credits=2,
        authorize=True, paid=True, private=True, token="synthetic",
        transport=lambda ticket, token: (404, _fake_quote_raw(ticket["option_symbol"], s="no_data"),
                                           {"X-Api-Ratelimit-Consumed":"0",
                                            "X-Api-Ratelimit-Remaining":"9000"}),
    )
    assert report["exact_source_gaps"] == 1 and report["complete_source_series"] == 0
    assert report["observed_credits_this_invocation"] == 0


def test_quote_campaign_rejects_missing_confirmation_before_any_provider_call(tmp_path, monkeypatch):
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    plan = _bare_quote_plan(["ABC220318C00100000"])
    with pytest.raises(CandidateChainCacheError, match="confirmations"):
        q.run_selected_quote_histories(settings, plan, max_new_requests=10, token="synthetic")
