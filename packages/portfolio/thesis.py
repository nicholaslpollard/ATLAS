from __future__ import annotations

import math
from collections.abc import Mapping

from packages.portfolio.phase13_policy import (
    PHASE13_GEOMETRY_ENTRY_SOURCE,
    PHASE13_GEOMETRY_REQUIRES_REWARD_GT_RISK,
    PHASE13_GEOMETRY_REWARD_RULE,
    PHASE13_GEOMETRY_RISK_RULE,
    PHASE13_HORIZON_SESSIONS,
)
from packages.schemas.case_file import GeometryStatus, TradeGeometry
from packages.schemas.deep_research import DeepResearchCase
from packages.schemas.discovery_score import DiscoveryDirection


class Phase13GeometryError(ValueError):
    pass


def _unavailable(direction: DiscoveryDirection, reason: str) -> TradeGeometry:
    return TradeGeometry(
        status=GeometryStatus.UNAVAILABLE,
        direction=direction,
        horizon_sessions=PHASE13_HORIZON_SESSIONS,
        reason_codes=(reason, "NO_EXECUTABLE_GEOMETRY_CREATED"),
    )


def build_trade_geometry(
    research: DeepResearchCase,
    *,
    reference_close: float,
    feature_values: Mapping[str, float],
) -> TradeGeometry:
    """Build deterministic reference geometry from accepted current/scenario evidence.

    ``reference_close`` is the accepted current canonical daily close. It is a planning
    reference only and is never treated as a fill price. The Phase 12 path scenarios
    are already direction-adjusted, so adverse excursion is negative and favorable
    excursion is positive for both bullish and bearish cases.
    """

    direction = research.direction
    if direction not in {DiscoveryDirection.BULLISH, DiscoveryDirection.BEARISH}:
        return _unavailable(direction, "NON_DIRECTIONAL_CASE")
    if not research.research_complete or not research.scenarios.available:
        return _unavailable(direction, "PHASE12_RESEARCH_OR_SCENARIOS_INCOMPLETE")
    if research.scenarios.max_adverse_excursion is None or research.scenarios.max_favorable_excursion is None:
        return _unavailable(direction, "PHASE12_PATH_EXCURSION_EVIDENCE_MISSING")

    try:
        entry = float(reference_close)
        natr = float(feature_values["natr_14"])
        mae_p10 = float(research.scenarios.max_adverse_excursion.p10)
        mfe_p75 = float(research.scenarios.max_favorable_excursion.p75)
    except (KeyError, TypeError, ValueError) as exc:
        raise Phase13GeometryError("Phase 13 geometry inputs are malformed") from exc

    if not all(math.isfinite(value) for value in (entry, natr, mae_p10, mfe_p75)):
        return _unavailable(direction, "NONFINITE_GEOMETRY_EVIDENCE")
    if entry <= 0.0 or natr <= 0.0 or mfe_p75 <= 0.0:
        return _unavailable(direction, "NONPOSITIVE_GEOMETRY_EVIDENCE")

    risk_fraction = max(natr, abs(min(0.0, mae_p10)))
    reward_fraction = mfe_p75
    if risk_fraction <= 0.0:
        return _unavailable(direction, "NONPOSITIVE_RISK_DISTANCE")
    if PHASE13_GEOMETRY_REQUIRES_REWARD_GT_RISK and reward_fraction <= risk_fraction:
        return _unavailable(direction, "EMPIRICAL_REWARD_DOES_NOT_EXCEED_RISK")

    if direction == DiscoveryDirection.BULLISH:
        stop = entry * (1.0 - risk_fraction)
        target = entry * (1.0 + reward_fraction)
    else:
        stop = entry * (1.0 + risk_fraction)
        target = entry * (1.0 - reward_fraction)
    if stop <= 0.0 or target <= 0.0:
        return _unavailable(direction, "REFERENCE_GEOMETRY_PRODUCED_NONPOSITIVE_PRICE")

    return TradeGeometry(
        status=GeometryStatus.AVAILABLE,
        direction=direction,
        horizon_sessions=PHASE13_HORIZON_SESSIONS,
        reference_entry=entry,
        stop=stop,
        target=target,
        risk_fraction=risk_fraction,
        reward_fraction=reward_fraction,
        reward_to_risk=reward_fraction / risk_fraction,
        natr_14=natr,
        empirical_mae_p10=mae_p10,
        empirical_mfe_p75=mfe_p75,
        reference_only_not_fill=True,
        reason_codes=(
            PHASE13_GEOMETRY_ENTRY_SOURCE,
            PHASE13_GEOMETRY_RISK_RULE,
            PHASE13_GEOMETRY_REWARD_RULE,
            "STRICT_DIRECTIONAL_GEOMETRY_VALIDATED",
        ),
    )
