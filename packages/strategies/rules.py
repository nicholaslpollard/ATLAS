from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from packages.schemas.strategy import StrategyAssessment

from .base import Strategy, StrategyContext
from .metadata import StrategyMetadata


STRATEGY_RULE_CONTRACT_VERSION = "strategy-rule-v1-sign-and-relative-structure-no-regime-logic"


class Comparison(StrEnum):
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"


@dataclass(frozen=True, slots=True)
class FeatureCondition:
    left: str
    comparison: Comparison
    right_feature: str | None = None
    right_value: float | None = None
    reason_code: str = "condition"

    def __post_init__(self) -> None:
        if not self.left.strip():
            raise ValueError("condition left feature cannot be blank")
        if (self.right_feature is None) == (self.right_value is None):
            raise ValueError("condition requires exactly one right_feature or right_value")
        if self.right_feature is not None and not self.right_feature.strip():
            raise ValueError("condition right_feature cannot be blank")
        if not self.reason_code.strip():
            raise ValueError("condition reason_code cannot be blank")

    @property
    def required_features(self) -> tuple[str, ...]:
        if self.right_feature is None:
            return (self.left,)
        return (self.left, self.right_feature)

    def evaluate(self, features: dict[str, float]) -> tuple[bool, dict[str, float | str | bool]]:
        left_value = float(features[self.left])
        right_value = (
            float(features[self.right_feature])
            if self.right_feature is not None
            else float(self.right_value)
        )
        if not math.isfinite(left_value) or not math.isfinite(right_value):
            return False, {
                "left": self.left,
                "left_value": left_value,
                "comparison": self.comparison.value,
                "right": self.right_feature if self.right_feature is not None else "constant",
                "right_value": right_value,
                "met": False,
            }
        if self.comparison == Comparison.GT:
            met = left_value > right_value
        elif self.comparison == Comparison.GE:
            met = left_value >= right_value
        elif self.comparison == Comparison.LT:
            met = left_value < right_value
        else:
            met = left_value <= right_value
        return met, {
            "left": self.left,
            "left_value": left_value,
            "comparison": self.comparison.value,
            "right": self.right_feature if self.right_feature is not None else "constant",
            "right_value": right_value,
            "met": met,
        }


class RuleStrategy(Strategy):
    """Auditable conjunction of point-in-time feature conditions."""

    def __init__(self, metadata: StrategyMetadata, conditions: tuple[FeatureCondition, ...]) -> None:
        if not conditions:
            raise ValueError("rule strategy requires at least one condition")
        required = tuple(sorted({name for condition in conditions for name in condition.required_features}))
        if tuple(sorted(metadata.required_features)) != required:
            raise ValueError("strategy metadata required_features do not match rule conditions")
        self._metadata = metadata
        self.conditions = conditions

    @property
    def metadata(self) -> StrategyMetadata:
        return self._metadata

    def evaluate(self, context: StrategyContext) -> StrategyAssessment:
        features = context.require(self.metadata.required_features)
        evidence: dict[str, object] = {
            "rule_contract_version": STRATEGY_RULE_CONTRACT_VERSION,
            "conditions": [],
        }
        reason_codes: list[str] = []
        met_count = 0
        details: list[dict[str, float | str | bool]] = []
        for condition in self.conditions:
            met, detail = condition.evaluate(features)
            details.append(detail)
            if met:
                met_count += 1
                reason_codes.append(f"MET:{condition.reason_code}")
            else:
                reason_codes.append(f"MISS:{condition.reason_code}")
        evidence["conditions"] = details
        return StrategyAssessment(
            strategy_id=self.metadata.strategy_id,
            family=self.metadata.family,
            direction=self.metadata.direction,
            instrument_id=context.instrument_id,
            ticker=context.ticker,
            as_of_date=context.as_of_date,
            fired=met_count == len(self.conditions),
            conditions_met=met_count,
            condition_count=len(self.conditions),
            evidence_score=met_count / len(self.conditions),
            evidence=evidence,
            reason_codes=tuple(reason_codes),
            ml_probability_evidence=context.ml_probability_evidence,
        )
