from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .phase30_policy import (
    PHASE30_AUTOMATION_WRITES,
    PHASE30_AUTOMATIC_BROKER_FAILOVER,
    PHASE30_BROKER_READS,
    PHASE30_BROKER_WRITES,
    PHASE30_LIVE_WRITES,
    PHASE30_ORDER_WRITES,
    PHASE30_PAPER_SUBMITS,
    PHASE30_PROVIDER_WRITES,
    PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED,
    phase30_policy_fingerprint,
)
from .phase30_validation import (
    PHASE30_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
    Phase30IndependentNegativeValidator,
)


PHASE30_CLOSEOUT_REPORT_CONTRACT_VERSION = (
    "phase30-closeout-v1-event-driven-public-information-accepted-negative-protected-unread"
)
PHASE30_ARCHITECTURE_AUDIT_CONTRACT_VERSION = "phase30-end-to-end-anti-workaround-audit-v1"


class Phase30CloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase30CloseoutError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase30CloseoutError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase30CloseoutError(f"{label} must be a JSON object")
    return payload


def phase30_disposition(finalist_ids: tuple[str, ...]) -> tuple[str, bool]:
    if finalist_ids:
        return "PENDING_PROTECTED_CONFIRMATION", False
    return "ACCEPTED_NEGATIVE", False


def _runtime_phase30_import_sites(project_root: Path) -> list[str]:
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
                if (stripped.startswith("import ") or stripped.startswith("from ")) and "phase30" in line:
                    sites.append(path.relative_to(project_root).as_posix())
                    break
    return sites


def phase30_architecture_audit_checks(project_root: Path) -> dict[str, bool]:
    audit_path = project_root / "docs" / "phase30_end_to_end_anti_workaround_audit.md"
    audit_text = audit_path.read_text(encoding="utf-8") if audit_path.is_file() else ""
    validation_path = project_root / "packages" / "backtesting" / "phase30_validation.py"
    validation_text = validation_path.read_text(encoding="utf-8") if validation_path.is_file() else ""
    development_path = project_root / "packages" / "backtesting" / "phase30_development.py"
    development_text = development_path.read_text(encoding="utf-8") if development_path.is_file() else ""
    future_doc = project_root / "docs" / "future_news_sentiment_and_option_fair_value.md"
    future_text = future_doc.read_text(encoding="utf-8") if future_doc.is_file() else ""
    external_values = (
        PHASE30_PROVIDER_WRITES,
        PHASE30_BROKER_READS,
        PHASE30_BROKER_WRITES,
        PHASE30_ORDER_WRITES,
        PHASE30_PAPER_SUBMITS,
        PHASE30_LIVE_WRITES,
        PHASE30_AUTOMATION_WRITES,
    )
    return {
        "audit_document_present": audit_path.is_file(),
        "audit_contract_present": PHASE30_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit_text,
        "audit_disposition_pass": "**Disposition:** PASS" in audit_text,
        "phase30_not_imported_by_runtime_authority": not _runtime_phase30_import_sites(project_root),
        "external_mutation_authority_zero": all(value == 0 for value in external_values),
        "automatic_broker_failover_disabled": PHASE30_AUTOMATIC_BROKER_FAILOVER is False,
        "runner_up_substitution_disabled": PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "independent_validator_does_not_import_development": "from .phase30_development" not in validation_text
        and "import phase30_development" not in validation_text,
        "development_protected_rows_hardcoded_zero": '"protected_candidate_rows_read": 0' in development_text
        and '"protected_return_rows_read": 0' in development_text
        and '"protected_holdout_consumed": False' in development_text,
        "future_sentiment_document_explicitly_does_not_alter_phase30": "does not alter the frozen phase30" in future_text.lower(),
    }


class Phase30Closeout:
    """Full Phase30 negative phase-end gate. Never reads protected candidate outcomes."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.validator = Phase30IndependentNegativeValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase30" / "v1"
        self.development_root = self.root / "development"

    def predictor_report_path(self) -> Path:
        return self.root / "predictors" / "predictor_report.json"

    def development_report_path(self) -> Path:
        return self.development_root / "development_study.json"

    def finalists_path(self) -> Path:
        return self.development_root / "finalists.json"

    def report_path(self) -> Path:
        return self.root / "phase30_closeout_report.json"

    def run(self) -> dict[str, Any]:
        predictor = _read_json(self.predictor_report_path(), "Phase30 predictor report")
        development = _read_json(self.development_report_path(), "Phase30 development report")
        finalists = _read_json(self.finalists_path(), "Phase30 finalist artifact")
        validation = _read_json(self.validator.report_path(), "Phase30 independent validation")

        finalist_ids = tuple(str(value) for value in development.get("finalist_ids", []))
        disposition, phase31_entry_satisfied = phase30_disposition(finalist_ids)
        if disposition != "ACCEPTED_NEGATIVE":
            raise Phase30CloseoutError(
                "Phase30 closeout may not finalize a nonempty finalist set without protected confirmation"
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
        architecture_checks = phase30_architecture_audit_checks(self.settings.project_root)
        protected_execution_root = self.root / "protected_confirmation"

        checks = {
            "predictor_pass": predictor.get("pass") is True,
            "development_pass": development.get("pass") is True,
            "independent_validation_contract": validation.get("contract_version")
            == PHASE30_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "independent_validation_pass": validation.get("pass") is True,
            "policy_fingerprint_consistent": all(
                payload.get("phase30_policy_fingerprint") == phase30_policy_fingerprint()
                for payload in (predictor, development, finalists, validation)
            ),
            "independent_sample_gate_negative_proof": validation.get("status")
            == "PASS_NEGATIVE_SAMPLE_GATE_PROOF"
            and all(
                bool(value)
                for value in dict(validation.get("mandatory_sample_gate_failures", {})).values()
            ),
            "selection_survivors_empty": development.get("selection_survivor_ids") == []
            and validation.get("selection_survivor_ids") == [],
            "selection_winners_empty": development.get("selection_winner_ids") == []
            and validation.get("selection_winner_ids") == [],
            "finalists_empty": development.get("finalist_ids") == []
            and finalists.get("finalist_ids") == []
            and finalists.get("finalists") == []
            and validation.get("finalist_ids") == [],
            "protected_candidate_rows_unread": int(development.get("protected_candidate_rows_read", -1)) == 0
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
            "negative_disposition_blocks_phase31": phase31_entry_satisfied is False,
            "live_still_disabled": PHASE30_LIVE_WRITES == 0,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase30CloseoutError("Phase30 closeout failed: " + ", ".join(failed))

        report: dict[str, Any] = {
            "contract_version": PHASE30_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase30_policy_fingerprint": phase30_policy_fingerprint(),
            "phase30_disposition": disposition,
            "phase31_entry_satisfied": phase31_entry_satisfied,
            "development_population_rows": int(development.get("development_population_rows", 0)),
            "development_population_tickers": int(development.get("development_population_tickers", 0)),
            "development_population_sessions": int(development.get("development_population_sessions", 0)),
            "selection_survivor_ids": [],
            "selection_winner_ids": [],
            "finalist_ids": [],
            "supported_candidate_ids": [],
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "independent_validation_status": validation.get("status"),
            "independent_reconstructed_selection": validation.get("reconstructed_selection"),
            "architecture_audit_contract": PHASE30_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
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
        atomic_write_text(
            self.report_path(), json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        return report
