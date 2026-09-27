from __future__ import annotations

"""Read-only 2022 news metadata index from accepted, D:-bound Alpaca files.

No provider transport, full-corpus re-acquisition, text-sentiment inference,
historical revision reconstruction, or strategy/outcome access is permitted.
"""

import hashlib
import json
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import duckdb

from packages.core.settings import AtlasSettings
from packages.data.historical_news_v1 import _month_paths, month_windows
from packages.data.historical_news_v1_closeout import (
    EXPECTED_NORMALIZED_ARTICLES,
    EXPECTED_RAW_PROVIDER_RECORDS,
    _canonical_hash,
)
from packages.data.historical_news_v1_contract import (
    HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
)
from packages.data.historical_news_v1_source_integrity_v2 import (
    EXPECTED_CORPUS_FINGERPRINT,
    HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT,
    SOURCE_INTEGRITY_V2_CONTRACT,
    effective_pit_available_at,
)

CONTRACT = "atlas-offline-2022-news-context-v1"
ACCEPTED_NEWS_REPORT = (
    "data/news/manifests/alpaca/historical_news_v1_source_integrity_v2.json"
)
AUTHORITY = {
    "provider_requests": 0,
    "full_article_revision_history_available": False,
    "news_text_sentiment_inferred": False,
    "outcome_access": False,
    "paper": False,
    "live": False,
}


class OfflineNewsContextError(ValueError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _accepted_paths(settings: AtlasSettings) -> tuple[list[str], dict[str, Any]]:
    settings.assert_external_storage_binding("news")
    path = settings.resolved_path(ACCEPTED_NEWS_REPORT)
    if path.is_symlink() or not path.is_file():
        raise OfflineNewsContextError("accepted local news V2 report missing")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        unsigned = dict(report)
        fingerprint = unsigned.pop("acceptance_fingerprint", None)
        if (
            report.get("status") != "PASS"
            or report.get("contract") != SOURCE_INTEGRITY_V2_CONTRACT
            or report.get("contract_fingerprint")
            != HISTORICAL_NEWS_V1_SOURCE_INTEGRITY_V2_FINGERPRINT
            or report.get("corpus_fingerprint") != EXPECTED_CORPUS_FINGERPRINT
            or fingerprint != _canonical_hash(unsigned)
            or report.get("raw_provider_records") != EXPECTED_RAW_PROVIDER_RECORDS
            or report.get("normalized_articles") != EXPECTED_NORMALIZED_ARTICLES
            or report.get("failed_partitions_under_v1") != ["2015-07", "2026-08"]
            or report.get("effective_pit_policy") != "MAX_CREATED_AT_UPDATED_AT_CONSERVATIVE"
            or report.get("authority", {}).get("source_integrity_accepted") is not True
            or report.get("authority", {}).get("provider_calls") is not False
        ):
            raise OfflineNewsContextError("accepted news chronology lineage changed")
        parquet_paths: list[str] = []
        partition_shas: dict[str, str] = {}
        for window in month_windows(
            datetime(2022, 1, 1, tzinfo=UTC).date(),
            datetime(2022, 12, 31, tzinfo=UTC).date(),
        ):
            paths = _month_paths(settings, window)
            receipt_path = paths["receipt"]
            data_path = paths["normalized"]
            if (
                receipt_path.is_symlink()
                or data_path.is_symlink()
                or not receipt_path.is_file()
                or not data_path.is_file()
            ):
                raise OfflineNewsContextError("missing intact 2022 normalized news partition")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            unsigned_receipt = dict(receipt)
            receipt_fp = unsigned_receipt.pop("receipt_fingerprint", None)
            if (
                receipt_fp != _canonical_hash(unsigned_receipt)
                or receipt.get("status") != "COMPLETE"
                or receipt.get("month") != window.key
                or receipt.get("contract_fingerprint")
                != HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT
                or receipt.get("normalized_sha256") != _sha(data_path)
            ):
                raise OfflineNewsContextError(
                    f"original normalized news receipt/bytes changed: {window.key}"
                )
            parquet_paths.append(str(data_path))
            partition_shas[window.key] = receipt["normalized_sha256"]
        if len(parquet_paths) != 12:
            raise OfflineNewsContextError("2022 news partition census incomplete")
        return parquet_paths, {
            "accepted_v2_fingerprint": fingerprint,
            "accepted_corpus_fingerprint": EXPECTED_CORPUS_FINGERPRINT,
            "normalized_2022_monthly_sha256": partition_shas,
        }
    except OfflineNewsContextError:
        raise
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise OfflineNewsContextError("accepted news metadata cannot be trusted") from exc


def _timestamp(value: object) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise OfflineNewsContextError("normalized news timestamp missing timezone")
    return value.astimezone(UTC)


def _symbol_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise OfflineNewsContextError("normalized news symbols JSON malformed")
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise OfflineNewsContextError("invalid normalized news symbols JSON") from exc
    if not isinstance(decoded, list) or any(not isinstance(s, str) for s in decoded):
        raise OfflineNewsContextError("news symbols must be an array of strings")
    return tuple(sorted(set(decoded)))


class OfflineNewsContext:
    """Article-ID-deduplicated conservative news-count lookback by ticker.

    The final retrieved text is not assumed to be its historical first edition.
    News counts are metadata-only and cannot access stock or option outcomes.
    """

    def __init__(self, by_ticker: dict[str, list[datetime]],
                 lineage: dict[str, Any], scanned_articles: int) -> None:
        self.by_ticker = {key: tuple(sorted(values)) for key, values in by_ticker.items()}
        self.lineage = lineage
        self.scanned_articles = scanned_articles

    @classmethod
    def from_accepted_2022(
        cls, settings: AtlasSettings, tickers: set[str],
        *, threads: int = 4,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> "OfflineNewsContext":
        if not tickers or any(not s or not isinstance(s, str) for s in tickers):
            raise OfflineNewsContextError("explicit nonempty ticker universe required")
        if type(threads) is not int or not 1 <= threads <= 8:
            raise OfflineNewsContextError("news query threads outside 1..8")
        paths, lineage = _accepted_paths(settings)
        # Stream only four metadata fields from the twelve 2022 Parquet partitions.
        # A late revision supersedes earlier versions of the same article ID;
        # it must not be backdated to the initial article timestamp.
        chosen: dict[str, tuple[datetime, tuple[str, ...]]] = {}
        con = duckdb.connect(database=":memory:")
        scanned = 0
        try:
            con.execute(f"PRAGMA threads={threads}")
            con.execute(
                "SELECT article_id, created_at, updated_at, symbols_json "
                "FROM read_parquet(?, hive_partitioning=false)",
                [paths],
            )
            while rows := con.fetchmany(8192):
                for article_id, created, updated, symbols_json in rows:
                    scanned += 1
                    if progress and scanned % 50_000 == 0:
                        progress({"stage": "NEWS_METADATA_SCAN",
                                  "articles_scanned": scanned, "provider_requests": 0})
                    if not isinstance(article_id, str) or not article_id:
                        raise OfflineNewsContextError("article ID missing")
                    effective = effective_pit_available_at(
                        _timestamp(created), _timestamp(updated)
                    )
                    symbols = _symbol_list(symbols_json)
                    # Restrict indexing to the stock opportunities in this exact
                    # development cohort, not every global headline.
                    relevant = tuple(x for x in symbols if x in tickers)
                    if not relevant:
                        continue
                    candidate = (effective, relevant)
                    previous = chosen.get(article_id)
                    if previous is None or candidate > previous:
                        chosen[article_id] = candidate
        except OfflineNewsContextError:
            raise
        except (OSError, ValueError, TypeError, duckdb.Error) as exc:
            raise OfflineNewsContextError("local news Parquet read failed") from exc
        finally:
            con.close()
        if progress:
            progress({"stage": "NEWS_METADATA_SCAN",
                      "articles_scanned": scanned, "provider_requests": 0})
        events: dict[str, list[datetime]] = defaultdict(list)
        for available, symbols in chosen.values():
            for ticker in symbols:
                events[ticker].append(available)
        return cls(dict(events), lineage, scanned)

    def prior_counts(self, ticker: str, *, decision_utc: datetime) -> dict[str, Any]:
        if not isinstance(decision_utc, datetime) or decision_utc.tzinfo is None:
            raise OfflineNewsContextError("decision cutoff must be timezone-aware")
        cutoff = decision_utc.astimezone(UTC)
        times = self.by_ticker.get(ticker, ())
        end = bisect_right(times, cutoff)
        last24h = bisect_left(times, cutoff - timedelta(hours=24))
        last7d = bisect_left(times, cutoff - timedelta(days=7))
        return {
            "ticker": ticker,
            "decision_cutoff_utc": cutoff.isoformat(),
            "unique_articles_available_prior_24h": end - last24h,
            "unique_articles_available_prior_7d": end - last7d,
            "news_time_basis": "MAX_PROVIDER_CREATED_UPDATED_CONSERVATIVE",
            "final_retrieved_text_not_assumed_available_before_update": True,
            "authority": AUTHORITY,
        }
