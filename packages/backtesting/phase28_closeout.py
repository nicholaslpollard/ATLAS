from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase27_closeout import phase27_architecture_audit_checks
from .phase28_blindness import (
    PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase28ProtectedBlindnessAudit,
)
from .phase28_confirmation import (
    PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE28_SUPPORT_OVERLAY_CONTRACT_VERSION,
    Phase28ProtectedConfirmation,
)
from .phase28_policy import (
    PHASE28_AUTOMATION_WRITES,
    PHASE28_AUTOMATIC_BROKER_FAILOVER,
    PHASE28_BROKER_READS,
    PHASE28_BROKER_WRITES,
    PHASE28_LIVE_WRITES,
    PHASE28_ORDER_WRITES,
    PHASE28_PAPER_SUBMITS,
    PHASE28_PROVIDER_READS,
    PHASE28_PROVIDER_WRITES,
    PHASE28_RUNNER_UP_SUBSTITUTION_ALLOWED,
    phase28_policy_fingerprint,
)
from .phase28_population import (
    PHASE28_POPULATION_REPORT_CONTRACT_VERSION,
    Phase28PopulationBuilder,
)
from .phase28_research import (
    PHASE28_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE28_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase28DevelopmentResearch,
)
from .phase28_runner import (
    PHASE28_CUMULATIVE_REPORT_CONTRACT_VERSION,
    Phase28CumulativeRunner,
)
from .phase28_validation import (
    PHASE28_VALIDATION_CONTRACT_VERSION,
    Phase28IndependentValidator,
)


PHASE28_ARCHITECTURE_AUDIT_CONTRACT_VERSION = "phase28-end-to-end-anti-workaround-audit-v1"
PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION = (
    "phase28-closeout-v1-full-phase-gate-network-alpha-result-plus-anti-workaround-audit"
)


class Phase28CloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase28CloseoutError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase28CloseoutError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase28CloseoutError(f"{label} must be a JSON object")
    return payload


def _runtime_phase28_import_sites(project_root: Path) -> list[str]:
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
            text = path.read_text(encoding="utf-8")
            import_lines = [
                line
                for line in text.splitlines()
                if (line.lstrip().startswith("import ") or line.lstrip().startswith("from "))
                and "phase28" in line.lower()
            ]
            if import_lines:
                sites.append(path.relative_to(project_root).as_posix())
    return sites


def phase28_architecture_audit_checks(project_root: Path) -> dict[str, bool]:
    inherited = phase27_architecture_audit_checks(project_root)
    audit_path = project_root / "docs" / "phase28_end_to_end_anti_workaround_audit.md"
    audit_text = audit_path.read_text(encoding="utf-8") if audit_path.is_file() else ""
    confirmation_path = project_root / "packages" / "backtesting" / "phase28_confirmation.py"
    confirmation_text = confirmation_path.read_text(encoding="utf-8") if confirmation_path.is_file() else ""
    research_path = project_root / "packages" / "backtesting" / "phase28_research.py"
    research_text = research_path.read_text(encoding="utf-8") if research_path.is_file() else ""
    validation_path = project_root / "packages" / "backtesting" / "phase28_validation.py"
    validation_text = validation_path.read_text(encoding="utf-8") if validation_path.is_file() else ""
    external_values = (
        PHASE28_PROVIDER_READS,
        PHASE28_PROVIDER_WRITES,
        PHASE28_BROKER_READS,
        PHASE28_BROKER_WRITES,
        PHASE28_ORDER_WRITES,
        PHASE28_PAPER_SUBMITS,
        PHASE28_LIVE_WRITES,
        PHASE28_AUTOMATION_WRITES,
    )
    read_plan_call = confirmation_text.find("self._ensure_read_plan(")
    outcome_join_call = confirmation_text.find("self._join_outcomes(query_keys)")
    return {
        "phase27_architecture_invariants_still_pass": all(inherited.values()),
        "audit_document_present": audit_path.is_file(),
        "audit_contract_present": PHASE28_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit_text,
        "audit_disposition_pass": "**Disposition:** PASS" in audit_text,
        "phase28_not_imported_by_runtime_authority": not _runtime_phase28_import_sites(project_root),
        "phase28_external_authority_zero": all(value == 0 for value in external_values),
        "phase28_automatic_broker_failover_disabled": PHASE28_AUTOMATIC_BROKER_FAILOVER is False,
        "phase28_runner_up_substitution_disabled": PHASE28_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_read_plan_precedes_outcome_join": read_plan_call >= 0
        and outcome_join_call > read_plan_call,
        "zero_finalist_confirmation_path_present": "SKIPPED_ZERO_FINALISTS" in confirmation_text
        and "if not finalist_entries:" in confirmation_text,
        "research_has_no_post_result_tuning_loop": "tune_hyperparameters" not in research_text,
        "independent_validator_does_not_import_phase28_network": "from .phase28_network" not in validation_text,
        "independent_validator_rebuilds_network_sample": "_network_sample_reconciliation(" in validation_text,
    }


def phase28_disposition(supported_candidate_ids: tuple[str, ...]) -> tuple[str, bool]:
    if supported_candidate_ids:
        return "ACCEPTED_POSITIVE", True
    return "ACCEPTED_NEGATIVE", False


class Phase28Closeout:
    """Full Phase28 phase-end acceptance gate over persisted target evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase28PopulationBuilder(settings)
        self.research = Phase28DevelopmentResearch(settings)
        self.blindness = Phase28ProtectedBlindnessAudit(settings)
        self.confirmation = Phase28ProtectedConfirmation(settings)
        self.validator = Phase28IndependentValidator(settings)
        self.runner = Phase28CumulativeRunner(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase28" / "v1"

    def report_path(self) -> Path:
        return self.root / "phase28_closeout_report.json"

    def run(self) -> dict[str, object]:
        population_path = self.population.report_path()
        research_path = self.research.report_path()
        finalists_path = self.research.finalists_path()
        blindness_path = self.blindness.report_path()
        confirmation_path = self.confirmation.report_path()
        support_path = self.confirmation.support_overlay_path()
        validation_path = self.validator.report_path()
        cumulative_path = self.runner.report_path()

        population = _read_json(population_path, "Phase28 population report")
        research = _read_json(research_path, "Phase28 research report")
        finalists = _read_json(finalists_path, "Phase28 finalists")
        blindness = _read_json(blindness_path, "Phase28 blindness audit")
        confirmation = _read_json(confirmation_path, "Phase28 confirmation report")
        support = _read_json(support_path, "Phase28 support overlay")
        validation = _read_json(validation_path, "Phase28 independent validation")
        cumulative = _read_json(cumulative_path, "Phase28 cumulative report")

        survivors = tuple(str(value) for value in research.get("selection_survivor_ids", []))
        winners = tuple(str(value) for value in research.get("selection_winner_ids", []))
        finalist_ids = tuple(str(value) for value in research.get("finalist_ids", []))
        confirmed = tuple(str(value) for value in confirmation.get("confirmed_candidate_ids", []))
        supported = tuple(str(value) for value in validation.get("supported_candidate_ids", []))
        disposition, phase29_entry_satisfied = phase28_disposition(supported)
        architecture_checks = phase28_architecture_audit_checks(self.settings.project_root)

        zero_fields = (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
        )
        external_zero = all(
            int(payload.get(field, -1)) == 0
            for payload in (population, research, blindness, confirmation, cumulative)
            for field in zero_fields
        )
        no_finalist_holdout_preserved = bool(finalist_ids) or (
            confirmation.get("status") == "SKIPPED_ZERO_FINALISTS"
            and int(confirmation.get("protected_candidate_rows_read", -1)) == 0
            and int(confirmation.get("protected_returns_read", -1)) == 0
            and confirmation.get("protected_holdout_consumed") is False
            and not self.confirmation.read_plan_path().exists()
            and not self.confirmation.protected_predictions_path().exists()
            and not self.confirmation.protected_score_signals_path().exists()
            and not self.confirmation.protected_signals_path().exists()
        )

        checks = {
            "population_contract": population.get("contract_version")
            == PHASE28_POPULATION_REPORT_CONTRACT_VERSION,
            "research_contract": research.get("contract_version")
            == PHASE28_RESEARCH_REPORT_CONTRACT_VERSION,
            "finalist_contract": finalists.get("contract_version")
            == PHASE28_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "blindness_contract": blindness.get("contract_version")
            == PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "confirmation_contract": confirmation.get("contract_version")
            == PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "support_contract": support.get("contract_version")
            == PHASE28_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "validation_contract": validation.get("contract_version")
            == PHASE28_VALIDATION_CONTRACT_VERSION,
            "cumulative_contract": cumulative.get("contract_version")
            == PHASE28_CUMULATIVE_REPORT_CONTRACT_VERSION,
            "policy_fingerprint_consistent": all(
                payload.get("phase28_policy_fingerprint") == phase28_policy_fingerprint()
                for payload in (
                    population,
                    research,
                    finalists,
                    blindness,
                    confirmation,
                    support,
                    validation,
                    cumulative,
                )
            ),
            "all_stage_reports_pass": all(
                payload.get("pass") is True
                for payload in (
                    population,
                    research,
                    blindness,
                    confirmation,
                    validation,
                    cumulative,
                )
            ),
            "cumulative_population_sha": cumulative.get("population_report_sha256")
            == sha256_file(population_path),
            "cumulative_research_sha": cumulative.get("research_report_sha256")
            == sha256_file(research_path),
            "cumulative_blindness_sha": cumulative.get("blindness_audit_sha256")
            == sha256_file(blindness_path),
            "cumulative_confirmation_sha": cumulative.get("confirmation_report_sha256")
            == sha256_file(confirmation_path),
            "cumulative_validation_sha": cumulative.get("independent_validation_sha256")
            == sha256_file(validation_path),
            "research_finalists_sha": research.get("finalists_sha256")
            == sha256_file(finalists_path),
            "confirmation_support_sha": confirmation.get("support_overlay_sha256")
            == sha256_file(support_path),
            "survivor_relationship_consistent": tuple(
                str(value) for value in cumulative.get("selection_survivor_ids", [])
            )
            == survivors,
            "winner_relationship_consistent": tuple(
                str(value) for value in cumulative.get("selection_winner_ids", [])
            )
            == winners,
            "finalist_relationship_consistent": tuple(
                str(value) for value in cumulative.get("finalist_ids", [])
            )
            == finalist_ids
            == tuple(str(value) for value in finalists.get("finalist_ids", [])),
            "supported_relationship_consistent": tuple(
                str(value) for value in cumulative.get("confirmed_supported_candidate_ids", [])
            )
            == confirmed
            == supported
            == tuple(str(value) for value in support.get("supported_candidate_ids", [])),
            "winners_subset_survivors": set(winners).issubset(set(survivors)),
            "finalists_subset_winners": set(finalist_ids).issubset(set(winners)),
            "supported_subset_finalists": set(supported).issubset(set(finalist_ids)),
            "blindness_was_pre_read": blindness.get("pass") is True
            and blindness.get("protected_holdout_consumed") is False
            and int(blindness.get("protected_returns_read", -1)) == 0,
            "zero_finalist_holdout_preserved": no_finalist_holdout_preserved,
            "support_is_historical_analytical_only": support.get("authority")
            == "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY",
            "support_has_no_paper_authority": support.get("paper_authority") is False,
            "support_has_no_live_authority": support.get("live_authority") is False,
            "external_activity_zero": external_zero,
            "architecture_audit_pass": all(architecture_checks.values()),
            "negative_disposition_blocks_phase29": bool(supported) or not phase29_entry_satisfied,
            "positive_disposition_requires_supported": disposition != "ACCEPTED_POSITIVE"
            or bool(supported),
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase28CloseoutError("Phase28 closeout failed: " + ", ".join(failed))

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase28_policy_fingerprint": phase28_policy_fingerprint(),
            "phase28_disposition": disposition,
            "phase29_entry_satisfied": phase29_entry_satisfied,
            "selection_survivor_ids": list(survivors),
            "selection_winner_ids": list(winners),
            "finalist_ids": list(finalist_ids),
            "supported_candidate_ids": list(supported),
            "protected_candidate_rows_read": int(
                confirmation.get("protected_candidate_rows_read", 0)
            ),
            "protected_returns_read": int(confirmation.get("protected_returns_read", 0)),
            "protected_holdout_consumed": bool(
                confirmation.get("protected_holdout_consumed", False)
            ),
            "development_network_rows": cumulative.get("development_network_rows"),
            "protected_network_rows": cumulative.get("protected_network_rows"),
            "architecture_audit_contract": PHASE28_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
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
