from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Mapping

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
from packages.execution.current_webull_stock_close_contract import (
    CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT,
    CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
)
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.recurrent_close_position import (
    RecurrentClosePositionError,
    apply_recurrent_close_position_batch_v1,
)
from packages.simulation.recurrent_cycle import RecurrentCycleReceiptV1
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunIdentityV1,
    RecurrentCycleRunnerV1,
)
from packages.simulation.recurrent_exit_fill import (
    RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT,
    RecurrentExitFillEvidenceV1,
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_exit_plan import (
    RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentStockExitPlanBundleV1,
    RecurrentStockExitPlanV1,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    recurrent_lifecycle_account_state_fingerprint,
)


CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION = str(
    CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT["contract_id"]
)
CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_SOURCE_ID = (
    "atlas-current-webull-stock-close/current.json"
)
_MAX_BUNDLE_BYTES = 64 * 1024 * 1024


class CurrentWebullStockCloseEvidenceError(RuntimeError):
    pass


class StockExitTriggerDisposition(StrEnum):
    NO_TRIGGER = "NO_TRIGGER"
    STOP = "STOP"
    TARGET = "TARGET"


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentWebullStockCloseEvidenceError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CurrentWebullStockCloseEvidenceError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-12,
        abs_tol=1e-9,
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


def _fill_source_fingerprint(
    *,
    quote_bundle_fingerprint: str,
    fee_source_id: str,
    fee_source_fingerprint: str,
    plan: RecurrentStockExitPlanV1,
    quote: CurrentWebullStockQuoteV1,
    disposition: StockExitTriggerDisposition,
    explicit_exit_fee_dollars: float,
) -> str:
    return _fingerprint_payload(
        {
            "contract_fingerprint": (
                CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
            ),
            "quote_bundle_fingerprint": quote_bundle_fingerprint,
            "fee_source_id": fee_source_id,
            "fee_source_fingerprint": fee_source_fingerprint,
            "plan_fingerprint": plan.plan_fingerprint,
            "quote": quote,
            "disposition": disposition,
            "explicit_exit_fee_dollars": explicit_exit_fee_dollars,
        }
    )


@dataclass(frozen=True)
class CurrentWebullStockCloseTriggerV1:
    plan: RecurrentStockExitPlanV1
    quote: CurrentWebullStockQuoteV1
    disposition: StockExitTriggerDisposition
    explicit_exit_fee_dollars: float | None
    fill: RecurrentExitFillEvidenceV1 | None

    time_exit_evaluated: bool = False
    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False

    def __post_init__(self) -> None:
        if self.plan.contract_fingerprint != (
            RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullStockCloseEvidenceError(
                "close trigger exit-plan contract fingerprint mismatch"
            )
        if self.quote.symbol != self.plan.ticker:
            raise CurrentWebullStockCloseEvidenceError(
                "close trigger quote/plan ticker mismatch"
            )
        if self.quote.session_segment != SessionSegment.REGULAR:
            raise CurrentWebullStockCloseEvidenceError(
                "close trigger quote must be regular-session"
            )
        bid = self.quote.bid_price
        if self.disposition == StockExitTriggerDisposition.NO_TRIGGER:
            if not (
                self.plan.stop_price_per_unit
                < bid
                < self.plan.target_price_per_unit
            ):
                raise CurrentWebullStockCloseEvidenceError(
                    "NO_TRIGGER bid must remain strictly between stop and target"
                )
            if self.explicit_exit_fee_dollars is not None or self.fill is not None:
                raise CurrentWebullStockCloseEvidenceError(
                    "NO_TRIGGER cannot carry fee or exit fill"
                )
        else:
            if self.explicit_exit_fee_dollars is None:
                raise CurrentWebullStockCloseEvidenceError(
                    "triggered close requires explicit exit fee"
                )
            if (
                not math.isfinite(self.explicit_exit_fee_dollars)
                or self.explicit_exit_fee_dollars < 0.0
            ):
                raise CurrentWebullStockCloseEvidenceError(
                    "triggered exit fee must be finite and nonnegative"
                )
            if self.fill is None:
                raise CurrentWebullStockCloseEvidenceError(
                    "triggered close requires recurrent exit-fill evidence"
                )
            if (
                self.fill.contract_fingerprint
                != RECURRENT_EXIT_FILL_CONTRACT_FINGERPRINT
            ):
                raise CurrentWebullStockCloseEvidenceError(
                    "triggered close fill contract fingerprint mismatch"
                )
            if self.disposition == StockExitTriggerDisposition.STOP:
                if bid > self.plan.stop_price_per_unit:
                    raise CurrentWebullStockCloseEvidenceError(
                        "STOP trigger requires bid at or below stop"
                    )
            elif self.disposition == StockExitTriggerDisposition.TARGET:
                if bid < self.plan.target_price_per_unit:
                    raise CurrentWebullStockCloseEvidenceError(
                        "TARGET trigger requires bid at or above target"
                    )
            else:
                raise CurrentWebullStockCloseEvidenceError(
                    "unsupported stock exit trigger disposition"
                )
            fill = self.fill
            if fill.position_fingerprint != self.plan.position_fingerprint:
                raise CurrentWebullStockCloseEvidenceError(
                    "close fill position does not match exit plan"
                )
            if fill.ticker != self.quote.symbol:
                raise CurrentWebullStockCloseEvidenceError(
                    "close fill ticker does not match quote"
                )
            if fill.exited_utc != self.quote.received_at_utc:
                raise CurrentWebullStockCloseEvidenceError(
                    "close fill timestamp must equal quote receipt"
                )
            if not _same(fill.exit_price_per_unit, bid):
                raise CurrentWebullStockCloseEvidenceError(
                    "long-stock exit fill price must equal executable bid"
                )
            if not _same(
                fill.exit_fees_dollars,
                self.explicit_exit_fee_dollars,
            ):
                raise CurrentWebullStockCloseEvidenceError(
                    "close fill fee does not match explicit fee evidence"
                )
        if (
            self.time_exit_evaluated
            or self.provider_calls_performed
            or self.broker_calls_performed
            or self.broker_fill_authority
            or self.order_creation_authority
            or self.paper_authority
            or self.live_authority
        ):
            raise CurrentWebullStockCloseEvidenceError(
                "close trigger record cannot claim time exit, network, broker-fill, order, or trading authority"
            )

    @property
    def trigger_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _bundle_payload(
    *,
    cycle_id: str,
    cycle_fingerprint: str,
    source_recurrent_state_fingerprint: str,
    exit_plan_bundle_fingerprint: str,
    quote_bundle_fingerprint: str,
    fee_source_id: str,
    fee_source_fingerprint: str,
    built_at_utc: datetime,
    triggers: tuple[CurrentWebullStockCloseTriggerV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ),
        "source_id": CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_SOURCE_ID,
        "cycle_id": cycle_id,
        "cycle_fingerprint": cycle_fingerprint,
        "source_recurrent_state_fingerprint": (
            source_recurrent_state_fingerprint
        ),
        "exit_plan_bundle_fingerprint": exit_plan_bundle_fingerprint,
        "quote_bundle_fingerprint": quote_bundle_fingerprint,
        "fee_source_id": fee_source_id,
        "fee_source_fingerprint": fee_source_fingerprint,
        "built_at_utc": built_at_utc,
        "triggers": triggers,
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
class CurrentWebullStockCloseEvidenceBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    cycle_id: str
    cycle_fingerprint: str
    source_recurrent_state_fingerprint: str
    exit_plan_bundle_fingerprint: str
    quote_bundle_fingerprint: str
    fee_source_id: str
    fee_source_fingerprint: str
    built_at_utc: datetime
    triggers: tuple[CurrentWebullStockCloseTriggerV1, ...]

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
            != CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION
        ):
            raise CurrentWebullStockCloseEvidenceError(
                "current Webull CLOSE contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullStockCloseEvidenceError(
                "current Webull CLOSE contract fingerprint mismatch"
            )
        if self.source_id != CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_SOURCE_ID:
            raise CurrentWebullStockCloseEvidenceError(
                "current Webull CLOSE source id mismatch"
            )
        for label, value in (
            ("bundle", self.bundle_fingerprint),
            ("cycle", self.cycle_fingerprint),
            (
                "source recurrent state",
                self.source_recurrent_state_fingerprint,
            ),
            (
                "exit-plan bundle",
                self.exit_plan_bundle_fingerprint,
            ),
            ("quote bundle", self.quote_bundle_fingerprint),
            ("fee source", self.fee_source_fingerprint),
        ):
            _require_sha(value, label=label)
        if not self.fee_source_id.strip():
            raise CurrentWebullStockCloseEvidenceError(
                "current Webull CLOSE fee source id cannot be blank"
            )
        built = _require_aware(
            self.built_at_utc,
            label="current Webull CLOSE build time",
        )
        ordered = tuple(
            sorted(
                self.triggers,
                key=lambda item: item.plan.position_fingerprint,
            )
        )
        if ordered != self.triggers:
            raise CurrentWebullStockCloseEvidenceError(
                "CLOSE triggers must be ordered by position fingerprint"
            )
        ids = tuple(
            item.plan.position_fingerprint
            for item in self.triggers
        )
        if len(ids) != len(set(ids)):
            raise CurrentWebullStockCloseEvidenceError(
                "CLOSE bundle cannot duplicate positions"
            )
        for trigger in self.triggers:
            if trigger.quote.received_at_utc > built:
                raise CurrentWebullStockCloseEvidenceError(
                    "CLOSE trigger quote cannot postdate bundle build"
                )
            if trigger.fill is not None:
                expected_source = _fill_source_fingerprint(
                    quote_bundle_fingerprint=(
                        self.quote_bundle_fingerprint
                    ),
                    fee_source_id=self.fee_source_id,
                    fee_source_fingerprint=(
                        self.fee_source_fingerprint
                    ),
                    plan=trigger.plan,
                    quote=trigger.quote,
                    disposition=trigger.disposition,
                    explicit_exit_fee_dollars=(
                        trigger.explicit_exit_fee_dollars or 0.0
                    ),
                )
                if (
                    trigger.fill.fill_source_fingerprint
                    != expected_source
                ):
                    raise CurrentWebullStockCloseEvidenceError(
                        "CLOSE fill source fingerprint mismatch"
                    )
        if any(
            (
                self.provider_calls_performed,
                self.broker_calls_performed,
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
            raise CurrentWebullStockCloseEvidenceError(
                "CLOSE evidence bundle cannot grant external or trading authority"
            )
        expected = _fingerprint_payload(
            _bundle_payload(
                cycle_id=self.cycle_id,
                cycle_fingerprint=self.cycle_fingerprint,
                source_recurrent_state_fingerprint=(
                    self.source_recurrent_state_fingerprint
                ),
                exit_plan_bundle_fingerprint=(
                    self.exit_plan_bundle_fingerprint
                ),
                quote_bundle_fingerprint=(
                    self.quote_bundle_fingerprint
                ),
                fee_source_id=self.fee_source_id,
                fee_source_fingerprint=self.fee_source_fingerprint,
                built_at_utc=built,
                triggers=self.triggers,
            )
        )
        if self.bundle_fingerprint != expected:
            raise CurrentWebullStockCloseEvidenceError(
                "CLOSE evidence bundle self-fingerprint mismatch"
            )

    @property
    def triggered_fills(self) -> tuple[RecurrentExitFillEvidenceV1, ...]:
        return tuple(
            trigger.fill
            for trigger in self.triggers
            if trigger.fill is not None
        )


def build_current_webull_stock_close_evidence_bundle_v1(
    *,
    account: RecurrentLifecycleAccountV1,
    identity: RecurrentCycleRunIdentityV1,
    exit_plan_bundle: RecurrentStockExitPlanBundleV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1,
    explicit_exit_fees_by_position: Mapping[str, float],
    fee_source_id: str,
    fee_source_fingerprint: str,
    built_at_utc: datetime | None = None,
) -> CurrentWebullStockCloseEvidenceBundleV1:
    state = account.state
    if (
        state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockCloseEvidenceError(
            "source recurrent account contract fingerprint mismatch"
        )
    if (
        state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(state)
    ):
        raise CurrentWebullStockCloseEvidenceError(
            "source recurrent state fingerprint mismatch"
        )
    if (
        exit_plan_bundle.contract_fingerprint
        != RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockCloseEvidenceError(
            "exit-plan bundle contract fingerprint mismatch"
        )
    if (
        quote_bundle.contract_fingerprint
        != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
    ):
        raise CurrentWebullStockCloseEvidenceError(
            "quote bundle contract fingerprint mismatch"
        )
    if not fee_source_id.strip():
        raise CurrentWebullStockCloseEvidenceError(
            "explicit exit fee source id cannot be blank"
        )
    _require_sha(
        fee_source_fingerprint,
        label="explicit exit fee source",
    )
    built = _require_aware(
        built_at_utc or datetime.now(UTC),
        label="current Webull CLOSE build time",
    )
    if built < state.as_of_utc:
        raise CurrentWebullStockCloseEvidenceError(
            "CLOSE evidence cannot predate recurrent state"
        )
    positions = tuple(state.open_positions)
    if any(
        position.instrument_kind != InstrumentKind.STOCK
        for position in positions
    ):
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE v1 cannot evaluate option positions"
        )
    if any(
        position.direction != DiscoveryDirection.BULLISH
        for position in positions
    ):
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE v1 supports bullish stock longs only"
        )
    positions_by_fp = {
        position.position_fingerprint: position
        for position in positions
    }
    plans_by_fp = {
        plan.position_fingerprint: plan
        for plan in exit_plan_bundle.plans
    }
    if set(positions_by_fp) != set(plans_by_fp):
        missing = sorted(set(positions_by_fp) - set(plans_by_fp))
        extra = sorted(set(plans_by_fp) - set(positions_by_fp))
        raise CurrentWebullStockCloseEvidenceError(
            "exit-plan coverage must exactly match current open positions; "
            f"missing={missing}, extra={extra}"
        )
    current_tickers = tuple(
        sorted({position.ticker for position in positions})
    )
    if quote_bundle.requested_symbols != current_tickers:
        raise CurrentWebullStockCloseEvidenceError(
            "Webull quote bundle symbols must exactly match current open-stock tickers"
        )
    quotes = {quote.symbol: quote for quote in quote_bundle.quotes}

    preliminary: list[
        tuple[
            RecurrentStockExitPlanV1,
            CurrentWebullStockQuoteV1,
            StockExitTriggerDisposition,
        ]
    ] = []
    for position_fp in sorted(positions_by_fp):
        position = positions_by_fp[position_fp]
        plan = plans_by_fp[position_fp]
        if (
            plan.instrument_id != position.instrument_id
            or plan.ticker != position.ticker
            or plan.direction != position.direction
            or plan.decision_record_fingerprint
            != position.decision_record_fingerprint
            or plan.entry_fill_fingerprint != position.fill_fingerprint
            or plan.funding_terms_fingerprint
            != position.funding_terms_fingerprint
            or not _same(
                plan.actual_entry_price_per_unit,
                position.entry_price_per_unit,
            )
        ):
            raise CurrentWebullStockCloseEvidenceError(
                "exit plan no longer matches current recurrent position"
            )
        quote = quotes.get(position.ticker)
        if quote is None:
            raise CurrentWebullStockCloseEvidenceError(
                f"missing exact-case Webull quote for {position.ticker}"
            )
        if quote.session_segment != SessionSegment.REGULAR:
            raise CurrentWebullStockCloseEvidenceError(
                f"Webull CLOSE quote is outside regular session for {position.ticker}"
            )
        if quote.received_at_utc < state.as_of_utc:
            raise CurrentWebullStockCloseEvidenceError(
                f"Webull CLOSE quote predates recurrent state for {position.ticker}"
            )
        provider_age = (
            built - quote.provider_timestamp_utc
        ).total_seconds()
        receive_age = (
            built - quote.received_at_utc
        ).total_seconds()
        if provider_age < -5.0 or receive_age < -5.0:
            raise CurrentWebullStockCloseEvidenceError(
                f"Webull CLOSE quote is ahead of build time for {position.ticker}"
            )
        if provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockCloseEvidenceError(
                f"Webull CLOSE quote exceeds {PHASE15_MAX_QUOTE_AGE_SECONDS}s execution age cap for {position.ticker}"
            )
        if receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS:
            raise CurrentWebullStockCloseEvidenceError(
                f"Webull CLOSE quote receipt is stale for {position.ticker}"
            )
        bid = quote.bid_price
        if bid <= plan.stop_price_per_unit:
            disposition = StockExitTriggerDisposition.STOP
        elif bid >= plan.target_price_per_unit:
            disposition = StockExitTriggerDisposition.TARGET
        else:
            disposition = StockExitTriggerDisposition.NO_TRIGGER
        preliminary.append((plan, quote, disposition))

    triggered_position_fps = {
        plan.position_fingerprint
        for plan, _quote, disposition in preliminary
        if disposition != StockExitTriggerDisposition.NO_TRIGGER
    }
    supplied_fee_keys = set(explicit_exit_fees_by_position)
    if supplied_fee_keys != triggered_position_fps:
        missing = sorted(triggered_position_fps - supplied_fee_keys)
        extra = sorted(supplied_fee_keys - triggered_position_fps)
        raise CurrentWebullStockCloseEvidenceError(
            "explicit exit fee coverage must exactly match triggered positions; "
            f"missing={missing}, extra={extra}"
        )

    triggers: list[CurrentWebullStockCloseTriggerV1] = []
    for plan, quote, disposition in preliminary:
        if disposition == StockExitTriggerDisposition.NO_TRIGGER:
            triggers.append(
                CurrentWebullStockCloseTriggerV1(
                    plan=plan,
                    quote=quote,
                    disposition=disposition,
                    explicit_exit_fee_dollars=None,
                    fill=None,
                )
            )
            continue
        fee = float(
            explicit_exit_fees_by_position[
                plan.position_fingerprint
            ]
        )
        if not math.isfinite(fee) or fee < 0.0:
            raise CurrentWebullStockCloseEvidenceError(
                f"explicit exit fee must be finite and nonnegative for {plan.ticker}"
            )
        source_fp = _fill_source_fingerprint(
            quote_bundle_fingerprint=quote_bundle.bundle_fingerprint,
            fee_source_id=fee_source_id,
            fee_source_fingerprint=fee_source_fingerprint,
            plan=plan,
            quote=quote,
            disposition=disposition,
            explicit_exit_fee_dollars=fee,
        )
        fill = build_recurrent_exit_fill_evidence(
            source_state=state,
            position_fingerprint=plan.position_fingerprint,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id=(
                    f"current-webull-stock-close:{plan.ticker}:{disposition.value}"
                ),
                fill_source_fingerprint=source_fp,
                exited_utc=quote.received_at_utc,
                exit_price_per_unit=quote.bid_price,
                explicit_exit_fees_dollars=fee,
            ),
        )
        triggers.append(
            CurrentWebullStockCloseTriggerV1(
                plan=plan,
                quote=quote,
                disposition=disposition,
                explicit_exit_fee_dollars=fee,
                fill=fill,
            )
        )

    ordered = tuple(
        sorted(
            triggers,
            key=lambda item: item.plan.position_fingerprint,
        )
    )
    fills = tuple(
        trigger.fill
        for trigger in ordered
        if trigger.fill is not None
    )
    try:
        apply_recurrent_close_position_batch_v1(
            account,
            fills,
        )
    except RecurrentClosePositionError as exc:
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE batch dry-run failed"
        ) from exc

    payload = _bundle_payload(
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        source_recurrent_state_fingerprint=state.state_fingerprint,
        exit_plan_bundle_fingerprint=(
            exit_plan_bundle.bundle_fingerprint
        ),
        quote_bundle_fingerprint=quote_bundle.bundle_fingerprint,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        triggers=ordered,
    )
    return CurrentWebullStockCloseEvidenceBundleV1(
        contract_version=(
            CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ),
        source_id=CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        source_recurrent_state_fingerprint=state.state_fingerprint,
        exit_plan_bundle_fingerprint=(
            exit_plan_bundle.bundle_fingerprint
        ),
        quote_bundle_fingerprint=quote_bundle.bundle_fingerprint,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        triggers=ordered,
    )


def current_webull_stock_close_evidence_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(settings).recurrent_close_evidence_file()


def _artifact_payload(
    bundle: CurrentWebullStockCloseEvidenceBundleV1,
) -> dict[str, object]:
    return _canonicalize(bundle)


def _plan_from_payload(payload: dict[str, object]) -> RecurrentStockExitPlanV1:
    from packages.simulation.recurrent_exit_plan import _plan_from_payload as decode

    return decode(payload)


def _fill_from_payload(
    payload: dict[str, object],
) -> RecurrentExitFillEvidenceV1:
    values = dict(payload)
    values["instrument_kind"] = InstrumentKind(
        str(values["instrument_kind"])
    )
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["opened_utc"] = datetime.fromisoformat(
        str(values["opened_utc"])
    )
    values["exited_utc"] = datetime.fromisoformat(
        str(values["exited_utc"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentExitFillEvidenceV1(**values)


def write_current_webull_stock_close_evidence_bundle_v1(
    settings: AtlasSettings,
    bundle: CurrentWebullStockCloseEvidenceBundleV1,
) -> Path:
    path = current_webull_stock_close_evidence_path(settings)
    raw = json.dumps(
        _artifact_payload(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_current_webull_stock_close_evidence_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE readback verification mismatch"
        )
    return path


def read_current_webull_stock_close_evidence_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> CurrentWebullStockCloseEvidenceBundleV1:
    target = (
        Path(path)
        if path is not None
        else current_webull_stock_close_evidence_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE artifact is invalid JSON"
        ) from exc
    try:
        triggers = tuple(
            CurrentWebullStockCloseTriggerV1(
                plan=_plan_from_payload(dict(item["plan"])),
                quote=CurrentWebullStockQuoteV1.model_validate(
                    item["quote"]
                ),
                disposition=StockExitTriggerDisposition(
                    str(item["disposition"])
                ),
                explicit_exit_fee_dollars=(
                    None
                    if item.get("explicit_exit_fee_dollars") is None
                    else float(item["explicit_exit_fee_dollars"])
                ),
                fill=(
                    None
                    if item.get("fill") is None
                    else _fill_from_payload(dict(item["fill"]))
                ),
                time_exit_evaluated=bool(
                    item["time_exit_evaluated"]
                ),
                provider_calls_performed=int(
                    item["provider_calls_performed"]
                ),
                broker_calls_performed=int(
                    item["broker_calls_performed"]
                ),
                broker_fill_authority=bool(
                    item["broker_fill_authority"]
                ),
                order_creation_authority=bool(
                    item["order_creation_authority"]
                ),
                paper_authority=bool(item["paper_authority"]),
                live_authority=bool(item["live_authority"]),
            )
            for item in payload["triggers"]
        )
        return CurrentWebullStockCloseEvidenceBundleV1(
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
            exit_plan_bundle_fingerprint=str(
                payload["exit_plan_bundle_fingerprint"]
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
            triggers=triggers,
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
        CurrentWebullStockCloseEvidenceError,
    ) as exc:
        if isinstance(exc, CurrentWebullStockCloseEvidenceError):
            raise
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE artifact failed typed validation"
        ) from exc


def apply_current_webull_stock_close_evidence_bundle_v1(
    *,
    runner: RecurrentCycleRunnerV1,
    identity: RecurrentCycleRunIdentityV1,
    bundle: CurrentWebullStockCloseEvidenceBundleV1,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    if (
        bundle.cycle_id != identity.cycle_id
        or bundle.cycle_fingerprint
        != identity.cycle_fingerprint
    ):
        raise CurrentWebullStockCloseEvidenceError(
            "current Webull CLOSE bundle is bound to a different cycle"
        )
    return runner.apply_close(
        identity=identity,
        evidence_source_id=bundle.source_id,
        evidence_source_fingerprint=bundle.bundle_fingerprint,
        fills=bundle.triggered_fills,
        now_utc=now_utc,
    )


__all__ = [
    "CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT",
    "CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_CONTRACT_VERSION",
    "CURRENT_WEBULL_STOCK_CLOSE_EVIDENCE_SOURCE_ID",
    "CurrentWebullStockCloseEvidenceBundleV1",
    "CurrentWebullStockCloseEvidenceError",
    "CurrentWebullStockCloseTriggerV1",
    "StockExitTriggerDisposition",
    "apply_current_webull_stock_close_evidence_bundle_v1",
    "build_current_webull_stock_close_evidence_bundle_v1",
    "current_webull_stock_close_evidence_path",
    "read_current_webull_stock_close_evidence_bundle_v1",
    "write_current_webull_stock_close_evidence_bundle_v1",
]
