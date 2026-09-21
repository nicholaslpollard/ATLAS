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
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import duckdb

from packages.core.atomic_io import replace_with_retry
from packages.core.settings import AtlasSettings
from packages.data.historical_option_reference_v1_contract import (
    ACTIVE_HARD_END_EXCLUSIVE,
    HISTORICAL_OPTION_REFERENCE_V1_CONTRACT,
    HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT,
    PAGE_LIMIT,
    REFERENCE_AS_OF_DATE,
    SOURCE_ROLE,
    STORAGE_CATEGORY,
    ReferencePartition,
    reference_partitions,
)
from packages.data.research_storage import (
    assert_category_acquisition_allowed,
    inspect_research_storage,
)


class HistoricalOptionReferenceV1Error(RuntimeError):
    pass


_REQUIRED_FIELDS: tuple[str, ...] = (
    "ticker",
    "underlying_ticker",
    "contract_type",
    "expiration_date",
    "strike_price",
    "exercise_style",
    "shares_per_contract",
)
_MAX_PAGES_PER_PARTITION = 100_000


def _stable_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _stable_hash(value: object) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_massive_api_key(settings: AtlasSettings) -> str:
    env_name = settings.massive.credentials.api_key_env
    key = os.getenv(env_name, "").strip()
    if not key:
        raise HistoricalOptionReferenceV1Error(
            f"Massive API key is not configured in {env_name}"
        )
    return key


def _request_json(
    settings: AtlasSettings,
    *,
    url: str,
    api_key: str,
) -> dict[str, Any]:
    cfg = settings.massive.reference
    delay = float(cfg.initial_retry_seconds)
    for attempt in range(1, int(cfg.max_attempts) + 1):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "ATLAS-historical-option-reference-v1/1",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=float(cfg.request_timeout_seconds),
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise HistoricalOptionReferenceV1Error(
                    "Massive option-reference response root is not an object"
                )
            return payload
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt >= int(cfg.max_attempts):
                body = exc.read().decode("utf-8", errors="replace")[:500]
                raise HistoricalOptionReferenceV1Error(
                    f"Massive option-reference request failed HTTP {exc.code}: {body}"
                ) from exc
            retry_after = exc.headers.get("Retry-After")
            try:
                wait_seconds = float(retry_after) if retry_after else delay
            except ValueError:
                wait_seconds = delay
            time.sleep(max(0.0, wait_seconds))
            delay = min(float(cfg.max_retry_seconds), max(delay * 2.0, 0.1))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt >= int(cfg.max_attempts):
                raise HistoricalOptionReferenceV1Error(
                    f"Massive option-reference request failed after {attempt} attempts: {exc}"
                ) from exc
            time.sleep(delay)
            delay = min(float(cfg.max_retry_seconds), max(delay * 2.0, 0.1))
    raise AssertionError("unreachable")


def _endpoint(settings: AtlasSettings) -> str:
    return (
        settings.massive.provider.rest_base_url.rstrip("/")
        + settings.data.research.options.reference_endpoint_path
    )


def _validate_next_url(settings: AtlasSettings, value: str) -> None:
    parsed = urllib.parse.urlsplit(value)
    base = urllib.parse.urlsplit(settings.massive.provider.rest_base_url)
    if parsed.scheme != "https" or parsed.netloc != base.netloc:
        raise HistoricalOptionReferenceV1Error(
            "Massive pagination next_url escaped the configured HTTPS API host"
        )


def _partition_query_url(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> str:
    query = urllib.parse.urlencode(
        {
            "expiration_date.gte": partition.expiration_gte.isoformat(),
            "expiration_date.lt": partition.expiration_lt.isoformat(),
            "as_of": REFERENCE_AS_OF_DATE.isoformat(),
            "expired": "true" if partition.expired else "false",
            "order": "asc",
            "sort": "ticker",
            "limit": PAGE_LIMIT,
        }
    )
    return _endpoint(settings) + "?" + query


def _boundary_probe(
    settings: AtlasSettings,
    *,
    api_key: str,
) -> dict[str, object]:
    query = urllib.parse.urlencode(
        {
            "expiration_date.gte": ACTIVE_HARD_END_EXCLUSIVE.isoformat(),
            "as_of": REFERENCE_AS_OF_DATE.isoformat(),
            "expired": "false",
            "order": "asc",
            "sort": "expiration_date",
            "limit": 1,
        }
    )
    payload = _request_json(
        settings,
        url=_endpoint(settings) + "?" + query,
        api_key=api_key,
    )
    results = payload.get("results") or []
    if not isinstance(results, list) or any(
        not isinstance(item, dict) for item in results
    ):
        raise HistoricalOptionReferenceV1Error(
            "active hard-end boundary probe returned malformed results"
        )
    if results:
        sample = results[0]
        raise HistoricalOptionReferenceV1Error(
            "active option contract exists at or beyond the frozen "
            f"{ACTIVE_HARD_END_EXCLUSIVE.isoformat()} hard end: "
            f"{sample.get('ticker')!r} expiration={sample.get('expiration_date')!r}"
        )
    return {
        "status": "PASS",
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "expiration_date_gte": ACTIVE_HARD_END_EXCLUSIVE.isoformat(),
        "expired": False,
        "result_count": 0,
    }


def _validate_decimal(
    value: object,
    *,
    partition_key: str,
    ticker: str,
    field: str,
) -> str:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise HistoricalOptionReferenceV1Error(
            f"{partition_key}: {ticker}: invalid {field}={value!r}"
        ) from exc
    if not decimal_value.is_finite():
        raise HistoricalOptionReferenceV1Error(
            f"{partition_key}: {ticker}: non-finite {field}={value!r}"
        )
    return str(value)


def _normalize_record(
    item: dict[str, Any],
    *,
    partition: ReferencePartition,
) -> dict[str, object]:
    missing = [
        field for field in _REQUIRED_FIELDS
        if item.get(field) in (None, "")
    ]
    if missing:
        raise HistoricalOptionReferenceV1Error(
            f"{partition.key}: option-reference row is missing required fields {missing}"
        )

    ticker = str(item["ticker"]).strip()
    underlying = str(item["underlying_ticker"]).strip()
    if not ticker or not underlying:
        raise HistoricalOptionReferenceV1Error(
            f"{partition.key}: option-reference row has blank identity"
        )

    try:
        expiration = date.fromisoformat(str(item["expiration_date"]))
    except ValueError as exc:
        raise HistoricalOptionReferenceV1Error(
            f"{partition.key}: {ticker}: invalid expiration_date="
            f"{item.get('expiration_date')!r}"
        ) from exc
    if not (partition.expiration_gte <= expiration < partition.expiration_lt):
        raise HistoricalOptionReferenceV1Error(
            f"{partition.key}: {ticker}: expiration {expiration} escaped "
            f"[{partition.expiration_gte}, {partition.expiration_lt})"
        )

    contract_type = str(item["contract_type"]).strip().lower()
    if contract_type not in {"call", "put"}:
        raise HistoricalOptionReferenceV1Error(
            f"{partition.key}: {ticker}: unexpected contract_type={contract_type!r}"
        )

    strike_price = _validate_decimal(
        item["strike_price"],
        partition_key=partition.key,
        ticker=ticker,
        field="strike_price",
    )
    shares_per_contract = _validate_decimal(
        item["shares_per_contract"],
        partition_key=partition.key,
        ticker=ticker,
        field="shares_per_contract",
    )

    return {
        "ticker": ticker,
        "underlying_ticker": underlying,
        "contract_type": contract_type,
        "expiration_date": expiration.isoformat(),
        "strike_price": strike_price,
        "exercise_style": str(item["exercise_style"]).strip(),
        "shares_per_contract": shares_per_contract,
        "primary_exchange": str(item.get("primary_exchange") or ""),
        "cfi": str(item.get("cfi") or ""),
        "correction_json": _stable_json(item.get("correction")),
        "additional_underlyings_json": _stable_json(
            item.get("additional_underlyings") or []
        ),
        "provider_record_sha256": _stable_hash(item),
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "reference_state": partition.state,
        "source_role": SOURCE_ROLE,
    }


def _sql_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def _write_parquet_from_jsonl(
    *,
    normalized_jsonl: Path,
    parquet_path: Path,
    row_count: int,
) -> None:
    con = duckdb.connect(database=":memory:")
    try:
        if row_count:
            con.execute(
                f"""
                COPY (
                    SELECT
                        CAST(ticker AS VARCHAR) AS ticker,
                        CAST(underlying_ticker AS VARCHAR) AS underlying_ticker,
                        CAST(contract_type AS VARCHAR) AS contract_type,
                        TRY_CAST(expiration_date AS DATE) AS expiration_date,
                        TRY_CAST(strike_price AS DECIMAL(24,8)) AS strike_price,
                        CAST(exercise_style AS VARCHAR) AS exercise_style,
                        TRY_CAST(shares_per_contract AS DECIMAL(24,8))
                            AS shares_per_contract,
                        CAST(primary_exchange AS VARCHAR) AS primary_exchange,
                        CAST(cfi AS VARCHAR) AS cfi,
                        CAST(correction_json AS VARCHAR) AS correction_json,
                        CAST(additional_underlyings_json AS VARCHAR)
                            AS additional_underlyings_json,
                        CAST(provider_record_sha256 AS VARCHAR)
                            AS provider_record_sha256,
                        TRY_CAST(reference_as_of_date AS DATE)
                            AS reference_as_of_date,
                        CAST(reference_state AS VARCHAR) AS reference_state,
                        CAST(source_role AS VARCHAR) AS source_role
                    FROM read_json_auto(
                        '{_sql_literal(normalized_jsonl)}',
                        format='newline_delimited'
                    )
                    ORDER BY ticker
                )
                TO '{_sql_literal(parquet_path)}'
                (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
        else:
            con.execute(
                """
                CREATE TABLE empty_option_reference (
                    ticker VARCHAR,
                    underlying_ticker VARCHAR,
                    contract_type VARCHAR,
                    expiration_date DATE,
                    strike_price DECIMAL(24,8),
                    exercise_style VARCHAR,
                    shares_per_contract DECIMAL(24,8),
                    primary_exchange VARCHAR,
                    cfi VARCHAR,
                    correction_json VARCHAR,
                    additional_underlyings_json VARCHAR,
                    provider_record_sha256 VARCHAR,
                    reference_as_of_date DATE,
                    reference_state VARCHAR,
                    source_role VARCHAR
                )
                """
            )
            con.execute(
                f"""
                COPY (
                    SELECT * FROM empty_option_reference
                )
                TO '{_sql_literal(parquet_path)}'
                (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
    finally:
        con.close()


def _partition_paths(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> dict[str, Path]:
    root = settings.resolved_path("data")
    options = settings.data.research.options
    expiration_month = partition.expiration_gte.replace(day=1)
    suffix = (
        Path("massive")
        / f"reference_as_of={REFERENCE_AS_OF_DATE.isoformat()}"
        / f"state={partition.state.lower()}"
        / f"expiration_year={expiration_month.year:04d}"
        / f"expiration_month={expiration_month.month:02d}"
    )
    manifest_suffix = (
        Path("massive")
        / "historical_option_reference_v1"
        / f"state={partition.state.lower()}"
        / f"expiration_year={expiration_month.year:04d}"
        / f"expiration_month={expiration_month.month:02d}"
    )
    return {
        "raw": root / options.reference_subdir / suffix / "contracts.jsonl.gz",
        "normalized": root / options.reference_subdir / suffix / "contracts.parquet",
        "receipt": root / options.manifests_subdir / manifest_suffix / "receipt.json",
    }


def _relative(settings: AtlasSettings, path: Path) -> str:
    return str(path.resolve().relative_to(settings.project_root.resolve())).replace(
        "\\", "/"
    )


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        raw = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        ) + "\n"
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temp, path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _verified_existing_receipt(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> dict[str, object] | None:
    paths = _partition_paths(settings, partition)
    if not paths["receipt"].is_file():
        return None
    try:
        receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if receipt.get("status") != "COMPLETE":
        return None
    if (
        receipt.get("contract_fingerprint")
        != HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT
    ):
        return None
    if receipt.get("partition") != partition.key:
        return None
    for name in ("raw", "normalized"):
        path = paths[name]
        if not path.is_file():
            return None
        if receipt.get(f"{name}_sha256") != _sha256_file(path):
            return None
    return receipt


def _check_disk_guard(settings: AtlasSettings, *, partition_key: str) -> None:
    snapshot = inspect_research_storage(settings)
    if snapshot.status == "BLOCKED_MINIMUM_FREE_SPACE":
        raise HistoricalOptionReferenceV1Error(
            f"{partition_key}: acquisition stopped at configured minimum free-space floor"
        )


def _acquire_partition(
    settings: AtlasSettings,
    partition: ReferencePartition,
    *,
    api_key: str,
    persistence_lock: threading.Lock,
) -> dict[str, object]:
    paths = _partition_paths(settings, partition)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    staging = settings.resolved_path(
        Path("data/staging/historical_option_reference_v1") / partition.key
    )
    staging.mkdir(parents=True, exist_ok=True)
    raw_temp = staging / "contracts.jsonl.gz.tmp"
    normalized_jsonl = staging / "contracts.normalized.jsonl.tmp"
    parquet_temp = staging / "contracts.parquet.tmp"
    for path in (raw_temp, normalized_jsonl, parquet_temp):
        path.unlink(missing_ok=True)

    seen_tickers: set[str] = set()
    page_count = 0
    request_id_count = 0
    first_ticker: str | None = None
    last_ticker: str | None = None
    next_url = _partition_query_url(settings, partition)
    seen_page_urls: set[str] = set()

    try:
        with raw_temp.open("wb") as raw_file, normalized_jsonl.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as normalized_file:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=6,
                fileobj=raw_file,
                mtime=0,
            ) as gzip_file:
                while next_url:
                    if page_count >= _MAX_PAGES_PER_PARTITION:
                        raise HistoricalOptionReferenceV1Error(
                            f"{partition.key}: pagination exceeded "
                            f"{_MAX_PAGES_PER_PARTITION:,} pages"
                        )
                    _validate_next_url(settings, next_url)
                    page_key = _stable_hash(next_url)
                    if page_key in seen_page_urls:
                        raise HistoricalOptionReferenceV1Error(
                            f"{partition.key}: pagination next_url cycle detected"
                        )
                    seen_page_urls.add(page_key)

                    payload = _request_json(
                        settings,
                        url=next_url,
                        api_key=api_key,
                    )
                    provider_status = payload.get("status")
                    if provider_status not in (None, "OK"):
                        raise HistoricalOptionReferenceV1Error(
                            f"{partition.key}: provider status={provider_status!r}"
                        )
                    results = payload.get("results") or []
                    if not isinstance(results, list) or any(
                        not isinstance(item, dict) for item in results
                    ):
                        raise HistoricalOptionReferenceV1Error(
                            f"{partition.key}: results is not a list of objects"
                        )
                    if payload.get("request_id"):
                        request_id_count += 1

                    for raw_item in results:
                        item = dict(raw_item)
                        normalized = _normalize_record(
                            item,
                            partition=partition,
                        )
                        ticker = str(normalized["ticker"])
                        if ticker in seen_tickers:
                            raise HistoricalOptionReferenceV1Error(
                                f"{partition.key}: duplicate ticker {ticker!r}"
                            )
                        seen_tickers.add(ticker)
                        if first_ticker is None:
                            first_ticker = ticker
                        last_ticker = ticker

                        gzip_file.write(
                            (_stable_json(item) + "\n").encode("utf-8")
                        )
                        normalized_file.write(_stable_json(normalized))
                        normalized_file.write("\n")

                    page_count += 1
                    if page_count % 25 == 0:
                        _check_disk_guard(
                            settings,
                            partition_key=partition.key,
                        )

                    candidate = payload.get("next_url")
                    if candidate in (None, ""):
                        next_url = ""
                    elif not isinstance(candidate, str):
                        raise HistoricalOptionReferenceV1Error(
                            f"{partition.key}: next_url is not a string"
                        )
                    else:
                        next_url = candidate

            normalized_file.flush()
            os.fsync(normalized_file.fileno())
        with raw_temp.open("rb") as handle:
            os.fsync(handle.fileno())

        _write_parquet_from_jsonl(
            normalized_jsonl=normalized_jsonl,
            parquet_path=parquet_temp,
            row_count=len(seen_tickers),
        )

        raw_bytes = int(raw_temp.stat().st_size)
        normalized_bytes = int(parquet_temp.stat().st_size)
        final_bytes = raw_bytes + normalized_bytes
        existing_bytes = sum(
            int(paths[name].stat().st_size)
            for name in ("raw", "normalized")
            if paths[name].is_file()
        )
        projected_additional = max(0, final_bytes - existing_bytes)

        with persistence_lock:
            assert_category_acquisition_allowed(
                settings,
                category=STORAGE_CATEGORY,
                projected_additional_bytes=projected_additional,
            )
            replace_with_retry(raw_temp, paths["raw"])
            replace_with_retry(parquet_temp, paths["normalized"])

        receipt: dict[str, object] = {
            "status": "COMPLETE",
            "contract": HISTORICAL_OPTION_REFERENCE_V1_CONTRACT,
            "contract_fingerprint": (
                HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT
            ),
            "provider": "massive",
            "partition": partition.key,
            "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
            "reference_state": partition.state,
            "expiration_gte": partition.expiration_gte.isoformat(),
            "expiration_lt": partition.expiration_lt.isoformat(),
            "expired_query_value": partition.expired,
            "page_limit": PAGE_LIMIT,
            "page_count": page_count,
            "request_id_count": request_id_count,
            "raw_provider_records": len(seen_tickers),
            "normalized_unique_contracts": len(seen_tickers),
            "duplicate_ticker_rows": 0,
            "first_ticker": first_ticker,
            "last_ticker": last_ticker,
            "raw_path": _relative(settings, paths["raw"]),
            "normalized_path": _relative(settings, paths["normalized"]),
            "raw_bytes": int(paths["raw"].stat().st_size),
            "normalized_bytes": int(paths["normalized"].stat().st_size),
            "raw_sha256": _sha256_file(paths["raw"]),
            "normalized_sha256": _sha256_file(paths["normalized"]),
            "source_role": SOURCE_ROLE,
            "historical_candidate_availability_authority": False,
            "historical_dynamic_deliverable_authority": False,
            "historical_market_price_authority": False,
        }
        receipt["receipt_fingerprint"] = _stable_hash(receipt)
        _atomic_write_json(paths["receipt"], receipt)
        return receipt
    finally:
        for path in (raw_temp, normalized_jsonl, parquet_temp):
            path.unlink(missing_ok=True)


def run_historical_option_reference_v1_acquisition(
    settings: AtlasSettings,
    *,
    workers: int = 4,
) -> dict[str, object]:
    if workers < 1:
        raise ValueError("workers must be at least 1")

    api_key = _resolve_massive_api_key(settings)
    boundary = _boundary_probe(settings, api_key=api_key)
    partitions = reference_partitions()
    persistence_lock = threading.Lock()

    reused: list[dict[str, object]] = []
    pending: list[ReferencePartition] = []
    for partition in partitions:
        receipt = _verified_existing_receipt(settings, partition)
        if receipt is None:
            pending.append(partition)
        else:
            reused.append(receipt)

    print(
        "historical option reference v1: "
        f"{len(partitions)} monthly partitions / "
        f"{len(reused)} verified reusable / "
        f"{len(pending)} pending / workers={workers}",
        flush=True,
    )
    print(
        "  active hard-end boundary probe: PASS / "
        f"no active contracts >= {ACTIVE_HARD_END_EXCLUSIVE.isoformat()} "
        f"as of {REFERENCE_AS_OF_DATE.isoformat()}",
        flush=True,
    )

    completed: list[dict[str, object]] = list(reused)
    if pending:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _acquire_partition,
                    settings,
                    partition,
                    api_key=api_key,
                    persistence_lock=persistence_lock,
                ): partition
                for partition in pending
            }
            done = 0
            for future in as_completed(futures):
                partition = futures[future]
                receipt = future.result()
                completed.append(receipt)
                done += 1
                storage = inspect_research_storage(settings)
                print(
                    f"  {done}/{len(pending)} acquired {partition.key}: "
                    f"{int(receipt['normalized_unique_contracts']):,} contracts / "
                    f"{int(receipt['page_count']):,} pages / "
                    f"reference="
                    f"{storage.category_usage_gib.get(STORAGE_CATEGORY, 0.0):.3f} GiB / "
                    f"free={storage.disk_free_gib:.2f} GiB",
                    flush=True,
                )

    completed.sort(key=lambda item: str(item["partition"]))
    total_raw_records = sum(
        int(item["raw_provider_records"]) for item in completed
    )
    total_normalized = sum(
        int(item["normalized_unique_contracts"]) for item in completed
    )
    total_raw_bytes = sum(int(item["raw_bytes"]) for item in completed)
    total_normalized_bytes = sum(
        int(item["normalized_bytes"]) for item in completed
    )
    storage = inspect_research_storage(settings)

    corpus_basis = {
        "contract_fingerprint": (
            HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT
        ),
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "partition_receipt_fingerprints": [
            str(item["receipt_fingerprint"]) for item in completed
        ],
        "raw_provider_records": total_raw_records,
        "normalized_unique_contracts": total_normalized,
        "raw_bytes": total_raw_bytes,
        "normalized_bytes": total_normalized_bytes,
    }
    summary: dict[str, object] = {
        "status": "COMPLETE",
        "contract": HISTORICAL_OPTION_REFERENCE_V1_CONTRACT,
        "contract_fingerprint": (
            HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT
        ),
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "active_hard_end_exclusive": ACTIVE_HARD_END_EXCLUSIVE.isoformat(),
        "boundary_probe": boundary,
        "monthly_partitions": len(completed),
        "reused_verified_partitions": len(reused),
        "acquired_partitions_this_run": len(pending),
        "raw_provider_records": total_raw_records,
        "normalized_unique_contracts": total_normalized,
        "duplicate_ticker_rows": 0,
        "raw_bytes": total_raw_bytes,
        "normalized_bytes": total_normalized_bytes,
        "source_role": SOURCE_ROLE,
        "storage_after": {
            "disk_free_gib": storage.disk_free_gib,
            "options_reference_usage_gib": (
                storage.category_usage_gib.get(STORAGE_CATEGORY, 0.0)
            ),
            "options_reference_quota_gib": (
                storage.category_quota_gib.get(STORAGE_CATEGORY, 0.0)
            ),
            "total_research_usage_gib": storage.total_research_usage_gib,
        },
        "partition_receipt_fingerprints": (
            corpus_basis["partition_receipt_fingerprints"]
        ),
        "corpus_fingerprint": _stable_hash(corpus_basis),
        "authority": {
            "source_acquisition_only": True,
            "reference_identity_and_structure": True,
            "historical_candidate_availability_authority": False,
            "historical_dynamic_deliverable_authority": False,
            "historical_market_price_authority": False,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    summary["run_fingerprint"] = _stable_hash(
        {
            key: value
            for key, value in summary.items()
            if key != "storage_after"
        }
    )

    summary_path = settings.resolved_path(
        "data/options/manifests/massive/"
        "historical_option_reference_v1_summary.json"
    )
    _atomic_write_json(summary_path, summary)
    return summary
