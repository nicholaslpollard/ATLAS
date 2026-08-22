from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.universe import UniverseRoute


DISCOVERY_CANDIDATE_CONTRACT_VERSION = "discovery-candidate-v1-health-activity-routing"


class DiscoveryActivityTier(StrEnum):
    BELOW_FLOOR = "below_floor"
    LIGHT = "light"
    ACTIVE = "active"
    LIQUID = "liquid"
    DEEP = "deep"


class DiscoveryReasonCode(StrEnum):
    BROAD_READY = "broad_ready"
    MISSING_DAILY_BAR = "missing_daily_bar"
    MISSING_DAILY_FEATURE = "missing_daily_feature"
    BAR_FEATURE_KEY_MISMATCH = "bar_feature_key_mismatch"
    INVALID_CLOSE = "invalid_close"
    INVALID_VOLUME = "invalid_volume"
    INVALID_DOLLAR_VOLUME = "invalid_dollar_volume"
    BELOW_MINIMUM_DOLLAR_VOLUME = "below_minimum_dollar_volume"
    MISSING_REGULAR_INTRADAY = "missing_regular_intrADAY"
    MANDATORY_ROUTE_BYPASS = "mandatory_route_bypass"


class DiscoveryCandidate(BaseModel):
    """Phase 8 foundation record before setup scoring or instrument selection."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = DISCOVERY_CANDIDATE_CONTRACT_VERSION
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    security_type: str | None = None
    routes: tuple[UniverseRoute, ...]
    discovery_eligible: bool

    daily_bar_timestamp_utc: datetime | None = None
    daily_feature_timestamp_utc: datetime | None = None
    close: float | None = None
    volume: float | None = None
    dollar_volume: float | None = None
    relative_volume_20: float | None = None
    relative_dollar_volume_20: float | None = None
    natr_14: float | None = None
    realized_volatility_20: float | None = None

    has_regular_1h: bool
    has_regular_4h: bool
    intraday_ready: bool
    data_health_pass: bool
    activity_pass: bool
    broad_discovery_ready: bool
    mandatory_route: bool
    consideration_required: bool
    activity_tier: DiscoveryActivityTier
    reason_codes: tuple[DiscoveryReasonCode, ...]

    @field_validator("instrument_id", "ticker")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("required discovery text cannot be blank")
        return cleaned

    @field_validator("routes")
    @classmethod
    def unique_routes(cls, value: tuple[UniverseRoute, ...]) -> tuple[UniverseRoute, ...]:
        if not value:
            raise ValueError("discovery candidate requires at least one route")
        if len(value) != len(set(value)):
            raise ValueError("discovery routes must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("reason_codes")
    @classmethod
    def unique_reasons(
        cls,
        value: tuple[DiscoveryReasonCode, ...],
    ) -> tuple[DiscoveryReasonCode, ...]:
        if not value:
            raise ValueError("discovery candidate requires at least one reason code")
        if len(value) != len(set(value)):
            raise ValueError("discovery reason codes must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @model_validator(mode="after")
    def validate_routing_semantics(self) -> "DiscoveryCandidate":
        mandatory = any(
            route in {UniverseRoute.POSITION, UniverseRoute.WATCHLIST, UniverseRoute.CUSTOM}
            for route in self.routes
        )
        if self.mandatory_route != mandatory:
            raise ValueError("mandatory_route does not match universe routes")
        expected_broad = self.discovery_eligible and self.data_health_pass and self.activity_pass
        if self.broad_discovery_ready != expected_broad:
            raise ValueError("broad_discovery_ready does not match eligibility/health/activity")
        if self.consideration_required != (self.broad_discovery_ready or self.mandatory_route):
            raise ValueError("consideration_required does not match broad/mandatory routing")
        if self.intraday_ready != (self.has_regular_1h or self.has_regular_4h):
            raise ValueError("intraday_ready does not match regular intraday coverage")
        if self.broad_discovery_ready and DiscoveryReasonCode.BROAD_READY not in self.reason_codes:
            raise ValueError("broad-ready candidate must carry BROAD_READY")
        return self
