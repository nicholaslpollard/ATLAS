from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase29_blindness import (
    PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase29ProtectedBlindnessAudit,
)
from .phase29_confirmation import (
    PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION,
    Phase29ProtectedConfirmation,
)
from .phase29_policy import phase29_policy_fingerprint
from .phase29_population import (
    PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
    Phase29PopulationBuilder,
)
from .phase29_research import (
    PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase29DevelopmentResearch,
)
from .phase29_validation import Phase29IndependentValidator


PHASE29_CUMULATIVE_REPORT_CONTRACT_VERSION = (
    "phase29-cumulative-v1-relative-value-one-phase-gate-target-evidence"
)


class Phase29RunnerError(RuntimeError):
    pass


def _read_existing(path: Path, *, contract_version: str, label: str) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase29RunnerError(f"invalid existing {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase29RunnerError(f"existing {label} must be an object")
    if payload.get("contract_version") != contract_version:
        raise Phase29RunnerError(f"existing {label} contract mismatch")
    if payload.get("phase29_policy_fingerprint") != phase29_policy_fingerprint():
        raise Phase29RunnerError(f"existing {label} policy fingerprint mismatch")
    if payload.get("pass") is not True:
        raise Phase29RunnerError(f"existing {label} is not passing")
    return payload


class Phase29CumulativeRunner:
    """Run or safely resume the frozen Phase29 evidence sequence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase29PopulationBuilder(settings)
        self.research = Phase29DevelopmentResearch(settings)
        self.blindness = Phase29ProtectedBlindnessAudit(settings)
        self.confirmation = Phase29ProtectedConfirmation(settings)
        self.validator = Phase29IndependentValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase29" / "v1"

    def report_path(self) -> Path:
        return self.root / "phase29_cumulative_report.json"

    @staticmethod
    def _run_or_reuse(
        *,
        path: Path,
        contract_version: str,
        label: str,
        runner: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        existing = _read_existing(path, contract_version=contract_version, label=label)
        return existing if existing is not None else runner()

    def run(self) -> dict[str, object]:
        population = self._run_or_reuse(
            path=self.population.report_path(),
            contract_version=PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
            label="Phase29 population report",
            runner=self.population.run,
        )
        research = self._run_or_reuse(
            path=self.research.report_path(),
            contract_version=PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
            label="Phase29 development research",
            runner=self.research.run,
        )
        blindness = self._run_or_reuse(
            path=self.blindness.report_path(),
            contract_version=PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION,
            label="Phase29 protected blindness audit",
            runner=self.blindness.run,
        )
        confirmation = self._run_or_reuse(
            path=self.confirmation.report_path(),
            contract_version=PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION,
            label="Phase29 protected confirmation",
            runner=self.confirmation.run,
        )
        validation = self.validator.run()

        survivors = tuple(str(value) for value in research.get("selection_survivor_ids", []))
        winners = tuple(str(value) for value in research.get("selection_winner_ids", []))
        finalists = tuple(str(value) for value in research.get("finalist_ids", []))
        supported = tuple(str(value) for value in validation.get("supported_candidate_ids", []))
        disposition = (
            "ACCEPTED_POSITIVE_PENDING_FULL_PHASE_GATE"
            if supported
            else "ACCEPTED_NEGATIVE_PENDING_FULL_PHASE_GATE"
        )
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
            int(report.get(field, -1)) == 0
            for report in (population, research, blindness, confirmation)
            for field in zero_fields
        )
        if not (
            external_zero
            and all(
                report.get("pass") is True
                for report in (population, research, blindness, confirmation, validation)
            )
        ):
            raise Phase29RunnerError("Phase29 cumulative evidence did not pass all components")

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE29_CUMULATIVE_REPORT_CONTRACT_VERSION,
            "phase29_policy_fingerprint": phase29_policy_fingerprint(),
            "disposition": disposition,
            "population_report_sha256": sha256_file(self.population.report_path()),
            "research_report_sha256": sha256_file(self.research.report_path()),
            "blindness_audit_sha256": sha256_file(self.blindness.report_path()),
            "confirmation_report_sha256": sha256_file(self.confirmation.report_path()),
            "independent_validation_sha256": sha256_file(self.validator.report_path()),
            "development_relative_value_rows": population.get("development_relative_value_rows"),
            "protected_relative_value_rows": population.get("protected_relative_value_rows"),
            "selection_survivor_ids": list(survivors),
            "selection_winner_ids": list(winners),
            "finalist_ids": list(finalists),
            "confirmed_supported_candidate_ids": list(supported),
            "protected_candidate_rows_read": confirmation.get("protected_candidate_rows_read", 0),
            "protected_returns_read": confirmation.get("protected_returns_read", 0),
            "protected_holdout_consumed": confirmation.get("protected_holdout_consumed", False),
            "independent_validation_pass": validation.get("pass") is True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
