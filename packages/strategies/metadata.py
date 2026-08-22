from __future__ import annotations

from dataclasses import dataclass

from packages.schemas.strategy import StrategyDirection, StrategyFamily


STRATEGY_METADATA_CONTRACT_VERSION = "strategy-metadata-v1-daily-feature-auditable-catalog"


@dataclass(frozen=True, slots=True)
class StrategyMetadata:
    strategy_id: str
    family: StrategyFamily
    direction: StrategyDirection
    required_features: tuple[str, ...]
    description: str
    contract_version: str = STRATEGY_METADATA_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id cannot be blank")
        if not self.required_features:
            raise ValueError("strategy metadata requires at least one feature")
        if len(self.required_features) != len(set(self.required_features)):
            raise ValueError("strategy required_features must be unique")
        if not self.description.strip():
            raise ValueError("strategy description cannot be blank")
