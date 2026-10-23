from __future__ import annotations

from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from packages.providers.thetadata.client import _canonical_bytes
from scripts import review_options_native_spy_standard_expiration_scope_v1 as scope


def synthetic_source(tmp_path: Path, monkeypatch, *, corrupt: bool = False):
    source = tmp_path / "raw"
    source.mkdir()
    dates = ["2025-06-20", "2025-07-24", "2025-07-25", "2025-06-08"]
    rows = []
    for i in range(132):
        exp = dates[i % 4]
        stamp = ("2025-06-09T10:00:00.001000-04:00" if i == 0
                 else "2025-06-09T09:59:59.996000-04:00")
        for right in ("CALL", "PUT"):
            rows.append({
                "symbol": "SPY", "expiration": exp, "right": right,
                "strike": float(500 + i),
                "timestamp": stamp,
                "bid": 2.00, "ask": 2.05,
                "bid_size": 10, "ask_size": 10,
                "bid_exchange": 1, "ask_exchange": 1,
                "bid_condition": 0, "ask_condition": 0,
            })
    raw = _canonical_bytes(rows)
    (source / "single_quote.json").write_bytes(raw)
    monkeypatch.setattr(scope, "PINNED_BODY_SHA", hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(scope, "audit_saved_quote", lambda p, write: {
        "replay": "REPRODUCED",
        "replay_reason": "OUT_OF_SCOPE_OPTION_EXPIRATION",
        "fingerprint": scope.PINNED_SCHEMA_AUDIT + "0"*48,
        "original_sha256": scope.PINNED_BODY_SHA,
        "rows": 264,
        "rights": {"CALL": 132, "PUT": 132},
        "missing_required": [],
        "provider_requests": 0,
        "original_report_fingerprint": "f"*64,
    })
    if corrupt:
        (source / "single_quote.json").write_bytes(raw + b" ")
    return tmp_path / "summary.json"


def test_expiration_scope_preserves_out_of_scope_and_boundary(tmp_path, monkeypatch):
    path = synthetic_source(tmp_path, monkeypatch)
    report = scope.inspect_saved_expiration_scope(path, write_report=True)
    assert report["raw_rows"] == 264
    assert report["requested_max_dte"] == 45
    assert report["expiration_buckets"] == {
        "expired_before_decision": 66, "over_max_dte": 66,
        "within_requested_dte": 132,
    }
    by_date = {r["expiration"]: r for r in report["per_expiration"]}
    assert by_date["2025-07-24"]["dte_calendar_days"] == 45
    assert by_date["2025-07-24"]["scope"] == "within_requested_dte"
    assert by_date["2025-07-25"]["dte_calendar_days"] == 46
    assert by_date["2025-07-25"]["scope"] == "over_max_dte"
    assert by_date["2025-06-08"]["scope"] == "expired_before_decision"
    assert by_date["2025-07-24"]["shared_call_put_strikes"] == 33
    assert report["other_schema_and_clock_anomalies"]["quote_after_decision_clock"] == 2
    assert report["source_accepted"] is False
    assert report["further_paid_requests_authorized"] is False
    assert report["provider_requests"] == report["protected_outcomes_read"] == 0
    saved = Path(report["saved_report"])
    assert saved.exists()
    assert scope.inspect_saved_expiration_scope(
        path, write_report=True
    )["fingerprint"] == report["fingerprint"]
    assert json.loads(saved.read_text())["fingerprint"] == report["fingerprint"]


def test_changed_pinned_source_bytes_fail_before_analysis(tmp_path, monkeypatch):
    path = synthetic_source(tmp_path, monkeypatch, corrupt=True)
    with pytest.raises(ValueError, match="ORIGINAL_2025_QUOTE_SHA_DRIFT"):
        scope.inspect_saved_expiration_scope(path, write_report=True)
    assert not list(tmp_path.glob("offline_expiration_scope_v1_*.json"))


def test_changed_original_schema_replay_fails_closed(tmp_path, monkeypatch):
    path = synthetic_source(tmp_path, monkeypatch)
    monkeypatch.setattr(scope, "PINNED_SCHEMA_AUDIT", "0"*16)
    with pytest.raises(ValueError, match="PINNED_2025_SOURCE_AUDIT_NOT_MATCHED"):
        scope.inspect_saved_expiration_scope(path)


def test_no_scope_reclassification_from_a_valid_45_day_boundary(tmp_path, monkeypatch):
    path = synthetic_source(tmp_path, monkeypatch)
    report = scope.inspect_saved_expiration_scope(path)
    assert report["first_out_of_scope_original_order"]["scope"] == "over_max_dte"
    assert report["first_out_of_scope_original_order"]["dte_calendar_days"] == 46
    assert report["all_returned_rows_within_requested_dte"] is False
    assert report["split_subset_strategy_admissible"] is False
