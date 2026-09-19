from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.simulation.recurrent_cycle import (
    RecurrentCycleReceiptV1,
    RecurrentCycleStage,
    RecurrentCycleStatus,
    cycle_fingerprint,
    RecurrentCycleStageRecordV1,
    read_recurrent_cycle_receipt,
    recurrent_cycle_receipt_path,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunIdentityV1,
    read_recurrent_cycle_stage_admission,
    recurrent_cycle_stage_admission_path,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanBookV1,
    RecurrentDecisionStockExitPlanError,
    StockExitPolicyInputsV1,
    build_recurrent_decision_stock_exit_plan_book_v1,
    read_recurrent_decision_stock_exit_plan_book_v1,
    write_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_exit_plan_refresh_contract import (
    RECURRENT_EXIT_PLAN_REFRESH_CONTRACT,
    RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_reserve_evidence import (
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT,
    RecurrentReserveEvidenceBundleV1,
)
from packages.simulation.recurrent_runtime import (
    DurableRecurrentLifecycleRuntimeV1,
)


RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_VERSION = str(
    RECURRENT_EXIT_PLAN_REFRESH_CONTRACT["contract_id"]
)
_MAX_RECEIPT_BYTES = 8 * 1024 * 1024
_REQUIRED_STAGES = (
    RecurrentCycleStage.CLOSE,
    RecurrentCycleStage.RESERVE,
    RecurrentCycleStage.ENTRY,
)


class RecurrentExitPlanRefreshError(RuntimeError):
    pass


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentExitPlanRefreshError(
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
class RecurrentExitPlanPolicyBindingV1:
    decision_record_fingerprint: str
    policy_inputs_fingerprint: str

    def __post_init__(self) -> None:
        _require_sha(
            self.decision_record_fingerprint,
            label="refresh policy decision record",
        )
        _require_sha(
            self.policy_inputs_fingerprint,
            label="refresh policy inputs",
        )


def _policy_bindings(
    policies: Mapping[str, StockExitPolicyInputsV1],
) -> tuple[RecurrentExitPlanPolicyBindingV1, ...]:
    return tuple(
        RecurrentExitPlanPolicyBindingV1(
            decision_record_fingerprint=decision_fp,
            policy_inputs_fingerprint=policy.inputs_fingerprint,
        )
        for decision_fp, policy in sorted(policies.items())
    )


def _receipt_payload(
    *,
    cycle_id: str,
    cycle_fingerprint: str,
    entry_stage_record_fingerprint: str,
    entry_stage_admission_sha256: str,
    entry_result_checkpoint_sha256: str,
    entry_result_snapshot_fingerprint: str,
    entry_result_revision: int,
    source_account_state_fingerprint: str,
    reserve_bundle_fingerprint: str | None,
    policy_bindings: tuple[RecurrentExitPlanPolicyBindingV1, ...],
    output_plan_book_fingerprint: str,
    output_plan_count: int,
    effective_at_utc: datetime,
) -> dict[str, object]:
    return {
        "contract_version": RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_VERSION,
        "contract_fingerprint": (
            RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT
        ),
        "cycle_id": cycle_id,
        "cycle_fingerprint": cycle_fingerprint,
        "entry_stage_record_fingerprint": (
            entry_stage_record_fingerprint
        ),
        "entry_stage_admission_sha256": (
            entry_stage_admission_sha256
        ),
        "entry_result_checkpoint_sha256": (
            entry_result_checkpoint_sha256
        ),
        "entry_result_snapshot_fingerprint": (
            entry_result_snapshot_fingerprint
        ),
        "entry_result_revision": entry_result_revision,
        "source_account_state_fingerprint": (
            source_account_state_fingerprint
        ),
        "reserve_bundle_fingerprint": reserve_bundle_fingerprint,
        "policy_bindings": policy_bindings,
        "output_plan_book_fingerprint": (
            output_plan_book_fingerprint
        ),
        "output_plan_count": output_plan_count,
        "effective_at_utc": effective_at_utc,
        "provider_reads": 0,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_creation_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
    }


@dataclass(frozen=True)
class RecurrentExitPlanRefreshReceiptV1:
    contract_version: str
    contract_fingerprint: str
    receipt_sha256: str
    cycle_id: str
    cycle_fingerprint: str
    entry_stage_record_fingerprint: str
    entry_stage_admission_sha256: str
    entry_result_checkpoint_sha256: str
    entry_result_snapshot_fingerprint: str
    entry_result_revision: int
    source_account_state_fingerprint: str
    reserve_bundle_fingerprint: str | None
    policy_bindings: tuple[RecurrentExitPlanPolicyBindingV1, ...]
    output_plan_book_fingerprint: str
    output_plan_count: int
    effective_at_utc: datetime

    provider_reads: int = 0
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
            != RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_VERSION
        ):
            raise RecurrentExitPlanRefreshError(
                "exit-plan refresh contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT
        ):
            raise RecurrentExitPlanRefreshError(
                "exit-plan refresh contract fingerprint mismatch"
            )
        for label, value in (
            ("refresh receipt", self.receipt_sha256),
            ("cycle", self.cycle_fingerprint),
            (
                "ENTRY stage record",
                self.entry_stage_record_fingerprint,
            ),
            (
                "ENTRY stage admission",
                self.entry_stage_admission_sha256,
            ),
            (
                "ENTRY result checkpoint",
                self.entry_result_checkpoint_sha256,
            ),
            (
                "ENTRY result snapshot",
                self.entry_result_snapshot_fingerprint,
            ),
            (
                "source account state",
                self.source_account_state_fingerprint,
            ),
            (
                "output plan book",
                self.output_plan_book_fingerprint,
            ),
        ):
            _require_sha(value, label=label)
        if self.reserve_bundle_fingerprint is not None:
            _require_sha(
                self.reserve_bundle_fingerprint,
                label="reserve bundle",
            )
        if self.entry_result_revision < 0:
            raise RecurrentExitPlanRefreshError(
                "ENTRY result revision cannot be negative"
            )
        if self.output_plan_count < 0:
            raise RecurrentExitPlanRefreshError(
                "output plan count cannot be negative"
            )
        if (
            self.effective_at_utc.tzinfo is None
            or self.effective_at_utc.utcoffset() is None
        ):
            raise RecurrentExitPlanRefreshError(
                "exit-plan refresh effective time must be timezone-aware"
            )
        ordered = tuple(
            sorted(
                self.policy_bindings,
                key=lambda item: item.decision_record_fingerprint,
            )
        )
        if ordered != self.policy_bindings:
            raise RecurrentExitPlanRefreshError(
                "refresh policy bindings must be deterministically ordered"
            )
        decision_ids = tuple(
            item.decision_record_fingerprint
            for item in self.policy_bindings
        )
        if len(decision_ids) != len(set(decision_ids)):
            raise RecurrentExitPlanRefreshError(
                "refresh policy bindings cannot duplicate decisions"
            )
        if any(
            (
                self.provider_reads,
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
            raise RecurrentExitPlanRefreshError(
                "exit-plan refresh cannot grant external or trading authority"
            )
        expected = _fingerprint_payload(
            _receipt_payload(
                cycle_id=self.cycle_id,
                cycle_fingerprint=self.cycle_fingerprint,
                entry_stage_record_fingerprint=(
                    self.entry_stage_record_fingerprint
                ),
                entry_stage_admission_sha256=(
                    self.entry_stage_admission_sha256
                ),
                entry_result_checkpoint_sha256=(
                    self.entry_result_checkpoint_sha256
                ),
                entry_result_snapshot_fingerprint=(
                    self.entry_result_snapshot_fingerprint
                ),
                entry_result_revision=self.entry_result_revision,
                source_account_state_fingerprint=(
                    self.source_account_state_fingerprint
                ),
                reserve_bundle_fingerprint=(
                    self.reserve_bundle_fingerprint
                ),
                policy_bindings=self.policy_bindings,
                output_plan_book_fingerprint=(
                    self.output_plan_book_fingerprint
                ),
                output_plan_count=self.output_plan_count,
                effective_at_utc=self.effective_at_utc,
            )
        )
        if self.receipt_sha256 != expected:
            raise RecurrentExitPlanRefreshError(
                "exit-plan refresh receipt self-fingerprint mismatch"
            )


@dataclass(frozen=True)
class RecurrentExitPlanRefreshResultV1:
    book: RecurrentDecisionStockExitPlanBookV1
    receipt: RecurrentExitPlanRefreshReceiptV1
    book_path: Path
    receipt_path: Path
    idempotent_reuse: bool


def recurrent_exit_plan_refresh_receipt_path(
    checkpoint_path: Path,
    cycle_id: str,
) -> Path:
    cycle_fp = cycle_fingerprint(cycle_id)
    return (
        Path(checkpoint_path).parent
        / "exit_plan_refresh"
        / f"{cycle_fp}.json"
    )


def _validate_cycle_ready_for_refresh(
    *,
    checkpoint_path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    identity: RecurrentCycleRunIdentityV1,
) -> RecurrentCycleReceiptV1:
    path = recurrent_cycle_receipt_path(
        checkpoint_path,
        identity.cycle_id,
    )
    if not path.is_file():
        raise RecurrentExitPlanRefreshError(
            "cycle receipt does not exist"
        )
    receipt = read_recurrent_cycle_receipt(path)
    if (
        receipt.cycle_id != identity.cycle_id
        or receipt.cycle_fingerprint != identity.cycle_fingerprint
    ):
        raise RecurrentExitPlanRefreshError(
            "cycle receipt does not match refresh identity"
        )
    if receipt.status != RecurrentCycleStatus.OPEN:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh requires an open cycle"
        )
    stages = tuple(stage.stage for stage in receipt.stages)
    if stages != _REQUIRED_STAGES:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh requires exactly CLOSE, RESERVE, ENTRY and no MARK"
        )
    status = runtime.status()
    if status.uncertain:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh cannot run while runtime is uncertain"
        )
    if (
        status.checkpoint_sha256 != receipt.current_checkpoint_sha256
        or status.snapshot_fingerprint
        != receipt.current_snapshot_fingerprint
        or status.revision != receipt.current_revision
    ):
        raise RecurrentExitPlanRefreshError(
            "runtime no longer matches the post-ENTRY cycle receipt"
        )
    entry = receipt.stages[-1]
    if (
        entry.result_checkpoint_sha256
        != receipt.current_checkpoint_sha256
        or entry.result_snapshot_fingerprint
        != receipt.current_snapshot_fingerprint
        or entry.result_revision != receipt.current_revision
    ):
        raise RecurrentExitPlanRefreshError(
            "cycle receipt does not terminate at the ENTRY result"
        )
    return receipt


def _read_existing_book_if_present(
    settings: AtlasSettings,
) -> RecurrentDecisionStockExitPlanBookV1 | None:
    path = MarketDataPaths(
        settings
    ).recurrent_decision_stock_exit_plan_file()
    if not path.is_file():
        return None
    return read_recurrent_decision_stock_exit_plan_book_v1(
        settings,
        path=path,
    )


def _validate_recovery_book(
    *,
    book: RecurrentDecisionStockExitPlanBookV1,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    policies: Mapping[str, StockExitPolicyInputsV1],
    expected_effective_at_utc: datetime,
) -> bool:
    state = runtime.current_account().state
    if (
        book.source_recurrent_state_fingerprint
        != state.state_fingerprint
        or book.built_at_utc != expected_effective_at_utc
    ):
        return False
    position_ids = {
        item.position_fingerprint for item in state.open_positions
    }
    plan_ids = {
        item.position_fingerprint for item in book.plans
    }
    if position_ids != plan_ids:
        return False
    policies_by_decision = dict(policies)
    plans_by_decision = {
        plan.decision_record_fingerprint: plan
        for plan in book.plans
    }
    for decision_fp, policy in policies_by_decision.items():
        plan = plans_by_decision.get(decision_fp)
        if plan is None or plan.exit_policy != policy:
            raise RecurrentExitPlanRefreshError(
                "existing current-state plan book conflicts with supplied exit policy"
            )
    return True


def recurrent_exit_plan_entry_stage_record_fingerprint(
    stage: RecurrentCycleStageRecordV1,
) -> str:
    if stage.stage != RecurrentCycleStage.ENTRY:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh stage fingerprint requires ENTRY"
        )
    return _fingerprint_payload(stage)


def _entry_stage_admission_sha(
    *,
    checkpoint_path: Path,
    cycle_id: str,
    entry_stage: RecurrentCycleStageRecordV1,
) -> str:
    admission_path = recurrent_cycle_stage_admission_path(
        checkpoint_path,
        cycle_id,
        RecurrentCycleStage.ENTRY,
    )
    if not admission_path.is_file():
        raise RecurrentExitPlanRefreshError(
            "ENTRY stage admission is unavailable"
        )
    admission = read_recurrent_cycle_stage_admission(
        admission_path
    )
    if (
        admission.cycle_id != cycle_id
        or admission.stage != RecurrentCycleStage.ENTRY
        or admission.source_checkpoint_sha256
        != entry_stage.source_checkpoint_sha256
        or admission.source_snapshot_fingerprint
        != entry_stage.source_snapshot_fingerprint
    ):
        raise RecurrentExitPlanRefreshError(
            "ENTRY stage admission does not match cycle stage lineage"
        )
    return admission.admission_sha256


def _build_refresh_receipt(
    *,
    cycle_receipt: RecurrentCycleReceiptV1,
    checkpoint_path: Path,
    account_state_fingerprint: str,
    reserve_bundle: RecurrentReserveEvidenceBundleV1 | None,
    policies: Mapping[str, StockExitPolicyInputsV1],
    book: RecurrentDecisionStockExitPlanBookV1,
) -> RecurrentExitPlanRefreshReceiptV1:
    entry = cycle_receipt.stages[-1]
    entry_record_fp = (
        recurrent_exit_plan_entry_stage_record_fingerprint(entry)
    )
    entry_admission_sha = _entry_stage_admission_sha(
        checkpoint_path=checkpoint_path,
        cycle_id=cycle_receipt.cycle_id,
        entry_stage=entry,
    )
    bindings = _policy_bindings(policies)
    payload = _receipt_payload(
        cycle_id=cycle_receipt.cycle_id,
        cycle_fingerprint=cycle_receipt.cycle_fingerprint,
        entry_stage_record_fingerprint=entry_record_fp,
        entry_stage_admission_sha256=entry_admission_sha,
        entry_result_checkpoint_sha256=(
            entry.result_checkpoint_sha256
        ),
        entry_result_snapshot_fingerprint=(
            entry.result_snapshot_fingerprint
        ),
        entry_result_revision=entry.result_revision,
        source_account_state_fingerprint=account_state_fingerprint,
        reserve_bundle_fingerprint=(
            None
            if reserve_bundle is None
            else reserve_bundle.bundle_fingerprint
        ),
        policy_bindings=bindings,
        output_plan_book_fingerprint=book.book_fingerprint,
        output_plan_count=len(book.plans),
        effective_at_utc=entry.recorded_at_utc,
    )
    return RecurrentExitPlanRefreshReceiptV1(
        contract_version=RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_VERSION,
        contract_fingerprint=(
            RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT
        ),
        receipt_sha256=_fingerprint_payload(payload),
        cycle_id=cycle_receipt.cycle_id,
        cycle_fingerprint=cycle_receipt.cycle_fingerprint,
        entry_stage_record_fingerprint=entry_record_fp,
        entry_stage_admission_sha256=entry_admission_sha,
        entry_result_checkpoint_sha256=(
            entry.result_checkpoint_sha256
        ),
        entry_result_snapshot_fingerprint=(
            entry.result_snapshot_fingerprint
        ),
        entry_result_revision=entry.result_revision,
        source_account_state_fingerprint=account_state_fingerprint,
        reserve_bundle_fingerprint=(
            None
            if reserve_bundle is None
            else reserve_bundle.bundle_fingerprint
        ),
        policy_bindings=bindings,
        output_plan_book_fingerprint=book.book_fingerprint,
        output_plan_count=len(book.plans),
        effective_at_utc=entry.recorded_at_utc,
    )


def write_recurrent_exit_plan_refresh_receipt(
    path: Path,
    receipt: RecurrentExitPlanRefreshReceiptV1,
) -> None:
    raw = json.dumps(
        _canonicalize(receipt),
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ) + "\n"
    atomic_write_text(path, raw, fsync=True)
    restored = read_recurrent_exit_plan_refresh_receipt(path)
    if restored != receipt:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh receipt readback mismatch"
        )


def read_recurrent_exit_plan_refresh_receipt(
    path: Path,
) -> RecurrentExitPlanRefreshReceiptV1:
    target = Path(path)
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh receipt is unavailable"
        ) from exc
    if size <= 0 or size > _MAX_RECEIPT_BYTES:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh receipt size is invalid"
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh receipt could not be read"
        ) from exc
    if len(raw) != size:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh receipt changed while reading"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh receipt is invalid JSON"
        ) from exc
    try:
        bindings = tuple(
            RecurrentExitPlanPolicyBindingV1(
                decision_record_fingerprint=str(
                    item["decision_record_fingerprint"]
                ),
                policy_inputs_fingerprint=str(
                    item["policy_inputs_fingerprint"]
                ),
            )
            for item in payload["policy_bindings"]
        )
        return RecurrentExitPlanRefreshReceiptV1(
            contract_version=str(payload["contract_version"]),
            contract_fingerprint=str(
                payload["contract_fingerprint"]
            ),
            receipt_sha256=str(payload["receipt_sha256"]),
            cycle_id=str(payload["cycle_id"]),
            cycle_fingerprint=str(payload["cycle_fingerprint"]),
            entry_stage_record_fingerprint=str(
                payload["entry_stage_record_fingerprint"]
            ),
            entry_stage_admission_sha256=str(
                payload["entry_stage_admission_sha256"]
            ),
            entry_result_checkpoint_sha256=str(
                payload["entry_result_checkpoint_sha256"]
            ),
            entry_result_snapshot_fingerprint=str(
                payload["entry_result_snapshot_fingerprint"]
            ),
            entry_result_revision=int(
                payload["entry_result_revision"]
            ),
            source_account_state_fingerprint=str(
                payload["source_account_state_fingerprint"]
            ),
            reserve_bundle_fingerprint=(
                None
                if payload.get("reserve_bundle_fingerprint") is None
                else str(payload["reserve_bundle_fingerprint"])
            ),
            policy_bindings=bindings,
            output_plan_book_fingerprint=str(
                payload["output_plan_book_fingerprint"]
            ),
            output_plan_count=int(payload["output_plan_count"]),
            effective_at_utc=datetime.fromisoformat(
                str(payload["effective_at_utc"])
            ),
            provider_reads=int(payload["provider_reads"]),
            provider_writes=int(payload["provider_writes"]),
            broker_reads=int(payload["broker_reads"]),
            broker_writes=int(payload["broker_writes"]),
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
        RecurrentExitPlanRefreshError,
    ) as exc:
        if isinstance(exc, RecurrentExitPlanRefreshError):
            raise
        raise RecurrentExitPlanRefreshError(
            "exit-plan refresh receipt failed typed validation"
        ) from exc


def refresh_recurrent_exit_plans_after_entry_v1(
    *,
    settings: AtlasSettings,
    checkpoint_path: Path,
    runtime: DurableRecurrentLifecycleRuntimeV1,
    identity: RecurrentCycleRunIdentityV1,
    current_reserve_bundle: RecurrentReserveEvidenceBundleV1 | None,
    exit_policy_by_decision: Mapping[str, StockExitPolicyInputsV1],
) -> RecurrentExitPlanRefreshResultV1:
    checkpoint = Path(checkpoint_path)
    cycle_receipt = _validate_cycle_ready_for_refresh(
        checkpoint_path=checkpoint,
        runtime=runtime,
        identity=identity,
    )
    if current_reserve_bundle is not None:
        if (
            current_reserve_bundle.contract_fingerprint
            != RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentExitPlanRefreshError(
                "refresh reserve bundle contract fingerprint mismatch"
            )
        if (
            current_reserve_bundle.cycle_id != identity.cycle_id
            or current_reserve_bundle.cycle_fingerprint
            != identity.cycle_fingerprint
        ):
            raise RecurrentExitPlanRefreshError(
                "refresh reserve bundle belongs to a different cycle"
            )
        reserve_admission_path = recurrent_cycle_stage_admission_path(
            checkpoint,
            identity.cycle_id,
            RecurrentCycleStage.RESERVE,
        )
        if not reserve_admission_path.is_file():
            raise RecurrentExitPlanRefreshError(
                "refresh reserve stage admission is unavailable"
            )
        reserve_admission = read_recurrent_cycle_stage_admission(
            reserve_admission_path
        )
        if (
            reserve_admission.cycle_id != identity.cycle_id
            or reserve_admission.stage != RecurrentCycleStage.RESERVE
            or reserve_admission.evidence_source_fingerprint
            != current_reserve_bundle.bundle_fingerprint
        ):
            raise RecurrentExitPlanRefreshError(
                "refresh reserve bundle does not match admitted RESERVE evidence"
            )

    receipt_path = recurrent_exit_plan_refresh_receipt_path(
        checkpoint,
        identity.cycle_id,
    )
    book_path = MarketDataPaths(
        settings
    ).recurrent_decision_stock_exit_plan_file()

    if receipt_path.is_file():
        receipt = read_recurrent_exit_plan_refresh_receipt(
            receipt_path
        )
        expected_bindings = _policy_bindings(
            exit_policy_by_decision
        )
        expected_reserve = (
            None
            if current_reserve_bundle is None
            else current_reserve_bundle.bundle_fingerprint
        )
        if (
            receipt.cycle_id != identity.cycle_id
            or receipt.cycle_fingerprint
            != identity.cycle_fingerprint
            or receipt.entry_stage_record_fingerprint
            != recurrent_exit_plan_entry_stage_record_fingerprint(
                cycle_receipt.stages[-1]
            )
            or receipt.entry_stage_admission_sha256
            != _entry_stage_admission_sha(
                checkpoint_path=checkpoint,
                cycle_id=identity.cycle_id,
                entry_stage=cycle_receipt.stages[-1],
            )
            or receipt.effective_at_utc
            != cycle_receipt.stages[-1].recorded_at_utc
            or receipt.reserve_bundle_fingerprint
            != expected_reserve
            or receipt.policy_bindings != expected_bindings
        ):
            raise RecurrentExitPlanRefreshError(
                "exit-plan refresh was already recorded with different evidence"
            )
        if not book_path.is_file():
            raise RecurrentExitPlanRefreshError(
                "recorded exit-plan refresh is missing its output book"
            )
        book = read_recurrent_decision_stock_exit_plan_book_v1(
            settings,
            path=book_path,
        )
        state = runtime.current_account().state
        if (
            receipt.source_account_state_fingerprint
            != state.state_fingerprint
            or receipt.output_plan_book_fingerprint
            != book.book_fingerprint
            or receipt.output_plan_count != len(book.plans)
            or book.source_recurrent_state_fingerprint
            != state.state_fingerprint
            or book.built_at_utc != receipt.effective_at_utc
        ):
            raise RecurrentExitPlanRefreshError(
                "recorded exit-plan refresh output no longer matches current state"
            )
        return RecurrentExitPlanRefreshResultV1(
            book=book,
            receipt=receipt,
            book_path=book_path,
            receipt_path=receipt_path,
            idempotent_reuse=True,
        )

    existing_book = _read_existing_book_if_present(settings)
    if (
        existing_book is not None
        and _validate_recovery_book(
            book=existing_book,
            runtime=runtime,
            policies=exit_policy_by_decision,
            expected_effective_at_utc=(
                cycle_receipt.stages[-1].recorded_at_utc
            ),
        )
    ):
        book = existing_book
    else:
        try:
            book = build_recurrent_decision_stock_exit_plan_book_v1(
                source_state=runtime.current_account().state,
                current_reserve_bundle=current_reserve_bundle,
                existing_book=existing_book,
                exit_policy_by_decision=exit_policy_by_decision,
                built_at_utc=cycle_receipt.stages[-1].recorded_at_utc,
            )
        except RecurrentDecisionStockExitPlanError as exc:
            raise RecurrentExitPlanRefreshError(
                "post-ENTRY exit-plan book construction failed"
            ) from exc
        write_recurrent_decision_stock_exit_plan_book_v1(
            settings,
            book,
        )

    receipt = _build_refresh_receipt(
        cycle_receipt=cycle_receipt,
        checkpoint_path=checkpoint,
        account_state_fingerprint=(
            runtime.current_account().state.state_fingerprint
        ),
        reserve_bundle=current_reserve_bundle,
        policies=exit_policy_by_decision,
        book=book,
    )
    write_recurrent_exit_plan_refresh_receipt(
        receipt_path,
        receipt,
    )
    return RecurrentExitPlanRefreshResultV1(
        book=book,
        receipt=receipt,
        book_path=book_path,
        receipt_path=receipt_path,
        idempotent_reuse=False,
    )


__all__ = [
    "RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT",
    "RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_VERSION",
    "RecurrentExitPlanPolicyBindingV1",
    "RecurrentExitPlanRefreshError",
    "RecurrentExitPlanRefreshReceiptV1",
    "RecurrentExitPlanRefreshResultV1",
    "read_recurrent_exit_plan_refresh_receipt",
    "recurrent_exit_plan_entry_stage_record_fingerprint",
    "recurrent_exit_plan_refresh_receipt_path",
    "refresh_recurrent_exit_plans_after_entry_v1",
    "write_recurrent_exit_plan_refresh_receipt",
]
