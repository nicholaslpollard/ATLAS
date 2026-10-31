from __future__ import annotations

from datetime import date
from pathlib import Path
import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts import run_spy_v69_source_first_multimonth_census as v69


def fake_day(day, idx, source_state):
    chosen = day in ("2025-06-09", "2025-06-11")
    signal = v69.signed({
        "session": day,
        "selected_contract": {
            "symbol": "SPY", "date_et": day,
            "expiration": day, "strike": "600", "right": "call"
        } if chosen else None,
    })
    requirement = {
        "provider": "thetadata", "method": "option_history_exact_quote_tape",
        "kwargs": {
            "symbol": "SPY", "date_et": day, "expiration": day,
            "strike": "600", "right": "call",
            "start_time_et": "09:45:00.000",
            "end_time_et": "15:30:00.000", "interval": "1s",
        },
    } if chosen else None
    receipt = {
        "query_id": _fingerprint(requirement),
        "state": source_state,
        "archive_sha256": "e" * 64 if source_state == "ARCHIVED" else None,
    } if chosen else None
    replay = v69.signed({
        "session": day,
        "signal": signal,
        "source_query_id": receipt["query_id"] if receipt else None,
        "source_sha256": receipt["archive_sha256"] if receipt else None,
        "status": "CLOSED_QUOTE_REFERENCE"
                  if source_state == "ARCHIVED" else
                  "NO_ENTRY" if chosen else "NO_SIGNAL",
        "actual_fills": 0, "events": [],
    })
    return v69.signed({
        "session": day, "day_index": idx,
        "signal_fingerprint": signal["fingerprint"],
        "native_minute_source_sha256": "a" * 64,
        "selected_contract": signal["selected_contract"],
        "exact_option_requirement": requirement,
        "exact_option_receipt": receipt,
        "standalone_replay_report": replay,
        "standalone_replay_disposition": replay["status"],
    })


def fake_audit_from_registry(registry):
    def audit(first, last, output):
        rows = [fake_day(x, i, registry.get(x)) for i, x in enumerate(
            ("2025-06-09", "2025-06-10", "2025-06-11"), 1
        ) if first.isoformat() <= x <= last.isoformat()]
        doc = v69.signed({
            "contract": v69.V65,
            "start": first.isoformat(), "end": last.isoformat(),
            "provider_requests": 0, "broker_orders": 0,
            "session_reports": rows,
        })
        output.write_text(json.dumps(doc), encoding="utf8")
        return doc
    return audit


def test_dynamic_requirements_fetch_all_and_verify_after_replay(tmp_path):
    state = {
        "2025-06-09": "NOT_REGISTERED",
        "2025-06-11": "NOT_REGISTERED",
    }
    called = []
    progress = []
    def resolve(settings, version, wanted, *, continue_on_error, on_progress):
        requests = list(wanted)
        assert continue_on_error is True
        assert len(requests) == 2
        assert all(x["method"] == "option_history_exact_quote_tape" for x in requests)
        assert {x["kwargs"]["date_et"] for x in requests} == set(state)
        for req in requests:
            state[req["kwargs"]["date_et"]] = "ARCHIVED"
            on_progress("provider_dispatch", {
                "query_id": _fingerprint({
                    "provider": "thetadata", "method": req["method"],
                    "kwargs": req["kwargs"]
                }), "date_et": req["kwargs"]["date_et"],
            })
            on_progress("source_done", {
                "query_id": "a" * 64, "status": "FETCHED_AND_ARCHIVED",
            })
        called.extend(requests)
        return {"source_uses_requested": len(requests),
                "provider_dispatch_attempts": len(requests)}
    out = tmp_path / "v69"
    result = v69.run(date(2025,6,9),date(2025,6,11),out,
                     audit=fake_audit_from_registry(state),
                     resolve=resolve,emit=progress.append)
    assert len(called) == 2
    assert result["status"] == "COMPLETE_SOURCE_CENSUS_QUOTE_REFERENCE_ONLY"
    assert result["chunks"] == 1 and result["weekdays"] == 3
    chunk = json.loads((out / "chunk_0001.summary.json").read_text())
    assert chunk["source_state_counts"] == {"ARCHIVED": 2}
    assert chunk["qualified_replay_status_counts"] == {
        "CLOSED_QUOTE_REFERENCE": 2, "NO_SIGNAL": 1
    }
    assert chunk["source_censor_not_counted_as_no_entry"] is True
    assert sum(x.startswith("PROGRESS_") for x in progress) == 10


def test_ambiguous_provider_dispatch_still_allows_other_new_source(tmp_path):
    state = {
        "2025-06-09": "FAILED_RETRYABLE",
        "2025-06-11": "NOT_REGISTERED",
    }
    def resolve(settings, version, wanted, *, continue_on_error, on_progress):
        requests = list(wanted)
        assert len(requests) == 2
        assert continue_on_error
        on_progress("source_blocked", {
            "query_id": "a"*64, "status": "SOURCE_RECONCILIATION_REQUIRED"
        })
        state["2025-06-11"] = "ARCHIVED"
        on_progress("source_done", {
            "query_id": "b"*64, "status": "FETCHED_AND_ARCHIVED"
        })
        return {"source_uses_requested": 2, "provider_dispatch_attempts": 1}
    out = tmp_path / "v69"
    res = v69.run(date(2025,6,9),date(2025,6,11),out,
                  audit=fake_audit_from_registry(state),resolve=resolve,
                  emit=lambda msg: None)
    assert res["status"] == "COMPLETE_WITH_SOURCE_OR_STOCK_BLOCKERS"
    chunk = json.loads((out / "chunk_0001.summary.json").read_text())
    assert chunk["source_state_counts"] == {
        "ARCHIVED": 1, "FAILED_RETRYABLE": 1,
    }
    assert chunk["qualified_replay_status_counts"] == {
        "CLOSED_QUOTE_REFERENCE": 1, "NO_SIGNAL": 1,
    }
    assert len(chunk["unresolved_source_requirements"]) == 1
    assert chunk["unresolved_source_requirements"][0]["not_a_trade_rejection"]


def test_original_underlying_source_blocker_no_option_dispatch(tmp_path):
    out = tmp_path / "v69"
    calls = []
    def no_native(*args):
        raise FileNotFoundError("SPY original month missing")
    def wrong_provider(*args, **kwargs):
        calls.append("provider")
        pytest.fail("missing underlying must block option requests")
    doc = v69.run(date(2025,6,9),date(2025,6,11),out,
                  audit=no_native,resolve=wrong_provider,
                  emit=lambda msg: None)
    assert not calls
    assert doc["status"] == "COMPLETE_WITH_SOURCE_OR_STOCK_BLOCKERS"
    blocker = json.loads((out / "chunk_0001.blocked.json").read_text())
    assert blocker["status"] == "UNDERLYING_OR_ORIGINAL_PREFLIGHT_BLOCKED"
    assert blocker["stock_source_acquisition_or_geometry_review_required"]
    assert blocker["option_source_queries_dispatched"] == 0


def test_immutable_output_prevents_any_calls(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    with pytest.raises(v69.V69Error, match="OUTPUT_ALREADY_EXISTS"):
        v69.run(date(2025,6,9),date(2025,6,11),out,
                audit=lambda *args: pytest.fail("no original read"),
                resolve=lambda *args: pytest.fail("no provider"))


def test_missing_source_demand_cannot_be_counted_as_genuine_trade_rejection():
    before = v69.signed({
        "contract": v69.V65, "start": "2025-06-09", "end": "2025-06-09",
        "provider_requests": 0,"broker_orders":0,
        "session_reports": [fake_day("2025-06-09",1,"NOT_REGISTERED")],
    })
    after = v69.signed({
        "contract": v69.V65, "start": "2025-06-09", "end": "2025-06-09",
        "provider_requests": 0,"broker_orders":0,
        "session_reports": [fake_day("2025-06-09",1,"FAILED_RETRYABLE")],
    })
    x = v69.summarize_chunk(
        before,after,{"source_uses_requested":1},date(2025,6,9),
        date(2025,6,9),1,
    )
    assert x["qualified_replay_status_counts"] == {}
    assert x["unresolved_source_requirements"][0]["status"] == (
        "SOURCE_REQUIREMENT_UNRESOLVED"
    )
