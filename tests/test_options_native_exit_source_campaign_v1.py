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
from scripts import run_options_native_spy_exit_fault_audit_v1 as fault_audit


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


def test_capacity_meter_32_dispatches_have_one_deep_scan(world, monkeypatch):
    settings, plan = world
    checks = []
    def deep(_settings, _reader):
        checks.append(1)
        return {
            "safe": True,
            "available_after_hourly_reservations": (
                exits.MIN_CAPACITY_PER_REQUEST * 100
            ),
        }
    monkeypatch.setattr(exits, "_safe_storage", deep)
    monkeypatch.setattr(
        exits, "_physical_free_bytes", lambda _settings: 100 * 1024**3,
    )
    meter = exits._ConservativeExitStorageMeter(
        settings, storage_reader=lambda *_: None,
    )
    for _ in range(32):
        assert meter.allow_next() is True
    assert meter.full_audits == 1
    assert len(checks) == 1
    assert meter.allow_next() is True
    assert meter.full_audits == 2
    assert len(checks) == 2


def test_capacity_meter_worst_case_debits_and_other_writer_pressure(
    world, monkeypatch,
):
    settings, plan = world
    one = exits.MIN_CAPACITY_PER_REQUEST
    fake = {"free": 100 * 1024**3}
    monkeypatch.setattr(
        exits, "_safe_storage",
        lambda *_args, **_kwargs: {
            "safe": True,
            "available_after_hourly_reservations": one * 2,
        },
    )
    monkeypatch.setattr(
        exits, "_physical_free_bytes", lambda _settings: fake["free"],
    )
    meter = exits._ConservativeExitStorageMeter(
        settings, storage_reader=lambda *_: None,
    )
    assert meter.allow_next() is True
    fake["free"] -= 2 * one  # One request allowance + unexpected disk writer
    assert meter.allow_next() is False
    assert meter.calls_since_full == 1


def test_capacity_meter_absolute_external_warning_floor(world, monkeypatch):
    settings, plan = world
    from types import SimpleNamespace
    settings.data = SimpleNamespace(
        research=SimpleNamespace(
            storage=SimpleNamespace(external_warning_free_gib=50.0)
        )
    )
    monkeypatch.setattr(
        exits, "_safe_storage",
        lambda *_args, **_kwargs: {
            "safe": True,
            "available_after_hourly_reservations": 100 * 1024**3,
        },
    )
    monkeypatch.setattr(
        exits, "_physical_free_bytes",
        lambda _settings: (
            50 * 1024**3 + exits.MIN_CAPACITY_PER_REQUEST - 1
        ),
    )
    meter = exits._ConservativeExitStorageMeter(
        settings, storage_reader=lambda *_: None,
    )
    assert meter.allow_next() is False
    assert meter.full_audits == 1


def test_running_campaign_limits_recursive_storage_scans(world, monkeypatch):
    settings, plan = world
    audits = []
    def audited(_settings, _reader):
        audits.append(1)
        return {
            "safe": True,
            "available_after_hourly_reservations": 100 * 1024**3,
        }
    monkeypatch.setattr(exits, "_safe_storage", audited)
    # Each request consumes only its precharged worst-case budget.
    monkeypatch.setattr(
        exits, "_physical_free_bytes", lambda _settings: 110 * 1024**3,
    )
    by_date = {r["session_et"]: r for r in plan["requests"][:33]}
    result = exits.run_exit_campaign(
        settings, Path("f"), Path("c"),
        workers=4, max_calls=33,
        reader=lambda **kw: source(by_date[kw["date_et"]]),
    )
    assert result["provider_calls_this_run"] == 33
    assert result["archives_this_run"] == 33
    assert result["stop_reason"] == "OPTIONAL_GLOBAL_CALL_LIMIT_REACHED"
    # One preview audit, then one full scan per 32 launches; no per-GET scan.
    assert len(audits) == 3
    assert result["full_storage_audits_this_run"] == 2
    assert exits.preview_exit_campaign(
        settings, Path("f"), Path("c")
    )["remaining_unattempted"] == 1570 - 33


def test_v21_offline_error_audit_preserves_errors_and_original_hashes(
    world, frozen, monkeypatch,
):
    settings, plan = world
    req_invalid, req_fault = plan["requests"][:2]
    from dataclasses import replace

    def damaged(**kwargs):
        if kwargs["date_et"] == req_fault["session_et"]:
            raise TimeoutError("Original provider request status unknown")
        r = source(req_invalid)
        rows = [dict(item) for item in r.rows]
        rows[0]["timestamp"] = "2099-01-01T10:00:00-05:00"
        raw = _canonical_bytes(rows)
        return replace(
            r, rows=tuple(rows), raw_body=raw, response_bytes=len(raw),
        )
    result = exits.run_exit_campaign(
        settings, Path("f"), Path("c"),
        workers=2, max_calls=2, reader=damaged,
    )
    assert result["provider_calls_this_run"] == 2
    monkeypatch.setattr(
        fault_audit, "_load_full_manifest", lambda *_: frozen,
    )
    checked = fault_audit.audit(settings, Path("f"), Path("c"))
    assert checked["total_new_exit_ids"] == 1570
    assert checked["provider_requests"] == 0
    assert checked["files_written"] == 0
    issues = {
        q["query_id"]: q for q in checked["abnormal_identities"]
    }
    assert set(issues) == {
        req_fault["query_id"], req_invalid["query_id"],
    }
    invalid = issues[req_invalid["query_id"]]
    assert invalid["state"] == "RAW_ARCHIVED_INVALID_SCHEMA"
    assert invalid["archive_present"] is True
    assert invalid["row_only_diagnostic"] == (
        "ORIGINAL_ROW_CHECK_FAILED code=EXIT_QUOTE_ESCAPES_REVIEW_CLOCK"
    )
    assert len(invalid["original_sha256"]) == 64
    failure = issues[req_fault["query_id"]]
    assert failure["state"] == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
    assert failure["recorded_error_type"] == "TimeoutError"
    assert failure["row_only_diagnostic"] == "NO_ORIGINAL_ROWS_RETAINED"
    assert failure["archive_present"] is False


def test_v21_row_valid_archive_does_not_forge_provider_metadata(
    world, frozen, monkeypatch,
):
    settings, plan = world
    req = plan["requests"][0]
    r = source(req)
    from dataclasses import replace
    bad = replace(r, http_status=499)
    result = exits.run_exit_campaign(
        settings, Path("f"), Path("c"),
        workers=1, max_calls=1, reader=lambda **kwargs: bad,
    )
    assert result["invalid_archives_this_run"] == 1
    monkeypatch.setattr(
        fault_audit, "_load_full_manifest", lambda *_: frozen,
    )
    issue = fault_audit.audit(
        settings, Path("f"), Path("c"),
    )["abnormal_identities"][0]
    assert issue["row_only_diagnostic"] == (
        "ROWS_PASS_LOCAL_CHECK_METADATA_CAUSE_UNRESOLVED"
        " local_classification=RAW_ARCHIVED_SCOPE_DIAGNOSTIC"
    )
    assert issue["state"] == "RAW_ARCHIVED_INVALID_SCHEMA"


def test_v22_preserves_origin_provider_error_class_without_secret_data(world):
    settings, plan = world
    req = plan["requests"][0]
    from packages.providers.thetadata.client import ThetaDataError

    def auth_failure(**kwargs):
        raise ThetaDataError(
            "provider confidential URL and secret NEVER STORE",
            provider_error_type="AuthenticationError",
            provider_grpc_status="UNAUTHENTICATED",
        )

    progress = []
    result = exits.run_exit_campaign(
        settings, Path("f"), Path("c"), workers=1, max_calls=1,
        reader=auth_failure, progress_every=1, progress=progress.append,
    )
    assert result["stop_reason"] == "PROVIDER_OR_STORAGE_FAILURE_STOP"
    assert exits._state(
        settings, req, plan["plan_fingerprint"],
    ) == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
    receipt = exits._receipt(
        settings, req, plan["plan_fingerprint"], "terminal",
    )
    assert receipt["error_type"] == "ThetaDataError"
    assert receipt["provider_failure_class"] == "AuthenticationError"
    assert receipt["provider_grpc_status"] == "UNAUTHENTICATED"
    assert "confidential" not in str(receipt)
    assert progress[0]["provider_failure_class"] == "AuthenticationError"
    assert progress[0]["provider_grpc_status"] == "UNAUTHENTICATED"


def test_v22_offline_archive_audit_does_not_invent_legacy_provider_details(
    world, frozen, monkeypatch,
):
    settings, plan = world
    req = plan["requests"][0]
    started = exits._evidence({
        "contract": exits.CONTRACT, "kind": "started",
        "plan_fingerprint": plan["plan_fingerprint"],
        "session_et": req["session_et"], "query_id": req["query_id"],
        "sdk_kwargs": exits._sdk_request(req),
        "state": "POSSIBLY_DISPATCHED_NO_SAME_QUERY_RETRY",
        "source_complete": False, "simulator_ready": False,
    })
    exits._write_receipt(
        settings, req, plan["plan_fingerprint"], "started", started,
    )
    # Deliberately versioned as old V19/V20: no provider-class fields.
    terminal = exits._evidence({
        "contract": exits.CONTRACT, "kind": "terminal",
        "plan_fingerprint": plan["plan_fingerprint"],
        "session_et": req["session_et"], "query_id": req["query_id"],
        "started_fingerprint": started["fingerprint"],
        "archive": None,
        "state": "PROVIDER_OR_STORAGE_ERROR_NO_RETRY",
        "error_type": "ThetaDataError",
        "source_complete": False, "simulator_ready": False,
    })
    exits._write_receipt(
        settings, req, plan["plan_fingerprint"], "terminal", terminal,
    )
    monkeypatch.setattr(
        fault_audit, "_load_full_manifest", lambda *_: frozen,
    )
    issue = fault_audit.audit(
        settings, Path("f"), Path("c"),
    )["abnormal_identities"][0]
    assert issue["recorded_error_type"] == "ThetaDataError"
    assert issue["provider_failure_class"] is None
    assert issue["provider_grpc_status"] is None


def test_v22_sdk_worker_sanitizes_error_class_and_grpc_status():
    from types import SimpleNamespace
    from scripts.thetadata_python_worker_v1 import (
        _sanitized_provider_exception,
    )
    class GrpcError(Exception):
        def code(self):
            return SimpleNamespace(name="RESOURCE_EXHAUSTED")
    assert _sanitized_provider_exception(GrpcError("secret")) == {
        "error_type": "GrpcError",
        "error_grpc_status": "RESOURCE_EXHAUSTED",
    }
    class Unsupported(Exception):
        def code(self):
            return SimpleNamespace(name="FAKE_SECRET_STATUS")
    assert _sanitized_provider_exception(Unsupported("secret")) == {
        "error_type": "Unsupported",
        "error_grpc_status": None,
    }


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


def test_v23_single_sdk_auth_with_four_parallel_derived_clients(monkeypatch):
    from threading import Barrier
    from types import ModuleType
    from scripts import thetadata_python_worker_v1 as worker
    import pandas as pd

    module = ModuleType("thetadata")
    sync = Barrier(4)
    created = []
    class FakeThetaClient:
        def __init__(
            self, *, existing_authorized_client=None, dataframe_type="polars"
        ):
            assert dataframe_type == "pandas"
            created.append(existing_authorized_client)
        def option_at_time_quote(self, **kwargs):
            sync.wait(timeout=5)
            return pd.DataFrame([{"date_et": kwargs["start_date"].isoformat()}])
    module.ThetaClient = FakeThetaClient
    monkeypatch.setitem(__import__("sys").modules, "thetadata", module)
    rt = worker.Runtime()
    rt.version = worker.TARGET_LIBRARY_VERSION
    rt.environment_fingerprint = "a" * 64
    original_client = FakeThetaClient(dataframe_type="pandas")
    rt.ensure = lambda: original_client
    sample = {
        "symbol": "SPY", "start_date": "2025-01-06",
        "end_date": "2025-01-06", "time_of_day": "10:00:00.000",
        "expiration": "*", "strike": "*", "right": "both",
        "max_dte": 45, "strike_range": 2,
    }
    result = rt.request_shared_batch([sample] * 4)
    assert result["shared_authenticated_session"] is True
    assert len(result["results"]) == 4
    assert all(q["ok"] is True for q in result["results"])
    assert len(created) == 4  # one fake existing base, three derived
    assert created[0] is None
    assert created[1:] == [original_client] * 3
    assert result["environment_fingerprint"] == "a" * 64


def test_v23_shared_campaign_reuses_origins_and_avoids_four_auths(world):
    from packages.data import options_native_exit_shared_session_campaign_v1 as shared
    settings, plan = world
    batches = []
    def batch_reader(queries):
        batches.append(queries)
        expected = plan["requests"][4 * (len(batches) - 1):4 * len(batches)]
        assert len(expected) == 4
        assert [q["date_et"] for q in queries] == [
            q["session_et"] for q in expected
        ]
        return [source(req, over_dte=True) for req in expected]
    result = shared.run_shared_exit_campaign(
        settings, Path("f"), Path("c"), max_calls=8,
        reader=batch_reader, progress_every=4,
    )
    assert result["provider_calls_this_run"] == 8
    assert result["archives_this_run"] == 8
    assert result["provider_faults_this_run"] == 0
    assert result["stop_reason"] == "OPTIONAL_GLOBAL_CALL_LIMIT_REACHED"
    assert result["account_authenticated_sessions"] == 1
    assert len(batches) == 2
    next_result = shared.run_shared_exit_campaign(
        settings, Path("f"), Path("c"), max_calls=4,
        reader=lambda queries: [
            source(req, over_dte=True) for req in plan["requests"][8:12]
        ],
    )
    assert next_result["archives_this_run"] == 4
    assert exits.preview_exit_campaign(
        settings, Path("f"), Path("c")
    )["remaining_unattempted"] == 1570 - 12


def test_v23_shared_batch_grpc_auth_fault_isolated_and_fails_closed(world):
    from packages.data import options_native_exit_shared_session_campaign_v1 as shared
    from packages.providers.thetadata.client import ThetaDataError
    settings, plan = world
    fault = ThetaDataError(
        "provider secret intentionally omitted",
        provider_error_type="_MultiThreadedRendezvous",
        provider_grpc_status="UNAUTHENTICATED",
    )
    attempts = []
    def reader(queries):
        attempts.append(queries)
        return [
            source(plan["requests"][0], over_dte=True),
            fault, fault, fault,
        ]
    r = shared.run_shared_exit_campaign(
        settings, Path("f"), Path("c"),
        reader=reader, progress_every=1,
    )
    assert r["provider_calls_this_run"] == 4
    assert r["archives_this_run"] == 1
    assert r["provider_faults_this_run"] == 3
    assert r["stop_reason"] == "PROVIDER_OR_STORAGE_FAILURE_STOP"
    assert len(attempts) == 1
    assert exits.preview_exit_campaign(
        settings, Path("f"), Path("c")
    )["remaining_unattempted"] == 1566
    for req in plan["requests"][1:4]:
        receipt = exits._receipt(
            settings, req, plan["plan_fingerprint"], "terminal",
        )
        assert receipt["provider_failure_class"] == "_MultiThreadedRendezvous"
        assert receipt["provider_grpc_status"] == "UNAUTHENTICATED"
        assert "secret" not in str(receipt)


def test_v23_shared_batch_transport_failure_never_retries(world):
    from packages.data import options_native_exit_shared_session_campaign_v1 as shared
    settings, plan = world
    batches = []
    def fail(queries):
        batches.append(queries)
        raise TimeoutError("unknown dispatch results")
    r = shared.run_shared_exit_campaign(
        settings, Path("f"), Path("c"), reader=fail,
    )
    assert r["provider_calls_this_run"] == 4
    assert r["provider_faults_this_run"] == 4
    assert r["archives_this_run"] == 0
    assert len(batches) == 1
    assert exits.preview_exit_campaign(
        settings, Path("f"), Path("c")
    )["remaining_unattempted"] == 1566
    for req in plan["requests"][:4]:
        assert exits._state(
            settings, req, plan["plan_fingerprint"]
        ) == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"


def test_v23_shared_source_cli_offline_has_no_sdk_or_provider(
    world, monkeypatch, capsys,
):
    from scripts import run_options_native_spy_exit_shared_session_v1 as cli23
    settings, plan = world
    monkeypatch.setattr(cli23, "load_settings", lambda *_: settings)
    monkeypatch.setattr(
        cli23, "_provider_shared_signature_preflight",
        lambda: pytest.fail("offline must not even preflight provider"),
    )
    assert cli23.main([]) == 0
    assert "provider_requests=0" in capsys.readouterr().out
    assert not settings.resolved_path(exits.ROOT_REL).exists()


def test_v23_shared_auth_setup_failure_is_before_all_paid_receipts(
    world, monkeypatch, capsys,
):
    from scripts import run_options_native_spy_exit_shared_session_v1 as cli23
    settings, plan = world
    monkeypatch.setattr(cli23, "load_settings", lambda *_: settings)
    monkeypatch.setattr(
        cli23, "_provider_shared_signature_preflight",
        lambda: {"thetadata_version": "1.0.12",
                 "shared_authenticated_client_status":
                 "SHARED_AUTH_CONSTRUCTOR_EXPLICIT"},
    )
    def cannot_authenticate():
        raise RuntimeError("SDK shared client setup refused")
    monkeypatch.setattr(
        cli23, "establish_option_quote_shared_authenticated_session",
        cannot_authenticate,
    )
    assert cli23.main(["--run", "--max-calls", "4"]) == 3
    assert "BLOCKED" in capsys.readouterr().out
    assert exits.preview_exit_campaign(
        settings, Path("f"), Path("c"),
    )["remaining_unattempted"] == 1570
    assert not settings.resolved_path(exits.ROOT_REL).exists()


def test_v23_shared_auth_setup_is_idempotent_and_never_uses_history(
    monkeypatch,
):
    from types import ModuleType
    from scripts import thetadata_python_worker_v1 as worker
    module = ModuleType("thetadata")
    created = []
    class Fake:
        def __init__(
            self, *, existing_authorized_client=None, dataframe_type="pandas"
        ):
            created.append(existing_authorized_client)
        def option_at_time_quote(self, **kwargs):
            raise AssertionError("auth readiness must not request history")
    module.ThetaClient = Fake
    monkeypatch.setitem(__import__("sys").modules, "thetadata", module)
    runtime = worker.Runtime()
    primary = Fake()
    runtime.ensure = lambda: primary
    assert runtime.setup_shared_auth_session()["historical_quote_requests"] == 0
    assert runtime.setup_shared_auth_session()["historical_quote_requests"] == 0
    assert len(created) == 4
    assert created[1:] == [primary] * 3
