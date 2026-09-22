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
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, TypeVar

import duckdb

from packages.core.atomic_io import replace_with_retry
from packages.core.settings import AtlasSettings
from packages.data.historical_option_reference_v1_contract import (
    HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT,
)
import packages.data.historical_option_reference_v2 as v2_parent
from packages.data.historical_option_reference_v2_contract import (
    HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT,
)
import packages.data.historical_option_reference_v3 as v3_parent
from packages.data.historical_option_reference_v3_contract import (
    HISTORICAL_OPTION_REFERENCE_V3_CONTRACT_FINGERPRINT,
)
import packages.data.historical_option_reference_v4 as v4_parent
from packages.data.historical_option_reference_v4_contract import (
    HISTORICAL_OPTION_REFERENCE_V4_CONTRACT_FINGERPRINT,
)
import packages.data.historical_option_reference_v5 as v5_parent
from packages.data.historical_option_reference_v5_contract import (
    HISTORICAL_OPTION_REFERENCE_V5_CONTRACT_FINGERPRINT,
)
from packages.data.historical_option_reference_v6_contract import (
    ACTIVE_HARD_END_EXCLUSIVE,
    HISTORICAL_OPTION_REFERENCE_V6_CONTRACT,
    HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT,
    PAGE_LIMIT,
    REFERENCE_AS_OF_DATE,
    ACHI_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    AAL_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    AMBIGUITY_QUARANTINE_ALLOWED_DIFFERING_FIELDS,
    AMBIGUITY_QUARANTINE_POLICY,
    AMBIGUITY_QUARANTINE_REASON,
    CORRECTION_SELECTION_POLICY,
    CONFLICT_ALLOWED_DIFFERING_FIELDS,
    EXPLICIT_CORRECTION_ALLOWED_DIFFERING_FIELDS,
    CONFLICT_RESOLUTION_POLICY,
    CONFLICT_RESOLUTION_REPEAT_COUNT,
    KNOWN_CONFLICTS,
    KNOWN_QUARANTINES,
    SOURCE_ROLE,
    STORAGE_CATEGORY,
    ReferencePartition,
    reference_partitions,
)
from packages.data.research_storage import (
    assert_category_acquisition_allowed,
    inspect_research_storage,
)


class HistoricalOptionReferenceV6Error(RuntimeError):
    pass


class HistoricalOptionReferenceV6HistoricalTargetCardinalityError(
    HistoricalOptionReferenceV6Error
):
    def __init__(
        self,
        *,
        ticker: str,
        as_of: date,
        target_count: int,
        request_ids: list[str],
    ) -> None:
        self.ticker = ticker
        self.as_of = as_of
        self.target_count = target_count
        self.request_ids = list(request_ids)
        super().__init__(
            f"{ticker}: pre-expiration structural-list expected exactly 1 "
            f"target row, received {target_count}"
        )


class HistoricalOptionReferenceV6Quarantine(RuntimeError):
    def __init__(self, record: dict[str, object]) -> None:
        self.record = dict(record)
        super().__init__(
            f"{record.get('ticker')}: quarantined unresolved option-reference ambiguity"
        )


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
        raise HistoricalOptionReferenceV6Error(
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
                "User-Agent": "ATLAS-historical-option-reference-v5/1",
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
                raise HistoricalOptionReferenceV6Error(
                    "Massive option-reference response root is not an object"
                )
            return payload
        except urllib.error.HTTPError as exc:
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            if not retryable or attempt >= int(cfg.max_attempts):
                body = exc.read().decode("utf-8", errors="replace")[:500]
                raise HistoricalOptionReferenceV6Error(
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
                raise HistoricalOptionReferenceV6Error(
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
        raise HistoricalOptionReferenceV6Error(
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
        raise HistoricalOptionReferenceV6Error(
            "active hard-end boundary probe returned malformed results"
        )
    if results:
        sample = results[0]
        raise HistoricalOptionReferenceV6Error(
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
        raise HistoricalOptionReferenceV6Error(
            f"{partition_key}: {ticker}: invalid {field}={value!r}"
        ) from exc
    if not decimal_value.is_finite():
        raise HistoricalOptionReferenceV6Error(
            f"{partition_key}: {ticker}: non-finite {field}={value!r}"
        )
    return str(value)


def _correction_rank(item: dict[str, Any]) -> int:
    value = item.get("correction")
    if value in (None, ""):
        return -1
    if isinstance(value, bool):
        raise HistoricalOptionReferenceV6Error(
            f"invalid boolean correction value: {value!r}"
        )
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HistoricalOptionReferenceV6Error(
            f"invalid correction value: {value!r}"
        ) from exc
    if not decimal_value.is_finite():
        raise HistoricalOptionReferenceV6Error(
            f"invalid correction value: {value!r}"
        )
    if decimal_value != decimal_value.to_integral_value():
        raise HistoricalOptionReferenceV6Error(
            f"non-integral correction value: {value!r}"
        )
    numeric = int(decimal_value)
    if numeric < 0:
        raise HistoricalOptionReferenceV6Error(
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
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: option-reference row is missing required fields {missing}"
        )

    ticker = str(item["ticker"]).strip()
    underlying = str(item["underlying_ticker"]).strip()
    if not ticker or not underlying:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: option-reference row has blank identity"
        )

    try:
        expiration = date.fromisoformat(str(item["expiration_date"]))
    except ValueError as exc:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: invalid expiration_date="
            f"{item.get('expiration_date')!r}"
        ) from exc
    if not (partition.expiration_gte <= expiration < partition.expiration_lt):
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: expiration {expiration} escaped "
            f"[{partition.expiration_gte}, {partition.expiration_lt})"
        )

    contract_type = str(item["contract_type"]).strip().lower()
    if contract_type not in {"call", "put", "other"}:
        raise HistoricalOptionReferenceV6Error(
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


def _overview_url(
    settings: AtlasSettings,
    *,
    ticker: str,
    as_of: date,
) -> str:
    encoded = urllib.parse.quote(ticker, safe="")
    query = urllib.parse.urlencode({"as_of": as_of.isoformat()})
    return _endpoint(settings).rstrip("/") + "/" + encoded + "?" + query


def _extract_overview_row(
    payload: dict[str, Any],
    *,
    ticker: str,
) -> dict[str, Any]:
    provider_status = payload.get("status")
    if provider_status not in (None, "OK"):
        raise HistoricalOptionReferenceV6Error(
            f"{ticker}: historical Contract Overview status={provider_status!r}"
        )
    row = payload.get("results")
    if row is None:
        row = payload.get("result")
    if isinstance(row, list):
        if len(row) != 1 or not isinstance(row[0], dict):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: historical Contract Overview did not return one row"
            )
        row = row[0]
    if not isinstance(row, dict):
        raise HistoricalOptionReferenceV6Error(
            f"{ticker}: historical Contract Overview did not return an object"
        )
    result = dict(row)
    if str(result.get("ticker") or "") != ticker:
        raise HistoricalOptionReferenceV6Error(
            f"{ticker}: historical Contract Overview ticker mismatch"
        )
    return result


def _differing_fields(rows: list[dict[str, Any]]) -> set[str]:
    fields = {key for row in rows for key in row}
    differing: set[str] = set()
    for field in fields:
        values = {_stable_json(row.get(field)) for row in rows}
        if len(values) > 1:
            differing.add(field)
    return differing


def _historical_list_url(
    settings: AtlasSettings,
    *,
    contract_type: str,
    expiration: date,
    strike_price: str,
    as_of: date,
) -> str:
    query = urllib.parse.urlencode(
        {
            "contract_type": contract_type,
            "expiration_date": expiration.isoformat(),
            "strike_price": strike_price,
            "as_of": as_of.isoformat(),
            "expired": "false",
            "order": "asc",
            "sort": "ticker",
            "limit": PAGE_LIMIT,
        }
    )
    return _endpoint(settings) + "?" + query


def _historical_target_row_once(
    settings: AtlasSettings,
    *,
    api_key: str,
    ticker: str,
    contract_type: str,
    expiration: date,
    strike_price: str,
    as_of: date,
) -> tuple[dict[str, Any], list[str]]:
    next_url = _historical_list_url(
        settings,
        contract_type=contract_type,
        expiration=expiration,
        strike_price=strike_price,
        as_of=as_of,
    )
    seen: set[str] = set()
    target_rows: list[dict[str, Any]] = []
    request_ids: list[str] = []
    page_count = 0

    while next_url:
        if next_url in seen:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: historical structural-list pagination loop"
            )
        seen.add(next_url)
        page_count += 1
        if page_count > _MAX_PAGES_PER_PARTITION:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: historical structural-list exceeded page guard"
            )
        payload = _request_json(settings, url=next_url, api_key=api_key)
        request_ids.append(str(payload.get("request_id") or ""))
        rows = payload.get("results") or []
        if not isinstance(rows, list) or any(
            not isinstance(item, dict) for item in rows
        ):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: historical structural-list returned malformed rows"
            )
        target_rows.extend(
            dict(item)
            for item in rows
            if str(item.get("ticker") or "") == ticker
        )
        value = payload.get("next_url")
        if value:
            if not isinstance(value, str):
                raise HistoricalOptionReferenceV6Error(
                    f"{ticker}: historical structural-list next_url was not a string"
                )
            _validate_next_url(settings, value)
            next_url = value
        else:
            next_url = ""

    if len(target_rows) != 1:
        raise HistoricalOptionReferenceV6HistoricalTargetCardinalityError(
            ticker=ticker,
            as_of=as_of,
            target_count=len(target_rows),
            request_ids=request_ids,
        )
    return target_rows[0], request_ids


def _resolve_narrow_unversioned_conflict(
    highest_rows: list[dict[str, Any]],
    *,
    partition: ReferencePartition,
    settings: AtlasSettings,
    api_key: str,
) -> tuple[dict[str, Any], dict[str, object]]:
    if partition.state != "EXPIRED":
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: same-rank conflict fallback is expired-contract only"
        )
    if not highest_rows:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: empty same-rank conflict group"
        )
    ticker = str(highest_rows[0].get("ticker") or "")
    if any(_correction_rank(row) != -1 for row in highest_rows):
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: conflict fallback requires missing correction"
        )

    differing = _differing_fields(highest_rows)
    allowed = set(CONFLICT_ALLOWED_DIFFERING_FIELDS)
    if not differing or not differing.issubset(allowed):
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: same-rank conflict fields "
            f"{sorted(differing)} exceed frozen V6 allowance {sorted(allowed)}"
        )

    structural = [
        _validate_structural_record(row, partition=partition)
        for row in highest_rows
    ]
    expirations = {item[1] for item in structural}
    contract_types = {item[2] for item in structural}
    strike_prices = {item[3] for item in structural}
    if len(expirations) != 1 or len(contract_types) != 1 or len(strike_prices) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: conflict rows disagree on immutable economics"
        )
    expiration = next(iter(expirations))
    contract_type = next(iter(contract_types))
    strike_price = next(iter(strike_prices))
    historical_as_of = expiration - timedelta(days=1)

    historical_rows: list[dict[str, Any]] = []
    historical_row_hashes: list[str] = []
    historical_list_request_ids: list[str] = []
    for _ in range(CONFLICT_RESOLUTION_REPEAT_COUNT):
        row, request_ids = _historical_target_row_once(
            settings,
            api_key=api_key,
            ticker=ticker,
            contract_type=contract_type,
            expiration=expiration,
            strike_price=strike_price,
            as_of=historical_as_of,
        )
        historical_rows.append(row)
        historical_row_hashes.append(_stable_hash(row))
        historical_list_request_ids.extend(request_ids)

    if len(set(historical_row_hashes)) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: pre-expiration structural-list target "
            f"row was not stable across {CONFLICT_RESOLUTION_REPEAT_COUNT} repeats"
        )

    overview_rows: list[dict[str, Any]] = []
    overview_hashes: list[str] = []
    overview_request_ids: list[str] = []
    url = _overview_url(settings, ticker=ticker, as_of=historical_as_of)
    for _ in range(CONFLICT_RESOLUTION_REPEAT_COUNT):
        payload = _request_json(settings, url=url, api_key=api_key)
        row = _extract_overview_row(payload, ticker=ticker)
        overview_rows.append(row)
        overview_hashes.append(_stable_hash(row))
        overview_request_ids.append(str(payload.get("request_id") or ""))

    if len(set(overview_hashes)) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: historical Contract Overview was not stable "
            f"across {CONFLICT_RESOLUTION_REPEAT_COUNT} repeats"
        )
    if historical_row_hashes[0] != overview_hashes[0]:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: pre-expiration structural-list and "
            "Contract Overview payloads did not match"
        )

    historical_json = _stable_json(historical_rows[0])
    matching_current = [
        row for row in highest_rows if _stable_json(row) == historical_json
    ]
    if len(matching_current) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: stable pre-expiration provider payload "
            f"matched {len(matching_current)} current conflicting rows instead of 1"
        )

    selected = matching_current[0]
    diagnostic_fingerprints: list[str] = []
    if "primary_exchange" in differing:
        diagnostic_fingerprints.append(AAL_DIAGNOSTIC_EVIDENCE_FINGERPRINT)
    if "underlying_ticker" in differing:
        diagnostic_fingerprints.append(ACHI_DIAGNOSTIC_EVIDENCE_FINGERPRINT)

    lineage = {
        "policy": CONFLICT_RESOLUTION_POLICY,
        "diagnostic_evidence_fingerprints": sorted(diagnostic_fingerprints),
        "historical_as_of": historical_as_of.isoformat(),
        "historical_list_sha256": historical_row_hashes[0],
        "overview_sha256": overview_hashes[0],
        "repeat_count": CONFLICT_RESOLUTION_REPEAT_COUNT,
        "historical_list_request_ids": historical_list_request_ids,
        "overview_request_ids": overview_request_ids,
        "differing_fields": sorted(differing),
        "conflicting_payload_hashes": sorted(
            {_stable_hash(row) for row in highest_rows}
        ),
    }
    return selected, lineage

def _resolve_narrow_explicit_correction_conflict(
    highest_rows: list[dict[str, Any]],
    *,
    partition: ReferencePartition,
    settings: AtlasSettings,
    api_key: str,
    highest_rank: int,
) -> tuple[dict[str, Any], dict[str, object]]:
    if partition.state != "EXPIRED":
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: explicit-correction conflict fallback is expired-contract only"
        )
    if not highest_rows:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: empty explicit-correction conflict group"
        )
    ticker = str(highest_rows[0].get("ticker") or "")
    ranks = {_correction_rank(row) for row in highest_rows}
    if highest_rank < 0 or ranks != {highest_rank}:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: explicit-correction fallback requires "
            f"one shared nonnegative highest correction rank; observed={sorted(ranks)}"
        )

    differing = _differing_fields(highest_rows)
    allowed = set(EXPLICIT_CORRECTION_ALLOWED_DIFFERING_FIELDS)
    if not differing or not differing.issubset(allowed):
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: explicit same-rank conflict fields "
            f"{sorted(differing)} exceed frozen V6 allowance {sorted(allowed)}"
        )

    structural = [
        _validate_structural_record(row, partition=partition)
        for row in highest_rows
    ]
    expirations = {item[1] for item in structural}
    contract_types = {item[2] for item in structural}
    strike_prices = {item[3] for item in structural}
    shares = {item[4] for item in structural}
    if (
        len(expirations) != 1
        or len(contract_types) != 1
        or len(strike_prices) != 1
        or len(shares) != 1
    ):
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: explicit conflict rows disagree on immutable economics"
        )

    expiration = next(iter(expirations))
    contract_type = next(iter(contract_types))
    strike_price = next(iter(strike_prices))
    historical_as_of = expiration - timedelta(days=1)

    historical_rows: list[dict[str, Any]] = []
    historical_row_hashes: list[str] = []
    historical_list_request_ids: list[str] = []
    for _ in range(CONFLICT_RESOLUTION_REPEAT_COUNT):
        row, request_ids = _historical_target_row_once(
            settings,
            api_key=api_key,
            ticker=ticker,
            contract_type=contract_type,
            expiration=expiration,
            strike_price=strike_price,
            as_of=historical_as_of,
        )
        historical_rows.append(row)
        historical_row_hashes.append(_stable_hash(row))
        historical_list_request_ids.extend(request_ids)

    if len(set(historical_row_hashes)) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: pre-expiration structural-list target "
            f"row was not stable across {CONFLICT_RESOLUTION_REPEAT_COUNT} repeats"
        )

    historical_rank = _correction_rank(historical_rows[0])
    if historical_rank != highest_rank:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: pre-expiration correction rank "
            f"{historical_rank} did not equal current highest rank {highest_rank}"
        )

    overview_rows: list[dict[str, Any]] = []
    overview_hashes: list[str] = []
    overview_request_ids: list[str] = []
    url = _overview_url(settings, ticker=ticker, as_of=historical_as_of)
    for _ in range(CONFLICT_RESOLUTION_REPEAT_COUNT):
        payload = _request_json(settings, url=url, api_key=api_key)
        row = _extract_overview_row(payload, ticker=ticker)
        overview_rows.append(row)
        overview_hashes.append(_stable_hash(row))
        overview_request_ids.append(str(payload.get("request_id") or ""))

    if len(set(overview_hashes)) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: historical Contract Overview was not stable "
            f"across {CONFLICT_RESOLUTION_REPEAT_COUNT} repeats"
        )
    if historical_row_hashes[0] != overview_hashes[0]:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: pre-expiration structural-list and "
            "Contract Overview payloads did not match"
        )

    historical_json = _stable_json(historical_rows[0])
    matching_current = [
        row for row in highest_rows if _stable_json(row) == historical_json
    ]
    if len(matching_current) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: {ticker}: stable pre-expiration provider payload "
            f"matched {len(matching_current)} current conflicting rows instead of 1"
        )

    lineage = {
        "policy": CONFLICT_RESOLUTION_POLICY,
        "diagnostic_evidence_fingerprints": [
            ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT
        ],
        "historical_as_of": historical_as_of.isoformat(),
        "historical_list_sha256": historical_row_hashes[0],
        "overview_sha256": overview_hashes[0],
        "repeat_count": CONFLICT_RESOLUTION_REPEAT_COUNT,
        "historical_list_request_ids": historical_list_request_ids,
        "overview_request_ids": overview_request_ids,
        "differing_fields": sorted(differing),
        "conflicting_payload_hashes": sorted(
            {_stable_hash(row) for row in highest_rows}
        ),
        "selected_correction_rank": highest_rank,
        "resolution_branch": "EXPLICIT_CORRECTION_DELIVERABLE",
    }
    return matching_current[0], lineage


def _confirm_unresolved_primary_exchange_quarantine(
    highest_rows: list[dict[str, Any]],
    *,
    partition: ReferencePartition,
    settings: AtlasSettings,
    api_key: str,
    first_gap: HistoricalOptionReferenceV6HistoricalTargetCardinalityError,
) -> dict[str, object]:
    if partition.state != "EXPIRED":
        raise first_gap
    if first_gap.target_count != 0:
        raise first_gap
    if not highest_rows:
        raise first_gap

    ticker = str(highest_rows[0].get("ticker") or "")
    if ticker != first_gap.ticker:
        raise first_gap
    if any(_correction_rank(row) != -1 for row in highest_rows):
        raise first_gap

    differing = _differing_fields(highest_rows)
    allowed = set(AMBIGUITY_QUARANTINE_ALLOWED_DIFFERING_FIELDS)
    if differing != allowed:
        raise first_gap

    underlying_tickers = sorted(
        {str(row.get("underlying_ticker") or "") for row in highest_rows}
    )
    if len(underlying_tickers) != 1 or not underlying_tickers[0]:
        raise first_gap

    structural = [
        _validate_structural_record(row, partition=partition)
        for row in highest_rows
    ]
    expirations = {item[1] for item in structural}
    contract_types = {item[2] for item in structural}
    strike_prices = {item[3] for item in structural}
    shares = {item[4] for item in structural}
    if (
        len(expirations) != 1
        or len(contract_types) != 1
        or len(strike_prices) != 1
        or len(shares) != 1
    ):
        raise first_gap

    expiration = next(iter(expirations))
    contract_type = next(iter(contract_types))
    strike_price = next(iter(strike_prices))
    historical_as_of = expiration - timedelta(days=1)
    if first_gap.as_of != historical_as_of:
        raise first_gap

    repeat_request_ids = list(first_gap.request_ids)
    try:
        _historical_target_row_once(
            settings,
            api_key=api_key,
            ticker=ticker,
            contract_type=contract_type,
            expiration=expiration,
            strike_price=strike_price,
            as_of=historical_as_of,
        )
    except HistoricalOptionReferenceV6HistoricalTargetCardinalityError as second_gap:
        if (
            second_gap.target_count != 0
            or second_gap.ticker != ticker
            or second_gap.as_of != historical_as_of
        ):
            raise first_gap
        repeat_request_ids.extend(second_gap.request_ids)
    else:
        raise first_gap

    current_hashes = sorted({_stable_hash(row) for row in highest_rows})
    current_exchanges = sorted(
        {str(row.get("primary_exchange") or "") for row in highest_rows}
    )
    record: dict[str, object] = {
        "ticker": ticker,
        "partition": partition.key,
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "reference_state": partition.state,
        "reason": AMBIGUITY_QUARANTINE_REASON,
        "policy": AMBIGUITY_QUARANTINE_POLICY,
        "diagnostic_evidence_fingerprints": (
            [ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT]
            if ticker == "O:ACIW140816C00040000"
            else []
        ),
        "current_raw_row_count": len(highest_rows),
        "current_payload_hashes": current_hashes,
        "current_underlying_tickers": underlying_tickers,
        "current_primary_exchanges": current_exchanges,
        "current_correction_ranks": sorted(
            {_correction_rank(row) for row in highest_rows}
        ),
        "differing_fields": sorted(differing),
        "historical_as_of": historical_as_of.isoformat(),
        "historical_target_row_count": 0,
        "historical_zero_target_repeat_count": 2,
        "historical_list_request_ids": repeat_request_ids,
        "raw_rows": highest_rows,
        "selected_provider_row": None,
        "excluded_from_normalized_reference": True,
        "historical_candidate_availability_authority": False,
        "historical_dynamic_deliverable_authority": False,
        "historical_market_price_authority": False,
    }
    record["quarantine_record_fingerprint"] = _stable_hash(record)
    return record


def _resolve_ticker_versions(
    versions: list[dict[str, Any]],
    *,
    partition: ReferencePartition,
    settings: AtlasSettings | None = None,
    api_key: str | None = None,
) -> tuple[dict[str, object], int]:
    if not versions:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: empty ticker-version group"
        )

    validated = [
        (_validate_structural_record(item, partition=partition), item)
        for item in versions
    ]
    tickers = {entry[0][0] for entry in validated}
    if len(tickers) != 1:
        raise HistoricalOptionReferenceV6Error(
            f"{partition.key}: mixed ticker identities in version group: {sorted(tickers)}"
        )
    ticker = next(iter(tickers))

    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for _structural, item in validated:
        ranked.append((_correction_rank(item), _stable_json(item), item))
    highest_rank = max(item[0] for item in ranked)
    highest = [item for item in ranked if item[0] == highest_rank]
    highest_payloads = {item[1] for item in highest}
    conflict_lineage: dict[str, object] | None = None
    if len(highest_payloads) != 1:
        if settings is None or api_key is None:
            raise HistoricalOptionReferenceV6Error(
                f"{partition.key}: {ticker}: conflicting provider rows share "
                f"highest correction rank {highest_rank}; V6 resolver context missing"
            )
        if highest_rank == -1:
            try:
                selected, conflict_lineage = _resolve_narrow_unversioned_conflict(
                    [item[2] for item in highest],
                    partition=partition,
                    settings=settings,
                    api_key=api_key,
                )
            except HistoricalOptionReferenceV6HistoricalTargetCardinalityError as gap:
                quarantine_record = _confirm_unresolved_primary_exchange_quarantine(
                    [item[2] for item in highest],
                    partition=partition,
                    settings=settings,
                    api_key=api_key,
                    first_gap=gap,
                )
                raise HistoricalOptionReferenceV6Quarantine(quarantine_record) from gap
        else:
            selected, conflict_lineage = _resolve_narrow_explicit_correction_conflict(
                [item[2] for item in highest],
                partition=partition,
                settings=settings,
                api_key=api_key,
                highest_rank=highest_rank,
            )
    else:
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
        "historically_resolved_conflict": conflict_lineage is not None,
        "conflict_resolution_policy": (
            str(conflict_lineage["policy"])
            if conflict_lineage is not None
            else ""
        ),
        "conflict_resolution_as_of_date": (
            str(conflict_lineage["historical_as_of"])
            if conflict_lineage is not None
            else ""
        ),
        "conflict_resolution_historical_list_sha256": (
            str(conflict_lineage["historical_list_sha256"])
            if conflict_lineage is not None
            else ""
        ),
        "conflict_resolution_overview_sha256": (
            str(conflict_lineage["overview_sha256"])
            if conflict_lineage is not None
            else ""
        ),
        "conflict_resolution_repeat_count": (
            int(conflict_lineage["repeat_count"])
            if conflict_lineage is not None
            else 0
        ),
        "conflict_resolution_differing_fields_json": _stable_json(
            conflict_lineage["differing_fields"]
            if conflict_lineage is not None
            else []
        ),
        "conflict_resolution_conflicting_hashes_json": _stable_json(
            conflict_lineage["conflicting_payload_hashes"]
            if conflict_lineage is not None
            else []
        ),
        "conflict_resolution_historical_list_request_ids_json": _stable_json(
            conflict_lineage["historical_list_request_ids"]
            if conflict_lineage is not None
            else []
        ),
        "conflict_resolution_overview_request_ids_json": _stable_json(
            conflict_lineage["overview_request_ids"]
            if conflict_lineage is not None
            else []
        ),
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
                            AS correction_selection_policy,
                        TRY_CAST(historically_resolved_conflict AS BOOLEAN)
                            AS historically_resolved_conflict,
                        CAST(conflict_resolution_policy AS VARCHAR)
                            AS conflict_resolution_policy,
                        TRY_CAST(conflict_resolution_as_of_date AS DATE)
                            AS conflict_resolution_as_of_date,
                        CAST(conflict_resolution_historical_list_sha256 AS VARCHAR)
                            AS conflict_resolution_historical_list_sha256,
                        CAST(conflict_resolution_overview_sha256 AS VARCHAR)
                            AS conflict_resolution_overview_sha256,
                        TRY_CAST(conflict_resolution_repeat_count AS BIGINT)
                            AS conflict_resolution_repeat_count,
                        CAST(conflict_resolution_differing_fields_json AS VARCHAR)
                            AS conflict_resolution_differing_fields_json,
                        CAST(conflict_resolution_conflicting_hashes_json AS VARCHAR)
                            AS conflict_resolution_conflicting_hashes_json,
                        CAST(conflict_resolution_historical_list_request_ids_json AS VARCHAR)
                            AS conflict_resolution_historical_list_request_ids_json,
                        CAST(conflict_resolution_overview_request_ids_json AS VARCHAR)
                            AS conflict_resolution_overview_request_ids_json
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
                    correction_selection_policy VARCHAR,
                    historically_resolved_conflict BOOLEAN,
                    conflict_resolution_policy VARCHAR,
                    conflict_resolution_as_of_date DATE,
                    conflict_resolution_historical_list_sha256 VARCHAR,
                    conflict_resolution_overview_sha256 VARCHAR,
                    conflict_resolution_repeat_count BIGINT,
                    conflict_resolution_differing_fields_json VARCHAR,
                    conflict_resolution_conflicting_hashes_json VARCHAR,
                    conflict_resolution_historical_list_request_ids_json VARCHAR,
                    conflict_resolution_overview_request_ids_json VARCHAR
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
        Path("massive/historical_option_reference_v6")
        / f"reference_as_of={REFERENCE_AS_OF_DATE.isoformat()}"
        / f"state={partition.state.lower()}"
        / f"expiration_year={expiration_month.year:04d}"
        / f"expiration_month={expiration_month.month:02d}"
    )
    manifest_suffix = (
        Path("massive")
        / "historical_option_reference_v6"
        / f"state={partition.state.lower()}"
        / f"expiration_year={expiration_month.year:04d}"
        / f"expiration_month={expiration_month.month:02d}"
    )
    return {
        "raw": root / options.reference_subdir / suffix / "contracts.jsonl.gz",
        "normalized": root / options.reference_subdir / suffix / "contracts.parquet",
        "quarantine": root / options.reference_subdir / suffix / "quarantine.jsonl",
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
        != HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT
    ):
        return None
    if receipt.get("partition") != partition.key:
        return None
    expected_fingerprint = receipt.get("receipt_fingerprint")
    fingerprint_payload = dict(receipt)
    fingerprint_payload.pop("receipt_fingerprint", None)
    if expected_fingerprint != _stable_hash(fingerprint_payload):
        return None
    for name in ("raw", "normalized", "quarantine"):
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


def _known_conflict_resolution_probes(
    settings: AtlasSettings,
    *,
    api_key: str,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for spec in KNOWN_CONFLICTS:
        ticker = str(spec["ticker"])
        contract_type = str(spec["contract_type"])
        expiration_text = str(spec["expiration_date"])
        strike_price = str(spec["strike_price"])
        query = urllib.parse.urlencode(
            {
                "contract_type": contract_type,
                "expiration_date": expiration_text,
                "strike_price": strike_price,
                "as_of": REFERENCE_AS_OF_DATE.isoformat(),
                "expired": "true",
                "order": "asc",
                "sort": "ticker",
                "limit": PAGE_LIMIT,
            }
        )
        payload = _request_json(
            settings,
            url=_endpoint(settings) + "?" + query,
            api_key=api_key,
        )
        rows = payload.get("results") or []
        if not isinstance(rows, list) or any(
            not isinstance(item, dict) for item in rows
        ):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-conflict preflight returned malformed rows"
            )
        target_rows = [
            dict(item)
            for item in rows
            if str(item.get("ticker") or "") == ticker
        ]
        expected_current = int(spec["expected_current_target_rows"])
        if len(target_rows) != expected_current:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-conflict preflight expected "
                f"{expected_current} current target rows, received {len(target_rows)}"
            )
        differing = sorted(_differing_fields(target_rows))
        expected_fields = sorted(
            str(item) for item in spec["expected_differing_fields"]
        )
        if differing != expected_fields:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-conflict preflight fields {differing} "
                f"did not match frozen {expected_fields}"
            )
        highest_rank = max(_correction_rank(row) for row in target_rows)
        expected_rank = int(spec["expected_highest_correction_rank"])
        if highest_rank != expected_rank:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-conflict preflight highest correction rank "
                f"{highest_rank} did not match frozen {expected_rank}"
            )

        expiration = date.fromisoformat(expiration_text)
        partition = next(
            (
                item
                for item in reference_partitions()
                if item.state == "EXPIRED"
                and item.expiration_gte <= expiration < item.expiration_lt
            ),
            None,
        )
        if partition is None:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-conflict preflight could not resolve partition"
            )
        normalized, _discarded = _resolve_ticker_versions(
            target_rows,
            partition=partition,
            settings=settings,
            api_key=api_key,
        )
        if not bool(normalized["historically_resolved_conflict"]):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-conflict preflight did not exercise V4 resolver"
            )
        results.append(
            {
                "status": "PASS",
                "id": str(spec["id"]),
                "ticker": ticker,
                "partition": partition.key,
                "current_target_rows": len(target_rows),
                "differing_fields": differing,
                "selected_provider_record_sha256": normalized[
                    "provider_record_sha256"
                ],
                "selected_underlying_ticker": normalized["underlying_ticker"],
                "selected_primary_exchange": normalized["primary_exchange"],
                "selected_correction_rank": normalized["selected_correction_rank"],
                "resolution_branch": str(spec["resolution_branch"]),
                "resolution_policy": normalized["conflict_resolution_policy"],
                "resolution_as_of_date": normalized[
                    "conflict_resolution_as_of_date"
                ],
                "resolution_historical_list_sha256": normalized[
                    "conflict_resolution_historical_list_sha256"
                ],
                "resolution_overview_sha256": normalized[
                    "conflict_resolution_overview_sha256"
                ],
                "diagnostic_evidence_fingerprint": str(
                    spec["diagnostic_evidence_fingerprint"]
                ),
            }
        )
    return results


def _known_quarantine_probes(
    settings: AtlasSettings,
    *,
    api_key: str,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for spec in KNOWN_QUARANTINES:
        ticker = str(spec["ticker"])
        expiration_text = str(spec["expiration_date"])
        query = urllib.parse.urlencode(
            {
                "contract_type": str(spec["contract_type"]),
                "expiration_date": expiration_text,
                "strike_price": str(spec["strike_price"]),
                "as_of": REFERENCE_AS_OF_DATE.isoformat(),
                "expired": "true",
                "order": "asc",
                "sort": "ticker",
                "limit": PAGE_LIMIT,
            }
        )
        payload = _request_json(
            settings,
            url=_endpoint(settings) + "?" + query,
            api_key=api_key,
        )
        rows = payload.get("results") or []
        if not isinstance(rows, list) or any(
            not isinstance(item, dict) for item in rows
        ):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-quarantine preflight returned malformed rows"
            )
        target_rows = [
            dict(item)
            for item in rows
            if str(item.get("ticker") or "") == ticker
        ]
        if len(target_rows) != int(spec["expected_current_target_rows"]):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-quarantine preflight current target-row count changed"
            )
        differing = sorted(_differing_fields(target_rows))
        expected_fields = sorted(str(x) for x in spec["expected_differing_fields"])
        if differing != expected_fields:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-quarantine preflight fields {differing} "
                f"did not match frozen {expected_fields}"
            )
        underlyings = sorted(
            {str(row.get("underlying_ticker") or "") for row in target_rows}
        )
        exchanges = sorted(
            {str(row.get("primary_exchange") or "") for row in target_rows}
        )
        if underlyings != sorted(str(x) for x in spec["expected_underlying_tickers"]):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-quarantine underlying set changed: {underlyings}"
            )
        if exchanges != sorted(str(x) for x in spec["expected_primary_exchanges"]):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-quarantine exchange set changed: {exchanges}"
            )
        highest_rank = max(_correction_rank(row) for row in target_rows)
        if highest_rank != int(spec["expected_highest_correction_rank"]):
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-quarantine correction rank changed: {highest_rank}"
            )

        expiration = date.fromisoformat(expiration_text)
        partition = next(
            item
            for item in reference_partitions()
            if item.state == "EXPIRED"
            and item.expiration_gte <= expiration < item.expiration_lt
        )
        try:
            _resolve_ticker_versions(
                target_rows,
                partition=partition,
                settings=settings,
                api_key=api_key,
            )
        except HistoricalOptionReferenceV6Quarantine as quarantine:
            record = quarantine.record
        else:
            raise HistoricalOptionReferenceV6Error(
                f"{ticker}: known-quarantine preflight did not exercise quarantine"
            )

        results.append(
            {
                "status": "PASS",
                "id": str(spec["id"]),
                "ticker": ticker,
                "partition": partition.key,
                "current_target_rows": len(target_rows),
                "differing_fields": differing,
                "current_underlying_tickers": underlyings,
                "current_primary_exchanges": exchanges,
                "selected_provider_row": None,
                "quarantine_reason": record["reason"],
                "quarantine_policy": record["policy"],
                "historical_as_of": record["historical_as_of"],
                "historical_target_row_count": record["historical_target_row_count"],
                "quarantine_record_fingerprint": record[
                    "quarantine_record_fingerprint"
                ],
            }
        )
    return results


def _verified_v5_raw_receipt(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> tuple[dict[str, object], Path] | None:
    receipt = v5_parent._verified_existing_receipt(settings, partition)
    if receipt is None:
        return None
    raw_path = v5_parent._receipt_data_path(settings, receipt.get("raw_path"))
    if raw_path is None or not raw_path.is_file():
        return None
    if receipt.get("raw_sha256") != _sha256_file(raw_path):
        return None
    return receipt, raw_path


def _verified_v4_raw_receipt(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> tuple[dict[str, object], Path] | None:
    receipt = v4_parent._verified_existing_receipt(settings, partition)
    if receipt is None:
        return None
    raw_path = v4_parent._receipt_data_path(settings, receipt.get("raw_path"))
    if raw_path is None or not raw_path.is_file():
        return None
    if receipt.get("raw_sha256") != _sha256_file(raw_path):
        return None
    return receipt, raw_path


def _verified_v3_raw_receipt(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> tuple[dict[str, object], Path] | None:
    receipt = v3_parent._verified_existing_receipt(settings, partition)
    if receipt is None:
        return None
    raw_path = v3_parent._receipt_data_path(settings, receipt.get("raw_path"))
    if raw_path is None or not raw_path.is_file():
        return None
    if receipt.get("raw_sha256") != _sha256_file(raw_path):
        return None
    return receipt, raw_path

def _verified_v2_raw_receipt(
    settings: AtlasSettings,
    partition: ReferencePartition,
) -> tuple[dict[str, object], Path] | None:
    receipt = v2_parent._verified_existing_receipt(settings, partition)
    if receipt is None:
        return None
    raw_path = v2_parent._receipt_data_path(settings, receipt.get("raw_path"))
    if raw_path is None or not raw_path.is_file():
        return None
    if receipt.get("raw_sha256") != _sha256_file(raw_path):
        return None
    return receipt, raw_path


def _check_disk_guard(settings: AtlasSettings, *, partition_key: str) -> None:
    snapshot = inspect_research_storage(settings)
    if snapshot.status == "BLOCKED_MINIMUM_FREE_SPACE":
        raise HistoricalOptionReferenceV6Error(
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
        Path("data/staging/historical_option_reference_v6") / partition.key
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
    historically_resolved_conflicts = 0
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
        nonlocal historically_resolved_conflicts
        nonlocal current_versions
        if not current_versions:
            return
        normalized, discarded = _resolve_ticker_versions(
            current_versions,
            partition=partition,
            settings=settings,
            api_key=api_key,
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
        if bool(normalized["historically_resolved_conflict"]):
            historically_resolved_conflicts += 1
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
                        raise HistoricalOptionReferenceV6Error(
                            f"{partition.key}: pagination exceeded "
                            f"{_MAX_PAGES_PER_PARTITION:,} pages"
                        )
                    _validate_next_url(settings, next_url)
                    page_key = _stable_hash(next_url)
                    if page_key in seen_page_urls:
                        raise HistoricalOptionReferenceV6Error(
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
                        raise HistoricalOptionReferenceV6Error(
                            f"{partition.key}: provider status={provider_status!r}"
                        )
                    results = payload.get("results") or []
                    if not isinstance(results, list) or any(
                        not isinstance(item, dict) for item in results
                    ):
                        raise HistoricalOptionReferenceV6Error(
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
                            raise HistoricalOptionReferenceV6Error(
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
                        raise HistoricalOptionReferenceV6Error(
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
            raise HistoricalOptionReferenceV6Error(
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
            "contract": HISTORICAL_OPTION_REFERENCE_V6_CONTRACT,
            "contract_fingerprint": (
                HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT
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
            "historically_resolved_conflicts": historically_resolved_conflicts,
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
                HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT
            ),
            "raw_reused_from_parent": False,
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


def _rebuild_partition_from_parent_raw(
    settings: AtlasSettings,
    partition: ReferencePartition,
    *,
    parent_receipt: dict[str, object],
    raw_path: Path,
    parent_contract_fingerprint: str,
    api_key: str,
    persistence_lock: threading.Lock,
) -> dict[str, object]:
    paths = _partition_paths(settings, partition)
    paths["normalized"].parent.mkdir(parents=True, exist_ok=True)
    paths["receipt"].parent.mkdir(parents=True, exist_ok=True)

    staging = settings.resolved_path(
        Path("data/staging/historical_option_reference_v6_parent_reuse")
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
    historically_resolved_conflicts = 0
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
        nonlocal historically_resolved_conflicts
        nonlocal current_versions
        if not current_versions:
            return
        normalized, discarded = _resolve_ticker_versions(
            current_versions,
            partition=partition,
            settings=settings,
            api_key=api_key,
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
        if bool(normalized["historically_resolved_conflict"]):
            historically_resolved_conflicts += 1
        current_versions = []

    try:
        with gzip.open(
            raw_path,
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
                    raise HistoricalOptionReferenceV6Error(
                        f"{partition.key}: invalid parent raw JSONL at line {line_number}"
                    ) from exc
                if not isinstance(raw_item, dict):
                    raise HistoricalOptionReferenceV6Error(
                        f"{partition.key}: parent raw line {line_number} is not an object"
                    )
                item = dict(raw_item)
                ticker, *_rest = _validate_structural_record(
                    item,
                    partition=partition,
                )
                if last_ticker is not None and ticker < last_ticker:
                    raise HistoricalOptionReferenceV6Error(
                        f"{partition.key}: verified parent raw ticker order regressed "
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

        expected_raw_records = int(parent_receipt["raw_provider_records"])
        if raw_provider_records != expected_raw_records:
            raise HistoricalOptionReferenceV6Error(
                f"{partition.key}: verified parent raw row count changed: "
                f"{raw_provider_records} != {expected_raw_records}"
            )
        if raw_provider_records != normalized_unique_contracts + duplicate_version_rows:
            raise HistoricalOptionReferenceV6Error(
                f"{partition.key}: parent raw/version reconciliation failed: "
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

        raw_path = raw_path
        receipt: dict[str, object] = {
            "status": "COMPLETE",
            "contract": HISTORICAL_OPTION_REFERENCE_V6_CONTRACT,
            "contract_fingerprint": (
                HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT
            ),
            "provider": "massive",
            "partition": partition.key,
            "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
            "reference_state": partition.state,
            "expiration_gte": partition.expiration_gte.isoformat(),
            "expiration_lt": partition.expiration_lt.isoformat(),
            "expired_query_value": partition.expired,
            "page_limit": PAGE_LIMIT,
            "page_count": int(parent_receipt.get("page_count", 0)),
            "request_id_count": int(parent_receipt.get("request_id_count", 0)),
            "raw_provider_records": raw_provider_records,
            "normalized_unique_contracts": normalized_unique_contracts,
            "duplicate_version_rows": duplicate_version_rows,
            "tickers_with_multiple_versions": tickers_with_multiple_versions,
            "exact_duplicate_rows": exact_duplicate_rows,
            "corrected_selected_contracts": corrected_selected_contracts,
            "historically_resolved_conflicts": historically_resolved_conflicts,
            "raw_version_reconciliation": (
                raw_provider_records
                == normalized_unique_contracts + duplicate_version_rows
            ),
            "correction_selection_policy": CORRECTION_SELECTION_POLICY,
            "first_ticker": first_ticker,
            "last_ticker": last_ticker,
            "raw_path": _relative(settings, raw_path),
            "normalized_path": _relative(settings, paths["normalized"]),
            "raw_origin_contract_fingerprint": str(
                parent_receipt.get("raw_origin_contract_fingerprint")
                or parent_contract_fingerprint
            ),
            "raw_parent_contract_fingerprint": parent_contract_fingerprint,
            "raw_parent_receipt_fingerprint": parent_receipt["receipt_fingerprint"],
            "raw_reused_from_parent": True,
            "raw_bytes": int(raw_path.stat().st_size),
            "normalized_bytes": int(paths["normalized"].stat().st_size),
            "raw_sha256": _sha256_file(raw_path),
            "normalized_sha256": _sha256_file(paths["normalized"]),
            "source_role": SOURCE_ROLE,
            "historical_candidate_availability_authority": False,
            "historical_dynamic_deliverable_authority": False,
            "historical_market_price_authority": False,
        }
        if receipt["raw_sha256"] != parent_receipt.get("raw_sha256"):
            raise HistoricalOptionReferenceV6Error(
                f"{partition.key}: parent raw hash changed during local V6 rebuild"
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


def run_historical_option_reference_v6_acquisition(
    settings: AtlasSettings,
    *,
    workers: int = 5,
) -> dict[str, object]:
    if workers < 1:
        raise ValueError("workers must be at least 1")

    api_key = _resolve_massive_api_key(settings)
    boundary = _boundary_probe(settings, api_key=api_key)
    known_conflict_probes = _known_conflict_resolution_probes(
        settings,
        api_key=api_key,
    )
    partitions = reference_partitions()
    persistence_lock = threading.Lock()

    reused_v6: list[dict[str, object]] = []
    rebuild_from_v4: list[tuple[ReferencePartition, dict[str, object], Path]] = []
    rebuild_from_v3: list[tuple[ReferencePartition, dict[str, object], Path]] = []
    rebuild_from_v2: list[tuple[ReferencePartition, dict[str, object], Path]] = []
    rebuild_from_v1: list[tuple[ReferencePartition, dict[str, object]]] = []
    provider_pending: list[ReferencePartition] = []

    for partition in partitions:
        receipt = _verified_existing_receipt(settings, partition)
        if receipt is not None:
            reused_v6.append(receipt)
            continue

        v4_source = _verified_v4_raw_receipt(settings, partition)
        if v4_source is not None:
            v4_receipt, raw_path = v4_source
            rebuild_from_v4.append((partition, v4_receipt, raw_path))
            continue

        v3_source = _verified_v3_raw_receipt(settings, partition)
        if v3_source is not None:
            v3_receipt, raw_path = v3_source
            rebuild_from_v3.append((partition, v3_receipt, raw_path))
            continue

        v2_source = _verified_v2_raw_receipt(settings, partition)
        if v2_source is not None:
            v2_receipt, raw_path = v2_source
            rebuild_from_v2.append((partition, v2_receipt, raw_path))
            continue

        v1_receipt = _verified_v1_raw_receipt(settings, partition)
        if v1_receipt is not None:
            rebuild_from_v1.append((partition, v1_receipt))
        else:
            provider_pending.append(partition)

    print(
        "historical option reference v6: "
        f"{len(partitions)} monthly partitions / "
        f"{len(reused_v6)} verified V6 reusable / "
        f"{len(rebuild_from_v4)} verified V4 raw reusable / "
        f"{len(rebuild_from_v3)} verified V3 raw reusable / "
        f"{len(rebuild_from_v2)} verified V2 raw reusable / "
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
    for probe in known_conflict_probes:
        print(
            "  known conflict resolution probe: PASS / "
            f"{probe['id']} / {probe['ticker']} -> "
            f"underlying={probe['selected_underlying_ticker']} "
            f"exchange={probe['selected_primary_exchange']} / "
            f"as_of={probe['resolution_as_of_date']}",
            flush=True,
        )

    completed: list[dict[str, object]] = list(reused_v6)

    def rebuild_parent_batch(
        items,
        *,
        label: str,
        parent_contract_fingerprint: str,
    ) -> list[dict[str, object]]:
        def task(item):
            partition, parent_receipt, raw_path = item
            return _rebuild_partition_from_parent_raw(
                settings,
                partition,
                parent_receipt=parent_receipt,
                raw_path=raw_path,
                parent_contract_fingerprint=parent_contract_fingerprint,
                api_key=api_key,
                persistence_lock=persistence_lock,
            )

        def progress(item, receipt, done):
            partition, _parent_receipt, _raw_path = item
            storage = inspect_research_storage(settings)
            print(
                f"  {done}/{len(items)} rebuilt {partition.key} "
                f"from verified {label} raw: "
                f"{int(receipt['normalized_unique_contracts']):,} contracts / "
                f"resolved={int(receipt['historically_resolved_conflicts']):,} / "
                f"reference={storage.category_usage_gib.get(STORAGE_CATEGORY, 0.0):.3f} GiB / "
                f"free={storage.disk_free_gib:.2f} GiB",
                flush=True,
            )

        return _run_bounded(
            items,
            workers=workers,
            task=task,
            on_complete=progress,
        )

    if rebuild_from_v4:
        completed.extend(
            rebuild_parent_batch(
                rebuild_from_v4,
                label="V4",
                parent_contract_fingerprint=(
                    HISTORICAL_OPTION_REFERENCE_V4_CONTRACT_FINGERPRINT
                ),
            )
        )

    if rebuild_from_v3:
        completed.extend(
            rebuild_parent_batch(
                rebuild_from_v3,
                label="V3",
                parent_contract_fingerprint=(
                    HISTORICAL_OPTION_REFERENCE_V3_CONTRACT_FINGERPRINT
                ),
            )
        )

    if rebuild_from_v2:
        completed.extend(
            rebuild_parent_batch(
                rebuild_from_v2,
                label="V2",
                parent_contract_fingerprint=(
                    HISTORICAL_OPTION_REFERENCE_V2_CONTRACT_FINGERPRINT
                ),
            )
        )

    if rebuild_from_v1:
        v1_items = [
            (
                partition,
                v1_receipt,
                _v1_partition_paths(settings, partition)["raw"],
            )
            for partition, v1_receipt in rebuild_from_v1
        ]
        completed.extend(
            rebuild_parent_batch(
                v1_items,
                label="V1",
                parent_contract_fingerprint=(
                    HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT
                ),
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
                f"{int(receipt['tickers_with_multiple_versions']):,} multi-version / "
                f"{int(receipt['historically_resolved_conflicts']):,} resolved / "
                f"{int(receipt['page_count']):,} pages / "
                f"reference={storage.category_usage_gib.get(STORAGE_CATEGORY, 0.0):.3f} GiB / "
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
    if len(completed) != len(partitions):
        raise HistoricalOptionReferenceV6Error(
            f"V6 partition completion mismatch: {len(completed)} != {len(partitions)}"
        )

    total_raw_records = sum(int(item["raw_provider_records"]) for item in completed)
    total_normalized = sum(
        int(item["normalized_unique_contracts"]) for item in completed
    )
    total_raw_bytes = sum(int(item["raw_bytes"]) for item in completed)
    total_normalized_bytes = sum(
        int(item["normalized_bytes"]) for item in completed
    )
    storage = inspect_research_storage(settings)

    corpus_basis = {
        "contract_fingerprint": HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT,
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
        "contract": HISTORICAL_OPTION_REFERENCE_V6_CONTRACT,
        "contract_fingerprint": HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT,
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "active_hard_end_exclusive": ACTIVE_HARD_END_EXCLUSIVE.isoformat(),
        "boundary_probe": boundary,
        "known_conflict_resolution_probes": known_conflict_probes,
        "monthly_partitions": len(completed),
        "reused_verified_partitions": len(reused_v6),
        "rebuilt_from_verified_v4_raw_this_run": len(rebuild_from_v4),
        "rebuilt_from_verified_v3_raw_this_run": len(rebuild_from_v3),
        "rebuilt_from_verified_v2_raw_this_run": len(rebuild_from_v2),
        "rebuilt_from_verified_v1_raw_this_run": len(rebuild_from_v1),
        "provider_acquired_partitions_this_run": len(provider_pending),
        "acquired_partitions_this_run": (
            len(rebuild_from_v4)
            + len(rebuild_from_v3)
            + len(rebuild_from_v2)
            + len(rebuild_from_v1)
            + len(provider_pending)
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
        "historically_resolved_conflicts": sum(
            int(item["historically_resolved_conflicts"]) for item in completed
        ),
        "raw_version_reconciliation": all(
            bool(item["raw_version_reconciliation"]) for item in completed
        ),
        "correction_selection_policy": CORRECTION_SELECTION_POLICY,
        "conflict_resolution_policy": CONFLICT_RESOLUTION_POLICY,
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
        "partition_receipt_fingerprints": corpus_basis[
            "partition_receipt_fingerprints"
        ],
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
        {key: value for key, value in summary.items() if key != "storage_after"}
    )

    summary_path = settings.resolved_path(
        "data/options/manifests/massive/"
        "historical_option_reference_v6_summary.json"
    )
    _atomic_write_json(summary_path, summary)
    return summary
