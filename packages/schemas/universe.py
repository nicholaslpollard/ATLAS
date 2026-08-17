from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.core.enums import InstrumentIdentityQuality
from packages.core.timestamps import to_utc


UNIVERSE_CONTRACT_VERSION = "universe-v1-explicit-eligibility-and-overrides"


class UniverseReasonCode(StrEnum):
    """Auditable reasons that affect broad-discovery universe eligibility."""

    ELIGIBLE = "eligible"
    REFERENCE_INACTIVE = "reference_inactive"
    REFERENCE_DELISTED = "reference_delisted"
    NON_US_LOCALE = "non_us_locale"
    UNSUPPORTED_MARKET = "unsupported_market"
    UNSUPPORTED_SECURITY_TYPE = "unsupported_security_type"
    MISSING_REFERENCE_METADATA = "missing_reference_metadata"
    DATA_UNAVAILABLE = "data_unavailable"
    DATA_QUARANTINED = "data_quarantined"
    MANUAL_EXCLUDE = "manual_exclude"
    POSITION_OVERRIDE = "position_override"
    WATCHLIST_OVERRIDE = "watchlist_override"
    CUSTOM_OVERRIDE = "custom_override"


class UniverseRoute(StrEnum):
    """Why ATLAS must consider an instrument in a run."""

    DISCOVERY = "discovery"
    POSITION = "position"
    WATCHLIST = "watchlist"
    CUSTOM = "custom"


class UniverseMember(BaseModel):
    """Point-in-time universe decision for one stable ATLAS instrument identity."""

    model_config = ConfigDict(frozen=True)

    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    as_of_date: date
    identity_quality: InstrumentIdentityQuality

    name: str | None = None
    market: str | None = None
    locale: str | None = None
    primary_exchange: str | None = None
    security_type: str | None = None
    reference_active: bool
    delisted_utc: datetime | None = None

    discovery_eligible: bool
    reason_codes: tuple[UniverseReasonCode, ...]
    routes: tuple[UniverseRoute, ...]

    @field_validator("instrument_id", "ticker")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("required universe text cannot be blank")
        return value

    @field_validator("delisted_utc")
    @classmethod
    def normalize_delisted_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else to_utc(value)

    @field_validator("reason_codes")
    @classmethod
    def unique_reasons(
        cls,
        value: tuple[UniverseReasonCode, ...],
    ) -> tuple[UniverseReasonCode, ...]:
        if not value:
            raise ValueError("universe decision requires at least one reason code")
        if len(value) != len(set(value)):
            raise ValueError("universe reason codes must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("routes")
    @classmethod
    def unique_routes(cls, value: tuple[UniverseRoute, ...]) -> tuple[UniverseRoute, ...]:
        if not value:
            raise ValueError("universe member requires at least one route")
        if len(value) != len(set(value)):
            raise ValueError("universe routes must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @model_validator(mode="after")
    def validate_decision_semantics(self) -> "UniverseMember":
        has_discovery_route = UniverseRoute.DISCOVERY in self.routes
        if self.discovery_eligible != has_discovery_route:
            raise ValueError("discovery route must exactly match discovery_eligible")

        if self.discovery_eligible:
            blocking = {
                UniverseReasonCode.REFERENCE_INACTIVE,
                UniverseReasonCode.REFERENCE_DELISTED,
                UniverseReasonCode.NON_US_LOCALE,
                UniverseReasonCode.UNSUPPORTED_MARKET,
                UniverseReasonCode.UNSUPPORTED_SECURITY_TYPE,
                UniverseReasonCode.MISSING_REFERENCE_METADATA,
                UniverseReasonCode.DATA_UNAVAILABLE,
                UniverseReasonCode.DATA_QUARANTINED,
                UniverseReasonCode.MANUAL_EXCLUDE,
            }
            if any(code in blocking for code in self.reason_codes):
                raise ValueError("eligible discovery member contains a blocking reason")
            if UniverseReasonCode.ELIGIBLE not in self.reason_codes:
                raise ValueError("eligible discovery member must include ELIGIBLE")
        elif UniverseReasonCode.ELIGIBLE in self.reason_codes:
            raise ValueError("ineligible discovery member cannot include ELIGIBLE")

        override_by_route = {
            UniverseRoute.POSITION: UniverseReasonCode.POSITION_OVERRIDE,
            UniverseRoute.WATCHLIST: UniverseReasonCode.WATCHLIST_OVERRIDE,
            UniverseRoute.CUSTOM: UniverseReasonCode.CUSTOM_OVERRIDE,
        }
        for route, reason in override_by_route.items():
            if route in self.routes and not self.discovery_eligible and reason not in self.reason_codes:
                raise ValueError(f"{route.value} bypass requires {reason.value}")
        return self


class UniverseSnapshot(BaseModel):
    """Deterministic point-in-time market universe used by discovery and research."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = UNIVERSE_CONTRACT_VERSION
    as_of_date: date
    reference_snapshot_date: date
    generated_at_utc: datetime
    members: tuple[UniverseMember, ...]
    fingerprint: str

    @field_validator("generated_at_utc")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "UniverseSnapshot":
        identities = [member.instrument_id for member in self.members]
        if len(identities) != len(set(identities)):
            raise ValueError("universe snapshot contains duplicate instrument_id values")
        if any(member.as_of_date != self.as_of_date for member in self.members):
            raise ValueError("universe member as_of_date does not match snapshot")
        return self

    @property
    def instrument_count(self) -> int:
        return len(self.members)

    @property
    def discovery_count(self) -> int:
        return sum(member.discovery_eligible for member in self.members)

    @property
    def position_count(self) -> int:
        return sum(UniverseRoute.POSITION in member.routes for member in self.members)

    @property
    def watchlist_count(self) -> int:
        return sum(UniverseRoute.WATCHLIST in member.routes for member in self.members)


def universe_members_fingerprint(
    *,
    as_of_date: date,
    reference_snapshot_date: date,
    members: tuple[UniverseMember, ...],
) -> str:
    """Fingerprint semantic membership only; generation time is intentionally excluded."""

    ordered = sorted(members, key=lambda item: item.instrument_id)
    payload = {
        "contract_version": UNIVERSE_CONTRACT_VERSION,
        "as_of_date": as_of_date.isoformat(),
        "reference_snapshot_date": reference_snapshot_date.isoformat(),
        "members": [member.model_dump(mode="json") for member in ordered],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
