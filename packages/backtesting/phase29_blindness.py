from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_closeout import PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION, Phase26Closeout
from .phase27_blindness import unexpected_protected_performance_keys
from .phase27_closeout import PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION, Phase27Closeout
from .phase28_closeout import PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION, Phase28Closeout
from .phase28_confirmation import (
    PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION,
    Phase28ProtectedConfirmation,
)
from .phase29_policy import PHASE29_FORBIDDEN_PROTECTED_OUTCOME_FIELDS, phase29_policy_fingerprint
from .phase29_population import (
    PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
    PHASE29_PROTECTED_FRAME_CONTRACT_VERSION,
    Phase29PopulationBuilder,
)
from .phase29_research import (
    PHASE29_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase29DevelopmentResearch,
)


PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION = (
    "phase29-protected-blindness-audit-v1-phase26-28-zero-read-holdout-reuse"
)
PHASE29_SPEC_RELATIVE_PATH = Path("docs/phase29_relative_value_statistical_arbitrage.md")


class Phase29BlindnessError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase29BlindnessError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase29BlindnessError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase29BlindnessError(f"{label} must be a JSON object")
    return payload


def _parquet_columns(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise Phase29BlindnessError(f"missing protected predictor artifact: {path}")
    con = connect_utc(":memory:")
    try:
        frame = con.execute(f"SELECT * FROM read_parquet({sql_string(path)}) LIMIT 0").fetch_df()
    finally:
        con.close()
    return tuple(str(column) for column in frame.columns)


def _protected_contract_values(path: Path) -> tuple[str, ...]:
    con = connect_utc(":memory:")
    try:
        rows = con.execute(
            f"SELECT DISTINCT phase29_contract_version FROM read_parquet({sql_string(path)})"
        ).fetchall()
    finally:
        con.close()
    return tuple(str(row[0]) for row in rows)


class Phase29ProtectedBlindnessAudit:
    """Prove the inherited master holdout is still unopened before Phase29 confirmation."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase26_closeout = Phase26Closeout(settings)
        self.phase27_closeout = Phase27Closeout(settings)
        self.phase28_closeout = Phase28Closeout(settings)
        self.phase28_confirmation = Phase28ProtectedConfirmation(settings)
        self.population = Phase29PopulationBuilder(settings)
        self.research = Phase29DevelopmentResearch(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase29" / "v1" / "blindness"
        self.confirmation_root = (
            derived / "strategy_evaluation" / "phase29" / "v1" / "confirmation"
        )

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
        p26_path = self.phase26_closeout.report_path()
        p27_path = self.phase27_closeout.report_path()
        p28_path = self.phase28_closeout.report_path()
        p28_confirmation_path = self.phase28_confirmation.report_path()
        population_path = self.population.report_path()
        protected_path = self.population.protected_path()
        research_path = self.research.report_path()
        finalists_path = self.research.finalists_path()
        spec_path = self.settings.project_root / PHASE29_SPEC_RELATIVE_PATH

        p26 = _read_json(p26_path, "Phase26 closeout")
        p27 = _read_json(p27_path, "Phase27 closeout")
        p28 = _read_json(p28_path, "Phase28 closeout")
        p28_confirmation = _read_json(p28_confirmation_path, "Phase28 confirmation")
        population = _read_json(population_path, "Phase29 population")
        research = _read_json(research_path, "Phase29 research")
        finalists = _read_json(finalists_path, "Phase29 finalists")
        if not spec_path.is_file():
            raise Phase29BlindnessError(f"Phase29 specification is missing: {spec_path}")

        protected_columns = _parquet_columns(protected_path)
        forbidden_columns = tuple(
            sorted(
                field
                for field in PHASE29_FORBIDDEN_PROTECTED_OUTCOME_FIELDS
                if field in protected_columns
            )
        )
        research_unexpected = unexpected_protected_performance_keys(research)
        finalist_unexpected = unexpected_protected_performance_keys(finalists)
        confirmation_absent, existing_confirmation_artifacts = self._confirmation_artifacts_absent()

        checks = {
            "phase26_closeout_contract": p26.get("contract_version")
            == PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase26_accepted_negative": p26.get("phase26_disposition") == "ACCEPTED_NEGATIVE"
            and p26.get("pass") is True,
            "phase26_protected_returns_zero": int(p26.get("protected_returns_read", -1)) == 0,
            "phase27_closeout_contract": p27.get("contract_version")
            == PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase27_accepted_negative": p27.get("phase27_disposition") == "ACCEPTED_NEGATIVE"
            and p27.get("pass") is True,
            "phase27_candidate_reads_zero": int(p27.get("protected_candidate_rows_read", -1)) == 0,
            "phase27_return_reads_zero": int(p27.get("protected_returns_read", -1)) == 0,
            "phase27_holdout_unconsumed": p27.get("protected_holdout_consumed") is False,
            "phase28_closeout_contract": p28.get("contract_version")
            == PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase28_accepted_negative": p28.get("phase28_disposition") == "ACCEPTED_NEGATIVE"
            and p28.get("pass") is True,
            "phase28_candidate_reads_zero": int(p28.get("protected_candidate_rows_read", -1)) == 0,
            "phase28_return_reads_zero": int(p28.get("protected_returns_read", -1)) == 0,
            "phase28_holdout_unconsumed": p28.get("protected_holdout_consumed") is False,
            "phase28_confirmation_contract": p28_confirmation.get("contract_version")
            == PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "phase28_confirmation_zero_finalists": p28_confirmation.get("status")
            == "SKIPPED_ZERO_FINALISTS"
            and int(p28_confirmation.get("finalist_count", -1)) == 0,
            "phase28_confirmation_reads_zero": int(
                p28_confirmation.get("protected_candidate_rows_read", -1)
            )
            == 0
            and int(p28_confirmation.get("protected_returns_read", -1)) == 0,
            "phase28_confirmation_holdout_unconsumed": p28_confirmation.get(
                "protected_holdout_consumed"
            )
            is False,
            "phase28_read_plan_absent": not self.phase28_confirmation.read_plan_path().exists(),
            "phase29_population_contract": population.get("contract_version")
            == PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
            "phase29_population_policy_frozen": population.get("phase29_policy_fingerprint")
            == phase29_policy_fingerprint(),
            "phase29_population_pass": population.get("pass") is True,
            "phase29_population_protected_reads_zero": int(
                population.get("protected_return_reads", -1)
            )
            == 0,
            "phase29_protected_row_contract": set(_protected_contract_values(protected_path))
            == {PHASE29_PROTECTED_FRAME_CONTRACT_VERSION},
            "phase29_protected_predictors_have_no_outcomes": not forbidden_columns,
            "phase29_research_contract": research.get("contract_version")
            == PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
            "phase29_research_policy_frozen": research.get("phase29_policy_fingerprint")
            == phase29_policy_fingerprint(),
            "phase29_research_protected_reads_zero": int(
                research.get("protected_return_reads", -1)
            )
            == 0,
            "phase29_research_has_no_protected_performance_fields": not research_unexpected,
            "phase29_finalist_contract": finalists.get("contract_version")
            == PHASE29_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase29_finalists_policy_frozen": finalists.get("phase29_policy_fingerprint")
            == phase29_policy_fingerprint(),
            "phase29_finalists_frozen": finalists.get("frozen") is True,
            "phase29_finalists_protected_reads_zero": int(
                finalists.get("protected_returns_read", -1)
            )
            == 0
            and int(finalists.get("protected_candidate_rows_read", -1)) == 0,
            "phase29_finalists_have_no_protected_performance_fields": not finalist_unexpected,
            "phase29_confirmation_artifacts_absent_before_audit": confirmation_absent,
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase29BlindnessError(
                "Phase29 protected holdout blindness audit failed: " + ", ".join(failed)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "phase29_policy_fingerprint": phase29_policy_fingerprint(),
            "phase29_spec_sha256": sha256_file(spec_path),
            "phase26_closeout_sha256": sha256_file(p26_path),
            "phase27_closeout_sha256": sha256_file(p27_path),
            "phase28_closeout_sha256": sha256_file(p28_path),
            "phase28_confirmation_sha256": sha256_file(p28_confirmation_path),
            "phase29_population_sha256": sha256_file(population_path),
            "phase29_protected_predictors_sha256": sha256_file(protected_path),
            "phase29_research_sha256": sha256_file(research_path),
            "phase29_finalists_sha256": sha256_file(finalists_path),
            "research_unexpected_protected_keys": list(research_unexpected),
            "finalist_unexpected_protected_keys": list(finalist_unexpected),
            "protected_predictor_forbidden_columns": list(forbidden_columns),
            "preexisting_phase29_confirmation_artifacts": list(existing_confirmation_artifacts),
            "eligible_for_phase29_protected_reuse": True,
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
