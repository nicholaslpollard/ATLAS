from __future__ import annotations

"""No-network synthetic contract checks for the local 2022 EOD reader."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.offline_option_history_v1 as m
from packages.data.marketdata_2022_selected_quote_campaign_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


def _fixture(tmp_path: Path, monkeypatch):
    calls = []
    settings = SimpleNamespace(
        resolved_path=lambda path: tmp_path / path,
        assert_external_storage_binding=lambda name: calls.append(name),
    )
    symbol = "TEST220617C00010000"
    query = {
        "option_symbol": symbol,
        "from_inclusive": "2022-01-01",
        "to_exclusive": "2022-06-18",
    }
    identity = _fingerprint({"contract": QUOTE_CONTRACT, "query": query})
    ticket = {
        **query,
        "request_identity": identity,
        "source_shard_memberships": [{"shard_index": 0, "opportunity_id": "one", "rank": 0}],
        "historical_eod_only": True,
        "historical_deliverable_not_verified": True,
    }
    plan = {
        "contract": QUOTE_CONTRACT,
        "status": "SOURCE_ONLY_SELECTED_CALL_QUOTE_HISTORIES_FROZEN",
        "year": 2022,
        "last_shard_inclusive": 70,
        "provider_reads_in_planning": 0,
        "unique_exact_quote_series": 1,
        "requests": [ticket],
    }
    plan["plan_fingerprint"] = _fingerprint(plan)
    monkeypatch.setattr(m, "EXPECTED_PLAN", plan["plan_fingerprint"])
    monkeypatch.setattr(m, "EXPECTED_QUOTE_HISTORIES", 1)
    plan_path = tmp_path / m.PLAN_REL / m.PLAN_FILENAME
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    times = [
        int(datetime(2022, 3, day, 21, tzinfo=UTC).timestamp())
        for day in (1, 2, 3)
    ]
    raw = json.dumps({
        "s": "ok",
        "optionSymbol": [symbol] * 3,
        "updated": times,
        "bid": [0.9, 1.0, 1.1],
        "ask": [1.1, 1.2, 1.3],
        "volume": [0, 10, 0],
    }).encode()
    raw_path = tmp_path / "exact_body.json"
    raw_path.write_bytes(raw)
    receipt = {
        "status": "COMPLETE_SOURCE_ONLY",
        "body_sha256": hashlib.sha256(raw).hexdigest(),
        "safe_summary": {"observed_rows": 3},
    }
    def fake_receipt(s, t):
        assert s is settings and t == ticket
        calls.append("local_receipt")
        return receipt
    monkeypatch.setattr(m, "_read_intact_quote", fake_receipt)
    monkeypatch.setattr(m, "_cache_paths", lambda s, t: (raw_path, None, None))
    return settings, symbol, plan_path, raw_path, receipt, calls


def test_index_and_strict_predecision_lookback_without_provider_calls(tmp_path, monkeypatch):
    settings, symbol, _, _, _, calls = _fixture(tmp_path, monkeypatch)
    store = m.OfflineOptionHistoryStore(settings)
    assert store.available_symbols == 1
    assert calls == ["options"]
    full = store.inspect_retrospective_history(symbol)
    assert full["observation_count"] == 3
    assert full["scope"] == "RETROSPECTIVE_FULL_HISTORY"
    assert full["authority"] == m.AUTHORITY
    assert full["authority"]["provider_requests"] == 0
    assert full["provider_updated_timestamp_is_not_publication_or_fill_proof"]
    before = store.predecision_history(
        symbol, decision_utc=datetime(2022, 3, 3, 14, 35, tzinfo=UTC)
    )
    assert before["scope"] == "CONSERVATIVE_PREDECISION_EOD_SOURCE_VIEW"
    assert before["observation_count"] == 2
    assert [r["session_et"] for r in before["observations"]] == [
        "2022-03-01", "2022-03-02"
    ]
    assert before["observations"][1]["ask_per_share"] == "1.2"
    assert before["observations"][1]["positive_reported_volume"] is True
    assert all(r["session_et"] != "2022-03-03" for r in before["observations"])
    assert calls == ["options", "local_receipt", "local_receipt"]


def test_missing_identity_and_naive_cutoff_fail_closed(tmp_path, monkeypatch):
    settings, symbol, _, _, _, _ = _fixture(tmp_path, monkeypatch)
    store = m.OfflineOptionHistoryStore(settings)
    with pytest.raises(m.OfflineOptionHistoryError, match="outside frozen"):
        store.inspect_retrospective_history("UNKNOWN220617C00010000")
    with pytest.raises(m.OfflineOptionHistoryError, match="timezone-aware"):
        store.predecision_history(symbol, decision_utc=datetime(2022, 3, 3, 9, 35))


def test_local_tampering_and_missing_receipt_never_fall_back(tmp_path, monkeypatch):
    settings, symbol, _, body_path, receipt, _ = _fixture(tmp_path, monkeypatch)
    store = m.OfflineOptionHistoryStore(settings)
    body_path.write_bytes(b"{}")
    with pytest.raises(m.OfflineOptionHistoryError, match="SHA differs"):
        store.inspect_retrospective_history(symbol)
    monkeypatch.setattr(m, "_read_intact_quote", lambda s, t: None)
    with pytest.raises(m.OfflineOptionHistoryError, match="unavailable"):
        store.inspect_retrospective_history(symbol)
    assert receipt["status"] == "COMPLETE_SOURCE_ONLY"


def test_plan_fingerprint_and_exact_query_identity_fail_closed(tmp_path, monkeypatch):
    settings, _, plan_path, _, _, _ = _fixture(tmp_path, monkeypatch)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["provider_reads_in_planning"] = 1
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(m.OfflineOptionHistoryError, match="cannot be trusted"):
        m.OfflineOptionHistoryStore(settings)
    plan["provider_reads_in_planning"] = 0
    plan["requests"][0]["request_identity"] = "0" * 64
    plan["plan_fingerprint"] = _fingerprint({
        key: value for key, value in plan.items() if key != "plan_fingerprint"
    })
    monkeypatch.setattr(m, "EXPECTED_PLAN", plan["plan_fingerprint"])
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(m.OfflineOptionHistoryError, match="cannot be trusted"):
        m.OfflineOptionHistoryStore(settings)
