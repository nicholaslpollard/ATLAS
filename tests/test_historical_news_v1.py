from __future__ import annotations

from datetime import date

from packages.data.historical_news_v1 import _normalized_rows, month_windows
from packages.data.historical_news_v1_contract import (
    HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
    HISTORY_END,
    HISTORY_START,
    PIT_TEXT_AVAILABLE_AT,
    historical_news_v1_manifest,
)


def test_historical_news_v1_contract_is_frozen_and_source_only() -> None:
    manifest = historical_news_v1_manifest()
    assert manifest["fingerprint"] == HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT
    assert manifest["history_start"] == "2015-01-01"
    assert manifest["history_end"] == "2026-09-19"
    assert manifest["pit_policy"]["retrieved_text_available_at"] == "UPDATED_AT"
    assert manifest["authority"]["source_acquisition_only"] is True
    assert manifest["authority"]["predictor_generation"] is False
    assert manifest["authority"]["paper_authority"] is False
    assert manifest["authority"]["live_authority"] is False


def test_month_windows_cover_scope_without_crossing_end() -> None:
    windows = month_windows(HISTORY_START, HISTORY_END)
    assert windows[0].key == "2015-01"
    assert windows[-1].key == "2026-09"
    assert windows[0].start_utc.date() == date(2015, 1, 1)
    assert windows[-1].end_utc.date() == date(2026, 9, 19)
    assert len(windows) == 141

    for previous, current in zip(windows, windows[1:], strict=False):
        assert previous.end_utc < current.start_utc


def test_normalized_news_text_is_not_backdated_to_created_at() -> None:
    rows = _normalized_rows(
        [
            {
                "id": 123,
                "headline": "Original headline",
                "summary": "Summary",
                "content": "Final retrieved body",
                "author": "Author",
                "created_at": "2020-01-02T14:00:00Z",
                "updated_at": "2020-01-02T16:30:00Z",
                "symbols": ["ABC"],
                "images": [],
                "url": "https://example.test/article",
            }
        ]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["created_at"] == "2020-01-02T14:00:00Z"
    assert row["updated_at"] == "2020-01-02T16:30:00Z"
    assert row["pit_available_at"] == "2020-01-02T16:30:00Z"
    assert row["pit_text_policy"] == PIT_TEXT_AVAILABLE_AT


def test_normalized_news_deduplicates_article_id_by_latest_update() -> None:
    rows = _normalized_rows(
        [
            {
                "id": 99,
                "headline": "Older",
                "content": "old",
                "created_at": "2021-01-01T10:00:00Z",
                "updated_at": "2021-01-01T10:05:00Z",
                "symbols": ["ABC"],
            },
            {
                "id": 99,
                "headline": "Newer",
                "content": "new",
                "created_at": "2021-01-01T10:00:00Z",
                "updated_at": "2021-01-01T10:10:00Z",
                "symbols": ["ABC"],
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["headline"] == "Newer"
    assert rows[0]["content"] == "new"
    assert rows[0]["pit_available_at"] == "2021-01-01T10:10:00Z"
