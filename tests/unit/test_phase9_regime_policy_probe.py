from __future__ import annotations

import pytest

from packages.regimes.policy_probe import (
    REGIME_POLICY_PROBE_CONTRACT_VERSION,
    composite_market_state,
    composite_sector_state,
    efficiency_state,
    market_structure_state,
    momentum_state,
    participation_state,
    quartile_vote,
    run_diagnostics,
    sector_structure_state,
    volatility_state,
)


SUMMARY = {"p25": 0.25, "p75": 0.75, "p90": 0.90}


def test_policy_probe_contract_and_quartile_vote_boundaries_are_locked():
    assert REGIME_POLICY_PROBE_CONTRACT_VERSION == (
        "regime-policy-probe-v1-quartile-dimensional-no-hysteresis"
    )
    assert quartile_vote(0.24, SUMMARY) == -1
    assert quartile_vote(0.25, SUMMARY) == -1
    assert quartile_vote(0.50, SUMMARY) == 0
    assert quartile_vote(0.75, SUMMARY) == 1
    assert quartile_vote(0.76, SUMMARY) == 1


def test_structure_and_momentum_state_boundaries_are_conservative():
    assert market_structure_state(4) == "STRONG_UP"
    assert market_structure_state(2) == "UP"
    assert market_structure_state(1) == "MIXED"
    assert market_structure_state(-2) == "DOWN"
    assert market_structure_state(-4) == "STRONG_DOWN"
    assert sector_structure_state(3) == "STRONG_UP"
    assert sector_structure_state(1) == "UP"
    assert sector_structure_state(0) == "MIXED"
    assert sector_structure_state(-3) == "STRONG_DOWN"
    assert momentum_state(2) == "STRONG_POSITIVE"
    assert momentum_state(1) == "POSITIVE"
    assert momentum_state(0) == "MIXED"
    assert momentum_state(-2) == "STRONG_NEGATIVE"


def test_composite_states_require_directional_agreement():
    assert composite_market_state("STRONG_UP", "STRONG_POSITIVE", "MIXED") == "STRONG_BULL"
    assert composite_market_state("UP", "MIXED", "MIXED") == "BULL"
    assert composite_market_state("UP", "NEGATIVE", "MIXED") == "MIXED"
    assert composite_market_state("STRONG_DOWN", "STRONG_NEGATIVE", "MIXED") == "STRONG_BEAR"
    assert composite_market_state("DOWN", "POSITIVE", "MIXED") == "MIXED"
    assert composite_sector_state("STRONG_UP", "POSITIVE") == "STRONG_BULL"
    assert composite_sector_state("DOWN", "MIXED") == "BEAR"
    assert composite_sector_state("DOWN", "POSITIVE") == "MIXED"


def test_participation_volatility_and_efficiency_are_separate_dimensions():
    assert participation_state(0.80, SUMMARY) == "BROAD_POSITIVE"
    assert participation_state(0.50, SUMMARY) == "MIXED"
    assert participation_state(0.20, SUMMARY) == "BROAD_NEGATIVE"
    assert volatility_state(0.95, 0.50, SUMMARY, SUMMARY) == "STRESSED"
    assert volatility_state(0.80, 0.50, SUMMARY, SUMMARY) == "ELEVATED"
    assert volatility_state(0.20, 0.20, SUMMARY, SUMMARY) == "CALM"
    assert volatility_state(0.50, 0.50, SUMMARY, SUMMARY) == "NORMAL"
    assert efficiency_state(0.80, SUMMARY) == "HIGH"
    assert efficiency_state(0.50, SUMMARY) == "NORMAL"
    assert efficiency_state(0.20, SUMMARY) == "LOW"


def test_run_diagnostics_surfaces_raw_chatter_and_one_day_runs():
    diagnostics = run_diagnostics(["BULL", "BULL", "MIXED", "BULL", "BULL", "BEAR"])
    assert diagnostics["observation_count"] == 6
    assert diagnostics["transition_count"] == 3
    assert diagnostics["transition_rate"] == pytest.approx(3 / 5)
    assert diagnostics["run_count"] == 4
    assert diagnostics["median_run_length"] == pytest.approx(1.5)
    assert diagnostics["one_day_run_count"] == 2
    assert diagnostics["one_day_run_share"] == pytest.approx(0.5)
