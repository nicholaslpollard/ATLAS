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
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, TypeVar

import duckdb

from packages.core.atomic_io import replace_with_retry
from packages.core.settings import AtlasSettings
from packages.data.historical_option_reference_v1_contract import (
    HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT,
)
from packages.data.historical_option_reference_v2_contract import (
    ACTIVE_HARD_END_EXCLUSIVE,
    HISTORICAL_OPTION_REFERENCE_V2_CONTRACT,
    HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT,
    PAGE_LIMIT,
    REFERENCE_AS_OF_DATE,
    CORRECTION_SELECTION_POLICY,
    SOURCE_ROLE,
    STORAGE_CATEGORY,
    ReferencePartition,
    reference_partitions,
)
from packages.data.research_storage import (
    assert_category_acquisition_allowed,
    inspect_research_storage,
)


class HistoricalOptionReferenceV2Error(RuntimeError):
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
_T = TypeVar("_T")


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
        raise HistoricalOptionReferenceV2Error(
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
                "User-Agent": "ATLAS-historical-option-reference-v2/1",
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
                raise HistoricalOptionReferenceV2Error(
                    "Massive option-reference response root is not an object"
                )
            return payload
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt >= int(cfg.max_attempts):
                body = exc.read().decode("utf-8", errors="replace")[:500]
                raise HistoricalOptionReferenceV2Error(
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
                raise HistoricalOptionReferenceV2Error(
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
        raise HistoricalOptionReferenceV2Error(
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
        raise HistoricalOptionReferenceV2Error(
            "active hard-end boundary probe returned malformed results"
        )
    if results:
        sample = results[0]
        raise HistoricalOptionReferenceV2Error(
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
        raise HistoricalOptionReferenceV2Error(
            f"{partition_key}: {ticker}: invalid {field}={value!r}"
        ) from exc
    if not decimal_value.is_finite():
        raise HistoricalOptionReferenceV2Error(
            f"{partition_key}: {ticker}: non-finite {field}={value!r}"
        )
    return str(value)


def _correction_rank(item: dict[str, Any]) -> int:
    value = item.get("correction")
    if value in (None, ""):
        return -1
    if isinstance(value, bool):
        raise HistoricalOptionReferenceV2Error(
            f"invalid boolean correction value: {value!r}"
        )
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HistoricalOptionReferenceV2Error(
            f"invalid correction value: {value!r}"
        ) from exc
    if not decimal_value.is_finite():
        raise HistoricalOptionReferenceV2Error(
            f"invalid correction value: {value!r}"
        )
    if decimal_value != decimal_value.to_integral_value():
        raise HistoricalOptionReferenceV2Error(
            f"non-integral correction value: {value!r}"
        )
    numeric = int(decimal_value)
    if numeric < 0:
        raise HistoricalOptionReferenceV2Error(
            f"negative correction value: {value!r}"
        )
    return numeric


def _validate_structural_record(
    item: dict[str, Any],
    *,
    partition: ReferencePartition,
) -> tuple[str, date, str, str, str]:
    missing = [
        field for field in _REQUIRED_FIELDS
        if item.get(field) in (None, "")
    ]
    if missing:
        raise HistoricalOptionReferenceV2Error(
            f"{partition.key}: option-reference row is missing required fields {missing}"
        )

    ticker = str(item["ticker"]).strip()
    underlying = str(item["underlying_ticker"]).strip()
    if not ticker or not underlying:
        raise HistoricalOptionReferenceV2Error(
            f"{partition.key}: option-reference row has blank identity"
        )

    try:
        expiration = date.fromisoformat(str(item["expiration_date"]))
    except ValueError as exc:
        raise HistoricalOptionReferenceV2Error(
            f"{partition.key}: {ticker}: invalid expiration_date="
            f"{item.get('expiration_date')!r}"
        ) from exc
    if not (partition.expiration_gte <= expiration < partition.expiration_lt):
        raise HistoricalOptionReferenceV2Error(
            f"{partition.key}: {ticker}: expiration {expiration} escaped "
            f"[{partition.expiration_gte}, {partition.expiration_lt})"
        )

    contract_type = str(item["contract_type"]).strip().lower()
    if contract_type not in {"call", "put", "other"}:
        raise HistoricalOptionReferenceV2Error(
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
    return ticker, expiration, contract_type, strike_price, shares_per_contract


def _resolve_ticker_versions(
    versions: list[dict[str, Any]],
    *,
    partition: ReferencePartition,
) -> tuple[dict[str, object], int]:
    if not versions:
        raise HistoricalOptionReferenceV2Error(
            f"{partition.key}: empty ticker-version group"
        )

    validated = [
        (_validate_structural_record(item, partition=partition), item)
        for item in versions
    ]
    tickers = {entry[0][0] for entry in validated}
    if len(tickers) != 1:
        raise HistoricalOptionReferenceV2Error(
            f"{partition.key}: mixed ticker identities in version group: {sorted(tickers)}"
        )
    ticker = next(iter(tickers))

    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for _structural, item in validated:
        ranked.append((_correction_rank(item), _stable_json(item), item))
    highest_rank = max(item[0] for item in ranked)
    highest = [item for item in ranked if item[0] == highest_rank]
    highest_payloads = {item[1] for item in highest}
    if len(highest_payloads) != 1:
        raise HistoricalOptionReferenceV2Error(
            f"{partition.key}: {ticker}: conflicting provider rows share "
            f"highest correction rank {highest_rank}"
        )
    selected_json = next(iter(highest_payloads))
    selected = next(item[2] for item in highest if item[1] == selected_json)

    ticker2, expiration, contract_type, strike_price, shares_per_contract = (
        _validate_structural_record(selected, partition=partition)
    )
    assert ticker2 == ticker

    selected_hash = _stable_hash(selected)
    all_hashes = [_stable_hash(item) for _structural, item in validated]
    discarded_hashes = list(all_hashes)
    discarded_hashes.remove(selected_hash)
    observed_corrections = sorted(
        {
            _correction_rank(item)
            for _structural, item in validated
        }
    )
    exact_duplicate_rows = sum(
        1
        for _structural, item in validated
        if _stable_hash(item) == selected_hash
    ) - 1

    normalized: dict[str, object] = {
        "ticker": ticker,
        "underlying_ticker": str(selected["underlying_ticker"]).strip(),
        "contract_type": contract_type,
        "expiration_date": expiration.isoformat(),
        "strike_price": strike_price,
        "exercise_style": str(selected["exercise_style"]).strip(),
        "shares_per_contract": shares_per_contract,
        "primary_exchange": str(selected.get("primary_exchange") or ""),
        "cfi": str(selected.get("cfi") or ""),
        "correction_json": _stable_json(selected.get("correction")),
        "additional_underlyings_json": _stable_json(
            selected.get("additional_underlyings") or []
        ),
        "provider_record_sha256": selected_hash,
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "reference_state": partition.state,
        "source_role": SOURCE_ROLE,
        "version_count": len(versions),
        "selected_correction_rank": highest_rank,
        "observed_correction_ranks_json": _stable_json(observed_corrections),
        "discarded_version_hashes_json": _stable_json(discarded_hashes),
        "exact_duplicate_rows": exact_duplicate_rows,
        "correction_selection_policy": CORRECTION_SELECTION_POLICY,
    }
    return normalized, len(discarded_hashes)

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
                        CAST(source_role AS VARCHAR) AS source_role,
                        TRY_CAST(version_count AS BIGINT) AS version_count,
                        TRY_CAST(selected_correction_rank AS BIGINT)
                            AS selected_correction_rank,
                        CAST(observed_correction_ranks_json AS VARCHAR)
                            AS observed_correction_ranks_json,
                        CAST(discarded_version_hashes_json AS VARCHAR)
                            AS discarded_version_hashes_json,
                        TRY_CAST(exact_duplicate_rows AS BIGINT)
                            AS exact_duplicate_rows,
                        CAST(correction_selection_policy AS VARCHAR)
                            AS correction_selection_policy
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
                    source_role VARCHAR,
                    version_count BIGINT,
                    selected_correction_rank BIGINT,
                    observed_correction_ranks_json VARCHAR,
                    discarded_version_hashes_json VARCHAR,
                    exact_duplicate_rows BIGINT,
                    correction_selection_policy VARCHAR
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


def _v1_partition_paths(
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


def _partition_paths(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> dict[str, Path]:
    root = settings.resolved_path("data")
    options = settings.data.research.options
    expiration_month = partition.expiration_gte.replace(day=1)
    suffix = (
        Path("massive/historical_option_reference_v2")
        / f"reference_as_of={REFERENCE_AS_OF_DATE.isoformat()}"
        / f"state={partition.state.lower()}"
        / f"expiration_year={expiration_month.year:04d}"
        / f"expiration_month={expiration_month.month:02d}"
    )
    manifest_suffix = (
        Path("massive")
        / "historical_option_reference_v2"
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


def _receipt_data_path(
    settings: AtlasSettings,
    value: object,
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    root = settings.project_root.resolve()
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        return None
    return candidate


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
        != HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
    ):
        return None
    if receipt.get("partition") != partition.key:
        return None
    expected_fingerprint = receipt.get("receipt_fingerprint")
    fingerprint_payload = dict(receipt)
    fingerprint_payload.pop("receipt_fingerprint", None)
    if expected_fingerprint != _stable_hash(fingerprint_payload):
        return None
    for name in ("raw", "normalized"):
        path = _receipt_data_path(settings, receipt.get(f"{name}_path"))
        if path is None or not path.is_file():
            return None
        if receipt.get(f"{name}_sha256") != _sha256_file(path):
            return None
    return receipt


def _verified_v1_raw_receipt(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> dict[str, object] | None:
    paths = _v1_partition_paths(settings, partition)
    receipt_path = paths["receipt"]
    if not receipt_path.is_file() or not paths["raw"].is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
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
    if receipt.get("reference_as_of_date") != REFERENCE_AS_OF_DATE.isoformat():
        return None
    if receipt.get("reference_state") != partition.state:
        return None
    if receipt.get("expiration_gte") != partition.expiration_gte.isoformat():
        return None
    if receipt.get("expiration_lt") != partition.expiration_lt.isoformat():
        return None
    if bool(receipt.get("expired_query_value")) != partition.expired:
        return None
    if int(receipt.get("page_limit", -1)) != PAGE_LIMIT:
        return None
    if int(receipt.get("duplicate_ticker_rows", -1)) != 0:
        return None
    if int(receipt.get("raw_provider_records", -1)) != int(
        receipt.get("normalized_unique_contracts", -2)
    ):
        return None
    expected_fingerprint = receipt.get("receipt_fingerprint")
    fingerprint_payload = dict(receipt)
    fingerprint_payload.pop("receipt_fingerprint", None)
    if expected_fingerprint != _stable_hash(fingerprint_payload):
        return None
    if receipt.get("raw_sha256") != _sha256_file(paths["raw"]):
        return None
    return receipt


def _check_disk_guard(settings: AtlasSettings, *, partition_key: str) -> None:
    snapshot = inspect_research_storage(settings)
    if snapshot.status == "BLOCKED_MINIMUM_FREE_SPACE":
        raise HistoricalOptionReferenceV2Error(
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
        Path("data/staging/historical_option_reference_v2") / partition.key
    )
    staging.mkdir(parents=True, exist_ok=True)
    raw_temp = staging / "contracts.jsonl.gz.tmp"
    normalized_jsonl = staging / "contracts.normalized.jsonl.tmp"
    parquet_temp = staging / "contracts.parquet.tmp"
    for path in (raw_temp, normalized_jsonl, parquet_temp):
        path.unlink(missing_ok=True)

    page_count = 0
    request_id_count = 0
    raw_provider_records = 0
    normalized_unique_contracts = 0
    duplicate_version_rows = 0
    tickers_with_multiple_versions = 0
    exact_duplicate_rows = 0
    corrected_selected_contracts = 0
    first_ticker: str | None = None
    last_ticker: str | None = None
    current_ticker: str | None = None
    current_versions: list[dict[str, Any]] = []
    next_url = _partition_query_url(settings, partition)
    seen_page_urls: set[str] = set()

    def flush_group(normalized_file) -> None:
        nonlocal normalized_unique_contracts
        nonlocal duplicate_version_rows
        nonlocal tickers_with_multiple_versions
        nonlocal exact_duplicate_rows
        nonlocal corrected_selected_contracts
        nonlocal current_versions
        if not current_versions:
            return
        normalized, discarded = _resolve_ticker_versions(
            current_versions,
            partition=partition,
        )
        normalized_file.write(_stable_json(normalized))
        normalized_file.write("\n")
        normalized_unique_contracts += 1
        duplicate_version_rows += discarded
        if len(current_versions) > 1:
            tickers_with_multiple_versions += 1
        exact_duplicate_rows += int(normalized["exact_duplicate_rows"])
        if int(normalized["selected_correction_rank"]) >= 0:
            corrected_selected_contracts += 1
        current_versions = []

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
                        raise HistoricalOptionReferenceV2Error(
                            f"{partition.key}: pagination exceeded "
                            f"{_MAX_PAGES_PER_PARTITION:,} pages"
                        )
                    _validate_next_url(settings, next_url)
                    page_key = _stable_hash(next_url)
                    if page_key in seen_page_urls:
                        raise HistoricalOptionReferenceV2Error(
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
                        raise HistoricalOptionReferenceV2Error(
                            f"{partition.key}: provider status={provider_status!r}"
                        )
                    results = payload.get("results") or []
                    if not isinstance(results, list) or any(
                        not isinstance(item, dict) for item in results
                    ):
                        raise HistoricalOptionReferenceV2Error(
                            f"{partition.key}: results is not a list of objects"
                        )
                    if payload.get("request_id"):
                        request_id_count += 1

                    for raw_item in results:
                        item = dict(raw_item)
                        ticker, *_rest = _validate_structural_record(
                            item,
                            partition=partition,
                        )
                        if last_ticker is not None and ticker < last_ticker:
                            raise HistoricalOptionReferenceV2Error(
                                f"{partition.key}: provider ticker order regressed "
                                f"from {last_ticker!r} to {ticker!r}"
                            )
                        if current_ticker is None:
                            current_ticker = ticker
                            first_ticker = ticker
                        elif ticker != current_ticker:
                            flush_group(normalized_file)
                            current_ticker = ticker

                        current_versions.append(item)
                        last_ticker = ticker
                        raw_provider_records += 1
                        gzip_file.write(
                            (_stable_json(item) + "\n").encode("utf-8")
                        )

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
                        raise HistoricalOptionReferenceV2Error(
                            f"{partition.key}: next_url is not a string"
                        )
                    else:
                        next_url = candidate

                flush_group(normalized_file)

            raw_file.flush()
            os.fsync(raw_file.fileno())
            normalized_file.flush()
            os.fsync(normalized_file.fileno())

        if raw_provider_records != normalized_unique_contracts + duplicate_version_rows:
            raise HistoricalOptionReferenceV2Error(
                f"{partition.key}: raw/version reconciliation failed: "
                f"{raw_provider_records} != {normalized_unique_contracts} + "
                f"{duplicate_version_rows}"
            )

        _write_parquet_from_jsonl(
            normalized_jsonl=normalized_jsonl,
            parquet_path=parquet_temp,
            row_count=normalized_unique_contracts,
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
            "contract": HISTORICAL_OPTION_REFERENCE_V2_CONTRACT,
            "contract_fingerprint": (
                HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
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
            "raw_provider_records": raw_provider_records,
            "normalized_unique_contracts": normalized_unique_contracts,
            "duplicate_version_rows": duplicate_version_rows,
            "tickers_with_multiple_versions": tickers_with_multiple_versions,
            "exact_duplicate_rows": exact_duplicate_rows,
            "corrected_selected_contracts": corrected_selected_contracts,
            "raw_version_reconciliation": (
                raw_provider_records
                == normalized_unique_contracts + duplicate_version_rows
            ),
            "correction_selection_policy": CORRECTION_SELECTION_POLICY,
            "first_ticker": first_ticker,
            "last_ticker": last_ticker,
            "raw_path": _relative(settings, paths["raw"]),
            "normalized_path": _relative(settings, paths["normalized"]),
            "raw_origin_contract_fingerprint": (
                HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
            ),
            "raw_reused_from_v1": False,
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


def _rebuild_partition_from_v1_raw(
    settings: AtlasSettings,
    partition: ReferencePartition,
    *,
    v1_receipt: dict[str, object],
    persistence_lock: threading.Lock,
) -> dict[str, object]:
    v1_paths = _v1_partition_paths(settings, partition)
    paths = _partition_paths(settings, partition)
    paths["normalized"].parent.mkdir(parents=True, exist_ok=True)
    paths["receipt"].parent.mkdir(parents=True, exist_ok=True)

    staging = settings.resolved_path(
        Path("data/staging/historical_option_reference_v2_v1_reuse")
        / partition.key
    )
    staging.mkdir(parents=True, exist_ok=True)
    normalized_jsonl = staging / "contracts.normalized.jsonl.tmp"
    parquet_temp = staging / "contracts.parquet.tmp"
    for path in (normalized_jsonl, parquet_temp):
        path.unlink(missing_ok=True)

    raw_provider_records = 0
    normalized_unique_contracts = 0
    duplicate_version_rows = 0
    tickers_with_multiple_versions = 0
    exact_duplicate_rows = 0
    corrected_selected_contracts = 0
    first_ticker: str | None = None
    last_ticker: str | None = None
    current_ticker: str | None = None
    current_versions: list[dict[str, Any]] = []

    def flush_group(normalized_file) -> None:
        nonlocal normalized_unique_contracts
        nonlocal duplicate_version_rows
        nonlocal tickers_with_multiple_versions
        nonlocal exact_duplicate_rows
        nonlocal corrected_selected_contracts
        nonlocal current_versions
        if not current_versions:
            return
        normalized, discarded = _resolve_ticker_versions(
            current_versions,
            partition=partition,
        )
        normalized_file.write(_stable_json(normalized))
        normalized_file.write("\n")
        normalized_unique_contracts += 1
        duplicate_version_rows += discarded
        if len(current_versions) > 1:
            tickers_with_multiple_versions += 1
        exact_duplicate_rows += int(normalized["exact_duplicate_rows"])
        if int(normalized["selected_correction_rank"]) >= 0:
            corrected_selected_contracts += 1
        current_versions = []

    try:
        with gzip.open(
            v1_paths["raw"],
            "rt",
            encoding="utf-8",
            newline="",
        ) as raw_file, normalized_jsonl.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as normalized_file:
            for line_number, line in enumerate(raw_file, start=1):
                if not line.strip():
                    continue
                try:
                    raw_item = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise HistoricalOptionReferenceV2Error(
                        f"{partition.key}: invalid V1 raw JSONL at line {line_number}"
                    ) from exc
                if not isinstance(raw_item, dict):
                    raise HistoricalOptionReferenceV2Error(
                        f"{partition.key}: V1 raw line {line_number} is not an object"
                    )
                item = dict(raw_item)
                ticker, *_rest = _validate_structural_record(
                    item,
                    partition=partition,
                )
                if last_ticker is not None and ticker < last_ticker:
                    raise HistoricalOptionReferenceV2Error(
                        f"{partition.key}: verified V1 raw ticker order regressed "
                        f"from {last_ticker!r} to {ticker!r}"
                    )
                if current_ticker is None:
                    current_ticker = ticker
                    first_ticker = ticker
                elif ticker != current_ticker:
                    flush_group(normalized_file)
                    current_ticker = ticker
                current_versions.append(item)
                last_ticker = ticker
                raw_provider_records += 1

            flush_group(normalized_file)
            normalized_file.flush()
            os.fsync(normalized_file.fileno())

        expected_raw_records = int(v1_receipt["raw_provider_records"])
        if raw_provider_records != expected_raw_records:
            raise HistoricalOptionReferenceV2Error(
                f"{partition.key}: verified V1 raw row count changed: "
                f"{raw_provider_records} != {expected_raw_records}"
            )
        if raw_provider_records != normalized_unique_contracts + duplicate_version_rows:
            raise HistoricalOptionReferenceV2Error(
                f"{partition.key}: V1 raw/version reconciliation failed: "
                f"{raw_provider_records} != {normalized_unique_contracts} + "
                f"{duplicate_version_rows}"
            )

        _write_parquet_from_jsonl(
            normalized_jsonl=normalized_jsonl,
            parquet_path=parquet_temp,
            row_count=normalized_unique_contracts,
        )
        normalized_bytes = int(parquet_temp.stat().st_size)
        existing_bytes = (
            int(paths["normalized"].stat().st_size)
            if paths["normalized"].is_file()
            else 0
        )
        projected_additional = max(0, normalized_bytes - existing_bytes)

        with persistence_lock:
            assert_category_acquisition_allowed(
                settings,
                category=STORAGE_CATEGORY,
                projected_additional_bytes=projected_additional,
            )
            replace_with_retry(parquet_temp, paths["normalized"])

        raw_path = v1_paths["raw"]
        receipt: dict[str, object] = {
            "status": "COMPLETE",
            "contract": HISTORICAL_OPTION_REFERENCE_V2_CONTRACT,
            "contract_fingerprint": (
                HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
            ),
            "provider": "massive",
            "partition": partition.key,
            "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
            "reference_state": partition.state,
            "expiration_gte": partition.expiration_gte.isoformat(),
            "expiration_lt": partition.expiration_lt.isoformat(),
            "expired_query_value": partition.expired,
            "page_limit": PAGE_LIMIT,
            "page_count": int(v1_receipt.get("page_count", 0)),
            "request_id_count": int(v1_receipt.get("request_id_count", 0)),
            "raw_provider_records": raw_provider_records,
            "normalized_unique_contracts": normalized_unique_contracts,
            "duplicate_version_rows": duplicate_version_rows,
            "tickers_with_multiple_versions": tickers_with_multiple_versions,
            "exact_duplicate_rows": exact_duplicate_rows,
            "corrected_selected_contracts": corrected_selected_contracts,
            "raw_version_reconciliation": (
                raw_provider_records
                == normalized_unique_contracts + duplicate_version_rows
            ),
            "correction_selection_policy": CORRECTION_SELECTION_POLICY,
            "first_ticker": first_ticker,
            "last_ticker": last_ticker,
            "raw_path": _relative(settings, raw_path),
            "normalized_path": _relative(settings, paths["normalized"]),
            "raw_origin_contract_fingerprint": (
                HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT
            ),
            "raw_origin_receipt_fingerprint": (
                v1_receipt["receipt_fingerprint"]
            ),
            "raw_reused_from_v1": True,
            "raw_bytes": int(raw_path.stat().st_size),
            "normalized_bytes": int(paths["normalized"].stat().st_size),
            "raw_sha256": _sha256_file(raw_path),
            "normalized_sha256": _sha256_file(paths["normalized"]),
            "source_role": SOURCE_ROLE,
            "historical_candidate_availability_authority": False,
            "historical_dynamic_deliverable_authority": False,
            "historical_market_price_authority": False,
        }
        if receipt["raw_sha256"] != v1_receipt.get("raw_sha256"):
            raise HistoricalOptionReferenceV2Error(
                f"{partition.key}: V1 raw hash changed during local V2 rebuild"
            )
        receipt["receipt_fingerprint"] = _stable_hash(receipt)
        _atomic_write_json(paths["receipt"], receipt)
        return receipt
    finally:
        for path in (normalized_jsonl, parquet_temp):
            path.unlink(missing_ok=True)


def _run_bounded(
    items: list[_T],
    *,
    workers: int,
    task: Callable[[_T], dict[str, object]],
    on_complete: Callable[[_T, dict[str, object], int], None],
) -> list[dict[str, object]]:
    if not items:
        return []

    iterator = iter(items)
    pool = ThreadPoolExecutor(max_workers=workers)
    in_flight: dict[object, _T] = {}
    results: list[dict[str, object]] = []

    def submit_next() -> bool:
        try:
            item = next(iterator)
        except StopIteration:
            return False
        in_flight[pool.submit(task, item)] = item
        return True

    try:
        for _ in range(min(workers, len(items))):
            submit_next()

        completed_count = 0
        while in_flight:
            done, _pending = wait(
                tuple(in_flight),
                return_when=FIRST_COMPLETED,
            )

            batch: list[tuple[_T, dict[str, object]]] = []
            for future in done:
                item = in_flight.pop(future)
                batch.append((item, future.result()))

            for item, receipt in batch:
                results.append(receipt)
                completed_count += 1
                on_complete(item, receipt, completed_count)

            for _ in batch:
                submit_next()
    except Exception:
        for future in in_flight:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
    return results


def run_historical_option_reference_v2_acquisition(
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

    reused_v2: list[dict[str, object]] = []
    rebuild_from_v1: list[tuple[ReferencePartition, dict[str, object]]] = []
    provider_pending: list[ReferencePartition] = []
    for partition in partitions:
        receipt = _verified_existing_receipt(settings, partition)
        if receipt is not None:
            reused_v2.append(receipt)
            continue
        v1_receipt = _verified_v1_raw_receipt(settings, partition)
        if v1_receipt is not None:
            rebuild_from_v1.append((partition, v1_receipt))
        else:
            provider_pending.append(partition)

    print(
        "historical option reference v2: "
        f"{len(partitions)} monthly partitions / "
        f"{len(reused_v2)} verified V2 reusable / "
        f"{len(rebuild_from_v1)} verified V1 raw reusable / "
        f"{len(provider_pending)} provider pending / workers={workers}",
        flush=True,
    )
    print(
        "  bounded scheduling: at most "
        f"{workers} partitions in flight; no all-corpus prequeue",
        flush=True,
    )
    print(
        "  active hard-end boundary probe: PASS / "
        f"no active contracts >= {ACTIVE_HARD_END_EXCLUSIVE.isoformat()} "
        f"as of {REFERENCE_AS_OF_DATE.isoformat()}",
        flush=True,
    )

    completed: list[dict[str, object]] = list(reused_v2)

    if rebuild_from_v1:
        def rebuild_task(
            item: tuple[ReferencePartition, dict[str, object]],
        ) -> dict[str, object]:
            partition, v1_receipt = item
            return _rebuild_partition_from_v1_raw(
                settings,
                partition,
                v1_receipt=v1_receipt,
                persistence_lock=persistence_lock,
            )

        def rebuild_progress(
            item: tuple[ReferencePartition, dict[str, object]],
            receipt: dict[str, object],
            done: int,
        ) -> None:
            partition, _v1_receipt = item
            storage = inspect_research_storage(settings)
            print(
                f"  {done}/{len(rebuild_from_v1)} rebuilt {partition.key} "
                "from verified V1 raw: "
                f"{int(receipt['normalized_unique_contracts']):,} contracts / "
                f"reference="
                f"{storage.category_usage_gib.get(STORAGE_CATEGORY, 0.0):.3f} GiB / "
                f"free={storage.disk_free_gib:.2f} GiB",
                flush=True,
            )

        completed.extend(
            _run_bounded(
                rebuild_from_v1,
                workers=workers,
                task=rebuild_task,
                on_complete=rebuild_progress,
            )
        )

    if provider_pending:
        def provider_task(partition: ReferencePartition) -> dict[str, object]:
            return _acquire_partition(
                settings,
                partition,
                api_key=api_key,
                persistence_lock=persistence_lock,
            )

        def provider_progress(
            partition: ReferencePartition,
            receipt: dict[str, object],
            done: int,
        ) -> None:
            storage = inspect_research_storage(settings)
            print(
                f"  {done}/{len(provider_pending)} acquired {partition.key}: "
                f"{int(receipt['normalized_unique_contracts']):,} contracts / "
                f"{int(receipt['duplicate_version_rows']):,} version rows / "
                f"{int(receipt['tickers_with_multiple_versions']):,} "
                "multi-version tickers / "
                f"{int(receipt['page_count']):,} pages / "
                f"reference="
                f"{storage.category_usage_gib.get(STORAGE_CATEGORY, 0.0):.3f} GiB / "
                f"free={storage.disk_free_gib:.2f} GiB",
                flush=True,
            )

        completed.extend(
            _run_bounded(
                provider_pending,
                workers=workers,
                task=provider_task,
                on_complete=provider_progress,
            )
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
            HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
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
        "contract": HISTORICAL_OPTION_REFERENCE_V2_CONTRACT,
        "contract_fingerprint": (
            HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
        ),
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "active_hard_end_exclusive": ACTIVE_HARD_END_EXCLUSIVE.isoformat(),
        "boundary_probe": boundary,
        "monthly_partitions": len(completed),
        "reused_verified_partitions": len(reused_v2),
        "rebuilt_from_verified_v1_raw_this_run": len(rebuild_from_v1),
        "provider_acquired_partitions_this_run": len(provider_pending),
        "acquired_partitions_this_run": (
            len(rebuild_from_v1) + len(provider_pending)
        ),
        "raw_provider_records": total_raw_records,
        "normalized_unique_contracts": total_normalized,
        "duplicate_version_rows": sum(
            int(item["duplicate_version_rows"]) for item in completed
        ),
        "tickers_with_multiple_versions": sum(
            int(item["tickers_with_multiple_versions"]) for item in completed
        ),
        "exact_duplicate_rows": sum(
            int(item["exact_duplicate_rows"]) for item in completed
        ),
        "corrected_selected_contracts": sum(
            int(item["corrected_selected_contracts"]) for item in completed
        ),
        "raw_version_reconciliation": all(
            bool(item["raw_version_reconciliation"]) for item in completed
        ),
        "correction_selection_policy": CORRECTION_SELECTION_POLICY,
        "raw_reused_from_v1_partitions": sum(
            1 for item in completed if bool(item.get("raw_reused_from_v1"))
        ),
        "bounded_in_flight_partitions": workers,
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
        "historical_option_reference_v2_summary.json"
    )
    _atomic_write_json(summary_path, summary)
    return summary
