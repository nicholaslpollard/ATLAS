from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Event, Lock

import pytest

from packages.data import options_native_exit_source_campaign_v1 as exits
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_pilot_plan_v1 import build_options_native_pilot_plan
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import run_options_native_spy_exit_source_campaign_v1 as cli


class Settings:
    def __init__(self, root):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
    def assert_external_storage_binding(self, name):
        assert name == "options"
    def resolved_path(self, rel):
        return self.root / rel


@pytest.fixture(scope="module")
def frozen():
    original = build_options_native_pilot_plan()["entry_quote_surface_requests"]
    assert len(original) == 411
    rows = []
    for i, item in enumerate(original, 1):
        row = _entry(
            exits.SPY_ORIGIN, "a" * 64, item["query_fingerprint"],
            {"endpoint": item["endpoint"], "params": item["params"]},
            role="WEEKLY_ENTRY_DECISION", anchor=False,
        )
        row["priority"] = i
        rows.append(row)
    return {
        "manifest_fingerprint": exits.PINNED_MANIFEST_FINGERPRINT,
        "source_request_count": 9866,
        "requests": rows,
    }


@pytest.fixture
def world(tmp_path, monkeypatch, frozen):
    settings = Settings(tmp_path)
    monkeypatch.setattr(exits, "_load_full_manifest", lambda *_: frozen)
    monkeypatch.setattr(
        exits, "review_native_pilot_acquisition_readiness",
        lambda *_args, **_kwargs: {
            "entry_covered_v12_sources": 410,
            "separately_saved_2025_spy_diagnostic": 1,
            "entry_outstanding_unattempted": 0,
            "additional_distinct_exit_review_queries": 1570,
        },
    )
    monkeypatch.setattr(exits, "_safe_storage", lambda *_args, **_kwargs: {
        "safe": True,
        "available_after_hourly_reservations": 60 * 1024**3,
    })
    plan = exits._demand(frozen)
    return settings, plan


def source(req, *, zero_bid=False, over_dte=False):
    d = date.fromisoformat(req["session_et"])
    exp = d + timedelta(days=(75 if over_dte else 35))
    stamp = datetime.combine(d, datetime.min.time()).replace(
        hour=9, minute=59, second=55,
    ).isoformat() + "-05:00"
    # Use UTC-05:00 only for winter dates; use ISO aware offset from XNYS.
    from zoneinfo import ZoneInfo
    stamp = datetime.combine(d, datetime.min.time()).replace(
        hour=9, minute=59, second=55,
        tzinfo=ZoneInfo("America/New_York"),
    ).isoformat()
    quotes = ({
        "symbol": "SPY", "expiration": exp.isoformat(),
        "strike": 500.0, "right": "call", "timestamp": stamp,
        "bid": 0.0 if zero_bid else 1.0, "ask": 1.2,
        "bid_size": 0 if zero_bid else 3, "ask_size": 4,
        "bid_exchange": 1, "ask_exchange": 2,
        "bid_condition": 0, "ask_condition": 0,
    }, {
        "symbol": "SPY", "expiration": exp.isoformat(),
        "strike": 500.0, "right": "put", "timestamp": stamp,
        "bid": 1.1, "ask": 1.3,
        "bid_size": 3, "ask_size": 3,
        "bid_exchange": 1, "ask_exchange": 2,
        "bid_condition": 0, "ask_condition": 0,
    })
    raw = _canonical_bytes(quotes)
    return ThetaDataResponse(
        http_status=200, rows=quotes, headers={},
        response_bytes=len(raw), raw_body=raw, elapsed_seconds=0.1,
        transport=TRANSPORT, library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="c" * 64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
    )


def test_exact_2055_exit_uses_deduplicate_411_entry_queries(frozen):
    plan = exits._demand(frozen)
    assert plan["exit_review_uses"] == 2055
    assert len(plan["requests"]) == 1570
    assert plan["reused_original_entry_queries"] > 0
    assert len({q["query_id"] for q in plan["requests"]}) == 1570
    assert list(q["session_et"] for q in plan["requests"]) == sorted(
        q["session_et"] for q in plan["requests"]
    )
    original_qids = {
        r["query_id"] for r in frozen["requests"]
    }
    assert not any(r["query_id"] in original_qids for r in plan["requests"])
    first = plan["requests"][0]
    assert first["source_role"] == "POST_ENTRY_MARK_REVIEW_NOT_FILL"
    assert exits._sdk_request(first) == {
        "symbol": "SPY", "date_et": first["session_et"],
        "time_of_day_et": "10:00:00.000",
        "right": "both", "max_dte": 45, "strike_range": 2,
    }
    assert plan["plan_fingerprint"] == exits._demand(frozen)["plan_fingerprint"]


def test_preview_is_read_only_and_only_new_exit_scopes(world):
    settings, plan = world
    p = exits.preview_exit_campaign(settings, Path("f"), Path("c"))
    assert p["remaining_unattempted"] == 1570
    assert p["exit_review_uses"] == 2055
    assert p["additional_distinct_exit_requests"] == 1570
    assert p["provider_requests"] == 0
    assert p["simulator_ready"] is False
    assert not settings.resolved_path(exits.ROOT_REL).exists()


def test_exit_acquisition_refuses_unverified_original_entry_corpus(
    world, monkeypatch,
):
    settings, plan = world
    monkeypatch.setattr(
        exits, "review_native_pilot_acquisition_readiness",
        lambda *_args, **_kwargs: {
            "entry_covered_v12_sources": 409,
            "separately_saved_2025_spy_diagnostic": 1,
            "entry_outstanding_unattempted": 1,
            "additional_distinct_exit_review_queries": 1570,
        },
    )
    with pytest.raises(
        exits.SpyExitSourceError,
        match="SPY_ORIGINAL_411_ENTRY_EVIDENCE_INCOMPLETE",
    ):
        exits.run_exit_campaign(
            settings, Path("f"), Path("c"),
            workers=4,
            reader=lambda **kwargs: pytest.fail("no provider without source"),
        )
    assert not settings.resolved_path(exits.ROOT_REL).exists()


def test_parallel_real_overlap_global_limit_and_lossless_resume(world):
    settings, plan = world
    first = plan["requests"][:4]
    observed = []
    lock = Lock()
    simultaneous = Event()

    def read(**kwargs):
        with lock:
            observed.append(kwargs["date_et"])
            if len(observed) == 4:
                simultaneous.set()
        assert simultaneous.wait(timeout=5)
        req = next(r for r in first if r["session_et"] == kwargs["date_et"])
        return source(req, over_dte=True)

    progress = []
    a = exits.run_exit_campaign(
        settings, Path("f"), Path("c"), workers=4,
        max_calls=4, reader=read,
        progress=progress.append, progress_every=1,
    )
    assert simultaneous.is_set()
    assert a["provider_calls_this_run"] == 4
    assert a["completed_provider_calls_this_run"] == 4
    assert a["archives_this_run"] == 4
    assert a["outside_dte_archives_this_run"] == 4
    assert a["stop_reason"] == "OPTIONAL_GLOBAL_CALL_LIMIT_REACHED"
    assert len(progress) == 4
    p = exits.preview_exit_campaign(settings, Path("f"), Path("c"))
    assert p["remaining_unattempted"] == 1566
    assert p["exit_source_states"]["RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC"] == 4
    for req in first:
        assert exits._state(
            settings, req, plan["plan_fingerprint"]
        ) == "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC"
        assert exits._path(settings, req["query_id"], "sources").is_file()
    next_req = plan["requests"][4]
    b = exits.run_exit_campaign(
        settings, Path("f"), Path("c"), workers=2, max_calls=1,
        reader=lambda **kwargs: source(next_req),
    )
    assert b["provider_calls_this_run"] == 1
    assert exits._state(
        settings, next_req, plan["plan_fingerprint"]
    ) == "RAW_ARCHIVED_SCOPE_DIAGNOSTIC"
    assert exits.preview_exit_campaign(
        settings, Path("f"), Path("c")
    )["remaining_unattempted"] == 1565


def test_invalid_schema_archive_is_preserved_not_execution_admitted(world):
    settings, plan = world
    req = plan["requests"][0]
    def bad(**kwargs):
        r = source(req)
        original = [dict(item) for item in r.rows]
        original[0]["timestamp"] = "2099-01-01T10:00:00-05:00"
        payload = _canonical_bytes(original)
        from dataclasses import replace
        return replace(
            r, rows=tuple(original),
            response_bytes=len(payload), raw_body=payload,
        )
    a = exits.run_exit_campaign(
        settings, Path("f"), Path("c"), workers=1,
        max_calls=1, reader=bad,
    )
    assert a["archives_this_run"] == 1
    assert a["invalid_archives_this_run"] == 1
    assert exits._state(
        settings, req, plan["plan_fingerprint"]
    ) == "RAW_ARCHIVED_INVALID_SCHEMA"
    assert a["simulator_ready"] is False


def test_four_invalid_source_schemas_stop_further_paid_requests(world):
    settings, plan = world
    from dataclasses import replace
    def bad(**kwargs):
        req = next(
            r for r in plan["requests"]
            if r["session_et"] == kwargs["date_et"]
        )
        good = source(req)
        rows = [dict(item) for item in good.rows]
        rows[0]["timestamp"] = "2099-01-01T10:00:00-05:00"
        raw = _canonical_bytes(rows)
        return replace(good, rows=tuple(rows),
                       raw_body=raw, response_bytes=len(raw))
    result = exits.run_exit_campaign(
        settings, Path("f"), Path("c"),
        workers=1, max_calls=5, reader=bad,
    )
    assert result["provider_calls_this_run"] == 4
    assert result["invalid_archives_this_run"] == 4
    assert result["stop_reason"] == (
        "REPEATED_INVALID_SOURCE_SCHEMA_STOPPED_RUN"
    )
    assert exits._state(
        settings, plan["requests"][4], plan["plan_fingerprint"]
    ) == "UNATTEMPTED"


def test_failure_stops_new_dispatch_and_does_not_retry_uncertain(world):
    settings, plan = world
    first, second = plan["requests"][:2]
    calls = []

    def failing(**kwargs):
        calls.append(kwargs["date_et"])
        if kwargs["date_et"] == first["session_et"]:
            raise TimeoutError("Ambiguous request delivery")
        return source(second)

    a = exits.run_exit_campaign(
        settings, Path("f"), Path("c"),
        workers=2, max_calls=2, reader=failing,
    )
    assert a["provider_calls_this_run"] == 2
    assert a["stop_reason"] == "PROVIDER_OR_STORAGE_FAILURE_STOP"
    assert exits._state(
        settings, first, plan["plan_fingerprint"]
    ) == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
    assert exits._state(
        settings, second, plan["plan_fingerprint"]
    ).startswith("RAW_ARCHIVED")
    assert exits.preview_exit_campaign(
        settings, Path("f"), Path("c")
    )["remaining_unattempted"] == 1568
    following = plan["requests"][2]
    b = exits.run_exit_campaign(
        settings, Path("f"), Path("c"),
        workers=1, max_calls=1, reader=lambda **kwargs: source(following),
    )
    assert b["provider_calls_this_run"] == 1
    assert calls == [first["session_et"], second["session_et"]] or (
        set(calls) == {first["session_et"], second["session_et"]}
    )


def test_corrupted_archive_fails_closed_before_replay(world):
    settings, plan = world
    req = plan["requests"][0]
    exits.run_exit_campaign(
        settings, Path("f"), Path("c"), workers=1, max_calls=1,
        reader=lambda **kwargs: source(req),
    )
    path = exits._path(settings, req["query_id"], "sources")
    path.write_bytes(b"not source")
    with pytest.raises(exits.SpyExitSourceError):
        exits.preview_exit_campaign(settings, Path("f"), Path("c"))


def test_original_request_identity_and_worker_limits_are_strict(world):
    settings, plan = world
    req = plan["requests"][0]
    forged = dict(req, query_id="a" * 64)
    with pytest.raises(exits.SpyExitSourceError):
        exits._sdk_request(forged)
    for workers in (0, 5, True):
        with pytest.raises(exits.SpyExitSourceError):
            exits.run_exit_campaign(
                settings, Path("f"), Path("c"), workers=workers,
                reader=lambda **kwargs: pytest.fail("never dispatch"),
            )
    with pytest.raises(exits.SpyExitSourceError):
        exits.run_exit_campaign(
            settings, Path("f"), Path("c"), max_calls=0,
            reader=lambda **kwargs: pytest.fail("never dispatch"),
        )


def test_readonly_cli_does_not_dispatch(world, monkeypatch, capsys):
    settings, plan = world
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "new_distinct_exit_scopes=1570" in out
    assert "remaining=1570" in out
    assert "provider_requests=0" in out
    assert not settings.resolved_path(exits.ROOT_REL).exists()
    with pytest.raises(SystemExit):
        cli.main(["--max-calls", "1"])
