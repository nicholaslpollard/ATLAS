from __future__ import annotations

from datetime import UTC, datetime

import pytest

from packages.core.exceptions import ProviderError
from packages.providers.massive.phase30 import MassivePhase30NewsClient


class _FakeRest:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, dict[str, object] | None]] = []

    def iter_pages(self, path: str, params: dict[str, object] | None = None):
        self.calls.append((path, params))
        yield from self.pages


def _article(
    article_id: str,
    published_utc: str,
    *,
    title: str | None = None,
    tickers: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": article_id,
        "published_utc": published_utc,
        "title": title or f"title-{article_id}",
        "tickers": ["ABC"] if tickers is None else tickers,
        "description": f"description-{article_id}",
    }


def test_phase30_news_client_is_bounded_sorted_deduplicated_and_preserves_ticker_text() -> None:
    first_b = _article("b", "2021-08-16T12:00:00Z", tickers=["brk.B"])
    fake = _FakeRest(
        [
            {"request_id": "r1", "results": [first_b]},
            {
                "request_id": "r2",
                "results": [
                    _article("a", "2021-08-16T11:00:00Z"),
                    dict(first_b),
                ],
            },
        ]
    )
    client = MassivePhase30NewsClient(fake)  # type: ignore[arg-type]

    result = client.news_window(
        start_utc=datetime(2021, 8, 16, 0, 0, tzinfo=UTC),
        end_utc=datetime(2021, 8, 16, 23, 59, 59, tzinfo=UTC),
    )

    assert [row["id"] for row in result.articles] == ["a", "b"]
    assert result.articles[1]["tickers"] == ["brk.B"]
    assert result.page_count == 2
    assert result.request_ids == ("r1", "r2")
    assert len(fake.calls) == 1
    path, params = fake.calls[0]
    assert path == "/v2/reference/news"
    assert params == {
        "published_utc.gte": "2021-08-16T00:00:00Z",
        "published_utc.lte": "2021-08-16T23:59:59Z",
        "order": "asc",
        "sort": "published_utc",
        "limit": 1000,
    }


def test_phase30_news_client_rejects_conflicting_duplicate_article_ids() -> None:
    fake = _FakeRest(
        [
            {
                "results": [
                    _article("same", "2021-08-16T11:00:00Z", title="first"),
                    _article("same", "2021-08-16T11:00:00Z", title="changed"),
                ]
            }
        ]
    )
    client = MassivePhase30NewsClient(fake)  # type: ignore[arg-type]

    with pytest.raises(ProviderError, match="conflicting payloads"):
        client.news_window(
            start_utc=datetime(2021, 8, 16, 0, 0, tzinfo=UTC),
            end_utc=datetime(2021, 8, 16, 23, 59, 59, tzinfo=UTC),
        )


def test_phase30_news_client_rejects_out_of_window_timestamp() -> None:
    fake = _FakeRest([{"results": [_article("x", "2021-08-17T00:00:00Z")] }])
    client = MassivePhase30NewsClient(fake)  # type: ignore[arg-type]

    with pytest.raises(ProviderError, match="outside the requested window"):
        client.news_window(
            start_utc=datetime(2021, 8, 16, 0, 0, tzinfo=UTC),
            end_utc=datetime(2021, 8, 16, 23, 59, 59, tzinfo=UTC),
        )


def test_phase30_news_client_rejects_malformed_ticker_association() -> None:
    article = _article("x", "2021-08-16T10:00:00Z")
    article["tickers"] = "ABC"
    fake = _FakeRest([{"results": [article]}])
    client = MassivePhase30NewsClient(fake)  # type: ignore[arg-type]

    with pytest.raises(ProviderError, match="tickers must be a list"):
        client.news_window(
            start_utc=datetime(2021, 8, 16, 0, 0, tzinfo=UTC),
            end_utc=datetime(2021, 8, 16, 23, 59, 59, tzinfo=UTC),
        )


def test_phase30_news_client_rejects_naive_bounds() -> None:
    fake = _FakeRest([])
    client = MassivePhase30NewsClient(fake)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="timezone-aware"):
        client.news_window(
            start_utc=datetime(2021, 8, 16, 0, 0),
            end_utc=datetime(2021, 8, 16, 23, 59, 59, tzinfo=UTC),
        )
