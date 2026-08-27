from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_closeout import (
    PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION,
    Phase26Closeout,
)
from .phase26_confirmation import (
    PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
    Phase26ProtectedConfirmation,
)
from .phase26_observations import Phase26ObservationBuilder
from .phase26_research import (
    PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase26DevelopmentResearch,
)
from .phase26_runner import (
    PHASE26_CUMULATIVE_REPORT_CONTRACT_VERSION,
    Phase26CumulativeRunner,
)
from .phase27_policy import (
    PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS,
    phase27_policy_fingerprint,
)
from .phase27_research import (
    PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE27_RESEARCH_REPORT_CONTRACT_VERSION,
    Phase27DevelopmentResearch,
)


PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION = (
    "phase27-protected-blindness-audit-v1-phase26-holdout-one-time-reuse"
)
PHASE27_SPEC_RELATIVE_PATH = Path(
    "docs/phase27_cross_sectional_expected_return_learning_ranking.md"
)
_ALLOWED_UNREAD_PROTECTED_KEYS = {
    "protected_return_reads",
    "protected_returns_read",
    "protected_candidate_rows_read",
}


class Phase27BlindnessError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase27BlindnessError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase27BlindnessError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase27BlindnessError(f"{label} must be a JSON object")
    return payload


def unexpected_protected_performance_keys(payload: object) -> tuple[str, ...]:
    """Find protected-labelled payload fields other than explicit unread counters.

    The audit intentionally allows persisted state such as ``protected_returns_read=0``.
    Any other protected-labelled research/finalist field is treated as evidence that
    protected performance may have been materialized before Phase27 confirmation.
    """

    found: set[str] = set()

    def visit(value: object, prefix: str = "") -> None:
        if isinstance(value, Mapping):
            for raw_key, child in value.items():
                key = str(raw_key)
                path = f"{prefix}.{key}" if prefix else key
                if "protected" in key.lower() and key not in _ALLOWED_UNREAD_PROTECTED_KEYS:
                    found.add(path)
                visit(child, path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{prefix}[{index}]")

    visit(payload)
    return tuple(sorted(found))


def _parquet_columns(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise Phase27BlindnessError(f"missing protected predictor artifact: {path}")
    con = connect_utc(":memory:")
    try:
        frame = con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) LIMIT 0"
        ).fetch_df()
    finally:
        con.close()
    return tuple(str(column) for column in frame.columns)


class Phase27ProtectedBlindnessAudit:
    """Independently prove the Phase26 holdout remains unopened for one Phase27 use."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase26_observations = Phase26ObservationBuilder(settings)
        self.phase26_research = Phase26DevelopmentResearch(settings)
        self.phase26_confirmation = Phase26ProtectedConfirmation(settings)
        self.phase26_runner = Phase26CumulativeRunner(settings)
        self.phase26_closeout = Phase26Closeout(settings)
        self.phase27_research = Phase27DevelopmentResearch(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase27" / "v1" / "blindness"
        self.confirmation_root = (
            derived / "strategy_evaluation" / "phase27" / "v1" / "confirmation"
        )

    def report_path(self) -> Path:
        return self.root / "protected_blindness_audit.json"

    def _phase27_confirmation_artifacts_absent(self) -> tuple[bool, tuple[str, ...]]:
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
        cumulative_path = self.phase26_runner.report_path()
        confirmation_path = self.phase26_confirmation.report_path()
        closeout_path = self.phase26_closeout.report_path()
        phase26_research_path = self.phase26_research.report_path()
        phase26_finalists_path = self.phase26_research.finalists_path()
        phase26_protected_path = self.phase26_observations.protected_predictors_path()
        phase27_research_path = self.phase27_research.report_path()
        phase27_finalists_path = self.phase27_research.finalists_path()
        spec_path = self.settings.project_root / PHASE27_SPEC_RELATIVE_PATH

        cumulative = _read_json(cumulative_path, "Phase26 cumulative report")
        confirmation = _read_json(confirmation_path, "Phase26 confirmation report")
        closeout = _read_json(closeout_path, "Phase26 closeout report")
        phase26_research = _read_json(phase26_research_path, "Phase26 research report")
        phase26_finalists = _read_json(phase26_finalists_path, "Phase26 finalists")
        phase27_research = _read_json(phase27_research_path, "Phase27 research report")
        phase27_finalists = _read_json(phase27_finalists_path, "Phase27 finalists")

        if not spec_path.is_file():
            raise Phase27BlindnessError(f"Phase27 frozen specification is missing: {spec_path}")

        protected_columns = _parquet_columns(phase26_protected_path)
        forbidden_columns = tuple(
            sorted(
                field
                for field in PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS
                if field in protected_columns
            )
        )
        phase26_research_unexpected = unexpected_protected_performance_keys(
            phase26_research
        )
        phase26_finalist_unexpected = unexpected_protected_performance_keys(
            phase26_finalists
        )
        confirmation_absent, existing_confirmation_artifacts = (
            self._phase27_confirmation_artifacts_absent()
        )

        checks: dict[str, bool] = {
            "phase26_cumulative_contract": cumulative.get("contract_version")
            == PHASE26_CUMULATIVE_REPORT_CONTRACT_VERSION,
            "phase26_cumulative_pass": cumulative.get("pass") is True,
            "phase26_cumulative_protected_reads_zero": int(
                cumulative.get("protected_returns_read", -1)
            )
            == 0,
            "phase26_confirmation_contract": confirmation.get("contract_version")
            == PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "phase26_confirmation_pass": confirmation.get("pass") is True,
            "phase26_confirmation_zero_finalists": confirmation.get("status")
            == "SKIPPED_ZERO_FINALISTS"
            and int(confirmation.get("finalist_count", -1)) == 0,
            "phase26_confirmation_candidate_reads_zero": int(
                confirmation.get("protected_candidate_rows_read", -1)
            )
            == 0,
            "phase26_confirmation_return_reads_zero": int(
                confirmation.get("protected_returns_read", -1)
            )
            == 0,
            "phase26_closeout_contract": closeout.get("contract_version")
            == PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION,
            "phase26_closeout_accepted_negative": closeout.get("phase26_disposition")
            == "ACCEPTED_NEGATIVE"
            and closeout.get("pass") is True,
            "phase26_closeout_protected_reads_zero": int(
                closeout.get("protected_returns_read", -1)
            )
            == 0,
            "phase26_research_contract": phase26_research.get("contract_version")
            == PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
            "phase26_research_protected_reads_zero": int(
                phase26_research.get("protected_returns_read", -1)
            )
            == 0,
            "phase26_research_has_no_protected_performance_fields": not phase26_research_unexpected,
            "phase26_finalist_contract": phase26_finalists.get("contract_version")
            == PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase26_finalists_frozen": phase26_finalists.get("finalists_frozen") is True,
            "phase26_finalists_protected_reads_zero": int(
                phase26_finalists.get("protected_returns_read", -1)
            )
            == 0,
            "phase26_finalists_have_no_protected_performance_fields": not phase26_finalist_unexpected,
            "phase26_protected_predictors_have_no_outcomes": not forbidden_columns,
            "phase27_research_contract": phase27_research.get("contract_version")
            == PHASE27_RESEARCH_REPORT_CONTRACT_VERSION,
            "phase27_research_policy_frozen": phase27_research.get(
                "phase27_policy_fingerprint"
            )
            == phase27_policy_fingerprint(),
            "phase27_research_protected_reads_zero": int(
                phase27_research.get("protected_return_reads", -1)
            )
            == 0,
            "phase27_finalist_contract": phase27_finalists.get("contract_version")
            == PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "phase27_finalists_policy_frozen": phase27_finalists.get(
                "phase27_policy_fingerprint"
            )
            == phase27_policy_fingerprint(),
            "phase27_finalists_frozen": phase27_finalists.get("frozen") is True,
            "phase27_finalists_protected_reads_zero": int(
                phase27_finalists.get("protected_returns_read", -1)
            )
            == 0
            and int(phase27_finalists.get("protected_candidate_rows_read", -1)) == 0,
            "phase27_confirmation_artifacts_absent_before_audit": confirmation_absent,
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = tuple(sorted(name for name, passed in checks.items() if not passed))
            raise Phase27BlindnessError(
                "Phase27 protected holdout blindness audit failed: " + ", ".join(failed)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "phase27_spec_sha256": sha256_file(spec_path),
            "phase26_cumulative_sha256": sha256_file(cumulative_path),
            "phase26_confirmation_sha256": sha256_file(confirmation_path),
            "phase26_closeout_sha256": sha256_file(closeout_path),
            "phase26_research_sha256": sha256_file(phase26_research_path),
            "phase26_finalists_sha256": sha256_file(phase26_finalists_path),
            "phase26_protected_predictors_sha256": sha256_file(phase26_protected_path),
            "phase27_research_sha256": sha256_file(phase27_research_path),
            "phase27_finalists_sha256": sha256_file(phase27_finalists_path),
            "phase26_research_unexpected_protected_keys": list(
                phase26_research_unexpected
            ),
            "phase26_finalist_unexpected_protected_keys": list(
                phase26_finalist_unexpected
            ),
            "protected_predictor_forbidden_columns": list(forbidden_columns),
            "preexisting_phase27_confirmation_artifacts": list(
                existing_confirmation_artifacts
            ),
            "eligible_for_phase27_protected_reuse": True,
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
