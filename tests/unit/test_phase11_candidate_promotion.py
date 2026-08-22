from __future__ import annotations

from datetime import date

from packages.discovery.promotion import CandidatePromotionEngine
from packages.schemas.candidate_promotion import StrategyHistoricalSupportSnapshot
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState
from packages.schemas.discovery_state import DiscoveryStateRecord
from packages.schemas.strategy import MLProbabilityEvidence


AS_OF = date(2026, 8, 21)


def _discovery(
    *,
    state: DiscoveryState = DiscoveryState.HOT,
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
) -> DiscoveryStateRecord:
    return DiscoveryStateRecord(
        instrument_id="figi:TEST",
        ticker="TEST",
        as_of_date=AS_OF,
        raw_state=state,
        effective_state=state,
        previous_effective_state=state,
        warm_confirmation_streak=0,
        demotion_streak=0,
        transition=f"hold_{state.value}",
        priority_score=0.8,
        bull_evidence=0.8,
        bear_evidence=0.2,
        direction=direction,
        scored_timeframes=3,
        top_setup="trend",
    )


def _ml() -> MLProbabilityEvidence:
    return MLProbabilityEvidence(model_id="accepted-model", p_down=0.2, p_neutral=0.3, p_up=0.5)


def _support(eligible: bool = True) -> StrategyHistoricalSupportSnapshot:
    return StrategyHistoricalSupportSnapshot(
        strategy_id="trend_following_long_v1",
        status="SUPPORTED" if eligible else "UNSUPPORTED",
        eligible_for_candidate_promotion=eligible,
        primary_cost_bps=10.0,
        development_mean_return=0.002 if eligible else -0.001,
        first_half_mean_return=0.001 if eligible else -0.001,
        second_half_mean_return=0.003 if eligible else -0.001,
        development_rows=1000,
    )


def _features() -> dict[str, float]:
    return {
        "close": 110.0,
        "ema_20": 105.0,
        "ema_50": 100.0,
        "ema_20_slope_1": 0.5,
        "macd_hist_12_26_9": 0.2,
        "return_1": 0.01,
        "rsi_14": 60.0,
        "breakout_distance_20": 0.02,
        "relative_volume_20": 1.5,
        "price_distance_ema_20": 0.01,
    }


def test_hot_candidate_promotes_when_supported_routed_strategy_fires() -> None:
    support = _support(True)
    record = CandidatePromotionEngine().evaluate(
        discovery=_discovery(),
        features=_features(),
        market_state="BULL",
        sector_state=None,
        ticker_state="UPTREND",
        ml_probability_evidence=_ml(),
        historical_support={support.strategy_id: support},
    )
    assert record.promoted is True
    assert record.supported_fired_strategy_ids == ("trend_following_long_v1",)
    assert record.ml_probability_evidence.p_up == 0.5
    assert "PROMOTE:SUPPORTED_ROUTED_STRATEGY_FIRED" in record.reason_codes


def test_unsupported_strategy_cannot_promote_candidate() -> None:
    support = _support(False)
    record = CandidatePromotionEngine().evaluate(
        discovery=_discovery(),
        features=_features(),
        market_state="BULL",
        sector_state=None,
        ticker_state="UPTREND",
        ml_probability_evidence=_ml(),
        historical_support={support.strategy_id: support},
    )
    assert record.promoted is False
    assert record.supported_fired_strategy_ids == ()


def test_market_regime_contradiction_prevents_long_promotion() -> None:
    support = _support(True)
    record = CandidatePromotionEngine().evaluate(
        discovery=_discovery(),
        features=_features(),
        market_state="BEAR",
        sector_state=None,
        ticker_state="UPTREND",
        ml_probability_evidence=_ml(),
        historical_support={support.strategy_id: support},
    )
    assert record.promoted is False


def test_watch_candidate_cannot_promote_even_if_strategy_fires() -> None:
    support = _support(True)
    record = CandidatePromotionEngine().evaluate(
        discovery=_discovery(state=DiscoveryState.WATCH),
        features=_features(),
        market_state="BULL",
        sector_state=None,
        ticker_state="UPTREND",
        ml_probability_evidence=_ml(),
        historical_support={support.strategy_id: support},
    )
    assert record.promoted is False
    assert "REJECT:DISCOVERY_NOT_WARM_HOT_DIRECTIONAL" in record.reason_codes
