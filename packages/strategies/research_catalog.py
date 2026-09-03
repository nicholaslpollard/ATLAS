from __future__ import annotations

import hashlib
import json

from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import (
    DEFAULT_SIGNAL_COST_GRID_BPS,
    ResearchStrategyFamily,
    StrategyAuthority,
    StrategyEvidenceSource,
    StrategySpecification,
)


REFERENCE_CATALOG_CONTRACT_VERSION = "a33-reference-catalog-v1-six-daily-pre-outcome-specifications"

_COMMON_UNIVERSE = (
    "PIT-active U.S. common stocks; exclude ETFs unless explicitly specified; adjusted analytical bars "
    "with raw/execution-price lineage; close >= $5; prior 20-session median dollar volume >= $5M; "
    "sufficient warm-up; no ambiguous identity; finalized daily-close signal; earliest entry next "
    "regular-session executable event."
)
_COMMON_COST = (
    f"Round-trip signal diagnostics at {DEFAULT_SIGNAL_COST_GRID_BPS} bps; 10 bps primary and 25 bps "
    "stress. Executable replay later replaces generic costs with spread/slippage/order/ADV economics."
)
_COMMON_EVALUATION = (
    "PIT chronological walk-forward evaluation; retain all eligible, fired, routed-out, rejected, and "
    "counterfactual opportunities; report after-cost results, concentration, uncertainty, regime, "
    "volatility, liquidity, direction, and year/fold slices without sparse-combination mining."
)


class StrategySpecificationRegistry:
    def __init__(self, specifications: tuple[StrategySpecification, ...] = ()) -> None:
        self._items: dict[str, StrategySpecification] = {}
        for specification in specifications:
            self.register(specification)

    def register(self, specification: StrategySpecification) -> None:
        if specification.registry_key in self._items:
            raise ValueError(f"strategy specification already registered: {specification.registry_key}")
        self._items[specification.registry_key] = specification

    def get(self, strategy_id: str, version: str = "1") -> StrategySpecification:
        key = f"{strategy_id}:{version}"
        try:
            return self._items[key]
        except KeyError as exc:
            raise KeyError(f"unknown strategy specification: {key}") from exc

    def all(self) -> tuple[StrategySpecification, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def fingerprint(self) -> str:
        payload = [item.model_dump(mode="json") for item in self.all()]
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


REFERENCE_STRATEGY_SPECIFICATIONS = (
    StrategySpecification(
        strategy_id="ma_trend_cross_50_200_long_v1",
        version="1",
        family=ResearchStrategyFamily.MOVING_AVERAGE_TREND,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG,),
        native_timeframe="1d",
        universe_contract=_COMMON_UNIVERSE,
        signal_contract=(
            "SMA50 crosses from at/below to above SMA200 at the finalized daily close. A persistent "
            "SMA50>SMA200 state without a prior-bar transition is not a new signal."
        ),
        entry_contract="Enter LONG no earlier than the next regular-session executable event.",
        exit_contract="Exit on reverse SMA50/SMA200 cross, 3 ATR trailing stop, or 126-session maximum hold.",
        risk_contract="Initial stop 2 ATR below entry; equal-risk sizing under the fixed small research risk budget.",
        cost_contract=_COMMON_COST,
        evaluation_contract=_COMMON_EVALUATION,
        required_features=("sma_50", "sma_200", "sma_50_prev", "sma_200_prev", "atr_14"),
    ),
    StrategySpecification(
        strategy_id="ema_pullback_20_50_long_v1",
        version="1",
        family=ResearchStrategyFamily.PULLBACK_CONTINUATION,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG,),
        native_timeframe="1d",
        universe_contract=_COMMON_UNIVERSE,
        signal_contract=(
            "EMA20 > EMA50; pullback reaches within 0.5 ATR of EMA20 without closing below EMA50; "
            "the first finalized close back above EMA20 is the setup transition."
        ),
        entry_contract="Enter LONG no earlier than the next regular-session executable event after confirmation.",
        exit_contract="Exit at 2.5R, finalized close below EMA50, or 15-session maximum hold.",
        risk_contract=(
            "Initial stop is below the pullback low or 1.5 ATR from entry, whichever is farther, but the exact "
            "price-selection/risk-cap algorithm must be resolved before outcome access."
        ),
        cost_contract=_COMMON_COST,
        evaluation_contract=_COMMON_EVALUATION,
        required_features=("ema_20", "ema_50", "atr_14", "pullback_low", "close", "close_prev"),
        pre_outcome_blockers=(
            "Freeze the exact pullback-low versus 1.5 ATR stop-price algorithm and risk-cap rejection behavior.",
        ),
    ),
    StrategySpecification(
        strategy_id="macd_shift_12_26_9_v1",
        version="1",
        family=ResearchStrategyFamily.MOMENTUM,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG, StrategyDirection.SHORT),
        native_timeframe="1d",
        universe_contract=_COMMON_UNIVERSE,
        signal_contract=(
            "LONG seed: MACD crosses above signal while both are below zero. SHORT seed: MACD crosses below "
            "signal while both are above zero. Each directional implementation must become a distinct version."
        ),
        entry_contract="Enter no earlier than the next regular-session executable event after the directional cross.",
        exit_contract="1.5 ATR stop; 3R target; opposite MACD cross; or 20-session maximum hold.",
        risk_contract="Equal-risk sizing; SHORT implementation additionally requires borrow/locate and asymmetric-cost policy.",
        cost_contract=_COMMON_COST,
        evaluation_contract=_COMMON_EVALUATION,
        required_features=("macd_12_26_9", "macd_signal_12_26_9", "macd_prev", "macd_signal_prev", "atr_14"),
        pre_outcome_blockers=(
            "Split LONG and SHORT into distinct versioned executable policies before outcome access.",
            "Freeze SHORT borrow/locate and asymmetric-cost treatment before any SHORT outcome access.",
        ),
    ),
    StrategySpecification(
        strategy_id="rsi_recovery_14_trend_long_v1",
        version="1",
        family=ResearchStrategyFamily.MEAN_REVERSION,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG,),
        native_timeframe="1d",
        universe_contract=_COMMON_UNIVERSE,
        signal_contract=(
            "Finalized close is above EMA200; RSI14 was below 30 and crosses back above 30. RSI<30 alone is not "
            "a signal and is not treated as intrinsic undervaluation."
        ),
        entry_contract="Enter LONG no earlier than the next regular-session executable event.",
        exit_contract="Exit at EMA20, RSI14 >= 60, or 10-session maximum hold.",
        risk_contract="Initial stop 2 ATR below entry; equal-risk sizing under the fixed small research risk budget.",
        cost_contract=_COMMON_COST,
        evaluation_contract=_COMMON_EVALUATION,
        required_features=("close", "ema_200", "ema_20", "rsi_14", "rsi_14_prev", "atr_14"),
    ),
    StrategySpecification(
        strategy_id="donchian_breakout_20_volume_v1",
        version="1",
        family=ResearchStrategyFamily.PRICE_BREAKOUT,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG, StrategyDirection.SHORT),
        native_timeframe="1d",
        universe_contract=_COMMON_UNIVERSE,
        signal_contract=(
            "LONG seed: finalized close crosses prior 20-session high; SHORT seed: crosses prior 20-session low; "
            "relative volume20 >= 1.5; EMA50 slope agrees. Directional implementations are distinct versions."
        ),
        entry_contract="Enter no earlier than the next regular-session executable event after the range-break transition.",
        exit_contract="Stop at channel boundary or 2 ATR subject to risk cap; 3 ATR trail; 20-session maximum hold.",
        risk_contract="Equal-risk sizing; exact directional stop choice and SHORT borrow/locate economics are frozen per version.",
        cost_contract=_COMMON_COST,
        evaluation_contract=_COMMON_EVALUATION,
        required_features=(
            "close",
            "close_prev",
            "donchian_high_20_prior",
            "donchian_low_20_prior",
            "relative_volume_20",
            "ema_50_slope_1",
            "atr_14",
        ),
        pre_outcome_blockers=(
            "Split LONG and SHORT into distinct versioned executable policies before outcome access.",
            "Freeze exact channel-boundary versus 2 ATR stop-price/risk-cap behavior per direction.",
            "Freeze SHORT borrow/locate and asymmetric-cost treatment before any SHORT outcome access.",
        ),
    ),
    StrategySpecification(
        strategy_id="bollinger_squeeze_breakout_20_v1",
        version="1",
        family=ResearchStrategyFamily.VOLATILITY_EXPANSION,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        authority=StrategyAuthority.RESEARCH,
        directions=(StrategyDirection.LONG, StrategyDirection.SHORT),
        native_timeframe="1d",
        universe_contract=_COMMON_UNIVERSE,
        signal_contract=(
            "BB width20 is at/below its trailing 126-session 10th percentile, then finalized close crosses the "
            "corresponding outer band with relative volume >= 1.25. Compression alone supplies no direction."
        ),
        entry_contract="Enter no earlier than the next regular-session executable event after the directional band break.",
        exit_contract="Stop at BB midline or 1.5 ATR; 3R/trailing exit; 20-session maximum hold.",
        risk_contract="Equal-risk sizing; exact stop selection and SHORT borrow/locate economics are frozen per version.",
        cost_contract=_COMMON_COST,
        evaluation_contract=_COMMON_EVALUATION,
        required_features=(
            "close",
            "close_prev",
            "bb_upper_20",
            "bb_lower_20",
            "bb_mid_20",
            "bb_width_20",
            "bb_width_20_p10_126",
            "relative_volume_20",
            "atr_14",
        ),
        pre_outcome_blockers=(
            "Split LONG and SHORT into distinct versioned executable policies before outcome access.",
            "Freeze exact BB-midline versus 1.5 ATR stop-price behavior per direction.",
            "Freeze SHORT borrow/locate and asymmetric-cost treatment before any SHORT outcome access.",
        ),
    ),
)


DEFAULT_REFERENCE_SPECIFICATION_REGISTRY = StrategySpecificationRegistry(REFERENCE_STRATEGY_SPECIFICATIONS)
