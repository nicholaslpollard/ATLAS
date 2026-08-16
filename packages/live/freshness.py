from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from packages.core.enums import LiveFreshness
from packages.core.timestamps import to_utc


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Classify live observations after accounting for intentional feed delay."""

    fresh_seconds: int = 90
    aging_seconds: int = 300

    def __post_init__(self) -> None:
        if self.fresh_seconds < 0:
            raise ValueError("fresh_seconds cannot be negative")
        if self.aging_seconds < self.fresh_seconds:
            raise ValueError("aging_seconds must be >= fresh_seconds")

    def classify(
        self,
        event_time_utc: datetime | None,
        now_utc: datetime,
        *,
        expected_delay_seconds: int = 0,
    ) -> LiveFreshness:
        if event_time_utc is None:
            return LiveFreshness.UNKNOWN
        if expected_delay_seconds < 0:
            raise ValueError("expected_delay_seconds cannot be negative")

        event_time = to_utc(event_time_utc)
        now = to_utc(now_utc)
        expected_arrival = event_time + timedelta(seconds=expected_delay_seconds)
        excess_age = max(0.0, (now - expected_arrival).total_seconds())
        if excess_age <= self.fresh_seconds:
            return LiveFreshness.FRESH
        if excess_age <= self.aging_seconds:
            return LiveFreshness.AGING
        return LiveFreshness.STALE
