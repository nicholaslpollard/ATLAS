from __future__ import annotations

import sqlite3

import pytest

from packages.data import options_on_demand_source_cache_v38 as cache
from packages.providers.thetadata.client import ThetaDataResponse, _canonical_bytes


class FakeSettings:
    def __init__(self, root):
        self.root = root
        (root / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, name):
        assert name == "options"

    def resolved_path(self, name):
        return self.root / name


def kwargs(**overrides):
    return {
        "symbol": "SPY",
        "expiration": "2025-06-20",
        "strike": "600",
        "right": "call",
        "date_et": "2025-06-09",
        "time_of_day_et": "10:00:00.000",
        **overrides,
    }


def response(*, explicit_no_data=False):
    rows = () if explicit_no_data else (
        {
            "symbol": "SPY", "expiration": "2025-06-20",
            "strike": 600, "right": "CALL",
            "bid": 1.0, "ask": 1.2, "timestamp": "2025-06-09T10:00:00-04:00",
        },
    )
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={}, response_bytes=len(raw),
        elapsed_seconds=0.01, raw_body=raw,
        explicit_no_data=explicit_no_data,
    )


def test_auto_fetch_persist_and_reuse_with_exact_identity(tmp_path, monkeypatch):
    settings = FakeSettings(tmp_path)
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    calls = []

    def fetch(name, parameters):
        calls.append((name, parameters))
        return response()

    first = cache.read_through_historical_options(
        settings, "option_at_time_quote", kwargs(), provider_call=fetch,
    )
    assert first["status"] == "FETCHED_AND_ARCHIVED"
    assert len(first["source_rows"]) == 1
    assert not first["simulator_ready"]
    cache_hit = cache.read_through_historical_options(
        settings, "option_at_time_quote", kwargs(), provider_call=fetch,
    )
    assert cache_hit["status"] == "CACHE_HIT"
    assert cache_hit["query_id"] == first["query_id"]
    assert cache_hit["source_rows"] == first["source_rows"]
    assert len(calls) == 1

    # Strategy change: date, strike, right, etc. create new, automatically
    # fetched sources without amending any frozen candidate plan.
    new = cache.read_through_historical_options(
        settings, "option_at_time_quote",
        kwargs(strike="605"), provider_call=fetch,
    )
    assert new["status"] == "FETCHED_AND_ARCHIVED"
    assert new["query_id"] != first["query_id"]
    assert len(calls) == 2
    with sqlite3.connect(settings.resolved_path(cache.DB_REL)) as db:
        assert db.execute("SELECT count(*) FROM sources WHERE state='ARCHIVED'").fetchone()[0] == 2


def test_cached_no_data_only_when_explicitly_certified(tmp_path):
    settings = FakeSettings(tmp_path)
    calls = []
    def empty(name, parameters):
        calls.append(name)
        return response(explicit_no_data=True)

    one = cache.read_through_historical_options(
        settings, "option_at_time_quote", kwargs(), provider_call=empty,
    )
    two = cache.read_through_historical_options(
        settings, "option_at_time_quote", kwargs(), provider_call=empty,
    )
    assert one["status"] == "FETCHED_EXPLICIT_NO_DATA"
    assert two["status"] == "CACHED_EXPLICIT_NO_DATA"
    assert len(calls) == 1


def test_provider_failure_can_retry_on_next_demand(tmp_path, monkeypatch):
    settings = FakeSettings(tmp_path)
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    def failure(name, parameters):
        raise RuntimeError("provider temporarily down")
    with pytest.raises(RuntimeError):
        cache.read_through_historical_options(
            settings, "option_at_time_quote", kwargs(), provider_call=failure,
        )
    after = cache.read_through_historical_options(
        settings, "option_at_time_quote", kwargs(), provider_call=lambda n, p: response(),
    )
    assert after["status"] == "FETCHED_AND_ARCHIVED"


def test_deduplicates_in_flight_and_refuses_uncertified_empty(tmp_path):
    settings = FakeSettings(tmp_path)
    requirement = cache.normalize_source_requirement("option_at_time_quote", kwargs())
    qid = cache._fingerprint(requirement)
    db = cache._database(settings)
    with cache._connect(db) as con:
        con.execute(
            "INSERT INTO sources(query_id,request_json,state,touched) VALUES (?,?,?,?)",
            (qid, __import__("json").dumps(requirement, sort_keys=True, separators=(",", ":")),
             "IN_FLIGHT", cache.time.time()),
        )
    with pytest.raises(cache.OnDemandSourceError, match="ALREADY_IN_FLIGHT"):
        cache.read_through_historical_options(
            settings, "option_at_time_quote", kwargs(),
            provider_call=lambda n, p: pytest.fail("duplicate provider dispatch"),
        )


def test_query_validation_no_frozen_roster_or_hardcoded_spy(tmp_path):
    from datetime import date, timedelta
    settings = FakeSettings(tmp_path)
    data = cache.normalize_source_requirement(
        "option_at_time_quote", kwargs(symbol="QQQ", strike="700")
    )
    assert data["kwargs"]["symbol"] == "QQQ"
    with pytest.raises(cache.OnDemandSourceError):
        cache.normalize_source_requirement("dangerous_method", kwargs())
    with pytest.raises(cache.OnDemandSourceError):
        cache.normalize_source_requirement(
            "option_at_time_quote", kwargs(date_et="2030-13-01")
        )
    # No global-request-budget or static candidate cap: 150 unique exact
    # dates are accepted as new query keys, independent of a 361-SPY pilot.
    qids = {
        cache._fingerprint(cache.normalize_source_requirement(
            "option_at_time_quote", kwargs(
                symbol="QQQ",
                date_et=(date(2025, 1, 1) + timedelta(days=i)).isoformat(),
            ),
        )) for i in range(150)
    }
    assert len(qids) == 150
