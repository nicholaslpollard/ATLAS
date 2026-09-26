from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_candidate_2025_structural_call_shortlist_v1 as mod
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint


def _case(tmp_path, monkeypatch, *, wrong_gap=False):
    root = tmp_path / "local"
    root.mkdir()
    settings = SimpleNamespace(resolved_path=lambda path: root / path)
    names = ("AGIO", "AMGN", "ATRC", "BANF", "DAKT", "FSLY",
             "ISRG", "LNT", "OLLI", "SRRK", "TEM", "TSLA")
    requests, bindings, orig_requests, orig_opps, bodies = [], {}, [], [], {}
    for i, ticker in enumerate(names):
        identity = f"{i+1:064x}"
        opportunity_id = f"op-{i:02d}"
        params = {"date": "2025-01-02", "expiration": "2025-02-21", "strike": "90-110"}
        requests.append({
            "request_identity": identity, "ticker": ticker, "params": params,
            "opportunity_ids": [opportunity_id],
        })
        bindings[opportunity_id] = {
            "side": "call", "decision_at_utc": "2025-01-03T14:35:00+00:00",
            "raw_underlying_price": "100", "stock_source_sha256": "a" * 64,
        }
        payload = {
            "s": "ok",
            "optionSymbol": [
                f"{ticker}250221C00095000", f"{ticker}250221C00105000",
                f"{ticker}250221P00100000",
            ],
            "side": ["call", "call", "put"],
            "strike": [95, 105, 100],
            "bid": [999, 0, 0],
            "ask": [999, 0, 0],
            "volume": [99999, 0, 0],
            "openInterest": [99999, 0, 0],
        }
        content = json.dumps(payload).encode()
        body_path = root / f"{identity}.json"
        body_path.write_bytes(content)
        body_sha = hashlib.sha256(content).hexdigest()
        bodies[identity] = body_path
        gap = i == (4 if wrong_gap else 5)
        orig_requests.append({
            "request_identity": identity, "ticker": ticker,
            "snapshot_date": params["date"], "expiration": params["expiration"],
            "strike_window": params["strike"], "opportunity_ids": [opportunity_id],
            "raw_body_sha256": mod.FROZEN_FSLY_BODY if gap else body_sha,
            "status": "SOURCE_NO_DATA_VERIFIED" if gap else "REUSED_VERIFIED",
            "row_count": 0 if gap else 3,
        })
        orig_opps.append({
            "opportunity_id": opportunity_id, "request_identity": identity,
            "requested_side": "call", "decision_at_utc": bindings[opportunity_id]["decision_at_utc"],
            "observed_same_side_rows": None if gap else 2,
        })
    plan = {"plan_fingerprint": mod.FROZEN_PLAN, "requests": requests, "source_bindings": bindings}
    closeout = {
        "closeout_fingerprint": mod.FROZEN_CLOSEOUT,
        "plan_fingerprint": mod.FROZEN_PLAN,
        "requests": orig_requests,
        "opportunities": orig_opps,
    }
    monkeypatch.setattr(mod, "verify_candidate_plan", lambda x: x)
    monkeypatch.setattr(mod, "_paths", lambda _settings, identifier:
                        SimpleNamespace(body=bodies[identifier]))
    def receipt(_paths, req, *, expected_plan_fingerprint):
        assert expected_plan_fingerprint == mod.FROZEN_PLAN
        idx = names.index(req["ticker"])
        gap = idx == (4 if wrong_gap else 5)
        return (
            {
                "status": "VERIFIED_NO_DATA", "body_sha256": mod.FROZEN_FSLY_BODY,
                "no_data_proof": mod.FROZEN_FSLY_PROOF,
            } if gap else {
                "status": "COMPLETE", "body_sha256": orig_requests[idx]["raw_body_sha256"],
                "row_count": 3,
            }
        )
    monkeypatch.setattr(mod, "_valid_receipt", receipt)
    if not wrong_gap:
        monkeypatch.setattr(mod, "FROZEN_FSLY", requests[5]["request_identity"])
    return settings, plan, closeout, bodies


def test_structural_rank_is_nearest_raw_open_and_tie_prefers_otm_without_quotes():
    rows = (
        {"side": "call", "optionSymbol": "A250221C00095000", "strike": 95,
         "bid": 999, "ask": 999, "volume": 999999, "openInterest": 999999},
        {"side": "put", "optionSymbol": "A250221P00100000", "strike": 100},
        {"side": "call", "optionSymbol": "A250221C00105000", "strike": 105,
         "bid": 0, "ask": 0, "volume": 0, "openInterest": 0},
    )
    from decimal import Decimal
    ranked = mod.rank_structural_calls(rows, Decimal("100"))
    assert [r["strike"] for r in ranked] == ["105", "95"]
    assert ranked[0]["call_moneyness_at_raw_open"] == "OTM"
    assert ranked[0]["standard_deliverable_independently_validated"] is False
    assert all("bid" not in r and "volume" not in r for r in ranked)


def test_exact_closed_cohort_generates_new_structural_shortlist(tmp_path, monkeypatch):
    settings, plan, closeout, bodies = _case(tmp_path, monkeypatch)
    originals = {name: path.read_bytes() for name, path in bodies.items()}
    result = mod.build_structural_call_shortlist(settings, plan, closeout)
    assert result["status"] == "PROVISIONAL_STRUCTURAL_SHORTLIST_ONLY"
    assert result["provisional_structural_symbols"] == 11
    assert result["source_call_rows_examined"] == 22
    assert result["complete_source_chains"] == 11
    assert result["exact_query_no_data"] == 1
    assert result["provider_reads"] == result["credits_consumed"] == 0
    fsly = next(x for x in result["opportunities"] if x["ticker"] == "FSLY")
    assert fsly["provisional_nearest_atm_call"] is None
    assert fsly["abstention_reason"] == "FSLY_EXACT_QUERY_NO_DATA"
    agio = next(x for x in result["opportunities"] if x["ticker"] == "AGIO")
    assert agio["provisional_nearest_atm_call"] == "AGIO250221C00105000"
    assert agio["quote_horizon_planning_only"] == {
        "from_inclusive": "2025-01-03", "to_exclusive": "2025-02-22",
        "decision_is_intraday_0935_no_same_day_eod_entry_price": True,
    }
    assert all(x["final_executable_option_contract_selected"] is False for x in result["opportunities"])
    assert originals == {name: path.read_bytes() for name, path in bodies.items()}


def test_wrong_source_gap_never_becomes_provisional_selection(tmp_path, monkeypatch):
    settings, plan, closeout, _ = _case(tmp_path, monkeypatch, wrong_gap=True)
    with pytest.raises(CandidateChainCacheError, match="unaccepted exact-query no-data"):
        mod.build_structural_call_shortlist(settings, plan, closeout)


def test_changed_raw_source_hash_fail_closed(tmp_path, monkeypatch):
    settings, plan, closeout, _ = _case(tmp_path, monkeypatch)
    closeout["requests"][1]["raw_body_sha256"] = "0" * 64
    with pytest.raises(CandidateChainCacheError, match="original chain receipt differs"):
        mod.build_structural_call_shortlist(settings, plan, closeout)


def test_same_session_eod_not_usable_for_0935_decision(tmp_path, monkeypatch):
    settings, plan, closeout, _ = _case(tmp_path, monkeypatch)
    plan["requests"][0]["params"]["date"] = "2025-01-03"
    closeout["requests"][0]["snapshot_date"] = "2025-01-03"
    with pytest.raises(CandidateChainCacheError, match="predate decision"):
        mod.build_structural_call_shortlist(settings, plan, closeout)


def test_manifest_write_single_new_file_is_idempotent_and_non_overwriting(tmp_path, monkeypatch):
    settings, plan, closeout, _ = _case(tmp_path, monkeypatch)
    result = mod.build_structural_call_shortlist(settings, plan, closeout)
    action, path = mod.write_local_shortlist(settings, result)
    assert action == "PREVIEW_NO_WRITES" and not path.exists()
    action, path = mod.write_local_shortlist(settings, result, authorize_local_write=True)
    assert action == "WRITTEN_AND_REVERIFIED"
    saved = path.read_bytes()
    action, _ = mod.write_local_shortlist(settings, result, authorize_local_write=True)
    assert action == "REUSED_EXACT_STRUCTURAL_SHORTLIST"
    with pytest.raises(CandidateChainCacheError, match="differs"):
        mod.write_local_shortlist(settings, dict(result, provider_reads=1),
                                  authorize_local_write=True)
    assert saved == path.read_bytes()


def test_existing_closeout_fingerprint_is_bound_without_rerunning_closeout(tmp_path, monkeypatch):
    settings, plan, closeout, _ = _case(tmp_path, monkeypatch)
    saved = {
        "contract": mod.CLOSEOUT_CONTRACT, "status": "COMPLETE_WITH_SOURCE_GAPS",
        "plan_fingerprint": mod.FROZEN_PLAN, "verified_complete_chains": 11,
        "exact_query_no_data": 1, "pending": 0, "verified_opportunities": 12,
        "requests": closeout["requests"], "opportunities": closeout["opportunities"],
    }
    saved["closeout_fingerprint"] = _fingerprint(saved)
    monkeypatch.setattr(mod, "FROZEN_CLOSEOUT", saved["closeout_fingerprint"])
    path = settings.resolved_path(mod.CLOSEOUT_REL)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(saved))
    assert mod.read_frozen_source_closeout(settings)["closeout_fingerprint"] == saved["closeout_fingerprint"]
    changed = dict(saved, pending=1)
    path.write_text(json.dumps(changed))
    with pytest.raises(CandidateChainCacheError, match="identity/status"):
        mod.read_frozen_source_closeout(settings)
