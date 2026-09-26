from __future__ import annotations

from pathlib import Path

import pytest

import scripts.classify_marketdata_candidate_2025_fsly_no_data_v1 as classifier


def _fixture(monkeypatch, *, valid=True):
    request = {
        "ticker": "FSLY", "request_identity": classifier.FSLY_NO_DATA_REQUEST_ID,
        "params": {"date": "2025-04-09", "expiration": "2025-05-16", "strike": "5.14-6.04"},
    }
    plan = {"requests": [{"ticker": "AGIO", "request_identity": "a" * 64}] +
            [{"ticker": "OTHER", "request_identity": f"{i:064x}"} for i in range(1, 5)] +
            [request] + [{"ticker": "OTHER", "request_identity": f"{i:064x}"}
                         for i in range(6, 12)]}
    proof = {
        "http_status": 404, "provider_payload_status": "no_data", "row_count": 0,
        "body_sha256": classifier.EXPECTED_FSLY_BODY_SHA256 if valid else "f" * 64,
        "body_bytes": 47, "original_receipt_fingerprint": "c" * 64,
        "provider_credits_consumed_reported": 0,
        "provider_credits_remaining_reported": 9995,
        "proof_fingerprint": "d" * 64,
    }
    calls = []
    def fake_record(_settings, _plan, _identity, *, authorize_offline_classification=False):
        calls.append(authorize_offline_classification)
        return {
            "action": "RECORDED_VERIFIED_NO_DATA" if authorize_offline_classification
                      else "PREVIEW_ONLY_NO_WRITES",
            "proof": proof,
        }
    def fake_cache(*_args, **_kwargs):
        calls.append("preview")
        return {
            "status": "PREVIEW", "provider_reads": 0, "new_complete": 0, "quarantined": 0,
            "planned_chain_requests": 12, "reused": 5, "no_data_verified": 1,
            "pending": 6,
            "request_results": [
                {"request_identity": "a" * 64, "status": "REUSED_VERIFIED"},
                *[{"request_identity": f"{i:064x}", "status": "REUSED_VERIFIED"}
                  for i in range(1, 5)],
                {"request_identity": classifier.FSLY_NO_DATA_REQUEST_ID,
                 "status": "SOURCE_NO_DATA_VERIFIED"},
                *[{"request_identity": f"{i:064x}", "status": "PENDING"}
                  for i in range(6, 12)],
            ],
        }
    monkeypatch.setattr(classifier, "load_settings", lambda *_args: object())
    monkeypatch.setattr(classifier, "preflight", lambda _settings: (plan, Path("exact-source.json")))
    monkeypatch.setattr(classifier, "record_exact_query_no_data", fake_record)
    monkeypatch.setattr(classifier, "run_candidate_chain_cache", fake_cache)
    return calls


def test_default_classification_is_offline_preview_only(monkeypatch, capsys):
    calls = _fixture(monkeypatch)
    assert classifier.main([]) == 0
    assert calls == [False]
    out = capsys.readouterr().out
    assert "PREVIEW_ONLY_NO_WRITES" in out
    assert "provider calls: 0" in out


def test_explicit_classification_reverifies_five_one_six_without_provider_reads(
    monkeypatch, capsys,
):
    calls = _fixture(monkeypatch)
    assert classifier.main(["--authorize-exact-no-data-record"]) == 0
    assert calls == [False, True, "preview"]
    out = capsys.readouterr().out
    assert "5 complete / 1 exact-query no-data / 6 pending" in out
    assert "provider calls: 0" in out


def test_changed_original_hash_prevents_sidecar_write(monkeypatch, capsys):
    calls = _fixture(monkeypatch, valid=False)
    assert classifier.main(["--authorize-exact-no-data-record"]) == 3
    assert calls == [False]
    assert "differs from frozen inspected evidence" in capsys.readouterr().out
