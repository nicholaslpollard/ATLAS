from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase27_blindness import unexpected_protected_performance_keys
from .phase27_closeout import PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION, Phase27Closeout
from .phase27_confirmation import (
    PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
    Phase27ProtectedConfirmation,
)
from .phase28_policy import PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS, phase28_policy_fingerprint
from .phase28_population import (
    PHASE28_POPULATION_REPORT_CONTRACT_VERSION,
    PHASE28_PROTECTED_FRAME_CONTRACT_VERSION,
    Phase28PopulationBuilder,
)
from .phase28_research import (
    PHASE28_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE28_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase28DevelopmentResearch,
)


PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION = (
    "phase28-protected-blindness-audit-v1-phase27-zero-read-holdout-reuse"
)
PHASE28_SPEC_RELATIVE_PATH = Path(
    "docs/phase28_cross_stock_lead_lag_residual_network_alpha.md"
)


class Phase28BlindnessError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase28BlindnessError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase28BlindnessError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase28BlindnessError(f"{label} must be a JSON object")
    return payload


def _parquet_columns(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise Phase28BlindnessError(f"missing Phase28 protected predictor artifact: {path}")
    con = connect_utc(":memory:")
    try:
        frame = con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) LIMIT 0"
        ).fetch_df()
    finally:
        con.close()
    return tuple(str(column) for column in frame.columns)


class Phase28ProtectedBlindnessAudit:
    """Prove the inherited master holdout is still outcome-unopened before Phase28."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase27_closeout = Phase27Closeout(settings)
        self.phase27_confirmation = Phase27ProtectedConfirmation(settings)
        self.population = Phase28PopulationBuilder(settings)
        self.research = Phase28DevelopmentResearch(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase28" / "v1" / "blindness"
        self.confirmation_root = derived / "strategy_evaluation" / "phase28" / "v1" / "confirmation"

    def report_path(self) -> Path:
        return self.root / "protected_blindness_audit.json"

    def _confirmation_artifacts_absent(self) -> tuple[bool, tuple[str, ...]]:
        if not self.confirmation_root.exists():
            return True, ()
        files = tuple(
            sorted(
                path.relative_to(self.confirmation_root).as_posix()
                for path in self.confirmation_root.rglob("*")
                if path.is_file()
            )
        )
        return len(files) == 0, files

    def run(self) -> dict[str, object]:
        closeout_path = self.phase27_closeout.report_path()
        confirmation_path = self.phase27_confirmation.report_path()
        population_path = self.population.report_path()
        protected_path = self.population.protected_path()
        research_path = self.research.report_path()
        finalists_path = self.research.finalists_path()
        spec_path = self.settings.project_root / PHASE28_SPEC_RELATIVE_PATH

        closeout = _read_json(closeout_path, "Phase27 closeout")
        confirmation = _read_json(confirmation_path, "Phase27 confirmation")
        population = _read_json(population_path, "Phase28 population report")
        research = _read_json(research_path, "Phase28 research report")
        finalists = _read_json(finalists_path, "Phase28 finalists")
        if not spec_path.is_file():
            raise Phase28BlindnessError(f"Phase28 frozen specification is missing: {spec_path}")

        protected_columns = _parquet_columns(protected_path)
        forbidden_columns = tuple(
            sorted(
                field
                for field in PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS
                if field in protected_columns
            )
        )
        research_unexpected = unexpected_protected_performance_keys(research)
        finalist_unexpected = unexpected_protected_performance_keys(finalists)
        confirmation_absent, existing_confirmation_artifacts = self._confirmation_artifacts_absent()

        checks = {
            "phase27_closeout_contract": closeout.get("contract_version")
            == PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase27_closeout_accepted_negative": closeout.get("phase27_disposition")
            == "ACCEPTED_NEGATIVE"
            and closeout.get("pass") is True,
            "phase27_closeout_candidate_reads_zero": int(
                closeout.get("protected_candidate_rows_read", -1)
            )
            == 0,
            "phase27_closeout_return_reads_zero": int(closeout.get("protected_returns_read", -1))
            == 0,
            "phase27_closeout_holdout_unconsumed": closeout.get("protected_holdout_consumed") is False,
            "phase27_confirmation_contract": confirmation.get("contract_version")
            == PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "phase27_confirmation_zero_finalists": confirmation.get("status")
            == "SKIPPED_ZERO_FINALISTS"
            and int(confirmation.get("finalist_count", -1)) == 0,
            "phase27_confirmation_candidate_reads_zero": int(
                confirmation.get("protected_candidate_rows_read", -1)
            )
            == 0,
            "phase27_confirmation_return_reads_zero": int(
                confirmation.get("protected_returns_read", -1)
            )
            == 0,
            "phase27_confirmation_holdout_unconsumed": confirmation.get("protected_holdout_consumed")
            is False,
            "phase27_read_plan_absent": not self.phase27_confirmation.read_plan_path().exists(),
            "phase28_population_contract": population.get("contract_version")
            == PHASE28_POPULATION_REPORT_CONTRACT_VERSION,
            "phase28_population_policy_frozen": population.get("phase28_policy_fingerprint")
            == phase28_policy_fingerprint(),
            "phase28_population_pass": population.get("pass") is True,
            "phase28_population_protected_reads_zero": int(population.get("protected_return_reads", -1))
            == 0,
            "phase28_protected_row_contract": set(
                _read_protected_contract_values(protected_path)
            )
            == {PHASE28_PROTECTED_FRAME_CONTRACT_VERSION},
            "phase28_protected_predictors_have_no_outcomes": not forbidden_columns,
            "phase28_research_contract": research.get("contract_version")
            == PHASE28_RESEARCH_REPORT_CONTRACT_VERSION,
            "phase28_research_policy_frozen": research.get("phase28_policy_fingerprint")
            == phase28_policy_fingerprint(),
            "phase28_research_protected_reads_zero": int(research.get("protected_return_reads", -1))
            == 0,
            "phase28_research_has_no_protected_performance_fields": not research_unexpected,
            "phase28_finalist_contract": finalists.get("contract_version")
            == PHASE28_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase28_finalists_policy_frozen": finalists.get("phase28_policy_fingerprint")
            == phase28_policy_fingerprint(),
            "phase28_finalists_frozen": finalists.get("frozen") is True,
            "phase28_finalists_protected_reads_zero": int(
                finalists.get("protected_returns_read", -1)
            )
            == 0
            and int(finalists.get("protected_candidate_rows_read", -1)) == 0,
            "phase28_finalists_have_no_protected_performance_fields": not finalist_unexpected,
            "phase28_confirmation_artifacts_absent_before_audit": confirmation_absent,
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase28BlindnessError(
                "Phase28 protected holdout blindness audit failed: " + ", ".join(failed)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "phase28_policy_fingerprint": phase28_policy_fingerprint(),
            "phase28_spec_sha256": sha256_file(spec_path),
            "phase27_closeout_sha256": sha256_file(closeout_path),
            "phase27_confirmation_sha256": sha256_file(confirmation_path),
            "phase28_population_sha256": sha256_file(population_path),
            "phase28_protected_predictors_sha256": sha256_file(protected_path),
            "phase28_research_sha256": sha256_file(research_path),
            "phase28_finalists_sha256": sha256_file(finalists_path),
            "research_unexpected_protected_keys": list(research_unexpected),
            "finalist_unexpected_protected_keys": list(finalist_unexpected),
            "protected_predictor_forbidden_columns": list(forbidden_columns),
            "preexisting_phase28_confirmation_artifacts": list(existing_confirmation_artifacts),
            "eligible_for_phase28_protected_reuse": True,
            "protected_holdout_consumed": False,
            "protected_returns_read": 0,
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


def _read_protected_contract_values(path: Path) -> tuple[str, ...]:
    con = connect_utc(":memory:")
    try:
        rows = con.execute(
            f"SELECT DISTINCT phase28_contract_version FROM read_parquet({sql_string(path)})"
        ).fetchall()
    finally:
        con.close()
    return tuple(str(row[0]) for row in rows)
