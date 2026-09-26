from __future__ import annotations

from types import SimpleNamespace

import pytest

import packages.data.marketdata_chain_campaign_v1 as campaign
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError


def _fake_preparer(settings, *, year, per_month, duckdb_threads):
    plan = {"plan_fingerprint": f"plan-{year}", "shared_chain_requests": 35}
    binding = {"year": year, "cohort_id": "c" * 16,
               "source_sha256": "f" * 64, "binding_fingerprint": "e" * 64}
    return plan, object(), binding, "EXPORTED_AND_BOUND_NEW_COHORT"


def test_2024_five_pending_then_2023_and_2022_share_single_budget(monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda _: None)
    called = []
    pending = {2024: 5, 2023: 35, 2022: 35}
    events = []
    def runner(settings, plan, source, *, max_total_new_requests, max_observed_credits,
               authorize, paid, private, classify_no_data, progress):
        year = int(plan["plan_fingerprint"].split("-")[1])
        take = min(max_total_new_requests, pending[year])
        pending[year] -= take
        called.append((year, max_total_new_requests, max_observed_credits, take))
        if progress:
            progress({"stage": "RUNNING", "attempts": take})
        return {"status": "COMPLETE_WITH_EXACT_QUERY_GAPS" if year == 2024 else "COMPLETE"
                if pending[year] == 0 else "PARTIAL_BOUND_REACHED",
                "completed_chains": 35-pending[year]-(1 if year == 2024 else 0),
                "proven_exact_query_gaps": 1 if year == 2024 else 0,
                "pending": pending[year], "new_provider_attempts_this_invocation": take,
                "observed_provider_credits_this_invocation": take}
    out = campaign.run_chain_campaign(
        object(), max_total_new_requests=60, max_observed_credits=80,
        authorize=True, paid=True, private=True, classify_no_data=True,
        preparer=_fake_preparer, runner=runner, progress=events.append,
    )
    assert [x[0] for x in called] == [2024, 2023, 2022]
    assert [x[3] for x in called] == [5, 35, 20]
    assert out["new_provider_attempts"] == 60 and out["observed_credits"] == 60
    assert out["completed_years"] == [2024, 2023]
    assert out["status"] == "PARTIAL_CAMPAIGN_BUDGET"
    assert out["year_reports"][-1]["pending"] == 15
    assert out["year_reports"][0]["proven_exact_query_gaps"] == 1
    assert events[0]["stage"] == "COHORT_START"


def test_no_new_export_after_year_with_pending_problem(monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda _: None)
    years = []
    def preparer(settings, *, year, per_month, duckdb_threads):
        years.append(year)
        return _fake_preparer(settings, year=year,
                              per_month=per_month, duckdb_threads=duckdb_threads)
    def runner(*args, **kwargs):
        return {"status": "PARTIAL_STORAGE_BLOCKED", "completed_chains": 20,
                "proven_exact_query_gaps": 0, "pending": 15,
                "new_provider_attempts_this_invocation": 3,
                "observed_provider_credits_this_invocation": 3}
    out = campaign.run_chain_campaign(
        object(), max_total_new_requests=60, authorize=True, paid=True, private=True,
        preparer=preparer, runner=runner,
    )
    assert years == [2024]
    assert out["status"] == "PARTIAL_COHORT_REQUIRES_REVIEW"
    assert out["new_provider_attempts"] == 3


def test_no_provider_authorization_and_scope_fail_before_work(monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda _: pytest.fail("should not reach preflight"))
    for kwargs in [
        {"years": (2025,)},
        {"years": (2024, 2024)},
        {"max_total_new_requests": 101},
        {"max_total_new_requests": 5, "authorize": True, "paid": True},
        {"max_total_new_requests": 0, "classify_no_data": True},
    ]:
        with pytest.raises(CandidateChainCacheError):
            campaign.run_chain_campaign(object(), **kwargs)


def test_preview_never_requests_provider_or_advances_after_pending(monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda _: None)
    count = []
    def runner(*args, **kwargs):
        count.append(kwargs["max_total_new_requests"])
        return {"status": "PREVIEW_NO_PROVIDER_READS", "completed_chains": 29,
                "proven_exact_query_gaps": 1, "pending": 5,
                "new_provider_attempts_this_invocation": 0,
                "observed_provider_credits_this_invocation": 0}
    result = campaign.run_chain_campaign(object(), preparer=_fake_preparer, runner=runner)
    assert count == [0]
    assert result["status"] == "PREVIEW_NO_PROVIDER_READS"
    assert result["year_reports"][0]["pending"] == 5


def test_provider_error_does_not_start_next_year(monkeypatch):
    monkeypatch.setattr(campaign, "_require_external", lambda _: None)
    years = []
    def preparer(settings, *, year, per_month, duckdb_threads):
        years.append(year)
        return _fake_preparer(settings, year=year,
                              per_month=per_month, duckdb_threads=duckdb_threads)
    def runner(*args, **kwargs):
        raise CandidateChainCacheError("unresolved paid attempt")
    with pytest.raises(CandidateChainCacheError, match="unresolved paid attempt"):
        campaign.run_chain_campaign(
            object(), max_total_new_requests=60,
            authorize=True, paid=True, private=True,
            preparer=preparer, runner=runner,
        )
    assert years == [2024]
