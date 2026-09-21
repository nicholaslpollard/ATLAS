from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta


HISTORICAL_OPTION_REFERENCE_V1_CONTRACT = "atlas-historical-option-reference-v1"
QUALIFICATION_CONTRACT_FINGERPRINT = (
    "17a3736f9317f7e403ea08c123aac35fabad0a8b2682bca7450373b797e9d260"
)
QUALIFICATION_EVIDENCE_FINGERPRINT = (
    "120f141089420dcfaf86e1d30203a1517f27815bf1e6b3587976ccb74f4025e3"
)
REFERENCE_AS_OF_DATE = date(2026, 9, 19)
HISTORY_START = date(2014, 6, 2)
ACTIVE_HARD_END_EXCLUSIVE = date(2032, 1, 1)
REFERENCE_ENDPOINT = "/v3/reference/options/contracts"
PAGE_LIMIT = 1000
SORT_ORDER = "asc"
SORT_FIELD = "ticker"
STORAGE_CATEGORY = "options_reference"
SOURCE_ROLE = "REFERENCE_IDENTITY_STRUCTURE_ONLY"


@dataclass(frozen=True, slots=True)
class ReferencePartition:
    key: str
    state: str
    expiration_gte: date
    expiration_lt: date
    expired: bool


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def reference_partitions() -> tuple[ReferencePartition, ...]:
    partitions: list[ReferencePartition] = []
    expired_end = REFERENCE_AS_OF_DATE + timedelta(days=1)

    cursor = date(HISTORY_START.year, HISTORY_START.month, 1)
    while cursor < expired_end:
        following = _next_month(cursor)
        lower = max(HISTORY_START, cursor)
        upper = min(expired_end, following)
        if lower < upper:
            partitions.append(
                ReferencePartition(
                    key=f"expired-{cursor.year:04d}-{cursor.month:02d}",
                    state="EXPIRED",
                    expiration_gte=lower,
                    expiration_lt=upper,
                    expired=True,
                )
            )
        cursor = following

    cursor = date(REFERENCE_AS_OF_DATE.year, REFERENCE_AS_OF_DATE.month, 1)
    while cursor < ACTIVE_HARD_END_EXCLUSIVE:
        following = _next_month(cursor)
        lower = max(expired_end, cursor)
        upper = min(ACTIVE_HARD_END_EXCLUSIVE, following)
        if lower < upper:
            partitions.append(
                ReferencePartition(
                    key=f"active-{cursor.year:04d}-{cursor.month:02d}",
                    state="ACTIVE",
                    expiration_gte=lower,
                    expiration_lt=upper,
                    expired=False,
                )
            )
        cursor = following

    return tuple(partitions)


def _stable_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def acquisition_contract_manifest() -> dict[str, object]:
    partitions = [
        {
            "key": item.key,
            "state": item.state,
            "expiration_gte": item.expiration_gte.isoformat(),
            "expiration_lt": item.expiration_lt.isoformat(),
            "expired": item.expired,
        }
        for item in reference_partitions()
    ]
    payload: dict[str, object] = {
        "contract": HISTORICAL_OPTION_REFERENCE_V1_CONTRACT,
        "provider": "massive",
        "qualification_contract_fingerprint": QUALIFICATION_CONTRACT_FINGERPRINT,
        "qualification_evidence_fingerprint": QUALIFICATION_EVIDENCE_FINGERPRINT,
        "reference_as_of_date": REFERENCE_AS_OF_DATE.isoformat(),
        "history_start": HISTORY_START.isoformat(),
        "active_hard_end_exclusive": ACTIVE_HARD_END_EXCLUSIVE.isoformat(),
        "boundary_probe": {
            "expiration_date_gte": ACTIVE_HARD_END_EXCLUSIVE.isoformat(),
            "expired": False,
            "must_return_zero_records": True,
        },
        "endpoint": REFERENCE_ENDPOINT,
        "page_limit": PAGE_LIMIT,
        "sort": SORT_FIELD,
        "order": SORT_ORDER,
        "partitions": partitions,
        "storage_category": STORAGE_CATEGORY,
        "source_role": {
            "reference_identity_and_structure": True,
            "historical_candidate_availability_authority": False,
            "historical_dynamic_deliverable_authority": False,
            "historical_market_price_authority": False,
        },
        "normalization": {
            "identity": "ticker",
            "duplicate_ticker_within_partition": "FAIL",
            "raw_to_normalized_count": "EXACT",
            "provider_fields_preserved": [
                "ticker",
                "underlying_ticker",
                "contract_type",
                "expiration_date",
                "strike_price",
                "exercise_style",
                "shares_per_contract",
                "primary_exchange",
                "cfi",
                "correction",
                "additional_underlyings",
            ],
            "provider_record_sha256": True,
        },
        "authority": {
            "source_acquisition_only": True,
            "predictor_generation": False,
            "strategy_outcome_access": False,
            "paper_authority": False,
            "live_authority": False,
        },
    }
    return payload


HISTORICAL_OPTION_REFERENCE_V1_CONTRACT_FINGERPRINT = _stable_hash(
    acquisition_contract_manifest()
)
