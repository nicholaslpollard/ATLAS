from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_candidate_2025_exact_reference_v1 as ref
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _case(tmp_path):
    root = tmp_path / "private"
    root.mkdir()
    settings = SimpleNamespace(
        resolved_path=lambda path: root / path,
        massive=SimpleNamespace(provider=SimpleNamespace(
            rest_base_url="https://api.massive.test",
        )),
        data=SimpleNamespace(research=SimpleNamespace(options=SimpleNamespace(
            reference_endpoint_path="/v3/reference/options/contracts",
        ))),
    )
    rows = []
    for ticker, symbol in ref.FROZEN_SYMBOLS.items():
        if symbol is None:
            rows.append({
                "ticker": ticker, "opportunity_id": "op-FSLY",
                "source_status": "EXACT_QUERY_NO_DATA",
                "provisional_nearest_atm_call": None, "structural_call_count": 0,
            })
            continue
        _, expiry, strike = ref._symbol_terms(symbol)
        rows.append({
            "ticker": ticker, "opportunity_id": "op-" + ticker,
            "source_status": "COMPLETE_ORIGINAL_CHAIN",
            "provisional_nearest_atm_call": symbol,
            "ranked_structural_calls": [{"option_symbol": symbol}],
            "final_executable_option_contract_selected": False,
            "historical_quote_or_fill_price_validated": False,
            "expiration": expiry, "provisional_strike": strike,
            "chain_snapshot_date": "2025-01-02",
            "source_chain_body_sha256": "a" * 64,
        })
    shortlist = {"shortlist_fingerprint": ref.FROZEN_SHORTLIST, "opportunities": rows}
    return settings, shortlist, ref.build_exact_reference_plan(shortlist)


def _response(ticket, *, shares=100, extra=None, symbol=None):
    return json.dumps({"status": "OK", "results": {
        "ticker": symbol or ticket["massive_ticker"],
        "underlying_ticker": ticket["ticker"],
        "contract_type": "call", "expiration_date": ticket["expiration"],
        "strike_price": float(ticket["strike"]),
        "exercise_style": "american",
        "shares_per_contract": shares,
        "additional_underlyings": extra, "cfi": "OCASPS",
    }}).encode("utf-8")


def test_exact_plan_uses_eleven_real_frozen_symbols_and_pit_snapshot(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    assert len(plan["requests"]) == 11
    assert len(plan["source_gap_exclusions"]) == 1
    assert plan["source_gap_exclusions"][0]["ticker"] == "FSLY"
    assert all(item["as_of"] == "2025-01-02" for item in plan["requests"])
    assert {x["option_symbol"] for x in plan["requests"]} == {
        s for s in ref.FROZEN_SYMBOLS.values() if s is not None
    }
    assert len({x["request_identity"] for x in plan["requests"]}) == 11
    assert ref.run_reference_dossiers(settings, plan)["pending"] == 11
    assert ref.run_reference_dossiers(settings, plan)["new_provider_attempts_this_run"] == 0
    action, file_path = ref.write_reference_plan(settings, plan)
    assert action == "WRITTEN_NEW_REFERENCE_PLAN"
    assert ref.write_reference_plan(settings, plan)[0] == "REUSED_EXACT_REFERENCE_PLAN"
    assert file_path.is_file()


def test_single_worker_exact_pit_reference_reads_and_no_repeat(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    mapping = {x["massive_ticker"]: x for x in plan["requests"]}
    starts = []
    sleeps = []
    def transport(url, api_key):
        assert api_key == "TEST_KEY"
        parsed = urllib.parse.urlsplit(url)
        assert parsed.scheme == "https" and parsed.netloc == "api.massive.test"
        ticker = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
        ticket = mapping[ticker]
        assert urllib.parse.parse_qs(parsed.query) == {"as_of": [ticket["as_of"]]}
        starts.append(ticket["ticker"])
        return 200, _response(ticket)
    report = ref.run_reference_dossiers(
        settings, plan, authorize_provider_reads=True, confirm_reference_only=True,
        max_new_requests=11, api_key="TEST_KEY", transport=transport,
        sleeper=lambda seconds: sleeps.append(seconds), monotonic=lambda: 0,
    )
    assert report["status"] == "SOURCE_REFERENCE_RECEIPTS_COMPLETE"
    assert report["new_provider_attempts_this_run"] == 11
    assert report["pending"] == 0
    assert report["independent_deliverable_verified"] == 0
    assert report["final_executable_contracts"] == 0
    assert len(starts) == 11 and len(sleeps) == 10
    assert all(x >= 13 for x in sleeps)
    assert all(x["status"] == "PIT_REFERENCE_TERMS_CONSISTENT_DELIVERABLE_UNVERIFIED"
               for x in report["results"])
    cached = ref.run_reference_dossiers(
        settings, plan, authorize_provider_reads=True, confirm_reference_only=True,
        max_new_requests=11, api_key="TEST_KEY",
        transport=lambda *_: pytest.fail("historical request must never replay"),
    )
    assert cached["previous_receipts_reused"] == 11
    assert cached["new_provider_attempts_this_run"] == 0


def test_adjusted_deliverable_stays_blocked_even_when_identity_matches(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    ticket = plan["requests"][0]
    classification, terms = ref._classify_reference(
        ticket, _response(ticket, shares=10, extra=[{"ticker":"XYZ", "amount":1}]), 200,
    )
    assert classification == "HISTORICAL_TERMS_ADJUSTED_OR_AMBIGUOUS"
    assert terms["historical_standard_deliverable_verified"] is False
    assert terms["option_quote_or_fill_verified"] is False
    assert terms["additional_underlyings"] == "PRESENT_OR_AMBIGUOUS"


def test_mismatched_reference_identity_is_quarantined_and_preserved(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    ticket = plan["requests"][0]
    with pytest.raises(CandidateChainCacheError, match="quarantined"):
        ref.run_reference_dossiers(
            settings, plan, authorize_provider_reads=True, confirm_reference_only=True,
            max_new_requests=11, api_key="TEST_KEY",
            transport=lambda *_: (200, _response(ticket, symbol="O:NOT_THE_TICKER")),
        )
    body, receipt, attempt = ref._paths(settings, ticket)
    before = tuple(x.read_bytes() for x in (body, receipt, attempt))
    assert json.loads(receipt.read_text())["status"] == "QUARANTINED_REVIEW_REQUIRED"
    with pytest.raises(CandidateChainCacheError, match="quarantine"):
        ref.run_reference_dossiers(
            settings, plan, authorize_provider_reads=True, confirm_reference_only=True,
            max_new_requests=11, api_key="TEST_KEY",
            transport=lambda *_: pytest.fail("quarantine must not replay"),
        )
    assert before == tuple(x.read_bytes() for x in (body, receipt, attempt))


def test_http_404_preserved_and_not_interpreted_as_historical_absence(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    ticket = plan["requests"][0]
    with pytest.raises(CandidateChainCacheError, match="HTTP_NON_200_REVIEW_REQUIRED"):
        ref.run_reference_dossiers(
            settings, plan, authorize_provider_reads=True, confirm_reference_only=True,
            max_new_requests=11, api_key="TEST_KEY",
            transport=lambda *_: (404, b'{"status":"NOT_FOUND"}'),
        )
    body, receipt, attempt = ref._paths(settings, ticket)
    assert body.read_bytes() == b'{"status":"NOT_FOUND"}'
    assert json.loads(receipt.read_text())["status"] == "QUARANTINED_REVIEW_REQUIRED"
    assert attempt.is_file()


def test_orphaned_attempt_and_tampered_raw_fail_closed(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    ticket = plan["requests"][0]
    with pytest.raises(CandidateChainCacheError, match="transport failed"):
        ref.run_reference_dossiers(
            settings, plan, authorize_provider_reads=True, confirm_reference_only=True,
            max_new_requests=11, api_key="TEST_KEY",
            transport=lambda *_: (_ for _ in ()).throw(TimeoutError("opaque")),
        )
    body, receipt, attempt = ref._paths(settings, ticket)
    assert attempt.is_file() and not body.exists() and not receipt.exists()
    with pytest.raises(CandidateChainCacheError, match="unresolved original reference attempt"):
        ref.run_reference_dossiers(settings, plan)
    assert not body.exists()


def test_no_credentials_or_explicit_authority_blocks_before_intent(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    ticket = plan["requests"][0]
    with pytest.raises(CandidateChainCacheError, match="authorization"):
        ref.run_reference_dossiers(settings, plan, max_new_requests=11)
    with pytest.raises(CandidateChainCacheError, match="credential missing"):
        ref.run_reference_dossiers(
            settings, plan, authorize_provider_reads=True,
            confirm_reference_only=True, max_new_requests=11, api_key="",
        )
    assert not any(x.exists() for x in ref._paths(settings, ticket))


def test_modified_frozen_symbol_cannot_be_authorized(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    plan["requests"][0]["option_symbol"] = "X250221C00001000"
    plan["requests"][0]["request_identity"] = ref._fingerprint({
        k: v for k, v in plan["requests"][0].items() if k != "request_identity"
    })
    plan["plan_fingerprint"] = ref._fingerprint({
        k: v for k, v in plan.items() if k != "plan_fingerprint"
    })
    with pytest.raises(CandidateChainCacheError, match="malformed"):
        ref.run_reference_dossiers(settings, plan)


def test_frozen_shortlist_change_blocks_new_plan(tmp_path):
    settings, shortlist, plan = _case(tmp_path)
    shortlist["opportunities"][0]["provisional_nearest_atm_call"] = "OTHER"
    with pytest.raises(CandidateChainCacheError, match="frozen provisional"):
        ref.build_exact_reference_plan(shortlist)
