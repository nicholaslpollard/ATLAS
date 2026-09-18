from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import SessionSegment
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_quote_bundle import (
    CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT,
    CurrentWebullStockQuoteBundleV1,
    CurrentWebullStockQuoteV1,
)
from packages.execution.current_webull_stock_entry_contract import (
    CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT,
    CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.trade_expression import (
    InstrumentKind,
    SelectionKind,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.recurrent_cycle import RecurrentCycleReceiptV1
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunIdentityV1,
    RecurrentCycleRunnerV1,
)
from packages.simulation.recurrent_entry_evidence import (
    RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT,
    RECURRENT_ENTRY_FILL_CONTRACT_VERSION,
    RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT,
    RECURRENT_FUNDING_TERMS_CONTRACT_VERSION,
    RecurrentEntryFillEvidenceV1,
    RecurrentFundingModel,
    RecurrentFundingTermsV1,
    build_recurrent_entry_fill_evidence,
    build_recurrent_funding_terms,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    RecurrentLifecycleEventKind,
)
from packages.simulation.recurrent_positions import (
    RecurrentPositionTransitionError,
    apply_recurrent_entry_batch_v1,
)
from packages.simulation.recurrent_reserve_evidence import (
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT,
    RecurrentReserveEvidenceBundleV1,
)
from packages.simulation.simulated_fill import SimulatedEntryFillInputs


CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_VERSION = str(
    CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT["contract_id"]
)
CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_SOURCE_ID = (
    "atlas-current-webull-stock-entry/current.json"
)
_MAX_BUNDLE_BYTES = 64 * 1024 * 1024


class CurrentWebullStockEntryEvidenceError(RuntimeError):
    pass


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentWebullStockEntryEvidenceError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CurrentWebullStockEntryEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        )


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


def _fingerprint_payload(value: object) -> str:
    raw = json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CurrentWebullStockEntryPairV1:
    quote: CurrentWebullStockQuoteV1
    explicit_entry_fee_dollars: float
    fill: RecurrentEntryFillEvidenceV1
    funding: RecurrentFundingTermsV1

    def __post_init__(self) -> None:
        if (
            self.fill.contract_fingerprint
            != RECURRENT_ENTRY_FILL_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "entry pair fill contract fingerprint mismatch"
            )
        if (
            self.funding.contract_fingerprint
            != RECURRENT_FUNDING_TERMS_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "entry pair funding contract fingerprint mismatch"
            )
        if self.fill.instrument_kind != InstrumentKind.STOCK:
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY v1 supports stock fills only"
            )
        if (
            not math.isfinite(self.explicit_entry_fee_dollars)
            or self.explicit_entry_fee_dollars < 0.0
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY explicit fee must be finite and nonnegative"
            )
        if self.quote.symbol != self.fill.ticker:
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY quote/fill symbol mismatch"
            )
        if self.quote.session_segment != SessionSegment.REGULAR:
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY quote must be regular-session"
            )
        if self.quote.received_at_utc != self.fill.filled_utc:
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY fill timestamp must equal quote receipt"
            )
        if not math.isclose(
            self.quote.ask_price,
            self.fill.fill_price_per_unit,
            rel_tol=1e-12,
            abs_tol=1e-9,
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY fill price must equal quote ask"
            )
        if not math.isclose(
            self.explicit_entry_fee_dollars,
            self.fill.entry_fees_dollars,
            rel_tol=1e-12,
            abs_tol=1e-9,
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY fill fee does not match explicit fee evidence"
            )
        checks = (
            (
                self.funding.recurrent_state_fingerprint,
                self.fill.recurrent_state_fingerprint,
                "recurrent state",
            ),
            (
                self.funding.fill_fingerprint,
                self.fill.fill_fingerprint,
                "fill",
            ),
            (
                self.funding.active_reservation_fingerprint,
                self.fill.active_reservation_fingerprint,
                "reservation",
            ),
            (
                self.funding.decision_record_fingerprint,
                self.fill.decision_record_fingerprint,
                "decision",
            ),
            (
                self.funding.candidate_fingerprint,
                self.fill.candidate_fingerprint,
                "candidate",
            ),
            (
                self.funding.instrument_kind,
                self.fill.instrument_kind,
                "instrument kind",
            ),
            (
                self.funding.direction,
                self.fill.direction,
                "direction",
            ),
        )
        for left, right, label in checks:
            if left != right:
                raise CurrentWebullStockEntryEvidenceError(
                    f"entry pair {label} lineage mismatch"
                )
        if (
            self.funding.funding_model
            != RecurrentFundingModel.CASH_ONLY_STOCK_LONG
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull stock ENTRY requires cash-only stock funding"
            )
        required = (
            self.fill.gross_fill_notional_dollars
            + self.fill.entry_fees_dollars
        )
        reserved = self.fill.reserved_capital_dollars
        supplemental = max(0.0, required - reserved)
        unspent = max(0.0, reserved - required)
        arithmetic = (
            (
                self.funding.required_cash_dollars,
                required,
                "required cash",
            ),
            (
                self.funding.reserved_capital_dollars,
                reserved,
                "reserved capital",
            ),
            (
                self.funding.supplemental_unreserved_cash_required_dollars,
                supplemental,
                "supplemental cash",
            ),
            (
                self.funding.unspent_reserved_capital_dollars,
                unspent,
                "unspent reserve",
            ),
        )
        for actual, expected, label in arithmetic:
            if not math.isclose(
                actual,
                expected,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise CurrentWebullStockEntryEvidenceError(
                    f"current Webull ENTRY funding {label} mismatch"
                )

    @property
    def pair_fingerprint(self) -> str:
        return _fingerprint_payload(
            {
                "fill_fingerprint": self.fill.fill_fingerprint,
                "funding_terms_fingerprint": (
                    self.funding.terms_fingerprint
                ),
            }
        )


def _entry_fill_source_fingerprint(
    *,
    quote_bundle_fingerprint: str,
    fee_source_id: str,
    fee_source_fingerprint: str,
    decision_record_fingerprint: str,
    quote: CurrentWebullStockQuoteV1,
    explicit_entry_fee_dollars: float,
) -> str:
    return _fingerprint_payload(
        {
            "contract_fingerprint": (
                CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT
            ),
            "quote_bundle_fingerprint": quote_bundle_fingerprint,
            "fee_source_id": fee_source_id,
            "fee_source_fingerprint": fee_source_fingerprint,
            "decision_record_fingerprint": (
                decision_record_fingerprint
            ),
            "quote": quote,
            "explicit_entry_fee_dollars": (
                explicit_entry_fee_dollars
            ),
        }
    )


def _bundle_payload(
    *,
    cycle_id: str,
    cycle_fingerprint: str,
    source_recurrent_state_fingerprint: str,
    reserve_bundle_fingerprint: str,
    quote_bundle_fingerprint: str,
    fee_source_id: str,
    fee_source_fingerprint: str,
    built_at_utc: datetime,
    pairs: tuple[CurrentWebullStockEntryPairV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT
        ),
        "source_id": CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_SOURCE_ID,
        "cycle_id": cycle_id,
        "cycle_fingerprint": cycle_fingerprint,
        "source_recurrent_state_fingerprint": (
            source_recurrent_state_fingerprint
        ),
        "reserve_bundle_fingerprint": reserve_bundle_fingerprint,
        "quote_bundle_fingerprint": quote_bundle_fingerprint,
        "fee_source_id": fee_source_id,
        "fee_source_fingerprint": fee_source_fingerprint,
        "built_at_utc": built_at_utc,
        "pairs": pairs,
        "provider_calls_performed": 0,
        "broker_calls_performed": 0,
        "provider_read_authority": False,
        "provider_write_authority": False,
        "broker_read_authority": False,
        "broker_write_authority": False,
        "broker_fill_authority": False,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class CurrentWebullStockEntryEvidenceBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    cycle_id: str
    cycle_fingerprint: str
    source_recurrent_state_fingerprint: str
    reserve_bundle_fingerprint: str
    quote_bundle_fingerprint: str
    fee_source_id: str
    fee_source_fingerprint: str
    built_at_utc: datetime
    pairs: tuple[CurrentWebullStockEntryPairV1, ...]

    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_VERSION
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY contract fingerprint mismatch"
            )
        if self.source_id != CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_SOURCE_ID:
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY source id mismatch"
            )
        for label, value in (
            ("bundle", self.bundle_fingerprint),
            ("cycle", self.cycle_fingerprint),
            (
                "source recurrent state",
                self.source_recurrent_state_fingerprint,
            ),
            ("reserve bundle", self.reserve_bundle_fingerprint),
            ("quote bundle", self.quote_bundle_fingerprint),
            ("fee source", self.fee_source_fingerprint),
        ):
            _require_sha(value, label=label)
        if not self.fee_source_id.strip():
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY fee source id cannot be blank"
            )
        built = _require_aware(
            self.built_at_utc,
            label="current Webull ENTRY build time",
        )
        ordered = tuple(
            sorted(
                self.pairs,
                key=lambda item: (
                    item.fill.filled_utc,
                    item.fill.fill_fingerprint,
                ),
            )
        )
        if ordered != self.pairs:
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY pairs must be deterministically ordered"
            )
        decisions = tuple(
            pair.fill.decision_record_fingerprint
            for pair in self.pairs
        )
        if len(decisions) != len(set(decisions)):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY bundle cannot duplicate decisions"
            )
        if any(pair.fill.filled_utc > built for pair in self.pairs):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY fill cannot occur after bundle build"
            )
        for pair in self.pairs:
            expected_source = _entry_fill_source_fingerprint(
                quote_bundle_fingerprint=(
                    self.quote_bundle_fingerprint
                ),
                fee_source_id=self.fee_source_id,
                fee_source_fingerprint=(
                    self.fee_source_fingerprint
                ),
                decision_record_fingerprint=(
                    pair.fill.decision_record_fingerprint
                ),
                quote=pair.quote,
                explicit_entry_fee_dollars=(
                    pair.explicit_entry_fee_dollars
                ),
            )
            if (
                pair.fill.fill_source_fingerprint
                != expected_source
            ):
                raise CurrentWebullStockEntryEvidenceError(
                    "current Webull ENTRY fill source fingerprint mismatch"
                )
        if any(
            (
                self.provider_calls_performed,
                self.broker_calls_performed,
            )
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY evidence performs no network calls"
            )
        if any(
            (
                self.provider_read_authority,
                self.provider_write_authority,
                self.broker_read_authority,
                self.broker_write_authority,
                self.broker_fill_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY bundle cannot grant external or trading authority"
            )
        expected = _fingerprint_payload(
            _bundle_payload(
                cycle_id=self.cycle_id,
                cycle_fingerprint=self.cycle_fingerprint,
                source_recurrent_state_fingerprint=(
                    self.source_recurrent_state_fingerprint
                ),
                reserve_bundle_fingerprint=(
                    self.reserve_bundle_fingerprint
                ),
                quote_bundle_fingerprint=(
                    self.quote_bundle_fingerprint
                ),
                fee_source_id=self.fee_source_id,
                fee_source_fingerprint=self.fee_source_fingerprint,
                built_at_utc=built,
                pairs=self.pairs,
            )
        )
        if self.bundle_fingerprint != expected:
            raise CurrentWebullStockEntryEvidenceError(
                "current Webull ENTRY bundle self-fingerprint mismatch"
            )

    @property
    def runner_entries(
        self,
    ) -> tuple[
        tuple[
            RecurrentEntryFillEvidenceV1,
            RecurrentFundingTermsV1,
        ],
        ...,
    ]:
        return tuple(
            (pair.fill, pair.funding)
            for pair in self.pairs
        )


def _explicit_rejection_for_decision(
    account: RecurrentLifecycleAccountV1,
    decision_record_fingerprint: str,
) -> bool:
    return any(
        event.decision_record_fingerprint
        == decision_record_fingerprint
        and event.kind
        == RecurrentLifecycleEventKind.REJECT_INSUFFICIENT_CAPITAL
        for event in account.ledger.events
    )


def _active_reservation_decisions(
    account: RecurrentLifecycleAccountV1,
) -> tuple[set[str], set[str]]:
    return (
        {
            item.decision_record_fingerprint
            for item in account.state.stock_reservations
        },
        {
            item.decision_record_fingerprint
            for item in account.state.option_reservations
        },
    )


def build_current_webull_stock_entry_evidence_bundle_v1(
    *,
    account: RecurrentLifecycleAccountV1,
    reserve_bundle: RecurrentReserveEvidenceBundleV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1,
    explicit_entry_fees_by_decision: Mapping[str, float],
    fee_source_id: str,
    fee_source_fingerprint: str,
    built_at_utc: datetime | None = None,
) -> CurrentWebullStockEntryEvidenceBundleV1:
    if (
        reserve_bundle.contract_fingerprint
        != RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockEntryEvidenceError(
            "reserve evidence bundle contract fingerprint mismatch"
        )
    if (
        quote_bundle.contract_fingerprint
        != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockEntryEvidenceError(
            "Webull quote bundle contract fingerprint mismatch"
        )
    if not fee_source_id.strip():
        raise CurrentWebullStockEntryEvidenceError(
            "explicit entry fee source id cannot be blank"
        )
    _require_sha(
        fee_source_fingerprint,
        label="explicit entry fee source",
    )
    built = _require_aware(
        built_at_utc or datetime.now(UTC),
        label="current Webull ENTRY build time",
    )
    if built < account.state.as_of_utc:
        raise CurrentWebullStockEntryEvidenceError(
            "ENTRY evidence cannot be built before current recurrent state"
        )

    quotes = {quote.symbol: quote for quote in quote_bundle.quotes}
    stock_active, option_active = _active_reservation_decisions(account)

    reserve_record_fps = {
        entry.record.record_fingerprint
        for entry in reserve_bundle.entries
    }
    orphan_stock = stock_active - reserve_record_fps
    orphan_option = option_active - reserve_record_fps
    if orphan_stock or orphan_option:
        raise CurrentWebullStockEntryEvidenceError(
            "active recurrent reservation lacks current RESERVE decision evidence"
        )

    selected_stock_records = []
    for entry in reserve_bundle.entries:
        record = entry.record
        decision_fp = record.record_fingerprint
        selection = record.trade_expression_decision.selection_kind
        if selection == SelectionKind.ABSTAIN:
            continue
        if selection == SelectionKind.OPTION:
            if decision_fp in option_active:
                raise CurrentWebullStockEntryEvidenceError(
                    "current Webull ENTRY v1 cannot enter active option reservations"
                )
            if _explicit_rejection_for_decision(account, decision_fp):
                continue
            raise CurrentWebullStockEntryEvidenceError(
                "selected option has neither active reservation nor explicit capital rejection"
            )
        if selection != SelectionKind.STOCK:
            raise CurrentWebullStockEntryEvidenceError(
                "unsupported recurrent ENTRY selection kind"
            )
        if decision_fp in stock_active:
            selected_stock_records.append(record)
            continue
        if _explicit_rejection_for_decision(account, decision_fp):
            continue
        raise CurrentWebullStockEntryEvidenceError(
            "selected stock has neither active reservation nor explicit capital rejection"
        )

    required_fee_keys = {
        record.record_fingerprint
        for record in selected_stock_records
    }
    supplied_fee_keys = set(explicit_entry_fees_by_decision)
    if supplied_fee_keys != required_fee_keys:
        missing = sorted(required_fee_keys - supplied_fee_keys)
        extra = sorted(supplied_fee_keys - required_fee_keys)
        raise CurrentWebullStockEntryEvidenceError(
            "explicit entry fee coverage must exactly match active stock decisions; "
            f"missing={missing}, extra={extra}"
        )

    pairs: list[CurrentWebullStockEntryPairV1] = []
    for record in selected_stock_records:
        decision_fp = record.record_fingerprint
        ticker = record.forecast.ticker
        quote = quotes.get(ticker)
        if quote is None:
            raise CurrentWebullStockEntryEvidenceError(
                f"Webull quote bundle lacks exact-case stock symbol {ticker}"
            )
        if quote.session_segment != SessionSegment.REGULAR:
            raise CurrentWebullStockEntryEvidenceError(
                f"Webull entry quote is outside regular session for {ticker}"
            )
        if quote.received_at_utc < account.state.as_of_utc:
            raise CurrentWebullStockEntryEvidenceError(
                f"Webull entry quote predates recurrent RESERVE state for {ticker}"
            )
        provider_age = (
            built - quote.provider_timestamp_utc
        ).total_seconds()
        receive_age = (
            built - quote.received_at_utc
        ).total_seconds()
        if provider_age < -5.0 or receive_age < -5.0:
            raise CurrentWebullStockEntryEvidenceError(
                f"Webull entry quote is ahead of build time for {ticker}"
            )
        if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockEntryEvidenceError(
                f"Webull entry quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap for {ticker}"
            )
        if receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockEntryEvidenceError(
                f"Webull entry quote receipt is stale for {ticker}"
            )

        fee = float(explicit_entry_fees_by_decision[decision_fp])
        if not math.isfinite(fee) or fee < 0.0:
            raise CurrentWebullStockEntryEvidenceError(
                f"explicit entry fee must be finite and nonnegative for {ticker}"
            )
        fill_source_fingerprint = _entry_fill_source_fingerprint(
            quote_bundle_fingerprint=quote_bundle.bundle_fingerprint,
            fee_source_id=fee_source_id,
            fee_source_fingerprint=fee_source_fingerprint,
            decision_record_fingerprint=decision_fp,
            quote=quote,
            explicit_entry_fee_dollars=fee,
        )
        fill = build_recurrent_entry_fill_evidence(
            account=account,
            record=record,
            inputs=SimulatedEntryFillInputs(
                fill_source_id=(
                    f"current-webull-stock-entry:{ticker}"
                ),
                fill_source_fingerprint=fill_source_fingerprint,
                filled_utc=quote.received_at_utc,
                fill_price_per_unit=quote.ask_price,
                explicit_entry_fees_dollars=fee,
            ),
            option_terms=None,
        )
        funding = build_recurrent_funding_terms(
            account=account,
            fill=fill,
        )
        pairs.append(
            CurrentWebullStockEntryPairV1(
                quote=quote,
                explicit_entry_fee_dollars=fee,
                fill=fill,
                funding=funding,
            )
        )

    ordered = tuple(
        sorted(
            pairs,
            key=lambda item: (
                item.fill.filled_utc,
                item.fill.fill_fingerprint,
            ),
        )
    )
    try:
        apply_recurrent_entry_batch_v1(
            account,
            tuple(
                (pair.fill, pair.funding)
                for pair in ordered
            ),
        )
    except RecurrentPositionTransitionError as exc:
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY batch funding/transition dry-run failed"
        ) from exc

    payload = _bundle_payload(
        cycle_id=reserve_bundle.cycle_id,
        cycle_fingerprint=reserve_bundle.cycle_fingerprint,
        source_recurrent_state_fingerprint=account.state.state_fingerprint,
        reserve_bundle_fingerprint=reserve_bundle.bundle_fingerprint,
        quote_bundle_fingerprint=quote_bundle.bundle_fingerprint,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        pairs=ordered,
    )
    return CurrentWebullStockEntryEvidenceBundleV1(
        contract_version=(
            CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT
        ),
        source_id=CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        cycle_id=reserve_bundle.cycle_id,
        cycle_fingerprint=reserve_bundle.cycle_fingerprint,
        source_recurrent_state_fingerprint=(
            account.state.state_fingerprint
        ),
        reserve_bundle_fingerprint=reserve_bundle.bundle_fingerprint,
        quote_bundle_fingerprint=quote_bundle.bundle_fingerprint,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        pairs=ordered,
    )


def current_webull_stock_entry_evidence_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_entry_evidence_file()


def _artifact_payload(
    bundle: CurrentWebullStockEntryEvidenceBundleV1,
) -> dict[str, object]:
    return {
        "contract_version": bundle.contract_version,
        "contract_fingerprint": bundle.contract_fingerprint,
        "source_id": bundle.source_id,
        "bundle_fingerprint": bundle.bundle_fingerprint,
        "cycle_id": bundle.cycle_id,
        "cycle_fingerprint": bundle.cycle_fingerprint,
        "source_recurrent_state_fingerprint": (
            bundle.source_recurrent_state_fingerprint
        ),
        "reserve_bundle_fingerprint": (
            bundle.reserve_bundle_fingerprint
        ),
        "quote_bundle_fingerprint": bundle.quote_bundle_fingerprint,
        "fee_source_id": bundle.fee_source_id,
        "fee_source_fingerprint": bundle.fee_source_fingerprint,
        "built_at_utc": bundle.built_at_utc.isoformat(),
        "pairs": [
            {
                "quote": _canonicalize(pair.quote),
                "explicit_entry_fee_dollars": (
                    pair.explicit_entry_fee_dollars
                ),
                "fill": _canonicalize(pair.fill),
                "funding": _canonicalize(pair.funding),
            }
            for pair in bundle.pairs
        ],
        "provider_calls_performed": bundle.provider_calls_performed,
        "broker_calls_performed": bundle.broker_calls_performed,
        "provider_read_authority": bundle.provider_read_authority,
        "provider_write_authority": bundle.provider_write_authority,
        "broker_read_authority": bundle.broker_read_authority,
        "broker_write_authority": bundle.broker_write_authority,
        "broker_fill_authority": bundle.broker_fill_authority,
        "order_creation_authority": bundle.order_creation_authority,
        "paper_authority": bundle.paper_authority,
        "live_authority": bundle.live_authority,
        "promotion_authority": bundle.promotion_authority,
        "confluence_authority": bundle.confluence_authority,
    }


def _fill_from_payload(
    payload: dict[str, object],
) -> RecurrentEntryFillEvidenceV1:
    values = dict(payload)
    values["instrument_kind"] = InstrumentKind(
        str(values["instrument_kind"])
    )
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["filled_utc"] = datetime.fromisoformat(
        str(values["filled_utc"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentEntryFillEvidenceV1(**values)


def _funding_from_payload(
    payload: dict[str, object],
) -> RecurrentFundingTermsV1:
    values = dict(payload)
    values["instrument_kind"] = InstrumentKind(
        str(values["instrument_kind"])
    )
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["funding_model"] = RecurrentFundingModel(
        str(values["funding_model"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentFundingTermsV1(**values)


def write_current_webull_stock_entry_evidence_bundle_v1(
    settings: AtlasSettings,
    bundle: CurrentWebullStockEntryEvidenceBundleV1,
) -> Path:
    path = current_webull_stock_entry_evidence_path(settings)
    raw = json.dumps(
        _artifact_payload(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_current_webull_stock_entry_evidence_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY readback verification mismatch"
        )
    return path


def read_current_webull_stock_entry_evidence_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> CurrentWebullStockEntryEvidenceBundleV1:
    target = (
        Path(path)
        if path is not None
        else current_webull_stock_entry_evidence_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY artifact root must be an object"
        )
    try:
        pairs = tuple(
            CurrentWebullStockEntryPairV1(
                quote=CurrentWebullStockQuoteV1.model_validate(
                    item["quote"]
                ),
                explicit_entry_fee_dollars=float(
                    item["explicit_entry_fee_dollars"]
                ),
                fill=_fill_from_payload(dict(item["fill"])),
                funding=_funding_from_payload(
                    dict(item["funding"])
                ),
            )
            for item in payload["pairs"]
        )
        return CurrentWebullStockEntryEvidenceBundleV1(
            contract_version=str(payload["contract_version"]),
            contract_fingerprint=str(
                payload["contract_fingerprint"]
            ),
            source_id=str(payload["source_id"]),
            bundle_fingerprint=str(
                payload["bundle_fingerprint"]
            ),
            cycle_id=str(payload["cycle_id"]),
            cycle_fingerprint=str(
                payload["cycle_fingerprint"]
            ),
            source_recurrent_state_fingerprint=str(
                payload["source_recurrent_state_fingerprint"]
            ),
            reserve_bundle_fingerprint=str(
                payload["reserve_bundle_fingerprint"]
            ),
            quote_bundle_fingerprint=str(
                payload["quote_bundle_fingerprint"]
            ),
            fee_source_id=str(payload["fee_source_id"]),
            fee_source_fingerprint=str(
                payload["fee_source_fingerprint"]
            ),
            built_at_utc=datetime.fromisoformat(
                str(payload["built_at_utc"])
            ),
            pairs=pairs,
            provider_calls_performed=int(
                payload["provider_calls_performed"]
            ),
            broker_calls_performed=int(
                payload["broker_calls_performed"]
            ),
            provider_read_authority=bool(
                payload["provider_read_authority"]
            ),
            provider_write_authority=bool(
                payload["provider_write_authority"]
            ),
            broker_read_authority=bool(
                payload["broker_read_authority"]
            ),
            broker_write_authority=bool(
                payload["broker_write_authority"]
            ),
            broker_fill_authority=bool(
                payload["broker_fill_authority"]
            ),
            order_creation_authority=bool(
                payload["order_creation_authority"]
            ),
            paper_authority=bool(payload["paper_authority"]),
            live_authority=bool(payload["live_authority"]),
            promotion_authority=bool(
                payload["promotion_authority"]
            ),
            confluence_authority=bool(
                payload["confluence_authority"]
            ),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        CurrentWebullStockEntryEvidenceError,
    ) as exc:
        if isinstance(exc, CurrentWebullStockEntryEvidenceError):
            raise
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY artifact failed typed validation"
        ) from exc


def apply_current_webull_stock_entry_evidence_bundle_v1(
    *,
    runner: RecurrentCycleRunnerV1,
    identity: RecurrentCycleRunIdentityV1,
    bundle: CurrentWebullStockEntryEvidenceBundleV1,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    if (
        bundle.cycle_id != identity.cycle_id
        or bundle.cycle_fingerprint
        != identity.cycle_fingerprint
    ):
        raise CurrentWebullStockEntryEvidenceError(
            "current Webull ENTRY bundle is bound to a different cycle"
        )
    return runner.apply_entry(
        identity=identity,
        evidence_source_id=bundle.source_id,
        evidence_source_fingerprint=bundle.bundle_fingerprint,
        entries=bundle.runner_entries,
        now_utc=now_utc,
    )


__all__ = [
    "CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT",
    "CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_VERSION",
    "CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_SOURCE_ID",
    "CurrentWebullStockEntryEvidenceBundleV1",
    "CurrentWebullStockEntryEvidenceError",
    "CurrentWebullStockEntryPairV1",
    "apply_current_webull_stock_entry_evidence_bundle_v1",
    "build_current_webull_stock_entry_evidence_bundle_v1",
    "current_webull_stock_entry_evidence_path",
    "read_current_webull_stock_entry_evidence_bundle_v1",
    "write_current_webull_stock_entry_evidence_bundle_v1",
]
