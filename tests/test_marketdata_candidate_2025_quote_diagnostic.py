from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
import packages.data.marketdata_candidate_2025_selected_quote_source_v1 as source
import packages.data.marketdata_candidate_2025_quote_diagnostic_v1 as diag

EASTERN = ZoneInfo("America/New_York")


def _setup(tmp_path, monkeypatch):
    settings = SimpleNamespace(resolved_path=lambda path: tmp_path / path)
    tickets = []
    roots = {}
    for ticker, (n, positive, remaining) in diag.EXPECTED_SOURCE.items():
        ticket = {
            "ticker": ticker, "option_symbol": ticker + "250221C00050000",
            "from_inclusive": "2025-01-01", "to_exclusive": "2025-03-01",
            "stock_decision_at_utc": datetime.combine(
                date(2025, 1, 1), time(9, 35), EASTERN
            ).astimezone(UTC).isoformat(),
            "source_reference_receipt_fingerprint": "b" * 64,
        }
        ticket["request_identity"] = _fingerprint(ticket)
        tickets.append(ticket)
        vol = [1 if i < positive else 0 for i in range(n)]
        raw = json.dumps({
            "s": "ok", "optionSymbol": [ticket["option_symbol"]] * n,
            "updated": [
                int(datetime.combine(date(2025, 1, 1) + timedelta(days=i), time(16), EASTERN).timestamp())
                for i in range(n)
            ],
            "bid": [1] * n, "ask": [1.2] * n, "last": [1.1] * n,
            "volume": vol, "openInterest": [100] * n, "underlyingPrice": [50] * n,
        }).encode()
        label, summary = source._classify(ticket, 203, raw)
        assert label == "EOD_SOURCE_ROWS_NO_FILL_AUTHORITY"
        body, receipt_path, attempt_path = source._paths(settings, ticket)
        intent = {
            "contract": source.CONTRACT, "plan_fingerprint": diag.FROZEN_QUOTE_PLAN,
            "request_identity": ticket["request_identity"],
            "option_symbol": ticket["option_symbol"], "automatic_retry_permitted": False,
        }
        intent["intent_fingerprint"] = _fingerprint(intent)
        receipt = {
            "contract": source.CONTRACT, "plan_fingerprint": diag.FROZEN_QUOTE_PLAN,
            "request_identity": ticket["request_identity"],
            "option_symbol": ticket["option_symbol"], "status": "COMPLETE_SOURCE_ONLY",
            "http_status": 203, "classification": label, "body_sha256": source._sha(raw),
            "body_bytes": len(raw), "safe_summary": summary,
            "rate_limit": {"limit": 10000, "consumed": 1, "remaining": remaining, "reset": 1},
            "subscription_retention_required": True, "no_deliverable_fill_or_pnl_authority": True,
        }
        receipt["receipt_fingerprint"] = _fingerprint(receipt)
        source._exclusive_write(body, raw)
        source._exclusive_write(receipt_path, receipt)
        source._exclusive_write(attempt_path, intent)
        roots[ticker] = (body, receipt_path, attempt_path)
    plan = {"plan_fingerprint": diag.FROZEN_QUOTE_PLAN, "requests": tickets}
    source._exclusive_write(settings.resolved_path(source.PLAN_REL), plan)
    monkeypatch.setattr(source, "read_accepted_inputs", lambda *_: ({}, {}))
    monkeypatch.setattr(source, "build_quote_plan", lambda *a: plan)
    return settings, plan, roots


def test_offline_complete_census_no_provider_calls_and_idempotence(tmp_path, monkeypatch):
    settings, plan, roots = _setup(tmp_path, monkeypatch)
    before = {k: tuple(path.read_bytes() for path in paths) for k, paths in roots.items()}
    result = diag.build_offline_dossier(settings)
    assert result["aggregate"]["eod_rows"] == 320
    assert result["aggregate"]["positive_volume_rows"] == 190
    assert result["aggregate"]["zero_volume_rows"] == 130
    assert result["aggregate"]["no_positive_volume_series"] == ["ATRC", "BANF"]
    assert result["aggregate"]["new_provider_gets_this_diagnostic"] == 0
    assert result["option_pnl_authority"] is False
    assert diag.write_local_dossier(settings, result, authorize=False)[0] == "PREVIEW_NO_WRITES"
    assert diag.write_local_dossier(settings, result, authorize=True)[0] == "WRITTEN_NEW_OFFLINE_DOSSIER"
    assert diag.write_local_dossier(settings, result, authorize=True)[0] == "REUSED_EXACT_OFFLINE_DOSSIER"
    assert before == {k: tuple(path.read_bytes() for path in paths) for k, paths in roots.items()}


def test_same_day_eod_is_not_0935_entry_and_zero_last_not_trade(tmp_path, monkeypatch):
    settings, _, _ = _setup(tmp_path, monkeypatch)
    result = diag.build_offline_dossier(settings)
    agio = next(x["metrics"] for x in result["per_contract"] if x["ticker"] == "AGIO")
    atrc = next(x["metrics"] for x in result["per_contract"] if x["ticker"] == "ATRC")
    assert agio["same_decision_day_eod_rows_unavailable_at_0935"] == 1
    assert agio["same_decision_day_positive_volume_eod_unavailable_at_0935"] == 1
    assert agio["first_post_decision_positive_volume_source_session"] == "2025-01-02"
    assert atrc["first_post_decision_positive_volume_source_session"] is None
    assert atrc["zero_volume_with_positive_last_not_a_same_session_trade"] == 26
    assert atrc["observed_two_sided_eod_quote_geometry_rows"] == 26
    assert atrc["eod_bid_ask_is_executable_fill"] is False


def test_tampered_raw_and_orphan_receipt_fail_closed(tmp_path, monkeypatch):
    settings, _, roots = _setup(tmp_path, monkeypatch)
    body = roots["AGIO"][0]
    body.write_bytes(body.read_bytes() + b" ")
    with pytest.raises(CandidateChainCacheError, match="lineage mismatch"):
        diag.build_offline_dossier(settings)
    settings2, _, roots2 = _setup(tmp_path / "next", monkeypatch)
    roots2["AGIO"][1].unlink()
    with pytest.raises(CandidateChainCacheError, match="unresolved quote attempt"):
        diag.build_offline_dossier(settings2)


def test_changed_original_plan_fails_before_loading_rows(tmp_path, monkeypatch):
    settings, plan, roots = _setup(tmp_path, monkeypatch)
    location = settings.resolved_path(source.PLAN_REL)
    location.write_text(json.dumps({"wrong": True}))
    with pytest.raises(CandidateChainCacheError, match="original quote plan differs"):
        diag.build_offline_dossier(settings)


def test_source_run_counts_are_frozen_not_posthoc_thresholds(tmp_path, monkeypatch):
    settings, plan, roots = _setup(tmp_path, monkeypatch)
    path = roots["AGIO"][1]
    data = json.loads(path.read_text())
    data["safe_summary"]["positive_volume_rows"] = 0
    data["receipt_fingerprint"] = _fingerprint({
        k: v for k, v in data.items() if k != "receipt_fingerprint"
    })
    path.write_text(json.dumps(data))
    with pytest.raises(CandidateChainCacheError):
        diag.build_offline_dossier(settings)
