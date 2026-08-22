from __future__ import annotations

import math

from packages.portfolio.phase13_policy import (
    PHASE13_MAX_ABS_CORRELATION,
    PHASE13_MAX_GROSS_NOTIONAL_FRACTION,
    PHASE13_MAX_OPEN_POSITIONS,
    PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION,
    PHASE13_RISK_PER_TRADE_FRACTION,
    PHASE13_SECTOR_CONCENTRATION_POLICY,
)
from packages.schemas.case_file import (
    GeometryStatus,
    PortfolioRiskAssessment,
    PortfolioRiskStatus,
    PortfolioSnapshot,
    TradeGeometry,
)


class Phase13RiskError(ValueError):
    pass


def unavailable_risk(reason: str) -> PortfolioRiskAssessment:
    return PortfolioRiskAssessment(
        status=PortfolioRiskStatus.UNAVAILABLE,
        proposed_quantity_is_order=False,
        reason_codes=(reason, "BROKER_NEUTRAL_RISK_EVIDENCE_NOT_GUESSED"),
    )


def evaluate_portfolio_risk(
    geometry: TradeGeometry,
    *,
    instrument_id: str,
    ticker: str,
    snapshot: PortfolioSnapshot | None,
    max_abs_correlation: float | None = None,
) -> PortfolioRiskAssessment:
    """Evaluate a risk-budget quantity without mutating or placing anything.

    The quantity is the direct result of the preregistered per-trade risk budget. ATLAS
    does not silently shrink it to make other limits pass; instead it reports REJECTED
    when that proposed plan violates a portfolio limit.
    """

    if geometry.status != GeometryStatus.AVAILABLE:
        return unavailable_risk("GEOMETRY_UNAVAILABLE")
    if snapshot is None:
        return unavailable_risk("PORTFOLIO_SNAPSHOT_UNAVAILABLE")
    if geometry.reference_entry is None or geometry.stop is None:
        raise Phase13RiskError("available geometry is missing entry/stop")

    entry = float(geometry.reference_entry)
    per_share_risk = abs(entry - float(geometry.stop))
    if not math.isfinite(per_share_risk) or per_share_risk <= 0.0:
        raise Phase13RiskError("geometry per-share risk is invalid")

    existing = next((item for item in snapshot.positions if item.instrument_id == instrument_id), None)
    other_positions = [item for item in snapshot.positions if item.instrument_id != instrument_id]
    if other_positions and max_abs_correlation is None:
        return unavailable_risk("CORRELATION_EVIDENCE_REQUIRED_FOR_EXISTING_PORTFOLIO")
    resolved_corr = 0.0 if not other_positions else float(max_abs_correlation)
    if not math.isfinite(resolved_corr) or not 0.0 <= resolved_corr <= 1.0:
        raise Phase13RiskError("max_abs_correlation must be finite within [0, 1]")

    risk_budget = float(snapshot.equity) * PHASE13_RISK_PER_TRADE_FRACTION
    raw_quantity = math.floor(risk_budget / per_share_risk)
    proposed_quantity = max(1, int(raw_quantity))
    proposed_notional = proposed_quantity * entry
    proposed_loss_at_stop = proposed_quantity * per_share_risk

    existing_name_value = 0.0 if existing is None else abs(float(existing.signed_market_value))
    projected_single_name = (existing_name_value + proposed_notional) / float(snapshot.equity)
    projected_gross = (float(snapshot.gross_market_value) + proposed_notional) / float(snapshot.equity)
    projected_position_count = len(snapshot.positions) + (0 if existing is not None else 1)

    checks = {
        "risk_budget": proposed_loss_at_stop <= risk_budget + 1e-12,
        "single_name": projected_single_name <= PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION + 1e-12,
        "gross": projected_gross <= PHASE13_MAX_GROSS_NOTIONAL_FRACTION + 1e-12,
        "position_count": projected_position_count <= PHASE13_MAX_OPEN_POSITIONS,
        "correlation": resolved_corr <= PHASE13_MAX_ABS_CORRELATION + 1e-12,
    }
    status = PortfolioRiskStatus.ADMISSIBLE if all(checks.values()) else PortfolioRiskStatus.REJECTED
    reasons = [
        "BROKER_NEUTRAL_PORTFOLIO_SNAPSHOT_EVALUATED",
        f"SECTOR_CONCENTRATION_{PHASE13_SECTOR_CONCENTRATION_POLICY}",
    ]
    reasons.extend(f"{name.upper()}_{'PASS' if passed else 'FAIL'}" for name, passed in checks.items())
    reasons.append("PROPOSED_QUANTITY_IS_PLANNING_EVIDENCE_NOT_ORDER")

    return PortfolioRiskAssessment(
        status=status,
        proposed_risk_budget=risk_budget,
        proposed_quantity=proposed_quantity,
        proposed_notional=proposed_notional,
        projected_single_name_fraction=projected_single_name,
        projected_gross_fraction=projected_gross,
        max_abs_correlation=resolved_corr,
        open_positions_before=len(snapshot.positions),
        proposed_quantity_is_order=False,
        reason_codes=tuple(reasons),
    )
