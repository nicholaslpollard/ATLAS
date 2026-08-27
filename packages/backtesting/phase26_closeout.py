from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase26_confirmation import (
    PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE26_SUPPORT_OVERLAY_CONTRACT_VERSION,
    Phase26ProtectedConfirmation,
)
from .phase26_observations import (
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase26_policy import phase26_policy_fingerprint
from .phase26_research import (
    PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase26DevelopmentResearch,
)
from .phase26_runner import (
    PHASE26_CUMULATIVE_REPORT_CONTRACT_VERSION,
    Phase26CumulativeRunner,
)
from .phase26_validation import (
    PHASE26_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
    Phase26IndependentValidator,
)


PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION = "phase26-end-to-end-anti-workaround-audit-v1"
PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION = (
    "phase26-closeout-v1-full-phase-gate-alpha-result-plus-anti-workaround-audit"
)


class Phase26CloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase26CloseoutError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase26CloseoutError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase26CloseoutError(f"{label} must be a JSON object")
    return payload


def _raw_submit_sites(project_root: Path) -> list[str]:
    sites: list[str] = []
    needle = "adapter.submit(plan)"
    for path in sorted((project_root / "packages").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if needle in text:
            relative = path.relative_to(project_root).as_posix()
            sites.extend([relative] * text.count(needle))
    return sites


def _runtime_recovery_import_sites(project_root: Path) -> list[str]:
    """Return runtime modules that import Phase25 research-recovery authority.

    Recovery modules may exist for provenance/rehydration, but they must not become
    callable authority from routine discovery, operations, risk, control-plane, or
    execution code.
    """

    roots = (
        "packages/discovery",
        "packages/operations",
        "packages/portfolio",
        "packages/risk",
        "packages/control_plane",
        "packages/execution",
    )
    forbidden = (
        "phase25_prerequisite_recovery",
        "phase25_gate6_recovery",
        "phase25_gate6_repair",
    )
    sites: list[str] = []
    for root in roots:
        base = project_root / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden):
                sites.append(path.relative_to(project_root).as_posix())
    return sites


def phase26_architecture_audit_checks(project_root: Path) -> dict[str, bool]:
    """Machine-check the highest-risk anti-workaround invariants.

    This does not replace the documented layer-by-layer audit; it locks the critical
    conclusions that can be verified directly from source structure.
    """

    from packages.execution.phase22_operator import (
        PHASE22_AUTOMATIC_BROKER_FAILOVER,
        PHASE22_BROWSER_EXECUTION_ENABLED,
        PHASE22_LIVE_EXECUTION_ENABLED,
        PHASE22_SCHEDULER_EXECUTION_ENABLED,
    )
    from packages.operations.phase23_policy import (
        PHASE23_AUTOMATIC_BROKER_FAILOVER,
        PHASE23_BROKER_MUTATIONS_ALLOWED,
        PHASE23_BROWSER_EXECUTION_ENABLED,
        PHASE23_FROZEN_SUPPORTED_STRATEGIES,
        PHASE23_LIVE_EXECUTION_ENABLED,
        PHASE23_ORDER_WRITES_ALLOWED,
        PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED,
        PHASE23_SCHEDULER_EXECUTION_ENABLED,
    )

    audit_path = project_root / "docs" / "phase26_end_to_end_anti_workaround_audit.md"
    audit_text = audit_path.read_text(encoding="utf-8") if audit_path.is_file() else ""
    control_plane = (project_root / "packages" / "control_plane" / "http_server.py").read_text(
        encoding="utf-8"
    )
    promotion = (project_root / "packages" / "discovery" / "promotion.py").read_text(
        encoding="utf-8"
    )
    phase23_validator = (project_root / "scripts" / "validate_phase23.py").read_text(
        encoding="utf-8"
    )

    return {
        "audit_document_present": audit_path.is_file(),
        "audit_contract_present": PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit_text,
        "audit_disposition_pass": "**Disposition:** PASS" in audit_text,
        "redundant_reference_rebind_removed": not (
            project_root / "packages" / "backtesting" / "phase25_gate6_reference_rebind.py"
        ).exists(),
        "recovery_not_imported_by_runtime_authority": not _runtime_recovery_import_sites(project_root),
        "single_raw_broker_submit_seam": _raw_submit_sites(project_root)
        == ["packages/execution/engine.py"],
        "phase22_live_disabled": PHASE22_LIVE_EXECUTION_ENABLED is False,
        "phase22_automatic_failover_disabled": PHASE22_AUTOMATIC_BROKER_FAILOVER is False,
        "phase22_browser_execution_disabled": PHASE22_BROWSER_EXECUTION_ENABLED is False,
        "phase22_scheduler_execution_disabled": PHASE22_SCHEDULER_EXECUTION_ENABLED is False,
        "phase23_live_disabled": PHASE23_LIVE_EXECUTION_ENABLED is False,
        "phase23_automatic_failover_disabled": PHASE23_AUTOMATIC_BROKER_FAILOVER is False,
        "phase23_browser_execution_disabled": PHASE23_BROWSER_EXECUTION_ENABLED is False,
        "phase23_scheduler_execution_disabled": PHASE23_SCHEDULER_EXECUTION_ENABLED is False,
        "phase23_broker_mutations_disabled": PHASE23_BROKER_MUTATIONS_ALLOWED is False,
        "phase23_order_writes_disabled": PHASE23_ORDER_WRITES_ALLOWED is False,
        "phase23_paper_submit_authority_disabled": PHASE23_PAPER_SUBMIT_AUTHORITY_ALLOWED is False,
        "phase23_supported_strategy_set_still_empty": PHASE23_FROZEN_SUPPORTED_STRATEGIES == (),
        "promotion_requires_historical_support": "NO_HISTORICAL_SUPPORT_RECORD" in promotion
        and "HISTORICALLY_UNSUPPORTED" in promotion
        and "REJECT:NO_SUPPORTED_ROUTED_STRATEGY_FIRED" in promotion,
        "control_plane_has_no_provider_write_endpoint": '"provider_write_endpoints_present": False'
        in control_plane,
        "control_plane_has_no_live_promotion": '"live_execution_promoted": False' in control_plane,
        "phase23_retained_validator_locks_single_submit_seam": "exactly_one_raw_submit_seam_remains"
        in phase23_validator,
    }


def phase26_disposition(supported_candidate_ids: tuple[str, ...]) -> tuple[str, bool]:
    if supported_candidate_ids:
        return "ACCEPTED_POSITIVE", True
    return "ACCEPTED_NEGATIVE", False


class Phase26Closeout:
    """Full Phase26 phase-end acceptance gate over target evidence and architecture audit."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.observations = Phase26ObservationBuilder(settings)
        self.research = Phase26DevelopmentResearch(settings)
        self.confirmation = Phase26ProtectedConfirmation(settings)
        self.validator = Phase26IndependentValidator(settings)
        self.runner = Phase26CumulativeRunner(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase26" / "v1"

    def report_path(self) -> Path:
        return self.root / "phase26_closeout_report.json"

    def run(self) -> dict[str, object]:
        cumulative_path = self.runner.report_path()
        observation_path = self.observations.report_path()
        research_path = self.research.report_path()
        finalist_path = self.research.finalists_path()
        confirmation_path = self.confirmation.report_path()
        support_path = self.confirmation.support_overlay_path()
        validation_path = self.validator.report_path()

        cumulative = _read_json(cumulative_path, "Phase26 cumulative report")
        observation = _read_json(observation_path, "Phase26 observation report")
        research = _read_json(research_path, "Phase26 research report")
        finalists = _read_json(finalist_path, "Phase26 finalists")
        confirmation = _read_json(confirmation_path, "Phase26 confirmation report")
        support = _read_json(support_path, "Phase26 support overlay")
        validation = _read_json(validation_path, "Phase26 independent validation")

        supported = tuple(str(value) for value in validation.get("supported_candidate_ids", []))
        selected = tuple(str(value) for value in research.get("selected_candidate_ids", []))
        finalist_ids = tuple(str(value) for value in research.get("finalist_candidate_ids", []))
        confirmed = tuple(str(value) for value in confirmation.get("confirmed_candidate_ids", []))
        disposition, phase27_entry_satisfied = phase26_disposition(supported)
        architecture_checks = phase26_architecture_audit_checks(self.settings.project_root)

        zero_authority_fields = (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
        )
        cumulative_authority_zero = all(int(cumulative.get(name, -1)) == 0 for name in zero_authority_fields)
        confirmation_authority_zero = all(
            int(confirmation.get(name, -1)) == 0
            for name in (
                "provider_reads",
                "provider_writes",
                "broker_reads",
                "broker_writes",
                "order_writes",
                "paper_submits",
                "live_writes",
            )
        )

        checks = {
            "cumulative_contract": cumulative.get("contract_version")
            == PHASE26_CUMULATIVE_REPORT_CONTRACT_VERSION,
            "observation_contract": observation.get("contract_version")
            == PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
            "research_contract": research.get("contract_version") == PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
            "finalist_contract": finalists.get("contract_version") == PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "confirmation_contract": confirmation.get("contract_version")
            == PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "support_contract": support.get("contract_version") == PHASE26_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "validation_contract": validation.get("contract_version")
            == PHASE26_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "policy_fingerprint_consistent": all(
                payload.get("phase26_policy_fingerprint") == phase26_policy_fingerprint()
                for payload in (cumulative, observation, research, finalists, confirmation, support, validation)
            ),
            "cumulative_pass": cumulative.get("pass") is True,
            "observation_pass": observation.get("pass") is True,
            "research_pass": research.get("pass") is True,
            "confirmation_pass": confirmation.get("pass") is True,
            "independent_validation_pass": validation.get("pass") is True,
            "cumulative_observation_sha": cumulative.get("observation_report_sha256")
            == sha256_file(observation_path),
            "cumulative_research_sha": cumulative.get("research_report_sha256") == sha256_file(research_path),
            "cumulative_confirmation_sha": cumulative.get("confirmation_report_sha256")
            == sha256_file(confirmation_path),
            "cumulative_validation_sha": cumulative.get("independent_validation_sha256")
            == sha256_file(validation_path),
            "research_finalist_sha": research.get("finalists_sha256") == sha256_file(finalist_path),
            "confirmation_support_sha": confirmation.get("support_overlay_sha256") == sha256_file(support_path),
            "selection_relationship_consistent": tuple(
                str(value) for value in cumulative.get("selected_candidate_ids", [])
            )
            == selected,
            "finalist_relationship_consistent": tuple(
                str(value) for value in cumulative.get("finalist_candidate_ids", [])
            )
            == finalist_ids
            == tuple(str(value) for value in finalists.get("finalist_candidate_ids", [])),
            "confirmed_relationship_consistent": tuple(
                str(value) for value in cumulative.get("confirmed_supported_candidate_ids", [])
            )
            == confirmed
            == supported
            == tuple(str(value) for value in support.get("supported_candidate_ids", [])),
            "finalists_subset_selected": set(finalist_ids).issubset(set(selected)),
            "supported_subset_finalists": set(supported).issubset(set(finalist_ids)),
            "zero_finalist_protected_blind": bool(finalist_ids)
            or (
                int(confirmation.get("protected_returns_read", -1)) == 0
                and int(confirmation.get("protected_candidate_rows_read", -1)) == 0
                and confirmation.get("status") == "SKIPPED_ZERO_FINALISTS"
            ),
            "support_is_historical_analytical_only": support.get("authority")
            == "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY",
            "support_has_no_paper_authority": support.get("paper_authority") is False,
            "support_has_no_live_authority": support.get("live_authority") is False,
            "cumulative_external_authority_zero": cumulative_authority_zero,
            "confirmation_external_authority_zero": confirmation_authority_zero,
            "architecture_audit_pass": all(architecture_checks.values()),
            "negative_disposition_blocks_phase27": bool(supported) or not phase27_entry_satisfied,
            "positive_disposition_requires_supported": disposition != "ACCEPTED_POSITIVE" or bool(supported),
        }
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase26CloseoutError("Phase26 closeout failed: " + ", ".join(failed))

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "phase26_disposition": disposition,
            "phase27_entry_satisfied": phase27_entry_satisfied,
            "selected_candidate_ids": list(selected),
            "finalist_candidate_ids": list(finalist_ids),
            "supported_candidate_ids": list(supported),
            "protected_returns_read": int(confirmation.get("protected_returns_read", 0)),
            "development_usable_rows": cumulative.get("development_usable_rows"),
            "protected_predictor_rows": cumulative.get("protected_predictor_rows"),
            "architecture_audit_contract": PHASE26_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
            "architecture_audit_checks": architecture_checks,
            "architecture_audit_pass": True,
            "cumulative_report_sha256": sha256_file(cumulative_path),
            "independent_validation_sha256": sha256_file(validation_path),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
