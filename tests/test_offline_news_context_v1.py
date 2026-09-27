from __future__ import annotations

"""No-provider local tests for metadata-only conservative news availability."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

import packages.data.offline_news_context_v1 as n
from packages.data.historical_news_v1_closeout import _canonical_hash


def test_accepted_month_partition_receipt_is_normalized_byte_bound(tmp_path, monkeypatch):
    report = {
        "status": "PASS", "contract": n.SOURCE_INTEGRITY_V2_CONTRACT,
        "contract_fingerprint": n.HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT,
        "corpus_fingerprint": n.EXPECTED_CORPUS_FINGERPRINT,
        "raw_provider_records": n.EXPECTED_RAW_PROVIDER_RECORDS,
        "normalized_articles": n.EXPECTED_NORMALIZED_ARTICLES,
        "failed_partitions_under_v1": ["2015-07", "2026-08"],
        "effective_pit_policy": "MAX_CREATED_AT_UPDATED_AT_CONSERVATIVE",
        "authority": {"source_integrity_accepted": True, "provider_calls": False},
    }
    report["acceptance_fingerprint"] = _canonical_hash(report)
    report_path = tmp_path / n.ACCEPTED_NEWS_REPORT
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps(report), encoding="utf-8")
    receipt_paths = {}
    for month in range(1, 13):
        key = f"2022-{month:02d}"
        p = tmp_path / f"2022-{month:02d}.parquet"
        p.write_bytes(b"mocked-normalized-byte-payload")
        receipt = {
            "status": "COMPLETE",
            "month": key,
            "contract_fingerprint": n.HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
            "normalized_sha256": n._sha(p),
        }
        receipt["receipt_fingerprint"] = _canonical_hash(receipt)
        r = tmp_path / f"receipt-{month:02d}.json"
        r.write_text(json.dumps(receipt), encoding="utf-8")
        receipt_paths[key] = {"normalized": p, "receipt": r}
    s = SimpleNamespace(
        assert_external_storage_binding=lambda category:
            None if category == "news" else pytest.fail("wrong storage binding"),
        resolved_path=lambda path: tmp_path / path,
    )
    monkeypatch.setattr(n, "_month_paths", lambda settings, window: receipt_paths[window.key])
    paths, lineage = n._accepted_paths(s)
    assert len(paths) == 12
    assert lineage["accepted_v2_fingerprint"] == report["acceptance_fingerprint"]
    assert set(lineage["normalized_2022_monthly_sha256"]) == set(receipt_paths)
    receipt_paths["2022-05"]["normalized"].write_bytes(b"changed")
    with pytest.raises(n.OfflineNewsContextError, match="2022-05"):
        n._accepted_paths(s)


def test_news_index_excludes_future_revision_and_deduplicates_articles(tmp_path, monkeypatch):
    path = tmp_path / "news.parquet"
    con = duckdb.connect(database=":memory:")
    try:
        con.execute(
            "CREATE TABLE news(article_id VARCHAR, created_at TIMESTAMPTZ, "
            "updated_at TIMESTAMPTZ, symbols_json VARCHAR)"
        )
        con.executemany("INSERT INTO news VALUES (?, ?, ?, ?)", [
            ("early", "2022-03-03T12:00:00Z", "2022-03-03T13:00:00Z", '["TEST"]'),
            ("revised", "2022-03-02T12:00:00Z", "2022-03-04T12:00:00Z", '["TEST"]'),
            ("revised", "2022-03-02T12:00:00Z", "2022-03-02T15:00:00Z", '["TEST"]'),
            ("after", "2022-03-03T16:00:00Z", "2022-03-03T16:00:00Z", '["TEST"]'),
            ("other", "2022-03-03T13:00:00Z", "2022-03-03T13:00:00Z", '["OTHER"]'),
        ])
        con.execute(f"COPY news TO '{str(path).replace(chr(39), chr(39)*2)}' (FORMAT PARQUET)")
    finally:
        con.close()
    monkeypatch.setattr(
        n, "_accepted_paths",
        lambda settings: ([str(path)], {"accepted_v2_fingerprint": "a" * 64}),
    )
    idx = n.OfflineNewsContext.from_accepted_2022(
        SimpleNamespace(), {"TEST"}, threads=2
    )
    decision = datetime(2022, 3, 3, 14, 35, tzinfo=UTC)
    counts = idx.prior_counts("TEST", decision_utc=decision)
    assert idx.scanned_articles == 5
    assert counts["unique_articles_available_prior_24h"] == 1
    assert counts["unique_articles_available_prior_7d"] == 1
    assert counts["authority"]["provider_requests"] == 0
    later = idx.prior_counts(
        "TEST", decision_utc=datetime(2022, 3, 5, 14, 35, tzinfo=UTC)
    )
    assert later["unique_articles_available_prior_7d"] == 3
    assert idx.prior_counts("ABSENT", decision_utc=decision)[
        "unique_articles_available_prior_7d"] == 0
    with pytest.raises(n.OfflineNewsContextError, match="timezone-aware"):
        idx.prior_counts("TEST", decision_utc=datetime(2022, 3, 3, 14, 35))


def test_news_symbol_and_effective_availability_fail_closed():
    with pytest.raises(n.OfflineNewsContextError, match="array"):
        n._symbol_list('{"bad": "shape"}')
    with pytest.raises(n.OfflineNewsContextError, match="timezone"):
        n._timestamp(datetime(2022, 3, 3))
    with pytest.raises(ValueError, match="required"):
        n.effective_pit_available_at(None, None)
