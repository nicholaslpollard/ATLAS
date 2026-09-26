from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.marketdata_candidate_expansion_v1 as exp
from packages.data.marketdata_candidate_batch_plan_v1 import plan_candidate_chain_batches
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _settings(root):
    return SimpleNamespace(resolved_path=lambda value: root / value)


def _source_case(tmp_path):
    settings = _settings(tmp_path)
    cohort_id = "a" * 16
    bundle = {
        "contract": exp.EXPORT_CONTRACT, "year": 2024, "per_month": 3,
        "protected_master_return_rows_read": 0,
        "authority": {"provider_reads": False},
        "rows": [{"opportunity_id": "s1"}],
    }
    content = (json.dumps(bundle, sort_keys=True, indent=2) + "\n").encode()
    digest = hashlib.sha256(content).hexdigest()
    path = settings.resolved_path(
        f"data/research/evidence/marketdata_candidate_stock_v1/{cohort_id}.json"
    )
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    plan = plan_candidate_chain_batches({
        "purpose": "SOURCE_ACQUISITION_ONLY",
        "opportunities": [{
            "opportunity_id": "s1", "ticker": "SPY", "snapshot_date": "2024-01-03",
            "decision_at_utc": "2024-01-04T14:35:00+00:00",
            "raw_underlying_price": "470", "underlying_price_basis": "RAW_AS_TRADED",
            "expiration": "2024-02-16", "side": "call",
            "stock_source_sha256": digest,
        }],
    })
    p = settings.resolved_path(
        f"data/options/manifests/marketdata_candidate_batch_plan_v1_{cohort_id}.json"
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan))
    exported = {
        "provider_reads": 0, "selected_opportunities": 1, "shared_chain_requests": 1,
        "cohort_identity": cohort_id, "stock_source_sha256": digest,
        "plan_fingerprint": plan["plan_fingerprint"],
    }
    return settings, plan, path, exported


def test_first_export_and_second_run_reuses_without_exporter(tmp_path):
    settings, expected, source, exported = _source_case(tmp_path)
    calls = []
    def exporter(*args, **kwargs):
        calls.append(kwargs)
        return exported
    plan, original, binding, action = exp.prepare_cohort(
        settings, year=2024, per_month=3, duckdb_threads=4, exporter=exporter,
    )
    assert plan == expected and source == original
    assert action == "EXPORTED_AND_BOUND_NEW_COHORT"
    again = exp.prepare_cohort(
        settings, year=2024, per_month=3, duckdb_threads=4,
        exporter=lambda *_a, **_k: pytest.fail("native raw verification should not repeat"),
    )
    assert again[3] == "REUSED_IMMUTABLE_EXPORTED_COHORT"
    assert len(calls) == 1 and calls[0]["year"] == 2024
    source.write_bytes(source.read_bytes() + b" ")
    with pytest.raises(CandidateChainCacheError, match="lineage changed"):
        exp.prepare_cohort(settings, year=2024, per_month=3, duckdb_threads=4)


def test_complete_acquisition_is_chunked_by_cache_limit(tmp_path, monkeypatch):
    settings, _, source, _ = _source_case(tmp_path)
    monkeypatch.setattr(exp, "_require_external", lambda *_: None)
    class Fake:
        completed = 0
        calls = []
        def __call__(self, *args, **kw):
            if not kw.get("max_new_requests"):
                return {
                    "plan_fingerprint": "dummy", "pending": 21 - self.completed,
                    "planned_chain_requests": 21, "reused": self.completed,
                    "no_data_verified": 0,
                }
            n = min(kw["max_new_requests"], 21 - self.completed)
            self.calls.append(n)
            self.completed += n
            return {
                "status": "COMPLETE" if self.completed == 21 else "PARTIAL_RESUMABLE",
                "provider_reads": n, "observed_credits_consumed_this_run": n,
                "last_observed_provider_credits_remaining": 9990 - self.completed,
                "reused": self.completed - n, "new_complete": n,
                "no_data_verified": 0, "pending": 21 - self.completed,
            }
    fake = Fake()
    plan = {"plan_fingerprint": "dummy", "requests": [{}] * 21}
    monkeypatch.setattr(exp, "verify_candidate_plan", lambda *_: plan)
    result = exp.run_expansion(settings, plan, source, max_total_new_requests=30,
                               authorize=True, paid=True, private=True, runner=fake)
    assert fake.calls == [10, 10, 1]
    assert result["status"] == "COMPLETE"
    assert result["new_provider_attempts_this_invocation"] == 21


def test_bounded_partial_and_confirmations(tmp_path, monkeypatch):
    settings, _, source, _ = _source_case(tmp_path)
    monkeypatch.setattr(exp, "_require_external", lambda *_: None)
    plan = {"plan_fingerprint": "dummy", "requests": [{}] * 21}
    monkeypatch.setattr(exp, "verify_candidate_plan", lambda *_: plan)
    calls = []
    def runner(*a, **k):
        live = k.get("max_new_requests", 0)
        if live:
            calls.append(live)
            return {"status": "PARTIAL_RESUMABLE", "provider_reads": live,
                    "observed_credits_consumed_this_run": live,
                    "last_observed_provider_credits_remaining": 9800,
                    "reused": len(calls) * 10 - 10, "new_complete": live,
                    "no_data_verified": 0, "pending": 11}
        return {"pending": 21, "planned_chain_requests": 21, "reused": 0, "no_data_verified": 0}
    with pytest.raises(CandidateChainCacheError, match="three"):
        exp.run_expansion(settings, plan, source, max_total_new_requests=10, runner=runner)
    result = exp.run_expansion(settings, plan, source, max_total_new_requests=10,
                               authorize=True, paid=True, private=True, runner=runner)
    assert calls == [10] and result["new_provider_attempts_this_invocation"] == 10
    assert result["status"] == "PARTIAL_BOUND_REACHED"


def test_preflight_rejects_internal_storage_before_paid_reads(monkeypatch):
    snapshot = SimpleNamespace(storage_mode="PROJECT_LOCAL", status="SAFE",
                               category_quota_gib={"options_candidate_cache": 120})
    monkeypatch.setattr(exp, "inspect_research_storage", lambda *_: snapshot)
    with pytest.raises(CandidateChainCacheError, match="secondary"):
        exp._require_external(object())


def test_classification_only_when_original_failure_proves_exact_404(tmp_path, monkeypatch):
    settings, _, source, _ = _source_case(tmp_path)
    plan = {"plan_fingerprint": "dummy", "requests": [{}]}
    monkeypatch.setattr(exp, "_require_external", lambda *_: None)
    monkeypatch.setattr(exp, "verify_candidate_plan", lambda *_: plan)
    failed = {
        "plan_fingerprint": "dummy", "status": "FAILED_REVIEW_REQUIRED",
        "provider_reads": 1, "observed_credits_consumed_this_run": 0,
        "last_observed_provider_credits_remaining": 9000, "quarantined": 1,
        "request_results": [{"request_identity": "x" * 64,
                             "status": "FAILED_REVIEW_REQUIRED",
                             "exception_type": "CandidateChainCacheError"}],
    }
    monkeypatch.setattr(exp, "_checkpoint", lambda *_: failed)
    counts = {"proved": False}
    def runner(*a, **k):
        if k.get("max_new_requests"):
            raise CandidateChainCacheError("original exact 404 quarantined")
        return {"pending": 0 if counts["proved"] else 1, "planned_chain_requests": 1,
                "reused": 0, "no_data_verified": 1 if counts["proved"] else 0}
    def handler(*args):
        counts["proved"] = True
        return "x" * 64
    result = exp.run_expansion(settings, plan, source, max_total_new_requests=2,
                               authorize=True, paid=True, private=True, classify_no_data=True,
                               runner=runner, no_data_handler=handler)
    assert result["status"] == "COMPLETE_WITH_EXACT_QUERY_GAPS"
    assert result["new_provider_attempts_this_invocation"] == 1
    assert result["new_offline_exact_gap_proofs"] == 1
    assert not result["no_selected_quotes_or_option_pnl_authority"] is False
    failed["request_results"][0]["exception_type"] = "TimeoutError"
    monkeypatch.setattr(exp, "_checkpoint", lambda *_: failed)
    with pytest.raises(CandidateChainCacheError, match="not a proven"):
        exp._offline_404_sidecar(settings, plan)
