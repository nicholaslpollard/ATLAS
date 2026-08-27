from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase26_confirmation import Phase26ProtectedConfirmation
from .phase26_observations import Phase26ObservationBuilder
from .phase26_policy import phase26_policy_fingerprint
from .phase26_research import Phase26DevelopmentResearch
from .phase26_validation import Phase26IndependentValidator


PHASE26_CUMULATIVE_REPORT_CONTRACT_VERSION = (
    "phase26-cumulative-v1-one-phase-gate-target-evidence"
)


class Phase26RunnerError(RuntimeError):
    pass


class Phase26CumulativeRunner:
    """Execute the complete provider/broker-free Phase26 evidence sequence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.observations = Phase26ObservationBuilder(settings)
        self.research = Phase26DevelopmentResearch(settings)
        self.confirmation = Phase26ProtectedConfirmation(settings)
        self.validator = Phase26IndependentValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase26" / "v1"

    def report_path(self) -> Path:
        return self.root / "phase26_cumulative_report.json"

    def run(self) -> dict[str, object]:
        observation = self.observations.run()
        research = self.research.run()
        confirmation = self.confirmation.run()
        validation = self.validator.run()
        supported = tuple(str(value) for value in validation.get("supported_candidate_ids", []))
        finalists = tuple(str(value) for value in research.get("finalist_candidate_ids", []))
        if supported:
            disposition = "ACCEPTED_POSITIVE_PENDING_FULL_PHASE_GATE"
        else:
            disposition = "ACCEPTED_NEGATIVE_PENDING_FULL_PHASE_GATE"

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_CUMULATIVE_REPORT_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "disposition": disposition,
            "observation_report_sha256": sha256_file(self.observations.report_path()),
            "research_report_sha256": sha256_file(self.research.report_path()),
            "confirmation_report_sha256": sha256_file(self.confirmation.report_path()),
            "independent_validation_sha256": sha256_file(self.validator.report_path()),
            "development_usable_rows": observation.get("development_usable_rows"),
            "protected_predictor_rows": observation.get("protected_predictor_rows"),
            "selected_candidate_ids": research.get("selected_candidate_ids", []),
            "finalist_candidate_ids": list(finalists),
            "confirmed_supported_candidate_ids": list(supported),
            "protected_returns_read": confirmation.get("protected_returns_read", 0),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "independent_validation_pass": validation.get("pass") is True,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": all(
                item.get("pass") is True
                for item in (observation, research, confirmation, validation)
            ),
        }
        if report["pass"] is not True:
            raise Phase26RunnerError("Phase26 cumulative evidence did not pass all components")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
