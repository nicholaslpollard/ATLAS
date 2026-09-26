from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError
import scripts.run_marketdata_candidate_2025_pilot as pilot


ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path, monkeypatch, *, include_source=True):
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    base = load_settings(ROOT, "development")
    # The test is scoped to the stable project-visible paths; production
    # binding validation remains owned by AtlasSettings.
    data = base.data.model_copy(update={
        "external_storage": base.data.external_storage.model_copy(update={"bindings": {}})
    })
    settings = base.model_copy(update={"project_root": project, "data": data})
    ids = [f"opportunity-{i}" for i in range(12)]
    bundle = {
        "contract": "atlas-marketdata-accepted-stock-candidate-export-v1",
        "rows": [{"opportunity_id": x} for x in ids],
    }
    source_bytes = (json.dumps(bundle, sort_keys=True) + "\n").encode()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    plan = {
        "plan_fingerprint": "a" * 64,
        "requests": [{"request_identity": "b" * 64, "ticker": "AGIO"}] +
                    [{"request_identity": f"{i:064x}", "ticker": f"T{i}"} for i in range(1, 12)],
        "source_bindings": {x: {"stock_source_sha256": source_sha} for x in ids},
    }
    plan["requests"][5]["ticker"] = "FSLY"
    plan_bytes = (json.dumps(plan, sort_keys=True) + "\n").encode()
    plan_path = settings.resolved_path(pilot.PLAN_REL)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_bytes(plan_bytes)
    source_path = settings.resolved_path(pilot.SOURCE_REL)
    if include_source:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(source_bytes)
    monkeypatch.setattr(pilot, "PLAN_FILE_SHA256", hashlib.sha256(plan_bytes).hexdigest())
    monkeypatch.setattr(pilot, "SOURCE_SHA256", source_sha)
    monkeypatch.setattr(pilot, "PLAN_FINGERPRINT", plan["plan_fingerprint"])
    monkeypatch.setattr(pilot, "AGIO_REQUEST_ID", plan["requests"][0]["request_identity"])
    monkeypatch.setattr(pilot, "FSLY_NO_DATA_REQUEST_ID", plan["requests"][5]["request_identity"])
    monkeypatch.setattr(pilot, "verify_candidate_plan", lambda x: x)
    return settings, plan, source_path


def _fake_preview(pilot_plan, reused):
    return {
        "status": "PREVIEW",
        "provider_reads": 0,
        "new_complete": 0,
        "quarantined": 0,
        "planned_chain_requests": 12,
        "reused": reused,
        "pending": 12 - reused,
        "request_results": [{
            "request_identity": pilot_plan["requests"][0]["request_identity"],
            "status": "REUSED_VERIFIED",
        }],
    }


def test_direct_junction_visible_source_path_is_used_without_recursive_discovery(tmp_path, monkeypatch):
    settings, plan, source = _fixture(tmp_path, monkeypatch)
    assert pilot.preflight(settings) == (plan, source)
    assert source == settings.resolved_path(pilot.SOURCE_REL)


def test_missing_bundle_blocks_before_any_provider_or_cache_calls(tmp_path, monkeypatch):
    settings, _plan, source = _fixture(tmp_path, monkeypatch, include_source=False)
    monkeypatch.setattr(
        pilot, "run_candidate_chain_cache",
        lambda *_args, **_kwargs: pytest.fail("no provider or cache call before source preflight"),
    )
    with pytest.raises(CandidateChainCacheError, match="exporter path"):
        pilot.run_pilot(settings, authorize_provider_reads=True,
                        confirm_paid_starter=True, confirm_private_internal_use=True)
    assert str(source) in str(source)


def test_wrong_source_bytes_fail_closed_before_paid_request(tmp_path, monkeypatch):
    settings, _plan, source = _fixture(tmp_path, monkeypatch)
    source.write_bytes(b"wrong")
    monkeypatch.setattr(
        pilot, "run_candidate_chain_cache",
        lambda *_args, **_kwargs: pytest.fail("no provider call"),
    )
    with pytest.raises(CandidateChainCacheError, match="bundle SHA mismatch"):
        pilot.run_pilot(settings, authorize_provider_reads=True,
                        confirm_paid_starter=True, confirm_private_internal_use=True)


def test_read_only_default_is_one_preview_and_no_paid_calls(tmp_path, monkeypatch):
    settings, plan, _source = _fixture(tmp_path, monkeypatch)
    calls = []
    def fake(_settings, _plan, **kwargs):
        calls.append(kwargs)
        return _fake_preview(plan, 1)
    monkeypatch.setattr(pilot, "run_candidate_chain_cache", fake)
    report = pilot.run_pilot(settings)
    assert report["pending"] == 11
    assert len(calls) == 1 and "max_new_requests" not in calls[0]


def test_guarded_10_plus_1_rechecks_receipts_without_checkpoint_assumptions(tmp_path, monkeypatch):
    settings, plan, source = _fixture(tmp_path, monkeypatch)
    calls = []
    reused = 1
    def fake(_settings, _plan, **kwargs):
        nonlocal reused
        n = kwargs.get("max_new_requests", 0)
        calls.append(n)
        if n:
            assert kwargs["stock_source_files"] == (source,)
            assert kwargs["authorize_provider_reads"]
            assert kwargs["confirm_paid_starter"]
            assert kwargs["confirm_private_internal_use"]
            result = {
                "status": "COMPLETE" if reused + n == 12 else "PARTIAL_RESUMABLE",
                "new_complete": n, "provider_reads": n,
                "credits_unknown_after_failed_request": False, "quarantined": 0,
            }
            reused += n
            return result
        return _fake_preview(plan, reused)
    monkeypatch.setattr(pilot, "run_candidate_chain_cache", fake)
    report = pilot.run_pilot(
        settings, authorize_provider_reads=True,
        confirm_paid_starter=True, confirm_private_internal_use=True,
    )
    assert calls == [0, 10, 0, 1, 0]
    assert report["reused"] == 12 and report["pending"] == 0


def test_bad_first_batch_never_starts_second_paid_batch(tmp_path, monkeypatch):
    settings, plan, _source = _fixture(tmp_path, monkeypatch)
    calls = []
    def fake(_settings, _plan, **kwargs):
        n = kwargs.get("max_new_requests", 0)
        calls.append(n)
        if not n:
            return _fake_preview(plan, 1)
        return {
            "status": "PARTIAL_CREDIT_FLOOR", "new_complete": 2,
            "provider_reads": 2, "credits_unknown_after_failed_request": False,
            "quarantined": 0,
        }
    monkeypatch.setattr(pilot, "run_candidate_chain_cache", fake)
    with pytest.raises(CandidateChainCacheError, match="continuation conditions"):
        pilot.run_pilot(settings, authorize_provider_reads=True,
                        confirm_paid_starter=True, confirm_private_internal_use=True)
    assert calls == [0, 10]


def test_incomplete_authority_and_oversized_budget_fail_before_preflight(tmp_path, monkeypatch):
    settings, _plan, _source = _fixture(tmp_path, monkeypatch)
    with pytest.raises(CandidateChainCacheError, match="three explicit"):
        pilot.run_pilot(settings, authorize_provider_reads=True)
    with pytest.raises(CandidateChainCacheError, match="1..11"):
        pilot.run_pilot(settings, max_total_new_requests=12)


def test_frozen_fsly_no_data_is_not_counted_as_a_complete_chain(tmp_path, monkeypatch):
    settings, plan, source = _fixture(tmp_path, monkeypatch)
    calls = []
    complete = 5
    def fake(_settings, _plan, **kwargs):
        nonlocal complete
        size = kwargs.get("max_new_requests", 0)
        calls.append(size)
        if size:
            assert size == 6
            assert kwargs["stock_source_files"] == (source,)
            complete += size
            return {
                "status": "COMPLETE_WITH_SOURCE_GAPS",
                "new_complete": size, "provider_reads": size,
                "credits_unknown_after_failed_request": False, "quarantined": 0,
            }
        return {
            "status": "PREVIEW", "provider_reads": 0, "new_complete": 0,
            "quarantined": 0, "planned_chain_requests": 12,
            "reused": complete, "no_data_verified": 1,
            "pending": 11 - complete,
            "request_results": [
                {"request_identity": plan["requests"][0]["request_identity"],
                 "status": "REUSED_VERIFIED"},
                *[{"request_identity": plan["requests"][i]["request_identity"],
                   "status": "PENDING"} for i in range(1, 5)],
                {"request_identity": plan["requests"][5]["request_identity"],
                 "status": "SOURCE_NO_DATA_VERIFIED"},
                *[{"request_identity": plan["requests"][i]["request_identity"],
                   "status": "PENDING"} for i in range(6, 12)],
            ],
        }
    monkeypatch.setattr(pilot, "run_candidate_chain_cache", fake)
    result = pilot.run_pilot(
        settings, authorize_provider_reads=True,
        confirm_paid_starter=True, confirm_private_internal_use=True,
    )
    assert calls == [0, 6, 0]
    assert result["reused"] == 11
    assert result["no_data_verified"] == 1
    assert result["pending"] == 0


def test_unrelated_no_data_proof_refuses_pilot_authorization(tmp_path, monkeypatch):
    settings, plan, _ = _fixture(tmp_path, monkeypatch)
    wrong = _fake_preview(plan, 5)
    wrong["pending"] = 6
    wrong["no_data_verified"] = 1
    wrong["request_results"] += [
        {"request_identity": plan["requests"][5]["request_identity"],
         "status": "REUSED_VERIFIED"}
    ]
    monkeypatch.setattr(pilot, "run_candidate_chain_cache", lambda *_a, **_k: wrong)
    with pytest.raises(CandidateChainCacheError, match="unexpected no-data"):
        pilot.run_pilot(
            settings, authorize_provider_reads=True,
            confirm_paid_starter=True, confirm_private_internal_use=True,
        )
