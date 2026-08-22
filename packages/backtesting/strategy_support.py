from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .strategy_evaluation import StrategyEvaluationSummary


STRATEGY_SUPPORT_POLICY_CONTRACT_VERSION = (
    "strategy-support-policy-v1-positive-10bps-mean-both-chronological-halves"
)
STRATEGY_SUPPORT_PRIMARY_COST_BPS = 10.0


class StrategySupportStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    MIXED = "MIXED"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class StrategySupportDecision:
    contract_version: str
    strategy_id: str
    status: StrategySupportStatus
    primary_cost_bps: float
    development_mean_return: float | None
    first_half_mean_return: float | None
    second_half_mean_return: float | None
    development_rows: int
    first_half_rows: int
    second_half_rows: int
    reason_codes: tuple[str, ...]

    @property
    def eligible_for_candidate_promotion(self) -> bool:
        return self.status == StrategySupportStatus.SUPPORTED


def _metric(summary: StrategyEvaluationSummary):
    key = format(STRATEGY_SUPPORT_PRIMARY_COST_BPS, "g")
    if key not in summary.aggregate_by_cost_bps:
        raise ValueError(f"evaluation summary is missing locked {key} bps cost evidence")
    return summary.aggregate_by_cost_bps[key]


def classify_strategy_support(
    *,
    development: StrategyEvaluationSummary,
    first_half: StrategyEvaluationSummary,
    second_half: StrategyEvaluationSummary,
) -> StrategySupportDecision:
    if not (
        development.strategy_id == first_half.strategy_id == second_half.strategy_id
    ):
        raise ValueError("strategy support summaries must refer to the same strategy")

    dev = _metric(development)
    first = _metric(first_half)
    second = _metric(second_half)
    reasons: list[str] = []
    if min(dev.rows, first.rows, second.rows) <= 0:
        status = StrategySupportStatus.INSUFFICIENT
        reasons.append("INSUFFICIENT:ONE_OR_MORE_DEVELOPMENT_SLICES_EMPTY")
    elif dev.mean_return is None or first.mean_return is None or second.mean_return is None:
        status = StrategySupportStatus.INSUFFICIENT
        reasons.append("INSUFFICIENT:MEAN_RETURN_UNAVAILABLE")
    elif dev.mean_return > 0.0 and first.mean_return > 0.0 and second.mean_return > 0.0:
        status = StrategySupportStatus.SUPPORTED
        reasons.extend(
            (
                "SUPPORTED:DEVELOPMENT_MEAN_POSITIVE_AFTER_10BPS",
                "SUPPORTED:FIRST_HALF_MEAN_POSITIVE_AFTER_10BPS",
                "SUPPORTED:SECOND_HALF_MEAN_POSITIVE_AFTER_10BPS",
            )
        )
    elif dev.mean_return > 0.0:
        status = StrategySupportStatus.MIXED
        reasons.append("MIXED:AGGREGATE_POSITIVE_BUT_CHRONOLOGICAL_STABILITY_FAILED")
    else:
        status = StrategySupportStatus.UNSUPPORTED
        reasons.append("UNSUPPORTED:DEVELOPMENT_MEAN_NOT_POSITIVE_AFTER_10BPS")

    return StrategySupportDecision(
        contract_version=STRATEGY_SUPPORT_POLICY_CONTRACT_VERSION,
        strategy_id=development.strategy_id,
        status=status,
        primary_cost_bps=STRATEGY_SUPPORT_PRIMARY_COST_BPS,
        development_mean_return=dev.mean_return,
        first_half_mean_return=first.mean_return,
        second_half_mean_return=second.mean_return,
        development_rows=dev.rows,
        first_half_rows=first.rows,
        second_half_rows=second.rows,
        reason_codes=tuple(reasons),
    )
