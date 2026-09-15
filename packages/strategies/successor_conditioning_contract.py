from __future__ import annotations

import hashlib
import json
from typing import Final


SUCCESSOR_CONDITIONING_CONTRACT: Final[str] = (
    "atlas-successor-conditioning-v1-training-only-walk-forward-research-no-promotion"
)

# Exact accepted standalone evidence binding. These values identify the completed
# 2026-09-14/15 DEVELOPMENT-only run and are intentionally performance-blind below
# the standalone artifact boundary: this conditioning contract was frozen before
# any route-level or condition-level return aggregates were opened.
ACCEPTED_RUN_CONTRACT_FINGERPRINT: Final[str] = (
    "d962d72579996c26485a292469e6483132b413c484b90471aba74b209993cafb"
)
ACCEPTED_STANDALONE_RUN_FINGERPRINT: Final[str] = (
    "c22bcb45b1a13dde11854f7ad166ae0abe1810fc0d6ab7371dbdd1165c1006e6"
)
ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT: Final[str] = (
    "4e5d66b8db1b37ac70dcff9e92fc4602bb729f90f18852db59f7e827de5a55d6"
)
ACCEPTED_INPUT_MANIFEST_FINGERPRINT: Final[str] = (
    "951baae6f157a730a3aea807288d46004a9e3d75aa71b5caec9a0c810596ec97"
)
ACCEPTED_GROUP_COUNT: Final[int] = 546
ACCEPTED_STANDALONE_RECORD_COUNT: Final[int] = 54_618_427

DEVELOPMENT_START: Final[str] = "2016-01-04"
DEVELOPMENT_END: Final[str] = "2026-04-30"

ROLLING_TRAIN_SESSIONS: Final[int] = 504
WALK_FORWARD_TEST_SESSIONS: Final[int] = 63
WALK_FORWARD_STEP_SESSIONS: Final[int] = 63
WALK_FORWARD_EMBARGO_SESSIONS: Final[int] = 1

MIN_CELL_OPPORTUNITIES: Final[int] = 60
MIN_CELL_UNIQUE_SESSIONS: Final[int] = 30
MIN_CELL_UNIQUE_INSTRUMENTS: Final[int] = 20
SESSION_CLUSTER_BOOTSTRAP_DRAWS: Final[int] = 1000
SELECTOR_LCB_QUANTILE: Final[float] = 0.05

REPORTING_COST_GRID_BPS: Final[tuple[int, ...]] = (0, 10, 25, 50, 100)
DAILY_PRIMARY_HORIZON_SESSIONS: Final[int] = 5
DAILY_PRIMARY_COST_BPS: Final[int] = 10
DAILY_STRESS_COST_BPS: Final[int] = 25
INTRADAY_PRIMARY_COST_BPS: Final[int] = 50
INTRADAY_STRESS_COST_BPS: Final[int] = 100

# Numeric bucket boundaries are frozen before condition performance is opened.
# They intentionally use broad practitioner-readable ranges rather than dense
# parameter grids. Legacy B35 minute rows retain their already-frozen buckets.
BUCKET_CONTRACT: Final[dict[str, object]] = {
    "relative_strength_return_difference": {
        "units": "decimal_return_difference_vs_spy",
        "cuts": [-0.10, -0.03, 0.03, 0.10],
        "labels": ["LE_M10PCT", "M10_TO_M3PCT", "M3_TO_P3PCT", "P3_TO_P10PCT", "GE_P10PCT"],
    },
    "atr_normalized_extension": {
        "units": "ATR_FROM_EMA20_SIGNED",
        "cuts": [-2.0, -1.0, 1.0, 2.0],
        "labels": ["LE_M2ATR", "M2_TO_M1ATR", "M1_TO_P1ATR", "P1_TO_P2ATR", "GE_P2ATR"],
    },
    "participation_ratio": {
        "units": "ratio",
        "cuts": [1.0, 1.5, 2.0, 4.0],
        "labels": ["LT_1", "1_TO_1_5", "1_5_TO_2", "2_TO_4", "GE_4"],
    },
    "prior_dollar_volume": {
        "units": "USD",
        "cuts": [1_000_000.0, 10_000_000.0, 50_000_000.0, 250_000_000.0],
        "labels": ["LT_1M", "1M_TO_10M", "10M_TO_50M", "50M_TO_250M", "GE_250M"],
    },
    "overnight_gap_magnitude": {
        "units": "absolute_decimal_return",
        "cuts": [0.02, 0.05, 0.10],
        "labels": ["LT_2PCT", "2_TO_5PCT", "5_TO_10PCT", "GE_10PCT"],
    },
    "realized_volatility": {
        "units": "annualized_decimal",
        "cuts": [0.25, 0.50, 1.00],
        "labels": ["LT_25PCT", "25_TO_50PCT", "50_TO_100PCT", "GE_100PCT"],
    },
    "signal_time_et": {
        "daily_label": "DAILY_CLOSE",
        "intraday_labels": [
            "0931_TO_0944",
            "0945_TO_1000",
            "1001_TO_1030",
            "1031_TO_1131",
            "1132_TO_1300",
            "1301_TO_1500",
            "1501_TO_CLOSE",
        ],
    },
}

# The first router is deliberately small and interpretable. Direction is explicit.
# More-specific supported cells own their result even when negative; fallback is
# permitted only when the more-specific cell lacks the frozen support minimum.
SELECTOR_FALLBACK_HIERARCHY: Final[tuple[tuple[str, ...], ...]] = (
    (
        "policy_id",
        "direction",
        "market_direction_alignment",
        "market_volatility_state",
        "higher_timeframe_ticker_trend",
        "signal_time_bucket",
        "liquidity_bucket",
    ),
    (
        "policy_id",
        "direction",
        "market_direction_alignment",
        "market_volatility_state",
        "higher_timeframe_ticker_trend",
        "signal_time_bucket",
    ),
    (
        "policy_id",
        "direction",
        "market_direction_alignment",
        "market_volatility_state",
        "higher_timeframe_ticker_trend",
    ),
    (
        "policy_id",
        "direction",
        "market_direction_alignment",
        "higher_timeframe_ticker_trend",
    ),
    ("policy_id", "direction"),
)

# All declared context dimensions are measured. Only the hierarchy above controls
# v1 research eligibility; the remaining slices are diagnostic and cannot be
# promoted or retroactively inserted into this selector after results are viewed.
CONDITION_DIMENSIONS: Final[tuple[str, ...]] = (
    "direction",
    "market_direction_alignment",
    "market_volatility_state",
    "relative_strength_20_bucket",
    "relative_strength_63_bucket",
    "higher_timeframe_ticker_trend",
    "trend_extension_bucket",
    "opening_participation_bucket",
    "premarket_participation_bucket",
    "liquidity_bucket",
    "overnight_gap_magnitude_bucket",
    "price_band",
    "signal_time_bucket",
    "realized_volatility_bucket",
    "execution_liquidity_quality",
    "context_provenance",
)

PRIMARY_CONDITION_INTERACTIONS: Final[tuple[tuple[str, ...], ...]] = (
    ("market_direction_alignment", "market_volatility_state"),
    ("higher_timeframe_ticker_trend", "relative_strength_20_bucket"),
    ("relative_strength_20_bucket", "relative_strength_63_bucket"),
    ("liquidity_bucket", "realized_volatility_bucket"),
    ("overnight_gap_magnitude_bucket", "signal_time_bucket"),
    ("opening_participation_bucket", "signal_time_bucket"),
    ("premarket_participation_bucket", "overnight_gap_magnitude_bucket"),
    ("higher_timeframe_ticker_trend", "trend_extension_bucket"),
)

AUTHORITY: Final[dict[str, object]] = {
    "strategy_authority": "RESEARCH",
    "development_only": True,
    "consumed_master_rows_permitted": 0,
    "future_blind_rows_permitted": 0,
    "provider_calls_permitted": 0,
    "broker_reads_permitted": 0,
    "broker_writes_permitted": 0,
    "paper_authority": False,
    "live_authority": False,
    "strategy_promotion": False,
    "selector_promotion": False,
    "confluence_opened": False,
    "b35_inspired_challenger_can_self_validate_on_development": False,
}


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def successor_conditioning_manifest() -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": SUCCESSOR_CONDITIONING_CONTRACT,
        "accepted_standalone": {
            "run_contract_fingerprint": ACCEPTED_RUN_CONTRACT_FINGERPRINT,
            "standalone_run_fingerprint": ACCEPTED_STANDALONE_RUN_FINGERPRINT,
            "artifact_set_fingerprint": ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
            "input_manifest_fingerprint": ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
            "group_count": ACCEPTED_GROUP_COUNT,
            "record_count": ACCEPTED_STANDALONE_RECORD_COUNT,
        },
        "scope": [DEVELOPMENT_START, DEVELOPMENT_END],
        "walk_forward": {
            "training_sessions": ROLLING_TRAIN_SESSIONS,
            "test_sessions": WALK_FORWARD_TEST_SESSIONS,
            "step_sessions": WALK_FORWARD_STEP_SESSIONS,
            "embargo_sessions": WALK_FORWARD_EMBARGO_SESSIONS,
        },
        "minimum_support": {
            "opportunities": MIN_CELL_OPPORTUNITIES,
            "sessions": MIN_CELL_UNIQUE_SESSIONS,
            "instruments": MIN_CELL_UNIQUE_INSTRUMENTS,
        },
        "scoring": {
            "cluster": "XNYS_SESSION",
            "bootstrap_draws": SESSION_CLUSTER_BOOTSTRAP_DRAWS,
            "lower_quantile": SELECTOR_LCB_QUANTILE,
            "eligible": "SUPPORTED_AND_PRIMARY_NET_RETURN_LCB_STRICTLY_POSITIVE",
            "daily": {
                "horizon_sessions": DAILY_PRIMARY_HORIZON_SESSIONS,
                "primary_cost_bps": DAILY_PRIMARY_COST_BPS,
                "stress_cost_bps": DAILY_STRESS_COST_BPS,
            },
            "intraday": {
                "primary_cost_bps": INTRADAY_PRIMARY_COST_BPS,
                "stress_cost_bps": INTRADAY_STRESS_COST_BPS,
            },
            "stress_is_reported_not_a_fallback_rescue": True,
        },
        "reporting_cost_grid_bps": list(REPORTING_COST_GRID_BPS),
        "bucket_contract": BUCKET_CONTRACT,
        "condition_dimensions": list(CONDITION_DIMENSIONS),
        "primary_condition_interactions": [list(item) for item in PRIMARY_CONDITION_INTERACTIONS],
        "selector_fallback_hierarchy": [list(item) for item in SELECTOR_FALLBACK_HIERARCHY],
        "fallback_only_when_more_specific_unsupported": True,
        "supported_nonpositive_cell_may_fallback": False,
        "standalone_artifacts_immutable": True,
        "raw_market_data_reread": False,
        "context_unavailable_is_never_reconstructed_post_result": True,
        "authority": AUTHORITY,
    }
    payload["fingerprint"] = _stable_hash(payload)
    return payload


SUCCESSOR_CONDITIONING_FINGERPRINT: Final[str] = str(
    successor_conditioning_manifest()["fingerprint"]
)
