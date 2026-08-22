from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from packages.schemas.strategy import StrategyDirection, StrategyFamily

from .base import Strategy
from .metadata import StrategyMetadata
from .rules import Comparison, FeatureCondition, RuleStrategy


STRATEGY_REGISTRY_CONTRACT_VERSION = "strategy-registry-v1-eight-daily-feature-rules"


class StrategyRegistry:
    def __init__(self, strategies: tuple[Strategy, ...] = ()) -> None:
        self._strategies: dict[str, Strategy] = {}
        for strategy in strategies:
            self.register(strategy)

    def register(self, strategy: Strategy) -> None:
        strategy_id = strategy.metadata.strategy_id
        if strategy_id in self._strategies:
            raise ValueError(f"strategy is already registered: {strategy_id}")
        self._strategies[strategy_id] = strategy

    def get(self, strategy_id: str) -> Strategy:
        try:
            return self._strategies[strategy_id]
        except KeyError as exc:
            raise KeyError(f"unknown strategy: {strategy_id}") from exc

    def all(self) -> tuple[Strategy, ...]:
        return tuple(self._strategies[key] for key in sorted(self._strategies))

    def metadata(self) -> tuple[StrategyMetadata, ...]:
        return tuple(strategy.metadata for strategy in self.all())

    def fingerprint(self) -> str:
        payload: list[dict[str, object]] = []
        for strategy in self.all():
            conditions = getattr(strategy, "conditions", ())
            payload.append(
                {
                    "metadata": asdict(strategy.metadata),
                    "conditions": [asdict(condition) for condition in conditions],
                }
            )
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def _metadata(
    strategy_id: str,
    family: StrategyFamily,
    direction: StrategyDirection,
    conditions: tuple[FeatureCondition, ...],
    description: str,
) -> StrategyMetadata:
    required = tuple(sorted({name for condition in conditions for name in condition.required_features}))
    return StrategyMetadata(
        strategy_id=strategy_id,
        family=family,
        direction=direction,
        required_features=required,
        description=description,
    )


def _rule(
    strategy_id: str,
    family: StrategyFamily,
    direction: StrategyDirection,
    conditions: tuple[FeatureCondition, ...],
    description: str,
) -> RuleStrategy:
    return RuleStrategy(_metadata(strategy_id, family, direction, conditions, description), conditions)


LONG_TREND = (
    FeatureCondition("close", Comparison.GT, right_feature="ema_20", reason_code="close_above_ema20"),
    FeatureCondition("ema_20", Comparison.GT, right_feature="ema_50", reason_code="ema20_above_ema50"),
    FeatureCondition("ema_20_slope_1", Comparison.GT, right_value=0.0, reason_code="ema20_slope_positive"),
    FeatureCondition("macd_hist_12_26_9", Comparison.GT, right_value=0.0, reason_code="macd_hist_positive"),
)
SHORT_TREND = (
    FeatureCondition("close", Comparison.LT, right_feature="ema_20", reason_code="close_below_ema20"),
    FeatureCondition("ema_20", Comparison.LT, right_feature="ema_50", reason_code="ema20_below_ema50"),
    FeatureCondition("ema_20_slope_1", Comparison.LT, right_value=0.0, reason_code="ema20_slope_negative"),
    FeatureCondition("macd_hist_12_26_9", Comparison.LT, right_value=0.0, reason_code="macd_hist_negative"),
)
LONG_MOMENTUM = (
    FeatureCondition("return_1", Comparison.GT, right_value=0.0, reason_code="positive_return"),
    FeatureCondition("rsi_14", Comparison.GT, right_value=50.0, reason_code="rsi_above_midline"),
    FeatureCondition("macd_hist_12_26_9", Comparison.GT, right_value=0.0, reason_code="macd_hist_positive"),
)
SHORT_MOMENTUM = (
    FeatureCondition("return_1", Comparison.LT, right_value=0.0, reason_code="negative_return"),
    FeatureCondition("rsi_14", Comparison.LT, right_value=50.0, reason_code="rsi_below_midline"),
    FeatureCondition("macd_hist_12_26_9", Comparison.LT, right_value=0.0, reason_code="macd_hist_negative"),
)
LONG_BREAKOUT = (
    FeatureCondition("breakout_distance_20", Comparison.GT, right_value=0.0, reason_code="above_prior_20_high"),
    FeatureCondition("relative_volume_20", Comparison.GT, right_value=1.0, reason_code="volume_above_20_average"),
    FeatureCondition("ema_20_slope_1", Comparison.GT, right_value=0.0, reason_code="ema20_slope_positive"),
)
SHORT_BREAKDOWN = (
    FeatureCondition("breakdown_distance_20", Comparison.LT, right_value=0.0, reason_code="below_prior_20_low"),
    FeatureCondition("relative_volume_20", Comparison.GT, right_value=1.0, reason_code="volume_above_20_average"),
    FeatureCondition("ema_20_slope_1", Comparison.LT, right_value=0.0, reason_code="ema20_slope_negative"),
)
LONG_PULLBACK = (
    FeatureCondition("ema_20", Comparison.GT, right_feature="ema_50", reason_code="uptrend_structure"),
    FeatureCondition("close", Comparison.GT, right_feature="ema_50", reason_code="close_above_ema50"),
    FeatureCondition("return_1", Comparison.LT, right_value=0.0, reason_code="one_session_pullback"),
    FeatureCondition("price_distance_ema_20", Comparison.LE, right_value=0.0, reason_code="at_or_below_ema20"),
)
SHORT_PULLBACK = (
    FeatureCondition("ema_20", Comparison.LT, right_feature="ema_50", reason_code="downtrend_structure"),
    FeatureCondition("close", Comparison.LT, right_feature="ema_50", reason_code="close_below_ema50"),
    FeatureCondition("return_1", Comparison.GT, right_value=0.0, reason_code="one_session_bounce"),
    FeatureCondition("price_distance_ema_20", Comparison.GE, right_value=0.0, reason_code="at_or_above_ema20"),
)


DEFAULT_STRATEGY_REGISTRY = StrategyRegistry(
    (
        _rule(
            "trend_following_long_v1",
            StrategyFamily.TREND_FOLLOWING,
            StrategyDirection.LONG,
            LONG_TREND,
            "Daily trend continuation with positive EMA structure and MACD confirmation.",
        ),
        _rule(
            "trend_following_short_v1",
            StrategyFamily.TREND_FOLLOWING,
            StrategyDirection.SHORT,
            SHORT_TREND,
            "Daily downside trend continuation with negative EMA structure and MACD confirmation.",
        ),
        _rule(
            "momentum_long_v1",
            StrategyFamily.MOMENTUM,
            StrategyDirection.LONG,
            LONG_MOMENTUM,
            "Positive daily return, RSI midline strength, and positive MACD histogram.",
        ),
        _rule(
            "momentum_short_v1",
            StrategyFamily.MOMENTUM,
            StrategyDirection.SHORT,
            SHORT_MOMENTUM,
            "Negative daily return, RSI midline weakness, and negative MACD histogram.",
        ),
        _rule(
            "breakout_long_v1",
            StrategyFamily.BREAKOUT,
            StrategyDirection.LONG,
            LONG_BREAKOUT,
            "Twenty-session upside breakout with above-average volume and positive EMA slope.",
        ),
        _rule(
            "breakdown_short_v1",
            StrategyFamily.BREAKOUT,
            StrategyDirection.SHORT,
            SHORT_BREAKDOWN,
            "Twenty-session downside breakdown with above-average volume and negative EMA slope.",
        ),
        _rule(
            "pullback_long_v1",
            StrategyFamily.PULLBACK,
            StrategyDirection.LONG,
            LONG_PULLBACK,
            "One-session pullback toward the 20 EMA while the broader 20/50 EMA structure remains up.",
        ),
        _rule(
            "pullback_short_v1",
            StrategyFamily.PULLBACK,
            StrategyDirection.SHORT,
            SHORT_PULLBACK,
            "One-session bounce toward the 20 EMA while the broader 20/50 EMA structure remains down.",
        ),
    )
)
