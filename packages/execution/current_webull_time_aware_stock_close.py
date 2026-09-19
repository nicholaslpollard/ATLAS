from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
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
    StockExitTriggerDisposition,
    current_webull_decision_stock_close_evidence_bundle_from_payload,
)
from packages.execution.current_webull_time_aware_stock_close_contract import (
    CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT,
    CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.simulation.forecast_horizon_time_disposition import (
    FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT,
    ForecastHorizonTimeDispositionBundleV1,
    ForecastHorizonTimeDispositionKind,
    ForecastHorizonTimeDispositionV1,
    forecast_horizon_time_disposition_bundle_from_payload,
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
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillEvidenceV1,
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
)


CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_VERSION = str(
    CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT["contract_id"]
)
CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_SOURCE_ID = (
    "atlas-current-webull-time-aware-stock-close/current.json"
)
_MAX_BUNDLE_BYTES = 256 * 1024 * 1024
_TOLERANCE = 1e-9


class CurrentWebullTimeAwareStockCloseError(RuntimeError):
    pass


class FinalStockCloseDisposition(StrEnum):
    NO_TRIGGER = "NO_TRIGGER"
    STOP = "STOP"
    TARGET = "TARGET"
    TIME = "TIME"


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CurrentWebullTimeAwareStockCloseError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise CurrentWebullTimeAwareStockCloseError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _same(left: float, right: float) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-12,
        abs_tol=_TOLERANCE,
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


def _time_fill_source_fingerprint(
    *,
    price_close_bundle_fingerprint: str,
    time_disposition_bundle_fingerprint: str,
    time_fee_source_id: str,
    time_fee_source_fingerprint: str,
    price_trigger: CurrentWebullDecisionStockCloseTriggerV1,
    time_disposition: ForecastHorizonTimeDispositionV1,
    explicit_time_exit_fee_dollars: float,
) -> str:
    return _fingerprint_payload(
        {
            "contract_fingerprint": (
                CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
            ),
            "price_close_bundle_fingerprint": (
                price_close_bundle_fingerprint
            ),
            "time_disposition_bundle_fingerprint": (
                time_disposition_bundle_fingerprint
            ),
            "time_fee_source_id": time_fee_source_id,
            "time_fee_source_fingerprint": (
                time_fee_source_fingerprint
            ),
            "price_trigger": price_trigger,
            "time_disposition": time_disposition,
            "explicit_time_exit_fee_dollars": (
                explicit_time_exit_fee_dollars
            ),
        }
    )


@dataclass(frozen=True)
class CurrentWebullTimeAwareStockCloseRowV1:
    price_trigger: CurrentWebullDecisionStockCloseTriggerV1
    time_disposition: ForecastHorizonTimeDispositionV1
    final_disposition: FinalStockCloseDisposition
    explicit_time_exit_fee_dollars: float | None
    final_fill: RecurrentExitFillEvidenceV1 | None

    provider_calls_performed: int = 0
    broker_calls_performed: int = 0
    broker_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.price_trigger.plan.position_fingerprint
            != self.time_disposition.position_fingerprint
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "price/time CLOSE row position mismatch"
            )
        if (
            self.price_trigger.plan.instrument_id
            != self.time_disposition.instrument_id
            or self.price_trigger.plan.ticker
            != self.time_disposition.ticker
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "price/time CLOSE row instrument mismatch"
            )

        price_kind = self.price_trigger.disposition
        time_kind = self.time_disposition.disposition
        if price_kind == StockExitTriggerDisposition.STOP:
            if self.final_disposition != FinalStockCloseDisposition.STOP:
                raise CurrentWebullTimeAwareStockCloseError(
                    "STOP price trigger must retain STOP precedence"
                )
            if self.final_fill != self.price_trigger.fill:
                raise CurrentWebullTimeAwareStockCloseError(
                    "STOP final fill must reuse accepted price CLOSE fill"
                )
            if self.explicit_time_exit_fee_dollars is not None:
                raise CurrentWebullTimeAwareStockCloseError(
                    "STOP price trigger cannot carry time-exit fee"
                )
        elif price_kind == StockExitTriggerDisposition.TARGET:
            if self.final_disposition != FinalStockCloseDisposition.TARGET:
                raise CurrentWebullTimeAwareStockCloseError(
                    "TARGET price trigger must retain TARGET precedence"
                )
            if self.final_fill != self.price_trigger.fill:
                raise CurrentWebullTimeAwareStockCloseError(
                    "TARGET final fill must reuse accepted price CLOSE fill"
                )
            if self.explicit_time_exit_fee_dollars is not None:
                raise CurrentWebullTimeAwareStockCloseError(
                    "TARGET price trigger cannot carry time-exit fee"
                )
        elif price_kind == StockExitTriggerDisposition.NO_TRIGGER:
            if time_kind == ForecastHorizonTimeDispositionKind.TIME_EXPIRED:
                if self.final_disposition != FinalStockCloseDisposition.TIME:
                    raise CurrentWebullTimeAwareStockCloseError(
                        "expired NO_TRIGGER row must resolve to TIME"
                    )
                if self.explicit_time_exit_fee_dollars is None:
                    raise CurrentWebullTimeAwareStockCloseError(
                        "TIME exit requires explicit fee evidence"
                    )
                if self.final_fill is None:
                    raise CurrentWebullTimeAwareStockCloseError(
                        "TIME exit requires recurrent exit-fill evidence"
                    )
                if (
                    self.price_trigger.quote.received_at_utc
                    < self.time_disposition.deadline_utc
                ):
                    raise CurrentWebullTimeAwareStockCloseError(
                        "TIME exit quote must be received at or after deadline"
                    )
                if not _same(
                    self.final_fill.exit_price_per_unit,
                    self.price_trigger.quote.bid_price,
                ):
                    raise CurrentWebullTimeAwareStockCloseError(
                        "TIME exit fill price must equal current Webull bid"
                    )
                if (
                    self.final_fill.exited_utc
                    != self.price_trigger.quote.received_at_utc
                ):
                    raise CurrentWebullTimeAwareStockCloseError(
                        "TIME exit fill timestamp must equal quote receipt"
                    )
                if not _same(
                    self.final_fill.exit_fees_dollars,
                    self.explicit_time_exit_fee_dollars,
                ):
                    raise CurrentWebullTimeAwareStockCloseError(
                        "TIME exit fill fee does not match explicit time fee"
                    )
            elif (
                time_kind
                == ForecastHorizonTimeDispositionKind.NOT_EXPIRED
            ):
                if (
                    self.final_disposition
                    != FinalStockCloseDisposition.NO_TRIGGER
                ):
                    raise CurrentWebullTimeAwareStockCloseError(
                        "nonexpired NO_TRIGGER row must remain NO_TRIGGER"
                    )
                if (
                    self.explicit_time_exit_fee_dollars is not None
                    or self.final_fill is not None
                ):
                    raise CurrentWebullTimeAwareStockCloseError(
                        "NO_TRIGGER row cannot carry time fee or fill"
                    )
            else:
                raise CurrentWebullTimeAwareStockCloseError(
                    "unsupported time disposition"
                )
        else:
            raise CurrentWebullTimeAwareStockCloseError(
                "unsupported price CLOSE disposition"
            )

        if self.final_fill is not None:
            if (
                self.final_fill.position_fingerprint
                != self.price_trigger.plan.position_fingerprint
            ):
                raise CurrentWebullTimeAwareStockCloseError(
                    "final fill position does not match price/time row"
                )
            if (
                self.final_fill.ticker
                != self.price_trigger.plan.ticker
            ):
                raise CurrentWebullTimeAwareStockCloseError(
                    "final fill ticker does not match price/time row"
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
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE row cannot grant network, broker-fill, order, or trading authority"
            )

    @property
    def position_fingerprint(self) -> str:
        return self.price_trigger.plan.position_fingerprint

    @property
    def row_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _bundle_payload(
    *,
    cycle_id: str,
    cycle_fingerprint: str,
    source_recurrent_state_fingerprint: str,
    price_close_bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1,
    time_disposition_bundle: ForecastHorizonTimeDispositionBundleV1,
    time_fee_source_id: str | None,
    time_fee_source_fingerprint: str | None,
    rows: tuple[CurrentWebullTimeAwareStockCloseRowV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
        ),
        "source_id": CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_SOURCE_ID,
        "cycle_id": cycle_id,
        "cycle_fingerprint": cycle_fingerprint,
        "source_recurrent_state_fingerprint": (
            source_recurrent_state_fingerprint
        ),
        "price_close_bundle": price_close_bundle,
        "time_disposition_bundle": time_disposition_bundle,
        "time_fee_source_id": time_fee_source_id,
        "time_fee_source_fingerprint": time_fee_source_fingerprint,
        "rows": rows,
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
class CurrentWebullTimeAwareStockCloseBundleV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    bundle_fingerprint: str
    cycle_id: str
    cycle_fingerprint: str
    source_recurrent_state_fingerprint: str
    price_close_bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1
    time_disposition_bundle: ForecastHorizonTimeDispositionBundleV1
    time_fee_source_id: str | None
    time_fee_source_fingerprint: str | None
    rows: tuple[CurrentWebullTimeAwareStockCloseRowV1, ...]

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
            != CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_VERSION
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE contract fingerprint mismatch"
            )
        if self.source_id != CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_SOURCE_ID:
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE source id mismatch"
            )
        for label, value in (
            ("bundle", self.bundle_fingerprint),
            ("cycle", self.cycle_fingerprint),
            (
                "source recurrent state",
                self.source_recurrent_state_fingerprint,
            ),
        ):
            _require_sha(value, label=label)
        if (
            self.price_close_bundle.contract_fingerprint
            != CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE price bundle contract mismatch"
            )
        if (
            self.time_disposition_bundle.contract_fingerprint
            != FORECAST_HORIZON_TIME_DISPOSITION_CONTRACT_FINGERPRINT
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE time bundle contract mismatch"
            )
        if (
            self.price_close_bundle.cycle_id != self.cycle_id
            or self.price_close_bundle.cycle_fingerprint
            != self.cycle_fingerprint
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE price bundle cycle mismatch"
            )
        if (
            self.price_close_bundle.source_recurrent_state_fingerprint
            != self.source_recurrent_state_fingerprint
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE price bundle recurrent-state mismatch"
            )
        if (
            self.time_disposition_bundle.source_clock_book.source_exit_plan_book
            != self.price_close_bundle.exit_plan_book
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE price/time exit-plan books differ"
            )
        if (
            self.time_disposition_bundle.evaluation_utc
            != self.price_close_bundle.built_at_utc
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE evaluation UTC must equal price CLOSE build time"
            )

        ordered = tuple(
            sorted(
                self.rows,
                key=lambda item: item.position_fingerprint,
            )
        )
        if ordered != self.rows:
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE rows must be ordered by position fingerprint"
            )
        price_triggers = self.price_close_bundle.triggers
        time_dispositions = self.time_disposition_bundle.dispositions
        if (
            len(self.rows) != len(price_triggers)
            or len(self.rows) != len(time_dispositions)
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE must exactly cover price and time rows"
            )
        for row, price_trigger, time_disposition in zip(
            self.rows,
            price_triggers,
            time_dispositions,
            strict=True,
        ):
            if (
                row.price_trigger != price_trigger
                or row.time_disposition != time_disposition
            ):
                raise CurrentWebullTimeAwareStockCloseError(
                    "time-aware CLOSE nested row evidence mismatch"
                )

        has_time = any(
            row.final_disposition == FinalStockCloseDisposition.TIME
            for row in self.rows
        )
        if has_time:
            if (
                self.time_fee_source_id is None
                or not self.time_fee_source_id.strip()
                or self.time_fee_source_fingerprint is None
            ):
                raise CurrentWebullTimeAwareStockCloseError(
                    "TIME exits require explicit time-fee source evidence"
                )
            _require_sha(
                self.time_fee_source_fingerprint,
                label="time-exit fee source",
            )
        elif (
            self.time_fee_source_id is not None
            or self.time_fee_source_fingerprint is not None
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "bundle without TIME exits cannot claim time-fee source"
            )

        if has_time:
            assert self.time_fee_source_id is not None
            assert self.time_fee_source_fingerprint is not None
            for row in self.rows:
                if row.final_disposition != FinalStockCloseDisposition.TIME:
                    continue
                assert row.final_fill is not None
                assert row.explicit_time_exit_fee_dollars is not None
                expected_source = _time_fill_source_fingerprint(
                    price_close_bundle_fingerprint=(
                        self.price_close_bundle.bundle_fingerprint
                    ),
                    time_disposition_bundle_fingerprint=(
                        self.time_disposition_bundle.bundle_fingerprint
                    ),
                    time_fee_source_id=self.time_fee_source_id,
                    time_fee_source_fingerprint=(
                        self.time_fee_source_fingerprint
                    ),
                    price_trigger=row.price_trigger,
                    time_disposition=row.time_disposition,
                    explicit_time_exit_fee_dollars=(
                        row.explicit_time_exit_fee_dollars
                    ),
                )
                if row.final_fill.fill_source_fingerprint != expected_source:
                    raise CurrentWebullTimeAwareStockCloseError(
                        "TIME exit fill source fingerprint mismatch"
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
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE bundle cannot grant external or trading authority"
            )

        expected = _fingerprint_payload(
            _bundle_payload(
                cycle_id=self.cycle_id,
                cycle_fingerprint=self.cycle_fingerprint,
                source_recurrent_state_fingerprint=(
                    self.source_recurrent_state_fingerprint
                ),
                price_close_bundle=self.price_close_bundle,
                time_disposition_bundle=self.time_disposition_bundle,
                time_fee_source_id=self.time_fee_source_id,
                time_fee_source_fingerprint=(
                    self.time_fee_source_fingerprint
                ),
                rows=self.rows,
            )
        )
        if self.bundle_fingerprint != expected:
            raise CurrentWebullTimeAwareStockCloseError(
                "time-aware CLOSE bundle self-fingerprint mismatch"
            )

    @property
    def triggered_fills(
        self,
    ) -> tuple[RecurrentExitFillEvidenceV1, ...]:
        return tuple(
            row.final_fill
            for row in self.rows
            if row.final_fill is not None
        )


def build_current_webull_time_aware_stock_close_bundle_v1(
    *,
    account: RecurrentLifecycleAccountV1,
    identity: RecurrentCycleRunIdentityV1,
    price_close_bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1,
    time_disposition_bundle: ForecastHorizonTimeDispositionBundleV1,
    explicit_time_exit_fees_by_position: Mapping[str, float],
    time_fee_source_id: str | None = None,
    time_fee_source_fingerprint: str | None = None,
) -> CurrentWebullTimeAwareStockCloseBundleV1:
    state = account.state
    if (
        price_close_bundle.cycle_id != identity.cycle_id
        or price_close_bundle.cycle_fingerprint
        != identity.cycle_fingerprint
    ):
        raise CurrentWebullTimeAwareStockCloseError(
            "price CLOSE bundle belongs to a different cycle"
        )
    if (
        price_close_bundle.source_recurrent_state_fingerprint
        != state.state_fingerprint
    ):
        raise CurrentWebullTimeAwareStockCloseError(
            "price CLOSE bundle is stale for current recurrent state"
        )
    if (
        time_disposition_bundle.source_clock_book.source_exit_plan_book
        != price_close_bundle.exit_plan_book
    ):
        raise CurrentWebullTimeAwareStockCloseError(
            "price and time evidence do not share exact exit-plan book"
        )
    if (
        time_disposition_bundle.evaluation_utc
        != price_close_bundle.built_at_utc
    ):
        raise CurrentWebullTimeAwareStockCloseError(
            "time evaluation must equal price CLOSE build time"
        )

    time_by_position = {
        item.position_fingerprint: item
        for item in time_disposition_bundle.dispositions
    }
    price_position_ids = {
        trigger.plan.position_fingerprint
        for trigger in price_close_bundle.triggers
    }
    time_position_ids = set(time_by_position)
    if price_position_ids != time_position_ids:
        missing = sorted(price_position_ids - time_position_ids)
        extra = sorted(time_position_ids - price_position_ids)
        raise CurrentWebullTimeAwareStockCloseError(
            "price/time position coverage mismatch; "
            f"missing={missing}, extra={extra}"
        )

    time_positions = {
        trigger.plan.position_fingerprint
        for trigger in price_close_bundle.triggers
        if (
            trigger.disposition == StockExitTriggerDisposition.NO_TRIGGER
            and time_by_position[
                trigger.plan.position_fingerprint
            ].disposition
            == ForecastHorizonTimeDispositionKind.TIME_EXPIRED
        )
    }
    supplied_time_fee_positions = set(
        explicit_time_exit_fees_by_position
    )
    if supplied_time_fee_positions != time_positions:
        missing = sorted(time_positions - supplied_time_fee_positions)
        extra = sorted(supplied_time_fee_positions - time_positions)
        raise CurrentWebullTimeAwareStockCloseError(
            "explicit time-exit fee coverage must exactly match TIME positions; "
            f"missing={missing}, extra={extra}"
        )

    if time_positions:
        if (
            time_fee_source_id is None
            or not time_fee_source_id.strip()
            or time_fee_source_fingerprint is None
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "TIME exits require explicit time-fee source evidence"
            )
        _require_sha(
            time_fee_source_fingerprint,
            label="time-exit fee source",
        )
    elif (
        time_fee_source_id is not None
        or time_fee_source_fingerprint is not None
    ):
        raise CurrentWebullTimeAwareStockCloseError(
            "bundle without TIME exits cannot claim time-fee source"
        )

    rows: list[CurrentWebullTimeAwareStockCloseRowV1] = []
    for price_trigger in price_close_bundle.triggers:
        position_fp = price_trigger.plan.position_fingerprint
        time_disposition = time_by_position.get(position_fp)
        if time_disposition is None:
            raise CurrentWebullTimeAwareStockCloseError(
                "price CLOSE position lacks time disposition"
            )

        if price_trigger.disposition == StockExitTriggerDisposition.STOP:
            rows.append(
                CurrentWebullTimeAwareStockCloseRowV1(
                    price_trigger=price_trigger,
                    time_disposition=time_disposition,
                    final_disposition=FinalStockCloseDisposition.STOP,
                    explicit_time_exit_fee_dollars=None,
                    final_fill=price_trigger.fill,
                )
            )
            continue
        if price_trigger.disposition == StockExitTriggerDisposition.TARGET:
            rows.append(
                CurrentWebullTimeAwareStockCloseRowV1(
                    price_trigger=price_trigger,
                    time_disposition=time_disposition,
                    final_disposition=FinalStockCloseDisposition.TARGET,
                    explicit_time_exit_fee_dollars=None,
                    final_fill=price_trigger.fill,
                )
            )
            continue

        if (
            time_disposition.disposition
            == ForecastHorizonTimeDispositionKind.NOT_EXPIRED
        ):
            rows.append(
                CurrentWebullTimeAwareStockCloseRowV1(
                    price_trigger=price_trigger,
                    time_disposition=time_disposition,
                    final_disposition=(
                        FinalStockCloseDisposition.NO_TRIGGER
                    ),
                    explicit_time_exit_fee_dollars=None,
                    final_fill=None,
                )
            )
            continue

        if (
            time_disposition.disposition
            != ForecastHorizonTimeDispositionKind.TIME_EXPIRED
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "unsupported time disposition"
            )
        if (
            price_trigger.quote.received_at_utc
            < time_disposition.deadline_utc
        ):
            raise CurrentWebullTimeAwareStockCloseError(
                "TIME exit requires quote received at or after deadline"
            )
        fee = float(
            explicit_time_exit_fees_by_position[position_fp]
        )
        if not math.isfinite(fee) or fee < 0.0:
            raise CurrentWebullTimeAwareStockCloseError(
                f"TIME exit fee must be finite and nonnegative for {price_trigger.plan.ticker}"
            )
        assert time_fee_source_id is not None
        assert time_fee_source_fingerprint is not None
        source_fp = _time_fill_source_fingerprint(
            price_close_bundle_fingerprint=(
                price_close_bundle.bundle_fingerprint
            ),
            time_disposition_bundle_fingerprint=(
                time_disposition_bundle.bundle_fingerprint
            ),
            time_fee_source_id=time_fee_source_id,
            time_fee_source_fingerprint=(
                time_fee_source_fingerprint
            ),
            price_trigger=price_trigger,
            time_disposition=time_disposition,
            explicit_time_exit_fee_dollars=fee,
        )
        fill = build_recurrent_exit_fill_evidence(
            source_state=state,
            position_fingerprint=position_fp,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id=(
                    f"current-webull-time-aware-close:{price_trigger.plan.ticker}:TIME"
                ),
                fill_source_fingerprint=source_fp,
                exited_utc=price_trigger.quote.received_at_utc,
                exit_price_per_unit=price_trigger.quote.bid_price,
                explicit_exit_fees_dollars=fee,
            ),
        )
        rows.append(
            CurrentWebullTimeAwareStockCloseRowV1(
                price_trigger=price_trigger,
                time_disposition=time_disposition,
                final_disposition=FinalStockCloseDisposition.TIME,
                explicit_time_exit_fee_dollars=fee,
                final_fill=fill,
            )
        )

    ordered = tuple(
        sorted(
            rows,
            key=lambda item: item.position_fingerprint,
        )
    )
    fills = tuple(
        row.final_fill
        for row in ordered
        if row.final_fill is not None
    )
    try:
        apply_recurrent_close_position_batch_v1(
            account,
            fills,
        )
    except RecurrentClosePositionError as exc:
        raise CurrentWebullTimeAwareStockCloseError(
            "combined price/time CLOSE batch dry-run failed"
        ) from exc

    payload = _bundle_payload(
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        source_recurrent_state_fingerprint=state.state_fingerprint,
        price_close_bundle=price_close_bundle,
        time_disposition_bundle=time_disposition_bundle,
        time_fee_source_id=time_fee_source_id,
        time_fee_source_fingerprint=time_fee_source_fingerprint,
        rows=ordered,
    )
    return CurrentWebullTimeAwareStockCloseBundleV1(
        contract_version=(
            CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT
        ),
        source_id=CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_SOURCE_ID,
        bundle_fingerprint=_fingerprint_payload(payload),
        cycle_id=identity.cycle_id,
        cycle_fingerprint=identity.cycle_fingerprint,
        source_recurrent_state_fingerprint=state.state_fingerprint,
        price_close_bundle=price_close_bundle,
        time_disposition_bundle=time_disposition_bundle,
        time_fee_source_id=time_fee_source_id,
        time_fee_source_fingerprint=time_fee_source_fingerprint,
        rows=ordered,
    )


def current_webull_time_aware_stock_close_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_time_aware_stock_close_evidence_file()


def _fill_from_payload(
    payload: dict[str, object],
) -> RecurrentExitFillEvidenceV1:
    values = dict(payload)
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    from packages.execution.trade_expression import InstrumentKind

    values["instrument_kind"] = InstrumentKind(
        str(values["instrument_kind"])
    )
    values["opened_utc"] = datetime.fromisoformat(
        str(values["opened_utc"])
    )
    values["exited_utc"] = datetime.fromisoformat(
        str(values["exited_utc"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentExitFillEvidenceV1(**values)


def current_webull_time_aware_stock_close_bundle_from_payload(
    payload: dict[str, object],
) -> CurrentWebullTimeAwareStockCloseBundleV1:
    price_bundle = (
        current_webull_decision_stock_close_evidence_bundle_from_payload(
            dict(payload["price_close_bundle"])
        )
    )
    time_bundle = (
        forecast_horizon_time_disposition_bundle_from_payload(
            dict(payload["time_disposition_bundle"])
        )
    )
    price_by_position = {
        item.plan.position_fingerprint: item
        for item in price_bundle.triggers
    }
    time_by_position = {
        item.position_fingerprint: item
        for item in time_bundle.dispositions
    }
    rows = tuple(
        CurrentWebullTimeAwareStockCloseRowV1(
            price_trigger=price_by_position[
                str(item["position_fingerprint"])
            ],
            time_disposition=time_by_position[
                str(item["position_fingerprint"])
            ],
            final_disposition=FinalStockCloseDisposition(
                str(item["final_disposition"])
            ),
            explicit_time_exit_fee_dollars=(
                None
                if item.get("explicit_time_exit_fee_dollars") is None
                else float(item["explicit_time_exit_fee_dollars"])
            ),
            final_fill=(
                None
                if item.get("final_fill") is None
                else _fill_from_payload(dict(item["final_fill"]))
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
        for item in payload["rows"]
    )
    return CurrentWebullTimeAwareStockCloseBundleV1(
        contract_version=str(payload["contract_version"]),
        contract_fingerprint=str(payload["contract_fingerprint"]),
        source_id=str(payload["source_id"]),
        bundle_fingerprint=str(payload["bundle_fingerprint"]),
        cycle_id=str(payload["cycle_id"]),
        cycle_fingerprint=str(payload["cycle_fingerprint"]),
        source_recurrent_state_fingerprint=str(
            payload["source_recurrent_state_fingerprint"]
        ),
        price_close_bundle=price_bundle,
        time_disposition_bundle=time_bundle,
        time_fee_source_id=(
            None
            if payload.get("time_fee_source_id") is None
            else str(payload["time_fee_source_id"])
        ),
        time_fee_source_fingerprint=(
            None
            if payload.get("time_fee_source_fingerprint") is None
            else str(payload["time_fee_source_fingerprint"])
        ),
        rows=rows,
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
        promotion_authority=bool(payload["promotion_authority"]),
        confluence_authority=bool(
            payload["confluence_authority"]
        ),
    )


def write_current_webull_time_aware_stock_close_bundle_v1(
    settings: AtlasSettings,
    bundle: CurrentWebullTimeAwareStockCloseBundleV1,
) -> Path:
    path = current_webull_time_aware_stock_close_path(settings)
    row_payloads = []
    for row in bundle.rows:
        item = _canonicalize(row)
        item["position_fingerprint"] = row.position_fingerprint
        row_payloads.append(item)
    payload = _canonicalize(bundle)
    payload["rows"] = row_payloads
    raw = json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_current_webull_time_aware_stock_close_bundle_v1(
        settings,
        path=path,
    )
    if restored != bundle:
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE readback mismatch"
        )
    return path


def read_current_webull_time_aware_stock_close_bundle_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> CurrentWebullTimeAwareStockCloseBundleV1:
    target = (
        Path(path)
        if path is not None
        else current_webull_time_aware_stock_close_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE artifact root must be an object"
        )
    try:
        return current_webull_time_aware_stock_close_bundle_from_payload(
            payload
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        CurrentWebullTimeAwareStockCloseError,
    ) as exc:
        if isinstance(
            exc,
            CurrentWebullTimeAwareStockCloseError,
        ):
            raise
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE artifact failed typed validation"
        ) from exc


def apply_current_webull_time_aware_stock_close_bundle_v1(
    *,
    runner: RecurrentCycleRunnerV1,
    identity: RecurrentCycleRunIdentityV1,
    bundle: CurrentWebullTimeAwareStockCloseBundleV1,
    now_utc: datetime | None = None,
) -> RecurrentCycleReceiptV1:
    if (
        bundle.cycle_id != identity.cycle_id
        or bundle.cycle_fingerprint
        != identity.cycle_fingerprint
    ):
        raise CurrentWebullTimeAwareStockCloseError(
            "time-aware CLOSE bundle belongs to a different cycle"
        )
    return runner.apply_close(
        identity=identity,
        evidence_source_id=bundle.source_id,
        evidence_source_fingerprint=bundle.bundle_fingerprint,
        fills=bundle.triggered_fills,
        now_utc=now_utc,
    )


__all__ = [
    "CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_FINGERPRINT",
    "CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_CONTRACT_VERSION",
    "CURRENT_WEBULL_TIME_AWARE_STOCK_CLOSE_SOURCE_ID",
    "CurrentWebullTimeAwareStockCloseBundleV1",
    "CurrentWebullTimeAwareStockCloseError",
    "CurrentWebullTimeAwareStockCloseRowV1",
    "FinalStockCloseDisposition",
    "apply_current_webull_time_aware_stock_close_bundle_v1",
    "build_current_webull_time_aware_stock_close_bundle_v1",
    "current_webull_time_aware_stock_close_bundle_from_payload",
    "current_webull_time_aware_stock_close_path",
    "read_current_webull_time_aware_stock_close_bundle_v1",
    "write_current_webull_time_aware_stock_close_bundle_v1",
]
