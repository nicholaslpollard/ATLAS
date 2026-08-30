from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


PHASE32_POLICY_CONTRACT_VERSION = "phase32-policy-v1-sec-8k-semantic-five-hypotheses"
PHASE32_SOURCE_PHASE31_MERGE = "ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4"
PHASE32_CORE_SOURCE_FINGERPRINT = (
    "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
)
PHASE32_SEMANTIC_SOURCE_FINGERPRINT = (
    "eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566"
)
PHASE32_SEMANTIC_SOURCE_CENSUS_CONTRACT = (
    "phase32-semantic-v2-source-census-v1-no-market-outcomes"
)
PHASE32_CENSUS_TAXONOMY_ROWS = 119
PHASE32_CENSUS_OBSERVED_TAXONOMY_ROWS = 112
PHASE32_CENSUS_DISCLOSURE_ROWS = 7468
PHASE32_CENSUS_UNIQUE_ACCESSIONS = 4427
PHASE32_CENSUS_UNIQUE_CIKS = 3097
PHASE32_CENSUS_TICKER_MAPPED_ROWS = 6231
PHASE32_CENSUS_TICKER_UNMAPPED_ROWS = 1237
PHASE32_CENSUS_TARGET_OUTCOME_ROWS_READ = 0
PHASE32_CENSUS_PROTECTED_RETURN_ROWS_READ = 0
PHASE32_TAXONOMY_VERSION = "1.0"

PHASE32_RESEARCH_SIGNAL_START = "2021-08-16"
PHASE32_DEVELOPMENT_LAST_SIGNAL = "2026-05-04"
PHASE32_OUTER_EMBARGO_START = "2026-05-05"
PHASE32_OUTER_EMBARGO_END = "2026-05-11"
PHASE32_PROTECTED_START = "2026-05-12"
PHASE32_PROTECTED_LAST_SIGNAL = "2026-08-04"
PHASE32_PROTECTED_OUTCOME_END = "2026-08-11"
PHASE32_PUBLIC_AVAILABILITY_RULE = (
    "FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME"
)
PHASE32_ENTRY_RULE = "DECISION_SESSION_OPEN"
PHASE32_EXIT_RULE = "CLOSE_5_XNYS_SESSIONS_AFTER_DECISION"
PHASE32_OUTCOME_HORIZON_SESSIONS = 5
PHASE32_BENCHMARK_TICKER = "SPY"
PHASE32_PRIMARY_RETURN_DEFINITION = (
    "direction*(stock_open_to_t5_close_return-SPY_open_to_t5_close_return)-cost"
)
PHASE32_UNHEDGED_RETURN_DEFINITION = "direction*stock_open_to_t5_close_return-cost"

PHASE32_ELIGIBLE_FORM_TYPE = "8-K"
PHASE32_AMENDMENTS_ALLOWED = False
PHASE32_SUPPORTING_TEXT_REQUIRED = True
PHASE32_PROVIDER_ITEMS_TEXT_ALPHA_AUTHORITY = False
PHASE32_PROVIDER_SUPPORTING_TEXT_SENTIMENT_AUTHORITY = False
PHASE32_TAXONOMY_EXACT_MATCH_ONLY = True
PHASE32_EVENT_UNIT = "ONE_PIT_INSTRUMENT_DECISION_SESSION_CANDIDATE"
PHASE32_SAME_CANDIDATE_EVENT_AGGREGATION = (
    "aggregate exact candidate tags/accessions; preserve accession/category lineage"
)
PHASE32_CROSS_CANDIDATE_SAME_DIRECTION_OVERLAP_ALLOWED = True
PHASE32_CONTRADICTORY_LONG_SHORT_INSTRUMENT_SESSION = "EXCLUDE_ALL"
PHASE32_INSTRUMENT_MAPPING_RULE = (
    "UNION_PROVIDER_NATIVE_DISCLOSURE_TEXT_INDEX_TICKER_METADATA_THEN_PIT_CIK_BOUND_UNIQUE_INSTRUMENT"
)
PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION = (
    "instrument-identity-v4-no-issuer-level-medium-collapse"
)
PHASE32_INSTRUMENT_ALLOWED_IDENTITY_QUALITIES = ("strong", "medium")
PHASE32_INSTRUMENT_MEDIUM_IDENTITY_RULE = (
    "CIK_PLUS_EXACT_PROVIDER_NATIVE_TICKER_PLUS_PRIMARY_EXCHANGE_PLUS_SECURITY_TYPE"
)
PHASE32_INSTRUMENT_MAPPING_EXACT_CASE_REQUIRED = True
PHASE32_INSTRUMENT_REFERENCE_CIK_MUST_EQUAL_FILING_CIK = True
PHASE32_INSTRUMENT_UNIQUE_RESOLUTION_REQUIRED = True
PHASE32_INSTRUMENT_FALLBACK_TICKER_SNAPSHOT_ALLOWED = False
PHASE32_INSTRUMENT_IDENTITY_INTERVAL_MUST_COVER_ENTRY_EXIT = True
PHASE32_CURRENT_UNIVERSE_BACKPROJECTION_ALLOWED = False
PHASE32_TICKER_ALIAS_BACKFILL_ALLOWED = False
PHASE32_SPLIT_OR_CORPORATE_ACTION_INVALID_RETURN_POLICY = "CENSOR_FAIL_CLOSED"

PHASE32_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)
PHASE32_PRIMARY_COST_BPS = 10.0
PHASE32_STRESS_COST_BPS = 25.0
PHASE32_SELECTION_FRACTION = 0.75
PHASE32_INTERNAL_PURGE_SESSIONS = 5
PHASE32_SELECTION_FOLDS = 6
PHASE32_INTERNAL_VALIDATION_FOLDS = 3
PHASE32_PROTECTED_FOLDS = 3
PHASE32_BOOTSTRAP_BLOCK_SESSIONS = 5
PHASE32_BOOTSTRAP_REPLICATES = 2000
PHASE32_BOOTSTRAP_SEED = 320832
PHASE32_SELECTION_CONFIDENCE = 0.95
PHASE32_INTERNAL_CONFIDENCE = 0.90
PHASE32_PROTECTED_CONFIDENCE = 0.80

PHASE32_SELECTION_MIN_EVENT_ROWS = 500
PHASE32_SELECTION_MIN_SIGNAL_SESSIONS = 200
PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS = 200
PHASE32_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE32_INTERNAL_MIN_EVENT_ROWS = 150
PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS = 60
PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS = 60
PHASE32_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE32_PROTECTED_MIN_EVENT_ROWS = 50
PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS = 20
PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS = 20
PHASE32_PROTECTED_MIN_POSITIVE_FOLDS = 2
PHASE32_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE32_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE32_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE32_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE32_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10
PHASE32_MAX_SINGLE_INSTRUMENT_ROW_FRACTION = 0.05
PHASE32_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_5"
PHASE32_MULTIPLE_TESTING_ALPHA = 0.05
PHASE32_SELECTION_WINNER_RULE = "highest_primary_selection_LCB_then_candidate_id"
PHASE32_MAX_SELECTION_WINNERS_PER_DIRECTION = 1
PHASE32_MAX_FINALISTS_PER_DIRECTION = 1
PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED = False
PHASE32_WIN_RATE_IS_HARD_GATE = False
PHASE32_MEDIAN_RETURN_IS_HARD_GATE = False
PHASE32_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED = True
PHASE32_PRIMARY_MEAN_POSITIVE_REQUIRED = True
PHASE32_PRIMARY_LCB_POSITIVE_REQUIRED = True
PHASE32_STRESS_MEAN_POSITIVE_REQUIRED = True
PHASE32_UNHEDGED_PRIMARY_MEAN_POSITIVE_REQUIRED = True
PHASE32_ROBUSTNESS_STATE_TIMING = "PREVIOUS_XNYS_SESSION_ONLY"

PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False
PHASE32_PROTECTED_HOLDOUT_CONSUMED_AFTER_ANY_NONEMPTY_RETURN_READ = True
PHASE32_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED = True
PHASE32_PROVIDER_WRITES = 0
PHASE32_BROKER_READS = 0
PHASE32_BROKER_WRITES = 0
PHASE32_ORDER_WRITES = 0
PHASE32_PAPER_SUBMITS = 0
PHASE32_LIVE_WRITES = 0
PHASE32_AUTOMATION_WRITES = 0
PHASE32_AUTOMATIC_BROKER_FAILOVER = False
PHASE32_PHASE33_SIGNAL_TO_TRADE_AUTHORITY = False


@dataclass(frozen=True, slots=True)
class Phase32CandidateSpec:
    candidate_id: str
    family: str
    direction: str
    taxonomy_triples: tuple[tuple[str, str, str], ...]
    mechanism: str
    probe_census_rows: int


PHASE32_CANDIDATES = (
    Phase32CandidateSpec(
        candidate_id="equity_issuance_short",
        family="equity_issuance",
        direction="SHORT",
        taxonomy_triples=(
            ("capital_and_financing", "equity_activity", "public_offering"),
            ("capital_and_financing", "equity_activity", "private_placement"),
            ("capital_and_financing", "equity_activity", "pipe_transaction"),
        ),
        mechanism="new_equity_supply_and_dilution_pressure",
        probe_census_rows=433,
    ),
    Phase32CandidateSpec(
        candidate_id="share_repurchase_long",
        family="share_repurchase",
        direction="LONG",
        taxonomy_triples=(
            ("capital_and_financing", "shareholder_returns", "share_repurchase_program"),
        ),
        mechanism="issuer_demand_capital_return_and_confidence",
        probe_census_rows=106,
    ),
    Phase32CandidateSpec(
        candidate_id="financial_integrity_adverse_short",
        family="financial_integrity_adverse",
        direction="SHORT",
        taxonomy_triples=(
            ("financial_results", "financial_integrity", "accounting_error_correction"),
            ("financial_results", "financial_integrity", "audit_opinion_withdrawal"),
            ("financial_results", "financial_integrity", "financial_restatement"),
            ("financial_results", "financial_integrity", "internal_control_weakness"),
        ),
        mechanism="financial_reporting_reliability_deterioration",
        probe_census_rows=53,
    ),
    Phase32CandidateSpec(
        candidate_id="listing_distress_short",
        family="listing_distress",
        direction="SHORT",
        taxonomy_triples=(
            ("regulatory_and_compliance", "exchange_listing", "listing_deficiency_notice"),
            ("regulatory_and_compliance", "exchange_listing", "delisting_determination"),
        ),
        mechanism="listing_access_and_compliance_deterioration",
        probe_census_rows=126,
    ),
    Phase32CandidateSpec(
        candidate_id="solvency_distress_short",
        family="solvency_distress",
        direction="SHORT",
        taxonomy_triples=(
            ("capital_and_financing", "debt_distress", "covenant_violation"),
            ("capital_and_financing", "debt_distress", "debt_acceleration"),
            ("capital_and_financing", "debt_distress", "payment_default"),
            ("capital_and_financing", "debt_distress", "rating_downgrade_trigger"),
            ("risk_events", "bankruptcy_and_insolvency", "going_concern"),
            ("risk_events", "bankruptcy_and_insolvency", "involuntary_bankruptcy"),
            ("risk_events", "bankruptcy_and_insolvency", "receivership_appointment"),
            ("risk_events", "bankruptcy_and_insolvency", "voluntary_bankruptcy"),
        ),
        mechanism="funding_and_solvency_impairment",
        probe_census_rows=64,
    ),
)


def _policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE32_POLICY_CONTRACT_VERSION,
        "source_phase31_merge": PHASE32_SOURCE_PHASE31_MERGE,
        "core_source_fingerprint": PHASE32_CORE_SOURCE_FINGERPRINT,
        "semantic_source_fingerprint": PHASE32_SEMANTIC_SOURCE_FINGERPRINT,
        "semantic_source_census_contract": PHASE32_SEMANTIC_SOURCE_CENSUS_CONTRACT,
        "semantic_source_census_target": {
            "taxonomy_rows": PHASE32_CENSUS_TAXONOMY_ROWS,
            "observed_taxonomy_rows": PHASE32_CENSUS_OBSERVED_TAXONOMY_ROWS,
            "disclosure_rows": PHASE32_CENSUS_DISCLOSURE_ROWS,
            "unique_accessions": PHASE32_CENSUS_UNIQUE_ACCESSIONS,
            "unique_ciks": PHASE32_CENSUS_UNIQUE_CIKS,
            "ticker_mapped_rows": PHASE32_CENSUS_TICKER_MAPPED_ROWS,
            "ticker_unmapped_rows": PHASE32_CENSUS_TICKER_UNMAPPED_ROWS,
            "target_outcome_rows_read": PHASE32_CENSUS_TARGET_OUTCOME_ROWS_READ,
            "protected_return_rows_read": PHASE32_CENSUS_PROTECTED_RETURN_ROWS_READ,
        },
        "taxonomy_version": PHASE32_TAXONOMY_VERSION,
        "research_signal_start": PHASE32_RESEARCH_SIGNAL_START,
        "development_last_signal": PHASE32_DEVELOPMENT_LAST_SIGNAL,
        "outer_embargo_start": PHASE32_OUTER_EMBARGO_START,
        "outer_embargo_end": PHASE32_OUTER_EMBARGO_END,
        "protected_start": PHASE32_PROTECTED_START,
        "protected_last_signal": PHASE32_PROTECTED_LAST_SIGNAL,
        "protected_outcome_end": PHASE32_PROTECTED_OUTCOME_END,
        "public_availability_rule": PHASE32_PUBLIC_AVAILABILITY_RULE,
        "entry_rule": PHASE32_ENTRY_RULE,
        "exit_rule": PHASE32_EXIT_RULE,
        "outcome_horizon_sessions": PHASE32_OUTCOME_HORIZON_SESSIONS,
        "benchmark": PHASE32_BENCHMARK_TICKER,
        "primary_return": PHASE32_PRIMARY_RETURN_DEFINITION,
        "unhedged_return": PHASE32_UNHEDGED_RETURN_DEFINITION,
        "eligible_form_type": PHASE32_ELIGIBLE_FORM_TYPE,
        "amendments_allowed": PHASE32_AMENDMENTS_ALLOWED,
        "supporting_text_required": PHASE32_SUPPORTING_TEXT_REQUIRED,
        "provider_items_text_alpha_authority": PHASE32_PROVIDER_ITEMS_TEXT_ALPHA_AUTHORITY,
        "provider_supporting_text_sentiment_authority": PHASE32_PROVIDER_SUPPORTING_TEXT_SENTIMENT_AUTHORITY,
        "taxonomy_exact_match_only": PHASE32_TAXONOMY_EXACT_MATCH_ONLY,
        "event_unit": PHASE32_EVENT_UNIT,
        "same_candidate_event_aggregation": PHASE32_SAME_CANDIDATE_EVENT_AGGREGATION,
        "cross_candidate_same_direction_overlap_allowed": PHASE32_CROSS_CANDIDATE_SAME_DIRECTION_OVERLAP_ALLOWED,
        "contradictory_long_short_instrument_session": PHASE32_CONTRADICTORY_LONG_SHORT_INSTRUMENT_SESSION,
        "instrument_mapping_rule": PHASE32_INSTRUMENT_MAPPING_RULE,
        "instrument_identity_contract_version": PHASE32_INSTRUMENT_IDENTITY_CONTRACT_VERSION,
        "instrument_allowed_identity_qualities": list(PHASE32_INSTRUMENT_ALLOWED_IDENTITY_QUALITIES),
        "instrument_medium_identity_rule": PHASE32_INSTRUMENT_MEDIUM_IDENTITY_RULE,
        "instrument_mapping_exact_case_required": PHASE32_INSTRUMENT_MAPPING_EXACT_CASE_REQUIRED,
        "instrument_reference_cik_must_equal_filing_cik": PHASE32_INSTRUMENT_REFERENCE_CIK_MUST_EQUAL_FILING_CIK,
        "instrument_unique_resolution_required": PHASE32_INSTRUMENT_UNIQUE_RESOLUTION_REQUIRED,
        "instrument_fallback_ticker_snapshot_allowed": PHASE32_INSTRUMENT_FALLBACK_TICKER_SNAPSHOT_ALLOWED,
        "instrument_identity_interval_must_cover_entry_exit": PHASE32_INSTRUMENT_IDENTITY_INTERVAL_MUST_COVER_ENTRY_EXIT,
        "current_universe_backprojection_allowed": PHASE32_CURRENT_UNIVERSE_BACKPROJECTION_ALLOWED,
        "ticker_alias_backfill_allowed": PHASE32_TICKER_ALIAS_BACKFILL_ALLOWED,
        "split_or_corporate_action_invalid_return_policy": PHASE32_SPLIT_OR_CORPORATE_ACTION_INVALID_RETURN_POLICY,
        "candidate_definitions": [asdict(candidate) for candidate in PHASE32_CANDIDATES],
        "cost_grid_bps": list(PHASE32_COST_GRID_BPS),
        "primary_cost_bps": PHASE32_PRIMARY_COST_BPS,
        "stress_cost_bps": PHASE32_STRESS_COST_BPS,
        "selection_fraction": PHASE32_SELECTION_FRACTION,
        "internal_purge_sessions": PHASE32_INTERNAL_PURGE_SESSIONS,
        "selection_folds": PHASE32_SELECTION_FOLDS,
        "internal_validation_folds": PHASE32_INTERNAL_VALIDATION_FOLDS,
        "protected_folds": PHASE32_PROTECTED_FOLDS,
        "bootstrap_block_sessions": PHASE32_BOOTSTRAP_BLOCK_SESSIONS,
        "bootstrap_replicates": PHASE32_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": PHASE32_BOOTSTRAP_SEED,
        "selection_confidence": PHASE32_SELECTION_CONFIDENCE,
        "internal_confidence": PHASE32_INTERNAL_CONFIDENCE,
        "protected_confidence": PHASE32_PROTECTED_CONFIDENCE,
        "selection_min_event_rows": PHASE32_SELECTION_MIN_EVENT_ROWS,
        "selection_min_signal_sessions": PHASE32_SELECTION_MIN_SIGNAL_SESSIONS,
        "selection_min_unique_instruments": PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS,
        "selection_min_positive_folds": PHASE32_SELECTION_MIN_POSITIVE_FOLDS,
        "internal_min_event_rows": PHASE32_INTERNAL_MIN_EVENT_ROWS,
        "internal_min_signal_sessions": PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS,
        "internal_min_unique_instruments": PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
        "internal_min_positive_folds": PHASE32_INTERNAL_MIN_POSITIVE_FOLDS,
        "protected_min_event_rows": PHASE32_PROTECTED_MIN_EVENT_ROWS,
        "protected_min_signal_sessions": PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS,
        "protected_min_unique_instruments": PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
        "protected_min_positive_folds": PHASE32_PROTECTED_MIN_POSITIVE_FOLDS,
        "min_positive_year_fraction": PHASE32_MIN_POSITIVE_YEAR_FRACTION,
        "min_positive_regime_fraction": PHASE32_MIN_POSITIVE_REGIME_FRACTION,
        "min_year_signal_sessions": PHASE32_MIN_YEAR_SIGNAL_SESSIONS,
        "min_regime_signal_sessions": PHASE32_MIN_REGIME_SIGNAL_SESSIONS,
        "max_single_session_row_fraction": PHASE32_MAX_SINGLE_SESSION_ROW_FRACTION,
        "max_single_instrument_row_fraction": PHASE32_MAX_SINGLE_INSTRUMENT_ROW_FRACTION,
        "multiple_testing_method": PHASE32_MULTIPLE_TESTING_METHOD,
        "multiple_testing_alpha": PHASE32_MULTIPLE_TESTING_ALPHA,
        "selection_winner_rule": PHASE32_SELECTION_WINNER_RULE,
        "max_selection_winners_per_direction": PHASE32_MAX_SELECTION_WINNERS_PER_DIRECTION,
        "max_finalists_per_direction": PHASE32_MAX_FINALISTS_PER_DIRECTION,
        "runner_up_substitution_allowed": PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
        "win_rate_is_hard_gate": PHASE32_WIN_RATE_IS_HARD_GATE,
        "median_return_is_hard_gate": PHASE32_MEDIAN_RETURN_IS_HARD_GATE,
        "deflated_performance_diagnostic_required": PHASE32_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED,
        "primary_mean_positive_required": PHASE32_PRIMARY_MEAN_POSITIVE_REQUIRED,
        "primary_lcb_positive_required": PHASE32_PRIMARY_LCB_POSITIVE_REQUIRED,
        "stress_mean_positive_required": PHASE32_STRESS_MEAN_POSITIVE_REQUIRED,
        "unhedged_primary_mean_positive_required": PHASE32_UNHEDGED_PRIMARY_MEAN_POSITIVE_REQUIRED,
        "robustness_state_timing": PHASE32_ROBUSTNESS_STATE_TIMING,
        "protected_returns_before_finalists_allowed": PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        "protected_holdout_consumed_after_any_nonempty_protected_return_read": PHASE32_PROTECTED_HOLDOUT_CONSUMED_AFTER_ANY_NONEMPTY_RETURN_READ,
        "protected_predictors_before_finalists_allowed": PHASE32_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED,
        "provider_writes": PHASE32_PROVIDER_WRITES,
        "broker_reads": PHASE32_BROKER_READS,
        "broker_writes": PHASE32_BROKER_WRITES,
        "order_writes": PHASE32_ORDER_WRITES,
        "paper_submits": PHASE32_PAPER_SUBMITS,
        "live_writes": PHASE32_LIVE_WRITES,
        "automation_writes": PHASE32_AUTOMATION_WRITES,
        "automatic_broker_failover": PHASE32_AUTOMATIC_BROKER_FAILOVER,
        "phase33_signal_to_trade_authority": PHASE32_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    }


def phase32_policy_fingerprint() -> str:
    raw = json.dumps(_policy_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase32_candidate_ids() -> tuple[str, ...]:
    return tuple(candidate.candidate_id for candidate in PHASE32_CANDIDATES)


def phase32_policy_public_dict() -> dict[str, object]:
    return dict(_policy_payload())
