from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    name: str
    family: str
    version: str
    minimum_history_bars: int
    dependencies: tuple[str, ...]
    recursive: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("feature name cannot be blank")
        if not self.family.strip():
            raise ValueError("feature family cannot be blank")
        if not self.version.strip():
            raise ValueError("feature version cannot be blank")
        if self.minimum_history_bars < 1:
            raise ValueError("minimum_history_bars must be at least 1")
        if not self.dependencies:
            raise ValueError("feature dependencies cannot be empty")


class FeatureRegistry:
    """Immutable-by-convention registry for reproducible feature contracts."""

    def __init__(self, definitions: tuple[FeatureDefinition, ...] = ()) -> None:
        self._definitions: dict[str, FeatureDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: FeatureDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"feature is already registered: {definition.name}")
        self._definitions[definition.name] = definition

    def get(self, name: str) -> FeatureDefinition:
        try:
            return self._definitions[name]
        except KeyError as exc:
            raise KeyError(f"unknown feature: {name}") from exc

    def all(self) -> tuple[FeatureDefinition, ...]:
        return tuple(self._definitions[name] for name in sorted(self._definitions))

    def fingerprint(self) -> str:
        payload = [asdict(definition) for definition in self.all()]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


CORE_FEATURE_CONTRACT_VERSION = "features-v1-wilder-and-explicit-warmup"


def _definition(
    name: str,
    family: str,
    minimum_history_bars: int,
    dependencies: tuple[str, ...],
    *,
    recursive: bool = False,
    description: str = "",
) -> FeatureDefinition:
    return FeatureDefinition(
        name=name,
        family=family,
        version=CORE_FEATURE_CONTRACT_VERSION,
        minimum_history_bars=minimum_history_bars,
        dependencies=dependencies,
        recursive=recursive,
        description=description,
    )


CORE_FEATURE_DEFINITIONS = (
    _definition("return_1", "momentum", 2, ("close",)),
    _definition("log_return_1", "momentum", 2, ("close",)),
    _definition("sma_20", "trend", 20, ("close",)),
    _definition("ema_20", "trend", 20, ("close",), recursive=True),
    _definition("ema_50", "trend", 50, ("close",), recursive=True),
    _definition("ema_200", "trend", 200, ("close",), recursive=True),
    _definition("rsi_14", "momentum", 15, ("close",), recursive=True),
    _definition("macd_12_26", "momentum", 26, ("close",), recursive=True),
    _definition("macd_signal_12_26_9", "momentum", 34, ("close",), recursive=True),
    _definition("macd_hist_12_26_9", "momentum", 34, ("close",), recursive=True),
    _definition("true_range", "volatility", 1, ("high", "low", "close")),
    _definition("atr_14", "volatility", 14, ("high", "low", "close"), recursive=True),
    _definition("natr_14", "volatility", 14, ("high", "low", "close"), recursive=True),
    _definition("bb_mid_20", "volatility", 20, ("close",)),
    _definition("bb_upper_20", "volatility", 20, ("close",)),
    _definition("bb_lower_20", "volatility", 20, ("close",)),
    _definition("bb_width_20", "volatility", 20, ("close",)),
    _definition("bb_position_20", "volatility", 20, ("close",)),
    _definition("realized_volatility_20", "volatility", 21, ("close",)),
    _definition("obv", "volume", 1, ("close", "volume"), recursive=True),
    _definition("relative_volume_20", "volume", 20, ("volume",)),
    _definition("volume_zscore_20", "volume", 20, ("volume",)),
    _definition("dollar_volume", "volume", 1, ("close", "volume")),
    _definition("relative_dollar_volume_20", "volume", 20, ("close", "volume")),
    _definition("range_position_20", "structure", 20, ("close", "high", "low")),
    _definition("prior_high_20", "structure", 21, ("high",)),
    _definition("prior_low_20", "structure", 21, ("low",)),
    _definition("breakout_distance_20", "structure", 21, ("close", "high")),
    _definition("breakdown_distance_20", "structure", 21, ("close", "low")),
    _definition("drawdown_20", "structure", 20, ("close",)),
    _definition("ema_20_slope_1", "trend", 21, ("close",), recursive=True),
    _definition("price_distance_ema_20", "trend", 20, ("close",), recursive=True),
    _definition("directional_efficiency_20", "trend", 21, ("close",)),
)

CORE_FEATURE_REGISTRY = FeatureRegistry(CORE_FEATURE_DEFINITIONS)
