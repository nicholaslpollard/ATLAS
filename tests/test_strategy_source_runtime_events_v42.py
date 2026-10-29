from __future__ import annotations

import sqlite3

from packages.data import options_on_demand_source_cache_v38 as cache
from packages.providers.thetadata.client import ThetaDataResponse, _canonical_bytes
from packages.simulation.strategy_options_source_runtime_v39 import resolve_strategy_source_demands


class Storage:
    def __init__(self, path):
        self.path = path
        (path / "data/options").mkdir(parents=True, exist_ok=True)

    def resolved_path(self, rel):
        return self.path / rel

    def assert_external_storage_binding(self, name):
        assert name == "options"


def requirement(strike):
    return {
        "candidate_id": "SPY-20250609-" + strike,
        "purpose": "entry_quote",
        "method": "option_at_time_quote",
        "kwargs": {
            "symbol": "SPY", "date_et": "2025-06-09",
            "expiration": "2025-07-18", "strike": strike,
            "right": "put", "time_of_day_et": "10:01:00.000",
        },
    }


def source():
    rows = ({"symbol": "SPY", "bid": 1.0, "ask": 1.1},)
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={},
        response_bytes=len(raw), elapsed_seconds=0.1, raw_body=raw,
    )


def test_lifecycle_event_status_and_true_dispatch_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    settings = Storage(tmp_path)
    observed = []

    def callback(kind, data):
        observed.append((kind, data))

    result = resolve_strategy_source_demands(
        settings, "progress_version",
        [requirement("600"), requirement("600"), requirement("605")],
        provider_call=lambda name, kwargs: source(),
        on_progress=callback,
    )
    assert result["source_uses_resolved"] == 3
    assert result["provider_dispatch_attempts"] == 2
    assert result["persisted_cache_hits"] == 1
    assert [kind for kind, _ in observed] == [
        "source_started", "provider_dispatch", "source_done",
        "source_started", "source_done",
        "source_started", "provider_dispatch", "source_done",
    ]
    assert [d["status"] for k,d in observed if k == "source_done"] == [
        "FETCHED_AND_ARCHIVED", "CACHE_HIT", "FETCHED_AND_ARCHIVED",
    ]


def test_lifecycle_reports_failed_attempt_then_continues(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "MIN_FREE_STORAGE_BYTES", 0)
    observed = []

    def fetch(name, arguments):
        if arguments["strike"] == "600":
            raise RuntimeError("deliberate test failure")
        return source()

    result = resolve_strategy_source_demands(
        Storage(tmp_path), "progress_version",
        [requirement("600"), requirement("605")],
        provider_call=fetch,
        on_progress=lambda kind, data: observed.append((kind, data)),
        continue_on_error=True,
    )
    assert result["provider_dispatch_attempts"] == 2
    assert result["source_uses_resolved"] == 1
    assert result["source_uses_failed_or_unresolved"] == 1
    assert [k for k,d in observed if k == "source_failed"] == ["source_failed"]
    assert "RuntimeError" in [d["error"] for k,d in observed if k == "source_failed"][0]
    assert observed[-1][0] == "source_done"
