from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import LiveFeedMode, SessionSegment
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.core.timestamps import to_utc
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.quote_source import ExecutionQuoteError


PHASE18_WEBULL_QUOTE_EVIDENCE_CONTRACT_VERSION = (
    "phase18-webull-quote-evidence-v1-readonly-l1-local-snapshot"
)
PHASE18_WEBULL_QUOTE_FILENAME = "webull_l1_quote.json"


class Phase18WebullQuoteEvidence(BaseModel):
    """Sanitized local evidence from one read-only Webull sandbox L1 request."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = PHASE18_WEBULL_QUOTE_EVIDENCE_CONTRACT_VERSION
    source: str = "webull_openapi_l1"
    environment: str = "sandbox"
    symbol: str = Field(min_length=1, max_length=32)
    provider_timestamp_utc: datetime
    received_at_utc: datetime
    session_date: date
    session_segment: SessionSegment
    bid_price: float = Field(gt=0)
    bid_size: int = Field(default=0, ge=0)
    ask_price: float = Field(gt=0)
    ask_size: int = Field(default=0, ge=0)
    feed_mode: LiveFeedMode = LiveFeedMode.REALTIME
    expected_delay_seconds: int = Field(default=0, ge=0)
    provider_read_calls: int = Field(default=1, ge=0)
    provider_writes: int = Field(default=0, ge=0)
    broker_writes: int = Field(default=0, ge=0)

    @field_validator("symbol")
    @classmethod
    def preserve_symbol_case(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("symbol cannot be blank")
        return value

    @field_validator("provider_timestamp_utc", "received_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> "Phase18WebullQuoteEvidence":
        if self.contract_version != PHASE18_WEBULL_QUOTE_EVIDENCE_CONTRACT_VERSION:
            raise ValueError("unexpected Phase 18 Webull quote evidence contract")
        if self.source != "webull_openapi_l1" or self.environment != "sandbox":
            raise ValueError("Phase 18 Webull quote evidence must come from sandbox OpenAPI L1")
        if self.ask_price < self.bid_price:
            raise ValueError("Webull quote ask cannot be below bid")
        if self.feed_mode != LiveFeedMode.REALTIME or self.expected_delay_seconds != 0:
            raise ValueError("Webull Phase 18 evidence must be marked undelayed realtime")
        if self.provider_writes != 0 or self.broker_writes != 0:
            raise ValueError("quote evidence cannot contain provider/broker writes")
        if self.provider_read_calls != 1:
            raise ValueError("quote evidence must represent exactly one provider read")
        return self


def phase18_webull_quote_path(settings: AtlasSettings) -> Path:
    live_root = settings.resolved_path(settings.data.paths.live)
    return live_root / "phase18" / PHASE18_WEBULL_QUOTE_FILENAME


def write_phase18_webull_quote_evidence(
    settings: AtlasSettings,
    evidence: Phase18WebullQuoteEvidence,
) -> Path:
    path = phase18_webull_quote_path(settings)
    atomic_write_text(path, evidence.model_dump_json(indent=2) + "\n")
    return path


class Phase18WebullQuoteResolver:
    """Read a previously captured Webull L1 quote without making provider calls."""

    def __init__(self, settings: AtlasSettings, *, path: Path | None = None) -> None:
        self.settings = settings
        self.path = Path(path) if path is not None else phase18_webull_quote_path(settings)
        self.read_count = 0

    def quote(
        self,
        ticker: str,
        *,
        now_utc: datetime | None = None,
    ) -> Phase18WebullQuoteEvidence:
        if not self.path.is_file():
            raise ExecutionQuoteError("Webull Phase 18 local quote evidence is unavailable")
        try:
            evidence = Phase18WebullQuoteEvidence.model_validate_json(
                self.path.read_text(encoding="utf-8")
            )
        except ValueError as exc:
            raise ExecutionQuoteError("Webull Phase 18 local quote evidence is invalid") from exc
        self.read_count += 1

        if evidence.symbol != ticker:
            raise ExecutionQuoteError(
                "Webull quote evidence does not contain the exact provider-native ticker"
            )

        now = to_utc(now_utc or datetime.now(UTC))
        provider_age = (now - evidence.provider_timestamp_utc).total_seconds()
        receive_age = (now - evidence.received_at_utc).total_seconds()
        if provider_age < -5.0 or receive_age < -5.0:
            raise ExecutionQuoteError("Webull quote evidence timestamp is ahead of the local clock")
        if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise ExecutionQuoteError(
                f"Webull quote evidence exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap"
            )
        if receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise ExecutionQuoteError("Webull local quote snapshot is stale")

        calendar = get_market_calendar(self.settings.data.calendar.exchange)
        computed_segment = calendar.classify(evidence.provider_timestamp_utc)
        if computed_segment != evidence.session_segment:
            raise ExecutionQuoteError("Webull quote evidence session classification is inconsistent")
        if computed_segment != SessionSegment.REGULAR:
            raise ExecutionQuoteError("execution quote source is outside regular session")

        return evidence
