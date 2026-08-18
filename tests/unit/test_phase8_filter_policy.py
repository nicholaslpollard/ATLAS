from __future__ import annotations

from datetime import UTC, datetime

from packages.discovery.filter_policy import ACTIVE_DISCOVERY_FILTER_POLICY
from packages.schemas.candidate import DiscoveryActivityTier, DiscoveryReasonCode
from packages.schemas.universe import UniverseRoute


def test_phase8_policy_has_no_price_floor_and_uses_dollar_volume() -> None:
    policy = ACTIVE_DISCOVERY_FILTER_POLICY
    ts = datetime(2026, 8, 14, 20, 0, tzinfo=UTC)

    low_price = policy.evaluate(
        discovery_eligible=True,
        routes=(UniverseRoute.DISCOVERY,),
        bar_present=True,
        feature_present=True,
        bar_timestamp_utc=ts,
        feature_timestamp_utc=ts,
        close=0.20,
        volume=2_000_000,
        dollar_volume=400_000,
        has_regular_1h=True,
        has_regular_4h=True,
    )
    assert low_price.data_health_pass is True
    assert low_price.activity_pass is True
    assert low_price.broad_discovery_ready is True
    assert low_price.activity_tier == DiscoveryActivityTier.LIGHT
    assert DiscoveryReasonCode.BROAD_READY in low_price.reason_codes


def test_phase8_policy_filters_thin_names_without_erasing_mandatory_routes() -> None:
    policy = ACTIVE_DISCOVERY_FILTER_POLICY
    ts = datetime(2026, 8, 14, 20, 0, tzinfo=UTC)

    thin = policy.evaluate(
        discovery_eligible=True,
        routes=(UniverseRoute.DISCOVERY,),
        bar_present=True,
        feature_present=True,
        bar_timestamp_utc=ts,
        feature_timestamp_utc=ts,
        close=10.0,
        volume=20_000,
        dollar_volume=200_000,
        has_regular_1h=False,
        has_regular_4h=False,
    )
    assert thin.data_health_pass is True
    assert thin.activity_pass is False
    assert thin.broad_discovery_ready is False
    assert thin.consideration_required is False
    assert DiscoveryReasonCode.BELOW_MINIMUM_DOLLAR_VOLUME in thin.reason_codes
    assert DiscoveryReasonCode.MISSING_REGULAR_INTRADAY in thin.reason_codes

    mandatory = policy.evaluate(
        discovery_eligible=False,
        routes=(UniverseRoute.POSITION,),
        bar_present=False,
        feature_present=False,
        bar_timestamp_utc=None,
        feature_timestamp_utc=None,
        close=None,
        volume=None,
        dollar_volume=None,
        has_regular_1h=False,
        has_regular_4h=False,
    )
    assert mandatory.data_health_pass is False
    assert mandatory.broad_discovery_ready is False
    assert mandatory.mandatory_route is True
    assert mandatory.consideration_required is True
    assert DiscoveryReasonCode.MANDATORY_ROUTE_BYPASS in mandatory.reason_codes


def test_phase8_policy_activity_tiers_are_measured_bands() -> None:
    policy = ACTIVE_DISCOVERY_FILTER_POLICY
    assert policy.activity_tier(249_999) == DiscoveryActivityTier.BELOW_FLOOR
    assert policy.activity_tier(250_000) == DiscoveryActivityTier.LIGHT
    assert policy.activity_tier(1_000_000) == DiscoveryActivityTier.ACTIVE
    assert policy.activity_tier(10_000_000) == DiscoveryActivityTier.LIQUID
    assert policy.activity_tier(50_000_000) == DiscoveryActivityTier.DEEP
