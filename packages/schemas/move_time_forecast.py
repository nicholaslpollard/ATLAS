from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast_contract import (
    MOVE_TIME_FORECAST_CONTRACT,
    MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
)


MOVE_TIME_FORECAST_CONTRACT_VERSION = str(MOVE_TIME_FORECAST_CONTRACT["contract_id"])


class ForecastAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class ForecastHorizonUnit(StrEnum):
    MINUTES = "MINUTES"
    SESSIONS = "SESSIONS"


class MoveThresholdProbability(BaseModel):
    """Underlying-path threshold evidence relative to the forecast direction."""

    model_config = ConfigDict(frozen=True)

    threshold_fraction: float = Field(gt=0.0)
    favorable_touch_probability: float = Field(ge=0.0, le=1.0)
    adverse_touch_probability: float = Field(ge=0.0, le=1.0)
    favorable_before_adverse_probability: float = Field(ge=0.0, le=1.0)
    adverse_before_favorable_probability: float = Field(ge=0.0, le=1.0)
    same_interval_collision_probability: float = Field(ge=0.0, le=1.0)
    median_favorable_time: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def validate_path_probabilities(self) -> "MoveThresholdProbability":
        if self.favorable_before_adverse_probability > self.favorable_touch_probability:
            raise ValueError("favorable-first probability cannot exceed favorable-touch probability")
        if self.adverse_before_favorable_probability > self.adverse_touch_probability:
            raise ValueError("adverse-first probability cannot exceed adverse-touch probability")
        if self.same_interval_collision_probability > min(
            self.favorable_touch_probability,
            self.adverse_touch_probability,
        ):
            raise ValueError("same-interval collision cannot exceed either touch probability")
        ordered_mass = (
            self.favorable_before_adverse_probability
            + self.adverse_before_favorable_probability
            + self.same_interval_collision_probability
        )
        if ordered_mass > 1.0 + 1e-12:
            raise ValueError("path-order probability mass cannot exceed one")
        if self.favorable_touch_probability > 0.0 and self.median_favorable_time is None:
            raise ValueError("positive favorable-touch probability requires median favorable time")
        if self.favorable_touch_probability == 0.0 and self.median_favorable_time is not None:
            raise ValueError("zero favorable-touch probability cannot carry favorable timing")
        return self


class UnderlyingMoveTimeForecast(BaseModel):
    """Versioned underlying distribution evidence produced before instrument selection.

    This object is deliberately broker-neutral. It describes the underlying
    price-path distribution and cannot itself select an instrument, create an
    order, promote a strategy, or claim historical option P&L.
    """

    model_config = ConfigDict(frozen=True)

    contract_version: str = MOVE_TIME_FORECAST_CONTRACT_VERSION
    contract_fingerprint: str = MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
    availability: ForecastAvailability
    instrument_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1, max_length=64)
    direction: DiscoveryDirection
    forecast_created_utc: datetime
    evidence_cutoff_utc: datetime
    horizon_unit: ForecastHorizonUnit
    horizon_value: int = Field(ge=1)
    method_id: str = Field(min_length=1)
    source_label: str = Field(min_length=1)
    source_fingerprint: str = Field(min_length=64, max_length=64)
    sample_size: int | None = Field(default=None, ge=1)

    reference_price: float | None = Field(default=None, gt=0.0)
    mean_signed_return: float | None = None
    median_signed_return: float | None = None
    p10_signed_return: float | None = None
    p25_signed_return: float | None = None
    p75_signed_return: float | None = None
    p90_signed_return: float | None = None
    probability_positive_return: float | None = Field(default=None, ge=0.0, le=1.0)
    mean_mfe: float | None = Field(default=None, ge=0.0)
    mean_mae: float | None = Field(default=None, ge=0.0)
    thresholds: tuple[MoveThresholdProbability, ...] = ()
    uncertainty_score: float | None = Field(default=None, ge=0.0, le=1.0)

    underlying_only: bool = True
    historical_option_pnl_claimed: bool = False
    instrument_selection_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    reason_codes: tuple[str, ...]

    @field_validator("instrument_id", "ticker", "method_id", "source_label")
    @classmethod
    def clean_required_text(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("required forecast text cannot be blank")
        return cleaned

    @field_validator("forecast_created_utc", "evidence_cutoff_utc")
    @classmethod
    def require_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("forecast timestamps must be timezone-aware")
        return value

    @field_validator("thresholds")
    @classmethod
    def sort_unique_thresholds(
        cls,
        value: tuple[MoveThresholdProbability, ...],
    ) -> tuple[MoveThresholdProbability, ...]:
        ordered = tuple(sorted(value, key=lambda item: item.threshold_fraction))
        fractions = [item.threshold_fraction for item in ordered]
        if len(fractions) != len(set(fractions)):
            raise ValueError("forecast thresholds must be unique")
        return ordered

    @model_validator(mode="after")
    def validate_forecast_semantics(self) -> "UnderlyingMoveTimeForecast":
        if self.contract_version != MOVE_TIME_FORECAST_CONTRACT_VERSION:
            raise ValueError("move/time forecast contract version mismatch")
        if self.contract_fingerprint != MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT:
            raise ValueError("move/time forecast contract fingerprint mismatch")
        if self.evidence_cutoff_utc > self.forecast_created_utc:
            raise ValueError("forecast cannot use evidence after its creation time")
        if not self.reason_codes:
            raise ValueError("move/time forecast requires reason codes")
        if not self.underlying_only:
            raise ValueError("move/time forecast must remain underlying-only")
        forbidden_authority = (
            self.historical_option_pnl_claimed,
            self.instrument_selection_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
        )
        if any(forbidden_authority):
            raise ValueError("move/time forecast cannot grant trading or promotion authority")

        distribution = (
            self.reference_price,
            self.mean_signed_return,
            self.median_signed_return,
            self.p10_signed_return,
            self.p25_signed_return,
            self.p75_signed_return,
            self.p90_signed_return,
            self.probability_positive_return,
            self.mean_mfe,
            self.mean_mae,
        )
        if self.availability == ForecastAvailability.UNAVAILABLE:
            if any(value is not None for value in distribution):
                raise ValueError("unavailable forecast cannot carry a partial distribution")
            if self.sample_size is not None or self.uncertainty_score is not None or self.thresholds:
                raise ValueError("unavailable forecast cannot carry path evidence")
            return self

        if any(value is None for value in distribution):
            raise ValueError("available forecast requires the complete signed-return distribution")
        if self.sample_size is None:
            raise ValueError("available forecast requires sample size")
        assert self.p10_signed_return is not None
        assert self.p25_signed_return is not None
        assert self.median_signed_return is not None
        assert self.p75_signed_return is not None
        assert self.p90_signed_return is not None
        if not (
            self.p10_signed_return
            <= self.p25_signed_return
            <= self.median_signed_return
            <= self.p75_signed_return
            <= self.p90_signed_return
        ):
            raise ValueError("signed-return quantiles must be monotonically ordered")

        if self.direction == DiscoveryDirection.NEUTRAL:
            if self.thresholds:
                raise ValueError("neutral forecast cannot define favorable/adverse thresholds")
        elif not self.thresholds:
            raise ValueError("directional available forecast requires path thresholds")

        previous: MoveThresholdProbability | None = None
        for threshold in self.thresholds:
            if threshold.median_favorable_time is not None:
                if threshold.median_favorable_time > float(self.horizon_value):
                    raise ValueError("median favorable time cannot exceed forecast horizon")
            if previous is not None:
                if threshold.favorable_touch_probability > previous.favorable_touch_probability + 1e-12:
                    raise ValueError("favorable-touch probability cannot rise with a larger threshold")
                if threshold.adverse_touch_probability > previous.adverse_touch_probability + 1e-12:
                    raise ValueError("adverse-touch probability cannot rise with a larger threshold")
            previous = threshold
        return self


def forecast_fingerprint(forecast: UnderlyingMoveTimeForecast) -> str:
    raw = json.dumps(
        forecast.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
