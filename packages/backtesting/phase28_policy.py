from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal


PHASE28_POLICY_CONTRACT_VERSION = (
    "phase28-policy-v1-cross-stock-lead-lag-residual-network-eight-hypotheses"
)
PHASE28_SOURCE_PHASE26_POLICY_FINGERPRINT = (
    "24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2"
)
PHASE28_SOURCE_PHASE27_POLICY_FINGERPRINT = (
    "63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0"
)
PHASE28_SOURCE_PHASE27_MERGE = "dc015f51232dc66ba94b6175c276a0227d5a3761"

PHASE28_RESEARCH_START = "2021-08-16"
PHASE28_DEVELOPMENT_END = "2026-05-06"
PHASE28_PROTECTED_START = "2026-05-12"
PHASE28_PROTECTED_END = "2026-08-11"
PHASE28_OUTCOME_HORIZON_SESSIONS = 3
PHASE28_PURGE_SESSIONS = 3

PHASE28_COMMON_RETURN_MIN_PEERS = 5
PHASE28_LEAD_LAG_PAIRS = 60
PHASE28_MIN_VALID_LAG_PAIRS = 50
PHASE28_MAX_LEADERS = 3
PHASE28_MIN_LEADERS = 2
PHASE28_RESIDUAL_MOMENTUM_SESSIONS = 20
PHASE28_PEER_MOMENTUM_SESSIONS = 5
PHASE28_MIN_DIRECTION_ROWS_PER_SESSION = 5
PHASE28_SIGNAL_TAIL_FRACTION = 0.20

PHASE28_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)
PHASE28_PRIMARY_COST_BPS = 10.0
PHASE28_STRESS_COST_BPS = 25.0

PHASE28_SELECTION_FRACTION = 0.75
PHASE28_SELECTION_FOLDS = 6
PHASE28_INTERNAL_VALIDATION_FOLDS = 3
PHASE28_PROTECTED_FOLDS = 3

PHASE28_BOOTSTRAP_BLOCK_SESSIONS = 6
PHASE28_BOOTSTRAP_REPLICATES = 2000
PHASE28_BOOTSTRAP_SEED = 280228
PHASE28_SELECTION_CONFIDENCE = 0.95
PHASE28_INTERNAL_CONFIDENCE = 0.90
PHASE28_PROTECTED_CONFIDENCE = 0.80

PHASE28_SELECTION_MIN_RAW_ROWS = 750
PHASE28_SELECTION_MIN_SIGNAL_SESSIONS = 250
PHASE28_INTERNAL_MIN_RAW_ROWS = 250
PHASE28_INTERNAL_MIN_SIGNAL_SESSIONS = 80
PHASE28_PROTECTED_MIN_RAW_ROWS = 75
PHASE28_PROTECTED_MIN_SIGNAL_SESSIONS = 24
PHASE28_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE28_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE28_PROTECTED_MIN_POSITIVE_FOLDS = 2
PHASE28_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE28_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE28_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE28_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE28_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10

PHASE28_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_8"
PHASE28_MULTIPLE_TESTING_ALPHA = 0.05
PHASE28_MAX_SELECTION_WINNERS_PER_DIRECTION = 1
PHASE28_MAX_FINALISTS_PER_DIRECTION = 1
PHASE28_RUNNER_UP_SUBSTITUTION_ALLOWED = False
PHASE28_WIN_RATE_IS_HARD_GATE = False
PHASE28_MEDIAN_RETURN_IS_HARD_GATE = False
PHASE28_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED = True

PHASE28_PROVIDER_READS = 0
PHASE28_PROVIDER_WRITES = 0
PHASE28_BROKER_READS = 0
PHASE28_BROKER_WRITES = 0
PHASE28_ORDER_WRITES = 0
PHASE28_PAPER_SUBMITS = 0
PHASE28_LIVE_WRITES = 0
PHASE28_AUTOMATION_WRITES = 0
PHASE28_AUTOMATIC_BROKER_FAILOVER = False
PHASE28_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False

PHASE28_RAW_SIGNAL_FIELDS: tuple[str, ...] = (
    "residual_momentum_20d",
    "peer_lead_1d",
    "peer_lead_5d",
    "peer_diffusion_gap_1d",
)
PHASE28_ROBUSTNESS_STATE_FIELDS = ("market_state", "effective_ticker_state")
PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS = (
    "future_date",
    "future_close",
    "forward_return",
    "directional_return",
)

StrategyDirection = Literal["LONG", "SHORT"]
SignalFamily = Literal[
    "residual_momentum_20d",
    "peer_lead_1d",
    "peer_lead_5d",
    "peer_diffusion_gap_1d",
]


@dataclass(frozen=True, slots=True)
class Phase28CandidateSpec:
    candidate_id: str
    family: SignalFamily
    direction: StrategyDirection
    score_semantics: str


PHASE28_CANDIDATES: tuple[Phase28CandidateSpec, ...] = (
    Phase28CandidateSpec(
        "residual_momentum_20d_long",
        "residual_momentum_20d",
        "LONG",
        "positive twenty-session focal residual momentum",
    ),
    Phase28CandidateSpec(
        "residual_momentum_20d_short",
        "residual_momentum_20d",
        "SHORT",
        "negative twenty-session focal residual momentum",
    ),
    Phase28CandidateSpec(
        "peer_lead_1d_long",
        "peer_lead_1d",
        "LONG",
        "positive weighted current-session residual return of frozen leaders",
    ),
    Phase28CandidateSpec(
        "peer_lead_1d_short",
        "peer_lead_1d",
        "SHORT",
        "negative weighted current-session residual return of frozen leaders",
    ),
    Phase28CandidateSpec(
        "peer_lead_5d_long",
        "peer_lead_5d",
        "LONG",
        "positive weighted five-session residual momentum of frozen leaders",
    ),
    Phase28CandidateSpec(
        "peer_lead_5d_short",
        "peer_lead_5d",
        "SHORT",
        "negative weighted five-session residual momentum of frozen leaders",
    ),
    Phase28CandidateSpec(
        "peer_diffusion_gap_1d_long",
        "peer_diffusion_gap_1d",
        "LONG",
        "positive leader residual return minus focal residual return",
    ),
    Phase28CandidateSpec(
        "peer_diffusion_gap_1d_short",
        "peer_diffusion_gap_1d",
        "SHORT",
        "negative leader residual return minus focal residual return",
    ),
)


def phase28_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE28_POLICY_CONTRACT_VERSION,
        "source_phase26_policy_fingerprint": PHASE28_SOURCE_PHASE26_POLICY_FINGERPRINT,
        "source_phase27_policy_fingerprint": PHASE28_SOURCE_PHASE27_POLICY_FINGERPRINT,
        "source_phase27_merge": PHASE28_SOURCE_PHASE27_MERGE,
        "research_start": PHASE28_RESEARCH_START,
        "development_end": PHASE28_DEVELOPMENT_END,
        "protected_start": PHASE28_PROTECTED_START,
        "protected_end": PHASE28_PROTECTED_END,
        "outcome_horizon_sessions": PHASE28_OUTCOME_HORIZON_SESSIONS,
        "purge_sessions": PHASE28_PURGE_SESSIONS,
        "network": {
            "common_return_method": "CROSS_SECTIONAL_MEDIAN_RAW_RETURN",
            "common_return_min_peers": PHASE28_COMMON_RETURN_MIN_PEERS,
            "lead_lag_pairs": PHASE28_LEAD_LAG_PAIRS,
            "min_valid_lag_pairs": PHASE28_MIN_VALID_LAG_PAIRS,
            "forward_corr_definition": "corr(peer_residual[s-1], focal_residual[s])",
            "reverse_corr_definition": "corr(focal_residual[s-1], peer_residual[s])",
            "asymmetry_definition": "forward_corr - reverse_corr",
            "leader_requires_forward_corr_positive": True,
            "leader_requires_asymmetry_positive": True,
            "max_leaders": PHASE28_MAX_LEADERS,
            "min_leaders": PHASE28_MIN_LEADERS,
            "leader_weight": "NORMALIZED_POSITIVE_ASYMMETRY",
            "network_estimation_end": "T_MINUS_1",
            "identity_safe_interval_required": True,
            "split_free_lookback_required": True,
        },
        "signals": {
            "raw_signal_fields": list(PHASE28_RAW_SIGNAL_FIELDS),
            "residual_momentum_sessions": PHASE28_RESIDUAL_MOMENTUM_SESSIONS,
            "peer_momentum_sessions": PHASE28_PEER_MOMENTUM_SESSIONS,
            "all_signals_complete_case_required": True,
            "long_score_orientation": 1,
            "short_score_orientation": -1,
        },
        "min_direction_rows_per_session": PHASE28_MIN_DIRECTION_ROWS_PER_SESSION,
        "signal_tail_fraction": PHASE28_SIGNAL_TAIL_FRACTION,
        "candidates": [asdict(candidate) for candidate in PHASE28_CANDIDATES],
        "selection_fraction": PHASE28_SELECTION_FRACTION,
        "selection_folds": PHASE28_SELECTION_FOLDS,
        "internal_validation_folds": PHASE28_INTERNAL_VALIDATION_FOLDS,
        "protected_folds": PHASE28_PROTECTED_FOLDS,
        "cost_grid_bps": list(PHASE28_COST_GRID_BPS),
        "primary_cost_bps": PHASE28_PRIMARY_COST_BPS,
        "stress_cost_bps": PHASE28_STRESS_COST_BPS,
        "bootstrap_block_sessions": PHASE28_BOOTSTRAP_BLOCK_SESSIONS,
        "bootstrap_replicates": PHASE28_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": PHASE28_BOOTSTRAP_SEED,
        "selection_confidence": PHASE28_SELECTION_CONFIDENCE,
        "internal_confidence": PHASE28_INTERNAL_CONFIDENCE,
        "protected_confidence": PHASE28_PROTECTED_CONFIDENCE,
        "selection_min_raw_rows": PHASE28_SELECTION_MIN_RAW_ROWS,
        "selection_min_signal_sessions": PHASE28_SELECTION_MIN_SIGNAL_SESSIONS,
        "internal_min_raw_rows": PHASE28_INTERNAL_MIN_RAW_ROWS,
        "internal_min_signal_sessions": PHASE28_INTERNAL_MIN_SIGNAL_SESSIONS,
        "protected_min_raw_rows": PHASE28_PROTECTED_MIN_RAW_ROWS,
        "protected_min_signal_sessions": PHASE28_PROTECTED_MIN_SIGNAL_SESSIONS,
        "selection_min_positive_folds": PHASE28_SELECTION_MIN_POSITIVE_FOLDS,
        "internal_min_positive_folds": PHASE28_INTERNAL_MIN_POSITIVE_FOLDS,
        "protected_min_positive_folds": PHASE28_PROTECTED_MIN_POSITIVE_FOLDS,
        "min_positive_year_fraction": PHASE28_MIN_POSITIVE_YEAR_FRACTION,
        "min_year_signal_sessions": PHASE28_MIN_YEAR_SIGNAL_SESSIONS,
        "min_positive_regime_fraction": PHASE28_MIN_POSITIVE_REGIME_FRACTION,
        "min_regime_signal_sessions": PHASE28_MIN_REGIME_SIGNAL_SESSIONS,
        "max_single_session_row_fraction": PHASE28_MAX_SINGLE_SESSION_ROW_FRACTION,
        "robustness_state_fields": list(PHASE28_ROBUSTNESS_STATE_FIELDS),
        "multiple_testing_method": PHASE28_MULTIPLE_TESTING_METHOD,
        "multiple_testing_alpha": PHASE28_MULTIPLE_TESTING_ALPHA,
        "max_selection_winners_per_direction": PHASE28_MAX_SELECTION_WINNERS_PER_DIRECTION,
        "max_finalists_per_direction": PHASE28_MAX_FINALISTS_PER_DIRECTION,
        "runner_up_substitution_allowed": PHASE28_RUNNER_UP_SUBSTITUTION_ALLOWED,
        "win_rate_is_hard_gate": PHASE28_WIN_RATE_IS_HARD_GATE,
        "median_return_is_hard_gate": PHASE28_MEDIAN_RETURN_IS_HARD_GATE,
        "deflated_performance_diagnostic_required": PHASE28_DEFLATED_PERFORMANCE_DIAGNOSTIC_REQUIRED,
        "forbidden_protected_outcome_fields": list(PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS),
        "protected_returns_before_finalists_allowed": PHASE28_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        "external_authority": {
            "provider_reads": PHASE28_PROVIDER_READS,
            "provider_writes": PHASE28_PROVIDER_WRITES,
            "broker_reads": PHASE28_BROKER_READS,
            "broker_writes": PHASE28_BROKER_WRITES,
            "order_writes": PHASE28_ORDER_WRITES,
            "paper_submits": PHASE28_PAPER_SUBMITS,
            "live_writes": PHASE28_LIVE_WRITES,
            "automation_writes": PHASE28_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE28_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase28_policy_fingerprint() -> str:
    payload = json.dumps(
        phase28_policy_payload(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
