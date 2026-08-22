from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.portfolio.phase13_engine import Phase13CaseEngine
from packages.portfolio.phase13_policy import (
    PHASE13_BROKER_WRITES,
    PHASE13_ORDER_WRITES,
    PHASE13_PRODUCTION_ML_WRITES,
)
from packages.portfolio.phase13_source import Phase13PlanningInputResolver
from packages.portfolio.phase13_validation import Phase13IndependentValidator


PHASE13_CLOSEOUT_CONTRACT_VERSION = (
    "phase13-closeout-v1-context-instrument-geometry-portfolio-risk-independent-validation"
)
PHASE13_NEXT_PHASE = "PHASE_14_INDEPENDENT_AI_AUDIT_ALERTING"


class Phase13CloseoutError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase13_acceptance_checks(
    *,
    manifest: dict[str, object],
    validation: dict[str, object],
) -> dict[str, bool]:
    validation_checks = dict(validation.get("checks") or {})
    upstream = int(manifest.get("phase12_case_count", -1))
    output = int(manifest.get("case_file_count", -1))
    return {
        "case_manifest_pass": manifest.get("pass") is True,
        "phase12_case_count_exact": upstream == output,
        "zero_case_noop_is_valid": upstream != 0
        or (
            output == 0
            and manifest.get("provider_initialized") is False
            and int(manifest.get("news_provider_calls", -1)) == 0
            and int(manifest.get("option_chain_provider_calls", -1)) == 0
            and int(manifest.get("portfolio_snapshot_reads", -1)) == 0
        ),
        "independent_validation_pass": validation.get("pass") is True,
        "accepted_phase12_input_reverified": validation_checks.get(
            "accepted_phase12_input_reverified"
        )
        is True,
        "preregistered_policy_exact": validation_checks.get("preregistered_policy_exact") is True,
        "case_plans_independently_recomputed": validation_checks.get(
            "case_plans_independently_recomputed"
        )
        is True,
        "no_execution_artifacts": validation_checks.get("no_execution_artifacts") is True,
        "production_ml_writes_zero": int(manifest.get("production_ml_writes", -1)) == 0
        and int(validation.get("production_ml_writes", -1)) == 0
        and PHASE13_PRODUCTION_ML_WRITES == 0,
        "broker_writes_zero": int(manifest.get("broker_writes", -1)) == 0
        and int(validation.get("broker_writes", -1)) == 0
        and PHASE13_BROKER_WRITES == 0,
        "order_writes_zero": int(manifest.get("order_writes", -1)) == 0
        and int(validation.get("order_writes", -1)) == 0
        and PHASE13_ORDER_WRITES == 0,
        "execution_absent": manifest.get("execution_present") is False,
    }


class Phase13Closeout:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase13PlanningInputResolver(settings)
        self.engine = Phase13CaseEngine(settings)
        self.validator = Phase13IndependentValidator(settings)
        self.root = self.engine.root
        self.report_path = self.root / "phase13_final_acceptance.json"

    def run(
        self,
        *,
        as_of_date: date | None = None,
        portfolio_snapshot_path: Path | None = None,
        correlation_evidence: dict[str, float] | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        planning_input = self.input_resolver.resolve(as_of_date)
        if progress is not None:
            progress(
                f"accepted Phase 12 research cases: {planning_input.case_count} on {planning_input.as_of_date}"
            )
        manifest = self.engine.run(
            as_of_date=planning_input.as_of_date,
            portfolio_snapshot_path=portfolio_snapshot_path,
            correlation_evidence=correlation_evidence,
            progress=progress,
        )
        if manifest.get("pass") is not True:
            raise Phase13CloseoutError("Phase 13 case materialization failed")
        if progress is not None:
            progress("independent validator: recomputing Phase 13 case-plan evidence")
        validation = self.validator.run(
            as_of_date=planning_input.as_of_date,
            portfolio_snapshot_path=portfolio_snapshot_path,
            correlation_evidence=correlation_evidence,
        )
        if validation.get("pass") is not True:
            raise Phase13CloseoutError("Phase 13 independent validation failed")
        checks = phase13_acceptance_checks(manifest=manifest, validation=validation)
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase13CloseoutError("Phase 13 closeout checks failed: " + ", ".join(failed))

        source_payload = {
            "contract_version": PHASE13_CLOSEOUT_CONTRACT_VERSION,
            "as_of_date": planning_input.as_of_date.isoformat(),
            "phase12_acceptance_sha256": planning_input.phase12_acceptance_sha256,
            "manifest_sha256": sha256_file(self.engine.manifest_path(planning_input.as_of_date)),
            "validation_sha256": sha256_file(self.validator.report_path),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE13_CLOSEOUT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": planning_input.as_of_date.isoformat(),
            "phase12_acceptance_sha256": planning_input.phase12_acceptance_sha256,
            "phase13_manifest_sha256": source_payload["manifest_sha256"],
            "phase13_validation_sha256": source_payload["validation_sha256"],
            "phase12_case_count": planning_input.case_count,
            "case_file_count": int(manifest["case_file_count"]),
            "phase14_review_ready_count": int(manifest["phase14_review_ready_count"]),
            "provider_initialized": bool(manifest["provider_initialized"]),
            "news_provider_calls": int(manifest["news_provider_calls"]),
            "option_chain_provider_calls": int(manifest["option_chain_provider_calls"]),
            "portfolio_snapshot_reads": int(manifest["portfolio_snapshot_reads"]),
            "zero_case_noop": planning_input.case_count == 0,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "execution_present": False,
            "final_disposition": {
                "phase13_accepted": True,
                "case_files_are_plans_not_orders": True,
                "equity_primary_until_option_relative_value_model_accepted": True,
                "reference_entry_is_not_assumed_fill": True,
                "missing_context_or_portfolio_evidence_is_not_guessed": True,
                "next_phase": PHASE13_NEXT_PHASE,
            },
            "pass": True,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
