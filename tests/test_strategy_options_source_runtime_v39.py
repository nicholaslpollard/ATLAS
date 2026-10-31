from __future__ import annotations

import sqlite3

import pytest

from packages.data.options_on_demand_source_cache_v38 import (
    DB_REL,
)
from packages.data.options_on_demand_source_cache_v38 import (
    MIN_FREE_STORAGE_BYTES,
)
from packages.providers.thetadata.client import ThetaDataResponse, _canonical_bytes
from packages.simulation import strategy_options_source_runtime_v39 as runtime
from packages.data import options_on_demand_source_cache_v38 as cache


class LocalSettings:
    def __init__(self, root):
        self.root = root
        (root / "data/options").mkdir(parents=True, exist_ok=True)

    def resolved_path(self, relative):
        return self.root / relative

    def assert_external_storage_binding(self, name):
        assert name == "options"


def want(candidate, *, strike="600", purpose="entry"):
    return {
        "candidate_id": candidate,
        "purpose": purpose,
        "method": "option_at_time_quote",
        "kwargs": {
            "symbol": "SPY",
            "date_et": "2025-06-09",
            "expiration": "2025-06-20",
            "strike": strike,
            "right": "call",
            "time_of_day_et": "10:00:00.000",
        },
    }


def source():
    rows = ({"symbol": "SPY", "bid": 1.05, "ask": 1.25},)
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={}, response_bytes=len(raw),
        elapsed_seconds=0.02, raw_body=raw,
    )


def test_changed_strategy_parameters_fetch_and_reuse_all_exact_sources(tmp_path, monkeypatch):
    settings = LocalSettings(tmp_path)
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    calls = []
    observed = []

    def fetch(method, kwargs):
        calls.append((method, kwargs["strike"]))
        return source()

    def demands():
        yield want("SPY-20150609-strategy-A")
        yield want("SPY-20150609-strategy-A", purpose="exit-review")
        yield want("SPY-20150609-strategy-B", strike="605")

    a = runtime.resolve_strategy_source_demands(
        settings, "strategy_spy_revision_1", demands(),
        provider_call=fetch,
        on_source=lambda item, src: observed.append(src["status"]),
    )
    assert a["status"] == "ALL_REQUESTED_SOURCES_PRESENT"
    assert a["source_uses_requested"] == 3
    assert a["source_uses_resolved"] == 3
    assert a["provider_fetch_successes"] == 2
    assert a["provider_dispatch_attempts"] == 2
    assert a["persisted_cache_hits"] == 1
    assert calls == [
        ("option_at_time_quote", "600"), ("option_at_time_quote", "605")
    ]
    assert observed == ["FETCHED_AND_ARCHIVED", "CACHE_HIT", "FETCHED_AND_ARCHIVED"]
    b = runtime.resolve_strategy_source_demands(
        settings, "strategy_spy_revision_2", [want("new-candidate", strike="605")],
        provider_call=lambda *args: pytest.fail("same source must be reused"),
    )
    assert b["persisted_cache_hits"] == 1
    with sqlite3.connect(settings.resolved_path(DB_REL)) as db:
        assert db.execute("SELECT COUNT(*) FROM sources WHERE state='ARCHIVED'").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM strategy_source_uses").fetchone()[0] == 4
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_source_uses WHERE strategy_version=?",
            ("strategy_spy_revision_2",),
        ).fetchone()[0] == 1


def test_uncertain_failed_provider_does_not_retry_but_other_new_needs_fetch(tmp_path, monkeypatch):
    settings = LocalSettings(tmp_path)
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    original_calls = []

    def fail(method, kwargs):
        original_calls.append(kwargs["strike"])
        raise RuntimeError("private credentials must not appear")

    report = runtime.resolve_strategy_source_demands(
        settings, "rev_a", [want("case_1"), want("case_2", strike="605")],
        provider_call=fail, continue_on_error=True,
    )
    assert report["status"] == "SOURCE_REQUIREMENTS_UNRESOLVED_OR_NO_DATA"
    assert report["provider_dispatch_attempts"] == 2
    assert report["source_uses_ambiguous_current_dispatch"] == 2
    assert original_calls == ["600", "605"]
    with sqlite3.connect(settings.resolved_path(DB_REL)) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_source_uses "
            "WHERE status='SOURCE_DISPATCH_OUTCOME_UNKNOWN'"
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT COUNT(*) FROM sources WHERE state='FAILED_RETRYABLE'"
        ).fetchone()[0] == 2

    fresh_calls = []
    def fetch_fresh(method, kwargs):
        fresh_calls.append(kwargs["strike"])
        return source()

    again = runtime.resolve_strategy_source_demands(
        settings, "rev_b", [
            want("case_1"), want("case_2", strike="605"),
            want("new_demand", strike="610"),
        ], provider_call=fetch_fresh, continue_on_error=True,
    )
    assert again["source_uses_ambiguous_prior_dispatch"] == 2
    assert again["source_uses_resolved"] == 1
    assert again["provider_dispatch_attempts"] == 1
    assert fresh_calls == ["610"]
    with sqlite3.connect(settings.resolved_path(DB_REL)) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_source_uses "
            "WHERE status='SOURCE_RECONCILIATION_REQUIRED'"
        ).fetchone()[0] == 2


def test_prior_inflight_query_never_dispatches_and_is_retained(tmp_path):
    import json
    import time
    from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

    settings = LocalSettings(tmp_path)
    req = cache.normalize_source_requirement("option_at_time_quote", want("x")["kwargs"])
    qid = _fingerprint(req)
    with cache._connect(cache._database(settings)) as db:
        db.execute(
            "INSERT INTO sources(query_id,request_json,state,touched) "
            "VALUES (?,?,?,?)",
            (qid, json.dumps(req, sort_keys=True, separators=(",", ":")),
             "IN_FLIGHT", time.time() - 9999),
        )
    report = runtime.resolve_strategy_source_demands(
        settings, "new_revision", [want("x")], continue_on_error=True,
        provider_call=lambda *args: pytest.fail("ambiguous lease must not retry"),
    )
    assert report["source_uses_ambiguous_prior_dispatch"] == 1
    assert report["provider_dispatch_attempts"] == 0
    assert report["source_uses_failed_or_unresolved"] == 1


def test_all_supported_theta_options_source_types_are_requested_without_skipping(
    tmp_path, monkeypatch
):
    settings = LocalSettings(tmp_path)
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    calls = []
    base = {"symbol": "SPY", "date_et": "2025-06-09"}
    demands = [
        {"candidate_id": "option_chain_1", "purpose": "entry_quote",
         "method": "option_at_time_quote",
         "kwargs": {**base, "expiration": "2025-06-20", "strike": "600",
                    "right": "call", "time_of_day_et": "09:35:00.000"}},
        {"candidate_id": "option_chain_1", "purpose": "exact_tape",
         "method": "option_history_exact_quote_tape",
         "kwargs": {**base, "expiration": "2025-06-09", "strike": "600",
                    "right": "call", "start_time_et": "09:35:00.000",
                    "end_time_et": "15:30:00.000"}},
        {"candidate_id": "option_chain_1", "purpose": "option_surface",
         "method": "option_at_time_quote_surface",
         "kwargs": {**base, "time_of_day_et": "09:35:00.000", "right": "both",
                    "max_dte": 45}},
        {"candidate_id": "option_chain_1", "purpose": "hourly_tape",
         "method": "option_history_hourly_quote_surface",
         "kwargs": {**base, "right": "both", "max_dte": 45}},
        {"candidate_id": "option_chain_1", "purpose": "prior_open_interest",
         "method": "option_history_open_interest_surface",
         "kwargs": {**base, "right": "put", "max_dte": 45}},
        {"candidate_id": "option_chain_1", "purpose": "greeks",
         "method": "option_history_binomial_first_order_greeks_at_minute",
         "kwargs": {**base, "expiration": "2025-06-20", "right": "call",
                    "time_of_day_et": "09:35:00.000",
                    "annual_dividend": 0.01, "binomial_steps": 101}},
    ]
    def getter(method, kw):
        calls.append(method)
        return source()
    first = runtime.resolve_strategy_source_demands(
        settings, "version_all_source_types", iter(demands),
        provider_call=getter,
    )
    assert first["source_uses_requested"] == 6
    assert first["source_uses_resolved"] == 6
    assert first["provider_dispatch_attempts"] == 6
    assert set(calls) == cache.ALLOWED
    again = runtime.resolve_strategy_source_demands(
        settings, "different_version", iter(demands),
        provider_call=lambda *args: pytest.fail("all sources already archived"),
    )
    assert again["persisted_cache_hits"] == 6
    assert again["provider_dispatch_attempts"] == 0


def test_generator_can_discover_new_source_after_prior_source_arrives(tmp_path, monkeypatch):
    settings = LocalSettings(tmp_path)
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    findings = []

    def producer():
        yield want("initial_case")
        if findings and findings[0] == "FETCHED_AND_ARCHIVED":
            yield want("new_case", strike="610")

    result = runtime.resolve_strategy_source_demands(
        settings, "strategy_revision_dynamic", producer(),
        provider_call=lambda *args: source(),
        on_source=lambda item, src: findings.append(src["status"]),
    )
    assert findings == ["FETCHED_AND_ARCHIVED", "FETCHED_AND_ARCHIVED"]
    assert result["source_uses_requested"] == result["source_uses_resolved"] == 2
    assert result["provider_fetch_successes"] == 2


def test_invalid_requirement_fails_before_provider_request(tmp_path):
    settings = LocalSettings(tmp_path)
    with pytest.raises(runtime.StrategySourceRuntimeError, match="DEMAND_SHAPE_INVALID"):
        runtime.resolve_strategy_source_demands(
            settings, "rev", [dict(candidate_id="one")],
            provider_call=lambda *args: pytest.fail("invalid request dispatched"),
        )
    with pytest.raises(runtime.StrategySourceRuntimeError, match="INVALID_STRATEGY_VERSION"):
        runtime.resolve_strategy_source_demands(
            settings, "../unsafe", [want("one")],
            provider_call=lambda *args: pytest.fail("invalid revision dispatched"),
        )


def test_zero_demand_does_not_claim_source_coverage_for_unseen_strategies(tmp_path):
    settings = LocalSettings(tmp_path)
    result = runtime.resolve_strategy_source_demands(settings, "empty_revision", [])
    assert result["source_uses_requested"] == 0
    assert result["historical_execution_proven"] is False
    assert result["point_in_time_feature_availability_proven"] is False
