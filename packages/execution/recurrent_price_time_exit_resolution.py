from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

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
from packages.execution.phase15_policy import PHASE15_MAX_QUOTE_AGE_SECONDS
from packages.execution.recurrent_price_time_exit_resolution_contract import (
    RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT,
    RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.recurrent_time_expiry_disposition import (
    RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT,
    RecurrentTimeExpiryDispositionBundleV1,
    TimeExpiryDisposition,
    recurrent_time_expiry_disposition_bundle_from_payload,
)


RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_VERSION = str(
    RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT["contract_id"]
)
RECURRENT_PRICE_TIME_EXIT_RESOLUTION_SOURCE_ID = (
    "atlas-recurrent-price-time-exit-resolution/current.json"
)
_MAX_BUNDLE_BYTES = 128 * 1024 * 1024


class RecurrentPriceTimeExitResolutionError(RuntimeError):
    pass


class PriceTriggerCondition(StrEnum):
    NO_PRICE_TRIGGER = "NO_PRICE_TRIGGER"
    STOP = "STOP"
    TARGET = "TARGET"


class ExitReason(StrEnum):
    STOP = "STOP"
    TARGET = "TARGET"
    TIME = "TIME"


class SelectedExitDisposition(StrEnum):
    HOLD = "HOLD"
    STOP = "STOP"
    TARGET = "TARGET"
    TIME = "TIME"


class ExitTriggerPrecedenceMode(StrEnum):
    PRICE_THEN_TIME = "PRICE_THEN_TIME"
    TIME_THEN_PRICE = "TIME_THEN_PRICE"


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentPriceTimeExitResolutionError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentPriceTimeExitResolutionError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
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
class ExitTriggerPrecedencePolicyV1:
    policy_id: str
    mode: ExitTriggerPrecedenceMode

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise RecurrentPriceTimeExitResolutionError(
                "exit-trigger precedence policy id cannot be blank"
            )

    @property
    def policy_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _price_condition(
    *,
    bid_price: float,
    stop_price: float,
    target_price: float,
) -> PriceTriggerCondition:
    if bid_price <= stop_price:
        return PriceTriggerCondition.STOP
    if bid_price >= target_price:
        return PriceTriggerCondition.TARGET
    return PriceTriggerCondition.NO_PRICE_TRIGGER


def _selected_disposition(
    *,
    price_condition: PriceTriggerCondition,
    time_exit_executable: bool,
    policy: ExitTriggerPrecedencePolicyV1,
) -> tuple[tuple[ExitReason, ...], SelectedExitDisposition]:
    reasons: list[ExitReason] = []
    if price_condition == PriceTriggerCondition.STOP:
        reasons.append(ExitReason.STOP)
    elif price_condition == PriceTriggerCondition.TARGET:
        reasons.append(ExitReason.TARGET)
    if time_exit_executable:
        reasons.append(ExitReason.TIME)

    if not reasons:
        return (), SelectedExitDisposition.HOLD
    if len(reasons) == 1:
        reason = reasons[0]
        return tuple(reasons), SelectedExitDisposition(reason.value)

    price_reason = (
        ExitReason.STOP
        if price_condition == PriceTriggerCondition.STOP
        else ExitReason.TARGET
    )
    if policy.mode == ExitTriggerPrecedenceMode.PRICE_THEN_TIME:
        selected = SelectedExitDisposition(price_reason.value)
    elif policy.mode == ExitTriggerPrecedenceMode.TIME_THEN_PRICE:
        selected = SelectedExitDisposition.TIME
    else:
        raise RecurrentPriceTimeExitResolutionError(
            "unsupported exit-trigger precedence mode"
        )
    return tuple(reasons), selected


@dataclass(frozen=True)
class RecurrentPriceTimeExitResolutionV1:
    position_fingerprint: str
    ticker: str
    direction: DiscoveryDirection
    quote: CurrentWebullStockQuoteV1
    time_disposition_fingerprint: str
    deadline_utc: datetime
    time_disposition: TimeExpiryDisposition
    price_condition: PriceTriggerCondition
    time_exit_executable: bool
    true_exit_reasons: tuple[ExitReason, ...]
    selected_disposition: SelectedExitDisposition
    precedence_policy_fingerprint: str

    fee_evidence_consumed: bool = False
    close_fill_authority: bool = False
    account_mutation_authority: bool = False
    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    provider_write_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False
    reason_codes: tuple[str, ...] = (
        "CURRENT_EXECUTABLE_BID_CLASSIFIED_AGAINST_ACCEPTED_PLAN",
        "TIME_REASON_REQUIRES_QUOTE_AT_OR_AFTER_IMMUTABLE_DEADLINE",
        "ALL_TRUE_EXIT_REASONS_RETAINED",
        "NO_FILL_OR_TRADING_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        _require_sha(
            self.position_fingerprint,
            label="exit-resolution position",
        )
        _require_sha(
            self.time_disposition_fingerprint,
            label="exit-resolution time disposition",
        )
        _require_sha(
            self.precedence_policy_fingerprint,
            label="exit-resolution precedence policy",
        )
        if not self.ticker.strip():
            raise RecurrentPriceTimeExitResolutionError(
                "exit-resolution ticker cannot be blank"
            )
        if self.direction != DiscoveryDirection.BULLISH:
            raise RecurrentPriceTimeExitResolutionError(
                "price/time exit resolution v1 supports bullish stock longs only"
            )
        if self.quote.symbol != self.ticker:
            raise RecurrentPriceTimeExitResolutionError(
                "exit-resolution quote/ticker mismatch"
            )
        if self.quote.session_segment != SessionSegment.REGULAR:
            raise RecurrentPriceTimeExitResolutionError(
                "exit-resolution quote must be regular-session"
            )
        deadline = _require_aware(
            self.deadline_utc,
            label="exit-resolution deadline",
        )
        expected_time_executable = (
            self.time_disposition == TimeExpiryDisposition.TIME_EXPIRED
            and self.quote.received_at_utc >= deadline
        )
        if self.time_exit_executable != expected_time_executable:
            raise RecurrentPriceTimeExitResolutionError(
                "time-exit executability does not match expiry/quote chronology"
            )
        if any(
            (
                self.fee_evidence_consumed,
                self.close_fill_authority,
                self.account_mutation_authority,
                self.provider_calls_performed,
                self.broker_calls_performed,
                self.provider_write_authority,
                self.broker_write_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentPriceTimeExitResolutionError(
                "exit resolution cannot grant fee, fill, mutation, external-write, or trading authority"
            )
        if not self.reason_codes:
            raise RecurrentPriceTimeExitResolutionError(
                "exit resolution requires reason codes"
            )

    @property
    def resolution_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _bundle_payload(
    *,
    expiry_bundle: RecurrentTimeExpiryDispositionBundleV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None,
    precedence_policy: ExitTriggerPrecedencePolicyV1,
    resolutions: tuple[RecurrentPriceTimeExitResolutionV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT
        ),
        "source_id": RECURRENT_PRICE_TIME_EXIT_RESOLUTION_SOURCE_ID,
        "expiry_bundle": expiry_bundle,
        "quote_bundle": quote_bundle,
        "precedence_policy": precedence_policy,
        "precedence_policy_fingerprint": (
            precedence_policy.policy_fingerprint
        ),
        "resolutions": resolutions,
        "fee_evidence_consumed": False,
        "close_fill_authority": False,
        "account_mutation_authority": False,
        "provider_calls_performed": 0,
        "broker_calls_performed": 0,
        "provider_write_authority": False,
        "broker_write_authority": False,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class RecurrentPriceTimeExitResolutionBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    expiry_bundle: RecurrentTimeExpiryDispositionBundleV1
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None
    precedence_policy: ExitTriggerPrecedencePolicyV1
    precedence_policy_fingerprint: str
    resolutions: tuple[RecurrentPriceTimeExitResolutionV1, ...]

    fee_evidence_consumed: bool = False
    close_fill_authority: bool = False
    account_mutation_authority: bool = False
    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    provider_write_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_VERSION
        ):
            raise RecurrentPriceTimeExitResolutionError(
                "price/time exit-resolution contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT
        ):
            raise RecurrentPriceTimeExitResolutionError(
                "price/time exit-resolution contract fingerprint mismatch"
            )
        if self.source_id != RECURRENT_PRICE_TIME_EXIT_RESOLUTION_SOURCE_ID:
            raise RecurrentPriceTimeExitResolutionError(
                "price/time exit-resolution source id mismatch"
            )
        _require_sha(
            self.bundle_fingerprint,
            label="price/time exit-resolution bundle",
        )
        if (
            self.expiry_bundle.contract_fingerprint
            != RECURRENT_TIME_EXPIRY_DISPOSITION_BUNDLE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentPriceTimeExitResolutionError(
                "price/time resolution expiry-bundle contract mismatch"
            )
        if (
            self.precedence_policy.policy_fingerprint
            != self.precedence_policy_fingerprint
        ):
            raise RecurrentPriceTimeExitResolutionError(
                "price/time precedence policy fingerprint mismatch"
            )

        ordered = tuple(
            sorted(
                self.resolutions,
                key=lambda item: item.position_fingerprint,
            )
        )
        if ordered != self.resolutions:
            raise RecurrentPriceTimeExitResolutionError(
                "price/time resolutions must be ordered by position fingerprint"
            )

        time_items = self.expiry_bundle.dispositions
        if not time_items:
            if self.quote_bundle is not None or self.resolutions:
                raise RecurrentPriceTimeExitResolutionError(
                    "empty exit-resolution bundle must be provider-inert"
                )
        else:
            if self.quote_bundle is None:
                raise RecurrentPriceTimeExitResolutionError(
                    "open exit resolutions require current quote evidence"
                )
            if (
                self.quote_bundle.contract_fingerprint
                != CURRENT_WEBULL_STOCK_QUOTE_BUNDLE_CONTRACT_FINGERPRINT
            ):
                raise RecurrentPriceTimeExitResolutionError(
                    "price/time quote-bundle contract mismatch"
                )
            evaluation = self.expiry_bundle.evaluation_utc
            if self.quote_bundle.captured_at_utc > evaluation:
                raise RecurrentPriceTimeExitResolutionError(
                    "quote-bundle capture cannot postdate expiry evaluation"
                )

            expected_symbols = tuple(
                sorted(
                    {
                        item.clock.ticker
                        for item in time_items
                    }
                )
            )
            if self.quote_bundle.requested_symbols != expected_symbols:
                raise RecurrentPriceTimeExitResolutionError(
                    "quote-bundle symbols must exactly match clock coverage"
                )
            quotes = {
                quote.symbol: quote
                for quote in self.quote_bundle.quotes
            }
            by_position = {
                item.position_fingerprint: item
                for item in self.resolutions
            }
            expected_positions = {
                item.clock.position_fingerprint
                for item in time_items
            }
            if set(by_position) != expected_positions:
                raise RecurrentPriceTimeExitResolutionError(
                    "price/time resolutions must exactly cover expiry positions"
                )

            for time_item in time_items:
                clock = time_item.clock
                plan = next(
                    plan
                    for plan in self.expiry_bundle.clock_book.exit_plan_book.plans
                    if plan.position_fingerprint == clock.position_fingerprint
                )
                resolution = by_position[clock.position_fingerprint]
                quote = quotes.get(clock.ticker)
                if quote is None or resolution.quote != quote:
                    raise RecurrentPriceTimeExitResolutionError(
                        "resolution quote does not match retained quote bundle"
                    )
                if (
                    resolution.time_disposition_fingerprint
                    != time_item.disposition_fingerprint
                    or resolution.deadline_utc
                    != clock.deadline_utc
                    or resolution.time_disposition
                    != time_item.disposition
                    or resolution.ticker != plan.ticker
                    or resolution.direction != plan.direction
                ):
                    raise RecurrentPriceTimeExitResolutionError(
                        "resolution lineage differs from expiry/plan evidence"
                    )

                provider_age = (
                    evaluation - quote.provider_timestamp_utc
                ).total_seconds()
                receive_age = (
                    evaluation - quote.received_at_utc
                ).total_seconds()
                if provider_age < -5.0 or receive_age < -5.0:
                    raise RecurrentPriceTimeExitResolutionError(
                        "resolution quote is ahead of evaluation time"
                    )
                if (
                    provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS
                    or receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS
                ):
                    raise RecurrentPriceTimeExitResolutionError(
                        "resolution quote exceeds accepted execution age cap"
                    )
                expected_price = _price_condition(
                    bid_price=quote.bid_price,
                    stop_price=plan.stop_price_per_unit,
                    target_price=plan.target_price_per_unit,
                )
                expected_time_executable = (
                    time_item.disposition
                    == TimeExpiryDisposition.TIME_EXPIRED
                    and quote.received_at_utc >= clock.deadline_utc
                )
                reasons, selected = _selected_disposition(
                    price_condition=expected_price,
                    time_exit_executable=expected_time_executable,
                    policy=self.precedence_policy,
                )
                if (
                    resolution.price_condition != expected_price
                    or resolution.time_exit_executable
                    != expected_time_executable
                    or resolution.true_exit_reasons != reasons
                    or resolution.selected_disposition != selected
                    or resolution.precedence_policy_fingerprint
                    != self.precedence_policy_fingerprint
                ):
                    raise RecurrentPriceTimeExitResolutionError(
                        "stored exit resolution does not match deterministic price/time rebuild"
                    )

        if any(
            (
                self.fee_evidence_consumed,
                self.close_fill_authority,
                self.account_mutation_authority,
                self.provider_calls_performed,
                self.broker_calls_performed,
                self.provider_write_authority,
                self.broker_write_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentPriceTimeExitResolutionError(
                "exit-resolution bundle cannot grant fee, fill, mutation, external-write, or trading authority"
            )

        expected = _fingerprint_payload(
            _bundle_payload(
                expiry_bundle=self.expiry_bundle,
                quote_bundle=self.quote_bundle,
                precedence_policy=self.precedence_policy,
                resolutions=self.resolutions,
            )
        )
        if self.bundle_fingerprint != expected:
            raise RecurrentPriceTimeExitResolutionError(
                "price/time exit-resolution bundle self-fingerprint mismatch"
            )


def build_recurrent_price_time_exit_resolution_bundle_v1(
    *,
    expiry_bundle: RecurrentTimeExpiryDispositionBundleV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None,
    precedence_policy: ExitTriggerPrecedencePolicyV1,
) -> RecurrentPriceTimeExitResolutionBundleV1:
    time_items = expiry_bundle.dispositions
    if not time_items:
        if quote_bundle is not None:
            raise RecurrentPriceTimeExitResolutionError(
                "empty price/time resolution must not claim quote evidence"
            )
        resolutions: tuple[
            RecurrentPriceTimeExitResolutionV1, ...
        ] = ()
    else:
        if quote_bundle is None:
            raise RecurrentPriceTimeExitResolutionError(
                "open price/time resolution requires quote evidence"
            )
        evaluation = expiry_bundle.evaluation_utc
        if quote_bundle.captured_at_utc > evaluation:
            raise RecurrentPriceTimeExitResolutionError(
                "quote-bundle capture cannot postdate expiry evaluation"
            )
        expected_symbols = tuple(
            sorted(
                {
                    item.clock.ticker
                    for item in time_items
                }
            )
        )
        if quote_bundle.requested_symbols != expected_symbols:
            raise RecurrentPriceTimeExitResolutionError(
                "quote-bundle symbols must exactly match clock coverage"
            )
        quotes = {
            quote.symbol: quote for quote in quote_bundle.quotes
        }
        plans = {
            plan.position_fingerprint: plan
            for plan in expiry_bundle.clock_book.exit_plan_book.plans
        }
        built: list[RecurrentPriceTimeExitResolutionV1] = []
        for time_item in time_items:
            clock = time_item.clock
            plan = plans[clock.position_fingerprint]
            quote = quotes[clock.ticker]
            if quote.session_segment != SessionSegment.REGULAR:
                raise RecurrentPriceTimeExitResolutionError(
                    f"resolution quote is outside regular session for {clock.ticker}"
                )
            provider_age = (
                evaluation - quote.provider_timestamp_utc
            ).total_seconds()
            receive_age = (
                evaluation - quote.received_at_utc
            ).total_seconds()
            if provider_age < -5.0 or receive_age < -5.0:
                raise RecurrentPriceTimeExitResolutionError(
                    f"resolution quote is ahead of evaluation for {clock.ticker}"
                )
            if (
                provider_age > PHASE15_MAX_QUOTE_AGE_SECONDS
                or receive_age > PHASE15_MAX_QUOTE_AGE_SECONDS
            ):
                raise RecurrentPriceTimeExitResolutionError(
                    f"resolution quote is stale for {clock.ticker}"
                )
            price_condition = _price_condition(
                bid_price=quote.bid_price,
                stop_price=plan.stop_price_per_unit,
                target_price=plan.target_price_per_unit,
            )
            time_executable = (
                time_item.disposition
                == TimeExpiryDisposition.TIME_EXPIRED
                and quote.received_at_utc >= clock.deadline_utc
            )
            reasons, selected = _selected_disposition(
                price_condition=price_condition,
                time_exit_executable=time_executable,
                policy=precedence_policy,
            )
            built.append(
                RecurrentPriceTimeExitResolutionV1(
                    position_fingerprint=clock.position_fingerprint,
                    ticker=clock.ticker,
                    direction=plan.direction,
                    quote=quote,
                    time_disposition_fingerprint=(
                        time_item.disposition_fingerprint
                    ),
                    deadline_utc=clock.deadline_utc,
                    time_disposition=time_item.disposition,
                    price_condition=price_condition,
                    time_exit_executable=time_executable,
                    true_exit_reasons=reasons,
                    selected_disposition=selected,
                    precedence_policy_fingerprint=(
                        precedence_policy.policy_fingerprint
                    ),
                )
            )
        resolutions = tuple(
            sorted(
                built,
                key=lambda item: item.position_fingerprint,
            )
        )

    payload = _bundle_payload(
        expiry_bundle=expiry_bundle,
        quote_bundle=quote_bundle,
        precedence_policy=precedence_policy,
        resolutions=resolutions,
    )
    return RecurrentPriceTimeExitResolutionBundleV1(
        contract_version=(
            RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT
        ),
        source_id=RECURRENT_PRICE_TIME_EXIT_RESOLUTION_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        expiry_bundle=expiry_bundle,
        quote_bundle=quote_bundle,
        precedence_policy=precedence_policy,
        precedence_policy_fingerprint=(
            precedence_policy.policy_fingerprint
        ),
        resolutions=resolutions,
    )


def recurrent_price_time_exit_resolution_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_price_time_exit_resolution_file()


def _precedence_policy_from_payload(
    payload: dict[str, object],
) -> ExitTriggerPrecedencePolicyV1:
    return ExitTriggerPrecedencePolicyV1(
        policy_id=str(payload["policy_id"]),
        mode=ExitTriggerPrecedenceMode(str(payload["mode"])),
    )


def _resolution_from_payload(
    payload: dict[str, object],
) -> RecurrentPriceTimeExitResolutionV1:
    values = dict(payload)
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["quote"] = CurrentWebullStockQuoteV1.model_validate(
        values["quote"]
    )
    values["deadline_utc"] = datetime.fromisoformat(
        str(values["deadline_utc"])
    )
    values["time_disposition"] = TimeExpiryDisposition(
        str(values["time_disposition"])
    )
    values["price_condition"] = PriceTriggerCondition(
        str(values["price_condition"])
    )
    values["true_exit_reasons"] = tuple(
        ExitReason(str(item))
        for item in values["true_exit_reasons"]
    )
    values["selected_disposition"] = SelectedExitDisposition(
        str(values["selected_disposition"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentPriceTimeExitResolutionV1(**values)


def recurrent_price_time_exit_resolution_bundle_from_payload(
    payload: dict[str, object],
) -> RecurrentPriceTimeExitResolutionBundleV1:
    expiry_bundle = (
        recurrent_time_expiry_disposition_bundle_from_payload(
            dict(payload["expiry_bundle"])
        )
    )
    quote_bundle = (
        None
        if payload.get("quote_bundle") is None
        else CurrentWebullStockQuoteBundleV1.model_validate(
            payload["quote_bundle"]
        )
    )
    policy = _precedence_policy_from_payload(
        dict(payload["precedence_policy"])
    )
    resolutions = tuple(
        _resolution_from_payload(dict(item))
        for item in payload["resolutions"]
    )
    return RecurrentPriceTimeExitResolutionBundleV1(
        contract_version=str(payload["contract_version"]),
        contract_fingerprint=str(payload["contract_fingerprint"]),
        source_id=str(payload["source_id"]),
        bundle_fingerprint=str(payload["bundle_fingerprint"]),
        expiry_bundle=expiry_bundle,
        quote_bundle=quote_bundle,
        precedence_policy=policy,
        precedence_policy_fingerprint=str(
            payload["precedence_policy_fingerprint"]
        ),
        resolutions=resolutions,
        fee_evidence_consumed=bool(
            payload["fee_evidence_consumed"]
        ),
        close_fill_authority=bool(
            payload["close_fill_authority"]
        ),
        account_mutation_authority=bool(
            payload["account_mutation_authority"]
        ),
        provider_calls_performed=int(
            payload["provider_calls_performed"]
        ),
        broker_calls_performed=int(
            payload["broker_calls_performed"]
        ),
        provider_write_authority=bool(
            payload["provider_write_authority"]
        ),
        broker_write_authority=bool(
            payload["broker_write_authority"]
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


def write_recurrent_price_time_exit_resolution_bundle_v1(
    settings: AtlasSettings,
    bundle: RecurrentPriceTimeExitResolutionBundleV1,
) -> Path:
    path = recurrent_price_time_exit_resolution_path(settings)
    raw = json.dumps(
        _canonicalize(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_recurrent_price_time_exit_resolution_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution readback mismatch"
        )
    return path


def read_recurrent_price_time_exit_resolution_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> RecurrentPriceTimeExitResolutionBundleV1:
    target = (
        Path(path)
        if path is not None
        else recurrent_price_time_exit_resolution_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution root must be an object"
        )
    try:
        return recurrent_price_time_exit_resolution_bundle_from_payload(
            payload
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        RecurrentPriceTimeExitResolutionError,
    ) as exc:
        if isinstance(
            exc,
            RecurrentPriceTimeExitResolutionError,
        ):
            raise
        raise RecurrentPriceTimeExitResolutionError(
            "price/time exit-resolution artifact failed typed validation"
        ) from exc


__all__ = [
    "RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_FINGERPRINT",
    "RECURRENT_PRICE_TIME_EXIT_RESOLUTION_CONTRACT_VERSION",
    "RECURRENT_PRICE_TIME_EXIT_RESOLUTION_SOURCE_ID",
    "ExitReason",
    "ExitTriggerPrecedenceMode",
    "ExitTriggerPrecedencePolicyV1",
    "PriceTriggerCondition",
    "RecurrentPriceTimeExitResolutionBundleV1",
    "RecurrentPriceTimeExitResolutionError",
    "RecurrentPriceTimeExitResolutionV1",
    "SelectedExitDisposition",
    "build_recurrent_price_time_exit_resolution_bundle_v1",
    "read_recurrent_price_time_exit_resolution_bundle_v1",
    "recurrent_price_time_exit_resolution_bundle_from_payload",
    "recurrent_price_time_exit_resolution_path",
    "write_recurrent_price_time_exit_resolution_bundle_v1",
]
