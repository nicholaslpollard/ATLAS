from packages.data.marketdata_candidate_batch_plan_v1 import MAX_CHAIN_GROUPS


def test_additive_group_capacity():
    assert MAX_CHAIN_GROUPS >= 40

import pytest
import packages.data.marketdata_candidate_expansion_v1 as expansion
from packages.data.marketdata_candidate_batch_plan_v1 import plan_candidate_chain_batches
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _plan(n):
    return plan_candidate_chain_batches({
        "purpose": "SOURCE_ACQUISITION_ONLY",
        "opportunities": [{
            "opportunity_id": f"additive-{i:03d}", "ticker": f"X{i:03d}",
            "snapshot_date": "2022-03-17",
            "decision_at_utc": "2022-03-18T13:35:00+00:00",
            "raw_underlying_price": "100",
            "underlying_price_basis": "RAW_AS_TRADED",
            "expiration": "2022-04-14", "side": "call",
            "stock_source_sha256": "a" * 64,
        } for i in range(n)],
    })


def test_exact_forty_request_plan_uses_existing_ten_call_batches(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text("{}")
    calls = []

    def cache(settings, plan, **kw):
        prior = sum(calls)
        if not kw.get("max_new_requests"):
            return {"pending": 40 - prior, "planned_chain_requests": 40,
                    "reused": prior, "no_data_verified": 0}
        amount = kw["max_new_requests"]
        calls.append(amount)
        return {"status": "COMPLETE" if sum(calls) == 40 else "PARTIAL_RESUMABLE",
                "provider_reads": amount, "observed_credits_consumed_this_run": amount,
                "last_observed_provider_credits_remaining": 9000,
                "reused": prior, "new_complete": amount,
                "no_data_verified": 0, "pending": 40 - sum(calls)}

    monkeypatch.setattr(expansion, "_require_external", lambda _: None)
    result = expansion.run_expansion(
        object(), _plan(40), source, max_total_new_requests=40,
        authorize=True, paid=True, private=True, runner=cache,
    )
    assert calls == [10, 10, 10, 10]
    assert result["status"] == "COMPLETE"
    assert result["completed_chains"] == result["new_provider_attempts_this_invocation"] == 40
    assert source.read_text() == "{}"


def test_planner_upper_bound_250_uses_read_only_receipt_preview(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("{}")
    plan = _plan(MAX_CHAIN_GROUPS)
    report = expansion.run_expansion(
        object(), plan, source,
        runner=lambda *args, **kwargs: {
            "pending": MAX_CHAIN_GROUPS,
            "planned_chain_requests": MAX_CHAIN_GROUPS,
            "reused": 0, "no_data_verified": 0,
        },
    )
    assert report["planned_requests"] == MAX_CHAIN_GROUPS
    assert report["status"] == "PREVIEW_NO_PROVIDER_READS"


def test_251_groups_rejected_before_any_cache_call(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text("{}")
    plan = _plan(1)
    invalid = dict(plan, requests=[{}] * (MAX_CHAIN_GROUPS + 1))
    monkeypatch.setattr(expansion, "verify_candidate_plan", lambda _: invalid)
    with pytest.raises(CandidateChainCacheError, match="plan/source is not accepted"):
        expansion.run_expansion(
            object(), plan, source,
            runner=lambda *args, **kwargs: pytest.fail("cache must not run"),
        )


def test_original_monthly_export_guard_and_ten_call_cache_unchanged():
    assert expansion.MAX_PER_MONTH == 3
    assert expansion.MAX_TOTAL_NEW_REQUESTS == 50
    assert expansion.MAX_NEW_REQUESTS == 10
    assert MAX_CHAIN_GROUPS == 250
