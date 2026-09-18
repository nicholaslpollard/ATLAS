from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import LiveFeedMode, SessionSegment
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.core.timestamps import to_utc
from packages.execution.current_webull_quote_bundle_contract import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT,
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
)
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS


CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_VERSION = str(
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT["contract_id"]
)
CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_FILENAME = "webull_stock_l1.json"
_MAX_BUNDLE_BYTES = 8 * 1024 * 1024


class CurrentWebullStockQuoteBundleError(RuntimeError):
    pass


class CurrentWebullStockQuoteV1(BaseModel):
    model_config = ConfigDict(frozen=True)

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
    broker_reads: int = Field(default=0, ge=0)
    broker_writes: int = Field(default=0, ge=0)

    @field_validator("symbol")
    @classmethod
    def preserve_symbol_case(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Webull quote symbol cannot be blank")
        return cleaned

    @field_validator("provider_timestamp_utc", "received_at_utc")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return to_utc(value)

    @model_validator(mode="after")
    def validate_quote(self) -> "CurrentWebullStockQuoteV1":
        if self.source != "webull_openapi_l1":
            raise ValueError("current Webull quote source mismatch")
        if self.environment != "sandbox":
            raise ValueError("current Webull quote must come from sandbox")
        if self.provider_timestamp_utc > self.received_at_utc:
            raise ValueError("Webull provider timestamp cannot follow receipt")
        if self.ask_price < self.bid_price:
            raise ValueError("Webull quote ask cannot be below bid")
        if (
            self.feed_mode != LiveFeedMode.REALTIME
            or self.expected_delay_seconds != 0
        ):
            raise ValueError(
                "current Webull quote must be zero-delay realtime"
            )
        if self.provider_read_calls != 1:
            raise ValueError(
                "each current Webull quote must represent exactly one provider read"
            )
        if any(
            (
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
            )
        ):
            raise ValueError(
                "current Webull quote cannot contain provider/broker mutation or account reads"
            )
        return self


def _bundle_fingerprint_payload(
    *,
    requested_symbols: tuple[str, ...],
    quotes: tuple[CurrentWebullStockQuoteV1, ...],
    captured_at_utc: datetime,
    provider_read_calls: int,
) -> dict[str, object]:
    return {
        "contract_version": (
            CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
        ),
        "requested_symbols": list(requested_symbols),
        "quotes": [
            quote.model_dump(mode="json")
            for quote in quotes
        ],
        "captured_at_utc": captured_at_utc.isoformat(),
        "provider_read_calls": provider_read_calls,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


def _fingerprint_payload(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class CurrentWebullStockQuoteBundleV1(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = (
        CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_VERSION
    )
    contract_fingerprint: str = (
        CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    )
    bundle_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    requested_symbols: tuple[str, ...]
    quotes: tuple[CurrentWebullStockQuoteV1, ...]
    captured_at_utc: datetime
    provider_read_calls: int = Field(ge=0)

    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    @field_validator("captured_at_utc")
    @classmethod
    def normalize_capture_time(cls, value: datetime) -> datetime:
        return to_utc(value)

    @field_validator("requested_symbols")
    @classmethod
    def validate_requested_symbols(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        cleaned = tuple(symbol.strip() for symbol in value)
        if not cleaned or any(not symbol for symbol in cleaned):
            raise ValueError("requested Webull symbols cannot be blank")
        if cleaned != tuple(sorted(cleaned)):
            raise ValueError(
                "requested Webull symbols must be deterministically sorted"
            )
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("requested Webull symbols must be unique")
        return cleaned

    @model_validator(mode="after")
    def validate_bundle(self) -> "CurrentWebullStockQuoteBundleV1":
        if (
            self.contract_version
            != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_VERSION
        ):
            raise ValueError("current Webull bundle contract version mismatch")
        if (
            self.contract_fingerprint
            != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
        ):
            raise ValueError(
                "current Webull bundle contract fingerprint mismatch"
            )
        quote_symbols = tuple(quote.symbol for quote in self.quotes)
        if quote_symbols != self.requested_symbols:
            raise ValueError(
                "current Webull bundle must completely cover requested symbols in exact sorted order"
            )
        if self.provider_read_calls != len(self.requested_symbols):
            raise ValueError(
                "current Webull bundle provider-read count must equal requested symbol count"
            )
        if any(
            quote.received_at_utc > self.captured_at_utc
            for quote in self.quotes
        ):
            raise ValueError(
                "current Webull bundle capture time cannot precede quote receipt"
            )
        if any(
            (
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
            )
        ):
            raise ValueError(
                "current Webull bundle cannot contain provider/broker mutation or account reads"
            )
        if any(
            (
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise ValueError(
                "current Webull bundle cannot grant order or trading authority"
            )
        expected = _fingerprint_payload(
            _bundle_fingerprint_payload(
                requested_symbols=self.requested_symbols,
                quotes=self.quotes,
                captured_at_utc=self.captured_at_utc,
                provider_read_calls=self.provider_read_calls,
            )
        )
        if self.bundle_fingerprint != expected:
            raise ValueError(
                "current Webull bundle self-fingerprint mismatch"
            )
        return self


def current_webull_stock_quote_bundle_path(
    settings: AtlasSettings,
) -> Path:
    root = settings.resolved_path(settings.data.paths.live)
    return (
        root
        / "simulation"
        / "current_quotes"
        / CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_FILENAME
    )


def build_current_webull_stock_quote_bundle_v1(
    *,
    requested_symbols: Sequence[str],
    quotes: Sequence[CurrentWebullStockQuoteV1],
    captured_at_utc: datetime | None = None,
) -> CurrentWebullStockQuoteBundleV1:
    requested = tuple(sorted(symbol.strip() for symbol in requested_symbols))
    if not requested or any(not symbol for symbol in requested):
        raise CurrentWebullStockQuoteBundleError(
            "requested Webull symbols cannot be blank"
        )
    if len(requested) != len(set(requested)):
        raise CurrentWebullStockQuoteBundleError(
            "requested Webull symbols cannot duplicate"
        )
    ordered_quotes = tuple(sorted(quotes, key=lambda quote: quote.symbol))
    captured = to_utc(captured_at_utc or datetime.now(UTC))
    fingerprint = _fingerprint_payload(
        _bundle_fingerprint_payload(
            requested_symbols=requested,
            quotes=ordered_quotes,
            captured_at_utc=captured,
            provider_read_calls=len(requested),
        )
    )
    try:
        return CurrentWebullStockQuoteBundleV1(
            bundle_fingerprint=fingerprint,
            requested_symbols=requested,
            quotes=ordered_quotes,
            captured_at_utc=captured,
            provider_read_calls=len(requested),
        )
    except ValueError as exc:
        raise CurrentWebullStockQuoteBundleError(
            "current Webull bundle failed validation"
        ) from exc


def write_current_webull_stock_quote_bundle_v1(
    settings: AtlasSettings,
    bundle: CurrentWebullStockQuoteBundleV1,
) -> Path:
    path = current_webull_stock_quote_bundle_path(settings)
    atomic_write_text(
        path,
        bundle.model_dump_json(indent=2) + "\n",
        fsync=True,
    )
    verified = read_current_webull_stock_quote_bundle_v1(
        settings,
        path=path,
        now_utc=bundle.captured_at_utc,
        enforce_freshness=False,
    )
    if verified != bundle:
        raise CurrentWebullStockQuoteBundleError(
            "current Webull bundle readback verification mismatch"
        )
    return path


def read_current_webull_stock_quote_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
    now_utc: datetime | None = None,
    enforce_freshness: bool = True,
) -> CurrentWebullStockQuoteBundleV1:
    target = (
        Path(path)
        if path is not None
        else current_webull_stock_quote_bundle_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise CurrentWebullStockQuoteBundleError(
            "current Webull quote bundle is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise CurrentWebullStockQuoteBundleError(
            "current Webull quote bundle size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise CurrentWebullStockQuoteBundleError(
            "current Webull quote bundle could not be read"
        ) from exc
    if len(raw) != size:
        raise CurrentWebullStockQuoteBundleError(
            "current Webull quote bundle changed while reading"
        )
    try:
        bundle = CurrentWebullStockQuoteBundleV1.model_validate_json(raw)
    except ValueError as exc:
        raise CurrentWebullStockQuoteBundleError(
            "current Webull quote bundle is invalid"
        ) from exc

    if not enforce_freshness:
        return bundle

    now = to_utc(now_utc or datetime.now(UTC))
    calendar = get_market_calendar(settings.data.calendar.exchange)
    for quote in bundle.quotes:
        provider_age = (
            now - quote.provider_timestamp_utc
        ).total_seconds()
        receive_age = (now - quote.received_at_utc).total_seconds()
        if provider_age < -5.0 or receive_age < -5.0:
            raise CurrentWebullStockQuoteBundleError(
                "current Webull quote timestamp is ahead of the local clock"
            )
        if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockQuoteBundleError(
                f"current Webull quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap"
            )
        if receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockQuoteBundleError(
                "current Webull local quote receipt is stale"
            )
        segment = calendar.classify(quote.provider_timestamp_utc)
        if segment != quote.session_segment:
            raise CurrentWebullStockQuoteBundleError(
                "current Webull quote session classification is inconsistent"
            )
        if segment != SessionSegment.REGULAR:
            raise CurrentWebullStockQuoteBundleError(
                "current Webull quote is outside regular session"
            )
    return bundle


def parse_current_webull_stock_quote_v1(
    *,
    settings: AtlasSettings,
    payload: object,
    symbol: str,
    received_at_utc: datetime,
) -> CurrentWebullStockQuoteV1:
    requested = symbol.strip()
    if not requested:
        raise CurrentWebullStockQuoteBundleError(
            "requested Webull symbol cannot be blank"
        )
    rows: list[dict[str, Any]]
    if isinstance(payload, dict):
        rows = [payload]
    elif isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    else:
        raise CurrentWebullStockQuoteBundleError(
            "Webull market-data response has unexpected shape"
        )
    exact = [
        row
        for row in rows
        if str(row.get("symbol") or "") == requested
    ]
    if len(exact) != 1:
        raise CurrentWebullStockQuoteBundleError(
            "Webull market-data response did not contain exactly one exact requested symbol"
        )
    row = exact[0]
    bids = row.get("bids")
    asks = row.get("asks")
    if (
        not isinstance(bids, list)
        or not bids
        or not isinstance(bids[0], dict)
    ):
        raise CurrentWebullStockQuoteBundleError(
            "Webull market-data response did not contain a best bid"
        )
    if (
        not isinstance(asks, list)
        or not asks
        or not isinstance(asks[0], dict)
    ):
        raise CurrentWebullStockQuoteBundleError(
            "Webull market-data response did not contain a best ask"
        )

    try:
        bid = float(bids[0].get("price") or 0.0)
        ask = float(asks[0].get("price") or 0.0)
        bid_size = int(float(bids[0].get("size") or 0))
        ask_size = int(float(asks[0].get("size") or 0))
        quote_time_ms = int(row.get("quote_time") or 0)
    except (TypeError, ValueError) as exc:
        raise CurrentWebullStockQuoteBundleError(
            "Webull market-data response contains invalid quote fields"
        ) from exc
    if bid <= 0.0 or ask <= 0.0 or ask < bid:
        raise CurrentWebullStockQuoteBundleError(
            "Webull market-data response contains invalid bid/ask geometry"
        )
    if quote_time_ms <= 0:
        raise CurrentWebullStockQuoteBundleError(
            "Webull market-data response did not contain quote_time"
        )
    provider_time = datetime.fromtimestamp(
        quote_time_ms / 1000.0,
        tz=UTC,
    )
    received = to_utc(received_at_utc)
    provider_age = (received - provider_time).total_seconds()
    if provider_age < -5.0:
        raise CurrentWebullStockQuoteBundleError(
            "Webull provider timestamp is ahead of local receipt time"
        )
    if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
        raise CurrentWebullStockQuoteBundleError(
            f"Webull quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap"
        )
    calendar = get_market_calendar(settings.data.calendar.exchange)
    segment = calendar.classify(provider_time)
    if segment != SessionSegment.REGULAR:
        raise CurrentWebullStockQuoteBundleError(
            "Webull quote is outside regular session"
        )
    return CurrentWebullStockQuoteV1(
        symbol=requested,
        provider_timestamp_utc=provider_time,
        received_at_utc=received,
        session_date=provider_time.astimezone(
            calendar.market_tz
        ).date(),
        session_segment=segment,
        bid_price=bid,
        bid_size=bid_size,
        ask_price=ask,
        ask_size=ask_size,
    )


__all__ = [
    "CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT",
    "CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_VERSION",
    "CurrentWebullStockQuoteBundleError",
    "CurrentWebullStockQuoteBundleV1",
    "CurrentWebullStockQuoteV1",
    "build_current_webull_stock_quote_bundle_v1",
    "current_webull_stock_quote_bundle_path",
    "parse_current_webull_stock_quote_v1",
    "read_current_webull_stock_quote_bundle_v1",
    "write_current_webull_stock_quote_bundle_v1",
]
