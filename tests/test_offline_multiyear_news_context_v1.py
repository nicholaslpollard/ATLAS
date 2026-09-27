from __future__ import annotations

"""Multi-year verified historical news tests, no API calls."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

import packages.data.offline_multiyear_news_context_v1 as m
from packages.data.historical_news_v1_closeout import _canonical_hash


def _accepted_fixture(tmp_path, monkeypatch, *, last=date(2021, 1, 31)):
    report = {
        "status": "PASS", "contract": m.SOURCE_INTEGRITY_V2_CONTRACT,
        "contract_fingerprint": m.HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT,
        "corpus_fingerprint": m.EXPECTED_CORPUS_FINGERPRINT,
        "raw_provider_records": m.EXPECTED_RAW_PROVIDER_RECORDS,
        "normalized_articles": m.EXPECTED_NORMALIZED_ARTICLES,
        "failed_partitions_under_v1": ["2015-07", "2026-08"],
        "effective_pit_policy": m.EFFECTIVE_PIT_POLICY,
        "authority": {"provider_calls": False, "source_integrity_accepted": True},
    }
    report["acceptance_fingerprint"] = _canonical_hash(report)
    report_path = tmp_path / m.ACCEPTED_NEWS_REPORT
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps(report), encoding="utf-8")
    month_paths = {}
    for window in m.month_windows(m.FIRST_LOOKBACK_MONTH, last):
        data = tmp_path / (window.key + ".parquet")
        receipt_path = tmp_path / (window.key + ".receipt.json")
        data.write_bytes(b"mock-original-normalized-parquet")
        receipt = {
            "status": "COMPLETE", "month": window.key,
            "contract_fingerprint": m.HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
            "normalized_sha256": m._sha(data),
        }
        receipt["receipt_fingerprint"] = _canonical_hash(receipt)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        month_paths[window.key] = {"normalized": data, "receipt": receipt_path}
    monkeypatch.setattr(m, "_month_paths",
                        lambda settings, window: month_paths[window.key])
    settings = SimpleNamespace(
        resolved_path=lambda path: tmp_path / path,
        assert_external_storage_binding=lambda name:
            None if name == "news" else pytest.fail("wrong binding"),
    )
    return settings, month_paths, report


def test_exact_normalized_receipts_and_mutation_fail_closed(tmp_path, monkeypatch):
    settings, paths, report = _accepted_fixture(tmp_path, monkeypatch)
    found, lineage = m.verified_news_partition_paths(settings, last_month=date(2021, 1, 31))
    assert len(found) == 2
    assert list(lineage["normalized_monthly_sha256"]) == ["2020-12", "2021-01"]
    assert lineage["accepted_v2_fingerprint"] == report["acceptance_fingerprint"]
    paths["2021-01"]["normalized"].write_bytes(b"changed")
    with pytest.raises(m.MultiYearNewsContextError, match="2021-01"):
        m.verified_news_partition_paths(settings, last_month=date(2021, 1, 31))


def test_2020_dec_prior_news_counts_for_early_2021_and_future_revision_unavailable(
    tmp_path, monkeypatch
):
    path = tmp_path / "sample.parquet"
    conn = duckdb.connect(database=":memory:")
    try:
        conn.execute(
            "CREATE TABLE news(article_id VARCHAR, created_at TIMESTAMPTZ, "
            "updated_at TIMESTAMPTZ, symbols_json VARCHAR)"
        )
        conn.executemany("INSERT INTO news VALUES (?, ?, ?, ?)", [
            ("dec", "2020-12-31T12:00:00Z", "2020-12-31T12:00:00Z", '["TEST"]'),
            ("revised", "2020-12-31T12:00:00Z", "2021-01-06T12:00:00Z", '["TEST"]'),
            ("revised", "2020-12-31T12:00:00Z", "2021-01-01T12:00:00Z", '["TEST"]'),
            ("other", "2021-01-03T13:00:00Z", "2021-01-03T13:00:00Z", '["OTHER"]'),
        ])
        conn.execute(f"COPY news TO '{str(path)}' (FORMAT PARQUET)")
    finally:
        conn.close()
    monkeypatch.setattr(
        m, "verified_news_partition_paths",
        lambda settings, **kwargs: ([str(path)], {"accepted_v2_fingerprint": "a" * 64}),
    )
    result = m.OfflineMultiYearNewsContext.from_accepted_history(
        SimpleNamespace(), {"TEST"}, threads=2
    )
    assert result.scanned_articles == 4
    assert result.duplicate_article_rows == 1
    early = result.prior_counts(
        "TEST", decision_utc=datetime(2021, 1, 4, 14, 35, tzinfo=UTC)
    )
    assert early["unique_articles_available_prior_7d"] == 1
    assert early["coverage_status"] == "VERIFIED_SOURCE_COVERAGE_AT_DECISION"
    later = result.prior_counts(
        "TEST", decision_utc=datetime(2021, 1, 7, 14, 35, tzinfo=UTC)
    )
    assert later["unique_articles_available_prior_7d"] == 2
    assert later["authority"]["provider_requests"] == 0


def test_unacquired_2026_day_is_missing_not_zero():
    old = m.OfflineNewsContext({}, {"accepted_v2_fingerprint": "b" * 64}, 0)
    ctx = m.OfflineMultiYearNewsContext(old, coverage_end=m.MAX_VERIFIED_COVERAGE,
                                        duplicate_article_rows=0)
    missing = ctx.prior_counts(
        "TEST", decision_utc=datetime(2026, 9, 21, 14, 35, tzinfo=UTC)
    )
    assert missing["coverage_status"] == "NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION"
    assert missing["unique_articles_available_prior_24h"] is None
    assert missing["unique_articles_available_prior_7d"] is None
    with pytest.raises(m.MultiYearNewsContextError, match="predates"):
        ctx.prior_counts(
            "TEST", decision_utc=datetime(2020, 12, 31, 14, 35, tzinfo=UTC)
        )
