from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Mapping

from packages.schemas.strategy import MLProbabilityEvidence, StrategyAssessment

from .metadata import StrategyMetadata


@dataclass(frozen=True, slots=True)
class StrategyContext:
    instrument_id: str
    ticker: str
    as_of_date: date
    features: Mapping[str, float]
    ml_probability_evidence: MLProbabilityEvidence | None = None

    def require(self, names: tuple[str, ...]) -> dict[str, float]:
        missing = [name for name in names if name not in self.features]
        if missing:
            raise KeyError(f"strategy context missing required features: {', '.join(missing)}")
        return {name: float(self.features[name]) for name in names}


class Strategy(ABC):
    """Regime-agnostic strategy setup evaluator.

    Implementations inspect point-in-time feature evidence only. Regime routing is
    deliberately owned by the external router and must not be embedded here.
    """

    @property
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        raise NotImplementedError

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategyAssessment:
        raise NotImplementedError
