from __future__ import annotations
"""V101 source/no-lookahead news filter tests; no provider or broker requests."""
from datetime import UTC, datetime
import gzip
import hashlib
import json

import pytest
from scripts import run_spy_v101_news_metadata_gate_quote_replay as v101

class News:
    def __init__(self, count24, count7, status="VERIFIED_SOURCE_COVERAGE_AT_DECISION"):
        self.n24 = count24
        self.n7 = count7
        self.status = status
        self.seen = []
    def prior_counts(self, ticker, *, decision_utc):
        self.seen.append((ticker, decision_utc))
        return {
            "coverage_status": self.status,
            "unique_articles_available_prior_24h": self.n24,
            "unique_articles_available_prior_7d": self.n7,
            "decision_cutoff_utc": decision_utc.isoformat(),
            "authority": {"provider_requests": 0, "news_text_or_sentiment_alpha": False},
        }


def test_original_et_clock_uses_only_historical_utc_cutoff():
    news = News(1,3)
    record = v101.gate_decision("2022_full", "2022-06-01T09:40:01-04:00", "q", news)
    assert news.seen == [("SPY", datetime(2022,6,1,13,40,1,tzinfo=UTC))]
    assert record["status"] == "QUALIFIED_NEWS_METADATA"
    assert v101.passes("NEWS_24H_AT_LEAST_1", record) is True
    assert v101.passes("NEWS_7D_AT_LEAST_3", record) is True
    assert v101.passes("NEWS_24H_ZERO", record) is False


def test_verified_zero_articles_is_not_missing_news():
    record = v101.gate_decision("2021_full", "2021-01-04T09:35:01-05:00", "q", News(0,0))
    assert v101.passes("NEWS_24H_ZERO", record) is True
    assert v101.passes("NEWS_24H_AT_LEAST_1", record) is False
    assert v101.passes("NEWS_7D_AT_LEAST_3", record) is False


def test_unknown_source_must_not_become_a_quiet_news_signal():
    record = v101.gate_decision("2024_full", "2024-01-02T09:35:01-05:00", "q",
                                News(None,None,"NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION"))
    assert record["status"] == "NEWS_SOURCE_NOT_ASOF_QUALIFIED"
    assert all(v101.passes(g,record) is None for g in v101.GATES)


def test_2020_original_has_no_qualified_news_and_no_spurious_reader_call():
    reader = News(0,0)
    record = v101.gate_decision("2020_SOURCE_PARTIAL","2020-04-09T09:35:01-04:00","q",reader)
    assert reader.seen == []
    assert record["status"] == "NEWS_SOURCE_OUTSIDE_VERIFIED_YEAR_SCOPE"
    assert v101.passes("NEWS_24H_ZERO",record) is None


@pytest.mark.parametrize("period,stamp", [
    ("2022_full","2023-06-01T09:35:01-04:00"),
    ("2025_h2","2025-06-30T09:35:01-04:00"),
    ("2026_janapr","2026-05-12T09:35:01-04:00"),
    ("2021_full","2021-01-01T09:35:01"),
])
def test_other_year_precohort_protected_and_naive_clocks_rejected(period,stamp):
    with pytest.raises(v101.V101Error,match="CLOCK"):
        v101.gate_decision(period,stamp,"q",News(1,3))


def test_news_count_quality_rejects_negative_boolean_null_and_inconsistent():
    for x,y in ((-1,2),(3,2),(True,2),(None,4)):
        with pytest.raises(v101.V101Error,match="COUNT"):
            v101.gate_decision("2022_full","2022-06-01T09:35:01-04:00","q",News(x,y))


def test_original_trial_exit_sha_parent_and_full_24_variant_grid():
    class V100:
        @staticmethod
        def check(item):
            assert item["fingerprint"].startswith("sig")
            return item
    groups=[]
    for policy in ("control_50_100","balanced_35_100","runner_35_150"):
        for lag in (1,3):
            trial={"fingerprint":f"sig-{policy}-{lag}","session":"2022-02-02",
                   "strategy":"impulse_0935","policy":policy,"lag_seconds":lag,
                   "actual_broker_fills":0}
            checks=[{"fingerprint":f"sig-{policy}-{lag}-{dwell}",
                     "original_trial_sha":trial["fingerprint"],
                     "session":trial["session"],"strategy":trial["strategy"],
                     "policy":policy,"lag_seconds":lag,
                     "limit_rest_seconds":dwell,"actual_broker_fills":0}
                    for dwell in (0,3,10,30)]
            groups.append({"original_v84_trial":trial,"original_v86_exit_rechecks":checks})
    assert len(v101.original_pairs({"original_24_variant_economic_trials":groups},v100=V100))==24
    groups[0]["original_v86_exit_rechecks"][0]["original_trial_sha"]="sig-wrong"
    with pytest.raises(v101.V101Error,match="PARENT"):
        v101.original_pairs({"original_24_variant_economic_trials":groups},v100=V100)


def test_new_original_evidence_is_signed_gzipped_and_immutable(tmp_path):
    class V100:
        @staticmethod
        def _fingerprint(item):
            return hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()
    path=tmp_path/"report.json.gz"
    receipt=v101.signed_write(path,{"contract":"test","value":2},V100)
    raw=path.read_bytes()
    obj=json.loads(gzip.decompress(raw))
    assert obj["fingerprint"]==receipt["signed_fingerprint"]
    assert hashlib.sha256(raw).hexdigest()==receipt["sha256"]
    with pytest.raises(FileExistsError):
        v101.signed_write(path,{"contract":"test"},V100)


def test_hypothetical_comparison_is_news_covered_years_only():
    assert v101.NEWS_PERIODS == (
        "2021_full","2022_full","2023_full","2024_full","2025_h2","2026_janapr")
    assert len(v101.GATES)==3


def test_protected_master_holdout_partitions_not_opened_by_v101_source_reader(monkeypatch):
    from packages.data import offline_multiyear_news_context_v1 as news
    scanned = []
    def read_months(settings, *, last_month, progress=None):
        scanned.append(last_month.isoformat())
        raise v101.V101Error("TEST_STOP_BEFORE_PARQUET_SCAN")
    monkeypatch.setattr(news,"verified_news_partition_paths",read_months)
    with pytest.raises(v101.V101Error,match="TEST_STOP"):
        v101.accepted_news_to_april_2026(object())
    assert scanned==["2026-04-01"]
