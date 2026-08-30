from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


XBRL_SCIENTIFIC_CONTRACT = "alpha-gate-xbrl-scientific-v1-six-yoy-quality-change-hypotheses"
XBRL_SCIENTIFIC_FINGERPRINT = "2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490"
XBRL_ENTRY_SOURCE_REPAIR_CONTRACT = (
    "alpha-gate-xbrl-pit-audit-v2-targeted-common-stock-active-only-identity-repair-no-market-outcomes"
)
XBRL_ENTRY_SOURCE_REPAIR_FINGERPRINT = "e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f"
XBRL_ENTRY_SOURCE_REPAIR_STATUS = "AUDIT_PASS"
XBRL_ENTRY_REPLAYED_IDENTITY_DECISIONS = 198
XBRL_ENTRY_UNAMBIGUOUS_MAPPINGS = 171
XBRL_ENTRY_ISSUERS_WITH_3_MAPPINGS = 38
XBRL_ENTRY_V1_REPORT_SHA256 = "93ef523faf31b2556f58ed760b2da3c10f6d4e75611b8501593a1ae896826edc"

XBRL_MECHANISM = "PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY"
XBRL_STUDY_CIK_POPULATION = "ACCEPTED_XBRL_FEASIBILITY_SAMPLE_EXACT_200_CIKS_NO_PERFORMANCE_RESAMPLING"
XBRL_PREDICTOR_SOURCE_START = "2016-01-01"
XBRL_PREDICTOR_SOURCE_CUTOFF = "2026-08-11"
XBRL_PERFORMANCE_SIGNAL_START = "2021-08-16"
XBRL_DEVELOPMENT_LAST_SIGNAL = "2024-12-31"
XBRL_OUTER_EMBARGO_START = "2025-01-02"
XBRL_OUTER_EMBARGO_END = "2025-04-03"
XBRL_PROTECTED_START = "2025-04-04"
XBRL_PROTECTED_LAST_SIGNAL = "2026-05-11"
XBRL_PROTECTED_OUTCOME_END = "2026-08-11"

XBRL_PUBLIC_AVAILABILITY_RULE = "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE"
XBRL_INSTRUMENT_RULE = "MASSIVE_EXACT_CIK_DATE_ACTIVE_TRUE_TYPE_CS_UNIQUE_STRONG_OR_MEDIUM"
XBRL_INSTANT_FACT_RULE = "ASSETS_USD_EXACT_ACCESSION_END_INSTANT"
XBRL_DURATION_FACT_RULE = "USD_ONLY_ORIGINAL_10Q_10K_ACCESSION_VERSIONED"
XBRL_QUARTER_DIRECT_DURATION_DAYS = (70, 110)
XBRL_ANNUAL_DURATION_DAYS = (300, 380)
XBRL_QUARTER_DERIVATION_RULE = (
    "DIRECT_70_110_DAY_QUARTER_FIRST;Q1_YTD_EQ_QUARTER;"
    "Q2_Q3_CURRENT_YTD_MINUS_PREVIOUS_PIT_YTD;Q4_FY_MINUS_PIT_Q1_Q2_Q3"
)
XBRL_PRIOR_ASSET_RULE = "MOST_RECENT_PRIOR_FISCAL_PERIOD_END_ASSETS_ACCEPTED_BY_CURRENT_DECISION_MAX_200_DAYS"
XBRL_GROSS_PROFIT_RULE = "DIRECT_GROSS_PROFIT_FIRST_ELSE_REVENUE_MINUS_COST_SAME_ACCESSION_PERIOD"
XBRL_REVENUE_TAG_PRECEDENCE = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
XBRL_COST_TAG_PRECEDENCE = ("CostOfRevenue", "CostOfGoodsAndServicesSold")
XBRL_YOY_RULE = "SAME_ISSUER_SAME_FISCAL_QUARTER_PRIOR_FY_ORIGINAL_PIT_FEATURE_VERSION"
XBRL_FEATURES = {
    "gross_profitability": "quarter_gross_profit/lagged_assets",
    "cash_profitability": "quarter_operating_cash_flow/lagged_assets",
    "accrual_intensity": "(quarter_net_income-quarter_operating_cash_flow)/lagged_assets",
}


@dataclass(frozen=True, slots=True)
class XBRLHypothesisSpec:
    candidate_id: str
    feature: str
    direction: str
    delta_rule: str


XBRL_HYPOTHESES = (
    XBRLHypothesisSpec("gross_profitability_improvement_long", "gross_profitability", "LONG", "current-prior_year>0"),
    XBRLHypothesisSpec("gross_profitability_deterioration_short", "gross_profitability", "SHORT", "current-prior_year<0"),
    XBRLHypothesisSpec("cash_profitability_improvement_long", "cash_profitability", "LONG", "current-prior_year>0"),
    XBRLHypothesisSpec("cash_profitability_deterioration_short", "cash_profitability", "SHORT", "current-prior_year<0"),
    XBRLHypothesisSpec("accrual_quality_improvement_long", "accrual_intensity", "LONG", "current-prior_year<0"),
    XBRLHypothesisSpec("accrual_quality_deterioration_short", "accrual_intensity", "SHORT", "current-prior_year>0"),
)

XBRL_ENTRY_RULE = "DECISION_SESSION_OPEN"
XBRL_EXIT_RULE = "CLOSE_63_XNYS_SESSIONS_AFTER_DECISION"
XBRL_PRIMARY_HORIZON_SESSIONS = 63
XBRL_DIAGNOSTIC_HORIZONS_SESSIONS = (21, 126)
XBRL_BENCHMARK = "SPY"
XBRL_PRIMARY_RETURN = (
    "direction*(stock_open_to_t63_close_return-SPY_open_to_t63_close_return)-direction_specific_cost"
)
XBRL_UNHEDGED_RETURN = "direction*stock_open_to_t63_close_return-direction_specific_cost"
XBRL_PRIMARY_COST_BPS = {"LONG": 10.0, "SHORT": 35.0}
XBRL_STRESS_COST_BPS = {"LONG": 25.0, "SHORT": 100.0}
XBRL_SHORT_BORROW_ASSUMPTION = (
    "PRIMARY_100_BPS_ANNUALIZED_PLUS_EXECUTION;STRESS_300_BPS_ANNUALIZED_PLUS_EXECUTION"
)

XBRL_DEVELOPMENT_SELECTION_FRACTION = 0.70
XBRL_INTERNAL_PURGE_SESSIONS = 63
XBRL_SELECTION_FOLDS = 4
XBRL_INTERNAL_VALIDATION_FOLDS = 3
XBRL_PROTECTED_FOLDS = 4
XBRL_BOOTSTRAP_BLOCK_SESSIONS = 63
XBRL_BOOTSTRAP_REPLICATES = 2000
XBRL_BOOTSTRAP_SEED = 330033
XBRL_SELECTION_CONFIDENCE = 0.95
XBRL_INTERNAL_CONFIDENCE = 0.90
XBRL_PROTECTED_CONFIDENCE = 0.80

XBRL_SELECTION_MIN_EVENT_ROWS = 250
XBRL_SELECTION_MIN_SIGNAL_SESSIONS = 120
XBRL_SELECTION_MIN_UNIQUE_INSTRUMENTS = 50
XBRL_SELECTION_MIN_POSITIVE_FOLDS = 3
XBRL_INTERNAL_MIN_EVENT_ROWS = 60
XBRL_INTERNAL_MIN_SIGNAL_SESSIONS = 30
XBRL_INTERNAL_MIN_UNIQUE_INSTRUMENTS = 20
XBRL_INTERNAL_MIN_POSITIVE_FOLDS = 2
XBRL_PROTECTED_MIN_EVENT_ROWS = 75
XBRL_PROTECTED_MIN_SIGNAL_SESSIONS = 30
XBRL_PROTECTED_MIN_UNIQUE_INSTRUMENTS = 25
XBRL_PROTECTED_MIN_POSITIVE_FOLDS = 2
XBRL_MIN_POSITIVE_YEAR_FRACTION = 0.60
XBRL_MIN_YEAR_SIGNAL_SESSIONS = 15
XBRL_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10
XBRL_MAX_SINGLE_INSTRUMENT_ROW_FRACTION = 0.05

XBRL_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_6"
XBRL_MULTIPLE_TESTING_ALPHA = 0.05
XBRL_SELECTION_WINNER_RULE = "highest_primary_selection_LCB_then_candidate_id"
XBRL_MAX_SELECTION_WINNERS_PER_DIRECTION = 1
XBRL_MAX_FINALISTS_PER_DIRECTION = 1
XBRL_RUNNER_UP_SUBSTITUTION_ALLOWED = False
XBRL_PRIMARY_MEAN_POSITIVE_REQUIRED = True
XBRL_PRIMARY_LCB_POSITIVE_REQUIRED = True
XBRL_STRESS_MEAN_POSITIVE_REQUIRED = True
XBRL_UNHEDGED_PRIMARY_MEAN_POSITIVE_REQUIRED = True
XBRL_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED = True

XBRL_PROTECTED_SOURCE_ONLY_PRECHECK_REQUIRED = True
XBRL_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False
XBRL_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED = True
XBRL_PROTECTED_HOLDOUT_CONSUMED_AFTER_ANY_NONEMPTY_RETURN_READ = True
XBRL_PROVIDER_WRITES = 0
XBRL_BROKER_READS = 0
XBRL_BROKER_WRITES = 0
XBRL_ORDER_WRITES = 0
XBRL_PAPER_SUBMITS = 0
XBRL_LIVE_WRITES = 0
XBRL_AUTOMATION_WRITES = 0
XBRL_AUTOMATIC_BROKER_FAILOVER = False
XBRL_PHASE33_SIGNAL_TO_TRADE_AUTHORITY = False


def _policy_payload() -> dict[str, object]:
    return {
        "contract_version": XBRL_SCIENTIFIC_CONTRACT,
        "entry_source_repair_contract": XBRL_ENTRY_SOURCE_REPAIR_CONTRACT,
        "entry_source_repair_fingerprint": XBRL_ENTRY_SOURCE_REPAIR_FINGERPRINT,
        "entry_source_repair_status": XBRL_ENTRY_SOURCE_REPAIR_STATUS,
        "entry_source_repair_replayed_identity_decisions": XBRL_ENTRY_REPLAYED_IDENTITY_DECISIONS,
        "entry_source_repair_unambiguous_mappings": XBRL_ENTRY_UNAMBIGUOUS_MAPPINGS,
        "entry_source_repair_issuers_with_3_mappings": XBRL_ENTRY_ISSUERS_WITH_3_MAPPINGS,
        "entry_v1_report_sha256": XBRL_ENTRY_V1_REPORT_SHA256,
        "mechanism": XBRL_MECHANISM,
        "study_cik_population": XBRL_STUDY_CIK_POPULATION,
        "predictor_source_start": XBRL_PREDICTOR_SOURCE_START,
        "predictor_source_cutoff": XBRL_PREDICTOR_SOURCE_CUTOFF,
        "performance_signal_start": XBRL_PERFORMANCE_SIGNAL_START,
        "development_last_signal": XBRL_DEVELOPMENT_LAST_SIGNAL,
        "outer_embargo_start": XBRL_OUTER_EMBARGO_START,
        "outer_embargo_end": XBRL_OUTER_EMBARGO_END,
        "protected_start": XBRL_PROTECTED_START,
        "protected_last_signal": XBRL_PROTECTED_LAST_SIGNAL,
        "protected_outcome_end": XBRL_PROTECTED_OUTCOME_END,
        "public_availability_rule": XBRL_PUBLIC_AVAILABILITY_RULE,
        "instrument_rule": XBRL_INSTRUMENT_RULE,
        "instant_fact_rule": XBRL_INSTANT_FACT_RULE,
        "duration_fact_rule": XBRL_DURATION_FACT_RULE,
        "quarter_direct_duration_days": list(XBRL_QUARTER_DIRECT_DURATION_DAYS),
        "annual_duration_days": list(XBRL_ANNUAL_DURATION_DAYS),
        "quarter_derivation_rule": XBRL_QUARTER_DERIVATION_RULE,
        "prior_asset_rule": XBRL_PRIOR_ASSET_RULE,
        "gross_profit_rule": XBRL_GROSS_PROFIT_RULE,
        "revenue_tag_precedence": list(XBRL_REVENUE_TAG_PRECEDENCE),
        "cost_tag_precedence": list(XBRL_COST_TAG_PRECEDENCE),
        "yoy_rule": XBRL_YOY_RULE,
        "features": dict(XBRL_FEATURES),
        "hypotheses": [asdict(spec) for spec in XBRL_HYPOTHESES],
        "entry_rule": XBRL_ENTRY_RULE,
        "exit_rule": XBRL_EXIT_RULE,
        "primary_horizon_sessions": XBRL_PRIMARY_HORIZON_SESSIONS,
        "diagnostic_horizons_sessions": list(XBRL_DIAGNOSTIC_HORIZONS_SESSIONS),
        "benchmark": XBRL_BENCHMARK,
        "primary_return": XBRL_PRIMARY_RETURN,
        "unhedged_return": XBRL_UNHEDGED_RETURN,
        "primary_cost_bps": dict(XBRL_PRIMARY_COST_BPS),
        "stress_cost_bps": dict(XBRL_STRESS_COST_BPS),
        "short_borrow_assumption": XBRL_SHORT_BORROW_ASSUMPTION,
        "development_selection_fraction": XBRL_DEVELOPMENT_SELECTION_FRACTION,
        "internal_purge_sessions": XBRL_INTERNAL_PURGE_SESSIONS,
        "selection_folds": XBRL_SELECTION_FOLDS,
        "internal_validation_folds": XBRL_INTERNAL_VALIDATION_FOLDS,
        "protected_folds": XBRL_PROTECTED_FOLDS,
        "bootstrap_block_sessions": XBRL_BOOTSTRAP_BLOCK_SESSIONS,
        "bootstrap_replicates": XBRL_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": XBRL_BOOTSTRAP_SEED,
        "selection_confidence": XBRL_SELECTION_CONFIDENCE,
        "internal_confidence": XBRL_INTERNAL_CONFIDENCE,
        "protected_confidence": XBRL_PROTECTED_CONFIDENCE,
        "selection_min_event_rows": XBRL_SELECTION_MIN_EVENT_ROWS,
        "selection_min_signal_sessions": XBRL_SELECTION_MIN_SIGNAL_SESSIONS,
        "selection_min_unique_instruments": XBRL_SELECTION_MIN_UNIQUE_INSTRUMENTS,
        "selection_min_positive_folds": XBRL_SELECTION_MIN_POSITIVE_FOLDS,
        "internal_min_event_rows": XBRL_INTERNAL_MIN_EVENT_ROWS,
        "internal_min_signal_sessions": XBRL_INTERNAL_MIN_SIGNAL_SESSIONS,
        "internal_min_unique_instruments": XBRL_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
        "internal_min_positive_folds": XBRL_INTERNAL_MIN_POSITIVE_FOLDS,
        "protected_min_event_rows": XBRL_PROTECTED_MIN_EVENT_ROWS,
        "protected_min_signal_sessions": XBRL_PROTECTED_MIN_SIGNAL_SESSIONS,
        "protected_min_unique_instruments": XBRL_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
        "protected_min_positive_folds": XBRL_PROTECTED_MIN_POSITIVE_FOLDS,
        "min_positive_year_fraction": XBRL_MIN_POSITIVE_YEAR_FRACTION,
        "min_year_signal_sessions": XBRL_MIN_YEAR_SIGNAL_SESSIONS,
        "max_single_session_row_fraction": XBRL_MAX_SINGLE_SESSION_ROW_FRACTION,
        "max_single_instrument_row_fraction": XBRL_MAX_SINGLE_INSTRUMENT_ROW_FRACTION,
        "multiple_testing_method": XBRL_MULTIPLE_TESTING_METHOD,
        "multiple_testing_alpha": XBRL_MULTIPLE_TESTING_ALPHA,
        "selection_winner_rule": XBRL_SELECTION_WINNER_RULE,
        "max_selection_winners_per_direction": XBRL_MAX_SELECTION_WINNERS_PER_DIRECTION,
        "max_finalists_per_direction": XBRL_MAX_FINALISTS_PER_DIRECTION,
        "runner_up_substitution_allowed": XBRL_RUNNER_UP_SUBSTITUTION_ALLOWED,
        "primary_mean_positive_required": XBRL_PRIMARY_MEAN_POSITIVE_REQUIRED,
        "primary_lcb_positive_required": XBRL_PRIMARY_LCB_POSITIVE_REQUIRED,
        "stress_mean_positive_required": XBRL_STRESS_MEAN_POSITIVE_REQUIRED,
        "unhedged_primary_mean_positive_required": XBRL_UNHEDGED_PRIMARY_MEAN_POSITIVE_REQUIRED,
        "deflated_performance_diagnostic_required": XBRL_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED,
        "protected_source_only_precheck_required": XBRL_PROTECTED_SOURCE_ONLY_PRECHECK_REQUIRED,
        "protected_returns_before_finalists_allowed": XBRL_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        "protected_predictors_before_finalists_allowed": XBRL_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED,
        "protected_holdout_consumed_after_any_nonempty_return_read": XBRL_PROTECTED_HOLDOUT_CONSUMED_AFTER_ANY_NONEMPTY_RETURN_READ,
        "provider_writes": XBRL_PROVIDER_WRITES,
        "broker_reads": XBRL_BROKER_READS,
        "broker_writes": XBRL_BROKER_WRITES,
        "order_writes": XBRL_ORDER_WRITES,
        "paper_submits": XBRL_PAPER_SUBMITS,
        "live_writes": XBRL_LIVE_WRITES,
        "automation_writes": XBRL_AUTOMATION_WRITES,
        "automatic_broker_failover": XBRL_AUTOMATIC_BROKER_FAILOVER,
        "phase33_signal_to_trade_authority": XBRL_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    }


def xbrl_scientific_fingerprint() -> str:
    encoded = json.dumps(_policy_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def scientific_contract_snapshot() -> dict[str, object]:
    return {**_policy_payload(), "fingerprint": xbrl_scientific_fingerprint()}
