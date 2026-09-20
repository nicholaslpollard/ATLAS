from __future__ import annotations

import gzip
import os
from pathlib import Path

from packages.data.historical_news_v1 import (
    _normalized_rows,
    _stable_json,
    _write_normalized_parquet,
)
from packages.data.historical_news_v1_closeout import (
    EXPECTED_ACQUISITION_RUN_FINGERPRINT,
    EXPECTED_MONTHLY_PARTITIONS,
    EXPECTED_NORMALIZED_ARTICLES,
    EXPECTED_RAW_PROVIDER_RECORDS,
    HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT,
    _canonical_hash,
    _inspect_global_normalized,
    _inspect_partition,
    _sha256_file,
    _stable_corpus_fingerprint,
    historical_news_v1_closeout_manifest,
)
from packages.data.historical_news_v1_contract import (
    HISTORICAL_NEWS_V1_CONTRACT,
    HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
)


def _record(article_id: int, *, headline: str = "Headline") -> dict[str, object]:
    return {
        "id": article_id,
        "headline": headline,
        "summary": "Summary",
        "content": "Body",
        "author": "Author",
        "created_at": "2020-01-02T14:00:00Z",
        "updated_at": "2020-01-02T14:05:00Z",
        "symbols": ["ABC"],
        "images": [],
        "url": "https://example.test/article",
        "source": "benzinga",
    }


def _write_fixture(
    tmp_path: Path,
    *,
    month: str,
    records: list[dict[str, object]],
    normalized_rows: list[dict[str, object]] | None = None,
    hive_layout: bool = False,
) -> tuple[Path, Path, dict[str, object]]:
    year, month_number = month.split("-", maxsplit=1)
    root = (
        tmp_path / f"year={year}" / f"month={month_number}"
        if hive_layout
        else tmp_path / month
    )
    raw_path = root / "articles.jsonl.gz"
    normalized_path = root / "articles.parquet"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    raw_lines = b"".join(
        (_stable_json(item) + "\n").encode("utf-8")
        for item in records
    )
    raw_path.write_bytes(gzip.compress(raw_lines, compresslevel=6, mtime=0))

    rows = normalized_rows if normalized_rows is not None else _normalized_rows(records)
    parquet_temp = _write_normalized_parquet(
        rows,
        staging_dir=tmp_path / month / "staging",
        final_path=normalized_path,
    )
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(parquet_temp, normalized_path)

    receipt: dict[str, object] = {
        "status": "COMPLETE",
        "contract": HISTORICAL_NEWS_V1_CONTRACT,
        "contract_fingerprint": HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
        "provider": "alpaca",
        "month": month,
        "query_start_utc": "2020-01-01T00:00:00Z",
        "query_end_utc": "2020-01-31T23:59:59.999999Z",
        "page_count": 1,
        "raw_provider_records": len(records),
        "normalized_unique_articles": len(rows),
        "duplicate_provider_records": len(records)
        - len({str(item["id"]) for item in records}),
        "pit_text_available_at": "UPDATED_AT",
        "raw_path": str(raw_path.resolve()),
        "normalized_path": str(normalized_path.resolve()),
        "raw_bytes": raw_path.stat().st_size,
        "normalized_bytes": normalized_path.stat().st_size,
        "raw_sha256": _sha256_file(raw_path),
        "normalized_sha256": _sha256_file(normalized_path),
    }
    receipt["receipt_fingerprint"] = _canonical_hash(receipt)
    return raw_path, normalized_path, receipt


def test_closeout_contract_binds_exact_completed_acquisition_and_stays_source_only() -> None:
    manifest = historical_news_v1_closeout_manifest()
    assert (
        manifest["fingerprint"]
        == HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT
        == "99b3b76cadbfff7a7975ce1c9c5b4f2103b2d9e8ec77acae46bba51f80fa8df0"
    )
    assert (
        manifest["expected_acquisition_run_fingerprint"]
        == EXPECTED_ACQUISITION_RUN_FINGERPRINT
    )
    assert manifest["expected_monthly_partitions"] == EXPECTED_MONTHLY_PARTITIONS == 141
    assert (
        manifest["expected_raw_provider_records"]
        == EXPECTED_RAW_PROVIDER_RECORDS
        == 2_211_606
    )
    assert (
        manifest["expected_normalized_articles"]
        == EXPECTED_NORMALIZED_ARTICLES
        == 2_211_606
    )
    authority = manifest["authority"]
    assert isinstance(authority, dict)
    assert authority["source_integrity_closeout_only"] is True
    assert authority["predictor_generation"] is False
    assert authority["paper_authority"] is False
    assert authority["live_authority"] is False


def test_partition_inspection_reconstructs_normalized_selection_from_raw(
    tmp_path: Path,
) -> None:
    records = [_record(1)]
    raw_path, normalized_path, receipt = _write_fixture(
        tmp_path,
        month="2020-01",
        records=records,
    )

    report = _inspect_partition(
        month="2020-01",
        query_start_utc="2020-01-01T00:00:00Z",
        query_end_utc="2020-01-31T23:59:59.999999Z",
        raw_path=raw_path,
        normalized_path=normalized_path,
        receipt=receipt,
    )

    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["raw_provider_records"] == 1
    assert report["normalized_articles"] == 1
    assert report["created_outside_query_window"] == 0
    assert report["updated_outside_query_window"] == 0


def test_partition_inspection_fails_if_normalized_row_is_not_bound_to_selected_raw(
    tmp_path: Path,
) -> None:
    records = [_record(1)]
    rows = _normalized_rows(records)
    rows[0] = dict(rows[0])
    rows[0]["provider_record_sha256"] = "0" * 64
    raw_path, normalized_path, receipt = _write_fixture(
        tmp_path,
        month="2020-01",
        records=records,
        normalized_rows=rows,
    )

    report = _inspect_partition(
        month="2020-01",
        query_start_utc="2020-01-01T00:00:00Z",
        query_end_utc="2020-01-31T23:59:59.999999Z",
        raw_path=raw_path,
        normalized_path=normalized_path,
        receipt=receipt,
    )

    assert report["status"] == "FAIL"
    assert any(
        "do not bind to the selected raw record" in error
        for error in report["errors"]
    )



def test_partition_inspection_ignores_hive_directory_columns(
    tmp_path: Path,
) -> None:
    raw_path, normalized_path, receipt = _write_fixture(
        tmp_path,
        month="2020-01",
        records=[_record(1)],
        hive_layout=True,
    )

    report = _inspect_partition(
        month="2020-01",
        query_start_utc="2020-01-01T00:00:00Z",
        query_end_utc="2020-01-31T23:59:59.999999Z",
        raw_path=raw_path,
        normalized_path=normalized_path,
        receipt=receipt,
    )

    assert report["status"] == "PASS"
    assert report["errors"] == []

def test_global_inspection_detects_cross_partition_article_id_duplicates(
    tmp_path: Path,
) -> None:
    first_raw, first_parquet, _first_receipt = _write_fixture(
        tmp_path,
        month="2020-01",
        records=[_record(7, headline="First")],
    )
    second_raw, second_parquet, _second_receipt = _write_fixture(
        tmp_path,
        month="2020-02",
        records=[_record(7, headline="Second")],
    )
    assert first_raw.is_file()
    assert second_raw.is_file()

    report = _inspect_global_normalized([first_parquet, second_parquet])

    assert report["row_count"] == 2
    assert report["distinct_article_ids"] == 1
    assert report["duplicate_article_id_rows"] == 1
    assert report["duplicate_article_id_samples"] == [
        {"article_id": "7", "rows": 2}
    ]


def test_corpus_fingerprint_ignores_machine_specific_receipt_metadata() -> None:
    base = {
        "month": "2020-01",
        "raw_provider_records": 10,
        "normalized_articles": 10,
        "raw_sha256": "1" * 64,
        "normalized_sha256": "2" * 64,
    }
    left = dict(base, receipt_fingerprint="a" * 64, raw_path="C:/one")
    right = dict(base, receipt_fingerprint="b" * 64, raw_path="D:/two")

    assert _stable_corpus_fingerprint([left]) == _stable_corpus_fingerprint([right])
