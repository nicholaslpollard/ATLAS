from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from packages.backtesting.phase30_acquisition import (
    Phase30NewsAcquisition,
    phase30_news_acquisition_bounds,
    phase30_news_shard_windows,
)
from packages.providers.massive.phase30 import Phase30NewsWindowResult


@dataclass
class _Paths:
    provider: Path = Path("data/provider")
    derived: Path = Path("data/derived")


@dataclass
class _Data:
    paths: _Paths = field(default_factory=_Paths)


class _Settings:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.data = _Data()

    def resolved_path(self, value: Path) -> Path:
        return self.root / value


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def news_window(self, *, start_utc, end_utc) -> Phase30NewsWindowResult:
        self.calls += 1
        published = min(start_utc + timedelta(hours=12), end_utc)
        row = {
            "id": f"article-{start_utc.date().isoformat()}",
            "title": "Historical company news",
            "published_utc": published.isoformat().replace("+00:00", "Z"),
            "tickers": ["ABC"],
        }
        return Phase30NewsWindowResult(
            articles=(row,),
            page_count=1,
            request_ids=(f"request-{self.calls}",),
        )


def test_phase30_acquisition_windows_are_exact_and_contiguous() -> None:
    start, end = phase30_news_acquisition_bounds()
    windows = phase30_news_shard_windows()

    assert start.isoformat() == "2021-07-16T00:00:00+00:00"
    assert end.isoformat() == "2026-08-11T23:59:59.999999+00:00"
    assert windows[0].start_utc == start
    assert windows[-1].end_utc == end
    assert all(
        left.end_utc + timedelta(microseconds=1) == right.start_utc
        for left, right in zip(windows, windows[1:])
    )


def test_phase30_full_news_acquisition_is_resumable_without_outcomes(tmp_path: Path) -> None:
    settings = _Settings(tmp_path)
    first_client = _FakeClient()
    first = Phase30NewsAcquisition(settings, first_client).run()

    assert first["pass"] is True
    assert first["target_outcome_rows_read"] == 0
    assert first["protected_return_rows_read"] == 0
    assert first["total_articles"] == len(phase30_news_shard_windows())
    assert first_client.calls == len(phase30_news_shard_windows())

    second_client = _FakeClient()
    second = Phase30NewsAcquisition(settings, second_client).run()

    assert second["pass"] is True
    assert second["resumed_shards"] == len(phase30_news_shard_windows())
    assert second_client.calls == 0
