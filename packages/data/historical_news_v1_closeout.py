from __future__ import annotations

import gzip
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable

import duckdb

from packages.core.atomic_io import replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.historical_news_v1 import _month_paths, month_windows
from packages.data.historical_news_v1_contract import (
    HISTORICAL_NEWS_V1_CONTRACT,
    HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
    HISTORY_END,
    HISTORY_START,
    PIT_TEXT_AVAILABLE_AT,
)


CLOSEOUT_CONTRACT: str = "atlas-historical-news-v1-source-integrity-closeout-v1"
EXPECTED_ACQUISITION_RUN_FINGERPRINT: str = (
    "8076044e7f7c233f98b990dc5595bc4171d1788c143c8391bf173f827ed12c2f"
)
EXPECTED_MONTHLY_PARTITIONS: int = 141
EXPECTED_RAW_PROVIDER_RECORDS: int = 2_211_606
EXPECTED_NORMALIZED_ARTICLES: int = 2_211_606

NORMALIZED_COLUMNS: tuple[str, ...] = (
    "article_id",
    "provider",
    "source",
    "author",
    "headline",
    "summary",
    "content",
    "url",
    "created_at",
    "updated_at",
    "pit_available_at",
    "symbols_json",
    "images_json",
    "provider_record_sha256",
    "pit_text_policy",
)


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_timestamp(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp is not timezone-aware")
    return parsed


def _rfc3339(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sql_literal(value: str | Path) -> str:
    return str(value).replace("'", "''")


def _parquet_source(paths: list[Path]) -> str:
    values = ",".join(f"'{_sql_literal(path)}'" for path in paths)
    return f"read_parquet([{values}])"


def _atomic_write_json(path: Path, payload: object) -> None:
    raw = (json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n").encode(
        "utf-8"
    )
    temp = unique_temp_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with temp.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def historical_news_v1_closeout_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": CLOSEOUT_CONTRACT,
        "acquisition_contract": HISTORICAL_NEWS_V1_CONTRACT,
        "acquisition_contract_fingerprint": HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
        "expected_acquisition_run_fingerprint": EXPECTED_ACQUISITION_RUN_FINGERPRINT,
        "history_start": HISTORY_START.isoformat(),
        "history_end": HISTORY_END.isoformat(),
        "expected_monthly_partitions": EXPECTED_MONTHLY_PARTITIONS,
        "expected_raw_provider_records": EXPECTED_RAW_PROVIDER_RECORDS,
        "expected_normalized_articles": EXPECTED_NORMALIZED_ARTICLES,
        "required_checks": [
            "SUMMARY_FINGERPRINT_AND_OBSERVED_COMPLETION_MATCH",
            "ALL_MONTH_RECEIPTS_COMPLETE_AND_FINGERPRINT_VALID",
            "RAW_AND_NORMALIZED_SHA256_MATCH_RECEIPTS",
            "RAW_JSONL_PARSE_AND_RECEIPT_COUNTS_RECONCILE",
            "NORMALIZED_SCHEMA_AND_RECEIPT_COUNTS_RECONCILE",
            "NORMALIZED_ROWS_BIND_TO_SELECTED_RAW_PROVIDER_RECORD_HASH",
            "PIT_AVAILABLE_AT_EQUALS_UPDATED_AT_AND_IS_NON_NULL",
            "UPDATED_AT_NOT_BEFORE_CREATED_AT",
            "SYMBOLS_AND_IMAGES_JSON_ARE_ARRAYS",
            "ARTICLE_IDS_UNIQUE_WITHIN_AND_ACROSS_MONTHS",
            "GLOBAL_TOTALS_RECONCILE_TO_ACQUISITION_SUMMARY",
        ],
        "provider_scope_policy": (
            "DO_NOT_INFER_UNDOCUMENTED_CREATED_AT_OR_UPDATED_AT_PARTITION_SEMANTICS"
        ),
        "authority": {
            "source_integrity_closeout_only": True,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    payload["fingerprint"] = _canonical_hash(payload)
    return payload


HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT: str = str(
    historical_news_v1_closeout_manifest()["fingerprint"]
)


def _receipt_fingerprint_is_valid(receipt: dict[str, object]) -> bool:
    expected = receipt.get("receipt_fingerprint")
    if not isinstance(expected, str) or not expected:
        return False
    payload = dict(receipt)
    payload.pop("receipt_fingerprint", None)
    return _canonical_hash(payload) == expected


def _summary_fingerprint_is_valid(summary: dict[str, object]) -> bool:
    expected = summary.get("run_fingerprint")
    if not isinstance(expected, str) or not expected:
        return False
    payload = dict(summary)
    payload.pop("run_fingerprint", None)
    return _canonical_hash(payload) == expected


def _load_json_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return value


def _inspect_partition(
    *,
    month: str,
    query_start_utc: str,
    query_end_utc: str,
    raw_path: Path,
    normalized_path: Path,
    receipt: dict[str, object],
) -> dict[str, object]:
    errors: list[str] = []
    if receipt.get("status") != "COMPLETE":
        errors.append("receipt status is not COMPLETE")
    if receipt.get("contract") != HISTORICAL_NEWS_V1_CONTRACT:
        errors.append("receipt acquisition contract mismatch")
    if receipt.get("contract_fingerprint") != HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT:
        errors.append("receipt acquisition contract fingerprint mismatch")
    if receipt.get("month") != month:
        errors.append("receipt month mismatch")
    if receipt.get("provider") != "alpaca":
        errors.append("receipt provider mismatch")
    if receipt.get("query_start_utc") != query_start_utc:
        errors.append("receipt query_start_utc mismatch")
    if receipt.get("query_end_utc") != query_end_utc:
        errors.append("receipt query_end_utc mismatch")
    if receipt.get("pit_text_available_at") != PIT_TEXT_AVAILABLE_AT:
        errors.append("receipt PIT text policy mismatch")
    try:
        if int(receipt.get("page_count", 0)) < 1:
            errors.append("receipt page_count is not positive")
    except (TypeError, ValueError):
        errors.append("receipt page_count is invalid")
    if not _receipt_fingerprint_is_valid(receipt):
        errors.append("receipt fingerprint does not recompute")

    if not raw_path.is_file():
        errors.append("raw gzip JSONL is missing")
    if not normalized_path.is_file():
        errors.append("normalized parquet is missing")
    if errors:
        return {"month": month, "status": "FAIL", "errors": errors}

    raw_sha256 = _sha256_file(raw_path)
    normalized_sha256 = _sha256_file(normalized_path)
    if receipt.get("raw_sha256") != raw_sha256:
        errors.append("raw SHA-256 does not match receipt")
    if receipt.get("normalized_sha256") != normalized_sha256:
        errors.append("normalized SHA-256 does not match receipt")
    if int(receipt.get("raw_bytes", -1)) != int(raw_path.stat().st_size):
        errors.append("raw byte size does not match receipt")
    if int(receipt.get("normalized_bytes", -1)) != int(normalized_path.stat().st_size):
        errors.append("normalized byte size does not match receipt")

    raw_count = 0
    missing_id = 0
    missing_created_at = 0
    missing_updated_at = 0
    invalid_timestamp = 0
    chronology_violations = 0
    created_outside_query_window = 0
    updated_outside_query_window = 0
    selected: dict[str, tuple[tuple[str, str], str]] = {}
    query_start = _parse_timestamp(query_start_utc)
    query_end = _parse_timestamp(query_end_utc)

    try:
        with gzip.open(raw_path, "rt", encoding="utf-8", newline="") as handle:
            for line_number, line in enumerate(handle, start=1):
                text = line.rstrip("\n")
                if not text:
                    errors.append(f"raw line {line_number} is empty")
                    continue
                raw_count += 1
                try:
                    item = json.loads(text)
                except json.JSONDecodeError:
                    errors.append(f"raw line {line_number} is not valid JSON")
                    continue
                if not isinstance(item, dict):
                    errors.append(f"raw line {line_number} is not a JSON object")
                    continue

                article_id = str(item.get("id") or "").strip()
                if not article_id:
                    missing_id += 1
                    continue

                created_raw = item.get("created_at")
                updated_raw = item.get("updated_at")
                if created_raw in (None, ""):
                    missing_created_at += 1
                if updated_raw in (None, ""):
                    missing_updated_at += 1
                effective_updated_raw = updated_raw or created_raw

                try:
                    created_at = _parse_timestamp(created_raw)
                    effective_updated_at = _parse_timestamp(effective_updated_raw)
                except (TypeError, ValueError):
                    invalid_timestamp += 1
                    created_at = None
                    effective_updated_at = None

                if (
                    created_at is not None
                    and effective_updated_at is not None
                    and effective_updated_at < created_at
                ):
                    chronology_violations += 1
                if (
                    created_at is not None
                    and query_start is not None
                    and query_end is not None
                    and not (query_start <= created_at <= query_end)
                ):
                    created_outside_query_window += 1
                if (
                    effective_updated_at is not None
                    and query_start is not None
                    and query_end is not None
                    and not (query_start <= effective_updated_at <= query_end)
                ):
                    updated_outside_query_window += 1

                selection_key = (str(updated_raw or ""), text)
                provider_record_sha256 = hashlib.sha256(
                    text.encode("utf-8")
                ).hexdigest()
                current = selected.get(article_id)
                if current is None or selection_key > current[0]:
                    selected[article_id] = (
                        selection_key,
                        provider_record_sha256,
                    )
    except (OSError, EOFError) as exc:
        errors.append(f"raw gzip JSONL cannot be read: {exc}")

    raw_duplicates = max(0, raw_count - len(selected))
    if missing_id:
        errors.append(f"{missing_id} raw provider records are missing article id")
    if missing_created_at:
        errors.append(f"{missing_created_at} raw provider records are missing created_at")
    if missing_updated_at:
        errors.append(f"{missing_updated_at} raw provider records are missing updated_at")
    if invalid_timestamp:
        errors.append(f"{invalid_timestamp} raw provider records have invalid timestamps")
    if chronology_violations:
        errors.append(
            f"{chronology_violations} raw provider records have updated_at before created_at"
        )
    if raw_count != int(receipt.get("raw_provider_records", -1)):
        errors.append("raw provider-record count does not match receipt")
    if raw_duplicates != int(receipt.get("duplicate_provider_records", -1)):
        errors.append("raw duplicate-provider-record count does not match receipt")

    normalized_count = 0
    normalized_distinct_ids = 0
    invalid_symbol_json = 0
    invalid_image_json = 0
    normalized_binding_mismatch = 0
    normalized_pit_mismatch = 0
    normalized_provider_mismatch = 0
    normalized_policy_mismatch = 0
    normalized_missing_time = 0
    normalized_chronology_violations = 0
    normalized_hash_format_errors = 0

    try:
        con = duckdb.connect(database=":memory:")
        try:
            source = _parquet_source([normalized_path])
            schema = con.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
            schema_names = tuple(str(row[0]) for row in schema)
            if schema_names != NORMALIZED_COLUMNS:
                errors.append(
                    "normalized parquet schema mismatch: "
                    f"expected {NORMALIZED_COLUMNS}, observed {schema_names}"
                )

            rows = con.execute(
                f"""
                SELECT
                    article_id,
                    provider,
                    created_at,
                    updated_at,
                    pit_available_at,
                    symbols_json,
                    images_json,
                    provider_record_sha256,
                    pit_text_policy
                FROM {source}
                """
            ).fetchall()
        finally:
            con.close()

        normalized_count = len(rows)
        normalized_ids: set[str] = set()
        for (
            article_id_value,
            provider,
            created_at,
            updated_at,
            pit_available_at,
            symbols_json,
            images_json,
            provider_record_sha256,
            pit_text_policy,
        ) in rows:
            article_id = str(article_id_value or "").strip()
            if article_id:
                normalized_ids.add(article_id)
            expected_selection = selected.get(article_id)
            if expected_selection is None or expected_selection[1] != str(
                provider_record_sha256 or ""
            ):
                normalized_binding_mismatch += 1

            digest = str(provider_record_sha256 or "")
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                normalized_hash_format_errors += 1

            if provider != "alpaca":
                normalized_provider_mismatch += 1
            if pit_text_policy != PIT_TEXT_AVAILABLE_AT:
                normalized_policy_mismatch += 1
            if updated_at is None or pit_available_at is None:
                normalized_missing_time += 1
            elif updated_at != pit_available_at:
                normalized_pit_mismatch += 1
            if created_at is not None and updated_at is not None and updated_at < created_at:
                normalized_chronology_violations += 1

            try:
                symbols = json.loads(str(symbols_json))
                if not isinstance(symbols, list):
                    invalid_symbol_json += 1
            except (TypeError, json.JSONDecodeError):
                invalid_symbol_json += 1
            try:
                images = json.loads(str(images_json))
                if not isinstance(images, list):
                    invalid_image_json += 1
            except (TypeError, json.JSONDecodeError):
                invalid_image_json += 1

        normalized_distinct_ids = len(normalized_ids)
    except Exception as exc:
        errors.append(f"normalized parquet cannot be inspected: {exc}")

    if normalized_count != int(receipt.get("normalized_unique_articles", -1)):
        errors.append("normalized article count does not match receipt")
    if normalized_count != len(selected):
        errors.append(
            "normalized article count does not equal independently selected raw article ids"
        )
    if normalized_distinct_ids != normalized_count:
        errors.append("normalized article ids are not unique within the month")
    if normalized_binding_mismatch:
        errors.append(
            f"{normalized_binding_mismatch} normalized rows do not bind to the selected raw record"
        )
    if normalized_hash_format_errors:
        errors.append(
            f"{normalized_hash_format_errors} normalized provider hashes are not lowercase SHA-256"
        )
    if normalized_provider_mismatch:
        errors.append(
            f"{normalized_provider_mismatch} normalized rows have provider != alpaca"
        )
    if normalized_policy_mismatch:
        errors.append(
            f"{normalized_policy_mismatch} normalized rows have the wrong PIT text policy"
        )
    if normalized_missing_time:
        errors.append(
            f"{normalized_missing_time} normalized rows are missing updated_at/PIT time"
        )
    if normalized_pit_mismatch:
        errors.append(
            f"{normalized_pit_mismatch} normalized rows have pit_available_at != updated_at"
        )
    if normalized_chronology_violations:
        errors.append(
            f"{normalized_chronology_violations} normalized rows have updated_at before created_at"
        )
    if invalid_symbol_json:
        errors.append(f"{invalid_symbol_json} normalized symbols_json values are not arrays")
    if invalid_image_json:
        errors.append(f"{invalid_image_json} normalized images_json values are not arrays")

    return {
        "month": month,
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "raw_provider_records": raw_count,
        "normalized_articles": normalized_count,
        "raw_duplicate_provider_records": raw_duplicates,
        "raw_sha256": raw_sha256,
        "normalized_sha256": normalized_sha256,
        "receipt_fingerprint": receipt.get("receipt_fingerprint"),
        "missing_created_at": missing_created_at,
        "missing_updated_at": missing_updated_at,
        "created_outside_query_window": created_outside_query_window,
        "updated_outside_query_window": updated_outside_query_window,
        "chronology_violations": chronology_violations
        + normalized_chronology_violations,
    }


def _inspect_global_normalized(paths: list[Path]) -> dict[str, object]:
    if not paths:
        return {
            "row_count": 0,
            "distinct_article_ids": 0,
            "duplicate_article_id_rows": 0,
            "duplicate_article_id_samples": [],
        }
    con = duckdb.connect(database=":memory:")
    try:
        source = _parquet_source(paths)
        row_count, distinct_ids = con.execute(
            f"""
            SELECT count(*), count(DISTINCT article_id)
            FROM {source}
            """
        ).fetchone()
        duplicate_rows = int(row_count) - int(distinct_ids)
        samples: list[dict[str, object]] = []
        if duplicate_rows:
            for article_id, count_rows in con.execute(
                f"""
                SELECT article_id, count(*) AS n
                FROM {source}
                GROUP BY article_id
                HAVING count(*) > 1
                ORDER BY n DESC, article_id
                LIMIT 25
                """
            ).fetchall():
                samples.append(
                    {"article_id": str(article_id), "rows": int(count_rows)}
                )
        return {
            "row_count": int(row_count),
            "distinct_article_ids": int(distinct_ids),
            "duplicate_article_id_rows": duplicate_rows,
            "duplicate_article_id_samples": samples,
        }
    finally:
        con.close()


def _stable_corpus_fingerprint(
    partition_reports: list[dict[str, object]],
) -> str:
    components = [
        {
            "month": report["month"],
            "raw_provider_records": report.get("raw_provider_records"),
            "normalized_articles": report.get("normalized_articles"),
            "raw_sha256": report.get("raw_sha256"),
            "normalized_sha256": report.get("normalized_sha256"),
        }
        for report in sorted(partition_reports, key=lambda item: str(item["month"]))
    ]
    return _canonical_hash(
        {
            "acquisition_contract_fingerprint": HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
            "partitions": components,
        }
    )


def run_historical_news_v1_closeout(
    settings: AtlasSettings,
    *,
    workers: int = 4,
    expected_run_fingerprint: str = EXPECTED_ACQUISITION_RUN_FINGERPRINT,
    output_path: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if workers < 1:
        raise ValueError("workers must be at least 1")

    errors: list[str] = []
    summary_path = settings.resolved_path(
        "data/news/manifests/alpaca/historical_news_v1_summary.json"
    )
    if not summary_path.is_file():
        summary: dict[str, object] = {}
        errors.append("Historical News V1 acquisition summary is missing")
    else:
        try:
            summary = _load_json_object(summary_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            summary = {}
            errors.append(f"Historical News V1 acquisition summary is unreadable: {exc}")

    if summary:
        if not _summary_fingerprint_is_valid(summary):
            errors.append("acquisition summary run fingerprint does not recompute")
        if summary.get("run_fingerprint") != expected_run_fingerprint:
            errors.append(
                "acquisition summary run fingerprint does not match the observed completed run"
            )
        if summary.get("status") != "COMPLETE":
            errors.append("acquisition summary status is not COMPLETE")
        if summary.get("contract") != HISTORICAL_NEWS_V1_CONTRACT:
            errors.append("acquisition summary contract mismatch")
        if summary.get("contract_fingerprint") != HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT:
            errors.append("acquisition summary contract fingerprint mismatch")
        if summary.get("history_start") != HISTORY_START.isoformat():
            errors.append("acquisition summary history_start mismatch")
        if summary.get("history_end") != HISTORY_END.isoformat():
            errors.append("acquisition summary history_end mismatch")
        if int(summary.get("monthly_partitions", -1)) != EXPECTED_MONTHLY_PARTITIONS:
            errors.append("acquisition summary monthly partition count mismatch")
        if int(summary.get("raw_provider_records", -1)) != EXPECTED_RAW_PROVIDER_RECORDS:
            errors.append("acquisition summary raw provider-record count mismatch")
        if int(summary.get("normalized_unique_articles", -1)) != EXPECTED_NORMALIZED_ARTICLES:
            errors.append("acquisition summary normalized article count mismatch")
        authority = summary.get("authority")
        if not isinstance(authority, dict):
            errors.append("acquisition summary authority block is missing")
        else:
            if authority.get("source_acquisition_only") is not True:
                errors.append("acquisition summary lost source-only authority")
            for key in (
                "predictor_generation",
                "strategy_outcome_access",
                "paper_authority",
                "live_authority",
            ):
                if authority.get(key) is not False:
                    errors.append(f"acquisition summary authority {key} is not false")

    windows = month_windows()
    if len(windows) != EXPECTED_MONTHLY_PARTITIONS:
        errors.append("frozen month-window count no longer matches closeout contract")

    jobs: list[tuple[object, dict[str, Path], dict[str, object]]] = []
    for window in windows:
        paths = _month_paths(settings, window)
        try:
            receipt = _load_json_object(paths["receipt"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            receipt = {}
            errors.append(f"{window.key}: receipt is unreadable or missing: {exc}")
        jobs.append((window, paths, receipt))

    partition_reports: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _inspect_partition,
                month=window.key,
                query_start_utc=_rfc3339(window.start_utc),
                query_end_utc=_rfc3339(window.end_utc),
                raw_path=paths["raw"],
                normalized_path=paths["normalized"],
                receipt=receipt,
            ): window.key
            for window, paths, receipt in jobs
        }
        completed = 0
        for future in as_completed(futures):
            month = futures[future]
            try:
                report = future.result()
            except Exception as exc:
                report = {
                    "month": month,
                    "status": "FAIL",
                    "errors": [f"unhandled closeout inspection error: {exc}"],
                }
            partition_reports.append(report)
            completed += 1
            if progress is not None and (
                completed == len(futures)
                or completed % 10 == 0
                or report["status"] != "PASS"
            ):
                progress(
                    f"{completed}/{len(futures)} partitions inspected; "
                    f"latest={month} status={report['status']}"
                )

    partition_reports.sort(key=lambda item: str(item["month"]))
    failed_partitions = [
        str(report["month"])
        for report in partition_reports
        if report["status"] != "PASS"
    ]
    if failed_partitions:
        errors.append(
            f"{len(failed_partitions)} monthly partitions failed integrity checks"
        )

    receipt_fingerprints = [
        report.get("receipt_fingerprint")
        for report in partition_reports
    ]
    if summary and summary.get("month_receipt_fingerprints") != receipt_fingerprints:
        errors.append(
            "ordered monthly receipt fingerprints do not match the acquisition summary"
        )

    normalized_paths = [
        paths["normalized"]
        for _window, paths, _receipt in jobs
        if paths["normalized"].is_file()
    ]
    try:
        global_normalized = _inspect_global_normalized(normalized_paths)
    except Exception as exc:
        global_normalized = {
            "row_count": 0,
            "distinct_article_ids": 0,
            "duplicate_article_id_rows": 0,
            "duplicate_article_id_samples": [],
        }
        errors.append(f"global normalized corpus cannot be inspected: {exc}")

    raw_total = sum(int(report.get("raw_provider_records", 0)) for report in partition_reports)
    normalized_total = sum(int(report.get("normalized_articles", 0)) for report in partition_reports)
    if raw_total != EXPECTED_RAW_PROVIDER_RECORDS:
        errors.append("independently scanned raw total does not match accepted completion count")
    if normalized_total != EXPECTED_NORMALIZED_ARTICLES:
        errors.append(
            "independently scanned normalized total does not match accepted completion count"
        )
    if int(global_normalized["row_count"]) != EXPECTED_NORMALIZED_ARTICLES:
        errors.append("global parquet row count does not match accepted completion count")
    if int(global_normalized["duplicate_article_id_rows"]) != 0:
        errors.append("article ids are duplicated across monthly normalized partitions")

    corpus_fingerprint = _stable_corpus_fingerprint(partition_reports)
    report: dict[str, object] = {
        "status": "PASS" if not errors else "FAIL",
        "contract": CLOSEOUT_CONTRACT,
        "contract_fingerprint": HISTORICAL_NEWS_V1_CLOSEOUT_CONTRACT_FINGERPRINT,
        "acquisition_contract": HISTORICAL_NEWS_V1_CONTRACT,
        "acquisition_contract_fingerprint": HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
        "acquisition_run_fingerprint": summary.get("run_fingerprint"),
        "expected_acquisition_run_fingerprint": expected_run_fingerprint,
        "history_start": HISTORY_START.isoformat(),
        "history_end": HISTORY_END.isoformat(),
        "monthly_partitions": len(partition_reports),
        "failed_partitions": failed_partitions,
        "raw_provider_records": raw_total,
        "normalized_articles": normalized_total,
        "global_normalized": global_normalized,
        "corpus_fingerprint": corpus_fingerprint,
        "errors": errors,
        "partition_reports": partition_reports,
        "authority": {
            "source_integrity_closeout_only": True,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    report["closeout_fingerprint"] = _canonical_hash(report)

    final_output = output_path or settings.resolved_path(
        "data/news/manifests/alpaca/historical_news_v1_closeout.json"
    )
    _atomic_write_json(final_output, report)
    return report
