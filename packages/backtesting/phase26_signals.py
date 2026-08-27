from __future__ import annotations

import pandas as pd

from .phase26_policy import (
    PHASE26_BEAR_BLOCKS,
    PHASE26_BULL_BLOCKS,
    Phase26CandidateSpec,
    SignalCondition,
)


class Phase26SignalError(ValueError):
    pass


def condition_mask(frame: pd.DataFrame, condition: SignalCondition) -> pd.Series:
    if condition.feature not in frame.columns:
        raise Phase26SignalError(f"missing Phase26 signal field: {condition.feature}")
    values = pd.to_numeric(frame[condition.feature], errors="coerce")
    op = condition.operator
    if op == "GT":
        mask = values > condition.value
    elif op == "GE":
        mask = values >= condition.value
    elif op == "LT":
        mask = values < condition.value
    elif op == "LE":
        mask = values <= condition.value
    elif op == "BETWEEN":
        if condition.upper is None:
            raise Phase26SignalError(
                f"BETWEEN condition is missing upper bound: {condition.feature}"
            )
        if condition.upper < condition.value:
            raise Phase26SignalError(
                f"BETWEEN upper bound is below lower bound: {condition.feature}"
            )
        mask = values.between(condition.value, condition.upper, inclusive="both")
    else:  # pragma: no cover - Literal plus policy tests keep this unreachable.
        raise Phase26SignalError(f"unsupported Phase26 condition operator: {op}")
    return mask.fillna(False).astype(bool)


def conditions_mask(
    frame: pd.DataFrame,
    conditions: tuple[SignalCondition, ...],
) -> pd.Series:
    result = pd.Series(True, index=frame.index, dtype=bool)
    for condition in conditions:
        result &= condition_mask(frame, condition)
    return result


def apply_composite_scores(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    bull_score = pd.Series(0, index=result.index, dtype="int64")
    bear_score = pd.Series(0, index=result.index, dtype="int64")
    for block in PHASE26_BULL_BLOCKS:
        bull_score += conditions_mask(result, block).astype("int64")
    for block in PHASE26_BEAR_BLOCKS:
        bear_score += conditions_mask(result, block).astype("int64")
    result["bull_block_score"] = bull_score
    result["bear_block_score"] = bear_score
    return result


def candidate_mask(frame: pd.DataFrame, candidate: Phase26CandidateSpec) -> pd.Series:
    expected_direction = "bullish" if candidate.direction == "LONG" else "bearish"
    if "direction" not in frame.columns:
        raise Phase26SignalError("Phase26 observation frame is missing direction")
    direction = frame["direction"].astype("string") == expected_direction
    return direction.fillna(False) & conditions_mask(frame, candidate.conditions)
