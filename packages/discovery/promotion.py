from __future__ import annotations

from collections.abc import Mapping

from packages.schemas.candidate_promotion import (
    CandidatePromotionRecord,
    StrategyHistoricalSupportSnapshot,
)
from packages.schemas.discovery_score import DiscoveryDirection, DiscoveryState
from packages.schemas.discovery_state import DiscoveryStateRecord
from packages.schemas.strategy import MLProbabilityEvidence
from packages.strategies.base import StrategyContext
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY, StrategyRegistry
from packages.strategies.router import StrategyRouter, StrategyRoutingContext


CANDIDATE_PROMOTION_POLICY_CONTRACT_VERSION = (
    "candidate-promotion-policy-v1-warmhot-supported-fired-regime-compatible"
)


class CandidatePromotionEngine:
    """Promote current discovery cases into expensive-research candidates.

    Promotion reuses accepted Phase 8 WARM/HOT semantics and requires at least one
    historically supported strategy that is direction/regime compatible and fires on
    current point-in-time features. ML probabilities are mandatory context but are not
    used as a direction or threshold signal.
    """

    def __init__(self, registry: StrategyRegistry = DEFAULT_STRATEGY_REGISTRY) -> None:
        self.registry = registry
        self.router = StrategyRouter(registry)

    @staticmethod
    def support_snapshot(payload: Mapping[str, object]) -> StrategyHistoricalSupportSnapshot:
        return StrategyHistoricalSupportSnapshot(
            strategy_id=str(payload["strategy_id"]),
            status=str(payload["status"]),
            eligible_for_candidate_promotion=bool(payload["eligible_for_candidate_promotion"]),
            primary_cost_bps=float(payload["primary_cost_bps"]),
            development_mean_return=(
                None if payload.get("development_mean_return") is None
                else float(payload["development_mean_return"])
            ),
            first_half_mean_return=(
                None if payload.get("first_half_mean_return") is None
                else float(payload["first_half_mean_return"])
            ),
            second_half_mean_return=(
                None if payload.get("second_half_mean_return") is None
                else float(payload["second_half_mean_return"])
            ),
            development_rows=int(payload["development_rows"]),
        )

    def evaluate(
        self,
        *,
        discovery: DiscoveryStateRecord,
        features: Mapping[str, float],
        market_state: str | None,
        sector_state: str | None,
        ticker_state: str | None,
        ml_probability_evidence: MLProbabilityEvidence,
        historical_support: Mapping[str, StrategyHistoricalSupportSnapshot],
    ) -> CandidatePromotionRecord:
        routing_context = StrategyRoutingContext(
            instrument_id=discovery.instrument_id,
            ticker=discovery.ticker,
            as_of_date=discovery.as_of_date,
            discovery_direction=discovery.direction,
            market_state=market_state,
            sector_state=sector_state,
            ticker_state=ticker_state,
        )
        routes = self.router.route(routing_context)
        assessments = []
        supported_fired: list[str] = []
        data_error = False
        reason_codes: list[str] = [
            f"DISCOVERY_STATE:{discovery.effective_state.value}",
            f"DISCOVERY_DIRECTION:{discovery.direction.value}",
        ]

        strategy_context = StrategyContext(
            instrument_id=discovery.instrument_id,
            ticker=discovery.ticker,
            as_of_date=discovery.as_of_date,
            features=features,
            ml_probability_evidence=ml_probability_evidence,
        )
        route_by_id = {route.strategy_id: route for route in routes}
        for strategy in self.registry.all():
            strategy_id = strategy.metadata.strategy_id
            route = route_by_id[strategy_id]
            if not route.eligible:
                continue
            support = historical_support.get(strategy_id)
            if support is None:
                reason_codes.append(f"NO_HISTORICAL_SUPPORT_RECORD:{strategy_id}")
                continue
            if not support.eligible_for_candidate_promotion:
                reason_codes.append(f"HISTORICALLY_UNSUPPORTED:{strategy_id}")
                continue
            try:
                assessment = strategy.evaluate(strategy_context)
            except KeyError:
                data_error = True
                reason_codes.append(f"STRATEGY_FEATURE_DATA_MISSING:{strategy_id}")
                continue
            assessments.append(assessment)
            if assessment.fired:
                supported_fired.append(strategy_id)

        discovery_ready = (
            discovery.effective_state in {DiscoveryState.WARM, DiscoveryState.HOT}
            and discovery.direction != DiscoveryDirection.NEUTRAL
        )
        promoted = discovery_ready and bool(supported_fired) and not data_error
        if not discovery_ready:
            reason_codes.append("REJECT:DISCOVERY_NOT_WARM_HOT_DIRECTIONAL")
        if not supported_fired:
            reason_codes.append("REJECT:NO_SUPPORTED_ROUTED_STRATEGY_FIRED")
        if data_error:
            reason_codes.append("REJECT:INCOMPLETE_SUPPORTED_STRATEGY_FEATURE_EVIDENCE")
        if promoted:
            reason_codes.append("PROMOTE:SUPPORTED_ROUTED_STRATEGY_FIRED")

        registered_ids = {strategy.metadata.strategy_id for strategy in self.registry.all()}
        support_values = tuple(
            historical_support[key]
            for key in sorted(historical_support)
            if key in registered_ids
        )
        return CandidatePromotionRecord(
            instrument_id=discovery.instrument_id,
            ticker=discovery.ticker,
            as_of_date=discovery.as_of_date,
            discovery_effective_state=discovery.effective_state,
            discovery_direction=discovery.direction,
            discovery_priority_score=discovery.priority_score,
            market_state=market_state,
            sector_state=sector_state,
            ticker_state=ticker_state,
            ml_probability_evidence=ml_probability_evidence,
            historical_support=support_values,
            route_decisions=routes,
            strategy_assessments=tuple(assessments),
            supported_fired_strategy_ids=tuple(sorted(supported_fired)),
            promoted=promoted,
            reason_codes=tuple(reason_codes),
        )


def support_mapping_from_study(report: Mapping[str, object]) -> dict[str, StrategyHistoricalSupportSnapshot]:
    studies = report.get("studies")
    if not isinstance(studies, list):
        raise ValueError("historical strategy study has no studies list")
    engine = CandidatePromotionEngine()
    result: dict[str, StrategyHistoricalSupportSnapshot] = {}
    for item in studies:
        if not isinstance(item, dict) or not isinstance(item.get("support"), dict):
            raise ValueError("historical strategy study contains malformed support evidence")
        snapshot = engine.support_snapshot(item["support"])
        if snapshot.strategy_id in result:
            raise ValueError("historical strategy study contains duplicate strategy support")
        result[snapshot.strategy_id] = snapshot
    return result
