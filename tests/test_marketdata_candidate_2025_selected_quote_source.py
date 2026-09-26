from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

import packages.data.marketdata_candidate_2025_exact_reference_v1 as ref
import packages.data.marketdata_candidate_2025_selected_quote_source_v1 as quote
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError

EASTERN = ZoneInfo("America/New_York")


def _case(tmp_path, monkeypatch):
    settings = SimpleNamespace(resolved_path=lambda value: tmp_path / value)
    rows = []
    for ticker, symbol in ref.FROZEN_SYMBOLS.items():
        if symbol is None:
            rows.append({"ticker": ticker, "opportunity_id": "op-FSLY", "source_status": "EXACT_QUERY_NO_DATA",
                         "provisional_nearest_atm_call": None, "structural_call_count": 0})
            continue
        _, expiry_str, strike = ref._symbol_terms(symbol)
        expiry = date.fromisoformat(expiry_str)
        snapshot = expiry - timedelta(days=21)
        first = snapshot + timedelta(days=1)
        decision = datetime.combine(first, time(9, 35), EASTERN).astimezone(UTC).isoformat()
        rows.append({
            "ticker": ticker, "opportunity_id": "op-" + ticker,
            "source_status": "COMPLETE_ORIGINAL_CHAIN", "provisional_nearest_atm_call": symbol,
            "ranked_structural_calls": [{"option_symbol": symbol}],
            "final_executable_option_contract_selected": False, "historical_quote_or_fill_price_validated": False,
            "expiration": expiry_str, "provisional_strike": strike,
            "chain_snapshot_date": snapshot.isoformat(), "source_chain_body_sha256": "a" * 64,
            "stock_decision_at_utc": decision, "quote_horizon_planning_only": {
                "from_inclusive": first.isoformat(), "to_exclusive": (expiry + timedelta(days=1)).isoformat(),
                "decision_is_intraday_0935_no_same_day_eod_entry_price": True,
            },
        })
    shortlist = {"shortlist_fingerprint": ref.FROZEN_SHORTLIST, "opportunities": rows}
    references = ref.build_exact_reference_plan(shortlist)
    monkeypatch.setattr(quote, "REFERENCE_PLAN_FINGERPRINT", references["plan_fingerprint"])
    monkeypatch.setattr(quote, "assert_reference_intact", lambda *a, **k: {
        "status": "COMPLETE_REFERENCE_RECEIPT", "classification": quote.REFERENCE_STATUS,
        "receipt_fingerprint": "b" * 64, "body_sha256": "c" * 64,
        "safe_terms": {"historical_standard_deliverable_verified": False,
                       "option_quote_or_fill_verified": False},
    })
    return settings, shortlist, references, quote.build_quote_plan(settings, shortlist, references)


def _response(ticket, *, symbol=None, day=None, volume=2):
    first = date.fromisoformat(ticket["from_inclusive"])
    stamp = int(datetime.combine(day or first, time(16), EASTERN).timestamp())
    return json.dumps({
        "s": "ok", "optionSymbol": [symbol or ticket["option_symbol"]], "updated": [stamp],
        "bid": [1.1], "ask": [1.3], "last": [1.2], "volume": [volume],
        "openInterest": [100], "underlyingPrice": [50.0], "iv": [None],
    }).encode()


def _headers(consumed=1, remaining=9000):
    return {"X-Api-Ratelimit-Consumed": str(consumed),
            "X-Api-Ratelimit-Remaining": str(remaining)}


def _run(settings, plan, *, transport, max_new=11):
    return quote.run_quote_source(
        settings, plan, authorize=True, confirm_paid=True, confirm_private_use=True,
        max_new_requests=max_new, token="SYNTHETIC_TOKEN", transport=transport,
        storage_guard=lambda *a, **kw: None,
    )


def test_exact_quote_plan_source_only(tmp_path, monkeypatch):
    settings, shortlist, references, plan = _case(tmp_path, monkeypatch)
    assert len(plan["requests"]) == 11 and plan["source_gap_excluded"] == "FSLY"
    assert all(x["to_exclusive"] == (date.fromisoformat(x["expiration"]) + timedelta(days=1)).isoformat()
               for x in plan["requests"])
    assert quote.write_plan(settings, plan, authorize=False)[0] == "PREVIEW_NO_WRITES"
    assert quote.write_plan(settings, plan, authorize=True)[0] == "WRITTEN_NEW_QUOTE_PLAN"
    assert quote.write_plan(settings, plan, authorize=True)[0] == "REUSED_EXACT_QUOTE_PLAN"
    assert quote.run_quote_source(settings, plan)["pending"] == 11


def test_bounded_batch_partial_resume_and_reuse(tmp_path, monkeypatch):
    settings, _, _, plan = _case(tmp_path, monkeypatch)
    calls = []
    def transport(ticket, token):
        assert token == "SYNTHETIC_TOKEN"
        calls.append(ticket["option_symbol"])
        return 200, _response(ticket), _headers(remaining=9000 - len(calls))
    first = _run(settings, plan, max_new=2, transport=transport)
    assert first["new_provider_attempts"] == 2 and first["pending"] == 9
    report = _run(settings, plan, transport=transport)
    assert report["new_provider_attempts"] == 9 and report["source_series"] == 11
    assert report["executable_option_prices"] == 0
    assert len(calls) == len(set(calls)) == 11
    cached = _run(settings, plan, transport=lambda *_: pytest.fail("must not replay"))
    assert cached["new_provider_attempts"] == 0 and cached["pending"] == 0


def test_exact_query_no_data_is_narrow_terminal_gap(tmp_path, monkeypatch):
    settings, _, _, plan = _case(tmp_path, monkeypatch)
    first = plan["requests"][0]["option_symbol"]
    def transport(ticket, token):
        if ticket["option_symbol"] == first:
            return 404, b'{"s":"no_data"}', _headers(0)
        return 200, _response(ticket), _headers()
    report = _run(settings, plan, transport=transport)
    assert report["source_series"] == 10 and report["exact_no_data_series"] == 1
    assert _run(settings, plan, transport=lambda *_: pytest.fail("no source-gap replay"))["exact_no_data_series"] == 1


def test_identity_quarantine_preserves_raw_no_retry(tmp_path, monkeypatch):
    settings, _, _, plan = _case(tmp_path, monkeypatch)
    ticket = plan["requests"][0]
    raw = _response(ticket, symbol="WRONG")
    with pytest.raises(CandidateChainCacheError, match="quarantined"):
        _run(settings, plan, transport=lambda *_: (200, raw, _headers()))
    paths = quote._paths(settings, ticket)
    assert paths[0].read_bytes() == raw and paths[2].is_file()
    assert json.loads(paths[1].read_text())["classification"] == "QUARANTINED_IDENTITY"
    with pytest.raises(CandidateChainCacheError, match="quarantine"):
        quote.run_quote_source(settings, plan)


def test_orphan_attempt_and_missing_headers_fail_closed(tmp_path, monkeypatch):
    settings, _, _, plan = _case(tmp_path, monkeypatch)
    with pytest.raises(CandidateChainCacheError, match="uncertain"):
        _run(settings, plan, transport=lambda *_: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(CandidateChainCacheError, match="unresolved"):
        quote.run_quote_source(settings, plan)
    settings2, _, _, plan2 = _case(tmp_path / "second", monkeypatch)
    ticket2 = plan2["requests"][0]
    with pytest.raises(CandidateChainCacheError, match="QUARANTINED_CREDIT_HEADERS"):
        _run(settings2, plan2, transport=lambda *_: (200, _response(ticket2), {}))


def test_authority_horizon_and_credit_floor(tmp_path, monkeypatch):
    settings, shortlist, refs, plan = _case(tmp_path, monkeypatch)
    with pytest.raises(CandidateChainCacheError, match="confirmations"):
        quote.run_quote_source(settings, plan, max_new_requests=11)
    with pytest.raises(CandidateChainCacheError, match="token"):
        quote.run_quote_source(settings, plan, authorize=True, confirm_paid=True,
                               confirm_private_use=True, max_new_requests=11)
    shortlist["opportunities"][0]["quote_horizon_planning_only"]["to_exclusive"] = "2027-01-01"
    with pytest.raises(CandidateChainCacheError, match="quote horizon"):
        quote.build_quote_plan(settings, shortlist, refs)
    calls = []
    def transport(ticket, token):
        calls.append(ticket["option_symbol"])
        return 200, _response(ticket), _headers(1, 199)
    report = _run(settings, plan, transport=transport)
    assert len(calls) == 1 and report["pending"] == 10


def test_frozen_date_boundary_and_mutated_plan(tmp_path, monkeypatch):
    settings, _, _, plan = _case(tmp_path, monkeypatch)
    ticket = plan["requests"][0]
    end = date.fromisoformat(ticket["to_exclusive"])
    assert quote._classify(ticket, 200, _response(ticket, day=end))[0] == "QUARANTINED_TIMESTAMP"
    plan["requests"][0]["option_symbol"] = "WRONG"
    with pytest.raises(CandidateChainCacheError, match="malformed"):
        quote.run_quote_source(settings, plan)
