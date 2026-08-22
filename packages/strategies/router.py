from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.strategy import (
    StrategyDirection,
    StrategyFamily,
    StrategyRegimeFit,
    StrategyRouteDecision,
)

from .metadata import StrategyMetadata
from .registry import DEFAULT_STRATEGY_REGISTRY, StrategyRegistry


STRATEGY_ROUTER_CONTRACT_VERSION = "strategy-router-v1-market-sector-ticker-external-routing"


@dataclass(frozen=True, slots=True)
class StrategyRoutingContext:
    instrument_id: str
    ticker: str
    as_of_date: date
    discovery_direction: DiscoveryDirection
    market_state: str | None
    sector_state: str | None
    ticker_state: str | None


_BULL = {"BULL", "STRONG_BULL"}
_BEAR = {"BEAR", "STRONG_BEAR"}
_MIXED = {"MIXED"}

_LONG_TICKER_PREFERRED = {"UPTREND", "STRONG_UPTREND", "PULLBACK_UP"}
_LONG_TICKER_ALLOWED = {"TRANSITION_UP", "RANGE_MIXED"}
_LONG_TICKER_BLOCKED = {"DOWNTREND", "STRONG_DOWNTREND", "BOUNCE_DOWN", "TRANSITION_DOWN"}
_SHORT_TICKER_PREFERRED = {"DOWNTREND", "STRONG_DOWNTREND", "BOUNCE_DOWN"}
_SHORT_TICKER_ALLOWED = {"TRANSITION_DOWN", "RANGE_MIXED"}
_SHORT_TICKER_BLOCKED = {"UPTREND", "STRONG_UPTREND", "PULLBACK_UP", "TRANSITION_UP"}


def _direction_match(discovery: DiscoveryDirection, direction: StrategyDirection) -> bool:
    if discovery == DiscoveryDirection.NEUTRAL:
        return False
    if discovery == DiscoveryDirection.BULLISH:
        return direction == StrategyDirection.LONG
    return direction == StrategyDirection.SHORT


def _trend_market_fit(state: str | None, direction: StrategyDirection) -> StrategyRegimeFit:
    if state is None:
        return StrategyRegimeFit.UNAVAILABLE
    if direction == StrategyDirection.LONG:
        if state in _BULL:
            return StrategyRegimeFit.PREFERRED
        if state in _MIXED:
            return StrategyRegimeFit.ALLOWED
        return StrategyRegimeFit.BLOCKED
    if state in _BEAR:
        return StrategyRegimeFit.PREFERRED
    if state in _MIXED:
        return StrategyRegimeFit.ALLOWED
    return StrategyRegimeFit.BLOCKED


def _market_fit(metadata: StrategyMetadata, state: str | None) -> StrategyRegimeFit:
    if metadata.family in {
        StrategyFamily.TREND_FOLLOWING,
        StrategyFamily.MOMENTUM,
        StrategyFamily.BREAKOUT,
        StrategyFamily.PULLBACK,
    }:
        return _trend_market_fit(state, metadata.direction)
    raise ValueError(f"unsupported strategy family: {metadata.family}")


def _sector_fit(metadata: StrategyMetadata, state: str | None) -> StrategyRegimeFit:
    # Phase 9 deliberately leaves sector unavailable when authoritative classification
    # is absent; missing sector context is therefore not silently converted to MIXED.
    if state is None:
        return StrategyRegimeFit.UNAVAILABLE
    return _market_fit(metadata, state)


def _ticker_fit(metadata: StrategyMetadata, state: str | None) -> StrategyRegimeFit:
    # Pre-2021 history has no fabricated intraday ticker regime. UNAVAILABLE remains
    # distinct and does not itself block a daily strategy evaluation.
    if state is None:
        return StrategyRegimeFit.UNAVAILABLE
    if metadata.direction == StrategyDirection.LONG:
        if state in _LONG_TICKER_PREFERRED:
            return StrategyRegimeFit.PREFERRED
        if state in _LONG_TICKER_ALLOWED:
            return StrategyRegimeFit.ALLOWED
        if state in _LONG_TICKER_BLOCKED:
            return StrategyRegimeFit.BLOCKED
    else:
        if state in _SHORT_TICKER_PREFERRED:
            return StrategyRegimeFit.PREFERRED
        if state in _SHORT_TICKER_ALLOWED:
            return StrategyRegimeFit.ALLOWED
        if state in _SHORT_TICKER_BLOCKED:
            return StrategyRegimeFit.BLOCKED
    return StrategyRegimeFit.ALLOWED


class StrategyRouter:
    """Deterministic, strategy-external market/sector/ticker regime router."""

    def __init__(self, registry: StrategyRegistry = DEFAULT_STRATEGY_REGISTRY) -> None:
        self.registry = registry

    def route_one(
        self,
        metadata: StrategyMetadata,
        context: StrategyRoutingContext,
    ) -> StrategyRouteDecision:
        direction_match = _direction_match(context.discovery_direction, metadata.direction)
        market_fit = _market_fit(metadata, context.market_state)
        sector_fit = _sector_fit(metadata, context.sector_state)
        ticker_fit = _ticker_fit(metadata, context.ticker_state)
        blocked = StrategyRegimeFit.BLOCKED in {market_fit, sector_fit, ticker_fit}
        eligible = direction_match and not blocked

        reasons: list[str] = [
            f"DISCOVERY_DIRECTION:{context.discovery_direction.value}",
            f"DIRECTION_MATCH:{str(direction_match).lower()}",
            f"MARKET_FIT:{market_fit.value}",
            f"SECTOR_FIT:{sector_fit.value}",
            f"TICKER_FIT:{ticker_fit.value}",
        ]
        if not direction_match:
            reasons.append("ROUTE_BLOCKED:DIRECTION_MISMATCH")
        if blocked:
            reasons.append("ROUTE_BLOCKED:REGIME_CONTRADICTION")
        if eligible:
            reasons.append("ROUTE_ELIGIBLE")

        return StrategyRouteDecision(
            strategy_id=metadata.strategy_id,
            family=metadata.family,
            direction=metadata.direction,
            instrument_id=context.instrument_id,
            ticker=context.ticker,
            as_of_date=context.as_of_date,
            eligible=eligible,
            direction_match=direction_match,
            market_fit=market_fit,
            sector_fit=sector_fit,
            ticker_fit=ticker_fit,
            market_state=context.market_state,
            sector_state=context.sector_state,
            ticker_state=context.ticker_state,
            reason_codes=tuple(reasons),
        )

    def route(self, context: StrategyRoutingContext) -> tuple[StrategyRouteDecision, ...]:
        return tuple(self.route_one(metadata, context) for metadata in self.registry.metadata())

    def eligible(self, context: StrategyRoutingContext) -> tuple[StrategyRouteDecision, ...]:
        return tuple(decision for decision in self.route(context) if decision.eligible)
