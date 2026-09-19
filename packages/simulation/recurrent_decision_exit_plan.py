from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.execution.trade_expression import (
    InstrumentKind,
    SelectionKind,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    forecast_fingerprint,
)
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    economic_candidate_fingerprint,
    simulation_decision_record_from_payload,
)
from packages.simulation.decision_record_contract import (
    SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT,
)
from packages.simulation.open_position_state import (
    SimulatedOpenPositionV1,
    simulated_open_position_fingerprint,
)
from packages.simulation.recurrent_decision_exit_plan_contract import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT,
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountStateV1,
    recurrent_lifecycle_account_state_fingerprint,
)
from packages.simulation.recurrent_reserve_evidence import (
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT,
    RecurrentReserveEvidenceBundleV1,
)


RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_VERSION = str(
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT["contract_id"]
)
RECURRENT_DECISION_STOCK_EXIT_PLAN_SOURCE_ID = (
    "atlas-recurrent-decision-stock-exit-plan/current.json"
)
_MAX_BUNDLE_BYTES = 64 * 1024 * 1024
_TOLERANCE = 1e-12


class RecurrentDecisionStockExitPlanError(RuntimeError):
    pass


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentDecisionStockExitPlanError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentDecisionStockExitPlanError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


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
class StockExitPolicyInputsV1:
    policy_id: str
    policy_fingerprint: str
    stop_threshold_fraction: float
    target_threshold_fraction: float
    time_exit_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise RecurrentDecisionStockExitPlanError(
                "stock exit policy id cannot be blank"
            )
        _require_sha(
            self.policy_fingerprint,
            label="stock exit policy",
        )
        for label, value in (
            ("stop threshold", self.stop_threshold_fraction),
            ("target threshold", self.target_threshold_fraction),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise RecurrentDecisionStockExitPlanError(
                    f"{label} must be finite and positive"
                )
        if self.time_exit_enabled:
            raise RecurrentDecisionStockExitPlanError(
                "time exit triggering is not enabled in v1"
            )

    @property
    def inputs_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _matching_threshold(
    record: SimulationDecisionRecord,
    fraction: float,
    *,
    label: str,
) -> MoveThresholdProbability:
    matches = tuple(
        threshold
        for threshold in record.forecast.thresholds
        if _same(threshold.threshold_fraction, fraction)
    )
    if len(matches) != 1:
        raise RecurrentDecisionStockExitPlanError(
            f"{label} threshold must match exactly one accepted forecast threshold"
        )
    return matches[0]


@dataclass(frozen=True)
class RecurrentDecisionStockExitPlanV1:
    contract_version: str
    contract_fingerprint: str
    source_recurrent_state_fingerprint: str
    position_fingerprint: str
    decision_record: SimulationDecisionRecord
    decision_record_fingerprint: str
    forecast_fingerprint: str
    candidate_fingerprint: str
    exit_policy: StockExitPolicyInputsV1
    exit_policy_inputs_fingerprint: str
    stop_threshold: MoveThresholdProbability
    target_threshold: MoveThresholdProbability

    instrument_id: str
    ticker: str
    direction: DiscoveryDirection
    opened_utc: datetime
    plan_created_utc: datetime
    actual_entry_price_per_unit: float
    stop_price_per_unit: float
    target_price_per_unit: float
    forecast_horizon_unit: ForecastHorizonUnit
    forecast_horizon_value: int

    time_exit_trigger_enabled: bool = False
    price_trigger_authority: bool = False
    close_fill_authority: bool = False
    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False
    reason_codes: tuple[str, ...] = (
        "EXACT_PRODUCT_DECISION_RECORD_BOUND",
        "EXACT_RECURRENT_OPEN_STOCK_POSITION_BOUND",
        "EXPLICIT_EXIT_POLICY_BOUND",
        "STOP_THRESHOLD_PRESENT_IN_ACCEPTED_FORECAST",
        "TARGET_THRESHOLD_PRESENT_IN_ACCEPTED_FORECAST",
        "STOP_TARGET_DERIVED_FROM_ACTUAL_ENTRY_FILL",
        "FORECAST_HORIZON_PRESERVED_WITHOUT_TIME_TRIGGER_AUTHORITY",
        "NO_CLOSE_OR_TRADING_AUTHORITY_GRANTED",
    )

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_VERSION
        ):
            raise RecurrentDecisionStockExitPlanError(
                "decision stock exit-plan contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentDecisionStockExitPlanError(
                "decision stock exit-plan contract fingerprint mismatch"
            )
        for label, value in (
            (
                "source recurrent state",
                self.source_recurrent_state_fingerprint,
            ),
            ("position", self.position_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("forecast", self.forecast_fingerprint),
            ("candidate", self.candidate_fingerprint),
            (
                "exit policy inputs",
                self.exit_policy_inputs_fingerprint,
            ),
        ):
            _require_sha(value, label=label)
        opened = _require_aware(
            self.opened_utc,
            label="exit-plan position-open time",
        )
        created = _require_aware(
            self.plan_created_utc,
            label="exit-plan creation time",
        )
        if created < opened:
            raise RecurrentDecisionStockExitPlanError(
                "exit plan cannot be created before position open"
            )
        record = self.decision_record
        if (
            record.contract_fingerprint
            != SIMULATION_DECISION_RECORD_CONTRACT_FINGERPRINT
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan decision-record contract fingerprint mismatch"
            )
        if record.record_fingerprint != self.decision_record_fingerprint:
            raise RecurrentDecisionStockExitPlanError(
                "exit plan decision-record fingerprint mismatch"
            )
        if (
            forecast_fingerprint(record.forecast)
            != self.forecast_fingerprint
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan forecast fingerprint mismatch"
            )
        if (
            record.forecast.availability
            != ForecastAvailability.AVAILABLE
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan requires available forecast evidence"
            )
        if self.direction != DiscoveryDirection.BULLISH:
            raise RecurrentDecisionStockExitPlanError(
                "decision stock exit-plan v1 supports bullish stock longs only"
            )
        if (
            record.forecast.instrument_id != self.instrument_id
            or record.forecast.ticker != self.ticker
            or record.forecast.direction != self.direction
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan decision/position identity mismatch"
            )
        decision = record.trade_expression_decision
        if decision.selection_kind != SelectionKind.STOCK:
            raise RecurrentDecisionStockExitPlanError(
                "exit plan requires a selected stock decision"
            )
        candidate = decision.chosen_candidate
        if candidate is None or candidate.kind != InstrumentKind.STOCK:
            raise RecurrentDecisionStockExitPlanError(
                "exit plan selected stock candidate is missing"
            )
        if (
            economic_candidate_fingerprint(candidate)
            != self.candidate_fingerprint
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan candidate fingerprint mismatch"
            )
        if (
            self.exit_policy.inputs_fingerprint
            != self.exit_policy_inputs_fingerprint
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit policy input fingerprint mismatch"
            )
        expected_stop_threshold = _matching_threshold(
            record,
            self.exit_policy.stop_threshold_fraction,
            label="stop",
        )
        expected_target_threshold = _matching_threshold(
            record,
            self.exit_policy.target_threshold_fraction,
            label="target",
        )
        if self.stop_threshold != expected_stop_threshold:
            raise RecurrentDecisionStockExitPlanError(
                "stored stop-threshold evidence mismatch"
            )
        if self.target_threshold != expected_target_threshold:
            raise RecurrentDecisionStockExitPlanError(
                "stored target-threshold evidence mismatch"
            )
        if (
            self.forecast_horizon_unit
            != record.forecast.horizon_unit
            or self.forecast_horizon_value
            != record.forecast.horizon_value
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan forecast horizon mismatch"
            )
        if (
            not math.isfinite(self.actual_entry_price_per_unit)
            or self.actual_entry_price_per_unit <= 0.0
        ):
            raise RecurrentDecisionStockExitPlanError(
                "actual entry price must be finite and positive"
            )
        expected_stop = self.actual_entry_price_per_unit * (
            1.0 - self.exit_policy.stop_threshold_fraction
        )
        expected_target = self.actual_entry_price_per_unit * (
            1.0 + self.exit_policy.target_threshold_fraction
        )
        if expected_stop <= 0.0:
            raise RecurrentDecisionStockExitPlanError(
                "exit policy stop threshold produces nonpositive stop"
            )
        if not _same(self.stop_price_per_unit, expected_stop):
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan stop is not derived from actual entry fill"
            )
        if not _same(self.target_price_per_unit, expected_target):
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan target is not derived from actual entry fill"
            )
        if not (
            self.stop_price_per_unit
            < self.actual_entry_price_per_unit
            < self.target_price_per_unit
        ):
            raise RecurrentDecisionStockExitPlanError(
                "bullish stock exit geometry is invalid"
            )
        if (
            self.time_exit_trigger_enabled
            or self.price_trigger_authority
            or self.close_fill_authority
            or self.provider_read_authority
            or self.provider_write_authority
            or self.broker_read_authority
            or self.broker_write_authority
            or self.order_creation_authority
            or self.paper_authority
            or self.live_authority
            or self.promotion_authority
            or self.confluence_authority
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan cannot grant trigger, close, provider, broker, order, trading, promotion, or confluence authority"
            )
        if not self.reason_codes:
            raise RecurrentDecisionStockExitPlanError(
                "exit plan requires reason codes"
            )

    @property
    def plan_fingerprint(self) -> str:
        return _fingerprint_payload(self)


def _validate_plan_against_position(
    plan: RecurrentDecisionStockExitPlanV1,
    position: SimulatedOpenPositionV1,
) -> None:
    if simulated_open_position_fingerprint(position) != plan.position_fingerprint:
        raise RecurrentDecisionStockExitPlanError(
            "persisted exit plan position fingerprint is no longer current"
        )
    checks = (
        (
            position.decision_record_fingerprint,
            plan.decision_record_fingerprint,
            "decision record",
        ),
        (
            position.candidate_fingerprint,
            plan.candidate_fingerprint,
            "candidate",
        ),
        (
            position.instrument_id,
            plan.instrument_id,
            "instrument id",
        ),
        (position.ticker, plan.ticker, "ticker"),
        (position.direction, plan.direction, "direction"),
        (position.opened_utc, plan.opened_utc, "opened time"),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise RecurrentDecisionStockExitPlanError(
                f"persisted exit plan {label} no longer matches open position"
            )
    if not _same(
        position.entry_price_per_unit,
        plan.actual_entry_price_per_unit,
    ):
        raise RecurrentDecisionStockExitPlanError(
            "persisted exit plan entry price no longer matches open position"
        )


def build_recurrent_decision_stock_exit_plan_v1(
    *,
    source_recurrent_state_fingerprint: str,
    position: SimulatedOpenPositionV1,
    decision_record: SimulationDecisionRecord,
    exit_policy: StockExitPolicyInputsV1,
    plan_created_utc: datetime | None = None,
) -> RecurrentDecisionStockExitPlanV1:
    _require_sha(
        source_recurrent_state_fingerprint,
        label="source recurrent state",
    )
    if position.instrument_kind != InstrumentKind.STOCK:
        raise RecurrentDecisionStockExitPlanError(
            "decision stock exit-plan v1 accepts stock positions only"
        )
    if position.direction != DiscoveryDirection.BULLISH:
        raise RecurrentDecisionStockExitPlanError(
            "decision stock exit-plan v1 accepts bullish stock longs only"
        )
    if (
        position.decision_record_fingerprint
        != decision_record.record_fingerprint
    ):
        raise RecurrentDecisionStockExitPlanError(
            "open position decision fingerprint does not match supplied decision"
        )
    decision = decision_record.trade_expression_decision
    candidate = decision.chosen_candidate
    if (
        decision.selection_kind != SelectionKind.STOCK
        or candidate is None
        or candidate.kind != InstrumentKind.STOCK
    ):
        raise RecurrentDecisionStockExitPlanError(
            "supplied decision did not select stock"
        )
    candidate_fp = economic_candidate_fingerprint(candidate)
    if position.candidate_fingerprint != candidate_fp:
        raise RecurrentDecisionStockExitPlanError(
            "open position candidate fingerprint does not match decision"
        )
    stop_threshold = _matching_threshold(
        decision_record,
        exit_policy.stop_threshold_fraction,
        label="stop",
    )
    target_threshold = _matching_threshold(
        decision_record,
        exit_policy.target_threshold_fraction,
        label="target",
    )
    created = _require_aware(
        plan_created_utc or datetime.now(UTC),
        label="exit-plan creation time",
    )
    stop = position.entry_price_per_unit * (
        1.0 - exit_policy.stop_threshold_fraction
    )
    target = position.entry_price_per_unit * (
        1.0 + exit_policy.target_threshold_fraction
    )
    return RecurrentDecisionStockExitPlanV1(
        contract_version=(
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        source_recurrent_state_fingerprint=(
            source_recurrent_state_fingerprint
        ),
        position_fingerprint=simulated_open_position_fingerprint(
            position
        ),
        decision_record=decision_record,
        decision_record_fingerprint=decision_record.record_fingerprint,
        forecast_fingerprint=forecast_fingerprint(
            decision_record.forecast
        ),
        candidate_fingerprint=candidate_fp,
        exit_policy=exit_policy,
        exit_policy_inputs_fingerprint=exit_policy.inputs_fingerprint,
        stop_threshold=stop_threshold,
        target_threshold=target_threshold,
        instrument_id=position.instrument_id,
        ticker=position.ticker,
        direction=position.direction,
        opened_utc=position.opened_utc,
        plan_created_utc=created,
        actual_entry_price_per_unit=position.entry_price_per_unit,
        stop_price_per_unit=stop,
        target_price_per_unit=target,
        forecast_horizon_unit=decision_record.forecast.horizon_unit,
        forecast_horizon_value=decision_record.forecast.horizon_value,
    )


def _book_payload(
    *,
    source_recurrent_state_fingerprint: str,
    built_at_utc: datetime,
    plans: tuple[RecurrentDecisionStockExitPlanV1, ...],
) -> dict[str, object]:
    return {
        "contract_version": (
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_VERSION
        ),
        "contract_fingerprint": (
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        "source_id": RECURRENT_DECISION_STOCK_EXIT_PLAN_SOURCE_ID,
        "source_recurrent_state_fingerprint": (
            source_recurrent_state_fingerprint
        ),
        "built_at_utc": built_at_utc,
        "plans": plans,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "price_trigger_authority": False,
        "close_fill_authority": False,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class RecurrentDecisionStockExitPlanBookV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    book_fingerprint: str
    source_recurrent_state_fingerprint: str
    built_at_utc: datetime
    plans: tuple[RecurrentDecisionStockExitPlanV1, ...]

    provider_reads: int = 0
    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    price_trigger_authority: bool = False
    close_fill_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_VERSION
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan book contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan book contract fingerprint mismatch"
            )
        if self.source_id != RECURRENT_DECISION_STOCK_EXIT_PLAN_SOURCE_ID:
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan book source id mismatch"
            )
        _require_sha(self.book_fingerprint, label="exit-plan book")
        _require_sha(
            self.source_recurrent_state_fingerprint,
            label="exit-plan source recurrent state",
        )
        built = _require_aware(
            self.built_at_utc,
            label="exit-plan book build time",
        )
        ordered = tuple(
            sorted(
                self.plans,
                key=lambda item: item.position_fingerprint,
            )
        )
        if ordered != self.plans:
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan book must be ordered by position fingerprint"
            )
        ids = tuple(plan.position_fingerprint for plan in self.plans)
        if len(ids) != len(set(ids)):
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan book cannot duplicate positions"
            )
        if any(plan.plan_created_utc > built for plan in self.plans):
            raise RecurrentDecisionStockExitPlanError(
                "exit plan cannot postdate book construction"
            )
        if any(
            (
                self.provider_reads,
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
                self.price_trigger_authority,
                self.close_fill_authority,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan book cannot grant provider, broker, trigger, close, order, trading, promotion, or confluence authority"
            )
        expected = _fingerprint_payload(
            _book_payload(
                source_recurrent_state_fingerprint=(
                    self.source_recurrent_state_fingerprint
                ),
                built_at_utc=built,
                plans=self.plans,
            )
        )
        if self.book_fingerprint != expected:
            raise RecurrentDecisionStockExitPlanError(
                "exit-plan book self-fingerprint mismatch"
            )


def build_recurrent_decision_stock_exit_plan_book_v1(
    *,
    source_state: RecurrentLifecycleAccountStateV1,
    current_reserve_bundle: RecurrentReserveEvidenceBundleV1 | None,
    existing_book: RecurrentDecisionStockExitPlanBookV1 | None,
    exit_policy_by_decision: Mapping[str, StockExitPolicyInputsV1],
    built_at_utc: datetime | None = None,
) -> RecurrentDecisionStockExitPlanBookV1:
    if (
        source_state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentDecisionStockExitPlanError(
            "source recurrent account contract fingerprint mismatch"
        )
    if (
        source_state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(source_state)
    ):
        raise RecurrentDecisionStockExitPlanError(
            "source recurrent account state fingerprint mismatch"
        )
    positions = tuple(source_state.open_positions)
    if any(
        position.instrument_kind != InstrumentKind.STOCK
        for position in positions
    ):
        raise RecurrentDecisionStockExitPlanError(
            "decision stock exit-plan v1 cannot cover open option positions"
        )
    if any(
        position.direction != DiscoveryDirection.BULLISH
        for position in positions
    ):
        raise RecurrentDecisionStockExitPlanError(
            "decision stock exit-plan v1 supports bullish stock longs only"
        )

    existing_by_position: dict[
        str, RecurrentDecisionStockExitPlanV1
    ] = {}
    if existing_book is not None:
        if (
            existing_book.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentDecisionStockExitPlanError(
                "existing exit-plan book contract fingerprint mismatch"
            )
        existing_by_position = {
            plan.position_fingerprint: plan
            for plan in existing_book.plans
        }

    reserve_records: dict[str, SimulationDecisionRecord] = {}
    if current_reserve_bundle is not None:
        if (
            current_reserve_bundle.contract_fingerprint
            != RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentDecisionStockExitPlanError(
                "current reserve bundle contract fingerprint mismatch"
            )
        reserve_records = {
            entry.record.record_fingerprint: entry.record
            for entry in current_reserve_bundle.entries
        }

    built = _require_aware(
        built_at_utc or datetime.now(UTC),
        label="exit-plan book build time",
    )
    if built < source_state.as_of_utc:
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book cannot predate recurrent state"
        )

    new_decision_fingerprints: set[str] = set()
    plans: list[RecurrentDecisionStockExitPlanV1] = []
    for position in sorted(
        positions,
        key=lambda item: item.position_fingerprint,
    ):
        existing = existing_by_position.get(
            position.position_fingerprint
        )
        if existing is not None:
            _validate_plan_against_position(existing, position)
            plans.append(existing)
            continue

        decision_fp = position.decision_record_fingerprint
        record = reserve_records.get(decision_fp)
        if record is None:
            raise RecurrentDecisionStockExitPlanError(
                "new open position lacks current RESERVE decision evidence"
            )
        policy = exit_policy_by_decision.get(decision_fp)
        if policy is None:
            raise RecurrentDecisionStockExitPlanError(
                "new open position lacks explicit exit policy"
            )
        new_decision_fingerprints.add(decision_fp)
        plans.append(
            build_recurrent_decision_stock_exit_plan_v1(
                source_recurrent_state_fingerprint=(
                    source_state.state_fingerprint
                ),
                position=position,
                decision_record=record,
                exit_policy=policy,
                plan_created_utc=built,
            )
        )

    supplied_policy_keys = set(exit_policy_by_decision)
    if supplied_policy_keys != new_decision_fingerprints:
        missing = sorted(
            new_decision_fingerprints - supplied_policy_keys
        )
        extra = sorted(
            supplied_policy_keys - new_decision_fingerprints
        )
        raise RecurrentDecisionStockExitPlanError(
            "exit-policy coverage must exactly match newly unplanned open positions; "
            f"missing={missing}, extra={extra}"
        )

    ordered = tuple(
        sorted(plans, key=lambda item: item.position_fingerprint)
    )
    payload = _book_payload(
        source_recurrent_state_fingerprint=(
            source_state.state_fingerprint
        ),
        built_at_utc=built,
        plans=ordered,
    )
    return RecurrentDecisionStockExitPlanBookV1(
        contract_version=(
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_VERSION
        ),
        contract_fingerprint=(
            RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ),
        source_id=RECURRENT_DECISION_STOCK_EXIT_PLAN_SOURCE_ID,
        book_fingerprint=_fingerprint_payload(payload),
        source_recurrent_state_fingerprint=(
            source_state.state_fingerprint
        ),
        built_at_utc=built,
        plans=ordered,
    )


def recurrent_decision_stock_exit_plan_path(
    settings: AtlasSettings,
) -> Path:
    return MarketDataPaths(
        settings
    ).recurrent_decision_stock_exit_plan_file()


def _policy_from_payload(
    payload: dict[str, object],
) -> StockExitPolicyInputsV1:
    values = dict(payload)
    return StockExitPolicyInputsV1(**values)


def recurrent_decision_stock_exit_plan_from_payload(
    payload: dict[str, object],
) -> RecurrentDecisionStockExitPlanV1:
    values = dict(payload)
    values["decision_record"] = (
        simulation_decision_record_from_payload(
            dict(values["decision_record"])
        )
    )
    values["exit_policy"] = _policy_from_payload(
        dict(values["exit_policy"])
    )
    values["stop_threshold"] = MoveThresholdProbability.model_validate(
        values["stop_threshold"]
    )
    values["target_threshold"] = (
        MoveThresholdProbability.model_validate(
            values["target_threshold"]
        )
    )
    values["direction"] = DiscoveryDirection(
        str(values["direction"])
    )
    values["forecast_horizon_unit"] = ForecastHorizonUnit(
        str(values["forecast_horizon_unit"])
    )
    values["opened_utc"] = datetime.fromisoformat(
        str(values["opened_utc"])
    )
    values["plan_created_utc"] = datetime.fromisoformat(
        str(values["plan_created_utc"])
    )
    values["reason_codes"] = tuple(values["reason_codes"])
    return RecurrentDecisionStockExitPlanV1(**values)


def write_recurrent_decision_stock_exit_plan_book_v1(
    settings: AtlasSettings,
    book: RecurrentDecisionStockExitPlanBookV1,
) -> Path:
    path = recurrent_decision_stock_exit_plan_path(settings)
    raw = json.dumps(
        _canonicalize(book),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_recurrent_decision_stock_exit_plan_book_v1(
        settings,
        path=path,
    )
    if restored != book:
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book readback verification mismatch"
        )
    return path


def read_recurrent_decision_stock_exit_plan_book_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> RecurrentDecisionStockExitPlanBookV1:
    target = (
        Path(path)
        if path is not None
        else recurrent_decision_stock_exit_plan_path(settings)
    )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book artifact is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_BUNDLE_BYTES:
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book artifact size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book artifact could not be read"
        ) from exc
    if len(raw) != size:
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book artifact changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book artifact is invalid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book artifact root must be an object"
        )
    try:
        plans = tuple(
            recurrent_decision_stock_exit_plan_from_payload(
                dict(item)
            )
            for item in payload["plans"]
        )
        return RecurrentDecisionStockExitPlanBookV1(
            contract_version=str(payload["contract_version"]),
            contract_fingerprint=str(
                payload["contract_fingerprint"]
            ),
            source_id=str(payload["source_id"]),
            book_fingerprint=str(payload["book_fingerprint"]),
            source_recurrent_state_fingerprint=str(
                payload["source_recurrent_state_fingerprint"]
            ),
            built_at_utc=datetime.fromisoformat(
                str(payload["built_at_utc"])
            ),
            plans=plans,
            provider_reads=int(payload["provider_reads"]),
            provider_writes=int(payload["provider_writes"]),
            broker_reads=int(payload["broker_reads"]),
            broker_writes=int(payload["broker_writes"]),
            price_trigger_authority=bool(
                payload["price_trigger_authority"]
            ),
            close_fill_authority=bool(
                payload["close_fill_authority"]
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
        RecurrentDecisionStockExitPlanError,
    ) as exc:
        if isinstance(
            exc,
            RecurrentDecisionStockExitPlanError,
        ):
            raise
        raise RecurrentDecisionStockExitPlanError(
            "exit-plan book artifact failed typed validation"
        ) from exc


__all__ = [
    "RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT",
    "RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_VERSION",
    "RECURRENT_DECISION_STOCK_EXIT_PLAN_SOURCE_ID",
    "RecurrentDecisionStockExitPlanBookV1",
    "RecurrentDecisionStockExitPlanError",
    "RecurrentDecisionStockExitPlanV1",
    "StockExitPolicyInputsV1",
    "build_recurrent_decision_stock_exit_plan_book_v1",
    "build_recurrent_decision_stock_exit_plan_v1",
    "read_recurrent_decision_stock_exit_plan_book_v1",
    "recurrent_decision_stock_exit_plan_from_payload",
    "recurrent_decision_stock_exit_plan_path",
    "write_recurrent_decision_stock_exit_plan_book_v1",
]
