from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import CONTRACT, _fingerprint
import scripts.inspect_marketdata_candidate_2025_pilot as inspector


SECRET = "SENSITIVE_PROVIDER_ERROR_TEXT_DO_NOT_PRINT"


def _build(tmp_path: Path, *, http_status=404, s="no_data"):
    root = tmp_path / "project"
    root.mkdir()
    settings = SimpleNamespace(resolved_path=lambda relative: root / relative)
    requests = [
        {
            "ticker": symbol, "request_identity": f"{i:064x}",
            "endpoint": f"options/chain/{symbol}/",
            "params": {
                "date": "2025-04-09", "expiration": "2025-05-16",
                "strike": "5.14-6.04",
            },
        }
        for i, symbol in enumerate(
            ("AGIO", "AMGN", "ATRC", "BANF", "DAKT", "FSLY",
             "ISRG", "LNT", "OLLI", "SRRK", "TEM", "TSLA"), 1
        )
    ]
    plan = {"plan_fingerprint": inspector.PLAN_FINGERPRINT, "requests": requests}
    fsly = requests[5]
    path = root / "data/options/candidate_cache/chains/marketdata_v1" / fsly["request_identity"][:2]
    path.mkdir(parents=True)
    body = path / (fsly["request_identity"] + ".json")
    receipt_path = path / (fsly["request_identity"] + ".receipt.json")
    attempt_path = path / (fsly["request_identity"] + ".attempt.json")

    payload = {"s": s, "errmsg": SECRET}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    body.write_bytes(raw)
    receipt = {
        "contract": CONTRACT,
        "status": "QUARANTINED",
        "failure": "unexpected provider response status",
        "request_identity": fsly["request_identity"],
        "endpoint": fsly["endpoint"], "params": fsly["params"],
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "body_bytes": len(raw), "row_count": 0,
        "http_status": http_status, "raw_http_body_exact": True,
        "rate_limit": {"consumed": 1, "remaining": 9994},
    }
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    receipt_path.write_text(json.dumps(receipt))
    attempt = {
        "contract": CONTRACT, "request_identity": fsly["request_identity"],
        "endpoint": fsly["endpoint"], "params": fsly["params"],
        "plan_fingerprint": plan["plan_fingerprint"],
        "automatic_retry_permitted": False,
    }
    attempt["intent_fingerprint"] = _fingerprint(attempt)
    attempt_path.write_text(json.dumps(attempt))
    return settings, plan, fsly, body, receipt_path, attempt_path


def test_frozen_fsly_quarantine_inspection_verifies_hashes_without_network(tmp_path, monkeypatch):
    settings, plan, request, body, receipt, attempt = _build(tmp_path)
    originals = [(p, p.read_bytes()) for p in (body, receipt, attempt)]
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: pytest.fail("zero-network diagnostic must not use provider"),
    )
    result = inspector.inspect_pilot(settings, plan)
    row = result["requests"][5]
    assert row["ticker"] == "FSLY"
    assert row["status"] == "QUARANTINED_VERIFIED_REVIEW_REQUIRED"
    assert row["http_status"] == 404
    assert row["payload_status"] == "no_data"
    assert row["credit_consumed_in_response_headers"] == 1
    assert row["credits_remaining_in_response_headers"] == 9994
    assert row["attempt_verified"] is True
    assert result["verified_quarantined"] == 1
    assert result["never_attempted"] == 11
    assert result["provider_reads_this_inspection"] == 0
    assert result["provider_credits_spent_this_inspection"] == 0
    assert SECRET not in json.dumps(result)
    assert [(p, p.read_bytes()) for p, _ in originals] == originals


def test_tampered_raw_or_receipt_fails_integrity_without_printing_error(tmp_path):
    settings, plan, _request, body, receipt, _attempt = _build(tmp_path)
    body.write_bytes(body.read_bytes() + b"x")
    row = inspector.inspect_pilot(settings, plan)["requests"][5]
    assert row["status"] == "UNREADABLE_EVIDENCE_PRESERVE"
    body.write_bytes(json.dumps({"s": "no_data", "errmsg": SECRET}).encode())
    row = inspector.inspect_pilot(settings, plan)["requests"][5]
    assert row["status"] == "EVIDENCE_INTEGRITY_MISMATCH_PRESERVE"


def test_malformed_payload_status_or_missing_attempt_is_not_executed(tmp_path):
    settings, plan, _request, body, receipt_path, attempt = _build(tmp_path)
    raw = json.dumps({"s": ["not-a-status"], "errmsg": SECRET}).encode()
    body.write_bytes(raw)
    receipt = json.loads(receipt_path.read_text())
    receipt["body_sha256"] = hashlib.sha256(raw).hexdigest()
    receipt["body_bytes"] = len(raw)
    receipt.pop("receipt_fingerprint")
    receipt["receipt_fingerprint"] = _fingerprint(receipt)
    receipt_path.write_text(json.dumps(receipt))
    attempt.unlink()
    row = inspector.inspect_pilot(settings, plan)["requests"][5]
    assert row["status"] == "QUARANTINED_VERIFIED_REVIEW_REQUIRED"
    assert row["payload_status"] == "OTHER_OR_ABSENT"
    assert row["attempt_verified"] is False
    assert SECRET not in json.dumps(row)


def test_unresolved_attempt_and_complete_reuse_are_distinct(tmp_path, monkeypatch):
    settings, plan, request, body, receipt_path, _attempt = _build(tmp_path)
    body.unlink()
    receipt_path.unlink()
    result = inspector.inspect_pilot(settings, plan)
    assert result["requests"][5]["status"] == "UNRESOLVED_ATTEMPT_PRESERVE"
    assert result["requests"][5]["attempt_verified"] is True

    # A separate COMPLETE pair must pass the real cache verifier, rather than
    # the inspector declaring a receipt COMPLETE solely from its status field.
    body.write_bytes(b'{"s":"ok"}')
    saved = {
        "contract": CONTRACT, "status": "COMPLETE",
        "request_identity": request["request_identity"], "endpoint": request["endpoint"],
        "params": request["params"],
        "body_sha256": hashlib.sha256(body.read_bytes()).hexdigest(),
        "body_bytes": len(body.read_bytes()), "raw_http_body_exact": True,
    }
    saved["receipt_fingerprint"] = _fingerprint(saved)
    receipt_path.write_text(json.dumps(saved))
    monkeypatch.setattr(inspector, "_valid_receipt", lambda *_args, **_kwargs: None)
    assert inspector.inspect_pilot(settings, plan)["requests"][5]["status"] == (
        "RECEIPT_VALIDATION_FAILED_PRESERVE"
    )


def test_cli_output_only_prints_allowlisted_metadata(tmp_path, monkeypatch, capsys):
    settings, plan, _request, _body, _receipt, _attempt = _build(tmp_path)
    monkeypatch.setattr(inspector, "load_settings", lambda *_args: settings)
    monkeypatch.setattr(inspector, "preflight", lambda _settings: (plan, Path("accepted-source.json")))
    assert inspector.main([]) == 0
    out = capsys.readouterr().out
    assert "FSLY" in out and "http_status: 404" in out
    assert "provider reads: 0" in out
    assert SECRET not in out
