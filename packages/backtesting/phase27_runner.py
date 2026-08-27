from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase27_blindness import (
    PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase27ProtectedBlindnessAudit,
)
from .phase27_confirmation import (
    PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
    Phase27ProtectedConfirmation,
)
from .phase27_policy import phase27_policy_fingerprint
from .phase27_population import (
    PHASE27_POPULATION_REPORT_CONTRACT_VERSION,
    Phase27PopulationBuilder,
)
from .phase27_research import (
    PHASE27_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase27DevelopmentResearch,
)
from .phase27_validation import Phase27IndependentValidator


PHASE27_CUMULATIVE_REPORT_CONTRACT_VERSION = (
    "phase27-cumulative-v1-one-phase-gate-target-evidence"
)


class Phase27RunnerError(RuntimeError):
    pass


def _read_existing(
    path: Path,
    *,
    contract_version: str,
    label: str,
) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase27RunnerError(f"invalid existing {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase27RunnerError(f"existing {label} must be an object")
    if payload.get("contract_version") != contract_version:
        raise Phase27RunnerError(f"existing {label} contract mismatch")
    if payload.get("phase27_policy_fingerprint") != phase27_policy_fingerprint():
        raise Phase27RunnerError(f"existing {label} policy fingerprint mismatch")
    if payload.get("pass") is not True:
        raise Phase27RunnerError(f"existing {label} is not passing")
    return payload


class Phase27CumulativeRunner:
    """Run or safely resume the frozen Phase27 evidence sequence.

    Once development research or protected evidence exists, the runner reuses the
    exact persisted artifacts rather than rerunning model selection. This prevents an
    accidental second draw from development/protected evidence during interruption
    recovery and lets the confirmation layer resume only its immutable read plan.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase27PopulationBuilder(settings)
        self.research = Phase27DevelopmentResearch(settings)
        self.blindness = Phase27ProtectedBlindnessAudit(settings)
        self.confirmation = Phase27ProtectedConfirmation(settings)
        self.validator = Phase27IndependentValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase27" / "v1"

    def report_path(self) -> Path:
        return self.root / "phase27_cumulative_report.json"

    @staticmethod
    def _run_or_reuse(
        *,
        path: Path,
        contract_version: str,
        label: str,
        runner: Callable[[], dict[str, object]],
    ) -> dict[str, object]:
        existing = _read_existing(
            path,
            contract_version=contract_version,
            label=label,
        )
        return existing if existing is not None else runner()

    def run(self) -> dict[str, object]:
        population = self._run_or_reuse(
            path=self.population.report_path(),
            contract_version=PHASE27_POPULATION_REPORT_CONTRACT_VERSION,
            label="Phase27 population report",
            runner=self.population.run,
        )
        research = self._run_or_reuse(
            path=self.research.report_path(),
            contract_version=PHASE27_RESEARCH_REPORT_CONTRACT_VERSION,
            label="Phase27 development research",
            runner=self.research.run,
        )
        blindness = self._run_or_reuse(
            path=self.blindness.report_path(),
            contract_version=PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
            label="Phase27 protected blindness audit",
            runner=self.blindness.run,
        )
        confirmation = self._run_or_reuse(
            path=self.confirmation.report_path(),
            contract_version=PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
            label="Phase27 protected confirmation",
            runner=self.confirmation.run,
        )
        validation = self.validator.run()

        supported = tuple(
            str(value) for value in validation.get("supported_candidate_ids", [])
        )
        finalists = tuple(str(value) for value in research.get("finalist_ids", []))
        selection_survivors = tuple(
            str(value) for value in research.get("selection_survivor_ids", [])
        )
        selection_winners = tuple(
            str(value) for value in research.get("selection_winner_ids", [])
        )
        disposition = (
            "ACCEPTED_POSITIVE_PENDING_FULL_PHASE_GATE"
            if supported
            else "ACCEPTED_NEGATIVE_PENDING_FULL_PHASE_GATE"
        )

        zero_authority_fields = (
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
            for field in zero_authority_fields
        )
        pass_value = bool(
            external_zero
            and all(
                report.get("pass") is True
                for report in (population, research, blindness, confirmation, validation)
            )
        )
        if not pass_value:
            raise Phase27RunnerError("Phase27 cumulative evidence did not pass all components")

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE27_CUMULATIVE_REPORT_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "disposition": disposition,
            "population_report_sha256": sha256_file(self.population.report_path()),
            "research_report_sha256": sha256_file(self.research.report_path()),
            "blindness_audit_sha256": sha256_file(self.blindness.report_path()),
            "confirmation_report_sha256": sha256_file(self.confirmation.report_path()),
            "independent_validation_sha256": sha256_file(self.validator.report_path()),
            "development_model_rows": population.get("development_model_rows"),
            "protected_model_rows": population.get("protected_model_rows"),
            "selection_survivor_ids": list(selection_survivors),
            "selection_winner_ids": list(selection_winners),
            "finalist_ids": list(finalists),
            "confirmed_supported_candidate_ids": list(supported),
            "protected_candidate_rows_read": confirmation.get(
                "protected_candidate_rows_read", 0
            ),
            "protected_returns_read": confirmation.get("protected_returns_read", 0),
            "protected_holdout_consumed": confirmation.get(
                "protected_holdout_consumed", False
            ),
            "independent_validation_pass": validation.get("pass") is True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
