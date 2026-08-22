from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.execution.phase15_foundation import (
    PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
    PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
)
from packages.execution.phase15_policy import (
    PHASE15_AUTOMATIC_BROKER_FAILOVER,
    PHASE15_LIVE_EXECUTION_ENABLED,
    PHASE15_OUTCOME_LEARNING_CAN_CHANGE_STRATEGY_SUPPORT,
    PHASE15_OUTCOME_LEARNING_CAN_CHANGE_THRESHOLDS,
    PHASE15_OUTCOME_LEARNING_CAN_PROMOTE_MODEL,
    phase15_policy_fingerprint,
)
from packages.execution.phase15_run import (
    PHASE15_NO_CASE_DISPOSITION,
    Phase15ExecutionRunEngine,
)
from packages.execution.phase15_source import Phase15ExecutionInputResolver
from packages.execution.phase15_validation import Phase15IndependentValidator
from packages.features.partition_store import sha256_file


PHASE15_CLOSEOUT_CONTRACT_VERSION = (
    "phase15-closeout-v1-cumulative-bound-zero-execution-independent-validation"
)
PHASE15_NEXT_PHASE = "PHASE_16_BROWSER_CONTROL_PLANE_PRODUCTION_OPERATIONS"


class Phase15CloseoutError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase15_acceptance_checks(
    *,
    execution_input: object,
    manifest: dict[str, object],
    validation: dict[str, object],
) -> dict[str, bool]:
    foundation = execution_input.cumulative_foundation
    validation_checks = dict(validation.get("checks") or {})
    return {
        "cumulative_foundation_fingerprint_exact": foundation.foundation_fingerprint
        == PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
        "cumulative_policy_fingerprint_exact": foundation.policy_fingerprint
        == PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
        "cumulative_acceptance_hash_present": len(foundation.acceptance_sha256) == 64,
        "cumulative_validation_hash_present": len(foundation.validation_sha256) == 64,
        "phase15_policy_fingerprint_exact": manifest.get("policy_fingerprint")
        == phase15_policy_fingerprint(),
        "execution_manifest_pass": manifest.get("pass") is True,
        "independent_validation_pass": validation.get("pass") is True,
        "input_reverified": validation_checks.get("accepted_phase14_input_reverified") is True,
        "policy_reverified": validation_checks.get("preregistered_policy_exact") is True,
        "zero_case_noop_reverified": validation_checks.get("zero_case_noop_is_valid") is True,
        "execution_cases_zero": execution_input.execution_case_count == 0
        and int(manifest.get("execution_case_count", -1)) == 0,
        "no_case_disposition_exact": manifest.get("no_case_disposition")
        == PHASE15_NO_CASE_DISPOSITION,
        "quote_source_not_initialized": manifest.get("quote_source_initialized") is False
        and int(manifest.get("quote_reads", -1)) == 0,
        "broker_not_initialized": manifest.get("broker_initialized") is False,
        "provider_submissions_zero": int(manifest.get("provider_submission_attempts", -1)) == 0,
        "broker_writes_zero": int(manifest.get("known_broker_writes", -1)) == 0
        and int(validation.get("known_broker_writes", -1)) == 0,
        "order_writes_zero": int(manifest.get("known_order_writes", -1)) == 0
        and int(validation.get("known_order_writes", -1)) == 0,
        "write_uncertainty_zero": int(manifest.get("unknown_write_record_count", -1)) == 0
        and int(validation.get("unknown_write_record_count", -1)) == 0,
        "production_ml_writes_zero": int(manifest.get("production_ml_writes", -1)) == 0
        and int(validation.get("production_ml_writes", -1)) == 0,
        "live_writes_zero": int(manifest.get("live_writes", -1)) == 0
        and int(validation.get("live_writes", -1)) == 0,
        "execution_absent_in_acceptance": manifest.get("execution_present") is False,
        "automatic_failover_absent": manifest.get("automatic_broker_failover_performed") is False
        and PHASE15_AUTOMATIC_BROKER_FAILOVER is False,
        "live_execution_not_promoted": PHASE15_LIVE_EXECUTION_ENABLED is False,
        "outcome_learning_descriptive_only": PHASE15_OUTCOME_LEARNING_CAN_PROMOTE_MODEL is False
        and PHASE15_OUTCOME_LEARNING_CAN_CHANGE_STRATEGY_SUPPORT is False
        and PHASE15_OUTCOME_LEARNING_CAN_CHANGE_THRESHOLDS is False,
    }


class Phase15Closeout:
    """Accept Phase 15 architecture without crossing the user's execution checkpoint."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase15ExecutionInputResolver(settings)
        self.engine = Phase15ExecutionRunEngine(settings)
        self.validator = Phase15IndependentValidator(settings)
        self.root = self.engine.root
        self.report_path = self.root / "phase15_final_acceptance.json"

    def run(
        self,
        *,
        as_of_date: date | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        execution_input = self.input_resolver.resolve(as_of_date)
        if progress is not None:
            progress(
                f"accepted cumulative foundation: {execution_input.cumulative_foundation.foundation_fingerprint}"
            )
            progress(
                f"accepted Phase 14 execution cases: {execution_input.execution_case_count} on {execution_input.as_of_date}"
            )
        if execution_input.execution_case_count != 0:
            raise Phase15CloseoutError(
                "Phase 15 closeout will not submit or shadow-execute nonzero cases without an explicit execution checkpoint"
            )

        manifest = self.engine.run(
            as_of_date=execution_input.as_of_date,
            environment=None,
            broker=None,
            progress=progress,
        )
        if manifest.get("pass") is not True:
            raise Phase15CloseoutError("Phase 15 zero-case execution manifest failed")

        if progress is not None:
            progress("independent validator: recomputing Phase 15 lineage, write counts, and no-op semantics")
        validation = self.validator.run(as_of_date=execution_input.as_of_date)
        if validation.get("pass") is not True:
            raise Phase15CloseoutError("Phase 15 independent validation failed")

        checks = phase15_acceptance_checks(
            execution_input=execution_input,
            manifest=manifest,
            validation=validation,
        )
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase15CloseoutError("Phase 15 closeout checks failed: " + ", ".join(failed))

        manifest_path = self.engine.manifest_path(execution_input.as_of_date)
        source_payload = {
            "contract_version": PHASE15_CLOSEOUT_CONTRACT_VERSION,
            "as_of_date": execution_input.as_of_date.isoformat(),
            "cumulative_foundation_fingerprint": execution_input.cumulative_foundation.foundation_fingerprint,
            "cumulative_acceptance_sha256": execution_input.cumulative_foundation.acceptance_sha256,
            "cumulative_validation_sha256": execution_input.cumulative_foundation.validation_sha256,
            "phase14_acceptance_sha256": execution_input.phase14_acceptance_sha256,
            "phase15_input_fingerprint": execution_input.source_fingerprint,
            "phase15_policy_fingerprint": phase15_policy_fingerprint(),
            "phase15_manifest_sha256": sha256_file(manifest_path),
            "phase15_validation_sha256": sha256_file(self.validator.report_path),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE15_CLOSEOUT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": execution_input.as_of_date.isoformat(),
            "cumulative_foundation_fingerprint": execution_input.cumulative_foundation.foundation_fingerprint,
            "cumulative_policy_fingerprint": execution_input.cumulative_foundation.policy_fingerprint,
            "cumulative_acceptance_sha256": execution_input.cumulative_foundation.acceptance_sha256,
            "cumulative_validation_sha256": execution_input.cumulative_foundation.validation_sha256,
            "phase14_acceptance_sha256": execution_input.phase14_acceptance_sha256,
            "phase15_input_fingerprint": execution_input.source_fingerprint,
            "phase15_policy_fingerprint": phase15_policy_fingerprint(),
            "phase15_manifest_sha256": source_payload["phase15_manifest_sha256"],
            "phase15_validation_sha256": source_payload["phase15_validation_sha256"],
            "execution_case_count": 0,
            "record_count": int(manifest.get("record_count", 0)),
            "quote_source_initialized": bool(manifest.get("quote_source_initialized")),
            "quote_reads": int(manifest.get("quote_reads", 0)),
            "broker_initialized": bool(manifest.get("broker_initialized")),
            "provider_submission_attempts": int(manifest.get("provider_submission_attempts", 0)),
            "broker_writes": int(manifest.get("known_broker_writes", 0)),
            "order_writes": int(manifest.get("known_order_writes", 0)),
            "unknown_write_record_count": int(manifest.get("unknown_write_record_count", 0)),
            "production_ml_writes": 0,
            "live_writes": 0,
            "execution_present": False,
            "zero_case_noop": True,
            "checks": checks,
            "final_disposition": {
                "phase15_accepted": True,
                "cumulative_foundation_is_execution_prerequisite": True,
                "broker_neutral_shadow_paper_architecture_accepted": True,
                "actual_broker_execution_exercised_in_acceptance": False,
                "live_execution_promoted": False,
                "automatic_cross_broker_failover_allowed": False,
                "outcome_learning_is_descriptive_only": True,
                "next_phase": PHASE15_NEXT_PHASE,
            },
            "pass": True,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        report["report_path"] = str(self.report_path.resolve())
        return report
