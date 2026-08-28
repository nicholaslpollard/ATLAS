from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


PHASE31_POLICY_CONTRACT_VERSION = (
    "phase31-policy-v1-sec-form4-pure-open-market-events-four-hypotheses"
)
PHASE31_SOURCE_PHASE30_MERGE = "bf673ad82886e7172db0d54a33dd9612fa9ea29e"
PHASE31_SOURCE_QUALITY_FINGERPRINT = (
    "2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83"
)
PHASE31_SOURCE_QUALITY_TARGET_RAW_ROWS = 45921
PHASE31_SOURCE_QUALITY_TARGET_VIOLATION_SEED_ROWS = 1
PHASE31_SOURCE_QUALITY_TARGET_CONTAMINATED_ACCESSIONS = 1
PHASE31_SOURCE_QUALITY_TARGET_QUARANTINED_ROWS = 6
PHASE31_SOURCE_QUALITY_TARGET_AUTHORITATIVE_ROWS = 45915
PHASE31_SOURCE_QUALITY_TARGET_QUARANTINE_SHA256 = (
    "586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb"
)
PHASE31_SOURCE_QUALITY_TARGET_WINDOW_SHA256 = {
    "research_boundary": "0378adc4364b0b49812f95f700ff47eb52d55b2cf2c17bbecad77a48d6f8a4d5",
    "mid_history": "d8acaf8834ce166901388b437d5df1adf097d798fefb2e86449d92683acd7afd",
    "development_boundary": "76c250af73a5694751eeb5974dbc55410c3ec63335d57632ab39d4a80d4edd8c",
    "protected_boundary": "a3b1b23c00ffbc7372f779d48171fa0a7aac04a5b3bf028c7b2e9bf74d0bb6e0",
}

PHASE31_SOURCE_HISTORY_START = "2021-07-16"
PHASE31_RESEARCH_SIGNAL_START = "2021-08-16"
PHASE31_DEVELOPMENT_LAST_SIGNAL = "2026-04-13"
PHASE31_OUTER_EMBARGO_START = "2026-04-14"
PHASE31_OUTER_EMBARGO_END = "2026-05-11"
PHASE31_PROTECTED_START = "2026-05-12"
PHASE31_PROTECTED_LAST_SIGNAL = "2026-07-14"
PHASE31_PROTECTED_OUTCOME_END = "2026-08-11"
PHASE31_PUBLIC_AVAILABILITY_RULE = "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE"
PHASE31_ENTRY_RULE = "DECISION_SESSION_OPEN"
PHASE31_EXIT_RULE = "CLOSE_20_XNYS_SESSIONS_AFTER_DECISION"
PHASE31_OUTCOME_HORIZON_SESSIONS = 20
PHASE31_BENCHMARK_TICKER = "SPY"
PHASE31_PRIMARY_RETURN_DEFINITION = (
    "direction*(stock_open_to_t20_close_return-SPY_open_to_t20_close_return)-cost"
)
PHASE31_UNHEDGED_RETURN_DEFINITION = "direction*stock_open_to_t20_close_return-cost"

PHASE31_ELIGIBLE_FORM_TYPE = "4"
PHASE31_ELIGIBLE_RECORD_TYPE = "transaction"
PHASE31_ELIGIBLE_TRANSACTION_CODES = ("P", "S")
PHASE31_ELIGIBLE_SECURITY_TYPE_VALUES = ("non-derivative", "non_derivative")
PHASE31_PURCHASE_ACQUIRED_DISPOSED = "A"
PHASE31_SALE_ACQUIRED_DISPOSED = "D"
PHASE31_REQUIRED_TRANSACTION_TIMELINESS = "O"
PHASE31_ACCESSION_CODE_PURITY_REQUIRED = True
PHASE31_REQUIRE_POSITIVE_SHARES = True
PHASE31_REQUIRE_POSITIVE_PRICE = True
PHASE31_EXCLUDE_AFF_10B5_ONE_TRUE = True
PHASE31_ALLOW_AFF_10B5_ONE_FALSE_OR_NULL = True
PHASE31_EXCLUDE_EQUITY_SWAP_TRUE = True
PHASE31_EXCLUDE_NOT_SUBJECT_TO_SECTION16_TRUE = True
PHASE31_REQUIRE_ANY_SECTION16_ROLE = True
PHASE31_REQUIRE_EXACTLY_ONE_PROVIDER_NATIVE_TICKER = True
PHASE31_CONTRADICTORY_TICKER_SESSION_POLICY = "EXCLUDE"
PHASE31_EVENT_UNIT = "ONE_EXACT_TICKER_DECISION_SESSION_DIRECTION"
PHASE31_EVENT_AGGREGATION = (
    "aggregate qualifying accessions/owners; preserve accession and owner lineage"
)
PHASE31_CLUSTER_LOOKBACK_SESSIONS = 20
PHASE31_CLUSTER_MIN_DISTINCT_OWNERS = 2
PHASE31_CLUSTER_MIN_DISTINCT_ACCESSIONS = 2

PHASE31_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)
PHASE31_PRIMARY_COST_BPS = 10.0
PHASE31_STRESS_COST_BPS = 25.0
PHASE31_SELECTION_FRACTION = 0.75
PHASE31_INTERNAL_PURGE_SESSIONS = 20
PHASE31_SELECTION_FOLDS = 6
PHASE31_INTERNAL_VALIDATION_FOLDS = 3
PHASE31_PROTECTED_FOLDS = 3
PHASE31_BOOTSTRAP_BLOCK_SESSIONS = 20
PHASE31_BOOTSTRAP_REPLICATES = 2000
PHASE31_BOOTSTRAP_SEED = 310231
PHASE31_SELECTION_CONFIDENCE = 0.95
PHASE31_INTERNAL_CONFIDENCE = 0.90
PHASE31_PROTECTED_CONFIDENCE = 0.80

PHASE31_SELECTION_MIN_RAW_ROWS = 750
PHASE31_SELECTION_MIN_SIGNAL_SESSIONS = 250
PHASE31_SELECTION_MIN_UNIQUE_TICKERS = 250
PHASE31_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE31_INTERNAL_MIN_RAW_ROWS = 250
PHASE31_INTERNAL_MIN_SIGNAL_SESSIONS = 80
PHASE31_INTERNAL_MIN_UNIQUE_TICKERS = 80
PHASE31_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE31_PROTECTED_MIN_RAW_ROWS = 75
PHASE31_PROTECTED_MIN_SIGNAL_SESSIONS = 24
PHASE31_PROTECTED_MIN_UNIQUE_TICKERS = 24
PHASE31_PROTECTED_MIN_POSITIVE_FOLDS = 2
PHASE31_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE31_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE31_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE31_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE31_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10
PHASE31_MAX_SINGLE_TICKER_ROW_FRACTION = 0.05
PHASE31_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_4"
PHASE31_MULTIPLE_TESTING_ALPHA = 0.05
PHASE31_SELECTION_WINNER_RULE = "highest_primary_selection_LCB_then_candidate_id"
PHASE31_MAX_SELECTION_WINNERS_PER_DIRECTION = 1
PHASE31_MAX_FINALISTS_PER_DIRECTION = 1
PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED = False
PHASE31_WIN_RATE_IS_HARD_GATE = False
PHASE31_MEDIAN_RETURN_IS_HARD_GATE = False
PHASE31_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED = True
PHASE31_PRIMARY_MEAN_POSITIVE_REQUIRED = True
PHASE31_PRIMARY_LCB_POSITIVE_REQUIRED = True
PHASE31_STRESS_MEAN_POSITIVE_REQUIRED = True
PHASE31_UNHEDGED_PRIMARY_MEAN_POSITIVE_REQUIRED = True
PHASE31_ROBUSTNESS_STATE_TIMING = "PREVIOUS_XNYS_SESSION_ONLY"

PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False
PHASE31_PROTECTED_HOLDOUT_CONSUMED_AFTER_ANY_NONEMPTY_RETURN_READ = True
PHASE31_PROVIDER_TEXT_ALPHA_AUTHORITY = False
PHASE31_FOOTNOTE_NLP_ALPHA_AUTHORITY = False
PHASE31_TRANSACTION_VALUE_THRESHOLD_USED = False
PHASE31_PROVIDER_WRITES = 0
PHASE31_BROKER_READS = 0
PHASE31_BROKER_WRITES = 0
PHASE31_ORDER_WRITES = 0
PHASE31_PAPER_SUBMITS = 0
PHASE31_LIVE_WRITES = 0
PHASE31_AUTOMATION_WRITES = 0
PHASE31_AUTOMATIC_BROKER_FAILOVER = False


@dataclass(frozen=True, slots=True)
class Phase31CandidateSpec:
    candidate_id: str
    family: str
    direction: str
    event_direction: str
    requires_cluster: bool


PHASE31_CANDIDATES = (
    Phase31CandidateSpec(
        candidate_id="open_market_purchase_long",
        family="open_market_purchase",
        direction="LONG",
        event_direction="PURCHASE",
        requires_cluster=False,
    ),
    Phase31CandidateSpec(
        candidate_id="clustered_open_market_purchase_long",
        family="clustered_open_market_purchase",
        direction="LONG",
        event_direction="PURCHASE",
        requires_cluster=True,
    ),
    Phase31CandidateSpec(
        candidate_id="open_market_sale_short",
        family="open_market_sale",
        direction="SHORT",
        event_direction="SALE",
        requires_cluster=False,
    ),
    Phase31CandidateSpec(
        candidate_id="clustered_open_market_sale_short",
        family="clustered_open_market_sale",
        direction="SHORT",
        event_direction="SALE",
        requires_cluster=True,
    ),
)


def _policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE31_POLICY_CONTRACT_VERSION,
        "source_phase30_merge": PHASE31_SOURCE_PHASE30_MERGE,
        "source_quality_fingerprint": PHASE31_SOURCE_QUALITY_FINGERPRINT,
        "source_quality_target": {
            "raw_rows": PHASE31_SOURCE_QUALITY_TARGET_RAW_ROWS,
            "chronology_violation_seed_rows": PHASE31_SOURCE_QUALITY_TARGET_VIOLATION_SEED_ROWS,
            "contaminated_accessions": PHASE31_SOURCE_QUALITY_TARGET_CONTAMINATED_ACCESSIONS,
            "quarantined_accession_rows": PHASE31_SOURCE_QUALITY_TARGET_QUARANTINED_ROWS,
            "authoritative_rows": PHASE31_SOURCE_QUALITY_TARGET_AUTHORITATIVE_ROWS,
            "quarantine_sha256": PHASE31_SOURCE_QUALITY_TARGET_QUARANTINE_SHA256,
            "authoritative_window_sha256": PHASE31_SOURCE_QUALITY_TARGET_WINDOW_SHA256,
        },
        "source_history_start": PHASE31_SOURCE_HISTORY_START,
        "research_signal_start": PHASE31_RESEARCH_SIGNAL_START,
        "development_last_signal": PHASE31_DEVELOPMENT_LAST_SIGNAL,
        "outer_embargo_start": PHASE31_OUTER_EMBARGO_START,
        "outer_embargo_end": PHASE31_OUTER_EMBARGO_END,
        "protected_start": PHASE31_PROTECTED_START,
        "protected_last_signal": PHASE31_PROTECTED_LAST_SIGNAL,
        "protected_outcome_end": PHASE31_PROTECTED_OUTCOME_END,
        "public_availability_rule": PHASE31_PUBLIC_AVAILABILITY_RULE,
        "entry_rule": PHASE31_ENTRY_RULE,
        "exit_rule": PHASE31_EXIT_RULE,
        "outcome_horizon_sessions": PHASE31_OUTCOME_HORIZON_SESSIONS,
        "benchmark": PHASE31_BENCHMARK_TICKER,
        "primary_return": PHASE31_PRIMARY_RETURN_DEFINITION,
        "unhedged_return": PHASE31_UNHEDGED_RETURN_DEFINITION,
        "eligible_form_type": PHASE31_ELIGIBLE_FORM_TYPE,
        "eligible_record_type": PHASE31_ELIGIBLE_RECORD_TYPE,
        "eligible_codes": list(PHASE31_ELIGIBLE_TRANSACTION_CODES),
        "accession_code_purity_required": PHASE31_ACCESSION_CODE_PURITY_REQUIRED,
        "eligible_security_type_values": list(PHASE31_ELIGIBLE_SECURITY_TYPE_VALUES),
        "purchase_acquired_disposed": PHASE31_PURCHASE_ACQUIRED_DISPOSED,
        "sale_acquired_disposed": PHASE31_SALE_ACQUIRED_DISPOSED,
        "require_positive_shares": PHASE31_REQUIRE_POSITIVE_SHARES,
        "require_positive_price": PHASE31_REQUIRE_POSITIVE_PRICE,
        "transaction_timeliness": PHASE31_REQUIRED_TRANSACTION_TIMELINESS,
        "exclude_aff_10b5_one_true": PHASE31_EXCLUDE_AFF_10B5_ONE_TRUE,
        "allow_aff_10b5_one_false_or_null": PHASE31_ALLOW_AFF_10B5_ONE_FALSE_OR_NULL,
        "exclude_equity_swap_true": PHASE31_EXCLUDE_EQUITY_SWAP_TRUE,
        "exclude_not_subject_to_section16_true": PHASE31_EXCLUDE_NOT_SUBJECT_TO_SECTION16_TRUE,
        "require_any_section16_role": PHASE31_REQUIRE_ANY_SECTION16_ROLE,
        "require_exactly_one_provider_native_ticker": PHASE31_REQUIRE_EXACTLY_ONE_PROVIDER_NATIVE_TICKER,
        "contradictory_purchase_sale_ticker_session": PHASE31_CONTRADICTORY_TICKER_SESSION_POLICY,
        "event_unit": PHASE31_EVENT_UNIT,
        "event_aggregation": PHASE31_EVENT_AGGREGATION,
        "cluster_lookback_sessions": PHASE31_CLUSTER_LOOKBACK_SESSIONS,
        "cluster_min_distinct_owners": PHASE31_CLUSTER_MIN_DISTINCT_OWNERS,
        "cluster_min_distinct_accessions": PHASE31_CLUSTER_MIN_DISTINCT_ACCESSIONS,
        "candidate_definitions": [asdict(candidate) for candidate in PHASE31_CANDIDATES],
        "cost_grid_bps": list(PHASE31_COST_GRID_BPS),
        "primary_cost_bps": PHASE31_PRIMARY_COST_BPS,
        "stress_cost_bps": PHASE31_STRESS_COST_BPS,
        "selection_fraction": PHASE31_SELECTION_FRACTION,
        "internal_purge_sessions": PHASE31_INTERNAL_PURGE_SESSIONS,
        "selection_folds": PHASE31_SELECTION_FOLDS,
        "internal_validation_folds": PHASE31_INTERNAL_VALIDATION_FOLDS,
        "protected_folds": PHASE31_PROTECTED_FOLDS,
        "bootstrap_block_sessions": PHASE31_BOOTSTRAP_BLOCK_SESSIONS,
        "bootstrap_replicates": PHASE31_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": PHASE31_BOOTSTRAP_SEED,
        "selection_confidence": PHASE31_SELECTION_CONFIDENCE,
        "internal_confidence": PHASE31_INTERNAL_CONFIDENCE,
        "protected_confidence": PHASE31_PROTECTED_CONFIDENCE,
        "selection_min_raw_rows": PHASE31_SELECTION_MIN_RAW_ROWS,
        "selection_min_signal_sessions": PHASE31_SELECTION_MIN_SIGNAL_SESSIONS,
        "selection_min_unique_tickers": PHASE31_SELECTION_MIN_UNIQUE_TICKERS,
        "selection_min_positive_folds": PHASE31_SELECTION_MIN_POSITIVE_FOLDS,
        "internal_min_raw_rows": PHASE31_INTERNAL_MIN_RAW_ROWS,
        "internal_min_signal_sessions": PHASE31_INTERNAL_MIN_SIGNAL_SESSIONS,
        "internal_min_unique_tickers": PHASE31_INTERNAL_MIN_UNIQUE_TICKERS,
        "internal_min_positive_folds": PHASE31_INTERNAL_MIN_POSITIVE_FOLDS,
        "protected_min_raw_rows": PHASE31_PROTECTED_MIN_RAW_ROWS,
        "protected_min_signal_sessions": PHASE31_PROTECTED_MIN_SIGNAL_SESSIONS,
        "protected_min_unique_tickers": PHASE31_PROTECTED_MIN_UNIQUE_TICKERS,
        "protected_min_positive_folds": PHASE31_PROTECTED_MIN_POSITIVE_FOLDS,
        "min_positive_year_fraction": PHASE31_MIN_POSITIVE_YEAR_FRACTION,
        "min_positive_regime_fraction": PHASE31_MIN_POSITIVE_REGIME_FRACTION,
        "min_year_signal_sessions": PHASE31_MIN_YEAR_SIGNAL_SESSIONS,
        "min_regime_signal_sessions": PHASE31_MIN_REGIME_SIGNAL_SESSIONS,
        "max_single_session_row_fraction": PHASE31_MAX_SINGLE_SESSION_ROW_FRACTION,
        "max_single_ticker_row_fraction": PHASE31_MAX_SINGLE_TICKER_ROW_FRACTION,
        "multiple_testing_method": PHASE31_MULTIPLE_TESTING_METHOD,
        "multiple_testing_alpha": PHASE31_MULTIPLE_TESTING_ALPHA,
        "selection_winner_rule": PHASE31_SELECTION_WINNER_RULE,
        "max_selection_winners_per_direction": PHASE31_MAX_SELECTION_WINNERS_PER_DIRECTION,
        "max_finalists_per_direction": PHASE31_MAX_FINALISTS_PER_DIRECTION,
        "runner_up_substitution_allowed": PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED,
        "win_rate_is_hard_gate": PHASE31_WIN_RATE_IS_HARD_GATE,
        "median_return_is_hard_gate": PHASE31_MEDIAN_RETURN_IS_HARD_GATE,
        "deflated_performance_diagnostic_required": PHASE31_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED,
        "primary_mean_positive_required": PHASE31_PRIMARY_MEAN_POSITIVE_REQUIRED,
        "primary_lcb_positive_required": PHASE31_PRIMARY_LCB_POSITIVE_REQUIRED,
        "stress_mean_positive_required": PHASE31_STRESS_MEAN_POSITIVE_REQUIRED,
        "unhedged_primary_mean_positive_required": PHASE31_UNHEDGED_PRIMARY_MEAN_POSITIVE_REQUIRED,
        "robustness_state_timing": PHASE31_ROBUSTNESS_STATE_TIMING,
        "protected_returns_before_finalists_allowed": PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        "protected_holdout_consumed_after_any_nonempty_protected_return_read": PHASE31_PROTECTED_HOLDOUT_CONSUMED_AFTER_ANY_NONEMPTY_RETURN_READ,
        "provider_text_alpha_authority": PHASE31_PROVIDER_TEXT_ALPHA_AUTHORITY,
        "footnote_nlp_alpha_authority": PHASE31_FOOTNOTE_NLP_ALPHA_AUTHORITY,
        "transaction_value_threshold_used": PHASE31_TRANSACTION_VALUE_THRESHOLD_USED,
        "provider_writes": PHASE31_PROVIDER_WRITES,
        "broker_reads": PHASE31_BROKER_READS,
        "broker_writes": PHASE31_BROKER_WRITES,
        "order_writes": PHASE31_ORDER_WRITES,
        "paper_submits": PHASE31_PAPER_SUBMITS,
        "live_writes": PHASE31_LIVE_WRITES,
        "automation_writes": PHASE31_AUTOMATION_WRITES,
        "automatic_broker_failover": PHASE31_AUTOMATIC_BROKER_FAILOVER,
    }


def phase31_policy_fingerprint() -> str:
    raw = json.dumps(_policy_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase31_candidate_ids() -> tuple[str, ...]:
    return tuple(candidate.candidate_id for candidate in PHASE31_CANDIDATES)


def phase31_policy_public_dict() -> dict[str, object]:
    return dict(_policy_payload())
