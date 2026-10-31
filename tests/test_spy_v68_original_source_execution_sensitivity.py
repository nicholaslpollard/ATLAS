from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import gzip
import hashlib
import json

import pytest

from scripts import run_spy_v68_original_source_execution_sensitivity as v68
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


def fixture_parents(tmp_path):
    rows = []
    days = [date(2025, 6, 9) + timedelta(days=i) for i in range(12)]
    for day in days:
        if day.weekday() not in range(5):
            continue
        name = day.isoformat()
        selected = name in v68.SIX_SIGNALS
        req = {"method": "option_history_exact_quote_tape", "kwargs": {
            "symbol": "SPY", "date_et": name, "expiration": name,
            "strike": "600", "right": "call",
            "start_time_et": "09:35:00.000",
            "end_time_et": "15:30:00.000", "interval": "1s"
        }} if selected else None
        qid = _fingerprint(req) if req else None
        sha = "f" * 64 if selected else None
        signal = {"session": name, "selected_contract": {"symbol": "SPY"} if selected else None}
        original = v68.signed({
            "session": name, "signal": signal,
            "status": "NO_ENTRY" if selected else "NO_SIGNAL",
            "censor_reason": "ACTION_ASK_PRICE_CHANGE_OVER_LIMIT" if selected else
                             "WEEKDAY_OUTSIDE_MWF_VERSION",
            "source_query_id": qid, "source_sha256": sha,
            "trade_net_pnl": None, "actual_fills": 0,
            "publication_verified": False, "valid_historical_alpha": False,
            "quote_reference_not_broker_execution": True,
            "policy": {"lag_seconds": 1, "max_adverse_pct": "1"},
        })
        rows.append(v68.signed({
            "session": name,
            "selected_contract": {"symbol": "SPY"} if selected else None,
            "exact_option_requirement": req,
            "exact_option_receipt": {"query_id": qid, "archive_sha256": sha,
                                     "state": "ARCHIVED"} if selected else None,
            "standalone_replay_report": original,
        }))
    assert len(rows) == 10
    v65 = v68.signed({
        "contract": v68.PARENT_V65, "start": "2025-06-09",
        "end": "2025-06-20", "weekdays_in_calendar_scope": 10,
        "provider_requests": 0, "broker_orders": 0, "session_reports": rows,
    })
    v67 = v68.signed({
        "contract": v68.PARENT_V67,
        "status": "COMPLETE_SOURCE_AND_OFFLINE_CENSUS",
        "v65_refreshed_fingerprint": v65["fingerprint"],
        "v65_refreshed_source_counts": {"ARCHIVED": 6},
        "v66_result_counts": {"SOURCE_ARCHIVED_AND_REVERIFIED": 3},
    })
    v67_path, v65_path = tmp_path / "v67.json", tmp_path / "v65.json"
    v67_path.write_text(json.dumps(v67), encoding="utf-8")
    v65_path.write_text(json.dumps(v65), encoding="utf-8")
    return v67_path, v65_path, v67, v65


def fixture_replay(signal, source, *, starting_cash, lag_seconds, max_adverse_pct):
    assert starting_cash == "25000"
    assert (lag_seconds, max_adverse_pct) in v68.POLICIES
    day = signal["session"]
    selected = signal["selected_contract"] is not None
    quote = source if selected else None
    if selected:
        assert quote is not None
    # Exact original reproduction of 1s/1pct synthetic result.
    status = (
        "NO_ENTRY" if selected else "NO_SIGNAL"
    ) if (lag_seconds, max_adverse_pct) == (1, "1") else (
        "CLOSED_QUOTE_REFERENCE" if selected else "NO_SIGNAL"
    )
    reason = (
        "ACTION_ASK_PRICE_CHANGE_OVER_LIMIT" if selected else
        "WEEKDAY_OUTSIDE_MWF_VERSION"
    ) if (lag_seconds, max_adverse_pct) == (1, "1") else (
        None if selected else "WEEKDAY_OUTSIDE_MWF_VERSION"
    )
    res = {
        "session": day, "signal": signal, "status": status,
        "censor_reason": reason,
        "source_query_id": quote["query_id"] if quote else None,
        "source_sha256": quote["source_sha256"] if quote else None,
        "trade_net_pnl": "25.00" if status == "CLOSED_QUOTE_REFERENCE" else None,
        "actual_fills": 0, "publication_verified": False,
        "valid_historical_alpha": False, "quote_reference_not_broker_execution": True,
        "policy": {"lag_seconds": lag_seconds, "max_adverse_pct": max_adverse_pct},
    }
    return v68.signed(res)


def cache_get(settings, qid):
    return {"cache_evidence": "CACHE_HIT", "source": settings[qid]}


def accepted_settings(v65):
    return {
        row["exact_option_receipt"]["query_id"]: {
            "status": "CACHE_HIT",
            "query_id": row["exact_option_receipt"]["query_id"],
            "source_sha256": row["exact_option_receipt"]["archive_sha256"],
            "exact_requirement": row["exact_option_requirement"],
            "source_rows": ({"bid": "1.0", "ask": "1.01"},),
        }
        for row in v65["session_reports"] if row["selected_contract"]
    }


def test_six_policy_census_preserves_all_original_sources_and_events(tmp_path, monkeypatch):
    p67, p65, parent67, parent65 = fixture_parents(tmp_path)
    monkeypatch.setattr(v68, "PARENT_V67_SHA", parent67["fingerprint"])
    monkeypatch.setattr(v68, "PARENT_V65_SHA", parent65["fingerprint"])
    calls, progress = [], []
    settings = accepted_settings(parent65)
    def read(settings_, qid):
        calls.append(qid)
        return cache_get(settings_, qid)
    out = tmp_path / "matrix"
    result = v68.run(
        p67, p65, out, settings_fn=lambda *args: settings,
        cache_read=read, replay=fixture_replay, progress=progress.append,
    )
    assert result["status"] == "COMPLETE_OFFLINE_SENSITIVITY_CENSUS"
    assert result["policy_count"] == 6
    assert result["scenario_session_replays"] == 60
    assert result["verified_original_option_sources"] == 6
    assert result["default_1s_1pct_replay_exactly_reproduced"] is True
    assert result["provider_requests"] == result["broker_orders"] == 0
    assert len(calls) == 6
    assert len([x for x in progress if x.startswith("PROGRESS_")]) == 10
    assert len(result["policies"]) == 6
    for row in result["policies"]:
        b = (out / row["file"]).read_bytes()
        assert hashlib.sha256(b).hexdigest() == row["gzip_sha256"]
        doc = json.loads(gzip.decompress(b))
        assert doc["fingerprint"] == row["report_fingerprint"]
        assert doc["fingerprint"] == _fingerprint({
            k: v for k, v in doc.items() if k != "fingerprint"
        })
        assert len(doc["session_reports"]) == 10
        assert doc["broker_orders"] == 0
        if row["policy_id"] == "lag1s_limit1pct":
            assert row["baseline_replay_fingerprints_reproduced"] == 10
            assert row["status_counts"] == {"NO_ENTRY": 6, "NO_SIGNAL": 4}
        else:
            assert row["status_counts"] == {
                "CLOSED_QUOTE_REFERENCE": 6, "NO_SIGNAL": 4
            }
            assert row["closed_trade_pnl_sum_not_cumulative_account"] == "150.00"


def test_parent_sha_or_session_change_refuses_all_cache_calls(tmp_path, monkeypatch):
    p67, p65, parent67, parent65 = fixture_parents(tmp_path)
    monkeypatch.setattr(v68, "PARENT_V67_SHA", parent67["fingerprint"])
    monkeypatch.setattr(v68, "PARENT_V65_SHA", parent65["fingerprint"])
    parent65["session_reports"][1]["session"] = "2045-01-01"
    p65.write_text(json.dumps(parent65), encoding="utf-8")
    with pytest.raises(v68.V68Error, match="PARENT_OR_FINGERPRINT_CHANGED"):
        v68.run(p67, p65, tmp_path / "out",
                settings_fn=lambda *args: pytest.fail("must not inspect cache"))


def test_missing_original_source_is_blocker_not_fabricated_no_entry(tmp_path, monkeypatch):
    p67, p65, parent67, parent65 = fixture_parents(tmp_path)
    monkeypatch.setattr(v68, "PARENT_V67_SHA", parent67["fingerprint"])
    monkeypatch.setattr(v68, "PARENT_V65_SHA", parent65["fingerprint"])
    settings = accepted_settings(parent65)
    out = tmp_path / "out"
    with pytest.raises(v68.V68Error, match="SOURCE_ACQUISITION_REQUIRED"):
        v68.run(p67, p65, out, settings_fn=lambda *args: settings,
                cache_read=lambda *args: {"cache_evidence": "EXACT_QUERY_NOT_IN_INDEX",
                                          "source": None},
                replay=lambda *args, **kwargs: pytest.fail("must not fabricate"),
                progress=lambda s: None)
    assert not out.exists()


def test_immutable_output_refuses_overwrite(tmp_path, monkeypatch):
    p67, p65, parent67, parent65 = fixture_parents(tmp_path)
    monkeypatch.setattr(v68, "PARENT_V67_SHA", parent67["fingerprint"])
    monkeypatch.setattr(v68, "PARENT_V65_SHA", parent65["fingerprint"])
    settings = accepted_settings(parent65)
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(v68.V68Error, match="IMMUTABLE_OUTPUT_ALREADY_EXISTS"):
        v68.run(p67, p65, out, settings_fn=lambda *args: settings,
                cache_read=cache_get,
                replay=lambda *args, **kwargs: pytest.fail("must not replay"),
                progress=lambda s: None)
