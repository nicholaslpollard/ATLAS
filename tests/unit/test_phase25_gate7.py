from __future__ import annotations

from datetime import date

import pandas as pd

from packages.backtesting.phase25_gate6_policy import phase25_gate6_policy_fingerprint
from packages.backtesting.phase25_gate7 import persist_exact_interval_ticker_states
from packages.backtesting.phase25_gate7_policy import (
    ACCEPTED_GATE6_POLICY_FINGERPRINT,
    PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED,
    PHASE25_GATE7_PROVIDER_READS,
    PHASE25_GATE7_PROVIDER_WRITES,
    PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY,
    PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED,
    PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED,
    PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED,
    PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate7_policy_fingerprint,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.strategies.router import StrategyRouter, StrategyRoutingContext


def test_gate7_freezes_gate6_and_has_zero_external_authority() -> None:
    assert ACCEPTED_GATE6_POLICY_FINGERPRINT == "5ee92c766031fcf02bf8b80d9a1f4366e7bb6faa8c3634236ad438ef11f52da0"
    assert phase25_gate6_policy_fingerprint() == ACCEPTED_GATE6_POLICY_FINGERPRINT
    assert len(phase25_gate7_policy_fingerprint()) == 64
    assert PHASE25_GATE7_PROVIDER_READS == PHASE25_GATE7_PROVIDER_WRITES == 0
    assert PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED is False
    assert PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY is False
    assert PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED is True
    assert PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED is False
    assert PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED is False
    assert PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED is False


def test_gate7_ticker_dimensional_confirmation_matches_two_session_semantics() -> None:
    raw = pd.DataFrame(
        [
            {
                "interval_key": "a",
                "instrument_id": "ins-a",
                "ticker": "ABC",
                "trading_date": date(2026, 8, 17),
                "daily_structure": "UP",
                "short_alignment": "MIXED",
                "momentum": "MIXED",
                "candidate_state": "UPTREND",
            },
            {
                "interval_key": "a",
                "instrument_id": "ins-a",
                "ticker": "ABC",
                "trading_date": date(2026, 8, 18),
                "daily_structure": "DOWN",
                "short_alignment": "MIXED",
                "momentum": "MIXED",
                "candidate_state": "DOWNTREND",
            },
            {
                "interval_key": "a",
                "instrument_id": "ins-a",
                "ticker": "ABC",
                "trading_date": date(2026, 8, 19),
                "daily_structure": "DOWN",
                "short_alignment": "MIXED",
                "momentum": "MIXED",
                "candidate_state": "DOWNTREND",
            },
        ]
    )
    ordinals = {
        date(2026, 8, 17): 0,
        date(2026, 8, 18): 1,
        date(2026, 8, 19): 2,
    }
    result = persist_exact_interval_ticker_states(raw, session_ordinals=ordinals)
    assert result["effective_ticker_state"].tolist() == [
        "UPTREND",
        "UPTREND",
        "DOWNTREND",
    ]
    assert result["persistence_depth"].tolist() == [1, 2, 3]


def test_gate7_ticker_persistence_resets_on_feature_session_gap() -> None:
    raw = pd.DataFrame(
        [
            {
                "interval_key": "a",
                "instrument_id": "ins-a",
                "ticker": "ABC",
                "trading_date": date(2026, 8, 17),
                "daily_structure": "UP",
                "short_alignment": "MIXED",
                "momentum": "MIXED",
                "candidate_state": "UPTREND",
            },
            {
                "interval_key": "a",
                "instrument_id": "ins-a",
                "ticker": "ABC",
                "trading_date": date(2026, 8, 19),
                "daily_structure": "DOWN",
                "short_alignment": "MIXED",
                "momentum": "MIXED",
                "candidate_state": "DOWNTREND",
            },
        ]
    )
    ordinals = {
        date(2026, 8, 17): 0,
        date(2026, 8, 18): 1,
        date(2026, 8, 19): 2,
    }
    result = persist_exact_interval_ticker_states(raw, session_ordinals=ordinals)
    assert result["effective_ticker_state"].tolist() == ["UPTREND", "DOWNTREND"]
    assert result["persistence_depth"].tolist() == [1, 1]


def test_gate7_sector_unavailable_is_nonblocking_in_production_router() -> None:
    context = StrategyRoutingContext(
        instrument_id="ins-a",
        ticker="ABC",
        as_of_date=date(2026, 8, 21),
        discovery_direction=DiscoveryDirection.BULLISH,
        market_state="BULL",
        sector_state=None,
        ticker_state="UPTREND",
    )
    decisions = StrategyRouter().route(context)
    long_decisions = [item for item in decisions if item.direction.value == "LONG"]
    short_decisions = [item for item in decisions if item.direction.value == "SHORT"]
    assert len(long_decisions) == 4
    assert all(item.sector_fit.value == "unavailable" for item in decisions)
    assert all(item.eligible for item in long_decisions)
    assert not any(item.eligible for item in short_decisions)
