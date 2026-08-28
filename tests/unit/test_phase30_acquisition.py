from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.backtesting.phase30_acquisition import (
    Phase30NewsAcquisition,
    Phase30NewsAcquisitionError,
    phase30_news_acquisition_bounds,
    phase30_news_shard_windows,
)
from packages.backtesting.phase30_feasibility import PHASE30_PROBE_WINDOWS
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


_PROBE_DATES = {
    "2021-08-16",
    "2026-05-06",
    "2026-05-12",
    "2026-08-11",
}


def _article(article_id: str, published: datetime, ticker: str = "ABC") -> dict[str, object]:
    return {
        "id": article_id,
        "title": "Historical company news",
        "published_utc": published.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "tickers": [ticker],
    }


class _FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def news_window(self, *, start_utc, end_utc) -> Phase30NewsWindowResult:
        self.calls += 1
        rows = [
            _article(
                f"article-{start_utc.date().isoformat()}",
                min(start_utc + timedelta(hours=12), end_utc),
            )
        ]
        for date_text in sorted(_PROBE_DATES):
            probe_time = datetime.fromisoformat(date_text).replace(tzinfo=UTC) + timedelta(hours=12)
            if start_utc <= probe_time <= end_utc:
                rows.append(_article(f"probe-{date_text}", probe_time))
        rows.sort(key=lambda row: (str(row["published_utc"]), str(row["id"])))
        return Phase30NewsWindowResult(
            articles=tuple(rows),
            page_count=1,
            request_ids=(f"request-{self.calls}",),
        )


def _seed_feasibility_evidence(
    settings: _Settings,
    *,
    research_start_ticker: str = "ABC",
) -> None:
    root = (
        settings.resolved_path(settings.data.paths.provider)
        / "massive"
        / "phase30_news_feasibility"
        / "v1"
    )
    root.mkdir(parents=True, exist_ok=True)
    for probe in PHASE30_PROBE_WINDOWS:
        date_text = probe.start_utc[:10]
        published = datetime.fromisoformat(date_text).replace(tzinfo=UTC) + timedelta(hours=12)
        ticker = research_start_ticker if probe.label == "research_start" else "ABC"
        row = _article(f"probe-{date_text}", published, ticker=ticker)
        (root / f"{probe.label}.jsonl").write_text(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
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


def test_phase30_full_news_acquisition_is_resumable_and_reconciles_feasibility(
    tmp_path: Path,
) -> None:
    settings = _Settings(tmp_path)
    _seed_feasibility_evidence(settings)
    first_client = _FakeClient()
    first = Phase30NewsAcquisition(settings, first_client).run()

    shard_count = len(phase30_news_shard_windows())
    assert first["pass"] is True
    assert first["target_outcome_rows_read"] == 0
    assert first["protected_return_rows_read"] == 0
    assert first["total_articles"] == shard_count + len(_PROBE_DATES)
    assert first_client.calls == shard_count
    assert all(
        first["checks"][f"feasibility_metadata_reconciled_{probe.label}"] is True
        for probe in PHASE30_PROBE_WINDOWS
    )

    second_client = _FakeClient()
    second = Phase30NewsAcquisition(settings, second_client).run()

    assert second["pass"] is True
    assert second["resumed_shards"] == shard_count
    assert second_client.calls == 0


def test_phase30_acquisition_fails_closed_on_feasibility_metadata_drift(
    tmp_path: Path,
) -> None:
    settings = _Settings(tmp_path)
    _seed_feasibility_evidence(settings, research_start_ticker="DIFFERENT")

    with pytest.raises(
        Phase30NewsAcquisitionError,
        match="authorized news metadata drifted from immutable feasibility evidence",
    ):
        Phase30NewsAcquisition(settings, _FakeClient()).run()
