from __future__ import annotations

"""Reusable 2021–2026 PIT-safe, offline news metadata index.

Reads all verified relevant month partitions once, not once per simulated
trade. Latest retrieved article revision is unavailable until BOTH provider
created and updated timestamps; final text is never backdated. Never mistake
the end of stored news coverage for a true zero-news day.
"""

import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import duckdb

from packages.core.settings import AtlasSettings
from packages.data.historical_news_v1 import _month_paths, month_windows
from packages.data.historical_news_v1_closeout import (
    EXPECTED_NORMALIZED_ARTICLES, EXPECTED_RAW_PROVIDER_RECORDS, _canonical_hash,
)
from packages.data.historical_news_v1_contract import (
    HISTORY_END, HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
)
from packages.data.historical_news_v1_source_integrity_v2 import (
    EFFECTIVE_PIT_POLICY, EXPECTED_CORPUS_FINGERPRINT,
    HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT,
    SOURCE_INTEGRITY_V2_CONTRACT, effective_pit_available_at,
)
from packages.data.offline_news_context_v1 import (
    ACCEPTED_NEWS_REPORT, OfflineNewsContext,
    OfflineNewsContextError, _sha, _symbol_list, _timestamp,
)

CONTRACT = "atlas-offline-six-year-pit-news-context-v1"
FIRST_LOOKBACK_MONTH = date(2020, 12, 1)
MIN_SIGNAL = date(2021, 1, 1)
MAX_VERIFIED_COVERAGE = HISTORY_END
EXPECTED_MONTHS = 70
AUTHORITY = {
    "provider_requests": 0, "broker_calls": 0, "protected_outcomes_read": 0,
    "news_text_or_sentiment_alpha": False,
    "final_article_revision_backdated": False,
    "paper": False, "live": False,
}


class MultiYearNewsContextError(OfflineNewsContextError):
    pass


def verified_news_partition_paths(
    settings: AtlasSettings, *,
    last_month: date = MAX_VERIFIED_COVERAGE,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    settings.assert_external_storage_binding("news")
    if not MIN_SIGNAL <= last_month <= MAX_VERIFIED_COVERAGE:
        raise MultiYearNewsContextError("news partition scope exceeds accepted corpus")
    report_path = settings.resolved_path(ACCEPTED_NEWS_REPORT)
    if report_path.is_symlink() or not report_path.is_file():
        raise MultiYearNewsContextError("accepted source-integrity V2 news report missing")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        unsigned = dict(report)
        accepted_fp = unsigned.pop("acceptance_fingerprint", None)
        if (
            report.get("status") != "PASS"
            or report.get("contract") != SOURCE_INTEGRITY_V2_CONTRACT
            or report.get("contract_fingerprint")
            != HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT
            or report.get("corpus_fingerprint") != EXPECTED_CORPUS_FINGERPRINT
            or report.get("raw_provider_records") != EXPECTED_RAW_PROVIDER_RECORDS
            or report.get("normalized_articles") != EXPECTED_NORMALIZED_ARTICLES
            or report.get("failed_partitions_under_v1") != ["2015-07", "2026-08"]
            or report.get("effective_pit_policy") != EFFECTIVE_PIT_POLICY
            or report.get("authority", {}).get("provider_calls") is not False
            or report.get("authority", {}).get("source_integrity_accepted") is not True
            or accepted_fp != _canonical_hash(unsigned)
        ):
            raise MultiYearNewsContextError("accepted full historical news lineage changed")
        windows = month_windows(FIRST_LOOKBACK_MONTH, last_month)
        if last_month == MAX_VERIFIED_COVERAGE and len(windows) != EXPECTED_MONTHS:
            raise MultiYearNewsContextError("full six-year news month census changed")
        paths: list[str] = []
        bindings: dict[str, str] = {}
        for index, window in enumerate(windows, 1):
            mapped = _month_paths(settings, window)
            data, receipt_path = mapped["normalized"], mapped["receipt"]
            if (
                data.is_symlink() or receipt_path.is_symlink()
                or not data.is_file() or not receipt_path.is_file()
            ):
                raise MultiYearNewsContextError(
                    f"accepted normalized news month missing: {window.key}"
                )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            rr = dict(receipt)
            signature = rr.pop("receipt_fingerprint", None)
            if (
                receipt.get("status") != "COMPLETE"
                or receipt.get("month") != window.key
                or receipt.get("contract_fingerprint")
                != HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT
                or signature != _canonical_hash(rr)
                or receipt.get("normalized_sha256") != _sha(data)
            ):
                raise MultiYearNewsContextError(
                    f"original local news receipt or normalized bytes changed: {window.key}"
                )
            paths.append(str(data))
            bindings[window.key] = receipt["normalized_sha256"]
            if progress and (index % 12 == 0 or index == len(windows)):
                progress({
                    "stage": "NEWS_PARTITION_SHA_PREFLIGHT",
                    "verified_months": index, "total_months": len(windows),
                    "provider_requests": 0,
                })
        return paths, {
            "accepted_v2_fingerprint": accepted_fp,
            "accepted_corpus_fingerprint": EXPECTED_CORPUS_FINGERPRINT,
            "normalized_monthly_sha256": bindings,
            "months": len(windows),
            "first_lookback_month": FIRST_LOOKBACK_MONTH.isoformat(),
            "last_source_day": last_month.isoformat(),
        }
    except MultiYearNewsContextError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise MultiYearNewsContextError("accepted historical news source unreadable") from exc


class OfflineMultiYearNewsContext:
    """Indexed metadata counts; no network, no historical revision speculation."""

    def __init__(self, prior: OfflineNewsContext, *,
                 coverage_end: date, duplicate_article_rows: int) -> None:
        self.prior = prior
        self.coverage_end = coverage_end
        self.duplicate_article_rows = duplicate_article_rows

    @classmethod
    def from_accepted_history(
        cls, settings: AtlasSettings, tickers: set[str], *,
        threads: int = 4,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> "OfflineMultiYearNewsContext":
        if (
            not tickers or any(not isinstance(x, str) or not x for x in tickers)
            or type(threads) is not int or not 1 <= threads <= 8
        ):
            raise MultiYearNewsContextError("nonempty ticker set and 1..8 threads required")
        paths, lineage = verified_news_partition_paths(settings, progress=progress)
        chosen: dict[str, tuple[datetime, tuple[str, ...]]] = {}
        scanned = 0
        relevant_rows = 0
        con = duckdb.connect(database=":memory:")
        try:
            con.execute(f"PRAGMA threads={threads}")
            con.execute(
                "SELECT article_id, created_at, updated_at, symbols_json "
                "FROM read_parquet(?, hive_partitioning=false)", [paths]
            )
            while batch := con.fetchmany(8192):
                for article_id, created, updated, symbols_json in batch:
                    scanned += 1
                    if progress and scanned % 50_000 == 0:
                        progress({
                            "stage": "MULTIYEAR_NEWS_METADATA_SCAN",
                            "articles_scanned": scanned, "provider_requests": 0,
                        })
                    if not isinstance(article_id, str) or not article_id:
                        raise MultiYearNewsContextError("missing normalized article identity")
                    effective = effective_pit_available_at(
                        _timestamp(created), _timestamp(updated)
                    )
                    relevant = tuple(s for s in _symbol_list(symbols_json) if s in tickers)
                    if not relevant:
                        continue
                    relevant_rows += 1
                    candidate = (effective, relevant)
                    previous = chosen.get(article_id)
                    if previous is None or candidate > previous:
                        chosen[article_id] = candidate
        except (OSError, ValueError, TypeError, duckdb.Error) as exc:
            raise MultiYearNewsContextError("historical Parquet metadata scan failed") from exc
        finally:
            con.close()
        by_symbol: dict[str, list[datetime]] = defaultdict(list)
        for effective, symbols in chosen.values():
            for ticker in symbols:
                by_symbol[ticker].append(effective)
        prior = OfflineNewsContext(dict(by_symbol), lineage, scanned)
        return cls(
            prior, coverage_end=MAX_VERIFIED_COVERAGE,
            duplicate_article_rows=relevant_rows - len(chosen),
        )

    @property
    def lineage(self) -> dict[str, Any]:
        return self.prior.lineage

    @property
    def scanned_articles(self) -> int:
        return self.prior.scanned_articles

    def prior_counts(self, ticker: str, *, decision_utc: datetime) -> dict[str, Any]:
        if not isinstance(decision_utc, datetime) or decision_utc.tzinfo is None:
            raise MultiYearNewsContextError("decision must be timezone-aware")
        when = decision_utc.astimezone(UTC)
        if when.date() < MIN_SIGNAL:
            raise MultiYearNewsContextError("news source decision predates six-year scope")
        if when.date() > self.coverage_end:
            # An unacquired day cannot be assigned zero observed headlines.
            return {
                "ticker": ticker,
                "decision_cutoff_utc": when.isoformat(),
                "coverage_status": "NEWS_SOURCE_NOT_ACQUIRED_THROUGH_DECISION",
                "unique_articles_available_prior_24h": None,
                "unique_articles_available_prior_7d": None,
                "last_accepted_source_day": self.coverage_end.isoformat(),
                "authority": AUTHORITY,
            }
        result = self.prior.prior_counts(ticker, decision_utc=when)
        return {
            **result,
            "coverage_status": "VERIFIED_SOURCE_COVERAGE_AT_DECISION",
            "last_accepted_source_day": self.coverage_end.isoformat(),
            "authority": AUTHORITY,
        }
