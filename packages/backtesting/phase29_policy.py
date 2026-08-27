from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


PHASE29_POLICY_CONTRACT_VERSION = (
    "phase29-policy-v1-relative-value-pca-distance-mean-reversion"
)
PHASE29_SOURCE_PHASE28_MERGE = "285f112d51463dd1e06ea4e874a882ad98f71dc5"
PHASE29_SOURCE_PHASE26_POLICY_FINGERPRINT = (
    "24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2"
)
PHASE29_SOURCE_PHASE27_POLICY_FINGERPRINT = (
    "63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0"
)
PHASE29_SOURCE_PHASE28_POLICY_FINGERPRINT = (
    "0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5"
)

PHASE29_RESEARCH_START = "2021-08-16"
PHASE29_DEVELOPMENT_END = "2026-05-06"
PHASE29_OUTER_PURGE_DATES = ("2026-05-07", "2026-05-08", "2026-05-11")
PHASE29_PROTECTED_START = "2026-05-12"
PHASE29_PROTECTED_END = "2026-08-11"
PHASE29_OUTCOME_HORIZON_SESSIONS = 3

# One fixed formation state. No formation-window or component-count search is allowed.
PHASE29_FORMATION_RETURN_SESSIONS = 60
PHASE29_REQUIRED_CLOSES = 62
PHASE29_PCA_COMPONENTS = 3
PHASE29_PCA_MIN_PEERS = 8
PHASE29_PAIR_FORMATION_PRICE_SESSIONS = 60
PHASE29_PAIR_MIN_SPREAD_STD = 1e-8
PHASE29_MIN_DIRECTION_ROWS_PER_SESSION = 5
PHASE29_SIGNAL_TAIL_FRACTION = 0.20

PHASE29_COST_GRID_BPS = (0.0, 5.0, 10.0, 25.0, 50.0)
PHASE29_PRIMARY_COST_BPS = 10.0
PHASE29_STRESS_COST_BPS = 25.0

PHASE29_SELECTION_FRACTION = 0.75
PHASE29_PURGE_SESSIONS = 3
PHASE29_SELECTION_FOLDS = 6
PHASE29_INTERNAL_VALIDATION_FOLDS = 3
PHASE29_PROTECTED_FOLDS = 3

PHASE29_BOOTSTRAP_BLOCK_SESSIONS = 6
PHASE29_BOOTSTRAP_REPLICATES = 2000
PHASE29_BOOTSTRAP_SEED = 290229
PHASE29_SELECTION_CONFIDENCE = 0.95
PHASE29_INTERNAL_CONFIDENCE = 0.90
PHASE29_PROTECTED_CONFIDENCE = 0.80

PHASE29_SELECTION_MIN_RAW_ROWS = 750
PHASE29_SELECTION_MIN_SIGNAL_SESSIONS = 250
PHASE29_SELECTION_MIN_POSITIVE_FOLDS = 5
PHASE29_INTERNAL_MIN_RAW_ROWS = 250
PHASE29_INTERNAL_MIN_SIGNAL_SESSIONS = 80
PHASE29_INTERNAL_MIN_POSITIVE_FOLDS = 2
PHASE29_PROTECTED_MIN_RAW_ROWS = 75
PHASE29_PROTECTED_MIN_SIGNAL_SESSIONS = 24
PHASE29_PROTECTED_MIN_POSITIVE_FOLDS = 2

PHASE29_MIN_POSITIVE_YEAR_FRACTION = 0.60
PHASE29_MIN_POSITIVE_REGIME_FRACTION = 0.50
PHASE29_MIN_YEAR_SIGNAL_SESSIONS = 20
PHASE29_MIN_REGIME_SIGNAL_SESSIONS = 20
PHASE29_MAX_SINGLE_SESSION_ROW_FRACTION = 0.10
PHASE29_MULTIPLE_TESTING_ALPHA = 0.05
PHASE29_MAX_SELECTION_WINNERS_PER_DIRECTION = 1
PHASE29_RUNNER_UP_SUBSTITUTION_ALLOWED = False
PHASE29_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False

PHASE29_PROVIDER_READS = 0
PHASE29_PROVIDER_WRITES = 0
PHASE29_BROKER_READS = 0
PHASE29_BROKER_WRITES = 0
PHASE29_ORDER_WRITES = 0
PHASE29_PAPER_SUBMITS = 0
PHASE29_LIVE_WRITES = 0
PHASE29_AUTOMATION_WRITES = 0
PHASE29_AUTOMATIC_BROKER_FAILOVER = False

PHASE29_RAW_SIGNAL_FIELDS = (
    "pca_residual_dislocation",
    "distance_pair_spread_z",
)

PHASE29_FORBIDDEN_PROTECTED_OUTCOME_FIELDS = (
    "future_close",
    "future_session_date",
    "forward_return",
    "directional_return",
    "primary_net_return",
    "stress_net_return",
)


@dataclass(frozen=True, slots=True)
class Phase29CandidateSpec:
    candidate_id: str
    family: str
    direction: str
    raw_signal_field: str
    orientation: float
    score_semantics: str


PHASE29_CANDIDATES = (
    Phase29CandidateSpec(
        candidate_id="pca_residual_reversion_long",
        family="pca_residual_reversion",
        direction="LONG",
        raw_signal_field="pca_residual_dislocation",
        orientation=-1.0,
        score_semantics="more-negative-current-residual-is-stronger-long-reversion",
    ),
    Phase29CandidateSpec(
        candidate_id="pca_residual_reversion_short",
        family="pca_residual_reversion",
        direction="SHORT",
        raw_signal_field="pca_residual_dislocation",
        orientation=1.0,
        score_semantics="more-positive-current-residual-is-stronger-short-reversion",
    ),
    Phase29CandidateSpec(
        candidate_id="distance_pair_reversion_long",
        family="distance_pair_reversion",
        direction="LONG",
        raw_signal_field="distance_pair_spread_z",
        orientation=-1.0,
        score_semantics="more-negative-current-pair-spread-z-is-stronger-long-reversion",
    ),
    Phase29CandidateSpec(
        candidate_id="distance_pair_reversion_short",
        family="distance_pair_reversion",
        direction="SHORT",
        raw_signal_field="distance_pair_spread_z",
        orientation=1.0,
        score_semantics="more-positive-current-pair-spread-z-is-stronger-short-reversion",
    ),
)


def _policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE29_POLICY_CONTRACT_VERSION,
        "source_phase28_merge": PHASE29_SOURCE_PHASE28_MERGE,
        "source_phase26_policy_fingerprint": PHASE29_SOURCE_PHASE26_POLICY_FINGERPRINT,
        "source_phase27_policy_fingerprint": PHASE29_SOURCE_PHASE27_POLICY_FINGERPRINT,
        "source_phase28_policy_fingerprint": PHASE29_SOURCE_PHASE28_POLICY_FINGERPRINT,
        "research_start": PHASE29_RESEARCH_START,
        "development_end": PHASE29_DEVELOPMENT_END,
        "outer_purge_dates": PHASE29_OUTER_PURGE_DATES,
        "protected_start": PHASE29_PROTECTED_START,
        "protected_end": PHASE29_PROTECTED_END,
        "outcome_horizon_sessions": PHASE29_OUTCOME_HORIZON_SESSIONS,
        "formation_return_sessions": PHASE29_FORMATION_RETURN_SESSIONS,
        "required_closes": PHASE29_REQUIRED_CLOSES,
        "pca_components": PHASE29_PCA_COMPONENTS,
        "pca_min_peers": PHASE29_PCA_MIN_PEERS,
        "pair_formation_price_sessions": PHASE29_PAIR_FORMATION_PRICE_SESSIONS,
        "pair_min_spread_std": PHASE29_PAIR_MIN_SPREAD_STD,
        "min_direction_rows_per_session": PHASE29_MIN_DIRECTION_ROWS_PER_SESSION,
        "signal_tail_fraction": PHASE29_SIGNAL_TAIL_FRACTION,
        "cost_grid_bps": PHASE29_COST_GRID_BPS,
        "primary_cost_bps": PHASE29_PRIMARY_COST_BPS,
        "stress_cost_bps": PHASE29_STRESS_COST_BPS,
        "selection_fraction": PHASE29_SELECTION_FRACTION,
        "purge_sessions": PHASE29_PURGE_SESSIONS,
        "selection_folds": PHASE29_SELECTION_FOLDS,
        "internal_validation_folds": PHASE29_INTERNAL_VALIDATION_FOLDS,
        "protected_folds": PHASE29_PROTECTED_FOLDS,
        "bootstrap_block_sessions": PHASE29_BOOTSTRAP_BLOCK_SESSIONS,
        "bootstrap_replicates": PHASE29_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": PHASE29_BOOTSTRAP_SEED,
        "selection_confidence": PHASE29_SELECTION_CONFIDENCE,
        "internal_confidence": PHASE29_INTERNAL_CONFIDENCE,
        "protected_confidence": PHASE29_PROTECTED_CONFIDENCE,
        "selection_min_raw_rows": PHASE29_SELECTION_MIN_RAW_ROWS,
        "selection_min_signal_sessions": PHASE29_SELECTION_MIN_SIGNAL_SESSIONS,
        "selection_min_positive_folds": PHASE29_SELECTION_MIN_POSITIVE_FOLDS,
        "internal_min_raw_rows": PHASE29_INTERNAL_MIN_RAW_ROWS,
        "internal_min_signal_sessions": PHASE29_INTERNAL_MIN_SIGNAL_SESSIONS,
        "internal_min_positive_folds": PHASE29_INTERNAL_MIN_POSITIVE_FOLDS,
        "protected_min_raw_rows": PHASE29_PROTECTED_MIN_RAW_ROWS,
        "protected_min_signal_sessions": PHASE29_PROTECTED_MIN_SIGNAL_SESSIONS,
        "protected_min_positive_folds": PHASE29_PROTECTED_MIN_POSITIVE_FOLDS,
        "min_positive_year_fraction": PHASE29_MIN_POSITIVE_YEAR_FRACTION,
        "min_positive_regime_fraction": PHASE29_MIN_POSITIVE_REGIME_FRACTION,
        "min_year_signal_sessions": PHASE29_MIN_YEAR_SIGNAL_SESSIONS,
        "min_regime_signal_sessions": PHASE29_MIN_REGIME_SIGNAL_SESSIONS,
        "max_single_session_row_fraction": PHASE29_MAX_SINGLE_SESSION_ROW_FRACTION,
        "multiple_testing_alpha": PHASE29_MULTIPLE_TESTING_ALPHA,
        "max_selection_winners_per_direction": PHASE29_MAX_SELECTION_WINNERS_PER_DIRECTION,
        "runner_up_substitution_allowed": PHASE29_RUNNER_UP_SUBSTITUTION_ALLOWED,
        "protected_returns_before_finalists_allowed": PHASE29_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        "candidate_definitions": [asdict(candidate) for candidate in PHASE29_CANDIDATES],
        "external_authority": {
            "provider_reads": PHASE29_PROVIDER_READS,
            "provider_writes": PHASE29_PROVIDER_WRITES,
            "broker_reads": PHASE29_BROKER_READS,
            "broker_writes": PHASE29_BROKER_WRITES,
            "order_writes": PHASE29_ORDER_WRITES,
            "paper_submits": PHASE29_PAPER_SUBMITS,
            "live_writes": PHASE29_LIVE_WRITES,
            "automation_writes": PHASE29_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE29_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase29_policy_fingerprint() -> str:
    raw = json.dumps(_policy_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
