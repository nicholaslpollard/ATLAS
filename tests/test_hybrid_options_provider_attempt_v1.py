from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data import hybrid_options_provider_attempt_v1 as v8
from packages.data.hybrid_options_acquisition_reservations_v1 import (
    plan_acquisition_reservations, _reservation_path,
)
from packages.data.hybrid_options_gap_planner_v1 import demo_batch, BATCH_CONTRACT
from packages.data.hybrid_options_source_store_v2 import (
    store_historical_quote_source, read_historical_quote_source,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import run_hybrid_options_single_provider_attempt_v1 as cli


class FakeSettings:
    def __init__(self, root: Path):
        self.root = root
        (root / "data/options").mkdir(parents=True, exist_ok=True)

    def assert_external_storage_binding(self, name):
        assert name == "options"

    def resolved_path(self, relative):
        return self.root / relative


def snapshot(*, available=180.0):
    return SimpleNamespace(
        storage_mode="EXTERNAL_SECONDARY",
        disk_free_gib=available,
        warning_free_gib=40.0,
        remaining_acquisition_budget_gib=180.0,
        category_usage_gib={"options_candidate_cache": 0.30},
        category_quota_gib={"options_candidate_cache": 120.0},
        acquisition_budget_gib=190.0, status="SAFE",
    )


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(
        shutil, "disk_usage",
        lambda _: SimpleNamespace(free=180 * 1024**3),
    )
    settings = FakeSettings(tmp_path)
    entry = demo_batch()["requests"][4]  # 2018 SPY hourly, currently unindexed
    batch = {"contract": BATCH_CONTRACT, "requests": [entry]}
    query = entry["query"]
    qid = _fingerprint({
        "source_type": "option_history_quote", "query": query,
    })
    def planning(settings, batch):
        return plan_acquisition_reservations(
            settings, batch,
            storage_reader=lambda _: snapshot(),
        )
    def reserve():
        return plan_acquisition_reservations(
            settings, batch, reserve=True,
            storage_reader=lambda _: snapshot(),
        )
    return settings, batch, query, qid, planning, reserve


def response(query, *, no_data=False):
    if no_data:
        rows = ()
    else:
        stamp = datetime.fromisoformat(
            query["date_et"] + "T10:30:00"
        ).replace(tzinfo=ZoneInfo("America/New_York")).isoformat()
        rows = tuple({
            "symbol": query["symbol"],
            "expiration": "2018-07-13",
            "strike": 260.0,
            "right": right,
            "timestamp": stamp,
            "bid": 2.0, "ask": 2.1, "bid_size": 4, "ask_size": 7,
        } for right in ("CALL", "PUT"))
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={},
        raw_body=raw, response_bytes=len(raw),
        elapsed_seconds=0.1, transport=TRANSPORT,
        library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="a" * 64,
        evidence_encoding=EVIDENCE_ENCODING,
        explicit_no_data=no_data,
    )


def consent(env, *, reader):
    settings, batch, _query, qid, planning, _reserve = env
    return v8.acquire_one_hourly_source(
        settings, batch, qid, reader=reader,
        plan_reader=planning,
        authorize_paid_single_request=True,
        acknowledge_ambiguous_request_no_retry=True,
    )


def test_default_preflight_read_only_and_no_reservation(env):
    settings, batch, query, qid, planning, reserve = env
    result = v8.inspect_single_attempt(
        settings, batch, qid, plan_reader=planning,
    )
    assert result["state"] == "NO_RESERVATION_NO_API"
    assert result["provider_requests"] == 0
    assert result["paid_provider_authority"] is False
    assert not settings.resolved_path(v8.ATTEMPT_REL).exists()
    reserve()
    ready = v8.inspect_single_attempt(
        settings, batch, qid, plan_reader=planning,
    )
    assert ready["state"] == "RESERVED_READY_FOR_EXPLICIT_SINGLE_ATTEMPT"
    assert ready["previous_attempt_marker"] is False
    assert ready["reservation_bytes"] == 128 * 1024**2


@pytest.mark.parametrize(
    "enabled,accepted", [(False, False), (True, False), (False, True)]
)
def test_no_paid_request_without_both_explicit_flags(env, enabled, accepted):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    calls = []
    with pytest.raises(v8.HybridSingleAttemptError, match="EXPLICIT_PAID"):
        v8.acquire_one_hourly_source(
            settings, batch, qid,
            reader=lambda **kwargs: calls.append(kwargs),
            plan_reader=planning,
            authorize_paid_single_request=enabled,
            acknowledge_ambiguous_request_no_retry=accepted,
        )
    assert calls == []
    assert not settings.resolved_path(v8.ATTEMPT_REL).exists()


def test_exactly_one_request_stores_compressed_source_and_fails_retries(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    invoked = []

    def reader(**kwargs):
        # Marker must be durable on disk before the provider sees a request.
        marker, result = v8._paths(settings, qid)
        assert marker.is_file()
        assert not result.exists()
        invoked.append(kwargs)
        return response(query)

    result = consent(env, reader=reader)
    assert result["result_state"] == "SOURCE_ARCHIVED_DIAGNOSTIC"
    assert result["stored_source"]["quote_rows"] == 2
    assert result["simulator_ready"] is False
    assert result["automatic_retry_authorized"] is False
    assert len(invoked) == 1
    assert invoked[0] == {
        "symbol": "SPY", "date_et": "2018-06-11",
        "right": "both", "max_dte": 45, "strike_range": 2,
    }
    source = read_historical_quote_source(
        settings, result["stored_source"]["source_id"],
    )
    assert source["quote_rows"] == 2
    assert source["simulator_ready"] is False
    preview = v8.inspect_single_attempt(
        settings, batch, qid, plan_reader=planning,
    )
    assert preview["state"] == "LOCAL_SOURCE_ALREADY_PRESENT_NO_API"
    with pytest.raises(v8.HybridSingleAttemptError, match="NOT_ELIGIBLE"):
        consent(env, reader=lambda **_: pytest.fail("must not call twice"))
    started, ended = v8._validate_existing(settings, qid)
    assert started["state"] == "POSSIBLY_DISPATCHED_NO_RETRY"
    assert ended["state"] == "SOURCE_ARCHIVED_DIAGNOSTIC"


def test_ambiguous_timeout_records_terminal_and_blocks_next_attempt(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    calls = []

    def timeout(**kwargs):
        calls.append(kwargs)
        raise TimeoutError("simulated ambiguous transport")

    result = consent(env, reader=timeout)
    assert result["result_state"] == "REQUEST_OR_STORAGE_FAILED_NO_RETRY"
    assert result["error_type"] == "TimeoutError"
    assert len(calls) == 1
    assert v8.inspect_single_attempt(
        settings, batch, qid, plan_reader=planning,
    )["state"] == "ATTEMPT_COMPLETED_NO_RETRY"
    with pytest.raises(v8.HybridSingleAttemptError):
        consent(env, reader=timeout)
    assert len(calls) == 1


def test_crash_after_marker_before_terminal_must_remain_indeterminate(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()

    def crash(**kwargs):
        raise KeyboardInterrupt("synthetic fatal process interruption")

    with pytest.raises(KeyboardInterrupt):
        consent(env, reader=crash)
    marker, result = v8._paths(settings, qid)
    assert marker.is_file()
    assert not result.exists()
    assert v8.inspect_single_attempt(
        settings, batch, qid, plan_reader=planning,
    )["state"] == "ATTEMPT_STATUS_UNKNOWN_NO_RETRY"
    with pytest.raises(v8.HybridSingleAttemptError):
        consent(env, reader=crash)


def test_explicit_no_data_is_never_promoted_as_coverage(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    out = consent(env, reader=lambda **kwargs: response(query, no_data=True))
    assert out["result_state"] == "EXPLICIT_NO_DATA_NOT_COVERAGE"
    assert out["stored_source"] is None
    assert not settings.resolved_path(
        "data/options/hybrid/source_store_v2.duckdb"
    ).exists()
    with pytest.raises(v8.HybridSingleAttemptError):
        consent(env, reader=lambda **kwargs: pytest.fail("retry forbidden"))


def test_empty_without_proven_no_data_does_not_store_source(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    fake = response(query, no_data=True)
    object.__setattr__(fake, "explicit_no_data", False)
    out = consent(env, reader=lambda **_: fake)
    assert out["result_state"] == "EMPTY_RESPONSE_UNQUALIFIED"
    assert out["stored_source"] is None


def test_storage_failure_after_provider_call_remains_no_retry(env, monkeypatch):
    settings, batch, query, qid, planning, reserve = env
    reserve()

    def fail_store(*_args, **_kwargs):
        raise OSError("synthetic source persistence failure")

    monkeypatch.setattr(v8, "store_historical_quote_source", fail_store)
    out = consent(env, reader=lambda **_: response(query))
    assert out["result_state"] == "REQUEST_OR_STORAGE_FAILED_NO_RETRY"
    assert out["error_type"] == "OSError"
    with pytest.raises(v8.HybridSingleAttemptError):
        consent(env, reader=lambda **_: response(query))


def test_tampered_attempt_receipt_never_grants_second_call(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    consent(env, reader=lambda **_: response(query, no_data=True))
    marker, _ = v8._paths(settings, qid)
    body = json.loads(marker.read_text())
    body["automatic_retry_authorized"] = True
    marker.write_text(json.dumps(body))
    with pytest.raises(v8.HybridSingleAttemptError, match="DRIFT"):
        v8.inspect_single_attempt(
            settings, batch, qid, plan_reader=planning,
        )


def test_no_call_when_unreserved_or_source_already_present(env):
    settings, batch, query, qid, planning, reserve = env
    with pytest.raises(v8.HybridSingleAttemptError):
        consent(env, reader=lambda **_: pytest.fail("not reserved"))
    store_historical_quote_source(
        settings, query, response=response(query), write=True,
    )
    reserve()
    with pytest.raises(v8.HybridSingleAttemptError):
        consent(env, reader=lambda **_: pytest.fail("existing source"))
    assert not settings.resolved_path(v8.ATTEMPT_REL).exists()


def test_query_id_mismatch_and_minute_adapter_never_call(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    with pytest.raises(v8.HybridSingleAttemptError, match="QUERY_NOT_IN"):
        v8.inspect_single_attempt(
            settings, batch, "a" * 64, plan_reader=planning,
        )
    minute = {**query, "interval": "1m"}
    minute_id = _fingerprint({
        "source_type": "option_history_quote", "query": minute,
    })
    minute_batch = {
        "contract": BATCH_CONTRACT,
        "requests": [{"strategy_key": "TEST_MINUTE", "purpose": "management",
                      "query": minute}],
    }
    with pytest.raises(v8.HybridSingleAttemptError, match="ADAPTER"):
        v8.inspect_single_attempt(
            settings, minute_batch, minute_id, plan_reader=planning,
        )


def test_cli_preview_and_paid_flag_guard(env, monkeypatch, capsys):
    settings, batch, query, qid, planning, reserve = env
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(
        cli, "plan_acquisition_reservations", planning,
    )
    monkeypatch.setattr(
        cli, "inspect_single_attempt",
        lambda *_a, **_kw: v8.inspect_single_attempt(
            settings, batch, qid, plan_reader=planning,
        ),
    )
    assert cli.main(["--demo"]) == 0
    assert "OFFLINE_PREVIEW_NO_API_CALLS" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["--demo", "--authorize-paid-single-hourly-request",
                  "--acknowledge-no-retry-after-ambiguous-attempt"])
    assert not settings.resolved_path(v8.ATTEMPT_REL).exists()


def test_attempt_marker_survives_result_missing_without_retry(env):
    settings, batch, query, qid, planning, reserve = env
    reserve()
    out = consent(env, reader=lambda **_: response(query, no_data=True))
    assert out["result_state"] == "EXPLICIT_NO_DATA_NOT_COVERAGE"
    marker, result = v8._paths(settings, qid)
    result.unlink()
    assert marker.is_file()
    assert v8.inspect_single_attempt(
        settings, batch, qid, plan_reader=planning,
    )["state"] == "ATTEMPT_STATUS_UNKNOWN_NO_RETRY"
    with pytest.raises(v8.HybridSingleAttemptError):
        consent(env, reader=lambda **_: pytest.fail("retry forbidden"))
