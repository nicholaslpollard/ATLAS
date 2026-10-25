from __future__ import annotations

from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data import hybrid_options_saved_aal_audit_v1 as audit
from packages.data import hybrid_options_unattended_campaign_v1 as camp
from packages.data.hybrid_options_frozen_research_demand_v1 import _entry
from packages.providers.thetadata.client import (
    EVIDENCE_ENCODING, TARGET_LIBRARY_VERSION, TRANSPORT,
    ThetaDataResponse, _canonical_bytes,
)
from scripts import run_hybrid_options_unattended_campaign_v1 as cli


class Settings:
    def __init__(self, root):
        self.root = root
        (root / "data/options/manifests").mkdir(parents=True)
    def assert_external_storage_binding(self, binding):
        assert binding == "options"
    def resolved_path(self, path):
        return self.root / path


def _row(symbol, date, priority):
    params = {
        "symbol": symbol, "start_date": date.replace("-", ""),
        "end_date": date.replace("-", ""), "time_of_day": "09:35:00.000",
        "right": "call", "max_dte": 75, "strike_range": None,
        "expiration": "*", "strike": "*", "format": "json",
    }
    row = _entry(
        "FROZEN_0935_MULTIYEAR_CALL_CANDIDATES",
        "a" * 64, "b" * 64,
        {"endpoint": "/v3/option/at_time/quote", "params": params},
        role="0935_CALL_ENTRY_DISCOVERY", anchor=False,
    )
    row["priority"] = priority
    return row


def _source(row, *, over=False, invalid=False, empty=False):
    if empty:
        quotes = ()
    else:
        exp = "2022-05-30" if over else "2022-01-14"
        stamp = row["date_et"] + "T09:34:55-05:00"
        quotes = ({
            "symbol": row["symbol"], "expiration": exp,
            "strike": 20.0, "right": "call", "timestamp": stamp,
            "bid_size": 3, "ask_size": 4,
            "bid": 1.1 if not invalid else 2.2, "ask": 1.2,
            "bid_exchange": 1, "ask_exchange": 2,
            "bid_condition": 0, "ask_condition": 0,
        },)
    raw = _canonical_bytes(quotes)
    return ThetaDataResponse(
        http_status=200, rows=quotes, headers={}, response_bytes=len(raw),
        raw_body=raw, elapsed_seconds=0.1,
        transport=TRANSPORT, library_version=TARGET_LIBRARY_VERSION,
        provider_environment_fingerprint="c" * 64,
        evidence_encoding=EVIDENCE_ENCODING, explicit_no_data=False,
    )


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    settings = Settings(tmp_path)
    rows = [
        _row("AAL", "2021-11-30", 1),
        _row("AAPL", "2021-12-01", 2),
        _row("MSFT", "2021-12-02", 3),
    ]
    full = {
        "manifest_fingerprint":
            "138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63",
        "source_request_count": 9866, "requests": rows,
    }
    monkeypatch.setattr(camp, "_load_full_manifest", lambda *_: full)
    monkeypatch.setattr(camp, "_prior_external_source_ids",
                        lambda *_: {rows[0]["query_id"]})
    monkeypatch.setattr(camp, "_storage_capacity", lambda *_: {
        "storage_status": "SAFE",
        "safe_available_bytes": 60 * 1024**3,
    })
    monkeypatch.setattr(camp, "_outstanding_reservations",
                        lambda *_: {"bytes": 0})
    return settings, full, rows


def test_unattended_preview_no_calls_or_writes(workspace):
    settings, full, rows = workspace
    report = camp.preview_campaign(settings, Path("full"), Path("source"))
    assert report["total_frozen_requests"] == 9866
    assert report["counts"]["external_existing"] == 1
    assert report["counts"]["not_attempted"] == 2
    assert report["next_request"]["symbol"] == "AAPL"
    assert report["storage"]["safe"] is True
    assert report["provider_requests"] == 0
    assert not settings.resolved_path(camp.ROOT_REL).exists()


def test_auto_run_one_request_and_resume_without_prompt(workspace):
    settings, full, rows = workspace
    called = []
    def read(**kw):
        path = camp._record_path(settings, rows[1]["query_id"], "started")
        assert path.is_file()
        called.append(kw)
        return _source(rows[len(called)])
    a = camp.run_campaign(
        settings, Path("full"), Path("source"),
        max_calls=1, reader=read,
    )
    assert a["provider_calls_this_run"] == 1
    assert a["stop_reason"] == "OPTIONAL_RUN_REQUEST_LIMIT_REACHED"
    assert a["archives_written_this_run"] == 1
    assert called[0]["date_et"] == "2021-12-01"
    report = camp.preview_campaign(settings, Path("full"), Path("source"))
    assert report["counts"]["previously_attempted"] == 1
    assert report["counts"]["saved_archives"] == 1
    assert report["counts"]["not_attempted"] == 1
    b = camp.run_campaign(
        settings, Path("full"), Path("source"),
        reader=lambda **kw: _source(rows[2]),
    )
    assert b["provider_calls_this_run"] == 1
    assert b["stop_reason"] == "FULL_FROZEN_MANIFEST_SCANNED"
    c = camp.run_campaign(
        settings, Path("full"), Path("source"),
        reader=lambda **kw: pytest.fail("must not duplicate"),
    )
    assert c["provider_calls_this_run"] == 0


def test_out_dte_source_preserved_and_resumed(workspace):
    settings, full, rows = workspace
    result = camp.run_campaign(
        settings, Path("full"), Path("source"), max_calls=1,
        reader=lambda **_: _source(rows[1], over=True),
    )
    assert result["out_of_dte_archives_this_run"] == 1
    qid = rows[1]["query_id"]
    path = camp._archive_path(settings, qid)
    assert json.loads(gzip.decompress(path.read_bytes()))[0][
        "expiration"
    ] == "2022-05-30"
    assert camp._inspect_attempt(settings, qid) == "RAW_ARCHIVED_OUT_DTE_DIAGNOSTIC"


def test_invalid_price_keeps_full_original_unqualified(workspace):
    settings, full, rows = workspace
    result = camp.run_campaign(
        settings, Path("full"), Path("source"), max_calls=1,
        reader=lambda **_: _source(rows[1], invalid=True),
    )
    assert result["invalid_schema_archives_this_run"] == 1
    assert camp._inspect_attempt(
        settings, rows[1]["query_id"]
    ) == "RAW_ARCHIVED_INVALID_SCHEMA"


def test_uncertain_timeout_skips_same_query_on_resume(workspace):
    settings, full, rows = workspace
    called = []
    def timeout(**kw):
        called.append(kw)
        raise TimeoutError("ambiguous provider delivery")
    first = camp.run_campaign(
        settings, Path("full"), Path("source"), reader=timeout,
    )
    assert first["provider_calls_this_run"] == 1
    assert first["stop_reason"] == "PROVIDER_OR_STORAGE_FAILURE_STOPPED_RUN"
    assert camp._inspect_attempt(
        settings, rows[1]["query_id"]
    ) == "PROVIDER_OR_STORAGE_ERROR_NO_RETRY"
    next_result = camp.run_campaign(
        settings, Path("full"), Path("source"),
        reader=lambda **kw: _source(rows[2]),
    )
    assert next_result["provider_calls_this_run"] == 1
    assert len(called) == 1


def test_hard_crash_leaves_durable_start_and_skips_query(workspace):
    settings, full, rows = workspace
    def crash(**kw):
        raise KeyboardInterrupt("process killed")
    with pytest.raises(KeyboardInterrupt):
        camp.run_campaign(
            settings, Path("full"), Path("source"), reader=crash,
        )
    preview = camp.preview_campaign(settings, Path("full"), Path("source"))
    assert preview["counts"]["uncertain_attempts"] == 1
    assert preview["counts"]["not_attempted"] == 1
    resumed = camp.run_campaign(
        settings, Path("full"), Path("source"),
        reader=lambda **kw: _source(rows[2]),
    )
    assert resumed["provider_calls_this_run"] == 1


def test_corrupt_compressed_archive_fails_closed(workspace):
    settings, full, rows = workspace
    camp.run_campaign(
        settings, Path("full"), Path("source"), max_calls=1,
        reader=lambda **kw: _source(rows[1]),
    )
    archive = camp._archive_path(settings, rows[1]["query_id"])
    archive.write_bytes(b"corrupted")
    with pytest.raises(camp.HybridCampaignError):
        camp.preview_campaign(settings, Path("full"), Path("source"))


def test_receipt_fingerprint_mutation_fails_closed(workspace):
    settings, full, rows = workspace
    camp.run_campaign(
        settings, Path("full"), Path("source"), max_calls=1,
        reader=lambda **kw: _source(rows[1]),
    )
    started = camp._record_path(settings, rows[1]["query_id"], "started")
    original = json.loads(started.read_text())
    original["simulator_ready"] = True
    started.write_text(json.dumps(original))
    with pytest.raises(camp.HybridCampaignError, match="DRIFT"):
        camp.preview_campaign(settings, Path("full"), Path("source"))


def test_disk_headroom_stops_before_new_calls(workspace, monkeypatch):
    settings, full, rows = workspace
    monkeypatch.setattr(camp, "_storage_capacity", lambda *_: {
        "storage_status": "SAFE",
        "safe_available_bytes": 10,
    })
    result = camp.run_campaign(
        settings, Path("full"), Path("source"),
        reader=lambda **kw: pytest.fail("storage preflight must block"),
    )
    assert result["provider_calls_this_run"] == 0
    assert result["stop_reason"] == "SAFE_STORAGE_HEADROOM_INSUFFICIENT"


def test_empty_source_unqualified_but_receipted(workspace):
    settings, full, rows = workspace
    result = camp.run_campaign(
        settings, Path("full"), Path("source"),
        max_calls=1, reader=lambda **kw: _source(rows[1], empty=True),
    )
    assert result["provider_calls_this_run"] == 1
    assert result["archives_written_this_run"] == 0
    assert camp._inspect_attempt(
        settings, rows[1]["query_id"]
    ) == "EMPTY_RESPONSE_SOURCE_ONLY"


def test_run_limit_validation_before_provider(workspace):
    settings, full, rows = workspace
    with pytest.raises(camp.HybridCampaignError, match="MAX_CALLS"):
        camp.run_campaign(
            settings, Path("full"), Path("source"), max_calls=0,
            reader=lambda **kw: pytest.fail("must not call"),
        )


def test_cli_no_interactive_auth_and_preview(workspace, monkeypatch, capsys):
    settings, full, rows = workspace
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(cli, "audit_saved_aal", lambda *_: {
        "status": "REPRODUCED_OUT_DTE_DIAGNOSTIC_SOURCE_ONLY",
        "total_original_rows": 20, "in_dte_rows": 10,
        "over_dte_rows": 10, "distinct_expiration_count": 2,
        "compressed_bytes": 100, "raw_bytes": 1000,
        "archived_full_raw_sha256": "f" * 64,
        "dte_buckets": {"76_180": 10, "15_45": 10},
    })
    assert cli.main([]) == 0
    stdout = capsys.readouterr().out
    assert "interactive_authorization_prompts=0" in stdout
    assert "remaining=2" in stdout
    assert "provider_requests=0" in stdout
    assert not settings.resolved_path(camp.ROOT_REL).exists()
    with pytest.raises(SystemExit):
        cli.main(["--max-calls", "2"])

def test_cli_reports_safe_archive_audit_error_code_without_provider(
    workspace, monkeypatch, capsys,
):
    settings, full, rows = workspace
    monkeypatch.setattr(cli, "load_settings", lambda *_: settings)
    monkeypatch.setattr(
        cli, "audit_saved_aal",
        lambda *_: (_ for _ in ()).throw(
            cli.HybridAalAuditError("AAL_ARCHIVED_ROWS_FAIL_V10_IDENTITY_REPLAY")
        ),
    )
    assert cli.main([]) == 3
    output = capsys.readouterr().out
    assert "code=AAL_ARCHIVED_ROWS_FAIL_V10_IDENTITY_REPLAY" in output
    assert "provider_requests=0" in output
    assert not settings.resolved_path(camp.ROOT_REL).exists()
