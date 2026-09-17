from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from packages.execution.trade_expression import InstrumentKind
from packages.simulation.market_mark_evidence_contract import (
    MARKET_MARK_EVIDENCE_CONTRACT,
    MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT,
    MAX_MARK_AGE_SECONDS,
)
from packages.simulation.open_position_state import (
    SimulatedOpenPositionV1,
    simulated_open_position_fingerprint,
)
from packages.simulation.open_position_state_contract import (
    OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
)


MARKET_MARK_EVIDENCE_CONTRACT_VERSION = str(MARKET_MARK_EVIDENCE_CONTRACT["contract_id"])
_TOLERANCE = 1e-9


class MarketMarkEvidenceError(ValueError):
    pass


class MarketMarkTransport(StrEnum):
    STREAM = "STREAM"
    SNAPSHOT = "SNAPSHOT"
    REPLAY = "REPLAY"


class MarketMarkFreshness(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
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


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise MarketMarkEvidenceError(f"{label} must be a SHA-256 fingerprint")
    try:
        int(value, 16)
    except ValueError as exc:
        raise MarketMarkEvidenceError(f"{label} must be a SHA-256 fingerprint") from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MarketMarkEvidenceError(f"{label} must be timezone-aware")


def _require_nonnegative(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise MarketMarkEvidenceError(f"{label} must be finite and nonnegative")


def _require_positive(value: float, *, label: str) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise MarketMarkEvidenceError(f"{label} must be finite and positive")


def _same(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=_TOLERANCE)


@dataclass(frozen=True)
class MarketMarkInputs:
    source_id: str
    source_fingerprint: str
    provider: str
    feed: str
    transport: MarketMarkTransport
    feed_quality: str
    market_timestamp_utc: datetime
    received_utc: datetime
    valuation_utc: datetime
    bid_price_per_unit: float
    ask_price_per_unit: float
    last_price_per_unit: float | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("source id", self.source_id),
            ("provider", self.provider),
            ("feed", self.feed),
            ("feed quality", self.feed_quality),
        ):
            if not value.strip():
                raise MarketMarkEvidenceError(f"{label} cannot be blank")
        _require_fingerprint(self.source_fingerprint, label="mark source fingerprint")
        for label, value in (
            ("market timestamp", self.market_timestamp_utc),
            ("receive timestamp", self.received_utc),
            ("valuation timestamp", self.valuation_utc),
        ):
            _require_aware(value, label=label)
        if self.market_timestamp_utc > self.received_utc:
            raise MarketMarkEvidenceError("market timestamp cannot follow receive timestamp")
        if self.received_utc > self.valuation_utc:
            raise MarketMarkEvidenceError("receive timestamp cannot follow valuation timestamp")
        _require_nonnegative(self.bid_price_per_unit, label="bid price")
        _require_nonnegative(self.ask_price_per_unit, label="ask price")
        if self.ask_price_per_unit + _TOLERANCE < self.bid_price_per_unit:
            raise MarketMarkEvidenceError("ask price cannot be below bid price")
        if self.last_price_per_unit is not None:
            _require_nonnegative(self.last_price_per_unit, label="last price")


@dataclass(frozen=True)
class SimulatedMarketMarkEvidence:
    contract_version: str
    contract_fingerprint: str
    open_position_contract_fingerprint: str
    position_fingerprint: str
    source_account_state_fingerprint: str
    decision_record_fingerprint: str
    fill_fingerprint: str
    funding_terms_fingerprint: str

    instrument_kind: InstrumentKind
    instrument_id: str
    ticker: str
    option_contract_ticker: str | None
    option_contract_type: str | None

    source_id: str
    source_fingerprint: str
    provider: str
    feed: str
    transport: MarketMarkTransport
    feed_quality: str
    market_timestamp_utc: datetime
    received_utc: datetime
    valuation_utc: datetime
    mark_age_seconds: float

    bid_price_per_unit: float
    ask_price_per_unit: float
    last_price_per_unit: float | None
    selected_mark_side: str
    selected_mark_price_per_unit: float
    freshness: MarketMarkFreshness
    valuation_eligible: bool
    reason_codes: tuple[str, ...]

    descriptive_only: bool = True
    account_mutation_authority: bool = False
    mark_to_market_authority: bool = False
    unrealized_pnl_authority: bool = False
    realized_pnl_authority: bool = False
    exit_closeout_authority: bool = False
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
        if self.contract_version != MARKET_MARK_EVIDENCE_CONTRACT_VERSION:
            raise MarketMarkEvidenceError("market-mark evidence contract version mismatch")
        if self.contract_fingerprint != MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT:
            raise MarketMarkEvidenceError("market-mark evidence contract fingerprint mismatch")
        if self.open_position_contract_fingerprint != OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT:
            raise MarketMarkEvidenceError("open-position contract fingerprint mismatch")
        for label, value in (
            ("position", self.position_fingerprint),
            ("source account state", self.source_account_state_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("fill", self.fill_fingerprint),
            ("funding terms", self.funding_terms_fingerprint),
            ("source", self.source_fingerprint),
        ):
            _require_fingerprint(value, label=f"{label} fingerprint")
        if not self.instrument_id.strip() or not self.ticker.strip():
            raise MarketMarkEvidenceError("marked position identity cannot be blank")
        for label, value in (
            ("source id", self.source_id),
            ("provider", self.provider),
            ("feed", self.feed),
            ("feed quality", self.feed_quality),
        ):
            if not value.strip():
                raise MarketMarkEvidenceError(f"{label} cannot be blank")
        for label, value in (
            ("market timestamp", self.market_timestamp_utc),
            ("receive timestamp", self.received_utc),
            ("valuation timestamp", self.valuation_utc),
        ):
            _require_aware(value, label=label)
        if self.market_timestamp_utc > self.received_utc or self.received_utc > self.valuation_utc:
            raise MarketMarkEvidenceError("mark timestamps must satisfy market <= receive <= valuation")
        _require_nonnegative(self.mark_age_seconds, label="mark age")
        expected_age = (self.valuation_utc - self.market_timestamp_utc).total_seconds()
        if not _same(self.mark_age_seconds, expected_age):
            raise MarketMarkEvidenceError("mark age must equal valuation minus market timestamp")
        _require_nonnegative(self.bid_price_per_unit, label="bid price")
        _require_nonnegative(self.ask_price_per_unit, label="ask price")
        if self.ask_price_per_unit + _TOLERANCE < self.bid_price_per_unit:
            raise MarketMarkEvidenceError("ask price cannot be below bid price")
        if self.last_price_per_unit is not None:
            _require_nonnegative(self.last_price_per_unit, label="last price")
        if self.selected_mark_side != "BID":
            raise MarketMarkEvidenceError("v1 conservative mark side must be BID")
        if not _same(self.selected_mark_price_per_unit, self.bid_price_per_unit):
            raise MarketMarkEvidenceError("selected mark must equal bid price")
        if not self.reason_codes:
            raise MarketMarkEvidenceError("market-mark evidence requires reason codes")
        if not self.descriptive_only:
            raise MarketMarkEvidenceError("market-mark evidence must remain descriptive only")

        expected_freshness = (
            MarketMarkFreshness.FRESH
            if self.mark_age_seconds <= MAX_MARK_AGE_SECONDS + _TOLERANCE
            else MarketMarkFreshness.STALE
        )
        if self.freshness != expected_freshness:
            raise MarketMarkEvidenceError("mark freshness does not match frozen age policy")
        if self.valuation_eligible != (self.freshness == MarketMarkFreshness.FRESH):
            raise MarketMarkEvidenceError("valuation eligibility must match freshness state")

        if self.instrument_kind == InstrumentKind.STOCK:
            if self.option_contract_ticker is not None or self.option_contract_type is not None:
                raise MarketMarkEvidenceError("stock mark cannot carry option identity")
            _require_positive(self.bid_price_per_unit, label="stock bid price")
            _require_positive(self.ask_price_per_unit, label="stock ask price")
        elif self.instrument_kind == InstrumentKind.OPTION:
            if not self.option_contract_ticker or self.option_contract_type not in {"call", "put"}:
                raise MarketMarkEvidenceError("option mark requires call/put contract identity")
            _require_positive(self.ask_price_per_unit, label="option ask price")
        else:
            raise MarketMarkEvidenceError("unsupported marked instrument kind")

        forbidden = (
            self.account_mutation_authority,
            self.mark_to_market_authority,
            self.unrealized_pnl_authority,
            self.realized_pnl_authority,
            self.exit_closeout_authority,
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
            raise MarketMarkEvidenceError(
                "market-mark evidence cannot grant mutation, valuation/P&L, provider, broker, order, trading, promotion, or confluence authority"
            )

    @property
    def mark_fingerprint(self) -> str:
        return simulated_market_mark_fingerprint(self)


def simulated_market_mark_fingerprint(mark: SimulatedMarketMarkEvidence) -> str:
    return _fingerprint_payload(mark)


def build_simulated_market_mark_evidence(
    *,
    position: SimulatedOpenPositionV1,
    inputs: MarketMarkInputs,
) -> SimulatedMarketMarkEvidence:
    position_fingerprint = simulated_open_position_fingerprint(position)
    mark_age_seconds = (inputs.valuation_utc - inputs.market_timestamp_utc).total_seconds()
    freshness = (
        MarketMarkFreshness.FRESH
        if mark_age_seconds <= MAX_MARK_AGE_SECONDS + _TOLERANCE
        else MarketMarkFreshness.STALE
    )
    valuation_eligible = freshness == MarketMarkFreshness.FRESH

    reason_codes = [
        "EXACT_OPEN_POSITION_FINGERPRINT_BOUND",
        "SOURCE_PROVIDER_FEED_TRANSPORT_PROVENANCE_BOUND",
        "CONSERVATIVE_EXECUTABLE_BID_SELECTED",
        "MIDPOINT_AND_LAST_NOT_USED_AS_VALUATION_TRUTH",
    ]
    if valuation_eligible:
        reason_codes.append("MARK_FRESH_UNDER_FROZEN_60_SECOND_POLICY")
    else:
        reason_codes.append("STALE_MARK_PRESERVED_NOT_VALUATION_ELIGIBLE")

    return SimulatedMarketMarkEvidence(
        contract_version=MARKET_MARK_EVIDENCE_CONTRACT_VERSION,
        contract_fingerprint=MARKET_MARK_EVIDENCE_CONTRACT_FINGERPRINT,
        open_position_contract_fingerprint=OPEN_POSITION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
        position_fingerprint=position_fingerprint,
        source_account_state_fingerprint=position.source_account_state_fingerprint,
        decision_record_fingerprint=position.decision_record_fingerprint,
        fill_fingerprint=position.fill_fingerprint,
        funding_terms_fingerprint=position.funding_terms_fingerprint,
        instrument_kind=position.instrument_kind,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        option_contract_ticker=position.option_contract_ticker,
        option_contract_type=position.option_contract_type,
        source_id=inputs.source_id,
        source_fingerprint=inputs.source_fingerprint,
        provider=inputs.provider,
        feed=inputs.feed,
        transport=inputs.transport,
        feed_quality=inputs.feed_quality,
        market_timestamp_utc=inputs.market_timestamp_utc,
        received_utc=inputs.received_utc,
        valuation_utc=inputs.valuation_utc,
        mark_age_seconds=mark_age_seconds,
        bid_price_per_unit=float(inputs.bid_price_per_unit),
        ask_price_per_unit=float(inputs.ask_price_per_unit),
        last_price_per_unit=(
            None if inputs.last_price_per_unit is None else float(inputs.last_price_per_unit)
        ),
        selected_mark_side="BID",
        selected_mark_price_per_unit=float(inputs.bid_price_per_unit),
        freshness=freshness,
        valuation_eligible=valuation_eligible,
        reason_codes=tuple(reason_codes),
    )
