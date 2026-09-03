from __future__ import annotations

import hashlib
import json

from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import ResearchStrategyFamily
from packages.schemas.strategy_policy import (
    IndicatorExitRule,
    InitialStopRule,
    SignalRule,
    StrategyAuthority,
    StrategyAuthorityRecord,
    StrategyCostPolicy,
    StrategyEvidenceSource,
    StrategyExecutionEnvironment,
    StrategyExecutionPolicy,
    StrategyExitPolicy,
    StrategyParameter,
    StrategyRiskPolicy,
    StrategySignalPolicy,
    StrategySpecification,
    StrategyUniversePolicy,
)


REFERENCE_STRATEGY_CATALOG_CONTRACT_VERSION = (
    "reference-strategy-catalog-v1-six-families-nine-direction-specific-policies"
)


def _parameters(**values: bool | int | float | str) -> tuple[StrategyParameter, ...]:
    return tuple(StrategyParameter(name=name, value=value) for name, value in sorted(values.items()))


COMMON_UNIVERSE = StrategyUniversePolicy()
COMMON_EXECUTION = StrategyExecutionPolicy()
COMMON_RISK = StrategyRiskPolicy()
COMMON_COSTS = StrategyCostPolicy()
COMMON_INVALIDATION = (
    "positive net expectancy does not survive the frozen 10 bps primary cost",
    "results are concentrated in one ticker, session, year, or exceptional trade",
    "chronological walk-forward results are unstable or reverse sign",
    "small predeclared neighboring checks materially break the mechanism",
)
COMMON_LONG_LIMITATIONS = (
    "practitioner baseline; external popularity is not evidence of profitability",
    "daily OHLC replay cannot resolve intrabar order beyond adverse-first collision handling",
    "generic bps diagnostics are not an instrument-level execution model",
)
COMMON_SHORT_LIMITATIONS = COMMON_LONG_LIMITATIONS + (
    "short borrow availability, locate fees, recalls, and asymmetric slippage are not yet modeled",
)


REFERENCE_STRATEGY_SPECIFICATIONS = (
    StrategySpecification(
        strategy_id="ma_trend_cross_50_200_long_v1",
        family_id="ma_trend_cross_50_200",
        family=ResearchStrategyFamily.MOVING_AVERAGE_TREND,
        direction=StrategyDirection.LONG,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("Golden Cross", "50/200 simple-moving-average crossover"),
        hypothesis="A slow upside trend transition may persist long enough to overcome costs.",
        signal=StrategySignalPolicy(
            rule=SignalRule.SMA_CROSS_UP,
            trigger_feature="sma_cross_50_200_up",
            required_features=("sma_cross_50_200_up", "sma_50", "sma_200", "atr_14"),
            minimum_history_sessions=201,
            parameters=_parameters(fast_sma=50, slow_sma=200, prior_relation="at_or_below"),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.ATR_FROM_ENTRY,
            initial_atr_multiple=2.0,
            trailing_atr_multiple=3.0,
            indicator_exit_rule=IndicatorExitRule.SMA_REVERSE_CROSS,
            maximum_holding_sessions=126,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_LONG_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="ema_pullback_20_50_long_v1",
        family_id="ema_pullback_20_50",
        family=ResearchStrategyFamily.PULLBACK_CONTINUATION,
        direction=StrategyDirection.LONG,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("20 EMA pullback", "EMA bounce"),
        hypothesis="A short, confirmed retracement inside an established uptrend may resume.",
        signal=StrategySignalPolicy(
            rule=SignalRule.EMA_PULLBACK_RECOVERY_LONG,
            trigger_feature="ema_pullback_recovery_20_50_long",
            required_features=(
                "ema_pullback_recovery_20_50_long",
                "ema_pullback_low_20_50_long",
                "ema_pullback_sessions_20_50_long",
                "ema_20",
                "ema_50",
                "atr_14",
            ),
            minimum_history_sessions=55,
            parameters=_parameters(
                fast_ema=20,
                slow_ema=50,
                touch_tolerance_atr=0.5,
                maximum_pullback_sessions=5,
                pullback_bar_must_intersect_tolerance_zone=True,
                one_bar_touch_and_recovery_allowed=True,
            ),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.PULLBACK_LOW_OR_ATR_FARTHER,
            initial_atr_multiple=1.5,
            profit_target_r=2.5,
            indicator_exit_rule=IndicatorExitRule.CLOSE_BELOW_EMA_50,
            maximum_holding_sessions=15,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_LONG_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="macd_shift_12_26_9_long_v1",
        family_id="macd_shift_12_26_9",
        family=ResearchStrategyFamily.MOMENTUM,
        direction=StrategyDirection.LONG,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("MACD signal crossover below zero",),
        hypothesis="An upside momentum turn below zero may precede broader continuation.",
        signal=StrategySignalPolicy(
            rule=SignalRule.MACD_SIGNAL_CROSS_UP_BELOW_ZERO,
            trigger_feature="macd_signal_cross_up_below_zero",
            required_features=(
                "macd_signal_cross_up_below_zero",
                "macd_12_26",
                "macd_signal_12_26_9",
                "atr_14",
            ),
            minimum_history_sessions=35,
            parameters=_parameters(fast_ema=12, slow_ema=26, signal_ema=9, zero_filter="both_below"),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.ATR_FROM_ENTRY,
            initial_atr_multiple=1.5,
            profit_target_r=3.0,
            indicator_exit_rule=IndicatorExitRule.MACD_OPPOSITE_CROSS,
            maximum_holding_sessions=20,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_LONG_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="macd_shift_12_26_9_short_v1",
        family_id="macd_shift_12_26_9",
        family=ResearchStrategyFamily.MOMENTUM,
        direction=StrategyDirection.SHORT,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("MACD signal crossover above zero",),
        hypothesis="A downside momentum turn above zero may precede broader continuation.",
        signal=StrategySignalPolicy(
            rule=SignalRule.MACD_SIGNAL_CROSS_DOWN_ABOVE_ZERO,
            trigger_feature="macd_signal_cross_down_above_zero",
            required_features=(
                "macd_signal_cross_down_above_zero",
                "macd_12_26",
                "macd_signal_12_26_9",
                "atr_14",
            ),
            minimum_history_sessions=35,
            parameters=_parameters(fast_ema=12, slow_ema=26, signal_ema=9, zero_filter="both_above"),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.ATR_FROM_ENTRY,
            initial_atr_multiple=1.5,
            profit_target_r=3.0,
            indicator_exit_rule=IndicatorExitRule.MACD_OPPOSITE_CROSS,
            maximum_holding_sessions=20,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_SHORT_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="rsi_recovery_14_trend_long_v1",
        family_id="rsi_recovery_14_trend",
        family=ResearchStrategyFamily.MEAN_REVERSION,
        direction=StrategyDirection.LONG,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("RSI oversold recovery", "long-trend mean reversion"),
        hypothesis="A recovery from strong downside momentum inside a long trend may mean-revert.",
        signal=StrategySignalPolicy(
            rule=SignalRule.RSI_RECOVERY_LONG_TREND,
            trigger_feature="rsi_recovery_14_above_30_ema_200_long",
            required_features=(
                "rsi_recovery_14_above_30_ema_200_long",
                "rsi_14",
                "ema_20",
                "ema_200",
                "atr_14",
            ),
            minimum_history_sessions=201,
            parameters=_parameters(rsi_period=14, recovery_level=30.0, trend_ema=200),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.ATR_FROM_ENTRY,
            initial_atr_multiple=2.0,
            indicator_exit_rule=IndicatorExitRule.RSI_60_OR_EMA_20,
            maximum_holding_sessions=10,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_LONG_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="donchian_breakout_20_volume_long_v1",
        family_id="donchian_breakout_20_volume",
        family=ResearchStrategyFamily.PRICE_BREAKOUT,
        direction=StrategyDirection.LONG,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("20-session Donchian breakout", "high-volume breakout"),
        hypothesis="An upside range escape with unusual participation and aligned trend may continue.",
        signal=StrategySignalPolicy(
            rule=SignalRule.DONCHIAN_VOLUME_BREAKOUT_LONG,
            trigger_feature="donchian_breakout_20_volume_long",
            required_features=(
                "donchian_breakout_20_volume_long",
                "prior_high_20",
                "ema_50_slope_1",
                "relative_volume_20",
                "atr_14",
            ),
            minimum_history_sessions=51,
            parameters=_parameters(channel_sessions=20, minimum_relative_volume=1.5, trend_ema=50),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.DONCHIAN_BOUNDARY_OR_ATR_CLOSER,
            initial_atr_multiple=2.0,
            trailing_atr_multiple=3.0,
            maximum_holding_sessions=20,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_LONG_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="donchian_breakout_20_volume_short_v1",
        family_id="donchian_breakout_20_volume",
        family=ResearchStrategyFamily.PRICE_BREAKOUT,
        direction=StrategyDirection.SHORT,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("20-session Donchian breakdown", "high-volume breakdown"),
        hypothesis="A downside range escape with unusual participation and aligned trend may continue.",
        signal=StrategySignalPolicy(
            rule=SignalRule.DONCHIAN_VOLUME_BREAKOUT_SHORT,
            trigger_feature="donchian_breakout_20_volume_short",
            required_features=(
                "donchian_breakout_20_volume_short",
                "prior_low_20",
                "ema_50_slope_1",
                "relative_volume_20",
                "atr_14",
            ),
            minimum_history_sessions=51,
            parameters=_parameters(channel_sessions=20, minimum_relative_volume=1.5, trend_ema=50),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.DONCHIAN_BOUNDARY_OR_ATR_CLOSER,
            initial_atr_multiple=2.0,
            trailing_atr_multiple=3.0,
            maximum_holding_sessions=20,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_SHORT_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="bollinger_squeeze_breakout_20_long_v1",
        family_id="bollinger_squeeze_breakout_20",
        family=ResearchStrategyFamily.VOLATILITY_EXPANSION,
        direction=StrategyDirection.LONG,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("Bollinger Band squeeze breakout",),
        hypothesis="An upside band escape after prior-session compression may begin volatility expansion.",
        signal=StrategySignalPolicy(
            rule=SignalRule.BOLLINGER_SQUEEZE_BREAKOUT_LONG,
            trigger_feature="bollinger_squeeze_breakout_20_long",
            required_features=(
                "bollinger_squeeze_breakout_20_long",
                "bb_mid_20",
                "bb_upper_20",
                "bb_width_p10_prior_126",
                "relative_volume_20",
                "atr_14",
            ),
            minimum_history_sessions=147,
            parameters=_parameters(
                band_sessions=20,
                band_standard_deviations=2.0,
                squeeze_lookback_sessions=126,
                squeeze_percentile=0.10,
                minimum_relative_volume=1.25,
                squeeze_must_occur_prior_session=True,
            ),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.BOLLINGER_MID_OR_ATR_CLOSER,
            initial_atr_multiple=1.5,
            profit_target_r=3.0,
            trailing_atr_multiple=2.0,
            maximum_holding_sessions=20,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_LONG_LIMITATIONS,
    ),
    StrategySpecification(
        strategy_id="bollinger_squeeze_breakout_20_short_v1",
        family_id="bollinger_squeeze_breakout_20",
        family=ResearchStrategyFamily.VOLATILITY_EXPANSION,
        direction=StrategyDirection.SHORT,
        evidence_source=StrategyEvidenceSource.PRACTITIONER_BASELINE,
        source_labels=("Bollinger Band squeeze breakdown",),
        hypothesis="A downside band escape after prior-session compression may begin volatility expansion.",
        signal=StrategySignalPolicy(
            rule=SignalRule.BOLLINGER_SQUEEZE_BREAKOUT_SHORT,
            trigger_feature="bollinger_squeeze_breakout_20_short",
            required_features=(
                "bollinger_squeeze_breakout_20_short",
                "bb_mid_20",
                "bb_lower_20",
                "bb_width_p10_prior_126",
                "relative_volume_20",
                "atr_14",
            ),
            minimum_history_sessions=147,
            parameters=_parameters(
                band_sessions=20,
                band_standard_deviations=2.0,
                squeeze_lookback_sessions=126,
                squeeze_percentile=0.10,
                minimum_relative_volume=1.25,
                squeeze_must_occur_prior_session=True,
            ),
        ),
        universe=COMMON_UNIVERSE,
        execution=COMMON_EXECUTION,
        exit=StrategyExitPolicy(
            initial_stop_rule=InitialStopRule.BOLLINGER_MID_OR_ATR_CLOSER,
            initial_atr_multiple=1.5,
            profit_target_r=3.0,
            trailing_atr_multiple=2.0,
            maximum_holding_sessions=20,
        ),
        risk=COMMON_RISK,
        costs=COMMON_COSTS,
        invalidation_conditions=COMMON_INVALIDATION,
        limitations=COMMON_SHORT_LIMITATIONS,
    ),
)


class ReferenceStrategyCatalog:
    def __init__(self, specifications: tuple[StrategySpecification, ...]) -> None:
        if not specifications:
            raise ValueError("reference strategy catalog cannot be empty")
        self._specifications: dict[str, StrategySpecification] = {}
        for specification in specifications:
            if specification.strategy_id in self._specifications:
                raise ValueError(f"duplicate reference strategy: {specification.strategy_id}")
            self._specifications[specification.strategy_id] = specification

    def get(self, strategy_id: str) -> StrategySpecification:
        try:
            return self._specifications[strategy_id]
        except KeyError as exc:
            raise KeyError(f"unknown reference strategy: {strategy_id}") from exc

    def all(self) -> tuple[StrategySpecification, ...]:
        return tuple(self._specifications[key] for key in sorted(self._specifications))

    def family_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item.family_id for item in self.all()}))

    def fingerprint(self) -> str:
        payload = {
            "contract_version": REFERENCE_STRATEGY_CATALOG_CONTRACT_VERSION,
            "strategies": [item.model_dump(mode="json") for item in self.all()],
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


REFERENCE_STRATEGY_CATALOG = ReferenceStrategyCatalog(REFERENCE_STRATEGY_SPECIFICATIONS)
REFERENCE_STRATEGY_POLICY_FINGERPRINT = (
    "26a6aae124b1a5d2b14b8a11a72671b06ac34d3cf94eb7ac47f16d2cfb94a8b3"
)
if REFERENCE_STRATEGY_CATALOG.fingerprint() != REFERENCE_STRATEGY_POLICY_FINGERPRINT:
    raise RuntimeError("frozen reference strategy policy fingerprint drifted")

REFERENCE_STRATEGY_AUTHORITIES = tuple(
    StrategyAuthorityRecord(
        strategy_id=specification.strategy_id,
        strategy_policy_fingerprint=specification.fingerprint(),
        authority=StrategyAuthority.RESEARCH,
        allowed_environments=(StrategyExecutionEnvironment.RESEARCH_REPLAY,),
        evidence_references=(
            "README.md practitioner-baseline boundary",
            "docs/roadmap.md section 13 frozen starting specifications",
        ),
    )
    for specification in REFERENCE_STRATEGY_CATALOG.all()
)


def reference_authority_fingerprint() -> str:
    payload = [item.model_dump(mode="json") for item in REFERENCE_STRATEGY_AUTHORITIES]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT = (
    "a23ec27367ae540b869abc428d118241e84436719a8a543cbdbc3f3b678c69c5"
)
if reference_authority_fingerprint() != REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT:
    raise RuntimeError("frozen reference strategy authority fingerprint drifted")
