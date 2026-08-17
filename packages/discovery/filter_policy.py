from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from packages.schemas.candidate import DiscoveryActivityTier, DiscoveryReasonCode
from packages.schemas.universe import UniverseRoute


DISCOVERY_FILTER_POLICY_VERSION = "discovery-filter-v1-250k-dollar-volume-no-price-floor"


@dataclass(frozen=True, slots=True)
class DiscoveryFilterDecision:
    data_health_pass: bool
    activity_pass: bool
    broad_discovery_ready: bool
    mandatory_route: bool
    consideration_required: bool
    intraday_ready: bool
    activity_tier: DiscoveryActivityTier
    reason_codes: tuple[DiscoveryReasonCode, ...]


@dataclass(frozen=True, slots=True)
class DiscoveryFilterPolicy:
    """Cheap deterministic health/activity policy before setup scoring.

    Dollar volume is the minimum-tradability measure because raw share volume badly
    overstates activity in penny stocks. There is intentionally no minimum share-price
    rule. Relative-volume warmup is not a hard gate so new listings remain discoverable.
    """

    minimum_dollar_volume: float = 250_000.0
    active_dollar_volume: float = 1_000_000.0
    liquid_dollar_volume: float = 10_000_000.0
    deep_dollar_volume: float = 50_000_000.0

    @property
    def fingerprint(self) -> str:
        payload = {
            "version": DISCOVERY_FILTER_POLICY_VERSION,
            "minimum_dollar_volume": self.minimum_dollar_volume,
            "active_dollar_volume": self.active_dollar_volume,
            "liquid_dollar_volume": self.liquid_dollar_volume,
            "deep_dollar_volume": self.deep_dollar_volume,
            "minimum_share_price": None,
            "relative_volume_is_hard_gate": False,
            "intraday_coverage_is_hard_gate": False,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _finite(value: object) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def activity_tier(self, dollar_volume: object) -> DiscoveryActivityTier:
        value = self._finite(dollar_volume)
        if value is None or value < self.minimum_dollar_volume:
            return DiscoveryActivityTier.BELOW_FLOOR
        if value < self.active_dollar_volume:
            return DiscoveryActivityTier.LIGHT
        if value < self.liquid_dollar_volume:
            return DiscoveryActivityTier.ACTIVE
        if value < self.deep_dollar_volume:
            return DiscoveryActivityTier.LIQUID
        return DiscoveryActivityTier.DEEP

    def evaluate(
        self,
        *,
        discovery_eligible: bool,
        routes: Iterable[UniverseRoute],
        bar_present: bool,
        feature_present: bool,
        bar_timestamp_utc: datetime | None,
        feature_timestamp_utc: datetime | None,
        close: object,
        volume: object,
        dollar_volume: object,
        has_regular_1h: bool,
        has_regular_4h: bool,
    ) -> DiscoveryFilterDecision:
        route_set = {UniverseRoute(route) for route in routes}
        mandatory = bool(
            route_set.intersection(
                {UniverseRoute.POSITION, UniverseRoute.WATCHLIST, UniverseRoute.CUSTOM}
            )
        )
        reasons: set[DiscoveryReasonCode] = set()

        if not bar_present:
            reasons.add(DiscoveryReasonCode.MISSING_DAILY_BAR)
        if not feature_present:
            reasons.add(DiscoveryReasonCode.MISSING_DAILY_FEATURE)
        if (
            bar_present
            and feature_present
            and bar_timestamp_utc is not None
            and feature_timestamp_utc is not None
            and bar_timestamp_utc != feature_timestamp_utc
        ):
            reasons.add(DiscoveryReasonCode.BAR_FEATURE_KEY_MISMATCH)

        close_value = self._finite(close)
        volume_value = self._finite(volume)
        dollar_value = self._finite(dollar_volume)
        if bar_present and (close_value is None or close_value <= 0):
            reasons.add(DiscoveryReasonCode.INVALID_CLOSE)
        if bar_present and (volume_value is None or volume_value < 0):
            reasons.add(DiscoveryReasonCode.INVALID_VOLUME)
        if feature_present and (dollar_value is None or dollar_value <= 0):
            reasons.add(DiscoveryReasonCode.INVALID_DOLLAR_VOLUME)

        blocking_health = {
            DiscoveryReasonCode.MISSING_DAILY_BAR,
            DiscoveryReasonCode.MISSING_DAILY_FEATURE,
            DiscoveryReasonCode.BAR_FEATURE_KEY_MISMATCH,
            DiscoveryReasonCode.INVALID_CLOSE,
            DiscoveryReasonCode.INVALID_VOLUME,
            DiscoveryReasonCode.INVALID_DOLLAR_VOLUME,
        }
        data_health_pass = not bool(reasons.intersection(blocking_health))

        activity_pass = bool(
            data_health_pass
            and dollar_value is not None
            and dollar_value >= self.minimum_dollar_volume
        )
        if data_health_pass and not activity_pass:
            reasons.add(DiscoveryReasonCode.BELOW_MINIMUM_DOLLAR_VOLUME)

        intraday_ready = bool(has_regular_1h or has_regular_4h)
        if not intraday_ready:
            reasons.add(DiscoveryReasonCode.MISSING_REGULAR_INTRADAY)

        broad_ready = bool(discovery_eligible and data_health_pass and activity_pass)
        if broad_ready:
            reasons.add(DiscoveryReasonCode.BROAD_READY)
        if mandatory and not broad_ready:
            reasons.add(DiscoveryReasonCode.MANDATORY_ROUTE_BYPASS)

        return DiscoveryFilterDecision(
            data_health_pass=data_health_pass,
            activity_pass=activity_pass,
            broad_discovery_ready=broad_ready,
            mandatory_route=mandatory,
            consideration_required=bool(broad_ready or mandatory),
            intraday_ready=intraday_ready,
            activity_tier=self.activity_tier(dollar_value),
            reason_codes=tuple(sorted(reasons, key=lambda item: item.value)),
        )


ACTIVE_DISCOVERY_FILTER_POLICY = DiscoveryFilterPolicy()
