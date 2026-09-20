from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Iterable

import duckdb

from packages.core.atomic_io import replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.data.historical_news_v1_contract import (
    HISTORICAL_NEWS_V1_CONTRACT,
    HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
    HISTORY_END,
    HISTORY_START,
    INCLUDE_CONTENT,
    NEWS_STORAGE_CATEGORY,
    PAGE_LIMIT,
    PIT_TEXT_AVAILABLE_AT,
    SORT_ORDER,
)
from packages.data.research_storage import (
    assert_category_acquisition_allowed,
    inspect_research_storage,
)


class HistoricalNewsV1Error(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MonthWindow:
    key: str
    start_utc: datetime
    end_utc: datetime
    year: int
    month: int


class _RateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self._interval = 60.0 / max(1, requests_per_minute)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_allowed - now)
            self._next_allowed = max(now, self._next_allowed) + self._interval
        if delay:
            time.sleep(delay)


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _canonical_hash(value: object) -> str:
    return _sha256_bytes(_stable_json(value).encode("utf-8"))


def _resolve_alpaca_credentials(
    settings: AtlasSettings,
) -> tuple[str, str, str]:
    cfg = settings.alpaca.credentials
    for profile in (cfg.preferred_profile, "paper", "live"):
        if profile == "paper":
            key_env = cfg.paper_api_key_env
            secret_env = cfg.paper_api_secret_env
        elif profile == "live":
            key_env = cfg.live_api_key_env
            secret_env = cfg.live_api_secret_env
        else:
            continue
        key = os.getenv(key_env, "").strip()
        secret = os.getenv(secret_env, "").strip()
        if key and secret:
            return profile, key, secret
    raise HistoricalNewsV1Error(
        "Alpaca market-data credentials are not configured in the expected environment variables"
    )


def _next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def month_windows(
    start: date = HISTORY_START,
    end: date = HISTORY_END,
) -> tuple[MonthWindow, ...]:
    if end < start:
        raise ValueError("end date must not precede start date")
    cursor = date(start.year, start.month, 1)
    windows: list[MonthWindow] = []
    while cursor <= end:
        following = _next_month(cursor)
        bounded_start = max(start, cursor)
        bounded_end = min(end, following - timedelta(days=1))
        start_utc = datetime.combine(bounded_start, dt_time.min, tzinfo=UTC)
        end_utc = datetime.combine(
            bounded_end,
            dt_time.max,
            tzinfo=UTC,
        )
        windows.append(
            MonthWindow(
                key=f"{cursor.year:04d}-{cursor.month:02d}",
                start_utc=start_utc,
                end_utc=end_utc,
                year=cursor.year,
                month=cursor.month,
            )
        )
        cursor = following
    return tuple(windows)


def _rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _request_json(
    *,
    url: str,
    key: str,
    secret: str,
    timeout_seconds: float,
    max_attempts: int,
    initial_retry_seconds: float,
    max_retry_seconds: float,
    limiter: _RateLimiter,
) -> dict[str, Any]:
    delay = max(0.0, initial_retry_seconds)
    for attempt in range(1, max_attempts + 1):
        limiter.wait()
        request = urllib.request.Request(
            url,
            headers={
                "APCA-API-KEY-ID": key,
                "APCA-API-SECRET-KEY": secret,
                "Accept": "application/json",
                "User-Agent": "ATLAS-historical-news-v1/1",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise HistoricalNewsV1Error("Alpaca news response root is not an object")
            return payload
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt >= max_attempts:
                body = exc.read().decode("utf-8", errors="replace")[:500]
                raise HistoricalNewsV1Error(
                    f"Alpaca news request failed HTTP {exc.code}: {body}"
                ) from exc
            retry_after = exc.headers.get("Retry-After")
            try:
                wait_seconds = float(retry_after) if retry_after else delay
            except ValueError:
                wait_seconds = delay
            time.sleep(max(0.0, wait_seconds))
            delay = min(max_retry_seconds, max(delay * 2.0, initial_retry_seconds))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt >= max_attempts:
                raise HistoricalNewsV1Error(
                    f"Alpaca news request failed after {attempt} attempts: {exc}"
                ) from exc
            time.sleep(delay)
            delay = min(max_retry_seconds, max(delay * 2.0, initial_retry_seconds))
    raise AssertionError("unreachable")


def _fetch_month(
    settings: AtlasSettings,
    window: MonthWindow,
    *,
    key: str,
    secret: str,
    limiter: _RateLimiter,
) -> dict[str, object]:
    market = settings.alpaca.market_data
    endpoint = (
        market.base_url.rstrip("/")
        + settings.data.research.news.endpoint_path
    )
    records: list[dict[str, Any]] = []
    page_token: str | None = None
    page_count = 0
    while True:
        query: dict[str, object] = {
            "start": _rfc3339(window.start_utc),
            "end": _rfc3339(window.end_utc),
            "sort": SORT_ORDER,
            "limit": PAGE_LIMIT,
            "include_content": "true" if INCLUDE_CONTENT else "false",
        }
        if page_token:
            query["page_token"] = page_token
        url = endpoint + "?" + urllib.parse.urlencode(query)
        payload = _request_json(
            url=url,
            key=key,
            secret=secret,
            timeout_seconds=market.request_timeout_seconds,
            max_attempts=market.max_attempts,
            initial_retry_seconds=market.initial_retry_seconds,
            max_retry_seconds=market.max_retry_seconds,
            limiter=limiter,
        )
        news = payload.get("news")
        if not isinstance(news, list):
            raise HistoricalNewsV1Error(
                f"{window.key}: Alpaca response is missing news[]"
            )
        for item in news:
            if not isinstance(item, dict):
                raise HistoricalNewsV1Error(
                    f"{window.key}: Alpaca news item is not an object"
                )
            records.append(item)
        page_count += 1
        token = payload.get("next_page_token")
        if token in (None, ""):
            break
        page_token = str(token)

    records.sort(
        key=lambda item: (
            str(item.get("updated_at") or ""),
            str(item.get("id") or ""),
            _stable_json(item),
        )
    )
    return {
        "window": window,
        "records": records,
        "page_count": page_count,
    }


def _normalized_rows(records: Iterable[dict[str, Any]]) -> list[dict[str, object]]:
    chosen: dict[str, dict[str, Any]] = {}
    for item in records:
        article_id = str(item.get("id") or "").strip()
        if not article_id:
            raise HistoricalNewsV1Error("provider article is missing id")
        existing = chosen.get(article_id)
        if existing is None:
            chosen[article_id] = item
            continue
        current_key = (
            str(item.get("updated_at") or ""),
            _stable_json(item),
        )
        existing_key = (
            str(existing.get("updated_at") or ""),
            _stable_json(existing),
        )
        if current_key > existing_key:
            chosen[article_id] = item

    rows: list[dict[str, object]] = []
    for article_id, item in chosen.items():
        created_at = item.get("created_at")
        updated_at = item.get("updated_at") or created_at
        if not updated_at:
            raise HistoricalNewsV1Error(
                f"article {article_id} has neither updated_at nor created_at"
            )
        rows.append(
            {
                "article_id": article_id,
                "provider": "alpaca",
                "source": str(item.get("source") or ""),
                "author": str(item.get("author") or ""),
                "headline": str(item.get("headline") or ""),
                "summary": str(item.get("summary") or ""),
                "content": str(item.get("content") or ""),
                "url": str(item.get("url") or ""),
                "created_at": None if created_at is None else str(created_at),
                "updated_at": str(updated_at),
                "pit_available_at": str(updated_at),
                "symbols_json": _stable_json(item.get("symbols") or []),
                "images_json": _stable_json(item.get("images") or []),
                "provider_record_sha256": _canonical_hash(item),
                "pit_text_policy": PIT_TEXT_AVAILABLE_AT,
            }
        )
    rows.sort(
        key=lambda row: (
            str(row["pit_available_at"]),
            str(row["article_id"]),
        )
    )
    return rows


def _sql_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def _write_normalized_parquet(
    rows: list[dict[str, object]],
    *,
    staging_dir: Path,
    final_path: Path,
) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = staging_dir / (final_path.stem + ".normalized.jsonl")
    parquet_path = staging_dir / (final_path.name + ".tmp.parquet")
    try:
        with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(_stable_json(row))
                handle.write("\n")

        con = duckdb.connect(database=":memory:")
        try:
            if rows:
                con.execute(
                    f"""
                    COPY (
                        SELECT
                            CAST(article_id AS VARCHAR) AS article_id,
                            CAST(provider AS VARCHAR) AS provider,
                            CAST(source AS VARCHAR) AS source,
                            CAST(author AS VARCHAR) AS author,
                            CAST(headline AS VARCHAR) AS headline,
                            CAST(summary AS VARCHAR) AS summary,
                            CAST(content AS VARCHAR) AS content,
                            CAST(url AS VARCHAR) AS url,
                            TRY_CAST(created_at AS TIMESTAMPTZ) AS created_at,
                            TRY_CAST(updated_at AS TIMESTAMPTZ) AS updated_at,
                            TRY_CAST(pit_available_at AS TIMESTAMPTZ) AS pit_available_at,
                            CAST(symbols_json AS VARCHAR) AS symbols_json,
                            CAST(images_json AS VARCHAR) AS images_json,
                            CAST(provider_record_sha256 AS VARCHAR) AS provider_record_sha256,
                            CAST(pit_text_policy AS VARCHAR) AS pit_text_policy
                        FROM read_json_auto('{_sql_literal(jsonl_path)}', format='newline_delimited')
                        ORDER BY pit_available_at, article_id
                    )
                    TO '{_sql_literal(parquet_path)}'
                    (FORMAT PARQUET, COMPRESSION ZSTD)
                    """
                )
            else:
                con.execute(
                    """
                    CREATE TABLE empty_news (
                        article_id VARCHAR,
                        provider VARCHAR,
                        source VARCHAR,
                        author VARCHAR,
                        headline VARCHAR,
                        summary VARCHAR,
                        content VARCHAR,
                        url VARCHAR,
                        created_at TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ,
                        pit_available_at TIMESTAMPTZ,
                        symbols_json VARCHAR,
                        images_json VARCHAR,
                        provider_record_sha256 VARCHAR,
                        pit_text_policy VARCHAR
                    )
                    """
                )
                con.execute(
                    f"""
                    COPY (
                        SELECT * FROM empty_news
                    )
                    TO '{_sql_literal(parquet_path)}'
                    (FORMAT PARQUET, COMPRESSION ZSTD)
                    """
                )
        finally:
            con.close()
        return parquet_path
    finally:
        jsonl_path.unlink(missing_ok=True)


def _atomic_write_bytes(final_path: Path, raw: bytes) -> None:
    temp_path = unique_temp_path(final_path)
    try:
        with temp_path.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temp_path, final_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _atomic_write_json(final_path: Path, payload: object) -> None:
    raw = (json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n").encode(
        "utf-8"
    )
    _atomic_write_bytes(final_path, raw)


def _month_paths(settings: AtlasSettings, window: MonthWindow) -> dict[str, Path]:
    root = settings.resolved_path("data")
    news = settings.data.research.news
    suffix = Path(f"alpaca/year={window.year:04d}/month={window.month:02d}")
    return {
        "raw": root / news.raw_subdir / suffix / "articles.jsonl.gz",
        "normalized": root / news.normalized_subdir / suffix / "articles.parquet",
        "receipt": root / news.manifests_subdir / suffix / "receipt.json",
    }


def _verified_existing_receipt(
    settings: AtlasSettings,
    window: MonthWindow,
) -> dict[str, object] | None:
    paths = _month_paths(settings, window)
    receipt_path = paths["receipt"]
    if not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if receipt.get("status") != "COMPLETE":
        return None
    if (
        receipt.get("contract_fingerprint")
        != HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT
    ):
        return None
    if receipt.get("month") != window.key:
        return None
    for key in ("raw", "normalized"):
        path = paths[key]
        if not path.is_file():
            return None
        expected = receipt.get(f"{key}_sha256")
        if expected != _sha256_file(path):
            return None
    return receipt


def _persist_month(
    settings: AtlasSettings,
    payload: dict[str, object],
) -> dict[str, object]:
    window = payload["window"]
    if not isinstance(window, MonthWindow):
        raise HistoricalNewsV1Error("month payload has invalid window")
    records = payload["records"]
    if not isinstance(records, list):
        raise HistoricalNewsV1Error("month payload has invalid records")
    page_count = int(payload["page_count"])
    paths = _month_paths(settings, window)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    raw_lines = b"".join(
        (_stable_json(item) + "\n").encode("utf-8")
        for item in records
    )
    raw_gzip = gzip.compress(raw_lines, compresslevel=6, mtime=0)
    normalized_rows = _normalized_rows(records)

    staging = settings.resolved_path(
        Path("data/staging/historical_news_v1")
        / f"{window.year:04d}"
        / f"{window.month:02d}"
    )
    parquet_temp = _write_normalized_parquet(
        normalized_rows,
        staging_dir=staging,
        final_path=paths["normalized"],
    )
    try:
        final_bytes = len(raw_gzip) + int(parquet_temp.stat().st_size)
        existing_bytes = sum(
            int(paths[name].stat().st_size)
            for name in ("raw", "normalized")
            if paths[name].is_file()
        )
        projected_additional = max(0, final_bytes - existing_bytes)
        assert_category_acquisition_allowed(
            settings,
            category=NEWS_STORAGE_CATEGORY,
            projected_additional_bytes=projected_additional,
        )
        _atomic_write_bytes(paths["raw"], raw_gzip)
        replace_with_retry(parquet_temp, paths["normalized"])

        created_values = [
            str(item.get("created_at"))
            for item in records
            if item.get("created_at")
        ]
        updated_values = [
            str(item.get("updated_at"))
            for item in records
            if item.get("updated_at")
        ]
        receipt: dict[str, object] = {
            "status": "COMPLETE",
            "contract": HISTORICAL_NEWS_V1_CONTRACT,
            "contract_fingerprint": HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
            "provider": "alpaca",
            "month": window.key,
            "query_start_utc": _rfc3339(window.start_utc),
            "query_end_utc": _rfc3339(window.end_utc),
            "page_count": page_count,
            "raw_provider_records": len(records),
            "normalized_unique_articles": len(normalized_rows),
            "duplicate_provider_records": len(records) - len(normalized_rows),
            "min_created_at": min(created_values) if created_values else None,
            "max_created_at": max(created_values) if created_values else None,
            "min_updated_at": min(updated_values) if updated_values else None,
            "max_updated_at": max(updated_values) if updated_values else None,
            "pit_text_available_at": PIT_TEXT_AVAILABLE_AT,
            "raw_path": str(paths["raw"].resolve()),
            "normalized_path": str(paths["normalized"].resolve()),
            "raw_bytes": int(paths["raw"].stat().st_size),
            "normalized_bytes": int(paths["normalized"].stat().st_size),
            "raw_sha256": _sha256_file(paths["raw"]),
            "normalized_sha256": _sha256_file(paths["normalized"]),
        }
        receipt["receipt_fingerprint"] = _canonical_hash(receipt)
        _atomic_write_json(paths["receipt"], receipt)
        return receipt
    finally:
        parquet_temp.unlink(missing_ok=True)


def run_historical_news_v1_acquisition(
    settings: AtlasSettings,
    *,
    workers: int = 4,
) -> dict[str, object]:
    if workers < 1:
        raise ValueError("workers must be at least 1")
    profile, key, secret = _resolve_alpaca_credentials(settings)
    limiter = _RateLimiter(settings.alpaca.market_data.requests_per_minute)
    windows = month_windows()

    reused: list[dict[str, object]] = []
    pending: list[MonthWindow] = []
    for window in windows:
        receipt = _verified_existing_receipt(settings, window)
        if receipt is None:
            pending.append(window)
        else:
            reused.append(receipt)

    print(
        "historical news v1: "
        f"{len(windows)} monthly partitions / {len(reused)} verified reusable / "
        f"{len(pending)} pending / workers={workers}",
        flush=True,
    )

    completed: list[dict[str, object]] = list(reused)
    if pending:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _fetch_month,
                    settings,
                    window,
                    key=key,
                    secret=secret,
                    limiter=limiter,
                ): window
                for window in pending
            }
            done = 0
            for future in as_completed(futures):
                window = futures[future]
                payload = future.result()
                receipt = _persist_month(settings, payload)
                completed.append(receipt)
                done += 1
                storage = inspect_research_storage(settings)
                print(
                    f"  {done}/{len(pending)} acquired {window.key}: "
                    f"{int(receipt['normalized_unique_articles']):,} articles / "
                    f"{int(receipt['page_count']):,} pages / "
                    f"news={storage.category_usage_gib.get('news', 0.0):.3f} GiB / "
                    f"free={storage.disk_free_gib:.2f} GiB",
                    flush=True,
                )

    completed.sort(key=lambda item: str(item["month"]))
    total_articles = sum(int(item["normalized_unique_articles"]) for item in completed)
    total_raw_records = sum(int(item["raw_provider_records"]) for item in completed)
    total_raw_bytes = sum(int(item["raw_bytes"]) for item in completed)
    total_normalized_bytes = sum(int(item["normalized_bytes"]) for item in completed)
    storage = inspect_research_storage(settings)

    summary: dict[str, object] = {
        "status": "COMPLETE",
        "contract": HISTORICAL_NEWS_V1_CONTRACT,
        "contract_fingerprint": HISTORICAL_NEWS_V1_CONTRACT_FINGERPRINT,
        "credential_profile": profile,
        "history_start": HISTORY_START.isoformat(),
        "history_end": HISTORY_END.isoformat(),
        "monthly_partitions": len(completed),
        "reused_verified_partitions": len(reused),
        "acquired_partitions_this_run": len(pending),
        "raw_provider_records": total_raw_records,
        "normalized_unique_articles": total_articles,
        "raw_bytes": total_raw_bytes,
        "normalized_bytes": total_normalized_bytes,
        "pit_text_available_at": PIT_TEXT_AVAILABLE_AT,
        "storage_after": {
            "disk_free_gib": storage.disk_free_gib,
            "news_usage_gib": storage.category_usage_gib.get("news", 0.0),
            "news_quota_gib": storage.category_quota_gib.get("news", 0.0),
            "total_research_usage_gib": storage.total_research_usage_gib,
        },
        "month_receipt_fingerprints": [
            item["receipt_fingerprint"] for item in completed
        ],
        "authority": {
            "source_acquisition_only": True,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    summary["run_fingerprint"] = _canonical_hash(summary)
    summary_path = settings.resolved_path(
        "data/news/manifests/alpaca/historical_news_v1_summary.json"
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(summary_path, summary)
    return summary
