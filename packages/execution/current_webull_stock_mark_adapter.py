from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel

from packages.execution.current_webull_quote_bundle import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
    CurrentWebullStockQuoteBundleV1,
)
from packages.execution.current_webull_stock_mark_adapter_contract import (
    CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT,
    CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT,
)
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.trade_expression import InstrumentKind
from packages.simulation.market_mark_evidence import (
    MarketMarkInputs,
    MarketMarkTransport,
    SimulatedMarketMarkEvidence,
    build_simulated_market_mark_evidence,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1


CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_VERSION = str(
    CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT["contract_id"]
)


class CurrentWebullStockMarkAdapterError(RuntimeError):
    pass


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="json"))
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _fingerprint_payload(value: Any) -> str:
    raw = json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentWebullStockMarkAdapterError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


@dataclass(frozen=True)
class CurrentWebullStockMarkBatchV1:
    contract_version: str
    contract_fingerprint: str
    source_bundle_fingerprint: str
    valuation_utc: datetime
    marks: tuple[SimulatedMarketMarkEvidence, ...]

    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_VERSION
        ):
            raise CurrentWebullStockMarkAdapterError(
                "current Webull stock-mark contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullStockMarkAdapterError(
                "current Webull stock-mark contract fingerprint mismatch"
            )
        if (
            len(self.source_bundle_fingerprint) != 64
            or any(
                ch not in "0123456789abcdef"
                for ch in self.source_bundle_fingerprint
            )
        ):
            raise CurrentWebullStockMarkAdapterError(
                "source bundle fingerprint must be SHA-256"
            )
        _require_aware(self.valuation_utc, label="valuation timestamp")
        ordered = tuple(
            sorted(
                self.marks,
                key=lambda mark: mark.decision_record_fingerprint,
            )
        )
        if ordered != self.marks:
            raise CurrentWebullStockMarkAdapterError(
                "Webull stock marks must be deterministically ordered"
            )
        if len(
            {
                mark.decision_record_fingerprint
                for mark in self.marks
            }
        ) != len(self.marks):
            raise CurrentWebullStockMarkAdapterError(
                "Webull stock marks cannot duplicate decision lineage"
            )
        forbidden = (
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden):
            raise CurrentWebullStockMarkAdapterError(
                "Webull stock-mark batch cannot grant external or trading authority"
            )

    @property
    def batch_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def build_current_webull_stock_marks_v1(
    *,
    bundle: CurrentWebullStockQuoteBundleV1,
    positions: Sequence[SimulatedOpenPositionV1],
    valuation_utc: datetime,
) -> CurrentWebullStockMarkBatchV1:
    if (
        bundle.contract_fingerprint
        != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockMarkAdapterError(
            "current Webull quote bundle contract fingerprint mismatch"
        )
    valuation = _require_aware(
        valuation_utc,
        label="valuation timestamp",
    )
    if bundle.captured_at_utc > valuation:
        raise CurrentWebullStockMarkAdapterError(
            "Webull quote bundle cannot be captured after valuation"
        )

    quotes = {quote.symbol: quote for quote in bundle.quotes}
    normalized_positions = tuple(
        sorted(
            positions,
            key=lambda position: position.decision_record_fingerprint,
        )
    )
    expected_symbols = {position.ticker for position in normalized_positions}
    if not expected_symbols.issubset(quotes):
        missing = sorted(expected_symbols - set(quotes))
        raise CurrentWebullStockMarkAdapterError(
            "Webull quote bundle is missing exact-case position symbols: "
            + ", ".join(missing)
        )

    marks: list[SimulatedMarketMarkEvidence] = []
    for position in normalized_positions:
        if position.instrument_kind != InstrumentKind.STOCK:
            raise CurrentWebullStockMarkAdapterError(
                "v1 Webull mark adapter supports stock positions only"
            )
        quote = quotes[position.ticker]
        if quote.provider_timestamp_utc < position.opened_utc:
            raise CurrentWebullStockMarkAdapterError(
                f"Webull quote predates open position for {position.ticker}"
            )
        provider_age = (
            valuation - quote.provider_timestamp_utc
        ).total_seconds()
        receive_age = (
            valuation - quote.received_at_utc
        ).total_seconds()
        if provider_age < -5.0 or receive_age < -5.0:
            raise CurrentWebullStockMarkAdapterError(
                f"Webull quote is ahead of valuation for {position.ticker}"
            )
        if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockMarkAdapterError(
                f"Webull quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap for {position.ticker}"
            )
        if receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockMarkAdapterError(
                f"Webull quote receipt is stale for {position.ticker}"
            )

        mark = build_simulated_market_mark_evidence(
            position=position,
            inputs=MarketMarkInputs(
                source_id=(
                    "current-webull-stock-quote-bundle#"
                    + position.ticker
                ),
                source_fingerprint=bundle.bundle_fingerprint,
                provider="webull",
                feed="sandbox_l1",
                transport=MarketMarkTransport.SNAPSHOT,
                feed_quality="REALTIME_ZERO_DELAY_EXECUTION_L1",
                market_timestamp_utc=quote.provider_timestamp_utc,
                received_utc=quote.received_at_utc,
                valuation_utc=valuation,
                bid_price_per_unit=quote.bid_price,
                ask_price_per_unit=quote.ask_price,
                last_price_per_unit=None,
            ),
        )
        if not mark.valuation_eligible:
            raise CurrentWebullStockMarkAdapterError(
                f"Webull quote failed market-mark freshness for {position.ticker}"
            )
        marks.append(mark)

    return CurrentWebullStockMarkBatchV1(
        contract_version=(
            CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
        ),
        source_bundle_fingerprint=bundle.bundle_fingerprint,
        valuation_utc=valuation,
        marks=tuple(marks),
    )


__all__ = [
    "CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT",
    "CurrentWebullStockMarkAdapterError",
    "CurrentWebullStockMarkBatchV1",
    "build_current_webull_stock_marks_v1",
]
