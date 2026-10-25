from __future__ import annotations

from datetime import date
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from packages.data import hybrid_options_saved_aal_audit_v1 as audit
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.providers.thetadata.client import _canonical_bytes


class FakeSettings:
    def __init__(self, root: Path):
        self.root = root
    def resolved_path(self, name):
        return self.root / name
    def assert_external_storage_binding(self, binding):
        assert binding == "options"


def call_row():
    day = "2021-11-30"
    params = {
        "symbol": "AAL", "start_date": "20211130",
        "end_date": "20211130", "time_of_day": "09:35:00.000",
        "expiration": "*", "strike": "*", "right": "call",
        "max_dte": 75, "strike_range": None, "format": "json",
    }
    result = _entry(
        "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES",
        "a" * 64, "b" * 64,
        {"endpoint": "/v3/option/at_time/quote", "params": params},
        role="0935_CALL_ENTRY_DISCOVERY", anchor=True,
    )
    result["priority"] = 1
    result["query_id"] = audit.AAL_QUERY_ID
    # Fixture fingerprints vary from accepted V9; use genuine request hash
    # checking in production and synthetic row binding in this focused test.
    return result


@pytest.fixture
def setup_aal(tmp_path, monkeypatch):
    s = FakeSettings(tmp_path)
    row = call_row()
    from packages.data.hybrid_options_at_time_source_gate_v1 import validate_exact_request
    # Stub already-verified frozen row from the accepted V11 preflight.
    monkeypatch.setattr(audit, "validate_exact_request", lambda _: {
        "symbol": "AAL", "date_et": "2021-11-30",
        "time_of_day_et": "09:35:00.000",
        "right": "call", "max_dte": 75, "strike_range": None,
    })
    monkeypatch.setattr(
        audit, "_load_full_manifest",
        lambda *_: {
            "requests": [row],
            "manifest_fingerprint": "c" * 64,
        },
    )
    archive_subdir = (
        "data/options/hybrid/at_time_qualification_v1/source/ab"
    )
    folder = s.resolved_path(archive_subdir)
    folder.mkdir(parents=True)
    rows = []
    for exp, strike in [("2022-01-14", 18.0), ("2022-04-15", 19.0)]:
        rows.append({
            "symbol": "AAL", "expiration": exp,
            "strike": strike, "right": "call",
            "timestamp": "2021-11-30T09:34:50-05:00",
            "bid": 0.8, "ask": 0.9, "bid_size": 1, "ask_size": 2,
            "bid_exchange": 1, "bid_condition": 0,
            "ask_exchange": 1, "ask_condition": 0,
        })
    raw = _canonical_bytes(rows)
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    digest = hashlib.sha256(raw).hexdigest()
    path = folder / (digest + ".json.gz")
    path.write_bytes(packed)
    original = {
        "relative_archive": archive_subdir.replace("data/options/", "") +
            "/" + path.name,
        "original_sha256": digest,
        "compressed_sha256": hashlib.sha256(packed).hexdigest(),
        "original_bytes": len(raw), "compressed_bytes": len(packed),
        "observed_rows": 2, "full_original_retained": True,
        "source_coverage_proven": False, "simulator_ready": False,
    }
    monkeypatch.setattr(
        audit, "_validate_attempt_state",
        lambda *_: (
            {"fingerprint": "d" * 64, "source_request_id": audit.AAL_QUERY_ID,
             "query": audit.validate_exact_request(row)},
            {"fingerprint": "e" * 64,
             "source_request_id": audit.AAL_QUERY_ID,
             "state": "SOURCE_ARCHIVED_QUARANTINED_DTE",
             "diagnostic_state": "QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION",
             "at_time_sdk_max_dte_forwarding_proven": False,
             "source_coverage_proven": False, "simulator_ready": False,
             "archive": original},
        ),
    )
    return s, path, row


def test_saved_aal_raw_is_lossless_and_dte_quarantined(setup_aal):
    s, archive, row = setup_aal
    report = audit.audit_saved_aal(s, Path("v9"), Path("source"))
    assert report["total_original_rows"] == 2
    assert report["in_dte_rows"] == 1
    assert report["over_dte_rows"] == 1
    assert report["dte_buckets"]["76_180"] == 1
    assert report["dte_buckets"]["15_45"] == 1
    assert report["positive_two_sided_displayed_size_rows"] == 2
    assert report["sdk_vs_server_cause_proven"] is False
    assert report["source_coverage_proven"] is False
    assert report["provider_requests"] == 0
    assert report["fingerprint"] == audit._fingerprint({
        k: v for k, v in report.items() if k != "fingerprint"
    })


def test_corrupted_gzip_detected_without_call_or_rewrite(setup_aal):
    s, path, row = setup_aal
    path.write_bytes(b"corrupted")
    with pytest.raises(audit.HybridAalAuditError):
        audit.audit_saved_aal(s, Path("v9"), Path("source"))
    assert path.read_bytes() == b"corrupted"


def test_corrupted_original_hash_fails(setup_aal):
    s, path, row = setup_aal
    path.write_bytes(gzip.compress(b"bad", compresslevel=9, mtime=0))
    with pytest.raises(audit.HybridAalAuditError):
        audit.audit_saved_aal(s, Path("v9"), Path("source"))
