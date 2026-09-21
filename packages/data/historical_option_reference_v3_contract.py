from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from packages.data.historical_option_reference_v2_contract import (
    ACTIVE_HARD_END_EXCLUSIVE,
    HISTORY_START,
    PAGE_LIMIT,
    REFERENCE_AS_OF_DATE,
    REFERENCE_ENDPOINT,
    SORT_FIELD,
    SORT_ORDER,
    SOURCE_ROLE,
    STORAGE_CATEGORY,
    ReferencePartition,
    reference_partitions,
)


HISTORICAL_OPTION_REFERENCE_V3_CONTRACT = "atlas-historical-option-reference-v3"
PARENT_V2_CONTRACT_FINGERPRINT = (
    "6d0af0b58a66b77c445d7e561d759dfd947e348e994045a1f7cfc16aeb9ccb41"
)
CONFLICT_DIAGNOSTIC_CONTRACT_FINGERPRINT = (
    "f544bb78cb6d61cbd69aa5fd266ee20349b3a977b39cb85e79a0a6a5ec0f9678"
)
CONFLICT_DIAGNOSTIC_EVIDENCE_FINGERPRINT = (
    "20f255cab7b19e1d27902a76ed386e94156393c019434fbff4623b6d269a1722"
)
CORRECTION_SELECTION_POLICY = "HIGHEST_EXPLICIT_CORRECTION_THEN_UNCORRECTED"
SAME_CORRECTION_CONFLICT_POLICY = (
    "FAIL_CLOSED_EXCEPT_NARROW_PREEXPIRATION_PRIMARY_EXCHANGE_RESOLUTION"
)
CONFLICT_RESOLUTION_POLICY = (
    "PREEXPIRATION_CONTRACT_OVERVIEW_EXACT_CURRENT_ROW_MATCH"
)
CONFLICT_ALLOWED_DIFFERING_FIELDS = ("primary_exchange",)
CONFLICT_RESOLUTION_REPEAT_COUNT = 2


def _stable_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def preexpiration_as_of(expiration_date):
    return expiration_date - timedelta(days=1)


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
        "contract": HISTORICAL_OPTION_REFERENCE_V3_CONTRACT,
        "parent_v2_contract_fingerprint": PARENT_V2_CONTRACT_FINGERPRINT,
        "v2_observed_failure": {
            "partition": "expired-2014-06",
            "ticker": "O:AAL140621C00020000",
            "failure_class": (
                "CONFLICTING_PROVIDER_ROWS_SHARE_HIGHEST_CORRECTION_RANK_MINUS_ONE"
            ),
        },
        "conflict_diagnostic": {
            "contract_fingerprint": CONFLICT_DIAGNOSTIC_CONTRACT_FINGERPRINT,
            "evidence_fingerprint": CONFLICT_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
            "observed_current_target_rows": 2,
            "observed_current_candidate_rows": 3,
            "observed_historical_target_rows": 1,
            "observed_current_overview_not_found": True,
            "observed_historical_overview_present": True,
            "observed_historical_overview_matches_historical_list": True,
            "observed_conflicting_fields": ["primary_exchange"],
            "all_requests_repeat_stable": True,
        },
        "provider": "massive",
        "provider_documented_semantics_as_of": "2026-09-21",
        "provider_documented_adjusted_contract_semantics": (
            "adjusted series may coexist with standard series and are not merged"
        ),
        "provider_documented_contract_overview_role": (
            "single-contract structural reference endpoint"
        ),
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
            "preserve_all_provider_rows_in_raw": True,
            "duplicate_ticker_resolution": {
                "base_policy": CORRECTION_SELECTION_POLICY,
                "missing_correction_rank": -1,
                "highest_numeric_correction_wins": True,
                "same_highest_correction_identical_payload": "DEDUPE_EXACT",
                "same_highest_correction_conflicting_payload": (
                    SAME_CORRECTION_CONFLICT_POLICY
                ),
            },
            "narrow_conflict_fallback": {
                "eligible_reference_state": "EXPIRED",
                "eligible_highest_correction_rank": -1,
                "allowed_differing_fields": list(
                    CONFLICT_ALLOWED_DIFFERING_FIELDS
                ),
                "as_of": "expiration_date_minus_1_calendar_day",
                "endpoint": REFERENCE_ENDPOINT + "/{options_ticker}",
                "repeat_count": CONFLICT_RESOLUTION_REPEAT_COUNT,
                "required_http_status": 200,
                "repeat_row_hash_must_match": True,
                "overview_ticker_must_match_target": True,
                "overview_payload_must_exactly_match_one_current_conflicting_payload": True,
                "otherwise": "FAIL_CLOSED",
                "policy": CONFLICT_RESOLUTION_POLICY,
            },
            "raw_to_normalized_reconciliation": (
                "RAW_ROWS_EQUAL_NORMALIZED_SELECTED_PLUS_DISCARDED_VERSION_ROWS"
            ),
            "provider_record_sha256": True,
            "record_conflict_resolution_lineage": True,
        },
        "reuse": {
            "verified_v3_receipts": True,
            "verified_v2_raw_lineage": True,
            "verified_v1_raw_lineage": True,
            "local_renormalization_required": True,
            "raw_copy_required": False,
        },
        "efficiency": {
            "bounded_in_flight_partitions": True,
            "default_workers": 4,
            "runtime_worker_count_not_scientific_identity": True,
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


HISTORICAL_OPTION_REFERENCE_V3_CONTRACT_FINGERPRINT = _stable_hash(
    acquisition_contract_manifest()
)
