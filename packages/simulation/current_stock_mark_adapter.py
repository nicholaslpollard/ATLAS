from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel

from packages.core.enums import (
    LiveConnectionState,
    LiveFeedMode,
    LiveFreshness,
)
from packages.execution.trade_expression import InstrumentKind
from packages.simulation.current_live_evidence import (
    CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT,
    CurrentLiveEvidenceV1,
)
from packages.simulation.current_stock_mark_adapter_contract import (
    CURRENT_STOCK_MARK_ADAPTER_CONTRACT,
    CURRENT_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT,
)
from packages.simulation.market_mark_evidence import (
    MarketMarkInputs,
    MarketMarkTransport,
    SimulatedMarketMarkEvidence,
    build_simulated_market_mark_evidence,
)
from packages.simulation.open_position_state import SimulatedOpenPositionV1


CURRENT_STOCK_MARK_ADAPTER_CONTRACT_VERSION = str(
    CURRENT_STOCK_MARK_ADAPTER_CONTRACT["contract_id"]
)


class CurrentStockMarkAdapterError(RuntimeError):
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
        raise CurrentStockMarkAdapterError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


@dataclass(frozen=True)
class CurrentStockMarkBatchV1:
    contract_version: str
    contract_fingerprint: str
    source_evidence_fingerprint: str
    source_id: str
    source_sha256: str
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
        if self.contract_version != CURRENT_STOCK_MARK_ADAPTER_CONTRACT_VERSION:
            raise CurrentStockMarkAdapterError(
                "current stock-mark adapter contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
        ):
            raise CurrentStockMarkAdapterError(
                "current stock-mark adapter contract fingerprint mismatch"
            )
        for label, value in (
            ("source evidence", self.source_evidence_fingerprint),
            ("source", self.source_sha256),
        ):
            if (
                len(value) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in value
                )
            ):
                raise CurrentStockMarkAdapterError(
                    f"{label} fingerprint must be SHA-256"
                )
        if not self.source_id.strip():
            raise CurrentStockMarkAdapterError(
                "current stock-mark source id cannot be blank"
            )
        _require_aware(self.valuation_utc, label="valuation timestamp")
        ordered = tuple(
            sorted(
                self.marks,
                key=lambda mark: mark.decision_record_fingerprint,
            )
        )
        if ordered != self.marks:
            raise CurrentStockMarkAdapterError(
                "current stock marks must be deterministically ordered"
            )
        if len(
            {
                mark.decision_record_fingerprint
                for mark in self.marks
            }
        ) != len(self.marks):
            raise CurrentStockMarkAdapterError(
                "current stock marks cannot duplicate decision lineage"
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
            raise CurrentStockMarkAdapterError(
                "current stock-mark batch cannot grant external or trading authority"
            )

    @property
    def batch_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def build_current_stock_marks_v1(
    *,
    evidence: CurrentLiveEvidenceV1,
    positions: Sequence[SimulatedOpenPositionV1],
    valuation_utc: datetime,
) -> CurrentStockMarkBatchV1:
    if (
        evidence.contract_fingerprint
        != CURRENT_LIVE_EVIDENCE_CONTRACT_FINGERPRINT
    ):
        raise CurrentStockMarkAdapterError(
            "current-live evidence contract fingerprint mismatch"
        )
    valuation = _require_aware(
        valuation_utc,
        label="valuation timestamp",
    )
    if evidence.captured_at_utc > valuation:
        raise CurrentStockMarkAdapterError(
            "current-live evidence cannot be captured after valuation"
        )

    snapshot = evidence.snapshot
    if snapshot.feed_mode != LiveFeedMode.REALTIME:
        raise CurrentStockMarkAdapterError(
            "current stock marks require realtime feed evidence"
        )
    if snapshot.expected_delay_seconds != 0:
        raise CurrentStockMarkAdapterError(
            "current stock marks require zero expected feed delay"
        )
    if snapshot.connection_state != LiveConnectionState.SUBSCRIBED:
        raise CurrentStockMarkAdapterError(
            "current stock marks require subscribed live state"
        )
    if snapshot.open_transport_gap_started_at_utc is not None:
        raise CurrentStockMarkAdapterError(
            "current stock marks refuse an open transport gap"
        )

    by_symbol = {state.symbol: state for state in snapshot.symbols}
    normalized_positions = tuple(
        sorted(
            positions,
            key=lambda item: item.decision_record_fingerprint,
        )
    )
    marks: list[SimulatedMarketMarkEvidence] = []
    for position in normalized_positions:
        if position.instrument_kind != InstrumentKind.STOCK:
            raise CurrentStockMarkAdapterError(
                "v1 current mark adapter supports stock positions only"
            )
        state = by_symbol.get(position.ticker)
        if state is None:
            raise CurrentStockMarkAdapterError(
                f"missing exact-case current quote for {position.ticker}"
            )
        quote = state.quote
        if quote is None:
            raise CurrentStockMarkAdapterError(
                f"current state has no quote for {position.ticker}; minute bars are not quotes"
            )
        if state.quote_freshness != LiveFreshness.FRESH:
            raise CurrentStockMarkAdapterError(
                f"current quote is not fresh for {position.ticker}"
            )
        if (
            quote.feed_mode != LiveFeedMode.REALTIME
            or quote.expected_delay_seconds != 0
        ):
            raise CurrentStockMarkAdapterError(
                f"current quote is not zero-delay realtime for {position.ticker}"
            )
        if quote.provider_timestamp_utc < position.opened_utc:
            raise CurrentStockMarkAdapterError(
                f"current quote predates open position for {position.ticker}"
            )
        mark = build_simulated_market_mark_evidence(
            position=position,
            inputs=MarketMarkInputs(
                source_id=(
                    f"{evidence.source_id}#quote:{position.ticker}"
                ),
                source_fingerprint=evidence.source_sha256,
                provider=quote.provider.value,
                feed=quote.feed_mode.value,
                transport=MarketMarkTransport.SNAPSHOT,
                feed_quality=state.quote_freshness.value,
                market_timestamp_utc=quote.provider_timestamp_utc,
                received_utc=quote.received_at_utc,
                valuation_utc=valuation,
                bid_price_per_unit=quote.bid_price,
                ask_price_per_unit=quote.ask_price,
                last_price_per_unit=None,
            ),
        )
        if not mark.valuation_eligible:
            raise CurrentStockMarkAdapterError(
                f"current quote exceeds mark freshness policy for {position.ticker}"
            )
        marks.append(mark)

    return CurrentStockMarkBatchV1(
        contract_version=CURRENT_STOCK_MARK_ADAPTER_CONTRACT_VERSION,
        contract_fingerprint=(
            CURRENT_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
        ),
        source_evidence_fingerprint=evidence.evidence_fingerprint,
        source_id=evidence.source_id,
        source_sha256=evidence.source_sha256,
        valuation_utc=valuation,
        marks=tuple(marks),
    )


__all__ = [
    "CURRENT_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT",
    "CurrentStockMarkAdapterError",
    "CurrentStockMarkBatchV1",
    "build_current_stock_marks_v1",
]
