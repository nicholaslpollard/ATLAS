from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from packages.core.settings import load_settings
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


def _settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    project = tmp_path / "project"
    project.mkdir()
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
        "stock_source_sha256": "a" * 64,
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
    return run_candidate_chain_cache(
        settings, plan, max_new_requests=1, provider_read=reader,
        authorize_provider_reads=True, confirm_paid_starter=True,
        confirm_private_internal_use=True, **extra,
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
