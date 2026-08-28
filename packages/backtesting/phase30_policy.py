from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal


PHASE30_POLICY_CONTRACT_VERSION = (
    "phase30-policy-v1-metadata-only-news-shock-confirmation-four-hypotheses"
)
PHASE30_SOURCE_PHASE29_MERGE = "87c9450e1b21606b83489f16ff326235ae92eb2b"
PHASE30_SOURCE_FEASIBILITY_FINGERPRINT = (
    "04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312"
)

PHASE30_RESEARCH_START = "2021-08-16"
PHASE30_DEVELOPMENT_END = "2026-05-06"
PHASE30_OUTER_PURGE_DATES = ("2026-05-07", "2026-05-08", "2026-05-11")
PHASE30_PROTECTED_START = "2026-05-12"
PHASE30_PROTECTED_END = "2026-08-11"
PHASE30_NEWS_WARMUP_START = "2021-07-16"
PHASE30_OUTCOME_HORIZON_SESSIONS = 3

# Point-in-time event timing. A publication belongs to the first XNYS session whose
# official close is at least this many minutes after publication. This handles normal
# and shortened sessions without inventing a fixed wall-clock close.
PHASE30_DECISION_BUFFER_MINUTES = 30

# Only event identity/timing/linkage may drive Phase30 alpha. Provider text and model
# output remain provenance because the feasibility gate did not establish historical
# revision/model-vintage semantics for those fields.
PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS = ("id", "published_utc", "tickers")
PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY = False
PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY = False

# News-shock construction: exact ticker-session article count relative to the prior
# 20 XNYS sessions, including zero-news sessions. The transform is deterministic and
# has no fitted parameters.
PHASE30_NEWS_BASELINE_SESSIONS = 20
PHASE30_NEWS_SURPRISE_TRANSFORM = (
    "log1p(current_unique_article_count)-mean(log1p(previous_20_session_counts_with_zeros))"
)
PHASE30_CURRENT_REACTION_FIELD = "d1_return_1"
PHASE30_MIN_DIRECTION_ROWS_PER_SESSION = 5
PHASE30_SIGNAL_TAIL_FRACTION = 0.20

PHASE30_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)
PHASE30_PRIMARY_COST_BPS = 10.0
PHASE30_STRESS_COST_BPS = 25.0

PHASE30_SELECTION_FRACTION = 0.75
PHASE30_PURGE_SESSIONS = 3
PHASE30_SELECTION_FOLDS = 6
PHASE30_INTERNAL_VALIDATION_FOLDS = 3
PHASE30_PROTECTED_FOLDS = 3

PHASE30_BOOTSTRAP_BLOCK_SESSIONS = 6
PHASE30_BOOTSTRAP_REPLICATES = 2000
PHASE30_BOOTSTRAP_SEED = 300230
PHASE30_SELECTION_CONFIDENCE = 0.95
PHASE30_INTERNAL_CONFIDENCE = 0.90
PHASE30_PROTECTED_CONFIDENCE = 0.80

PHASE30_SELECTION_MIN_RAW_ROWS = 750
PHASE30_SELECTION_MIN_SIGNAL_SESSIONS = 250
PHASE30_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE30_INTERNAL_MIN_RAW_ROWS = 250
PHASE30_INTERNAL_MIN_SIGNAL_SESSIONS = 80
PHASE30_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE30_PROTECTED_MIN_RAW_ROWS = 75
PHASE30_PROTECTED_MIN_SIGNAL_SESSIONS = 24
PHASE30_PROTECTED_MIN_POSITIVE_FOLDS = 2

PHASE30_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE30_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE30_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE30_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE30_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10
PHASE30_MAX_SINGLE_TICKER_ROW_FRACTION = 0.10

PHASE30_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_4"
PHASE30_MULTIPLE_TESTING_ALPHA = 0.05
PHASE30_MAX_SELECTION_WINNERS_PER_DIRECTION = 1
PHASE30_MAX_FINALISTS_PER_DIRECTION = 1
PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED = False
PHASE30_WIN_RATE_IS_HARD_GATE = False
PHASE30_MEDIAN_RETURN_IS_HARD_GATE = False
PHASE30_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED = True
PHASE30_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False

PHASE30_PROVIDER_READS_ALLOWED = True
PHASE30_PROVIDER_WRITES = 0
PHASE30_BROKER_READS = 0
PHASE30_BROKER_WRITES = 0
PHASE30_ORDER_WRITES = 0
PHASE30_PAPER_SUBMITS = 0
PHASE30_LIVE_WRITES = 0
PHASE30_AUTOMATION_WRITES = 0
PHASE30_AUTOMATIC_BROKER_FAILOVER = False

StrategyDirection = Literal["LONG", "SHORT"]
ReactionSign = Literal["POSITIVE", "NEGATIVE"]


@dataclass(frozen=True, slots=True)
class Phase30CandidateSpec:
    candidate_id: str
    family: str
    direction: StrategyDirection
    required_reaction_sign: ReactionSign
    score_field: str
    score_orientation: float
    thesis: str


PHASE30_CANDIDATES = (
    Phase30CandidateSpec(
        candidate_id="news_shock_aligned_continuation_long",
        family="news_shock_aligned_continuation",
        direction="LONG",
        required_reaction_sign="POSITIVE",
        score_field="news_surprise",
        score_orientation=1.0,
        thesis=(
            "Confirm an existing LONG production candidate when unusual public-news "
            "arrival coincides with a positive finalized-session market reaction."
        ),
    ),
    Phase30CandidateSpec(
        candidate_id="news_shock_aligned_continuation_short",
        family="news_shock_aligned_continuation",
        direction="SHORT",
        required_reaction_sign="NEGATIVE",
        score_field="news_surprise",
        score_orientation=1.0,
        thesis=(
            "Confirm an existing SHORT production candidate when unusual public-news "
            "arrival coincides with a negative finalized-session market reaction."
        ),
    ),
    Phase30CandidateSpec(
        candidate_id="news_shock_counterreaction_reversal_long",
        family="news_shock_counterreaction_reversal",
        direction="LONG",
        required_reaction_sign="NEGATIVE",
        score_field="news_surprise",
        score_orientation=1.0,
        thesis=(
            "Confirm an existing LONG production candidate only if an unusual news "
            "arrival produced an opposing negative session reaction that subsequently "
            "reverses toward the pre-existing LONG thesis."
        ),
    ),
    Phase30CandidateSpec(
        candidate_id="news_shock_counterreaction_reversal_short",
        family="news_shock_counterreaction_reversal",
        direction="SHORT",
        required_reaction_sign="POSITIVE",
        score_field="news_surprise",
        score_orientation=1.0,
        thesis=(
            "Confirm an existing SHORT production candidate only if an unusual news "
            "arrival produced an opposing positive session reaction that subsequently "
            "reverses toward the pre-existing SHORT thesis."
        ),
    ),
)


def phase30_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE30_POLICY_CONTRACT_VERSION,
        "source_phase29_merge": PHASE30_SOURCE_PHASE29_MERGE,
        "source_feasibility_fingerprint": PHASE30_SOURCE_FEASIBILITY_FINGERPRINT,
        "research_start": PHASE30_RESEARCH_START,
        "development_end": PHASE30_DEVELOPMENT_END,
        "outer_purge_dates": PHASE30_OUTER_PURGE_DATES,
        "protected_start": PHASE30_PROTECTED_START,
        "protected_end": PHASE30_PROTECTED_END,
        "news_warmup_start": PHASE30_NEWS_WARMUP_START,
        "outcome_horizon_sessions": PHASE30_OUTCOME_HORIZON_SESSIONS,
        "decision_buffer_minutes": PHASE30_DECISION_BUFFER_MINUTES,
        "authorized_news_alpha_fields": PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS,
        "provider_content_alpha_authority": PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
        "provider_insights_alpha_authority": PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
        "news_baseline_sessions": PHASE30_NEWS_BASELINE_SESSIONS,
        "news_surprise_transform": PHASE30_NEWS_SURPRISE_TRANSFORM,
        "current_reaction_field": PHASE30_CURRENT_REACTION_FIELD,
        "min_direction_rows_per_session": PHASE30_MIN_DIRECTION_ROWS_PER_SESSION,
        "signal_tail_fraction": PHASE30_SIGNAL_TAIL_FRACTION,
        "candidate_definitions": [asdict(candidate) for candidate in PHASE30_CANDIDATES],
        "cost_grid_bps": PHASE30_COST_GRID_BPS,
        "primary_cost_bps": PHASE30_PRIMARY_COST_BPS,
        "stress_cost_bps": PHASE30_STRESS_COST_BPS,
        "selection_fraction": PHASE30_SELECTION_FRACTION,
        "purge_sessions": PHASE30_PURGE_SESSIONS,
        "selection_folds": PHASE30_SELECTION_FOLDS,
        "internal_validation_folds": PHASE30_INTERNAL_VALIDATION_FOLDS,
        "protected_folds": PHASE30_PROTECTED_FOLDS,
        "bootstrap_block_sessions": PHASE30_BOOTSTRAP_BLOCK_SESSIONS,
        "bootstrap_replicates": PHASE30_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": PHASE30_BOOTSTRAP_SEED,
        "selection_confidence": PHASE30_SELECTION_CONFIDENCE,
        "internal_confidence": PHASE30_INTERNAL_CONFIDENCE,
        "protected_confidence": PHASE30_PROTECTED_CONFIDENCE,
        "selection_min_raw_rows": PHASE30_SELECTION_MIN_RAW_ROWS,
        "selection_min_signal_sessions": PHASE30_SELECTION_MIN_SIGNAL_SESSIONS,
        "selection_min_positive_folds": PHASE30_SELECTION_MIN_POSITIVE_FOLDS,
        "internal_min_raw_rows": PHASE30_INTERNAL_MIN_RAW_ROWS,
        "internal_min_signal_sessions": PHASE30_INTERNAL_MIN_SIGNAL_SESSIONS,
        "internal_min_positive_folds": PHASE30_INTERNAL_MIN_POSITIVE_FOLDS,
        "protected_min_raw_rows": PHASE30_PROTECTED_MIN_RAW_ROWS,
        "protected_min_signal_sessions": PHASE30_PROTECTED_MIN_SIGNAL_SESSIONS,
        "protected_min_positive_folds": PHASE30_PROTECTED_MIN_POSITIVE_FOLDS,
        "min_positive_year_fraction": PHASE30_MIN_POSITIVE_YEAR_FRACTION,
        "min_positive_regime_fraction": PHASE30_MIN_POSITIVE_REGIME_FRACTION,
        "min_year_signal_sessions": PHASE30_MIN_YEAR_SIGNAL_SESSIONS,
        "min_regime_signal_sessions": PHASE30_MIN_REGIME_SIGNAL_SESSIONS,
        "max_single_session_row_fraction": PHASE30_MAX_SINGLE_SESSION_ROW_FRACTION,
        "max_single_ticker_row_fraction": PHASE30_MAX_SINGLE_TICKER_ROW_FRACTION,
        "multiple_testing_method": PHASE30_MULTIPLE_TESTING_METHOD,
        "multiple_testing_alpha": PHASE30_MULTIPLE_TESTING_ALPHA,
        "max_selection_winners_per_direction": PHASE30_MAX_SELECTION_WINNERS_PER_DIRECTION,
        "max_finalists_per_direction": PHASE30_MAX_FINALISTS_PER_DIRECTION,
        "runner_up_substitution_allowed": PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED,
        "win_rate_is_hard_gate": PHASE30_WIN_RATE_IS_HARD_GATE,
        "median_return_is_hard_gate": PHASE30_MEDIAN_RETURN_IS_HARD_GATE,
        "deflated_performance_diagnostic_required": PHASE30_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED,
        "protected_returns_before_finalists_allowed": PHASE30_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        "protected_holdout_consumed_after_any_nonempty_phase30_protected_return_read": True,
        "external_authority": {
            "provider_reads_allowed": PHASE30_PROVIDER_READS_ALLOWED,
            "provider_writes": PHASE30_PROVIDER_WRITES,
            "broker_reads": PHASE30_BROKER_READS,
            "broker_writes": PHASE30_BROKER_WRITES,
            "order_writes": PHASE30_ORDER_WRITES,
            "paper_submits": PHASE30_PAPER_SUBMITS,
            "live_writes": PHASE30_LIVE_WRITES,
            "automation_writes": PHASE30_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE30_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase30_policy_fingerprint() -> str:
    raw = json.dumps(
        phase30_policy_payload(), sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
