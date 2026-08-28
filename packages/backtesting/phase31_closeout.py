from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .phase31_policy import (
    PHASE31_AUTOMATION_WRITES,
    PHASE31_AUTOMATIC_BROKER_FAILOVER,
    PHASE31_BROKER_READS,
    PHASE31_BROKER_WRITES,
    PHASE31_LIVE_WRITES,
    PHASE31_ORDER_WRITES,
    PHASE31_PAPER_SUBMITS,
    PHASE31_PROVIDER_WRITES,
    PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED,
    phase31_policy_fingerprint,
)
from .phase31_validation import (
    PHASE31_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
    Phase31IndependentNegativeValidator,
)


PHASE31_CLOSEOUT_REPORT_CONTRACT_VERSION = (
    "phase31-closeout-v1-sec-form4-insider-alpha-accepted-negative-protected-unread"
)
PHASE31_ARCHITECTURE_AUDIT_CONTRACT_VERSION = "phase31-end-to-end-anti-workaround-audit-v1"


class Phase31CloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase31CloseoutError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31CloseoutError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase31CloseoutError(f"{label} must be a JSON object")
    return payload


def phase31_disposition(finalist_ids: tuple[str, ...]) -> tuple[str, bool]:
    if finalist_ids:
        return "PENDING_PROTECTED_CONFIRMATION", False
    return "ACCEPTED_NEGATIVE", False


def _runtime_phase31_import_sites(project_root: Path) -> list[str]:
    roots = (
        "packages/discovery",
        "packages/operations",
        "packages/portfolio",
        "packages/risk",
        "packages/control_plane",
        "packages/execution",
    )
    sites: list[str] = []
    for root in roots:
        base = project_root / root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            text = path.read_text(encoding="utf-8").lower()
            for line in text.splitlines():
                stripped = line.lstrip()
                if (stripped.startswith("import ") or stripped.startswith("from ")) and "phase31" in line:
                    sites.append(path.relative_to(project_root).as_posix())
                    break
    return sites


def phase31_architecture_audit_checks(project_root: Path) -> dict[str, bool]:
    audit_path = project_root / "docs" / "phase31_end_to_end_anti_workaround_audit.md"
    audit_text = audit_path.read_text(encoding="utf-8") if audit_path.is_file() else ""
    validation_path = project_root / "packages" / "backtesting" / "phase31_validation.py"
    validation_text = validation_path.read_text(encoding="utf-8") if validation_path.is_file() else ""
    development_path = project_root / "packages" / "backtesting" / "phase31_development.py"
    development_text = development_path.read_text(encoding="utf-8") if development_path.is_file() else ""
    external_values = (
        PHASE31_PROVIDER_WRITES,
        PHASE31_BROKER_READS,
        PHASE31_BROKER_WRITES,
        PHASE31_ORDER_WRITES,
        PHASE31_PAPER_SUBMITS,
        PHASE31_LIVE_WRITES,
        PHASE31_AUTOMATION_WRITES,
    )
    return {
        "audit_document_present": audit_path.is_file(),
        "audit_contract_present": PHASE31_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit_text,
        "audit_disposition_pass": "**Disposition:** PASS" in audit_text,
        "phase31_not_imported_by_runtime_authority": not _runtime_phase31_import_sites(project_root),
        "external_mutation_authority_zero": all(value == 0 for value in external_values),
        "automatic_broker_failover_disabled": PHASE31_AUTOMATIC_BROKER_FAILOVER is False,
        "runner_up_substitution_disabled": PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "independent_validator_does_not_import_development": "from .phase31_development" not in validation_text
        and "import phase31_development" not in validation_text,
        "independent_validator_hash_binds_protected_without_parsing": "sha256_file(protected_path)" in validation_text
        and "read_parquet({sql_string(protected_path)" not in validation_text,
        "development_protected_rows_hardcoded_zero": '"protected_candidate_rows_read": 0' in development_text
        and '"protected_return_rows_read": 0' in development_text
        and '"protected_holdout_consumed": False' in development_text,
    }


class Phase31Closeout:
    """Full Phase31 negative phase-end gate. Never reads protected candidate outcomes."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.validator = Phase31IndependentNegativeValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase31" / "v1"
        self.development_root = self.root / "development"

    def predictor_report_path(self) -> Path:
        return self.root / "predictors" / "predictor_report.json"

    def development_report_path(self) -> Path:
        return self.development_root / "development_study.json"

    def finalists_path(self) -> Path:
        return self.development_root / "finalists.json"

    def report_path(self) -> Path:
        return self.root / "phase31_closeout_report.json"

    def run(self) -> dict[str, Any]:
        predictor = _read_json(self.predictor_report_path(), "Phase31 predictor report")
        development = _read_json(self.development_report_path(), "Phase31 development report")
        finalists = _read_json(self.finalists_path(), "Phase31 finalist artifact")
        validation = _read_json(self.validator.report_path(), "Phase31 independent validation")

        finalist_ids = tuple(str(value) for value in development.get("finalist_ids", []))
        disposition, phase32_entry_satisfied = phase31_disposition(finalist_ids)
        if disposition != "ACCEPTED_NEGATIVE":
            raise Phase31CloseoutError(
                "Phase31 closeout may not finalize a nonempty finalist set without protected confirmation"
            )

        zero_fields = (
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
            "automation_writes",
        )
        external_zero = all(
            int(payload.get(field, -1)) == 0
            for payload in (predictor, development, validation)
            for field in zero_fields
        )
        architecture_checks = phase31_architecture_audit_checks(self.settings.project_root)
        protected_execution_root = self.root / "protected_confirmation"
        mandatory_failures = validation.get("mandatory_sample_gate_failures", {})
        metric_matches = validation.get("exact_metric_matches", {})

        checks = {
            "predictor_pass": predictor.get("pass") is True,
            "development_pass": development.get("pass") is True,
            "independent_validation_contract": validation.get("contract_version")
            == PHASE31_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "independent_validation_pass": validation.get("pass") is True,
            "policy_fingerprint_consistent": all(
                payload.get("phase31_policy_fingerprint") == phase31_policy_fingerprint()
                for payload in (predictor, development, finalists, validation)
            ),
            "independent_mandatory_sample_gate_negative_proof": validation.get("status")
            == "PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF"
            and isinstance(mandatory_failures, dict)
            and len(mandatory_failures) == 4
            and all(bool(value) for value in mandatory_failures.values()),
            "independent_sample_metrics_exact": isinstance(metric_matches, dict)
            and len(metric_matches) == 4
            and all(bool(value) for value in metric_matches.values()),
            "selection_survivors_empty": development.get("selection_survivor_ids") == []
            and validation.get("selection_survivor_ids") == [],
            "selection_winners_empty": development.get("selection_winner_ids") == []
            and validation.get("selection_winner_ids") == [],
            "finalists_empty": development.get("finalist_ids") == []
            and finalists.get("finalist_ids") == []
            and finalists.get("finalists") == []
            and validation.get("finalist_ids") == [],
            "protected_candidate_rows_unread": int(
                development.get("protected_candidate_rows_read", -1)
            )
            == 0
            and int(finalists.get("protected_candidate_rows_read", -1)) == 0
            and int(validation.get("protected_candidate_rows_read", -1)) == 0,
            "protected_returns_unread": int(predictor.get("protected_return_rows_read", -1)) == 0
            and int(development.get("protected_return_rows_read", -1)) == 0
            and int(finalists.get("protected_returns_read", -1)) == 0
            and int(validation.get("protected_return_rows_read", -1)) == 0,
            "protected_holdout_unconsumed": development.get("protected_holdout_consumed") is False
            and finalists.get("protected_holdout_consumed") is False
            and validation.get("protected_holdout_consumed") is False,
            "no_protected_confirmation_artifacts": not protected_execution_root.exists(),
            "external_activity_zero": external_zero,
            "architecture_audit_pass": all(architecture_checks.values()),
            "negative_disposition_blocks_phase32": phase32_entry_satisfied is False,
            "live_still_disabled": PHASE31_LIVE_WRITES == 0,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31CloseoutError("Phase31 closeout failed: " + ", ".join(failed))

        report: dict[str, Any] = {
            "contract_version": PHASE31_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase31_policy_fingerprint": phase31_policy_fingerprint(),
            "phase31_disposition": disposition,
            "phase32_entry_satisfied": phase32_entry_satisfied,
            "development_predictor_rows": int(
                development.get("development_target_rows_read", 0)
            ),
            "development_usable_outcome_rows": int(
                development.get("development_usable_outcome_rows", 0)
            ),
            "outcome_path_exclusions": development.get("outcome_path_exclusions"),
            "selection_survivor_ids": [],
            "selection_winner_ids": [],
            "finalist_ids": [],
            "supported_candidate_ids": [],
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "independent_validation_status": validation.get("status"),
            "independent_reconstructed_selection": validation.get("reconstructed_selection"),
            "architecture_audit_contract": PHASE31_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
            "architecture_audit_checks": architecture_checks,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(self.report_path().resolve()),
            "pass": True,
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
