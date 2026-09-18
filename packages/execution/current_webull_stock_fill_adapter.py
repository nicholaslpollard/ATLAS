from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel

from packages.core.enums import SessionSegment
from packages.execution.current_webull_quote_bundle import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
    CurrentWebullStockQuoteBundleV1,
    CurrentWebullStockQuoteV1,
)
from packages.execution.current_webull_stock_fill_adapter_contract import (
    CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT,
    CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT,
)
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.trade_expression import (
    InstrumentKind,
    SelectionKind,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.decision_record import SimulationDecisionRecord
from packages.simulation.recurrent_entry_evidence import (
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingTermsV1,
    build_recurrent_entry_fill_evidence,
    build_recurrent_funding_terms,
)
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillEvidenceV1,
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
)
from packages.simulation.simulated_fill import SimulatedEntryFillInputs


CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_VERSION = str(
    CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT["contract_id"]
)


class CurrentWebullStockFillAdapterError(RuntimeError):
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


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise CurrentWebullStockFillAdapterError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_fee(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise CurrentWebullStockFillAdapterError(
            f"{label} must be finite and nonnegative"
        )


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentWebullStockFillAdapterError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


@dataclass(frozen=True)
class ExplicitStockEntryFeeV1:
    decision_record_fingerprint: str
    entry_fees_dollars: float

    def __post_init__(self) -> None:
        _require_sha(
            self.decision_record_fingerprint,
            label="entry decision record",
        )
        _require_fee(
            self.entry_fees_dollars,
            label="explicit entry fees",
        )


@dataclass(frozen=True)
class ExplicitStockExitFeeV1:
    position_fingerprint: str
    exit_fees_dollars: float

    def __post_init__(self) -> None:
        _require_sha(
            self.position_fingerprint,
            label="exit position",
        )
        _require_fee(
            self.exit_fees_dollars,
            label="explicit exit fees",
        )


@dataclass(frozen=True)
class CurrentWebullStockEntryBatchV1:
    contract_version: str
    contract_fingerprint: str
    source_bundle_fingerprint: str
    source_recurrent_state_fingerprint: str
    valuation_utc: datetime
    entries: tuple[
        tuple[RecurrentEntryFillEvidenceV1, RecurrentFundingTermsV1],
        ...,
    ]

    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False

    def __post_init__(self) -> None:
        _validate_batch_common(
            contract_version=self.contract_version,
            contract_fingerprint=self.contract_fingerprint,
            source_bundle_fingerprint=self.source_bundle_fingerprint,
            source_recurrent_state_fingerprint=(
                self.source_recurrent_state_fingerprint
            ),
            valuation_utc=self.valuation_utc,
            forbidden=(
                self.provider_read_authority,
                self.provider_write_authority,
                self.broker_read_authority,
                self.broker_write_authority,
                self.broker_fill_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
            ),
        )
        ordered = tuple(
            sorted(
                self.entries,
                key=lambda item: item[0].decision_record_fingerprint,
            )
        )
        if ordered != self.entries:
            raise CurrentWebullStockFillAdapterError(
                "Webull stock entry batch must be deterministically ordered"
            )

    @property
    def batch_fingerprint(self) -> str:
        return _fingerprint_payload(self)


@dataclass(frozen=True)
class CurrentWebullStockExitBatchV1:
    contract_version: str
    contract_fingerprint: str
    source_bundle_fingerprint: str
    source_recurrent_state_fingerprint: str
    valuation_utc: datetime
    fills: tuple[RecurrentExitFillEvidenceV1, ...]

    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False

    def __post_init__(self) -> None:
        _validate_batch_common(
            contract_version=self.contract_version,
            contract_fingerprint=self.contract_fingerprint,
            source_bundle_fingerprint=self.source_bundle_fingerprint,
            source_recurrent_state_fingerprint=(
                self.source_recurrent_state_fingerprint
            ),
            valuation_utc=self.valuation_utc,
            forbidden=(
                self.provider_read_authority,
                self.provider_write_authority,
                self.broker_read_authority,
                self.broker_write_authority,
                self.broker_fill_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
            ),
        )
        ordered = tuple(
            sorted(
                self.fills,
                key=lambda fill: fill.decision_record_fingerprint,
            )
        )
        if ordered != self.fills:
            raise CurrentWebullStockFillAdapterError(
                "Webull stock exit batch must be deterministically ordered"
            )

    @property
    def batch_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _validate_batch_common(
    *,
    contract_version: str,
    contract_fingerprint: str,
    source_bundle_fingerprint: str,
    source_recurrent_state_fingerprint: str,
    valuation_utc: datetime,
    forbidden: tuple[bool, ...],
) -> None:
    if (
        contract_version
        != CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_VERSION
    ):
        raise CurrentWebullStockFillAdapterError(
            "Webull stock-fill adapter contract version mismatch"
        )
    if (
        contract_fingerprint
        != CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockFillAdapterError(
            "Webull stock-fill adapter contract fingerprint mismatch"
        )
    _require_sha(source_bundle_fingerprint, label="source bundle")
    _require_sha(
        source_recurrent_state_fingerprint,
        label="source recurrent state",
    )
    _require_aware(valuation_utc, label="valuation timestamp")
    if any(forbidden):
        raise CurrentWebullStockFillAdapterError(
            "Webull stock-fill batch cannot grant provider, broker, fill, order, or trading authority"
        )


def _validate_bundle_and_valuation(
    *,
    bundle: CurrentWebullStockQuoteBundleV1,
    valuation_utc: datetime,
) -> tuple[datetime, dict[str, CurrentWebullStockQuoteV1]]:
    if (
        bundle.contract_fingerprint
        != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockFillAdapterError(
            "current Webull quote bundle contract fingerprint mismatch"
        )
    valuation = _require_aware(
        valuation_utc,
        label="valuation timestamp",
    )
    if bundle.captured_at_utc > valuation:
        raise CurrentWebullStockFillAdapterError(
            "Webull quote bundle cannot be captured after valuation"
        )
    return valuation, {quote.symbol: quote for quote in bundle.quotes}


def _quote_for(
    *,
    quotes: dict[str, CurrentWebullStockQuoteV1],
    ticker: str,
    valuation_utc: datetime,
    not_before_utc: datetime,
) -> CurrentWebullStockQuoteV1:
    quote = quotes.get(ticker)
    if quote is None:
        raise CurrentWebullStockFillAdapterError(
            f"missing exact-case Webull quote for {ticker}"
        )
    if quote.session_segment != SessionSegment.REGULAR:
        raise CurrentWebullStockFillAdapterError(
            f"Webull quote is outside regular session for {ticker}"
        )
    if quote.provider_timestamp_utc < not_before_utc:
        raise CurrentWebullStockFillAdapterError(
            f"Webull quote predates required lineage for {ticker}"
        )
    provider_age = (
        valuation_utc - quote.provider_timestamp_utc
    ).total_seconds()
    receive_age = (
        valuation_utc - quote.received_at_utc
    ).total_seconds()
    if provider_age < -5.0 or receive_age < -5.0:
        raise CurrentWebullStockFillAdapterError(
            f"Webull quote is ahead of valuation for {ticker}"
        )
    if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
        raise CurrentWebullStockFillAdapterError(
            f"Webull quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap for {ticker}"
        )
    if receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
        raise CurrentWebullStockFillAdapterError(
            f"Webull quote receipt is stale for {ticker}"
        )
    return quote


def build_current_webull_stock_entries_v1(
    *,
    bundle: CurrentWebullStockQuoteBundleV1,
    account: RecurrentLifecycleAccountV1,
    records: Sequence[SimulationDecisionRecord],
    fees: Sequence[ExplicitStockEntryFeeV1],
    valuation_utc: datetime,
) -> CurrentWebullStockEntryBatchV1:
    valuation, quotes = _validate_bundle_and_valuation(
        bundle=bundle,
        valuation_utc=valuation_utc,
    )
    if valuation < account.state.as_of_utc:
        raise CurrentWebullStockFillAdapterError(
            "entry valuation cannot precede recurrent account state"
        )

    record_map: dict[str, SimulationDecisionRecord] = {}
    for record in records:
        fp = record.record_fingerprint
        if fp in record_map:
            raise CurrentWebullStockFillAdapterError(
                "entry records cannot duplicate decision fingerprints"
            )
        record_map[fp] = record

    ordered_fees = tuple(
        sorted(fees, key=lambda item: item.decision_record_fingerprint)
    )
    if len(ordered_fees) != len(
        {item.decision_record_fingerprint for item in ordered_fees}
    ):
        raise CurrentWebullStockFillAdapterError(
            "entry fee inputs cannot duplicate decision fingerprints"
        )

    entries: list[
        tuple[RecurrentEntryFillEvidenceV1, RecurrentFundingTermsV1]
    ] = []
    for fee in ordered_fees:
        record = record_map.get(fee.decision_record_fingerprint)
        if record is None:
            raise CurrentWebullStockFillAdapterError(
                "explicit entry fee references a missing decision record"
            )
        decision = record.trade_expression_decision
        if decision.selection_kind != SelectionKind.STOCK:
            raise CurrentWebullStockFillAdapterError(
                "Webull stock entry requires a STOCK-selected decision"
            )
        if record.forecast.direction != DiscoveryDirection.BULLISH:
            raise CurrentWebullStockFillAdapterError(
                "Webull stock entry v1 supports bullish cash-funded stock longs only"
            )
        quote = _quote_for(
            quotes=quotes,
            ticker=record.forecast.ticker,
            valuation_utc=valuation,
            not_before_utc=record.decision_created_utc,
        )
        fill = build_recurrent_entry_fill_evidence(
            account=account,
            record=record,
            inputs=SimulatedEntryFillInputs(
                fill_source_id=(
                    "current-webull-stock-quote-bundle#entry:"
                    + record.forecast.ticker
                ),
                fill_source_fingerprint=bundle.bundle_fingerprint,
                filled_utc=valuation,
                fill_price_per_unit=quote.ask_price,
                explicit_entry_fees_dollars=fee.entry_fees_dollars,
            ),
        )
        funding = build_recurrent_funding_terms(
            account=account,
            fill=fill,
        )
        entries.append((fill, funding))

    return CurrentWebullStockEntryBatchV1(
        contract_version=(
            CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT
        ),
        source_bundle_fingerprint=bundle.bundle_fingerprint,
        source_recurrent_state_fingerprint=account.state.state_fingerprint,
        valuation_utc=valuation,
        entries=tuple(entries),
    )


def build_current_webull_stock_exits_v1(
    *,
    bundle: CurrentWebullStockQuoteBundleV1,
    account: RecurrentLifecycleAccountV1,
    fees: Sequence[ExplicitStockExitFeeV1],
    valuation_utc: datetime,
) -> CurrentWebullStockExitBatchV1:
    valuation, quotes = _validate_bundle_and_valuation(
        bundle=bundle,
        valuation_utc=valuation_utc,
    )
    if valuation < account.state.as_of_utc:
        raise CurrentWebullStockFillAdapterError(
            "exit valuation cannot precede recurrent account state"
        )

    position_map = {
        position.position_fingerprint: position
        for position in account.state.open_positions
    }
    ordered_fees = tuple(
        sorted(fees, key=lambda item: item.position_fingerprint)
    )
    if len(ordered_fees) != len(
        {item.position_fingerprint for item in ordered_fees}
    ):
        raise CurrentWebullStockFillAdapterError(
            "exit fee inputs cannot duplicate position fingerprints"
        )

    fills: list[RecurrentExitFillEvidenceV1] = []
    for fee in ordered_fees:
        position = position_map.get(fee.position_fingerprint)
        if position is None:
            raise CurrentWebullStockFillAdapterError(
                "explicit exit fee references a missing active position"
            )
        if position.instrument_kind != InstrumentKind.STOCK:
            raise CurrentWebullStockFillAdapterError(
                "Webull stock exit v1 supports stock positions only"
            )
        quote = _quote_for(
            quotes=quotes,
            ticker=position.ticker,
            valuation_utc=valuation,
            not_before_utc=position.opened_utc,
        )
        fills.append(
            build_recurrent_exit_fill_evidence(
                source_state=account.state,
                position_fingerprint=position.position_fingerprint,
                inputs=RecurrentExitFillInputsV1(
                    fill_source_id=(
                        "current-webull-stock-quote-bundle#exit:"
                        + position.ticker
                    ),
                    fill_source_fingerprint=bundle.bundle_fingerprint,
                    exited_utc=valuation,
                    exit_price_per_unit=quote.bid_price,
                    explicit_exit_fees_dollars=fee.exit_fees_dollars,
                ),
            )
        )

    return CurrentWebullStockExitBatchV1(
        contract_version=(
            CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT
        ),
        source_bundle_fingerprint=bundle.bundle_fingerprint,
        source_recurrent_state_fingerprint=account.state.state_fingerprint,
        valuation_utc=valuation,
        fills=tuple(
            sorted(
                fills,
                key=lambda fill: fill.decision_record_fingerprint,
            )
        ),
    )


__all__ = [
    "CURRENT_WEBULL_STOCK_FILL_ADAPTER_CONTRACT_FINGERPRINT",
    "CurrentWebullStockEntryBatchV1",
    "CurrentWebullStockExitBatchV1",
    "CurrentWebullStockFillAdapterError",
    "ExplicitStockEntryFeeV1",
    "ExplicitStockExitFeeV1",
    "build_current_webull_stock_entries_v1",
    "build_current_webull_stock_exits_v1",
]
