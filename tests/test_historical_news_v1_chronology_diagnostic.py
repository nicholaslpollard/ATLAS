from __future__ import annotations

import gzip
import os
from pathlib import Path

from packages.data.historical_news_v1 import (
    _normalized_rows,
    _stable_json,
    _write_normalized_parquet,
)
from packages.data.historical_news_v1_chronology_diagnostic import (
    _chronology_fields,
    _normalized_anomalies_for_month,
    _select_raw_records,
)


def _record(
    article_id: int,
    *,
    created_at: str,
    updated_at: str,
    headline: str = "Headline",
) -> dict[str, object]:
    return {
        "id": article_id,
        "headline": headline,
        "summary": "Summary",
        "content": "Body",
        "author": "Author",
        "created_at": created_at,
        "updated_at": updated_at,
        "symbols": ["ABC"],
        "images": [],
        "url": "https://example.test/article",
        "source": "benzinga",
    }


def test_chronology_fields_identifies_pit_before_creation() -> None:
    fields = _chronology_fields(
        created_at="2020-01-02T14:05:00Z",
        updated_at="2020-01-02T14:00:00Z",
        pit_available_at="2020-01-02T14:00:00Z",
    )

    assert fields["updated_before_created"] is True
    assert fields["updated_before_created_seconds"] == 300.0
    assert fields["pit_before_created"] is True
    assert fields["pit_equals_updated"] is True


def test_select_raw_records_matches_acquisition_duplicate_resolution(
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "articles.jsonl.gz"
    records = [
        _record(
            7,
            created_at="2020-01-02T14:00:00Z",
            updated_at="2020-01-02T14:05:00Z",
            headline="Older",
        ),
        _record(
            7,
            created_at="2020-01-02T14:00:00Z",
            updated_at="2020-01-02T14:10:00Z",
            headline="Newer",
        ),
    ]
    raw_lines = b"".join(
        (_stable_json(item) + "\n").encode("utf-8")
        for item in records
    )
    raw_path.write_bytes(gzip.compress(raw_lines, compresslevel=6, mtime=0))

    selected = _select_raw_records(raw_path, {"7"})

    assert selected["7"]["headline"] == "Newer"
    assert selected["7"]["updated_at"] == "2020-01-02T14:10:00Z"


def test_normalized_diagnostic_finds_anomaly_through_hive_style_path(
    tmp_path: Path,
) -> None:
    record = _record(
        9,
        created_at="2020-01-02T14:05:00Z",
        updated_at="2020-01-02T14:00:00Z",
    )
    rows = _normalized_rows([record])
    normalized_path = (
        tmp_path
        / "year=2020"
        / "month=01"
        / "articles.parquet"
    )
    parquet_temp = _write_normalized_parquet(
        rows,
        staging_dir=tmp_path / "staging",
        final_path=normalized_path,
    )
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(parquet_temp, normalized_path)

    anomalies = _normalized_anomalies_for_month(
        month="2020-01",
        normalized_path=normalized_path,
        query_start_utc="2020-01-01T00:00:00Z",
        query_end_utc="2020-01-31T23:59:59.999999Z",
    )

    assert len(anomalies) == 1
    assert anomalies[0]["article_id"] == "9"
    assert anomalies[0]["updated_before_created"] is True
    assert anomalies[0]["pit_before_created"] is True
