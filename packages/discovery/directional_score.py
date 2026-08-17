from __future__ import annotations

import numpy as np
import pandas as pd


DIRECTIONAL_SCORE_POLICY_VERSION = "directional-score-v1-available-timeframe-weighted"
TIMEFRAME_WEIGHTS = {"1d": 0.30, "4h": 0.40, "1h": 0.30}
DIRECTION_MARGIN = 0.08

_DIRECTIONAL_COLUMNS = (
    "trend_bull",
    "trend_bear",
    "momentum_bull",
    "momentum_bear",
    "breakout_bull",
    "breakdown_bear",
    "pullback_bull",
    "pullback_bear",
    "reversal_bull",
    "reversal_bear",
    "mean_reversion_bull",
    "mean_reversion_bear",
    "unusual_volume",
    "volatility_expansion",
)


def weighted_available(
    timeframe_scores: dict[str, pd.DataFrame],
    column: str,
) -> pd.Series:
    """Weight available timeframe evidence and renormalize around missing inputs."""

    if not timeframe_scores:
        return pd.Series(dtype="float64")
    index = next(iter(timeframe_scores.values())).index
    numerator = pd.Series(0.0, index=index, dtype="float64")
    denominator = pd.Series(0.0, index=index, dtype="float64")
    for timeframe, frame in timeframe_scores.items():
        weight = TIMEFRAME_WEIGHTS[timeframe]
        values = pd.to_numeric(frame.get(column), errors="coerce")
        available = values.notna()
        numerator = numerator + values.fillna(0.0) * weight
        denominator = denominator + available.astype("float64") * weight
    return (numerator / denominator.where(denominator > 0.0)).clip(0.0, 1.0)


def _positive_percentile(values: pd.Series) -> pd.Series:
    positive = values.where(values > 0.0)
    ranked = positive.rank(method="average", pct=True)
    return ranked.fillna(0.0).clip(0.0, 1.0)


def aggregate_multitimeframe(timeframe_scores: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Aggregate normalized timeframe evidence into setup and directional scores."""

    if not timeframe_scores:
        return pd.DataFrame()
    index = next(iter(timeframe_scores.values())).index
    out = pd.DataFrame(index=index)
    for column in _DIRECTIONAL_COLUMNS:
        out[column] = weighted_available(timeframe_scores, column)

    bull_base = (
        0.60 * out["trend_bull"].fillna(0.0)
        + 0.40 * out["momentum_bull"].fillna(0.0)
    )
    bear_base = (
        0.60 * out["trend_bear"].fillna(0.0)
        + 0.40 * out["momentum_bear"].fillna(0.0)
    )
    signed_strength = bull_base - bear_base
    out["relative_strength_bull"] = _positive_percentile(signed_strength)
    out["relative_strength_bear"] = _positive_percentile(-signed_strength)

    out["trend_score"] = out[["trend_bull", "trend_bear"]].max(axis=1).fillna(0.0)
    out["momentum_score"] = out[["momentum_bull", "momentum_bear"]].max(axis=1).fillna(0.0)
    out["breakout_score"] = out["breakout_bull"].fillna(0.0)
    out["breakdown_score"] = out["breakdown_bear"].fillna(0.0)
    out["pullback_score"] = out[["pullback_bull", "pullback_bear"]].max(axis=1).fillna(0.0)
    out["reversal_score"] = out[["reversal_bull", "reversal_bear"]].max(axis=1).fillna(0.0)
    out["mean_reversion_score"] = out[
        ["mean_reversion_bull", "mean_reversion_bear"]
    ].max(axis=1).fillna(0.0)
    out["relative_strength_score"] = out[
        ["relative_strength_bull", "relative_strength_bear"]
    ].max(axis=1).fillna(0.0)
    out["unusual_volume_score"] = out["unusual_volume"].fillna(0.0)
    out["volatility_expansion_score"] = out["volatility_expansion"].fillna(0.0)

    bull_core = out[
        [
            "trend_bull",
            "momentum_bull",
            "breakout_bull",
            "pullback_bull",
            "reversal_bull",
            "mean_reversion_bull",
            "relative_strength_bull",
        ]
    ].mean(axis=1, skipna=True).fillna(0.0)
    bear_core = out[
        [
            "trend_bear",
            "momentum_bear",
            "breakdown_bear",
            "pullback_bear",
            "reversal_bear",
            "mean_reversion_bear",
            "relative_strength_bear",
        ]
    ].mean(axis=1, skipna=True).fillna(0.0)
    context = (
        0.55 * out["unusual_volume_score"]
        + 0.45 * out["volatility_expansion_score"]
    )
    out["bull_evidence"] = (0.85 * bull_core + 0.15 * context).clip(0.0, 1.0)
    out["bear_evidence"] = (0.85 * bear_core + 0.15 * context).clip(0.0, 1.0)

    setup_columns = [
        "trend_score",
        "momentum_score",
        "breakout_score",
        "pullback_score",
        "reversal_score",
        "mean_reversion_score",
        "relative_strength_score",
        "unusual_volume_score",
        "volatility_expansion_score",
        "breakdown_score",
    ]
    setup_matrix = out[setup_columns]
    out["top_setup"] = setup_matrix.idxmax(axis=1).str.removesuffix("_score")
    out["top_setup_score"] = setup_matrix.max(axis=1)
    dominant = out[["bull_evidence", "bear_evidence"]].max(axis=1)
    contradiction = out[["bull_evidence", "bear_evidence"]].min(axis=1)
    out["priority_score"] = (
        0.70 * dominant
        + 0.20 * out["top_setup_score"]
        + 0.10 * context
        - 0.20 * contradiction
    ).clip(0.0, 1.0)

    delta = out["bull_evidence"] - out["bear_evidence"]
    out["direction"] = np.select(
        [delta >= DIRECTION_MARGIN, delta <= -DIRECTION_MARGIN],
        ["bullish", "bearish"],
        default="neutral",
    )
    return out
