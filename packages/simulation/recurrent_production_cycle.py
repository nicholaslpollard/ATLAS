from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from packages.core.settings import AtlasSettings
from packages.execution.current_webull_decision_stock_close import (
    CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT,
    CurrentWebullDecisionStockCloseEvidenceBundleV1,
    apply_current_webull_decision_stock_close_evidence_bundle_v1,
)
from packages.execution.current_webull_stock_entry import (
    CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT,
    CurrentWebullStockEntryEvidenceBundleV1,
    apply_current_webull_stock_entry_evidence_bundle_v1,
)
from packages.execution.current_webull_stock_mark_adapter import (
    CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT,
    CurrentWebullStockMarkBatchV1,
)
from packages.simulation.recurrent_cycle import (
    RecurrentCycleReceiptV1,
    RecurrentCycleStage,
    RecurrentCycleStatus,
    read_recurrent_cycle_receipt,
    recurrent_cycle_receipt_path,
)
from packages.simulation.recurrent_cycle_runner import (
    RecurrentCycleRunIdentityV1,
    RecurrentCycleRunnerV1,
    read_recurrent_cycle_stage_admission,
    recurrent_cycle_stage_admission_path,
)
from packages.simulation.recurrent_decision_exit_plan import (
    RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentDecisionStockExitPlanError,
    StockExitPolicyInputsV1,
    read_recurrent_decision_stock_exit_plan_book_v1,
)
from packages.simulation.recurrent_exit_plan_refresh import (
    RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT,
    RecurrentExitPlanRefreshError,
    RecurrentExitPlanRefreshResultV1,
    read_recurrent_exit_plan_refresh_receipt,
    recurrent_exit_plan_entry_stage_record_fingerprint,
    recurrent_exit_plan_refresh_receipt_path,
    refresh_recurrent_exit_plans_after_entry_v1,
)
from packages.simulation.recurrent_production_cycle_contract import (
    RECURRENT_PRODUCTION_CYCLE_CONTRACT,
    RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_reserve_evidence import (
    RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT,
    RecurrentReserveEvidenceBundleV1,
    apply_recurrent_reserve_evidence_bundle_v1,
)


RECURRENT_PRODUCTION_CYCLE_CONTRACT_VERSION = str(
    RECURRENT_PRODUCTION_CYCLE_CONTRACT["contract_id"]
)
CURRENT_WEBULL_STOCK_MARK_SOURCE_ID = (
    "atlas-simulation-current-webull-stock-mark-adapter-v1"
)
EMPTY_PRODUCTION_MARK_SOURCE_ID = (
    "atlas-simulation-recurrent-production-empty-mark-v1"
)
_REQUIRED_PRE_MARK_STAGES = (
    RecurrentCycleStage.CLOSE,
    RecurrentCycleStage.RESERVE,
    RecurrentCycleStage.ENTRY,
)


class RecurrentProductionCycleError(RuntimeError):
    pass


def _require_sha(value: str, *, label: str) -> None:
    if (
        len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise RecurrentProductionCycleError(
            f"{label} must be a SHA-256 fingerprint"
        )


def _require_identity(
    *,
    cycle_id: str,
    cycle_fingerprint: str,
    identity: RecurrentCycleRunIdentityV1,
    label: str,
) -> None:
    if (
        cycle_id != identity.cycle_id
        or cycle_fingerprint != identity.cycle_fingerprint
    ):
        raise RecurrentProductionCycleError(
            f"{label} is bound to a different recurrent cycle"
        )


@dataclass
class RecurrentProductionCycleV1:
    settings: AtlasSettings
    runner: RecurrentCycleRunnerV1
    identity: RecurrentCycleRunIdentityV1

    def __post_init__(self) -> None:
        if (
            RECURRENT_EXIT_PLAN_REFRESH_CONTRACT_FINGERPRINT
            != "7cf394ab6ba2fd3dc7e506a7718acb9f90ff647a55ed7b68c0a6a5f4eade2abc"
        ):
            raise RecurrentProductionCycleError(
                "post-ENTRY exit-plan refresh contract mismatch"
            )

    @classmethod
    def restore(
        cls,
        *,
        settings: AtlasSettings,
        checkpoint_path: Path,
        identity: RecurrentCycleRunIdentityV1,
    ) -> "RecurrentProductionCycleV1":
        return cls(
            settings=settings,
            runner=RecurrentCycleRunnerV1.restore(
                Path(checkpoint_path)
            ),
            identity=identity,
        )

    @property
    def checkpoint_path(self) -> Path:
        return Path(self.runner.checkpoint_path)

    def _receipt(self) -> RecurrentCycleReceiptV1:
        path = recurrent_cycle_receipt_path(
            self.checkpoint_path,
            self.identity.cycle_id,
        )
        if not path.is_file():
            raise RecurrentProductionCycleError(
                "production cycle has not been begun"
            )
        receipt = read_recurrent_cycle_receipt(path)
        _require_identity(
            cycle_id=receipt.cycle_id,
            cycle_fingerprint=receipt.cycle_fingerprint,
            identity=self.identity,
            label="cycle receipt",
        )
        return receipt

    @staticmethod
    def _stages(
        receipt: RecurrentCycleReceiptV1,
    ) -> tuple[RecurrentCycleStage, ...]:
        return tuple(stage.stage for stage in receipt.stages)

    def _stage_recorded(
        self,
        stage: RecurrentCycleStage,
    ) -> bool:
        receipt = self._receipt()
        return stage in self._stages(receipt)

    def begin(
        self,
        *,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        _path, receipt = self.runner.begin(
            identity=self.identity,
            now_utc=now_utc,
        )
        return receipt

    def apply_close(
        self,
        *,
        bundle: CurrentWebullDecisionStockCloseEvidenceBundleV1,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        if (
            bundle.contract_fingerprint
            != CURRENT_WEBULL_DECISION_STOCK_CLOSE_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentProductionCycleError(
                "production CLOSE bundle contract fingerprint mismatch"
            )
        _require_identity(
            cycle_id=bundle.cycle_id,
            cycle_fingerprint=bundle.cycle_fingerprint,
            identity=self.identity,
            label="production CLOSE bundle",
        )
        if not self._stage_recorded(RecurrentCycleStage.CLOSE):
            current_state = self.runner.runtime.current_account().state
            if (
                bundle.source_recurrent_state_fingerprint
                != current_state.state_fingerprint
            ):
                raise RecurrentProductionCycleError(
                    "production CLOSE bundle is stale for current recurrent state"
                )
        return apply_current_webull_decision_stock_close_evidence_bundle_v1(
            runner=self.runner,
            identity=self.identity,
            bundle=bundle,
            now_utc=now_utc,
        )

    def apply_reserve(
        self,
        *,
        bundle: RecurrentReserveEvidenceBundleV1,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        if (
            bundle.contract_fingerprint
            != RECURRENT_RESERVE_EVIDENCE_BUNDLE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentProductionCycleError(
                "production RESERVE bundle contract fingerprint mismatch"
            )
        _require_identity(
            cycle_id=bundle.cycle_id,
            cycle_fingerprint=bundle.cycle_fingerprint,
            identity=self.identity,
            label="production RESERVE bundle",
        )
        return apply_recurrent_reserve_evidence_bundle_v1(
            runner=self.runner,
            identity=self.identity,
            bundle=bundle,
            now_utc=now_utc,
        )

    def apply_entry(
        self,
        *,
        bundle: CurrentWebullStockEntryEvidenceBundleV1,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        if (
            bundle.contract_fingerprint
            != CURRENT_WEBULL_STOCK_ENTRY_EVIDENCE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentProductionCycleError(
                "production ENTRY bundle contract fingerprint mismatch"
            )
        _require_identity(
            cycle_id=bundle.cycle_id,
            cycle_fingerprint=bundle.cycle_fingerprint,
            identity=self.identity,
            label="production ENTRY bundle",
        )
        if not self._stage_recorded(RecurrentCycleStage.ENTRY):
            current_state = self.runner.runtime.current_account().state
            if (
                bundle.source_recurrent_state_fingerprint
                != current_state.state_fingerprint
            ):
                raise RecurrentProductionCycleError(
                    "production ENTRY bundle is stale for current recurrent state"
                )
            reserve_admission_path = (
                recurrent_cycle_stage_admission_path(
                    self.checkpoint_path,
                    self.identity.cycle_id,
                    RecurrentCycleStage.RESERVE,
                )
            )
            if not reserve_admission_path.is_file():
                raise RecurrentProductionCycleError(
                    "production ENTRY requires admitted RESERVE evidence"
                )
            reserve_admission = read_recurrent_cycle_stage_admission(
                reserve_admission_path
            )
            if (
                reserve_admission.cycle_id
                != self.identity.cycle_id
                or reserve_admission.stage
                != RecurrentCycleStage.RESERVE
                or reserve_admission.evidence_source_fingerprint
                != bundle.reserve_bundle_fingerprint
            ):
                raise RecurrentProductionCycleError(
                    "production ENTRY does not bind the admitted RESERVE bundle"
                )
        return apply_current_webull_stock_entry_evidence_bundle_v1(
            runner=self.runner,
            identity=self.identity,
            bundle=bundle,
            now_utc=now_utc,
        )

    def refresh_exit_plans(
        self,
        *,
        reserve_bundle: RecurrentReserveEvidenceBundleV1,
        exit_policy_by_decision: Mapping[
            str,
            StockExitPolicyInputsV1,
        ],
    ) -> RecurrentExitPlanRefreshResultV1:
        try:
            return refresh_recurrent_exit_plans_after_entry_v1(
                settings=self.settings,
                checkpoint_path=self.checkpoint_path,
                runtime=self.runner.runtime,
                identity=self.identity,
                current_reserve_bundle=reserve_bundle,
                exit_policy_by_decision=exit_policy_by_decision,
            )
        except RecurrentExitPlanRefreshError as exc:
            raise RecurrentProductionCycleError(
                "production post-ENTRY exit-plan refresh failed"
            ) from exc

    def _require_recorded_refresh_for_mark(
        self,
        *,
        reserve_bundle: RecurrentReserveEvidenceBundleV1,
        exit_policy_by_decision: Mapping[
            str,
            StockExitPolicyInputsV1,
        ],
    ) -> None:
        cycle_receipt = self._receipt()
        if len(cycle_receipt.stages) < 3:
            raise RecurrentProductionCycleError(
                "production MARK requires completed ENTRY"
            )
        if tuple(
            stage.stage for stage in cycle_receipt.stages[:3]
        ) != _REQUIRED_PRE_MARK_STAGES:
            raise RecurrentProductionCycleError(
                "production MARK has invalid pre-MARK stage lineage"
            )
        entry_stage = cycle_receipt.stages[2]
        receipt_path = recurrent_exit_plan_refresh_receipt_path(
            self.checkpoint_path,
            self.identity.cycle_id,
        )
        if not receipt_path.is_file():
            raise RecurrentProductionCycleError(
                "production MARK requires durable post-ENTRY exit-plan refresh receipt"
            )
        refresh_receipt = read_recurrent_exit_plan_refresh_receipt(
            receipt_path
        )
        _require_identity(
            cycle_id=refresh_receipt.cycle_id,
            cycle_fingerprint=refresh_receipt.cycle_fingerprint,
            identity=self.identity,
            label="exit-plan refresh receipt",
        )
        expected_entry_fp = (
            recurrent_exit_plan_entry_stage_record_fingerprint(
                entry_stage
            )
        )
        if (
            refresh_receipt.entry_stage_record_fingerprint
            != expected_entry_fp
        ):
            raise RecurrentProductionCycleError(
                "production MARK refresh receipt does not bind current ENTRY stage"
            )
        entry_admission_path = recurrent_cycle_stage_admission_path(
            self.checkpoint_path,
            self.identity.cycle_id,
            RecurrentCycleStage.ENTRY,
        )
        if not entry_admission_path.is_file():
            raise RecurrentProductionCycleError(
                "production MARK is missing ENTRY stage admission"
            )
        entry_admission = read_recurrent_cycle_stage_admission(
            entry_admission_path
        )
        if (
            refresh_receipt.entry_stage_admission_sha256
            != entry_admission.admission_sha256
        ):
            raise RecurrentProductionCycleError(
                "production MARK refresh receipt does not bind ENTRY admission"
            )
        if (
            refresh_receipt.entry_result_checkpoint_sha256
            != entry_stage.result_checkpoint_sha256
            or refresh_receipt.entry_result_snapshot_fingerprint
            != entry_stage.result_snapshot_fingerprint
            or refresh_receipt.entry_result_revision
            != entry_stage.result_revision
        ):
            raise RecurrentProductionCycleError(
                "production MARK refresh receipt does not bind ENTRY result"
            )
        if (
            reserve_bundle.bundle_fingerprint
            != refresh_receipt.reserve_bundle_fingerprint
        ):
            raise RecurrentProductionCycleError(
                "production MARK reserve bundle differs from refresh lineage"
            )
        expected_policy_bindings = tuple(
            sorted(
                (
                    decision_fp,
                    policy.inputs_fingerprint,
                )
                for decision_fp, policy
                in exit_policy_by_decision.items()
            )
        )
        actual_policy_bindings = tuple(
            (
                item.decision_record_fingerprint,
                item.policy_inputs_fingerprint,
            )
            for item in refresh_receipt.policy_bindings
        )
        if actual_policy_bindings != expected_policy_bindings:
            raise RecurrentProductionCycleError(
                "production MARK exit policy differs from refresh lineage"
            )
        state = self.runner.runtime.current_account().state
        if (
            refresh_receipt.source_account_state_fingerprint
            != state.state_fingerprint
        ):
            raise RecurrentProductionCycleError(
                "production MARK refresh state does not match current account"
            )
        try:
            book = read_recurrent_decision_stock_exit_plan_book_v1(
                self.settings
            )
        except RecurrentDecisionStockExitPlanError as exc:
            raise RecurrentProductionCycleError(
                "production MARK exit-plan book is unavailable or invalid"
            ) from exc
        if (
            book.contract_fingerprint
            != RECURRENT_DECISION_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        ):
            raise RecurrentProductionCycleError(
                "production MARK exit-plan book contract mismatch"
            )
        if (
            book.book_fingerprint
            != refresh_receipt.output_plan_book_fingerprint
            or len(book.plans)
            != refresh_receipt.output_plan_count
            or book.source_recurrent_state_fingerprint
            != state.state_fingerprint
            or book.built_at_utc != refresh_receipt.effective_at_utc
        ):
            raise RecurrentProductionCycleError(
                "production MARK exit-plan book does not match refresh receipt"
            )

    def apply_mark(
        self,
        *,
        reserve_bundle: RecurrentReserveEvidenceBundleV1,
        exit_policy_by_decision: Mapping[
            str,
            StockExitPolicyInputsV1,
        ],
        mark_batch: CurrentWebullStockMarkBatchV1 | None,
        valuation_utc: datetime,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        receipt = self._receipt()
        mark_recorded = (
            RecurrentCycleStage.MARK in self._stages(receipt)
        )
        if not mark_recorded:
            self.refresh_exit_plans(
                reserve_bundle=reserve_bundle,
                exit_policy_by_decision=exit_policy_by_decision,
            )
        self._require_recorded_refresh_for_mark(
            reserve_bundle=reserve_bundle,
            exit_policy_by_decision=exit_policy_by_decision,
        )

        positions = tuple(
            self.runner.runtime.current_account().state.open_positions
        )
        if positions:
            if mark_batch is None:
                raise RecurrentProductionCycleError(
                    "open production positions require current Webull stock-mark evidence"
                )
            if (
                mark_batch.contract_fingerprint
                != CURRENT_WEBULL_STOCK_MARK_ADAPTER_CONTRACT_FINGERPRINT
            ):
                raise RecurrentProductionCycleError(
                    "production MARK batch contract fingerprint mismatch"
                )
            if mark_batch.valuation_utc != valuation_utc:
                raise RecurrentProductionCycleError(
                    "production MARK valuation does not match Webull mark batch"
                )
            expected_positions = {
                position.position_fingerprint
                for position in positions
            }
            marked_positions = {
                mark.position_fingerprint
                for mark in mark_batch.marks
            }
            if marked_positions != expected_positions:
                missing = sorted(
                    expected_positions - marked_positions
                )
                extra = sorted(
                    marked_positions - expected_positions
                )
                raise RecurrentProductionCycleError(
                    "production MARK coverage must exactly match open positions; "
                    f"missing={missing}, extra={extra}"
                )
            if mark_recorded:
                mark_admission = read_recurrent_cycle_stage_admission(
                    recurrent_cycle_stage_admission_path(
                        self.checkpoint_path,
                        self.identity.cycle_id,
                        RecurrentCycleStage.MARK,
                    )
                )
                if (
                    mark_admission.evidence_source_id
                    != CURRENT_WEBULL_STOCK_MARK_SOURCE_ID
                    or mark_admission.evidence_source_fingerprint
                    != mark_batch.batch_fingerprint
                    or mark_admission.action_context
                    != valuation_utc.isoformat()
                ):
                    raise RecurrentProductionCycleError(
                        "recorded production MARK differs from supplied Webull mark evidence"
                    )
                return receipt
            return self.runner.apply_mark(
                identity=self.identity,
                evidence_source_id=(
                    CURRENT_WEBULL_STOCK_MARK_SOURCE_ID
                ),
                evidence_source_fingerprint=(
                    mark_batch.batch_fingerprint
                ),
                marks=mark_batch.marks,
                valuation_utc=valuation_utc,
                now_utc=now_utc,
            )

        if mark_batch is not None:
            raise RecurrentProductionCycleError(
                "zero-position production MARK must be provider-inert"
            )
        _require_sha(
            RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT,
            label="production-cycle contract",
        )
        if mark_recorded:
            mark_admission = read_recurrent_cycle_stage_admission(
                recurrent_cycle_stage_admission_path(
                    self.checkpoint_path,
                    self.identity.cycle_id,
                    RecurrentCycleStage.MARK,
                )
            )
            if (
                mark_admission.evidence_source_id
                != EMPTY_PRODUCTION_MARK_SOURCE_ID
                or mark_admission.evidence_source_fingerprint
                != RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
                or mark_admission.action_context
                != valuation_utc.isoformat()
            ):
                raise RecurrentProductionCycleError(
                    "recorded empty production MARK differs from supplied valuation"
                )
            return receipt
        return self.runner.apply_mark(
            identity=self.identity,
            evidence_source_id=EMPTY_PRODUCTION_MARK_SOURCE_ID,
            evidence_source_fingerprint=(
                RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT
            ),
            marks=(),
            valuation_utc=valuation_utc,
            now_utc=now_utc,
        )

    def complete(
        self,
        *,
        now_utc: datetime | None = None,
    ) -> RecurrentCycleReceiptV1:
        receipt = self._receipt()
        if receipt.status == RecurrentCycleStatus.COMPLETE:
            return receipt
        if RecurrentCycleStage.MARK not in self._stages(receipt):
            raise RecurrentProductionCycleError(
                "production cycle cannot complete before MARK"
            )
        return self.runner.complete(
            identity=self.identity,
            now_utc=now_utc,
        )


__all__ = [
    "EMPTY_PRODUCTION_MARK_SOURCE_ID",
    "RECURRENT_PRODUCTION_CYCLE_CONTRACT_FINGERPRINT",
    "RECURRENT_PRODUCTION_CYCLE_CONTRACT_VERSION",
    "RecurrentProductionCycleError",
    "RecurrentProductionCycleV1",
]
