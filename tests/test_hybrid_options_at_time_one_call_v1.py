from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data import hybrid_options_at_time_one_call_v1 as v11
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import qualify_one_hybrid_at_time_option_source_v1 as cli


class FakeSettings:
    def __init__(self, root: Path):
        self.root = root
        (root / "data/options/manifests").mkdir(parents=True)

    def assert_external_storage_binding(self, what):
        assert what == "options"

    def resolved_path(self, relative):
        return self.root / relative


def one_request(symbol: str, day: str, priority: int) -> dict:
    stamp = day.replace("-", "")
    original = {
        "endpoint": "/v3/option/at_time/quote",
        "params": {
            "symbol": symbol, "start_date": stamp, "end_date": stamp,
            "time_of_day": "09:35:00.000", "right": "call",
            "max_dte": 75, "strike_range": None,
            "expiration": "*", "strike": "*", "format": "json",
        },
    }
    row = _entry(
        "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES", "a" * 64,
        ("b" * 63 + str(priority)),
        original, role="0935_CALL_ENTRY_DISCOVERY", anchor=True,
    )
    row["priority"] = priority
    return row


@pytest.fixture
def sample(tmp_path, monkeypatch):
    settings = FakeSettings(tmp_path)
    rows = [
        one_request("AAPL", "2021-01-04", 1),
        one_request("MSFT", "2021-06-07", 2),
        one_request("SPY", "2021-12-27", 3),
    ]
    manifest = {
        "manifest_fingerprint": v11.PINNED_MANIFEST_FINGERPRINT,
        "requests": rows,
    }
    monkeypatch.setattr(v11, "_load_full_manifest", lambda *_: manifest)
    monkeypatch.setattr(
        v11, "_storage_capacity", lambda *_: {
            "storage_status": "SAFE",
            "safe_available_bytes": 119 * 1024**3,
        },
    )
    monkeypatch.setattr(
        v11, "_outstanding_reservations",
        lambda *_: {"count": 0, "bytes": 0},
    )
    return settings, Path("unused_v9.json"), Path("unused_candidate.json"), rows


def fake_response(row, *, over=False, corrupt=False, no_data=False):
    if no_data:
        rows = ()
    else:
        day = row["date_et"]
        dt = datetime.fromisoformat(day)
        expiration = (
            dt.replace(month=4, day=30).date().isoformat()
            if over else
            dt.replace(month=2, day=19).date().isoformat()
        )
        stamp = day + "T09:34:59-05:00"
        rows = ({
            "symbol": row["symbol"],
            "expiration": expiration, "strike": 130.0,
            "right": "call", "timestamp": stamp,
            "bid": 4.0, "ask": 4.1,
            "bid_size": 5, "ask_size": 6,
            "bid_exchange": 1, "ask_exchange": 1,
            "bid_condition": 0, "ask_condition": 0,
        },)
        if corrupt:
            rows[0]["ask"] = 2.0
    raw = _canonical_bytes(rows)
    return ThetaDataResponse(
        http_status=200, rows=tuple(rows), headers={},
        response_bytes=len(raw), raw_body=raw,
        elapsed_seconds=0.1, transport=TRANSPORT,
        library_version=TARGET_LIBRARY_VERSION,
        evidence_encoding=EVIDENCE_ENCODING,
        provider_environment_fingerprint="a" * 64,
        explicit_no_data=no_data,
    )


def authorize(sample, reader, *, index=0):
    settings, manifest, candidate, rows = sample
    return v11.run_one_qualification(
        settings, manifest, candidate,
        query_id=rows[index]["query_id"], reader=reader,
        authorize_one_paid_diagnostic_call=True,
        acknowledge_max_dte_unproven=True,
        acknowledge_no_retry_after_ambiguity=True,
    )


def test_readonly_preview_selects_oldest_2021_anchor(sample):
    settings, manifest, candidate, rows = sample
    preview = v11.inspect_one_qualification(settings, manifest, candidate)
    assert preview["status"] == "ELIGIBLE_FOR_SEPARATE_EXPLICIT_ONE_CALL_ONLY"
    assert preview["source_request_id"] == rows[0]["query_id"]
    assert preview["qualifying_anchor"]["date_et"] == "2021-01-04"
    assert len(preview["eligible_2021_anchors"]) == 3
    assert preview["provider_requests"] == 0
    assert preview["paid_provider_authority"] is False
    assert preview["sdk_max_dte_forwarding_proven"] is False
    assert not settings.resolved_path(v11.ROOT_REL).exists()


@pytest.mark.parametrize("flags", [
    (False, False, False),
    (True, False, True),
    (False, True, True),
    (True, True, False),
])
def test_all_three_approvals_required_before_file_or_sdk(sample, flags):
    settings, manifest, candidate, rows = sample
    invoked = []
    with pytest.raises(v11.HybridAtTimeQualificationError, match="THREE_EXPLICIT"):
        v11.run_one_qualification(
            settings, manifest, candidate,
            query_id=rows[0]["query_id"],
            reader=lambda **k: invoked.append(k),
            authorize_one_paid_diagnostic_call=flags[0],
            acknowledge_max_dte_unproven=flags[1],
            acknowledge_no_retry_after_ambiguity=flags[2],
        )
    assert invoked == []
    assert not settings.resolved_path(v11.ROOT_REL).exists()


def test_only_three_frozen_2021_anchors_eligible(sample):
    settings, manifest, candidate, rows = sample
    with pytest.raises(v11.HybridAtTimeQualificationError, match="QUERY_NOT_A"):
        v11.inspect_one_qualification(
            settings, manifest, candidate, query_id="d" * 64,
        )
    with pytest.raises(v11.HybridAtTimeQualificationError, match="EXACT"):
        v11.inspect_one_qualification(
            settings, manifest, candidate, query_id="not-a-query",
        )


def test_one_paid_call_only_after_durable_marker(sample):
    settings, manifest, candidate, rows = sample
    actual = []
    def reader(**kwargs):
        started, terminal = v11._paths(settings)
        assert started.is_file() and not terminal.exists()
        actual.append(kwargs)
        return fake_response(rows[0])
    result = authorize(sample, reader)
    assert len(actual) == 1
    assert actual[0] == {
        "symbol": "AAPL", "date_et": "2021-01-04",
        "time_of_day_et": "09:35:00.000",
        "right": "call", "max_dte": 75, "strike_range": None,
    }
    assert result["status"] == "SOURCE_ARCHIVED_DIAGNOSTIC_ONLY"
    assert result["diagnostic_state"] == "IN_SCOPE_OBSERVED_NOT_EXECUTABLE"
    assert result["simulator_ready"] is False
    archived = result["original_archive"]
    assert archived["observed_rows"] == 1
    body = settings.resolved_path("data/options") / archived["relative_archive"]
    assert body.is_file()
    assert hashlib.sha256(body.read_bytes()).hexdigest() == archived["compressed_sha256"]
    assert hashlib.sha256(gzip.decompress(body.read_bytes())).hexdigest() == archived["original_sha256"]
    assert archived["full_original_retained"] is True
    assert archived["source_coverage_proven"] is False
    with pytest.raises(v11.HybridAtTimeQualificationError, match="ONE_CALL_SOURCE_PREFLIGHT"):
        authorize(sample, lambda **_: pytest.fail("never auto-retry"))
    preview = v11.inspect_one_qualification(settings, manifest, candidate)
    assert preview["status"] == "PRIOR_ATTEMPT_COMPLETE_NO_RETRY"


def test_global_one_attempt_blocks_other_anchor(sample):
    settings, manifest, candidate, rows = sample
    authorize(sample, lambda **_: fake_response(rows[0]))
    with pytest.raises(v11.HybridAtTimeQualificationError, match="ONE_CALL_SOURCE_PREFLIGHT"):
        authorize(sample, lambda **_: pytest.fail("global cap"), index=1)


def test_over_dte_is_archived_unfiltered(sample):
    settings, manifest, candidate, rows = sample
    result = authorize(sample, lambda **_: fake_response(rows[0], over=True))
    assert result["status"] == "SOURCE_ARCHIVED_QUARANTINED_DTE"
    assert result["diagnostic_state"] == "QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION"
    assert result["original_archive"]["observed_rows"] == 1
    path = settings.resolved_path("data/options") / result["original_archive"]["relative_archive"]
    saved_rows = json.loads(gzip.decompress(path.read_bytes()))
    assert saved_rows[0]["expiration"] == "2021-04-30"


def test_crossed_quote_source_is_preserved_but_unqualified(sample):
    settings, manifest, candidate, rows = sample
    result = authorize(sample, lambda **_: fake_response(rows[0], corrupt=True))
    assert result["status"] == "SOURCE_ARCHIVED_INVALID_SCHEMA"
    assert result["original_archive"]["observed_rows"] == 1
    assert result["error_type"] in {
        "HybridAtTimeSourceGateError",
        "ThetaDataCandidateSurfaceQualificationError",
    }
    assert result["simulator_ready"] is False


def test_timeout_records_result_and_permanently_blocks_retry(sample):
    settings, manifest, candidate, rows = sample
    calls = []
    def timeout(**kwargs):
        calls.append(kwargs)
        raise TimeoutError("unknown delivery")
    result = authorize(sample, timeout)
    assert result["status"] == "ATTEMPT_FAILED_UNCERTAIN_NO_RETRY"
    assert result["error_type"] == "TimeoutError"
    assert len(calls) == 1
    with pytest.raises(v11.HybridAtTimeQualificationError):
        authorize(sample, timeout)
    assert len(calls) == 1


def test_hard_interruption_leaves_unfinished_marker_no_retry(sample):
    settings, manifest, candidate, rows = sample
    def crash(**kwargs):
        raise KeyboardInterrupt("simulated process crash")
    with pytest.raises(KeyboardInterrupt):
        authorize(sample, crash)
    marker, terminal = v11._paths(settings)
    assert marker.is_file() and not terminal.exists()
    preview = v11.inspect_one_qualification(settings, manifest, candidate)
    assert preview["status"] == "PRIOR_ATTEMPT_UNCERTAIN_NO_RETRY"
    with pytest.raises(v11.HybridAtTimeQualificationError):
        authorize(sample, crash)


def test_no_data_and_empty_response_never_create_source_archive(sample):
    settings, manifest, candidate, rows = sample
    result = authorize(
        sample, lambda **_: fake_response(rows[0], no_data=True),
    )
    assert result["status"] == "EXPLICIT_NO_DATA_NO_COVERAGE"
    assert result["original_archive"] is None
    assert not list(settings.resolved_path(v11.ROOT_REL).rglob("*.json.gz"))


def test_storage_budget_insufficient_blocks_paid_call(sample, monkeypatch):
    settings, manifest, candidate, rows = sample
    monkeypatch.setattr(v11, "_storage_capacity", lambda *_: {
        "storage_status": "SAFE",
        "safe_available_bytes": 128,
    })
    result = v11.inspect_one_qualification(settings, manifest, candidate)
    assert result["status"] == "STORAGE_HEADROOM_BLOCKS_ONE_CALL"
    with pytest.raises(v11.HybridAtTimeQualificationError):
        authorize(sample, lambda **_: pytest.fail("must not dispatch"))
    assert not settings.resolved_path(v11.ROOT_REL).exists()


def test_marker_fingerprint_tamper_blocks_even_preview(sample):
    settings, manifest, candidate, rows = sample
    authorize(sample, lambda **_: fake_response(rows[0]))
    marker, terminal = v11._paths(settings)
    modified = json.loads(marker.read_text())
    modified["automatic_retry_allowed"] = True
    marker.write_text(json.dumps(modified))
    with pytest.raises(v11.HybridAtTimeQualificationError, match="IDENTITY_DRIFT"):
        v11.inspect_one_qualification(settings, manifest, candidate)


def test_wrong_manifest_name_and_candidate_lineage_block(tmp_path):
    settings = FakeSettings(tmp_path)
    wrong = settings.resolved_path(
        "data/options/manifests/hybrid_exact_at_time_research_demand_v1_wrong.json"
    )
    wrong.write_text("{}")
    with pytest.raises(v11.HybridAtTimeQualificationError, match="PINNED_FULL"):
        v11._load_full_manifest(settings, wrong, Path("no_candidate.json"))


def test_cli_offline_preview_requires_no_provider(sample, monkeypatch, capsys):
    settings, manifest, candidate, rows = sample
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    # Actual inspect is still zero-call; immutable fake full demand fixture.
    assert cli.main(["--manifest", str(manifest), "--candidate-plan", str(candidate)]) == 0
    output = capsys.readouterr().out
    assert "OFFLINE_NO_API_PREVIEW" in output
    assert "provider_requests=0" in output
    assert "max_dte_semantics_unproven=True" in output
    assert not settings.resolved_path(v11.ROOT_REL).exists()


def test_cli_incomplete_paid_flags_rejected_before_inspection(sample, monkeypatch):
    settings, manifest, candidate, rows = sample
    monkeypatch.setattr(cli, "load_settings", lambda *_: pytest.fail("not initialized"))
    with pytest.raises(SystemExit):
        cli.main(["--authorize-one-paid-qualification-call",
                  "--query-id", rows[0]["query_id"]])
    assert not settings.resolved_path(v11.ROOT_REL).exists()
