from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings, load_settings
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    TradeExpressionMode,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
)
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    build_simulation_decision_record,
)
from packages.simulation.recurrent_workstation_acceptance_contract import (
    RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT,
    RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT,
)


RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_VERSION = str(
    RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT["contract_id"]
)
REFERENCE_HORIZON_MINUTES = 1
REFERENCE_THRESHOLD_FRACTION = 0.20
_MAX_RECEIPT_BYTES = 8 * 1024 * 1024


class RecurrentWorkstationAcceptanceError(RuntimeError):
    pass


def workstation_entry_schedule_utc(
    *,
    provider_timestamp_utc: datetime,
    received_at_utc: datetime,
    captured_at_utc: datetime,
) -> datetime:
    provider = _require_aware(
        provider_timestamp_utc,
        label="acceptance provider timestamp",
    )
    received = _require_aware(
        received_at_utc,
        label="acceptance quote receipt time",
    )
    captured = _require_aware(
        captured_at_utc,
        label="acceptance quote capture time",
    )
    if provider > received:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance provider timestamp cannot follow quote receipt"
        )
    if received > captured:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance quote receipt cannot follow bundle capture"
        )
    return received


def workstation_entry_cycle_action_utc(
    *,
    scheduled_for_utc: datetime,
    captured_at_utc: datetime,
) -> datetime:
    scheduled = _require_aware(
        scheduled_for_utc,
        label="acceptance scheduled cycle time",
    )
    captured = _require_aware(
        captured_at_utc,
        label="acceptance quote capture time",
    )
    if captured < scheduled:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance cycle action cannot precede its scheduled slot"
        )
    return captured


def _require_aware(value: datetime, *, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentWorkstationAcceptanceError(
            f"{label} must be timezone-aware"
        )
    return value.astimezone(UTC)


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentWorkstationAcceptanceError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _fingerprint_payload(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def isolated_acceptance_settings(
    *,
    project_root: Path,
    live_root: Path,
) -> AtlasSettings:
    settings = load_settings(project_root)
    configured_live = settings.resolved_path(
        settings.data.paths.live
    ).resolve()
    isolated_live = Path(live_root).expanduser().resolve()
    if isolated_live == configured_live:
        raise RecurrentWorkstationAcceptanceError(
            "workstation acceptance refuses the configured normal live root"
        )
    if isolated_live == project_root.resolve():
        raise RecurrentWorkstationAcceptanceError(
            "workstation acceptance live root cannot be the project root"
        )
    paths = settings.data.paths.model_copy(
        update={"live": isolated_live}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def workstation_acceptance_root(
    settings: AtlasSettings,
) -> Path:
    return settings.resolved_path(
        settings.data.paths.live
    ) / "acceptance"


def workstation_acceptance_context_path(
    settings: AtlasSettings,
) -> Path:
    return workstation_acceptance_root(settings) / "context.json"


def workstation_acceptance_receipt_path(
    settings: AtlasSettings,
) -> Path:
    return workstation_acceptance_root(settings) / "receipt.json"


def workstation_acceptance_stage_path(
    settings: AtlasSettings,
    stage: str,
) -> Path:
    clean = str(stage).strip().lower()
    if clean not in {"entry", "mark", "close", "retry"}:
        raise RecurrentWorkstationAcceptanceError(
            "unsupported workstation acceptance stage"
        )
    return workstation_acceptance_root(settings) / f"{clean}.json"


def write_acceptance_json(
    path: Path,
    payload: dict[str, Any],
) -> Path:
    raw = json.dumps(
        payload,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(Path(path), raw, fsync=True)
    return Path(path)


def read_acceptance_json(path: Path) -> dict[str, Any]:
    target = Path(path)
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentWorkstationAcceptanceError(
            f"acceptance artifact unavailable: {target.name}"
        ) from exc
    if size <= 0 or size > _MAX_RECEIPT_BYTES:
        raise RecurrentWorkstationAcceptanceError(
            f"acceptance artifact size invalid: {target.name}"
        )
    try:
        payload = json.loads(target.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentWorkstationAcceptanceError(
            f"acceptance artifact invalid: {target.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise RecurrentWorkstationAcceptanceError(
            f"acceptance artifact root must be an object: {target.name}"
        )
    return payload


def build_workstation_reference_decision_v1(
    *,
    ticker: str,
    reference_price: float,
    decision_created_utc: datetime,
    evidence_cutoff_utc: datetime,
    position_notional_dollars: float,
) -> SimulationDecisionRecord:
    symbol = str(ticker).strip()
    if not symbol:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance ticker cannot be blank"
        )
    if not math.isfinite(reference_price) or reference_price <= 0.0:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance reference price must be finite and positive"
        )
    if (
        not math.isfinite(position_notional_dollars)
        or position_notional_dollars <= 0.0
    ):
        raise RecurrentWorkstationAcceptanceError(
            "acceptance position notional must be finite and positive"
        )
    created = _require_aware(
        decision_created_utc,
        label="acceptance decision time",
    )
    cutoff = _require_aware(
        evidence_cutoff_utc,
        label="acceptance evidence cutoff",
    )
    if created < cutoff:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance decision cannot predate evidence cutoff"
        )

    threshold = MoveThresholdProbability(
        threshold_fraction=REFERENCE_THRESHOLD_FRACTION,
        favorable_touch_probability=0.50,
        adverse_touch_probability=0.50,
        favorable_before_adverse_probability=0.25,
        adverse_before_favorable_probability=0.25,
        same_interval_collision_probability=0.0,
        median_favorable_time=0.50,
    )
    forecast = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=f"acceptance:{symbol}",
        ticker=symbol,
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=created,
        evidence_cutoff_utc=cutoff,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=REFERENCE_HORIZON_MINUTES,
        method_id="workstation-acceptance-reference-fixture-v1",
        source_label="PRODUCT_ACCEPTANCE_FIXTURE_NOT_STRATEGY_EVIDENCE",
        source_fingerprint=_fingerprint_payload(
            {
                "ticker": symbol,
                "reference_price": reference_price,
                "cutoff": cutoff.isoformat(),
                "horizon_minutes": REFERENCE_HORIZON_MINUTES,
                "threshold_fraction": REFERENCE_THRESHOLD_FRACTION,
            }
        ),
        sample_size=1,
        reference_price=reference_price,
        mean_signed_return=0.001,
        median_signed_return=0.001,
        p10_signed_return=-REFERENCE_THRESHOLD_FRACTION,
        p25_signed_return=-0.01,
        p75_signed_return=0.01,
        p90_signed_return=REFERENCE_THRESHOLD_FRACTION,
        probability_positive_return=0.60,
        mean_mfe=REFERENCE_THRESHOLD_FRACTION,
        mean_mae=REFERENCE_THRESHOLD_FRACTION,
        thresholds=(threshold,),
        uncertainty_score=1.0,
        reason_codes=(
            "PRODUCT_ACCEPTANCE_FIXTURE",
            "NOT_STRATEGY_EVIDENCE",
            "WIDE_PRICE_BAND_FOR_TIME_PATH",
        ),
    )
    return build_simulation_decision_record(
        decision_created_utc=created,
        forecast=forecast,
        stock_inputs=StockEconomicsInputs(
            position_notional_dollars=position_notional_dollars,
            capital_required_dollars=position_notional_dollars,
            entry_slippage_bps=0.0,
            exit_slippage_bps=0.0,
            round_trip_commission_dollars=0.0,
            round_trip_fees_dollars=0.0,
            horizon_borrow_cost_dollars=0.0,
            horizon_financing_cost_dollars=0.0,
            net_probability_profit=0.50,
            liquidity_score=1.0,
            executable=True,
            risk_budget_ok=True,
        ),
        actionability_policy=ActionabilityPolicy(
            min_expected_net_value=0.0,
            min_expected_return_on_capital=0.0,
            min_probability_profit=0.0,
            max_expected_loss_to_gain_ratio=1e12,
            max_execution_cost_to_expected_gain_ratio=1e12,
            min_liquidity_score=0.0,
            material_superiority_ratio=1.0,
        ),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
    )


@dataclass(frozen=True)
class RecurrentWorkstationAcceptanceReceiptV1:
    contract_version: str
    contract_fingerprint: str
    receipt_fingerprint: str
    run_id: str
    ticker: str
    isolated_live_root: str
    initial_equity: float
    entry_fee_dollars: float
    exit_fee_dollars: float
    entry_cycle_id: str
    close_cycle_id: str
    entry_quote_bundle_fingerprint: str
    mark_quote_bundle_fingerprint: str
    close_quote_bundle_fingerprint: str
    decision_record_fingerprint: str
    exit_plan_book_fingerprint: str
    clock_book_fingerprint: str
    time_disposition_bundle_fingerprint: str
    time_aware_close_bundle_fingerprint: str
    final_disposition: str
    final_checkpoint_sha256: str
    final_snapshot_fingerprint: str
    final_revision: int
    closed_trade_count: int
    dashboard_status_after_mark: str
    dashboard_account_state_fingerprint: str
    cycle_health_status_after_retry: str
    accepted_at_utc: str
    provider_read_calls: int

    provider_writes: int = 0
    broker_reads: int = 0
    broker_writes: int = 0
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if (
            self.contract_version
            != RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_VERSION
        ):
            raise RecurrentWorkstationAcceptanceError(
                "acceptance receipt contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentWorkstationAcceptanceError(
                "acceptance receipt contract fingerprint mismatch"
            )
        if not self.run_id.strip() or not self.ticker.strip():
            raise RecurrentWorkstationAcceptanceError(
                "acceptance receipt identity cannot be blank"
            )
        if (
            not math.isfinite(self.initial_equity)
            or self.initial_equity <= 0.0
        ):
            raise RecurrentWorkstationAcceptanceError(
                "acceptance receipt initial equity must be finite and positive"
            )
        for label, value in (
            ("entry fee", self.entry_fee_dollars),
            ("exit fee", self.exit_fee_dollars),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise RecurrentWorkstationAcceptanceError(
                    f"acceptance receipt {label} must be finite and nonnegative"
                )
        try:
            accepted = datetime.fromisoformat(self.accepted_at_utc)
        except ValueError as exc:
            raise RecurrentWorkstationAcceptanceError(
                "acceptance receipt accepted time is invalid"
            ) from exc
        _require_aware(
            accepted,
            label="acceptance receipt accepted time",
        )
        for label, value in (
            ("receipt", self.receipt_fingerprint),
            ("entry quote bundle", self.entry_quote_bundle_fingerprint),
            ("mark quote bundle", self.mark_quote_bundle_fingerprint),
            ("close quote bundle", self.close_quote_bundle_fingerprint),
            ("decision record", self.decision_record_fingerprint),
            ("exit-plan book", self.exit_plan_book_fingerprint),
            ("clock book", self.clock_book_fingerprint),
            ("time disposition", self.time_disposition_bundle_fingerprint),
            ("time-aware CLOSE", self.time_aware_close_bundle_fingerprint),
            ("final checkpoint", self.final_checkpoint_sha256),
            ("final snapshot", self.final_snapshot_fingerprint),
            (
                "dashboard account state",
                self.dashboard_account_state_fingerprint,
            ),
        ):
            _require_sha(value, label=label)
        if self.final_disposition != "TIME":
            raise RecurrentWorkstationAcceptanceError(
                "workstation acceptance requires final TIME disposition"
            )
        if self.closed_trade_count != 1:
            raise RecurrentWorkstationAcceptanceError(
                "workstation acceptance requires exactly one closed trade"
            )
        if self.dashboard_status_after_mark != "AVAILABLE":
            raise RecurrentWorkstationAcceptanceError(
                "workstation acceptance requires AVAILABLE dashboard snapshot"
            )
        if self.cycle_health_status_after_retry != "OPEN_CYCLE":
            raise RecurrentWorkstationAcceptanceError(
                "workstation acceptance requires valid OPEN_CYCLE health after CLOSE retry"
            )
        if self.final_revision < 0 or self.provider_read_calls != 3:
            raise RecurrentWorkstationAcceptanceError(
                "workstation acceptance provider/revision accounting mismatch"
            )
        if any(
            (
                self.provider_writes,
                self.broker_reads,
                self.broker_writes,
                self.order_creation_authority,
                self.paper_authority,
                self.live_authority,
                self.promotion_authority,
                self.confluence_authority,
            )
        ):
            raise RecurrentWorkstationAcceptanceError(
                "acceptance receipt cannot grant external or trading authority"
            )
        payload = asdict(self)
        observed = payload.pop("receipt_fingerprint")
        expected = _fingerprint_payload(payload)
        if observed != expected:
            raise RecurrentWorkstationAcceptanceError(
                "acceptance receipt self-fingerprint mismatch"
            )


def build_workstation_acceptance_receipt_v1(
    **values: Any,
) -> RecurrentWorkstationAcceptanceReceiptV1:
    payload = {
        "contract_version": RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_VERSION,
        "contract_fingerprint": (
            RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT
        ),
        **values,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }
    fingerprint = _fingerprint_payload(payload)
    return RecurrentWorkstationAcceptanceReceiptV1(
        receipt_fingerprint=fingerprint,
        **payload,
    )


def write_workstation_acceptance_receipt_v1(
    settings: AtlasSettings,
    receipt: RecurrentWorkstationAcceptanceReceiptV1,
) -> Path:
    path = workstation_acceptance_receipt_path(settings)
    write_acceptance_json(path, asdict(receipt))
    restored = read_workstation_acceptance_receipt_v1(
        settings,
        path=path,
    )
    if restored != receipt:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance receipt readback mismatch"
        )
    return path


def read_workstation_acceptance_receipt_v1(
    settings: AtlasSettings,
    *,
    path: Path | None = None,
) -> RecurrentWorkstationAcceptanceReceiptV1:
    target = (
        Path(path)
        if path is not None
        else workstation_acceptance_receipt_path(settings)
    )
    payload = read_acceptance_json(target)
    try:
        return RecurrentWorkstationAcceptanceReceiptV1(**payload)
    except (TypeError, ValueError) as exc:
        raise RecurrentWorkstationAcceptanceError(
            "acceptance receipt failed typed validation"
        ) from exc


__all__ = [
    "RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_FINGERPRINT",
    "RECURRENT_WORKSTATION_ACCEPTANCE_CONTRACT_VERSION",
    "REFERENCE_HORIZON_MINUTES",
    "REFERENCE_THRESHOLD_FRACTION",
    "RecurrentWorkstationAcceptanceError",
    "RecurrentWorkstationAcceptanceReceiptV1",
    "workstation_entry_schedule_utc",
    "workstation_entry_cycle_action_utc",
    "build_workstation_acceptance_receipt_v1",
    "build_workstation_reference_decision_v1",
    "isolated_acceptance_settings",
    "read_acceptance_json",
    "read_workstation_acceptance_receipt_v1",
    "workstation_acceptance_context_path",
    "workstation_acceptance_receipt_path",
    "workstation_acceptance_root",
    "workstation_acceptance_stage_path",
    "write_acceptance_json",
    "write_workstation_acceptance_receipt_v1",
]
