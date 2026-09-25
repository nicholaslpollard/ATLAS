from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.core.settings import load_settings
import packages.data.marketdata_candidate_chain_cache_v1 as cache_module
from packages.data.marketdata_candidate_batch_plan_v1 import plan_candidate_chain_batches
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CACHE_SUBDIR,
    CandidateChainCacheError,
    MAX_NEW_REQUESTS,
    _paths,
    run_candidate_chain_cache,
    verify_candidate_plan,
)
from packages.providers.marketdata_app import MarketDataResponse


ROOT = Path(__file__).resolve().parents[1]
SOURCE_BYTES = b"accepted DEVELOPMENT source fixture"
SOURCE_SHA = hashlib.sha256(SOURCE_BYTES).hexdigest()


def _settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    project = tmp_path / "project"
    project.mkdir()
    # CI Windows runner has less than ATLAS's 50-GiB production floor.
    # Mock only the external disk quota sensor, never relax runtime policy.
    monkeypatch.setattr(
        cache_module, "inspect_research_storage",
        lambda _settings: SimpleNamespace(status="SAFE", storage_mode="PROJECT_LOCAL"),
    )
    monkeypatch.setattr(
        cache_module, "assert_category_acquisition_allowed",
        lambda *_args, **_kwargs: None,
    )
    return load_settings(ROOT, "development").model_copy(update={"project_root": project})


def _plan(*, count: int = 1):
    rows = [{
        "opportunity_id": f"accepted-case-{index}",
        "ticker": "SPY",
        "snapshot_date": "2026-09-14",
        "decision_at_utc": "2026-09-15T13:30:00+00:00",
        "raw_underlying_price": "100.00",
        "underlying_price_basis": "RAW_AS_TRADED",
        "expiration": "2026-10-16",
        "side": "call" if index % 2 else "put",
        "stock_source_sha256": SOURCE_SHA,
    } for index in range(count)]
    return plan_candidate_chain_batches({
        "purpose": "SOURCE_ACQUISITION_ONLY", "opportunities": rows,
    })


def _response(*, headers: bool = True):
    payload = {
        "s": "ok",
        "optionSymbol": ["SPY261016C00100000"],
        "underlying": ["SPY"],
        "expiration": ["2026-10-16"],
        "side": ["call"],
        "strike": [100.0],
        "bid": [1.0],
        "ask": [1.2],
        "volume": [5],
        "openInterest": [10],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return MarketDataResponse(
        http_status=200, payload=payload,
        headers=(
            {"X-Api-Ratelimit-Remaining": "9965", "X-Api-Ratelimit-Consumed": "1"}
            if headers else {}
        ),
        response_bytes=len(raw), elapsed_seconds=0.01, raw_body=raw,
    )


def _authorized(settings, plan, reader, **extra):
    source = settings.project_root / "data/research/evidence/marketdata_candidate_stock_v1/source.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(SOURCE_BYTES)
    return run_candidate_chain_cache(
        settings, plan, max_new_requests=1, provider_read=reader,
        authorize_provider_reads=True, confirm_paid_starter=True,
        confirm_private_internal_use=True, stock_source_files=(source,), **extra,
    )


def test_preview_is_zero_provider_reads_and_no_cache_writes(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan(count=50)
    def prohibited(*_args):
        raise AssertionError("no provider read in preview")
    result = run_candidate_chain_cache(settings, plan, provider_read=prohibited)
    assert result["status"] == "PREVIEW"
    assert result["planned_chain_requests"] == 1
    assert result["pending"] == 1
    assert result["provider_reads"] == 0
    assert not settings.resolved_path(CACHE_SUBDIR).exists()


def test_live_requires_all_three_operator_gates(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    with pytest.raises(CandidateChainCacheError, match="explicit authorization"):
        run_candidate_chain_cache(settings, plan, max_new_requests=1)
    with pytest.raises(CandidateChainCacheError, match="positive max_new_requests"):
        run_candidate_chain_cache(settings, plan, authorize_provider_reads=True)


def test_recomputed_plan_catches_tampering(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    bad = deepcopy(plan)
    bad["requests"][0]["params"]["date"] = "2026-09-16"
    with pytest.raises(CandidateChainCacheError, match="does not match"):
        run_candidate_chain_cache(settings, bad)
    bad = deepcopy(plan)
    bad["source_bindings"]["accepted-case-0"]["stock_source_sha256"] = "b" * 64
    with pytest.raises(CandidateChainCacheError, match="does not match"):
        verify_candidate_plan(bad)


def test_exact_http_body_is_cached_then_hash_verified_and_reused(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan(count=50)
    response = _response()
    called = 0

    def reader(path, params):
        nonlocal called
        called += 1
        assert path == "options/chain/SPY/"
        assert set(params) == {"date", "expiration", "strike"}
        return response

    first = _authorized(settings, plan, reader)
    assert first["status"] == "COMPLETE"
    assert first["provider_reads"] == 1
    assert first["new_complete"] == 1
    assert first["no_quote_paths_or_option_pnl_authority"]
    request = plan["requests"][0]
    paths = _paths(settings, request["request_identity"])
    assert paths.body.read_bytes() == response.raw_body
    receipt = json.loads(paths.receipt.read_text())
    assert receipt["status"] == "COMPLETE"
    assert receipt["raw_http_body_exact"] is True
    assert receipt["no_execution_price_or_option_pnl_authority"] is True
    assert receipt["rate_limit"]["remaining"] == 9965

    second = _authorized(settings, plan, reader)
    assert second["provider_reads"] == 0
    assert second["reused"] == 1
    assert called == 1

    paths.body.write_bytes(paths.body.read_bytes() + b" ")
    with pytest.raises(CandidateChainCacheError, match="receipt/source mismatch"):
        _authorized(settings, plan, reader)
    assert called == 1


def test_partial_cache_cannot_be_silently_overwritten(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    paths = _paths(settings, plan["requests"][0]["request_identity"])
    paths.body.parent.mkdir(parents=True)
    paths.body.write_bytes(_response().raw_body)
    with pytest.raises(CandidateChainCacheError, match="partial chain cache"):
        _authorized(settings, plan, lambda *_args: _response())


def test_missing_credit_headers_quarantines_exact_source(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    with pytest.raises(CandidateChainCacheError, match="quarantined"):
        _authorized(settings, plan, lambda *_args: _response(headers=False))
    paths = _paths(settings, plan["requests"][0]["request_identity"])
    receipt = json.loads(paths.receipt.read_text())
    assert receipt["status"] == "QUARANTINED"
    assert receipt["failure"] == "required provider credit headers missing"
    with pytest.raises(CandidateChainCacheError, match="receipt/source mismatch"):
        _authorized(settings, plan, lambda *_args: _response())


def test_transport_must_provide_exact_raw_bytes(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    response = _response()
    no_raw = MarketDataResponse(
        http_status=response.http_status, payload=response.payload,
        headers=response.headers, response_bytes=response.response_bytes,
        elapsed_seconds=response.elapsed_seconds,
    )
    with pytest.raises(CandidateChainCacheError, match="exact raw HTTP"):
        _authorized(settings, plan, lambda *_args: no_raw)


def test_rejects_unbounded_call_count(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    with pytest.raises(CandidateChainCacheError, match=f"0..{MAX_NEW_REQUESTS}"):
        run_candidate_chain_cache(settings, _plan(), max_new_requests=MAX_NEW_REQUESTS + 1)


def test_live_source_hash_must_match_physical_file(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    file = settings.project_root / "data/research/evidence/marketdata_candidate_stock_v1/source.json"
    file.parent.mkdir(parents=True)
    file.write_bytes(b"wrong source")
    with pytest.raises(CandidateChainCacheError, match="does not match any declared"):
        run_candidate_chain_cache(
            settings, plan, max_new_requests=1,
            authorize_provider_reads=True,
            confirm_paid_starter=True,
            confirm_private_internal_use=True,
            stock_source_files=(file,),
            provider_read=lambda *_args: (_ for _ in ()).throw(
                AssertionError("provider call before source hash verification")
            ),
        )


def test_404_provider_body_is_quarantined_not_cached_as_success(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    raw = b'{"s":"no_data","errmsg":"not found"}'
    response = MarketDataResponse(
        http_status=404, payload=json.loads(raw), response_bytes=len(raw),
        elapsed_seconds=0.01, raw_body=raw,
        headers={"X-Api-Ratelimit-Remaining": "9960", "X-Api-Ratelimit-Consumed": "1"},
    )
    with pytest.raises(CandidateChainCacheError, match="quarantined"):
        _authorized(settings, plan, lambda *_args: response)
    paths = _paths(settings, plan["requests"][0]["request_identity"])
    assert paths.body.read_bytes() == raw
    assert json.loads(paths.receipt.read_text())["status"] == "QUARANTINED"


def test_actual_storage_gate_blocks_provider_when_below_minimum(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(
        cache_module, "inspect_research_storage",
        lambda _settings: SimpleNamespace(
            status="BLOCKED_MINIMUM_FREE_SPACE", storage_mode="PROJECT_LOCAL"
        ),
    )
    with pytest.raises(CandidateChainCacheError, match="minimum free-space"):
        _authorized(
            settings, _plan(),
            lambda *_args: (_ for _ in ()).throw(AssertionError("no API call permitted")),
        )


def test_run_checkpoint_and_exact_intent_exist_before_provider_call(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan(count=50)
    latest = settings.resolved_path(
        "data/options/manifests/"
        f"marketdata_candidate_chain_cache_v1_{plan['plan_fingerprint'][:16]}.json"
    )
    paths = _paths(settings, plan["requests"][0]["request_identity"])

    def reader(_endpoint, _params):
        assert paths.attempt.is_file()
        intent = json.loads(paths.attempt.read_text(encoding="utf-8"))
        assert intent["request_identity"] == plan["requests"][0]["request_identity"]
        checkpoint = json.loads(latest.read_text(encoding="utf-8"))
        assert checkpoint["status"] == "RUNNING"
        assert checkpoint["provider_reads"] == 1
        assert checkpoint["request_results"][-1]["status"] == "REQUEST_STARTED_CHARGE_UNKNOWN"
        assert Path(checkpoint["run_report_path"]).is_file()
        return _response()

    result = _authorized(settings, plan, reader)
    assert result["status"] == "COMPLETE"
    assert result["processed_requests"] == 1
    assert result["completed_chains"] == 1
    assert result["observed_credits_consumed_this_run"] == 1
    assert result["last_observed_provider_credits_remaining"] == 9965
    assert result["new_raw_bytes"] == len(_response().raw_body)
    assert result["elapsed_seconds"] >= 0
    assert result["request_results"][0]["status"] == "NEW_COMPLETE"
    assert result["report_fingerprint"] == cache_module._fingerprint({
        k: v for k, v in result.items() if k != "report_fingerprint"
    })
    persisted = json.loads(Path(result["run_report_path"]).read_text(encoding="utf-8"))
    assert persisted == result
    assert json.loads(latest.read_text(encoding="utf-8")) == result
    assert not latest.with_suffix(".lock").exists()

    second = _authorized(settings, plan, lambda *_args: (_ for _ in ()).throw(
        AssertionError("accepted source should be reused without another paid request")
    ))
    assert second["status"] == "COMPLETE"
    assert second["provider_reads"] == 0
    assert second["reused"] == 1
    assert second["verified_reused_bytes"] == len(_response().raw_body)
    assert paths.attempt.is_file()


def test_ambiguous_transport_failure_persists_and_never_auto_retries(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    calls = 0

    def uncertain(_endpoint, _params):
        nonlocal calls
        calls += 1
        raise TimeoutError("provider may have charged the request")

    with pytest.raises(TimeoutError):
        _authorized(settings, plan, uncertain)
    assert calls == 1
    request = plan["requests"][0]
    paths = _paths(settings, request["request_identity"])
    assert paths.attempt.is_file()
    assert not paths.body.exists()
    latest = settings.resolved_path(
        "data/options/manifests/"
        f"marketdata_candidate_chain_cache_v1_{plan['plan_fingerprint'][:16]}.json"
    )
    checkpoint = json.loads(latest.read_text(encoding="utf-8"))
    assert checkpoint["status"] == "FAILED_REVIEW_REQUIRED"
    assert checkpoint["provider_reads"] == 1
    assert checkpoint["credits_unknown_after_failed_request"] is True
    assert checkpoint["request_results"][-1]["exception_type"] == "TimeoutError"
    assert not latest.with_suffix(".lock").exists()
    with pytest.raises(CandidateChainCacheError, match="unresolved provider attempt"):
        _authorized(settings, plan, uncertain)
    assert calls == 1
    assert json.loads(Path(checkpoint["run_report_path"]).read_text()) == checkpoint


def test_existing_plan_lock_prevents_concurrent_spending(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    latest = settings.resolved_path(
        "data/options/manifests/"
        f"marketdata_candidate_chain_cache_v1_{plan['plan_fingerprint'][:16]}.json"
    )
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.with_suffix(".lock").write_text("another process", encoding="utf-8")
    with pytest.raises(CandidateChainCacheError, match="plan lock"):
        _authorized(settings, plan, lambda *_args: (_ for _ in ()).throw(
            AssertionError("concurrent reader must not be called")
        ))
    assert not _paths(settings, plan["requests"][0]["request_identity"]).attempt.exists()


def test_mismatched_provider_chain_identity_is_quarantined(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    baseline = _response()
    payload = dict(baseline.payload)
    payload["underlying"] = ["QQQ"]
    raw = json.dumps(payload, separators=(",", ":")).encode()
    response = MarketDataResponse(
        http_status=200, payload=payload, headers=baseline.headers,
        response_bytes=len(raw), elapsed_seconds=0.01, raw_body=raw,
    )
    with pytest.raises(CandidateChainCacheError, match="quarantined"):
        _authorized(settings, plan, lambda *_args: response)
    paths = _paths(settings, plan["requests"][0]["request_identity"])
    saved = json.loads(paths.receipt.read_text(encoding="utf-8"))
    assert saved["status"] == "QUARANTINED"
    assert saved["failure"] == "chain rows violate ticker, expiry, strike or identity envelope"
    assert paths.body.read_bytes() == raw


def test_storage_gate_is_tracked_without_calling_provider(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    def blocked(*_args, **_kwargs):
        raise cache_module.ResearchStorageError("test quota")
    monkeypatch.setattr(cache_module, "assert_category_acquisition_allowed", blocked)
    report = _authorized(settings, plan, lambda *_args: (_ for _ in ()).throw(
        AssertionError("storage guard must stop before a provider call")
    ))
    assert report["status"] == "PARTIAL_STORAGE_BLOCKED"
    assert report["provider_reads"] == 0
    assert report["pending"] == 1
    assert report["request_results"][0]["status"] == "BLOCKED_STORAGE"
    assert Path(report["run_report_path"]).is_file()


def test_preview_with_complete_receipt_still_never_writes_run_report(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch)
    plan = _plan()
    _authorized(settings, plan, lambda *_args: _response())
    latest = settings.resolved_path(
        "data/options/manifests/"
        f"marketdata_candidate_chain_cache_v1_{plan['plan_fingerprint'][:16]}.json"
    )
    before = latest.read_bytes()
    report = run_candidate_chain_cache(settings, plan, provider_read=lambda *_args: (
        _ for _ in ()
    ).throw(AssertionError("preview must not call API")))
    assert report["status"] == "PREVIEW"
    assert report["reused"] == 1
    assert report["verified_reused_bytes"] == len(_response().raw_body)
    assert latest.read_bytes() == before
