from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from packages.control_plane.phase16_policy import (
    PHASE16_ACCEPTED_PHASE15_MERGE_SHA,
    PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
    PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY,
    PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED,
    phase16_policy_fingerprint,
)
from packages.control_plane.phase16_smoke import (
    PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION,
    Phase16OperationalSmoke,
)
from packages.control_plane.phase16_validation import (
    PHASE16_ACCEPTED_POLICY_FINGERPRINT,
    PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
    Phase16IndependentValidator,
)
from packages.control_plane.status import Phase16StatusService
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


PHASE16_CLOSEOUT_CONTRACT_VERSION = (
    "phase16-closeout-v1-phase15-bound-independent-validation-loopback-smoke-zero-provider-mutation"
)
PHASE16_NEXT_CHECKPOINT = "PROVIDER_MUTATION_REQUIRES_SEPARATE_EXPLICIT_USER_CHECKPOINT"


class Phase16CloseoutError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _git_head(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip().lower()
    return value if len(value) == 40 and all(ch in "0123456789abcdef" for ch in value) else None


class Phase16Closeout:
    """Accept the Phase 16 control-plane architecture without broker mutation promotion."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.project_root = Path(settings.project_root).resolve()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "control_plane" / "phase16" / "v1"
        self.report_path = self.root / "phase16_final_acceptance.json"
        self.validator = Phase16IndependentValidator(settings)
        self.smoke = Phase16OperationalSmoke(settings)
        self.status_service = Phase16StatusService(settings)

    def run(self) -> dict[str, object]:
        phase15 = self.status_service.phase15_acceptance()
        if not phase15.accepted:
            raise Phase16CloseoutError(
                f"accepted Phase 15 artifact is required: {phase15.error_code}"
            )
        system = self.status_service.system_status()
        records = self.status_service.action_ledger.records()
        provider_write_attempt_count = sum(
            1 for record in records.values() if record.provider_write_attempted
        )
        provider_write_uncertain_count = sum(
            1 for record in records.values() if record.provider_write_uncertain
        )

        validation = self.validator.run(write_report=True)
        smoke = self.smoke.run(refresh_brokers=False, write_report=True)
        git_head = _git_head(self.project_root)

        checks = {
            "phase15_artifact_accepted": phase15.accepted is True,
            "phase15_policy_exact": phase15.policy_fingerprint
            == PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
            "phase15_actual_broker_execution_absent": phase15.actual_broker_execution_exercised is False,
            "phase15_live_execution_not_promoted": phase15.live_execution_promoted is False,
            "phase16_policy_exact": phase16_policy_fingerprint()
            == PHASE16_ACCEPTED_POLICY_FINGERPRINT,
            "independent_validation_contract_exact": validation.get("contract_version")
            == PHASE16_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "independent_validation_pass": validation.get("pass") is True,
            "independent_validation_provider_calls_zero": int(validation.get("provider_calls", -1)) == 0,
            "independent_validation_provider_writes_zero": int(validation.get("provider_writes", -1)) == 0,
            "smoke_contract_exact": smoke.get("contract_version")
            == PHASE16_OPERATIONAL_SMOKE_CONTRACT_VERSION,
            "smoke_pass": smoke.get("pass") is True,
            "smoke_broker_refresh_not_requested": smoke.get("broker_refresh_requested") is False,
            "smoke_provider_factory_calls_zero": int(smoke.get("provider_factory_calls", -1)) == 0,
            "smoke_provider_mutations_zero": int(smoke.get("provider_mutation_endpoint_invocations", -1)) == 0,
            "system_runtime_valid": system.runtime_state_valid is True,
            "system_runtime_audit_binding_valid": system.runtime_audit_binding_valid is True,
            "system_action_ledger_valid": system.action_ledger_valid is True,
            "system_provider_write_uncertain_false": system.provider_write_uncertain is False,
            "active_actions_zero": system.active_action_count == 0,
            "uncertain_actions_zero": system.uncertain_action_count == 0,
            "recorded_provider_write_attempts_zero": provider_write_attempt_count == 0,
            "recorded_provider_write_uncertainty_zero": provider_write_uncertain_count == 0,
            "provider_write_endpoints_absent": system.provider_write_endpoints_present is False,
            "browser_not_execution_authority": PHASE16_BROWSER_CAN_CREATE_EXECUTION_AUTHORITY is False,
            "live_execution_not_promoted": PHASE16_LIVE_EXECUTION_PROMOTION_ALLOWED is False
            and system.live_execution_promoted is False,
            "automatic_failover_disabled": PHASE16_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False
            and system.automatic_cross_broker_failover_allowed is False,
            "git_head_present": git_head is not None,
        }
        failed = tuple(sorted(name for name, value in checks.items() if not value))
        if failed:
            raise Phase16CloseoutError(
                "Phase 16 closeout checks failed: " + ", ".join(failed)
            )

        validation_path = self.validator.report_path
        smoke_path = self.smoke.report_path
        source_payload = {
            "contract_version": PHASE16_CLOSEOUT_CONTRACT_VERSION,
            "git_head_sha": git_head,
            "accepted_phase15_merge_sha": PHASE16_ACCEPTED_PHASE15_MERGE_SHA,
            "accepted_phase15_policy_fingerprint": PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
            "phase16_policy_fingerprint": phase16_policy_fingerprint(),
            "implementation_fingerprint": validation["implementation_fingerprint"],
            "independent_validation_sha256": _sha256_file(validation_path),
            "operational_smoke_sha256": _sha256_file(smoke_path),
            "action_audit_last_event_hash": self.status_service.action_ledger.verify().get("last_event_hash"),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE16_CLOSEOUT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "git_head_sha": git_head,
            "accepted_phase15_merge_sha": PHASE16_ACCEPTED_PHASE15_MERGE_SHA,
            "accepted_phase15_policy_fingerprint": PHASE16_ACCEPTED_PHASE15_POLICY_FINGERPRINT,
            "phase15_as_of_date": phase15.as_of_date,
            "phase16_policy_fingerprint": phase16_policy_fingerprint(),
            "implementation_fingerprint": validation["implementation_fingerprint"],
            "independent_validation_sha256": source_payload["independent_validation_sha256"],
            "operational_smoke_sha256": source_payload["operational_smoke_sha256"],
            "action_audit_last_event_hash": source_payload["action_audit_last_event_hash"],
            "action_count": system.action_count,
            "active_action_count": system.active_action_count,
            "uncertain_action_count": system.uncertain_action_count,
            "provider_read_refresh_exercised_in_acceptance": False,
            "provider_factory_calls": 0,
            "provider_write_attempt_count": provider_write_attempt_count,
            "provider_write_uncertain_count": provider_write_uncertain_count,
            "provider_mutation_endpoint_invocations": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "position_writes": 0,
            "live_writes": 0,
            "checks": checks,
            "final_disposition": {
                "phase16_accepted": True,
                "browser_control_plane_accepted": True,
                "loopback_operational_smoke_accepted": True,
                "broker_switch_local_routing_only": True,
                "cleanup_exact_plan_review_accepted": True,
                "safe_prewrite_abandon_accepted": True,
                "actual_provider_mutation_exercised_in_acceptance": False,
                "cleanup_provider_writes_promoted": False,
                "live_execution_promoted": False,
                "automatic_cross_broker_failover_allowed": False,
                "next_checkpoint": PHASE16_NEXT_CHECKPOINT,
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
