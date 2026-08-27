from __future__ import annotations

from collections import Counter
from datetime import date

from packages.backtesting.phase26_policy import (
    PHASE26_AUTOMATION_WRITES,
    PHASE26_BEAR_BLOCKS,
    PHASE26_BROKER_READS,
    PHASE26_BROKER_WRITES,
    PHASE26_BULL_BLOCKS,
    PHASE26_CANDIDATES,
    PHASE26_COST_GRID_BPS,
    PHASE26_DEVELOPMENT_END,
    PHASE26_LIVE_WRITES,
    PHASE26_MEDIAN_RETURN_IS_HARD_GATE,
    PHASE26_MULTIPLE_TESTING_METHOD,
    PHASE26_ORDER_WRITES,
    PHASE26_OUTCOME_HORIZON_SESSIONS,
    PHASE26_PAPER_SUBMITS,
    PHASE26_PRIMARY_COST_BPS,
    PHASE26_PROTECTED_END,
    PHASE26_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE26_PROTECTED_START,
    PHASE26_PROVIDER_READS,
    PHASE26_PROVIDER_WRITES,
    PHASE26_PURGE_SESSIONS,
    PHASE26_RESEARCH_START,
    PHASE26_SECTOR_MAPPING_AUTHORITY,
    PHASE26_STRESS_COST_BPS,
    PHASE26_WIN_RATE_IS_HARD_GATE,
    phase26_policy_fingerprint,
    phase26_policy_payload,
)


def test_phase26_candidate_search_space_is_exactly_balanced_and_frozen() -> None:
    assert len(PHASE26_CANDIDATES) == 24
    assert len({candidate.candidate_id for candidate in PHASE26_CANDIDATES}) == 24

    families = Counter(candidate.family for candidate in PHASE26_CANDIDATES)
    assert families == {
        "cross_sectional_relative_strength": 4,
        "volatility_liquidity_mean_reversion": 4,
        "volatility_normalized_breakout": 4,
        "multi_timeframe_state_transition": 4,
        "gap_behavior": 4,
        "independent_feature_block_composite": 4,
    }
    for family in families:
        directions = Counter(
            candidate.direction for candidate in PHASE26_CANDIDATES if candidate.family == family
        )
        assert directions == {"LONG": 2, "SHORT": 2}

    assert PHASE26_BULL_BLOCKS != PHASE26_BEAR_BLOCKS
    assert len(PHASE26_BULL_BLOCKS) == 5
    assert len(PHASE26_BEAR_BLOCKS) == 5


def test_phase26_chronology_and_economics_are_locked() -> None:
    assert PHASE26_RESEARCH_START == "2021-08-16"
    assert PHASE26_DEVELOPMENT_END == "2026-05-06"
    assert PHASE26_PROTECTED_START == "2026-05-12"
    assert PHASE26_PROTECTED_END == "2026-08-11"
    assert date.fromisoformat(PHASE26_RESEARCH_START) < date.fromisoformat(PHASE26_DEVELOPMENT_END)
    assert date.fromisoformat(PHASE26_DEVELOPMENT_END) < date.fromisoformat(PHASE26_PROTECTED_START)
    assert date.fromisoformat(PHASE26_PROTECTED_START) <= date.fromisoformat(PHASE26_PROTECTED_END)
    assert PHASE26_OUTCOME_HORIZON_SESSIONS == 3
    assert PHASE26_PURGE_SESSIONS == 3
    assert PHASE26_PRIMARY_COST_BPS == 10.0
    assert PHASE26_STRESS_COST_BPS == 25.0
    assert PHASE26_COST_GRID_BPS == (0.0, 5.0, 10.0, 25.0)
    assert PHASE26_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_24"


def test_phase26_expectancy_not_hit_rate_is_the_hard_economic_gate() -> None:
    assert PHASE26_MEDIAN_RETURN_IS_HARD_GATE is False
    assert PHASE26_WIN_RATE_IS_HARD_GATE is False


def test_phase26_is_provider_broker_and_live_free_until_later_phases() -> None:
    assert PHASE26_PROVIDER_READS == 0
    assert PHASE26_PROVIDER_WRITES == 0
    assert PHASE26_BROKER_READS == 0
    assert PHASE26_BROKER_WRITES == 0
    assert PHASE26_ORDER_WRITES == 0
    assert PHASE26_PAPER_SUBMITS == 0
    assert PHASE26_LIVE_WRITES == 0
    assert PHASE26_AUTOMATION_WRITES == 0
    assert PHASE26_SECTOR_MAPPING_AUTHORITY is False
    assert PHASE26_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is False


def test_phase26_policy_fingerprint_is_deterministic_and_complete() -> None:
    payload = phase26_policy_payload()
    first = phase26_policy_fingerprint()
    second = phase26_policy_fingerprint()

    assert first == second
    assert len(first) == 64
    assert payload["contract_version"].startswith("phase26-policy-v1-")
    assert len(payload["candidates"]) == 24
    assert payload["robustness"]["median_return_is_hard_gate"] is False
    assert payload["robustness"]["win_rate_is_hard_gate"] is False
    assert payload["dates"]["development_end"] == "2026-05-06"
    assert payload["outcome"]["observation_exact_interval_required"] is True
    assert payload["outcome"]["future_endpoint_same_provider_native_ticker_required"] is True
    assert payload["outcome"]["future_endpoint_must_remain_inside_observation_interval"] is False
