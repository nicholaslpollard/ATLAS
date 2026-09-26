from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_candidate_2025_source_closeout_v1 as closeout
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _fixture(tmp_path, monkeypatch, *, gap_index=5):
    root = tmp_path / "local"
    root.mkdir()
    settings = SimpleNamespace(resolved_path=lambda path: root / path)
    requests = []
    bindings = {}
    bodies = {}
    for i in range(12):
        identifier = f"{i + 1:064x}"
        ticker = "FSLY" if i == gap_index else f"T{i}"
        opportunity_id = f"op-{i}"
        requests.append({
            "request_identity": identifier, "ticker": ticker,
            "params": {"date": "2025-01-02", "expiration": "2025-02-21", "strike": "1-2"},
            "opportunity_ids": [opportunity_id],
        })
        bindings[opportunity_id] = {
            "side": "call", "decision_at_utc": "2025-01-03T14:35:00+00:00",
            "stock_source_sha256": "a" * 64,
        }
        bodies[identifier] = root / (identifier + ".json")
        bodies[identifier].write_text(json.dumps({"s":"ok", "optionSymbol":[ticker+"250221C00001000"],
                              "side":["call"], "strike":[1]}))
    plan = {
        "plan_fingerprint": closeout.FROZEN_PLAN,
        "requests": requests, "source_bindings": bindings,
    }
    monkeypatch.setattr(closeout, "FROZEN_FSLY", requests[gap_index]["request_identity"])
    monkeypatch.setattr(closeout, "verify_candidate_plan", lambda v: v)
    monkeypatch.setattr(
        closeout, "run_candidate_chain_cache",
        lambda *_args: {
            "status": "PREVIEW", "provider_reads": 0, "reused": 11,
            "no_data_verified": 1, "pending": 0, "new_complete": 0,
            "request_results": [
                {"request_identity": req["request_identity"],
                 "status": "SOURCE_NO_DATA_VERIFIED" if i == gap_index else "REUSED_VERIFIED"}
                for i, req in enumerate(requests)
            ],
        },
    )
    monkeypatch.setattr(closeout, "_paths", lambda _settings, request_id:
                        SimpleNamespace(body=bodies[request_id]))
    monkeypatch.setattr(closeout, "array_rows", lambda v: tuple({
        "side": v["side"][0], "optionSymbol": v["optionSymbol"][0],
    } for _ in range(1)))
    monkeypatch.setattr(closeout, "_valid_receipt",
        lambda _paths, req, *, expected_plan_fingerprint:
        {
            "status": "VERIFIED_NO_DATA", "body_sha256": closeout.FROZEN_FSLY_BODY,
            "body_bytes": 47, "no_data_proof": closeout.FROZEN_FSLY_PROOF,
        } if req["ticker"] == "FSLY" else {
            "status": "COMPLETE", "body_sha256": "f" * 64,
            "body_bytes": 99, "row_count": 1, "rate_limit": {"consumed": 1},
        })
    return settings, plan, bodies


def test_frozen_closeout_eleven_one_zero_source_only(tmp_path, monkeypatch):
    settings, plan, bodies = _fixture(tmp_path, monkeypatch)
    before = {key: path.read_bytes() for key, path in bodies.items()}
    result = closeout.build_source_closeout(settings, plan, source_sha256="a" * 64)
    assert result["status"] == "COMPLETE_WITH_SOURCE_GAPS"
    assert result["verified_complete_chains"] == 11
    assert result["exact_query_no_data"] == 1 and result["pending"] == 0
    assert result["provider_reported_credits_consumed_by_complete_receipts"] == 11
    assert result["requests"][5]["status"] == "SOURCE_NO_DATA_VERIFIED"
    assert result["opportunities"][0]["final_contract_selected"] is False
    assert before == {key: path.read_bytes() for key, path in bodies.items()}


def test_local_closeout_no_write_default_and_exclusive_idempotent(tmp_path, monkeypatch):
    settings, plan, _ = _fixture(tmp_path, monkeypatch)
    report = closeout.build_source_closeout(settings, plan, source_sha256="a" * 64)
    status, path = closeout.write_local_closeout(settings, report)
    assert status == "PREVIEW_NO_WRITES" and not path.exists()
    status, path = closeout.write_local_closeout(settings, report, authorize_local_write=True)
    assert status == "WRITTEN_AND_REVERIFIED"
    original = path.read_bytes()
    status, _ = closeout.write_local_closeout(settings, report, authorize_local_write=True)
    assert status == "REUSED_EXACT_LOCAL_CLOSEOUT"
    changed = dict(report, pending=1)
    with pytest.raises(CandidateChainCacheError, match="differs"):
        closeout.write_local_closeout(settings, changed, authorize_local_write=True)
    assert path.read_bytes() == original


def test_wrong_gap_identity_fails_closed(tmp_path, monkeypatch):
    settings, plan, _ = _fixture(tmp_path, monkeypatch, gap_index=4)
    monkeypatch.setattr(closeout, "FROZEN_FSLY", "f" * 64)
    with pytest.raises(CandidateChainCacheError, match="accepted FSLY proof"):
        closeout.build_source_closeout(settings, plan, source_sha256="a" * 64)


def test_incomplete_preview_never_reads_or_writes_raw(tmp_path, monkeypatch):
    settings, plan, bodies = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(closeout, "run_candidate_chain_cache",
                        lambda *_args: {"status": "PREVIEW", "provider_reads": 0,
                                        "reused": 10, "no_data_verified": 1,
                                        "pending": 1, "new_complete": 0,
                                        "request_results": []})
    with pytest.raises(CandidateChainCacheError, match="requires 11 verified"):
        closeout.build_source_closeout(settings, plan, source_sha256="a" * 64)
    assert all(path.is_file() for path in bodies.values())
