from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase28_closeout import phase28_architecture_audit_checks
from .phase29_blindness import (
    PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase29ProtectedBlindnessAudit,
)
from .phase29_confirmation import (
    PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE29_SUPPORT_OVERLAY_CONTRACT_VERSION,
    Phase29ProtectedConfirmation,
)
from .phase29_policy import (
    PHASE29_AUTOMATION_WRITES,
    PHASE29_AUTOMATIC_BROKER_FAILOVER,
    PHASE29_BROKER_READS,
    PHASE29_BROKER_WRITES,
    PHASE29_LIVE_WRITES,
    PHASE29_ORDER_WRITES,
    PHASE29_PAPER_SUBMITS,
    PHASE29_PROVIDER_READS,
    PHASE29_PROVIDER_WRITES,
    PHASE29_RUNNER_UP_SUBSTITUTION_ALLOWED,
    phase29_policy_fingerprint,
)
from .phase29_population import (
    PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
    Phase29PopulationBuilder,
)
from .phase29_research import (
    PHASE29_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase29DevelopmentResearch,
)
from .phase29_runner import (
    PHASE29_CUMULATIVE_REPORT_CONTRACT_VERSION,
    Phase29CumulativeRunner,
)
from .phase29_validation import (
    PHASE29_VALIDATION_CONTRACT_VERSION,
    Phase29IndependentValidator,
)


PHASE29_ARCHITECTURE_AUDIT_CONTRACT_VERSION = "phase29-end-to-end-anti-workaround-audit-v1"
PHASE29_CLOSEOUT_REPORT_CONTRACT_VERSION = (
    "phase29-closeout-v1-full-phase-gate-relative-value-result-plus-anti-workaround-audit"
)


class Phase29CloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase29CloseoutError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase29CloseoutError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase29CloseoutError(f"{label} must be a JSON object")
    return payload


def _runtime_phase29_import_sites(project_root: Path) -> list[str]:
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
                and "phase29" in line.lower()
            ]
            if import_lines:
                sites.append(path.relative_to(project_root).as_posix())
    return sites


def phase29_architecture_audit_checks(project_root: Path) -> dict[str, bool]:
    inherited = phase28_architecture_audit_checks(project_root)
    audit_path = project_root / "docs" / "phase29_end_to_end_anti_workaround_audit.md"
    audit_text = audit_path.read_text(encoding="utf-8") if audit_path.is_file() else ""
    confirmation_path = project_root / "packages" / "backtesting" / "phase29_confirmation.py"
    confirmation_text = confirmation_path.read_text(encoding="utf-8") if confirmation_path.is_file() else ""
    research_path = project_root / "packages" / "backtesting" / "phase29_research.py"
    research_text = research_path.read_text(encoding="utf-8") if research_path.is_file() else ""
    validation_path = project_root / "packages" / "backtesting" / "phase29_validation.py"
    validation_text = validation_path.read_text(encoding="utf-8") if validation_path.is_file() else ""
    population_path = project_root / "packages" / "backtesting" / "phase29_population.py"
    population_text = population_path.read_text(encoding="utf-8") if population_path.is_file() else ""
    external_values = (
        PHASE29_PROVIDER_READS,
        PHASE29_PROVIDER_WRITES,
        PHASE29_BROKER_READS,
        PHASE29_BROKER_WRITES,
        PHASE29_ORDER_WRITES,
        PHASE29_PAPER_SUBMITS,
        PHASE29_LIVE_WRITES,
        PHASE29_AUTOMATION_WRITES,
    )
    read_plan_call = confirmation_text.find("self._ensure_read_plan(")
    outcome_join_call = confirmation_text.find("self._join_outcomes(query_keys)")
    return {
        "phase28_architecture_invariants_still_pass": all(inherited.values()),
        "audit_document_present": audit_path.is_file(),
        "audit_contract_present": PHASE29_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit_text,
        "audit_disposition_pass": "**Disposition:** PASS" in audit_text,
        "phase29_not_imported_by_runtime_authority": not _runtime_phase29_import_sites(project_root),
        "phase29_external_authority_zero": all(value == 0 for value in external_values),
        "phase29_automatic_broker_failover_disabled": PHASE29_AUTOMATIC_BROKER_FAILOVER is False,
        "phase29_runner_up_substitution_disabled": PHASE29_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_read_plan_precedes_outcome_join": read_plan_call >= 0
        and outcome_join_call > read_plan_call,
        "zero_finalist_confirmation_path_present": "SKIPPED_ZERO_FINALISTS" in confirmation_text
        and "if not finalist_entries:" in confirmation_text,
        "research_has_no_post_result_tuning_loop": "tune_hyperparameters" not in research_text,
        "independent_validator_does_not_import_phase29_relative_value": "from .phase29_relative_value" not in validation_text,
        "independent_validator_rebuilds_raw_relative_value_sample": "_network_sample_reconciliation(" in validation_text,
        "independent_validator_rebuilds_protected_fold_labels": "_independent_fold_labels(" in validation_text,
        "population_censors_only_declared_relative_value_failures": "except Phase29RelativeValueError:" in population_text
        and "except (ValueError, RuntimeError):" not in population_text,
        "support_rejects_market_neutral_pair_authority": '"market_neutral_pair_execution_authority": False'
        in confirmation_text,
    }


def phase29_disposition(supported_candidate_ids: tuple[str, ...]) -> tuple[str, bool]:
    if supported_candidate_ids:
        return "ACCEPTED_POSITIVE", True
    return "ACCEPTED_NEGATIVE", False


class Phase29Closeout:
    """Full Phase29 phase-end acceptance gate over persisted target evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase29PopulationBuilder(settings)
        self.research = Phase29DevelopmentResearch(settings)
        self.blindness = Phase29ProtectedBlindnessAudit(settings)
        self.confirmation = Phase29ProtectedConfirmation(settings)
        self.validator = Phase29IndependentValidator(settings)
        self.runner = Phase29CumulativeRunner(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase29" / "v1"

    def report_path(self) -> Path:
        return self.root / "phase29_closeout_report.json"

    def run(self) -> dict[str, object]:
        population_path = self.population.report_path()
        research_path = self.research.report_path()
        finalists_path = self.research.finalists_path()
        blindness_path = self.blindness.report_path()
        confirmation_path = self.confirmation.report_path()
        support_path = self.confirmation.support_overlay_path()
        validation_path = self.validator.report_path()
        cumulative_path = self.runner.report_path()

        population = _read_json(population_path, "Phase29 population report")
        research = _read_json(research_path, "Phase29 research report")
        finalists = _read_json(finalists_path, "Phase29 finalists")
        blindness = _read_json(blindness_path, "Phase29 blindness audit")
        confirmation = _read_json(confirmation_path, "Phase29 confirmation report")
        support = _read_json(support_path, "Phase29 support overlay")
        validation = _read_json(validation_path, "Phase29 independent validation")
        cumulative = _read_json(cumulative_path, "Phase29 cumulative report")

        survivors = tuple(str(value) for value in research.get("selection_survivor_ids", []))
        winners = tuple(str(value) for value in research.get("selection_winner_ids", []))
        finalist_ids = tuple(str(value) for value in research.get("finalist_ids", []))
        confirmed = tuple(str(value) for value in confirmation.get("confirmed_candidate_ids", []))
        supported = tuple(str(value) for value in validation.get("supported_candidate_ids", []))
        disposition, phase30_entry_satisfied = phase29_disposition(supported)
        architecture_checks = phase29_architecture_audit_checks(self.settings.project_root)

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
            == PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
            "research_contract": research.get("contract_version")
            == PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
            "finalist_contract": finalists.get("contract_version")
            == PHASE29_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "blindness_contract": blindness.get("contract_version")
            == PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "confirmation_contract": confirmation.get("contract_version")
            == PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "support_contract": support.get("contract_version")
            == PHASE29_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "validation_contract": validation.get("contract_version")
            == PHASE29_VALIDATION_CONTRACT_VERSION,
            "cumulative_contract": cumulative.get("contract_version")
            == PHASE29_CUMULATIVE_REPORT_CONTRACT_VERSION,
            "policy_fingerprint_consistent": all(
                payload.get("phase29_policy_fingerprint") == phase29_policy_fingerprint()
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
            "cumulative_disposition_pending_full_gate": cumulative.get("disposition")
            == (
                "ACCEPTED_POSITIVE_PENDING_FULL_PHASE_GATE"
                if supported
                else "ACCEPTED_NEGATIVE_PENDING_FULL_PHASE_GATE"
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
            "support_is_relative_value_confirmation_only": support.get("relative_value_confirmation_only")
            is True,
            "support_has_no_market_neutral_pair_authority": support.get(
                "market_neutral_pair_execution_authority"
            )
            is False,
            "support_has_no_paper_authority": support.get("paper_authority") is False,
            "support_has_no_live_authority": support.get("live_authority") is False,
            "external_activity_zero": external_zero,
            "architecture_audit_pass": all(architecture_checks.values()),
            "negative_disposition_blocks_phase30": bool(supported) or not phase30_entry_satisfied,
            "positive_disposition_requires_supported": disposition != "ACCEPTED_POSITIVE"
            or bool(supported),
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase29CloseoutError("Phase29 closeout failed: " + ", ".join(failed))

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE29_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase29_policy_fingerprint": phase29_policy_fingerprint(),
            "phase29_disposition": disposition,
            "phase30_entry_satisfied": phase30_entry_satisfied,
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
            "development_relative_value_rows": cumulative.get("development_relative_value_rows"),
            "protected_relative_value_rows": cumulative.get("protected_relative_value_rows"),
            "architecture_audit_contract": PHASE29_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
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
            "automation_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
