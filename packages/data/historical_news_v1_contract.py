from __future__ import annotations

from datetime import date
from typing import Final

from packages.backtesting.successor_runner_contract import canonical_sha256


HISTORICAL_NEWS_V1_CONTRACT: Final[str] = "atlas-historical-news-v1"
SOURCE_PROVIDER: Final[str] = "alpaca"
SOURCE_ENDPOINT: Final[str] = "/v1beta1/news"
HISTORY_START: Final[date] = date(2015, 1, 1)
HISTORY_END: Final[date] = date(2026, 9, 19)
PAGE_LIMIT: Final[int] = 50
INCLUDE_CONTENT: Final[bool] = True
SORT_ORDER: Final[str] = "asc"
PARTITIONING: Final[str] = "CALENDAR_MONTH_BY_UPDATED_AT_QUERY_WINDOW"
RAW_FORMAT: Final[str] = "GZIP_JSONL_PROVIDER_RECORDS"
NORMALIZED_FORMAT: Final[str] = "ZSTD_PARQUET"
PIT_TEXT_AVAILABLE_AT: Final[str] = "UPDATED_AT"
NEWS_STORAGE_CATEGORY: Final[str] = "news"

AUTHORITY: Final[dict[str, object]] = {
    "source_acquisition_only": True,
    "predictor_generation": False,
    "strategy_outcome_access": False,
    "consumed_master_rows_permitted": 0,
    "future_blind_rows_permitted": 0,
    "broker_reads_permitted": 0,
    "broker_writes_permitted": 0,
    "order_actions_permitted": 0,
    "paper_authority": False,
    "live_authority": False,
}


def historical_news_v1_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": HISTORICAL_NEWS_V1_CONTRACT,
        "provider": SOURCE_PROVIDER,
        "endpoint": SOURCE_ENDPOINT,
        "history_start": HISTORY_START.isoformat(),
        "history_end": HISTORY_END.isoformat(),
        "page_limit": PAGE_LIMIT,
        "include_content": INCLUDE_CONTENT,
        "sort": SORT_ORDER,
        "partitioning": PARTITIONING,
        "raw_format": RAW_FORMAT,
        "normalized_format": NORMALIZED_FORMAT,
        "pit_policy": {
            "provider_created_at_retained": True,
            "provider_updated_at_retained": True,
            "retrieved_text_available_at": PIT_TEXT_AVAILABLE_AT,
            "reason": (
                "HISTORICAL_ENDPOINT_DOES_NOT_EXPOSE_FULL_ARTICLE_REVISION_HISTORY_"
                "SO_RETRIEVED_TEXT_IS_NOT_BACKDATED_TO_CREATED_AT"
            ),
        },
        "deduplication": {
            "normalized_key": "ARTICLE_ID",
            "duplicate_resolution": "LATEST_UPDATED_AT_THEN_CANONICAL_JSON",
            "raw_provider_records_preserved": True,
        },
        "storage_category": NEWS_STORAGE_CATEGORY,
        "resume_policy": (
            "REUSE_ONLY_HASH_VERIFIED_COMPLETE_MONTH_RECEIPTS_BOUND_TO_THIS_CONTRACT"
        ),
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT: Final[str] = str(
    historical_news_v1_manifest()["fingerprint"]
)
