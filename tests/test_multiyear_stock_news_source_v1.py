from __future__ import annotations

"""Offline stock/news join tests with frozen original case denominator."""

from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.multiyear_stock_news_source_v1 as m
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


def _census():
    cases = []
    for year, item in ((2021, 1), (2025, 2)):
        cases.append({
            "case_id": f"case-{item}", "ticker": "TEST",
            "signal_session": f"{year}-03-01",
            "entry_session": f"{year}-03-02",
            "planned_option_decision_at_utc": f"{year}-03-02T14:35:00+00:00",
            "source_status": "ELIGIBLE_NEEDS_VERIFIED_NATIVE_RAW_OPEN_AND_PIT_CHAIN",
            "source_selection_integrity_fingerprint": "b" * 64,
            "source_selection_analysis_fingerprint": "a" * 64,
            "native_raw_entry_open": None, "selected_option_symbol": None,
            "no_outcome_or_return_fields_projected": True,
        })
    by_year = {
        str(year): {
            "accepted_development_daily_long_signals":
                (1 if year in (2021, 2025) else 0),
            "source_authority": (
                "NEEDS_SEPARATE_PROSPECTIVE_OR_ACCEPTED_2026_SOURCE"
                if year == 2026 else "ACCEPTED_DEVELOPMENT_SELECTED_SIGNAL_METADATA_ONLY"
            ),
        }
        for year in range(2021, 2027)
    }
    doc = {
        "contract": m.STOCK_CONTRACT,
        "status": "SIX_YEAR_VISIBLE_ACCEPTED_SIGNAL_CENSUS_SOURCE_ONLY",
        "authority": m.STOCK_AUTHORITY,
        "provider_requests": 0,
        "protected_outcomes_read": 0,
        "original_source_integrity_fingerprint": "b" * 64,
        "conditioning_analysis_fingerprint": "a" * 64,
        "daily_long_case_denominator": len(cases),
        "by_year": by_year,
        "cases": cases,
    }
    doc["census_fingerprint"] = _fingerprint(doc)
    return doc


class FakeNews:
    lineage = {"accepted_v2_fingerprint": "c" * 64}
    coverage_end = date(2026, 9, 19)
    scanned_articles = 20
    duplicate_article_rows = 1

    def prior_counts(self, ticker, *, decision_utc):
        assert ticker == "TEST" and decision_utc.tzinfo is not None
        if decision_utc.year == 2021:
            return {
                "coverage_status": "VERIFIED_SOURCE_COVERAGE_AT_DECISION",
                "unique_articles_available_prior_24h": 2,
                "unique_articles_available_prior_7d": 3,
            }
        return {
            "coverage_status": "NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION",
            "unique_articles_available_prior_24h": None,
            "unique_articles_available_prior_7d": None,
        }


def test_all_years_and_missing_news_preserved_in_source_denominator(tmp_path):
    census = _census()
    report = m.join_stock_pit_news(census, FakeNews())
    assert report["original_stock_signal_denominator"] == 2
    assert report["news_positive_24h_signals"] == 1
    assert report["news_positive_7d_signals"] == 1
    assert report["missing_news_source_signals"] == 1
    assert report["six_year_coverage"]["2021"]["original_stock_signal_denominator"] == 1
    assert report["six_year_coverage"]["2026"]["original_stock_signal_denominator"] == 0
    assert report["rows"][1]["prior_24h_news_articles"] is None
    assert report["rows"][1]["news_coverage_status"] == "NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION"
    assert report["rows"][0]["native_raw_entry_open"] is None
    assert report["rows"][0]["selected_option_symbol"] is None
    assert report["authority"]["historical_option_trade_pnl"] is False
    assert report["provider_requests"] == report["protected_outcomes_read"] == 0
    assert report["source_join_fingerprint"] == _fingerprint({
        k: v for k, v in report.items() if k != "source_join_fingerprint"
    })
    settings = SimpleNamespace(resolved_path=lambda p: tmp_path / p)
    target, status = m.write_stock_news_source(settings, census, report)
    assert target.is_file() and status == "WRITTEN_NEW_STOCK_NEWS_FEATURES"
    assert m.inspect_existing_join(settings, census) == report
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(m.StockNewsSourceError, match="cannot be trusted"):
        m.inspect_existing_join(settings, census)


def test_duplicate_and_modified_original_source_cannot_join():
    census = _census()
    census["cases"][1]["case_id"] = census["cases"][0]["case_id"]
    census["census_fingerprint"] = _fingerprint({
        k: v for k, v in census.items() if k != "census_fingerprint"
    })
    with pytest.raises(m.StockNewsSourceError, match="duplicate"):
        m.join_stock_pit_news(census, FakeNews())
    census = _census()
    census["cases"][0]["native_raw_entry_open"] = "123.0"
    census["census_fingerprint"] = _fingerprint({
        k: v for k, v in census.items() if k != "census_fingerprint"
    })
    with pytest.raises(m.StockNewsSourceError, match="unaccepted"):
        m.join_stock_pit_news(census, FakeNews())


def test_bad_news_counts_refused_instead_of_fabricating_zero():
    census = _census()
    class BadNews(FakeNews):
        def prior_counts(self, ticker, *, decision_utc):
            return {
                "coverage_status": "NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION",
                "unique_articles_available_prior_24h": 0,
                "unique_articles_available_prior_7d": 0,
            }
    with pytest.raises(m.StockNewsSourceError, match="false zero"):
        m.join_stock_pit_news(census, BadNews())


def test_existing_join_reused_without_reopening_70_news_partitions(tmp_path, monkeypatch):
    census = _census()
    settings = SimpleNamespace(
        project_root=tmp_path, resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda name:
            None if name in {"news", "research_evidence"} else pytest.fail("wrong binding")
    )
    stock = settings.resolved_path(
        m.STOCK_REL + "_" + census["original_source_integrity_fingerprint"][:16] + ".json"
    )
    stock.parent.mkdir(parents=True)
    stock.write_text(__import__("json").dumps(census), encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        m.OfflineMultiYearNewsContext, "from_accepted_history",
        lambda *args, **kwargs: calls.append("scan") or FakeNews()
    )
    first = m.build_stock_news_source(settings)
    second = m.build_stock_news_source(settings)
    assert first[3] == "WRITTEN_NEW_STOCK_NEWS_FEATURES"
    assert second[3] == "REUSED_VERIFIED_FEATURE_SOURCE_NO_NEWS_RESCAN"
    assert len(calls) == 1
    assert first[1] == second[1]
