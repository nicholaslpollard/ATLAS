from __future__ import annotations

import hashlib
import json

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


HISTORICAL_OPTION_REFERENCE_V6_CONTRACT = "atlas-historical-option-reference-v6"
PARENT_V4_CONTRACT_FINGERPRINT = (
    "2ddeb58d5f552ff0edb87a2244f130b813cf49600f5f82b1f50d8e1ee047a57d"
)
AAL_DIAGNOSTIC_CONTRACT_FINGERPRINT = (
    "f544bb78cb6d61cbd69aa5fd266ee20349b3a977b39cb85e79a0a6a5ec0f9678"
)
AAL_DIAGNOSTIC_EVIDENCE_FINGERPRINT = (
    "20f255cab7b19e1d27902a76ed386e94156393c019434fbff4623b6d269a1722"
)
ACHI_DIAGNOSTIC_CONTRACT_FINGERPRINT = (
    "aaf0a8e52fdd56521fe000dc1ead04059115d2639b18eb29fad03b8fe76eaec1"
)
ACHI_DIAGNOSTIC_EVIDENCE_FINGERPRINT = (
    "b655282ff5f1da7bd3c2d7ac931a34b37650ffaa57354c6ac47efdfe746f81d1"
)
ACT2_DIAGNOSTIC_CONTRACT_FINGERPRINT = (
    "54a4436ba1cfee33c6dc3eaabfedd4334c50985d2ee696fab2cc97cfc22620c7"
)
ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT = (
    "283f736a73a742704c7d005b9c0c48aee2b11cf2dd1eccc8bf44fd52a443e1e3"
)
ACIW_DIAGNOSTIC_CONTRACT_FINGERPRINT = (
    "5be1afdd7cb18cf77f6e0c5b76d2329f4afd1d8c07c37b2c051ec003325688b1"
)
ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT = (
    "9c04eba3dd7fce45bbd3e35366e93191acb92493c3e4ed34001e0ad4ef31c777"
)
AMBIGUITY_QUARANTINE_POLICY = (
    "QUARANTINE_UNRESOLVED_EXPIRED_UNVERSIONED_PRIMARY_EXCHANGE_GAP_NO_GUESS"
)
AMBIGUITY_QUARANTINE_REASON = (
    "NO_PROVIDER_NATIVE_PREEXPIRATION_IDENTITY"
)
AMBIGUITY_QUARANTINE_ALLOWED_DIFFERING_FIELDS = (
    "primary_exchange",
)
CORRECTION_SELECTION_POLICY = "HIGHEST_EXPLICIT_CORRECTION_THEN_UNCORRECTED"
SAME_CORRECTION_CONFLICT_POLICY = (
    "FAIL_CLOSED_EXCEPT_FROZEN_PREEXPIRATION_REFERENCE_BRANCHES"
)
CONFLICT_RESOLUTION_POLICY = (
    "PREEXPIRATION_LIST_AND_OVERVIEW_EXACT_CURRENT_ROW_MATCH"
)
CONFLICT_ALLOWED_DIFFERING_FIELDS = (
    "primary_exchange",
    "underlying_ticker",
)
EXPLICIT_CORRECTION_ALLOWED_DIFFERING_FIELDS = (
    "additional_underlyings",
)
CONFLICT_RESOLUTION_REPEAT_COUNT = 2

KNOWN_CONFLICTS: tuple[dict[str, object], ...] = (
    {
        "id": "AAL_PRIMARY_EXCHANGE",
        "ticker": "O:AAL140621C00020000",
        "contract_type": "call",
        "expiration_date": "2014-06-21",
        "strike_price": 20,
        "expected_current_target_rows": 2,
        "expected_historical_target_rows": 1,
        "expected_differing_fields": ["primary_exchange"],
        "expected_highest_correction_rank": -1,
        "resolution_branch": "UNVERSIONED_IDENTITY",
        "diagnostic_contract_fingerprint": AAL_DIAGNOSTIC_CONTRACT_FINGERPRINT,
        "diagnostic_evidence_fingerprint": AAL_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    },
    {
        "id": "ACHI_UNDERLYING_IDENTITY",
        "ticker": "O:ACHI140621C00001000",
        "contract_type": "call",
        "expiration_date": "2014-06-21",
        "strike_price": 1,
        "expected_current_target_rows": 2,
        "expected_historical_target_rows": 1,
        "expected_differing_fields": ["underlying_ticker"],
        "expected_highest_correction_rank": -1,
        "resolution_branch": "UNVERSIONED_IDENTITY",
        "diagnostic_contract_fingerprint": ACHI_DIAGNOSTIC_CONTRACT_FINGERPRINT,
        "diagnostic_evidence_fingerprint": ACHI_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    },
    {
        "id": "ACT2_EXPLICIT_CORRECTION_DELIVERABLE",
        "ticker": "O:ACT2140719C00045000",
        "contract_type": "call",
        "expiration_date": "2014-07-19",
        "strike_price": 45,
        "expected_current_target_rows": 2,
        "expected_historical_target_rows": 1,
        "expected_differing_fields": ["additional_underlyings"],
        "expected_highest_correction_rank": 2,
        "resolution_branch": "EXPLICIT_CORRECTION_DELIVERABLE",
        "diagnostic_contract_fingerprint": ACT2_DIAGNOSTIC_CONTRACT_FINGERPRINT,
        "diagnostic_evidence_fingerprint": ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    },
)


KNOWN_QUARANTINES: tuple[dict[str, object], ...] = (
    {
        "id": "ACIW_UNRESOLVED_PRIMARY_EXCHANGE",
        "ticker": "O:ACIW140816C00040000",
        "contract_type": "call",
        "expiration_date": "2014-08-16",
        "strike_price": 40,
        "expected_current_target_rows": 2,
        "expected_differing_fields": ["primary_exchange"],
        "expected_underlying_tickers": ["ACIW"],
        "expected_primary_exchanges": ["GMNI", "XCBO"],
        "expected_highest_correction_rank": -1,
        "historical_as_of": "2014-08-15",
        "expected_historical_target_rows": 0,
        "resolution_branch": "AMBIGUITY_QUARANTINE",
        "diagnostic_contract_fingerprint": ACIW_DIAGNOSTIC_CONTRACT_FINGERPRINT,
        "diagnostic_evidence_fingerprint": ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
    },
)


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
        "contract": HISTORICAL_OPTION_REFERENCE_V6_CONTRACT,
        "parent_v5_contract_fingerprint": PARENT_V5_CONTRACT_FINGERPRINT,
        "v5_observed_failure": {
            "partition": "expired-2014-07",
            "ticker": "O:ACT2140719C00045000",
            "failure_class": (
                "EXPLICIT_SAME_HIGHEST_CORRECTION_ADDITIONAL_UNDERLYINGS_CONFLICT"
            ),
        },
        "accepted_diagnostics": {
            "aal_primary_exchange": {
                "contract_fingerprint": AAL_DIAGNOSTIC_CONTRACT_FINGERPRINT,
                "evidence_fingerprint": AAL_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
                "current_target_rows": 2,
                "historical_target_rows": 1,
                "current_overview_not_found": True,
                "historical_overview_present": True,
                "historical_overview_matches_historical_list": True,
                "historical_overview_matches_exactly_one_current_row": True,
                "differing_fields": ["primary_exchange"],
                "highest_correction_rank": -1,
                "repeat_stable": True,
            },
            "achi_underlying_identity": {
                "contract_fingerprint": ACHI_DIAGNOSTIC_CONTRACT_FINGERPRINT,
                "evidence_fingerprint": ACHI_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
                "current_target_rows": 2,
                "historical_target_rows": 1,
                "current_underlying_tickers": ["ACHI", "AH"],
                "historical_underlying_tickers": ["ACHI"],
                "current_overview_not_found": True,
                "historical_overview_present": True,
                "historical_overview_matches_historical_list": True,
                "historical_overview_matches_exactly_one_current_row": True,
                "differing_fields": ["underlying_ticker"],
                "highest_correction_rank": -1,
                "repeat_stable": True,
            },
            "act2_explicit_correction_deliverable": {
                "contract_fingerprint": ACT2_DIAGNOSTIC_CONTRACT_FINGERPRINT,
                "evidence_fingerprint": ACT2_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
                "current_target_rows": 2,
                "historical_target_rows": 1,
                "current_correction_values": [2],
                "historical_correction_values": [2],
                "all_current_rows_have_explicit_correction": True,
                "current_rows_share_one_correction_value": True,
                "current_overview_not_found": True,
                "historical_overview_present": True,
                "historical_overview_matches_historical_list": True,
                "historical_overview_matches_exactly_one_current_row": True,
                "differing_fields": ["additional_underlyings"],
                "repeat_stable": True,
            },
            "aciw_unresolved_primary_exchange_gap": {
                "contract_fingerprint": ACIW_DIAGNOSTIC_CONTRACT_FINGERPRINT,
                "evidence_fingerprint": ACIW_DIAGNOSTIC_EVIDENCE_FINGERPRINT,
                "current_target_rows": 2,
                "current_underlying_tickers": ["ACIW"],
                "current_primary_exchanges": ["GMNI", "XCBO"],
                "current_correction_values": [None],
                "differing_fields": ["primary_exchange"],
                "failed_preexpiration_as_of": "2014-08-15",
                "failed_preexpiration_target_rows": 0,
                "boundary_matrix_repeat_stable": True,
                "contract_overview_present_on_boundary": False,
                "historical_exact_match_found": False,
            },
        },
        "provider": "massive",
        "provider_documented_semantics_as_of": "2026-09-21",
        "provider_documented_semantics": {
            "option_contract_overview": (
                "single-contract structural reference endpoint"
            ),
            "option_as_of": (
                "point-in-time option-contract reference selector"
            ),
            "option_correction": (
                "correction number for an option contract"
            ),
            "underlying_ticker": (
                "ticker of the underlying asset that the option contract relates to"
            ),
            "additional_underlyings": (
                "additional underlying assets or deliverables associated with a contract"
            ),
            "adjusted_series": (
                "adjusted and standard option series may coexist and are not merged"
            ),
            "stock_ticker_history": (
                "historical ticker symbols are retained and are not stitched across changes"
            ),
            "stock_otc_history_floor": "2021-12-31",
        },
        "external_corroboration_only": {
            "source": "SEC_EDGAR",
            "cik": "0001472595",
            "finding": (
                "Accretive Health traded NYSE as AH through 2014-03-14 and "
                "OTC as ACHI beginning 2014-03-17"
            ),
            "used_by_runtime_resolver": False,
        },
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
        "known_conflict_preacquisition_probes": [
            dict(item) for item in KNOWN_CONFLICTS
        ],
        "known_quarantine_preacquisition_probes": [
            dict(item) for item in KNOWN_QUARANTINES
        ],
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
            "unversioned_identity_fallback": {
                "eligible_reference_state": "EXPIRED",
                "eligible_highest_correction_rank": -1,
                "allowed_differing_fields": list(
                    CONFLICT_ALLOWED_DIFFERING_FIELDS
                ),
                "historical_as_of": "expiration_date_minus_1_calendar_day",
                "historical_list": {
                    "endpoint": REFERENCE_ENDPOINT,
                    "underlying_filter": "OMITTED",
                    "filters_from_current_rows": [
                        "contract_type",
                        "expiration_date",
                        "strike_price",
                    ],
                    "target_ticker_rows_required": 1,
                    "repeat_count": CONFLICT_RESOLUTION_REPEAT_COUNT,
                    "repeat_target_row_hash_must_match": True,
                },
                "historical_overview": {
                    "endpoint": REFERENCE_ENDPOINT + "/{options_ticker}",
                    "repeat_count": CONFLICT_RESOLUTION_REPEAT_COUNT,
                    "required_http_status": 200,
                    "repeat_row_hash_must_match": True,
                    "ticker_must_match_target": True,
                },
                "historical_list_and_overview_payload_must_match": True,
                "historical_payload_must_exactly_match_one_current_conflicting_payload": True,
                "otherwise": "FAIL_CLOSED",
                "policy": CONFLICT_RESOLUTION_POLICY,
            },
            "explicit_correction_deliverable_fallback": {
                "eligible_reference_state": "EXPIRED",
                "eligible_highest_correction_rank": "EXPLICIT_NONNEGATIVE",
                "all_conflicting_rows_must_share_highest_correction_rank": True,
                "allowed_differing_fields": list(
                    EXPLICIT_CORRECTION_ALLOWED_DIFFERING_FIELDS
                ),
                "historical_as_of": "expiration_date_minus_1_calendar_day",
                "historical_list": {
                    "endpoint": REFERENCE_ENDPOINT,
                    "underlying_filter": "OMITTED",
                    "filters_from_current_rows": [
                        "contract_type",
                        "expiration_date",
                        "strike_price",
                    ],
                    "target_ticker_rows_required": 1,
                    "repeat_count": CONFLICT_RESOLUTION_REPEAT_COUNT,
                    "repeat_target_row_hash_must_match": True,
                },
                "historical_overview": {
                    "endpoint": REFERENCE_ENDPOINT + "/{options_ticker}",
                    "repeat_count": CONFLICT_RESOLUTION_REPEAT_COUNT,
                    "required_http_status": 200,
                    "repeat_row_hash_must_match": True,
                    "ticker_must_match_target": True,
                },
                "historical_list_and_overview_payload_must_match": True,
                "historical_payload_must_exactly_match_one_current_conflicting_payload": True,
                "historical_payload_correction_rank_must_equal_current_highest_rank": True,
                "dynamic_deliverable_authority_created": False,
                "otherwise": "FAIL_CLOSED",
                "policy": CONFLICT_RESOLUTION_POLICY,
            },
            "ambiguity_quarantine": {
                "policy": AMBIGUITY_QUARANTINE_POLICY,
                "reason": AMBIGUITY_QUARANTINE_REASON,
                "eligible_reference_state": "EXPIRED",
                "eligible_highest_correction_rank": -1,
                "allowed_differing_fields": list(
                    AMBIGUITY_QUARANTINE_ALLOWED_DIFFERING_FIELDS
                ),
                "current_underlying_ticker_must_be_identical": True,
                "historical_as_of": "expiration_date_minus_1_calendar_day",
                "historical_target_row_count_required": 0,
                "historical_zero_target_repeat_count": 2,
                "preserve_all_raw_conflicting_rows": True,
                "exclude_quarantined_ticker_from_normalized_reference": True,
                "write_partition_quarantine_artifact": True,
                "record_payload_hashes_and_request_ids": True,
                "no_selected_provider_row": True,
                "no_historical_identity_inference": True,
                "quarantine_is_not_candidate_availability_authority": True,
                "quarantine_is_not_dynamic_deliverable_authority": True,
                "quarantine_is_not_market_price_authority": True,
                "otherwise": "FAIL_CLOSED",
            },
            "raw_to_normalized_reconciliation": (
                "RAW_ROWS_EQUAL_NORMALIZED_SELECTED_PLUS_DISCARDED_VERSION_ROWS_PLUS_QUARANTINED_RAW_ROWS"
            ),
            "provider_record_sha256": True,
            "record_conflict_resolution_lineage": True,
        },
        "reuse": {
            "verified_v6_receipts": True,
            "verified_v5_raw_lineage": True,
            "verified_v4_raw_lineage": True,
            "verified_v3_raw_lineage": True,
            "verified_v2_raw_lineage": True,
            "verified_v1_raw_lineage": True,
            "local_renormalization_required": True,
            "raw_copy_required": False,
        },
        "efficiency": {
            "bounded_in_flight_partitions": True,
            "default_workers": 5,
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


HISTORICAL_OPTION_REFERENCE_V6_CONTRACT_FINGERPRINT = _stable_hash(
    acquisition_contract_manifest()
)
