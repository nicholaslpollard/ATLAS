from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from packages.data.options_native_spy_standard_canary_v1 import run_single_canary
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts.audit_options_native_spy_standard_one_quote_v1 import audit_saved_quote


class _Settings:
    def __init__(self, root: Path):
        self.root = root
    def assert_external_storage_binding(self, category: str):
        assert category == "options"
    def resolved_path(self, relative: str):
        return self.root / relative


def _response(date_et: str, *, field: str = "created", future: bool = False):
    day = date(int(date_et[:4]), int(date_et[4:6]), int(date_et[6:]))
    clock = datetime.combine(day, datetime.min.time().replace(hour=10),
                             ZoneInfo("America/New_York"))
    stamp = (clock + timedelta(seconds=1) if future
             else clock - timedelta(seconds=1)).isoformat()
    expiration = (day + timedelta(days=35)).isoformat()
    rows = tuple({
        "symbol": "SPY", "expiration": expiration, "strike": 500.0,
        "right": right, field: stamp,
        "bid_size": 5, "bid_exchange": 1, "bid": 5.0,
        "bid_condition": 0, "ask_size": 7, "ask_exchange": 1,
        "ask": 5.10, "ask_condition": 0,
    } for right in ("CALL", "PUT"))
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=rows, headers={}, response_bytes=len(raw),
        elapsed_seconds=0.1, raw_body=raw, transport=TRANSPORT,
        library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="a"*64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
    )


def _saved_canary(tmp_path, *, field="created", future=False):
    requests = []
    def reader(**kw):
        requests.append(kw)
        return _response(kw["date_et"], field=field, future=future)
    report = run_single_canary(
        _Settings(tmp_path), reader=reader,
        authorize_one_standard_quote=True,
        confirm_thetadata_standard=True,
        acknowledge_one_quote_method_call=True,
    )
    assert report["provider_result"] == "SOURCE_SCHEMA_OR_CLOCK_UNQUALIFIED"
    assert len(requests) == 1
    return Path(report["report_path"]), requests


def test_offline_replay_identifies_created_instead_of_timestamp_without_gets(tmp_path):
    saved, requests = _saved_canary(tmp_path)
    summary_before = saved.read_bytes()
    body = saved.parent / "raw" / "single_quote.json"
    body_before = body.read_bytes()
    audit = audit_saved_quote(saved, write=True)
    assert audit["rows"] == 2
    assert audit["replay"] == "REPRODUCED"
    assert audit["replay_reason"] == "QUOTE_REQUIRED_FIELDS_MISSING"
    assert audit["missing_required"] == ["timestamp"]
    assert audit["clock_columns"]["created"]["count"] == 2
    assert audit["clock_columns"]["created"]["first_three"][0].startswith("2025-06-09")
    assert audit["source_accepted"] is False
    assert audit["provider_requests"] == 0
    assert len(requests) == 1
    assert saved.read_bytes() == summary_before and body.read_bytes() == body_before
    assert audit_saved_quote(saved, write=True)["fingerprint"] == audit["fingerprint"]
    assert json.loads(Path(audit["saved_report"]).read_text())["fingerprint"] == audit["fingerprint"]


def test_future_quote_with_timestamp_is_reproduced_offline(tmp_path):
    saved, requests = _saved_canary(tmp_path, field="timestamp", future=True)
    audit = audit_saved_quote(saved)
    assert audit["replay"] == "REPRODUCED"
    assert audit["replay_reason"] == "FUTURE_OR_WRONG_SESSION_QUOTE"
    assert audit["missing_required"] == []
    assert audit["clock_columns"]["timestamp"]["count"] == 2
    assert len(requests) == 1


def test_altered_original_quote_body_does_not_pass_sha_binding(tmp_path):
    saved, requests = _saved_canary(tmp_path)
    body = saved.parent / "raw" / "single_quote.json"
    data = bytearray(body.read_bytes())
    data[0] = ord("{")
    body.write_bytes(data)
    with pytest.raises(ValueError, match="ORIGINAL_PROVIDER_BODY_SHA_DRIFT"):
        audit_saved_quote(saved, write=False)
    assert len(requests) == 1


def test_altered_original_report_fingerprint_fails_closed(tmp_path):
    saved, requests = _saved_canary(tmp_path)
    obj = json.loads(saved.read_text())
    obj["requested_date_et"] = "20250610"
    saved.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="ORIGINAL_CANARY_SCOPE_OR_STATUS_DRIFT"):
        audit_saved_quote(saved)
    assert len(requests) == 1
