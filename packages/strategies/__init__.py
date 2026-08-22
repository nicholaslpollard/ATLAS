"""ATLAS strategy catalog, rule evaluation, and external regime routing."""

from .base import Strategy, StrategyContext
from .metadata import STRATEGY_METADATA_CONTRACT_VERSION, StrategyMetadata
from .registry import DEFAULT_STRATEGY_REGISTRY, STRATEGY_REGISTRY_CONTRACT_VERSION, StrategyRegistry
from .router import STRATEGY_ROUTER_CONTRACT_VERSION, StrategyRouter, StrategyRoutingContext
from .rules import STRATEGY_RULE_CONTRACT_VERSION, Comparison, FeatureCondition, RuleStrategy

__all__ = [
    "Comparison",
    "DEFAULT_STRATEGY_REGISTRY",
    "FeatureCondition",
    "RuleStrategy",
    "STRATEGY_METADATA_CONTRACT_VERSION",
    "STRATEGY_REGISTRY_CONTRACT_VERSION",
    "STRATEGY_ROUTER_CONTRACT_VERSION",
    "STRATEGY_RULE_CONTRACT_VERSION",
    "Strategy",
    "StrategyContext",
    "StrategyMetadata",
    "StrategyRegistry",
    "StrategyRouter",
    "StrategyRoutingContext",
]
