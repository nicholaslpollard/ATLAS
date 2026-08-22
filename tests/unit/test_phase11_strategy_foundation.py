from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.strategy import MLProbabilityEvidence, StrategyAssessment, StrategyDirection, StrategyRegimeFit
from packages.strategies.base import StrategyContext
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY
from packages.strategies.router import StrategyRouter, StrategyRoutingContext


AS_OF = date(2026, 8, 21)


def _routing(
    direction: DiscoveryDirection,
    *,
    market: str | None = "BULL",
    sector: str | None = "BULL",
    ticker: str | None = "UPTREND",
) -> StrategyRoutingContext:
    return StrategyRoutingContext(
        instrument_id="figi:TEST",
        ticker="TEST",
        as_of_date=AS_OF,
        discovery_direction=direction,
        market_state=market,
        sector_state=sector,
        ticker_state=ticker,
    )


def test_phase11_registry_contains_eight_versioned_rules() -> None:
    strategies = DEFAULT_STRATEGY_REGISTRY.all()
    assert len(strategies) == 8
    assert len({strategy.metadata.strategy_id for strategy in strategies}) == 8
    assert len(DEFAULT_STRATEGY_REGISTRY.fingerprint()) == 64
    assert {strategy.metadata.direction for strategy in strategies} == {
        StrategyDirection.LONG,
        StrategyDirection.SHORT,
    }


def test_rule_strategy_emits_setup_evidence_not_trade_geometry() -> None:
    strategy = DEFAULT_STRATEGY_REGISTRY.get("trend_following_long_v1")
    context = StrategyContext(
        instrument_id="figi:TEST",
        ticker="TEST",
        as_of_date=AS_OF,
        features={
            "close": 110.0,
            "ema_20": 105.0,
            "ema_50": 100.0,
            "ema_20_slope_1": 0.5,
            "macd_hist_12_26_9": 0.2,
        },
    )
    assessment = strategy.evaluate(context)
    assert assessment.fired is True
    assert assessment.evidence_score == 1.0
    fields = StrategyAssessment.model_fields
    assert set(fields) >= {"fired", "evidence", "ml_probability_evidence"}
    assert {"entry", "stop", "target", "quantity", "broker"}.isdisjoint(fields)


def test_rule_strategy_partial_match_is_not_fired() -> None:
    strategy = DEFAULT_STRATEGY_REGISTRY.get("momentum_long_v1")
    assessment = strategy.evaluate(
        StrategyContext(
            instrument_id="figi:TEST",
            ticker="TEST",
            as_of_date=AS_OF,
            features={"return_1": 0.01, "rsi_14": 49.0, "macd_hist_12_26_9": 0.1},
        )
    )
    assert assessment.fired is False
    assert assessment.conditions_met == 2
    assert assessment.condition_count == 3
    assert assessment.evidence_score == pytest.approx(2 / 3)


def test_strategy_context_fails_closed_on_missing_required_feature() -> None:
    strategy = DEFAULT_STRATEGY_REGISTRY.get("breakout_long_v1")
    with pytest.raises(KeyError):
        strategy.evaluate(
            StrategyContext(
                instrument_id="figi:TEST",
                ticker="TEST",
                as_of_date=AS_OF,
                features={"breakout_distance_20": 0.01},
            )
        )


def test_ml_probability_evidence_requires_probability_simplex() -> None:
    evidence = MLProbabilityEvidence(model_id="m1", p_down=0.2, p_neutral=0.3, p_up=0.5)
    assert evidence.p_up == 0.5
    with pytest.raises(ValidationError):
        MLProbabilityEvidence(model_id="m1", p_down=0.2, p_neutral=0.3, p_up=0.6)


def test_bullish_context_routes_long_and_blocks_short_direction() -> None:
    decisions = StrategyRouter().route(_routing(DiscoveryDirection.BULLISH))
    long_decisions = [item for item in decisions if item.direction == StrategyDirection.LONG]
    short_decisions = [item for item in decisions if item.direction == StrategyDirection.SHORT]
    assert long_decisions and all(item.eligible for item in long_decisions)
    assert short_decisions and all(not item.eligible for item in short_decisions)
    assert all(item.market_fit == StrategyRegimeFit.PREFERRED for item in long_decisions)


def test_bearish_context_routes_short_strategies() -> None:
    decisions = StrategyRouter().eligible(
        _routing(
            DiscoveryDirection.BEARISH,
            market="BEAR",
            sector="STRONG_BEAR",
            ticker="DOWNTREND",
        )
    )
    assert decisions
    assert all(item.direction == StrategyDirection.SHORT for item in decisions)


def test_neutral_discovery_direction_routes_nothing() -> None:
    assert StrategyRouter().eligible(_routing(DiscoveryDirection.NEUTRAL)) == ()


def test_missing_ticker_regime_does_not_fabricate_or_block_daily_route() -> None:
    decisions = StrategyRouter().eligible(
        _routing(DiscoveryDirection.BULLISH, market="BULL", sector="BULL", ticker=None)
    )
    assert decisions
    assert all(item.ticker_fit == StrategyRegimeFit.UNAVAILABLE for item in decisions)


def test_authoritative_sector_contradiction_blocks_route() -> None:
    decisions = StrategyRouter().route(
        _routing(DiscoveryDirection.BULLISH, market="BULL", sector="BEAR", ticker="UPTREND")
    )
    long_decisions = [item for item in decisions if item.direction == StrategyDirection.LONG]
    assert long_decisions
    assert all(not item.eligible for item in long_decisions)
    assert all(item.sector_fit == StrategyRegimeFit.BLOCKED for item in long_decisions)
