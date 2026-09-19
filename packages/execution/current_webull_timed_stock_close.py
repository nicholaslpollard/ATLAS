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
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.current_webull_decision_stock_close import (
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
    CurrentWebullDecisionStockCloseEvidenceBundleV1,
    CurrentWebullDecisionStockCloseTriggerV1,
    CurrentWebullDecisionStockCloseEvidenceError,
    StockExitTriggerDisposition,
    build_current_webull_decision_stock_close_evidence_bundle_v1,
    current_webull_decision_stock_close_evidence_bundle_from_payload_v1,
)
from packages.execution.current_webull_quote_bundle import (
    CurrentWebullStockQuoteBundleV1,
)
from packages.execution.current_webull_timed_stock_close_contract import (
    CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT,
    CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_FINGERPRINT,
)
from packages.execution.trade_expression import InstrumentKind
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.forecast_horizon_clock import (
    FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT,
    ForecastHorizonClockEvidenceV1,
    ForecastHorizonClockPolicyV1,
    ForecastHorizonClockError,
    build_forecast_horizon_clock_evidence_v1,
    forecast_horizon_clock_evidence_from_payload_v1,
)
from packages.simulation.recurrent_close_position import (
    RecurrentClosePositionError,
    apply_recurrent_close_position_batch_v1,
)
from packages.simulation.recurrent_cycle import RecurrentCycleReceiptV1
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunIdentityV1,
    RecurrentCycleRunnerV1,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RecurrentDecisionStockExitPlanBookV1,
)
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillEvidenceV1,
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
)


CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_VERSION = str(
    CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT["contract_id"]
)
CURRENT_WEBULL_TIMED_STOCK_CLOSE_SOURCE_ID = (
    "atlas-current-webull-timed-stock-close/current.json"
)
_MAX_BUNDLE_BYTES = 192 * 1024 * 1024


class CurrentWebullTimedStockCloseError(RuntimeError):
    pass


class TimedStockExitDisposition(StrEnum):
    NO_TRIGGER = "NO_TRIGGER"
    STOP = "STOP"
    TARGET = "TARGET"
    TIME = "TIME"


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CurrentWebullTimedStockCloseError(
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


def _price_triggered_position_ids(
    *,
    plan_book: RecurrentDecisionStockExitPlanBookV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None,
) -> set[str]:
    if quote_bundle is None:
        return set()
    quotes = {
        quote.symbol: quote for quote in quote_bundle.quotes
    }
    triggered: set[str] = set()
    for plan in plan_book.plans:
        quote = quotes.get(plan.ticker)
        if quote is None:
            continue
        if (
            quote.bid_price <= plan.stop_price_per_unit
            or quote.bid_price >= plan.target_price_per_unit
        ):
            triggered.add(plan.position_fingerprint)
    return triggered


def _fill_source_fingerprint(
    *,
    base_bundle_fingerprint: str,
    clock_evidence_fingerprint: str,
    fee_source_id: str,
    fee_source_fingerprint: str,
    disposition: TimedStockExitDisposition,
    position_fingerprint: str,
    explicit_exit_fee_dollars: float,
) -> str:
    return _fingerprint_payload(
        {
            "contract_fingerprint": (
                CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_FINGERPRINT
            ),
            "base_bundle_fingerprint": base_bundle_fingerprint,
            "clock_evidence_fingerprint": (
                clock_evidence_fingerprint
            ),
            "fee_source_id": fee_source_id,
            "fee_source_fingerprint": fee_source_fingerprint,
            "disposition": disposition,
            "position_fingerprint": position_fingerprint,
            "explicit_exit_fee_dollars": explicit_exit_fee_dollars,
        }
    )


@dataclass(frozen=True)
class CurrentWebullTimedStockCloseTriggerV2:
    base_trigger: CurrentWebullDecisionStockCloseTriggerV1
    clock_evidence: ForecastHorizonClockEvidenceV1
    disposition: TimedStockExitDisposition
    explicit_exit_fee_dollars: float | None
    fill: RecurrentExitFillEvidenceV1 | None

    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.clock_evidence.contract_fingerprint
            != FORECAST_HORIZON_CLOCK_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE clock contract fingerprint mismatch"
            )
        if (
            self.clock_evidence.plan_fingerprint
            != self.base_trigger.plan.plan_fingerprint
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE clock/plan fingerprint mismatch"
            )
        if (
            self.clock_evidence.evaluation_utc
            != self.base_trigger.quote.received_at_utc
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE clock must be evaluated at quote receipt"
            )
        expected = (
            TimedStockExitDisposition.TIME
            if self.clock_evidence.expired
            else TimedStockExitDisposition(
                self.base_trigger.disposition.value
            )
        )
        if self.disposition != expected:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE disposition violates TIME precedence"
            )
        if self.disposition == TimedStockExitDisposition.NO_TRIGGER:
            if (
                self.explicit_exit_fee_dollars is not None
                or self.fill is not None
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed NO_TRIGGER cannot carry fee or fill"
                )
        else:
            if self.explicit_exit_fee_dollars is None:
                raise CurrentWebullTimedStockCloseError(
                    "timed triggered CLOSE requires explicit fee"
                )
            if (
                not math.isfinite(self.explicit_exit_fee_dollars)
                or self.explicit_exit_fee_dollars < 0.0
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed CLOSE fee must be finite and nonnegative"
                )
            if self.fill is None:
                raise CurrentWebullTimedStockCloseError(
                    "timed triggered CLOSE requires fill"
                )
            if (
                self.base_trigger.explicit_exit_fee_dollars
                is not None
                and not math.isclose(
                    self.base_trigger.explicit_exit_fee_dollars,
                    self.explicit_exit_fee_dollars,
                    rel_tol=1e-12,
                    abs_tol=1e-9,
                )
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed CLOSE cannot change accepted base price-trigger fee"
                )
            if (
                self.fill.position_fingerprint
                != self.base_trigger.plan.position_fingerprint
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed CLOSE fill/position mismatch"
                )
            if self.fill.ticker != self.base_trigger.plan.ticker:
                raise CurrentWebullTimedStockCloseError(
                    "timed CLOSE fill ticker mismatch"
                )
            if (
                self.fill.exited_utc
                != self.base_trigger.quote.received_at_utc
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed CLOSE fill time must equal quote receipt"
                )
            if not math.isclose(
                self.fill.exit_price_per_unit,
                self.base_trigger.quote.bid_price,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed CLOSE fill must use executable bid"
                )
            if not math.isclose(
                self.fill.exit_fees_dollars,
                self.explicit_exit_fee_dollars,
                rel_tol=1e-12,
                abs_tol=1e-9,
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed CLOSE fill fee mismatch"
                )
        if self.base_bundle.built_at_utc != self.built_at_utc:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE build time must equal retained base bundle build time"
            )
        if final_triggered:
            assert self.fee_source_id is not None
            assert self.fee_source_fingerprint is not None
            for trigger in final_triggered:
                assert trigger.fill is not None
                assert trigger.explicit_exit_fee_dollars is not None
                expected_source = _fill_source_fingerprint(
                    base_bundle_fingerprint=(
                        self.base_bundle.bundle_fingerprint
                    ),
                    clock_evidence_fingerprint=(
                        trigger.clock_evidence.evidence_fingerprint
                    ),
                    fee_source_id=self.fee_source_id,
                    fee_source_fingerprint=(
                        self.fee_source_fingerprint
                    ),
                    disposition=trigger.disposition,
                    position_fingerprint=(
                        trigger.base_trigger.plan.position_fingerprint
                    ),
                    explicit_exit_fee_dollars=(
                        trigger.explicit_exit_fee_dollars
                    ),
                )
                if (
                    trigger.fill.fill_source_fingerprint
                    != expected_source
                ):
                    raise CurrentWebullTimedStockCloseError(
                        "timed CLOSE fill-source fingerprint mismatch"
                    )
        if any(
            (
                self.provider_calls_performed,
                self.broker_calls_performed,
                self.broker_fill_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
            )
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE trigger cannot grant external or trading authority"
            )

    @property
    def trigger_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _bundle_payload(
    *,
    base_bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1,
    fee_source_id: str | None,
    fee_source_fingerprint: str | None,
    built_at_utc: datetime,
    triggers: tuple[CurrentWebullTimedStockCloseTriggerV2, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_FINGERPRINT
        ),
        "source_id": CURRENT_WEBULL_TIMED_STOCK_CLOSE_SOURCE_ID,
        "base_bundle": base_bundle,
        "fee_source_id": fee_source_id,
        "fee_source_fingerprint": fee_source_fingerprint,
        "built_at_utc": built_at_utc,
        "triggers": triggers,
        "provider_calls_performed": 0,
        "broker_calls_performed": 0,
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
class CurrentWebullTimedStockCloseBundleV2:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    base_bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1
    fee_source_id: str | None
    fee_source_fingerprint: str | None
    built_at_utc: datetime
    triggers: tuple[CurrentWebullTimedStockCloseTriggerV2, ...]

    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
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
            != CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_VERSION
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE contract fingerprint mismatch"
            )
        if self.source_id != CURRENT_WEBULL_TIMED_STOCK_CLOSE_SOURCE_ID:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE source id mismatch"
            )
        _require_sha(
            self.bundle_fingerprint,
            label="timed CLOSE bundle",
        )
        if (
            self.base_bundle.contract_fingerprint
            != CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE base v1 contract mismatch"
            )
        if (
            self.built_at_utc.tzinfo is None
            or self.built_at_utc.utcoffset() is None
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE build time must be timezone-aware"
            )
        ordered = tuple(
            sorted(
                self.triggers,
                key=lambda item: (
                    item.base_trigger.plan.position_fingerprint
                ),
            )
        )
        if ordered != self.triggers:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE triggers must be deterministically ordered"
            )
        base_triggers = tuple(
            trigger.base_trigger for trigger in self.triggers
        )
        if base_triggers != self.base_bundle.triggers:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE must exactly cover base v1 triggers"
            )
        final_triggered = tuple(
            trigger
            for trigger in self.triggers
            if trigger.disposition
            != TimedStockExitDisposition.NO_TRIGGER
        )
        if final_triggered:
            if (
                self.fee_source_id is None
                or not self.fee_source_id.strip()
                or self.fee_source_fingerprint is None
            ):
                raise CurrentWebullTimedStockCloseError(
                    "timed triggered bundle requires fee source"
                )
            _require_sha(
                self.fee_source_fingerprint,
                label="timed CLOSE fee source",
            )
        elif (
            self.fee_source_id is not None
            or self.fee_source_fingerprint is not None
        ):
            raise CurrentWebullTimedStockCloseError(
                "timed NO_TRIGGER bundle cannot claim fee source"
            )
        if any(
            (
                self.provider_calls_performed,
                self.broker_calls_performed,
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
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE cannot grant external or trading authority"
            )
        expected = _fingerprint_payload(
            _bundle_payload(
                base_bundle=self.base_bundle,
                fee_source_id=self.fee_source_id,
                fee_source_fingerprint=self.fee_source_fingerprint,
                built_at_utc=self.built_at_utc,
                triggers=self.triggers,
            )
        )
        if self.bundle_fingerprint != expected:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE bundle self-fingerprint mismatch"
            )

    @property
    def cycle_id(self) -> str:
        return self.base_bundle.cycle_id

    @property
    def cycle_fingerprint(self) -> str:
        return self.base_bundle.cycle_fingerprint

    @property
    def triggered_fills(
        self,
    ) -> tuple[RecurrentExitFillEvidenceV1, ...]:
        return tuple(
            trigger.fill
            for trigger in self.triggers
            if trigger.fill is not None
        )


def build_current_webull_timed_stock_close_bundle_v2(
    *,
    account: RecurrentLifecycleAccountV1,
    identity: RecurrentCycleRunIdentityV1,
    exit_plan_book: RecurrentDecisionStockExitPlanBookV1,
    quote_bundle: CurrentWebullStockQuoteBundleV1 | None,
    clock_policy_by_position: Mapping[
        str, ForecastHorizonClockPolicyV1
    ],
    explicit_exit_fees_by_position: Mapping[str, float],
    fee_source_id: str | None = None,
    fee_source_fingerprint: str | None = None,
    built_at_utc: datetime | None = None,
) -> CurrentWebullTimedStockCloseBundleV2:
    built = (
        datetime.now(UTC)
        if built_at_utc is None
        else built_at_utc.astimezone(UTC)
    )

    price_triggered = _price_triggered_position_ids(
        plan_book=exit_plan_book,
        quote_bundle=quote_bundle,
    )
    price_fee_map = {
        position_fp: explicit_exit_fees_by_position[position_fp]
        for position_fp in price_triggered
        if position_fp in explicit_exit_fees_by_position
    }
    try:
        base_bundle = (
            build_current_webull_decision_stock_close_evidence_bundle_v1(
                account=account,
                identity=identity,
                exit_plan_book=exit_plan_book,
                quote_bundle=quote_bundle,
                explicit_exit_fees_by_position=price_fee_map,
                fee_source_id=(
                    fee_source_id if price_triggered else None
                ),
                fee_source_fingerprint=(
                    fee_source_fingerprint
                    if price_triggered
                    else None
                ),
                built_at_utc=built,
            )
        )
    except CurrentWebullDecisionStockCloseEvidenceError as exc:
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE base price evidence failed"
        ) from exc

    expected_policy_ids = {
        trigger.plan.position_fingerprint
        for trigger in base_bundle.triggers
    }
    supplied_policy_ids = set(clock_policy_by_position)
    if supplied_policy_ids != expected_policy_ids:
        missing = sorted(
            expected_policy_ids - supplied_policy_ids
        )
        extra = sorted(
            supplied_policy_ids - expected_policy_ids
        )
        raise CurrentWebullTimedStockCloseError(
            "clock-policy coverage must exactly match open positions; "
            f"missing={missing}, extra={extra}"
        )

    staged: list[
        tuple[
            CurrentWebullDecisionStockCloseTriggerV1,
            ForecastHorizonClockEvidenceV1,
            TimedStockExitDisposition,
        ]
    ] = []
    for base_trigger in base_bundle.triggers:
        position_fp = base_trigger.plan.position_fingerprint
        try:
            clock = build_forecast_horizon_clock_evidence_v1(
                plan=base_trigger.plan,
                evaluation_utc=(
                    base_trigger.quote.received_at_utc
                ),
                policy=clock_policy_by_position[position_fp],
            )
        except ForecastHorizonClockError as exc:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE clock evaluation failed"
            ) from exc
        disposition = (
            TimedStockExitDisposition.TIME
            if clock.expired
            else TimedStockExitDisposition(
                base_trigger.disposition.value
            )
        )
        staged.append((base_trigger, clock, disposition))

    final_triggered_ids = {
        base_trigger.plan.position_fingerprint
        for base_trigger, _clock, disposition in staged
        if disposition != TimedStockExitDisposition.NO_TRIGGER
    }
    supplied_fee_ids = set(explicit_exit_fees_by_position)
    if supplied_fee_ids != final_triggered_ids:
        missing = sorted(final_triggered_ids - supplied_fee_ids)
        extra = sorted(supplied_fee_ids - final_triggered_ids)
        raise CurrentWebullTimedStockCloseError(
            "final timed CLOSE fee coverage must exactly match triggered positions; "
            f"missing={missing}, extra={extra}"
        )
    if final_triggered_ids:
        if (
            fee_source_id is None
            or not fee_source_id.strip()
            or fee_source_fingerprint is None
        ):
            raise CurrentWebullTimedStockCloseError(
                "final timed CLOSE requires explicit fee source"
            )
        _require_sha(
            fee_source_fingerprint,
            label="timed CLOSE fee source",
        )
    elif fee_source_id is not None or fee_source_fingerprint is not None:
        raise CurrentWebullTimedStockCloseError(
            "timed NO_TRIGGER bundle cannot claim fee source"
        )

    final: list[CurrentWebullTimedStockCloseTriggerV2] = []
    state = account.state
    for base_trigger, clock, disposition in staged:
        if disposition == TimedStockExitDisposition.NO_TRIGGER:
            final.append(
                CurrentWebullTimedStockCloseTriggerV2(
                    base_trigger=base_trigger,
                    clock_evidence=clock,
                    disposition=disposition,
                    explicit_exit_fee_dollars=None,
                    fill=None,
                )
            )
            continue
        position_fp = base_trigger.plan.position_fingerprint
        fee = float(
            explicit_exit_fees_by_position[position_fp]
        )
        if not math.isfinite(fee) or fee < 0.0:
            raise CurrentWebullTimedStockCloseError(
                "timed CLOSE fee must be finite and nonnegative"
            )
        assert fee_source_id is not None
        assert fee_source_fingerprint is not None
        source_fp = _fill_source_fingerprint(
            base_bundle_fingerprint=(
                base_bundle.bundle_fingerprint
            ),
            clock_evidence_fingerprint=(
                clock.evidence_fingerprint
            ),
            fee_source_id=fee_source_id,
            fee_source_fingerprint=fee_source_fingerprint,
            disposition=disposition,
            position_fingerprint=position_fp,
            explicit_exit_fee_dollars=fee,
        )
        fill = build_recurrent_exit_fill_evidence(
            source_state=state,
            position_fingerprint=position_fp,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id=(
                    f"current-webull-timed-stock-close:"
                    f"{base_trigger.plan.ticker}:"
                    f"{disposition.value}"
                ),
                fill_source_fingerprint=source_fp,
                exited_utc=base_trigger.quote.received_at_utc,
                exit_price_per_unit=(
                    base_trigger.quote.bid_price
                ),
                explicit_exit_fees_dollars=fee,
            ),
        )
        final.append(
            CurrentWebullTimedStockCloseTriggerV2(
                base_trigger=base_trigger,
                clock_evidence=clock,
                disposition=disposition,
                explicit_exit_fee_dollars=fee,
                fill=fill,
            )
        )

    ordered = tuple(
        sorted(
            final,
            key=lambda item: (
                item.base_trigger.plan.position_fingerprint
            ),
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
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE final batch dry-run failed"
        ) from exc

    payload = _bundle_payload(
        base_bundle=base_bundle,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        triggers=ordered,
    )
    return CurrentWebullTimedStockCloseBundleV2(
        contract_version=(
            CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_FINGERPRINT
        ),
        source_id=CURRENT_WEBULL_TIMED_STOCK_CLOSE_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        base_bundle=base_bundle,
        fee_source_id=fee_source_id,
        fee_source_fingerprint=fee_source_fingerprint,
        built_at_utc=built,
        triggers=ordered,
    )


def current_webull_timed_stock_close_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_timed_stock_close_evidence_file()


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


def current_webull_timed_stock_close_bundle_from_payload_v2(
    payload: dict[str, object],
) -> CurrentWebullTimedStockCloseBundleV2:
    try:
        base = (
            current_webull_decision_stock_close_evidence_bundle_from_payload_v1(
                dict(payload["base_bundle"])
            )
        )
        triggers = tuple(
            CurrentWebullTimedStockCloseTriggerV2(
                base_trigger=base.triggers[index],
                clock_evidence=(
                    forecast_horizon_clock_evidence_from_payload_v1(
                        dict(item["clock_evidence"])
                    )
                ),
                disposition=TimedStockExitDisposition(
                    str(item["disposition"])
                ),
                explicit_exit_fee_dollars=(
                    None
                    if item.get(
                        "explicit_exit_fee_dollars"
                    )
                    is None
                    else float(
                        item["explicit_exit_fee_dollars"]
                    )
                ),
                fill=(
                    None
                    if item.get("fill") is None
                    else _fill_from_payload(
                        dict(item["fill"])
                    )
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
                paper_authority=bool(
                    item["paper_authority"]
                ),
                live_authority=bool(
                    item["live_authority"]
                ),
            )
            for index, item in enumerate(payload["triggers"])
        )
        return CurrentWebullTimedStockCloseBundleV2(
            contract_version=str(payload["contract_version"]),
            contract_fingerprint=str(
                payload["contract_fingerprint"]
            ),
            source_id=str(payload["source_id"]),
            bundle_fingerprint=str(
                payload["bundle_fingerprint"]
            ),
            base_bundle=base,
            fee_source_id=(
                None
                if payload.get("fee_source_id") is None
                else str(payload["fee_source_id"])
            ),
            fee_source_fingerprint=(
                None
                if payload.get("fee_source_fingerprint") is None
                else str(payload["fee_source_fingerprint"])
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
        CurrentWebullTimedStockCloseError,
        CurrentWebullDecisionStockCloseEvidenceError,
        ForecastHorizonClockError,
    ) as exc:
        if isinstance(exc, CurrentWebullTimedStockCloseError):
            raise
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE payload failed typed validation"
        ) from exc


def write_current_webull_timed_stock_close_bundle_v2(
    settings: AtlasSettings,
    bundle: CurrentWebullTimedStockCloseBundleV2,
) -> Path:
    path = current_webull_timed_stock_close_path(settings)
    raw = json.dumps(
        _canonicalize(bundle),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_current_webull_timed_stock_close_bundle_v2(
        settings,
        path=path,
    )
    if restored != bundle:
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE readback mismatch"
        )
    return path


def read_current_webull_timed_stock_close_bundle_v2(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> CurrentWebullTimedStockCloseBundleV2:
    target = (
        Path(path)
        if path is not None
        else current_webull_timed_stock_close_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE artifact root must be object"
        )
    return current_webull_timed_stock_close_bundle_from_payload_v2(
        payload
    )


def apply_current_webull_timed_stock_close_bundle_v2(
    *,
    runner: RecurrentCycleRunnerV1,
    identity: RecurrentCycleRunIdentityV1,
    bundle: CurrentWebullTimedStockCloseBundleV2,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    if (
        bundle.cycle_id != identity.cycle_id
        or bundle.cycle_fingerprint
        != identity.cycle_fingerprint
    ):
        raise CurrentWebullTimedStockCloseError(
            "timed CLOSE bundle belongs to different cycle"
        )
    return runner.apply_close(
        identity=identity,
        evidence_source_id=bundle.source_id,
        evidence_source_fingerprint=bundle.bundle_fingerprint,
        fills=bundle.triggered_fills,
        now_utc=now_utc,
    )


__all__ = [
    "CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_FINGERPRINT",
    "CURRENT_WEBULL_TIMED_STOCK_CLOSE_CONTRACT_VERSION",
    "CURRENT_WEBULL_TIMED_STOCK_CLOSE_SOURCE_ID",
    "CurrentWebullTimedStockCloseBundleV2",
    "CurrentWebullTimedStockCloseError",
    "CurrentWebullTimedStockCloseTriggerV2",
    "TimedStockExitDisposition",
    "apply_current_webull_timed_stock_close_bundle_v2",
    "build_current_webull_timed_stock_close_bundle_v2",
    "current_webull_timed_stock_close_bundle_from_payload_v2",
    "current_webull_timed_stock_close_path",
    "read_current_webull_timed_stock_close_bundle_v2",
    "write_current_webull_timed_stock_close_bundle_v2",
]
