from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Callable

from packages.ai.phase14_engine import Phase14AuditEngine
from packages.ai.phase14_policy import (
    PHASE14_BROKER_WRITES,
    PHASE14_ORDER_WRITES,
    PHASE14_POSITION_WRITES,
    PHASE14_PRODUCTION_ML_WRITES,
)
from packages.ai.phase14_source import Phase14ReviewInputResolver
from packages.ai.phase14_validation import Phase14IndependentValidator
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file


PHASE14_CLOSEOUT_CONTRACT_VERSION = (
    "phase14-closeout-v1-independent-ai-audit-alert-artifact-independent-validation"
)
PHASE14_NEXT_PHASE = "PHASE_15_BROKER_EXECUTION_OUTCOME_LEARNING"


class Phase14CloseoutError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def phase14_acceptance_checks(
    *,
    manifest: dict[str, object],
    validation: dict[str, object],
) -> dict[str, bool]:
    validation_checks = dict(validation.get("checks") or {})
    review_ready = int(manifest.get("phase13_review_ready_count", -1))
    reviews = int(manifest.get("ai_review_count", -1))
    alerts = int(manifest.get("alert_artifact_count", -1))
    return {
        "review_manifest_pass": manifest.get("pass") is True,
        "review_count_exact": review_ready == reviews,
        "alert_count_exact": reviews == alerts,
        "zero_review_noop_is_valid": review_ready != 0
        or (
            reviews == 0
            and alerts == 0
            and manifest.get("provider_initialized") is False
            and int(manifest.get("provider_calls", -1)) == 0
        ),
        "independent_validation_pass": validation.get("pass") is True,
        "accepted_phase13_input_reverified": validation_checks.get(
            "accepted_phase13_input_reverified"
        )
        is True,
        "preregistered_policy_exact": validation_checks.get("preregistered_policy_exact") is True,
        "reviews_independently_revalidated": validation_checks.get(
            "reviews_independently_revalidated"
        )
        is True,
        "alerts_independently_recomputed": validation_checks.get(
            "alerts_independently_recomputed"
        )
        is True,
        "ai_structured_mutation_fields_absent": validation_checks.get(
            "ai_structured_mutation_fields_absent"
        )
        is True,
        "external_delivery_disabled": validation_checks.get("external_delivery_disabled") is True,
        "external_deliveries_zero": int(manifest.get("external_deliveries", -1)) == 0
        and int(validation.get("external_deliveries", -1)) == 0,
        "production_ml_writes_zero": int(manifest.get("production_ml_writes", -1)) == 0
        and int(validation.get("production_ml_writes", -1)) == 0
        and PHASE14_PRODUCTION_ML_WRITES == 0,
        "broker_writes_zero": int(manifest.get("broker_writes", -1)) == 0
        and int(validation.get("broker_writes", -1)) == 0
        and PHASE14_BROKER_WRITES == 0,
        "order_writes_zero": int(manifest.get("order_writes", -1)) == 0
        and int(validation.get("order_writes", -1)) == 0
        and PHASE14_ORDER_WRITES == 0,
        "position_writes_zero": int(manifest.get("position_writes", -1)) == 0
        and int(validation.get("position_writes", -1)) == 0
        and PHASE14_POSITION_WRITES == 0,
        "execution_absent": manifest.get("execution_present") is False
        and validation.get("execution_present") is False,
    }


class Phase14Closeout:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase14ReviewInputResolver(settings)
        self.engine = Phase14AuditEngine(settings)
        self.validator = Phase14IndependentValidator(settings)
        self.root = self.engine.root
        self.report_path = self.root / "phase14_final_acceptance.json"

    def run(
        self,
        *,
        as_of_date: date | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> dict[str, object]:
        review_input = self.input_resolver.resolve(as_of_date)
        if progress is not None:
            progress(
                f"accepted Phase 13 review-ready cases: {review_input.review_ready_count} on {review_input.as_of_date}"
            )
        manifest = self.engine.run(as_of_date=review_input.as_of_date, progress=progress)
        if manifest.get("pass") is not True:
            raise Phase14CloseoutError("Phase 14 AI review manifest failed")
        if progress is not None:
            progress("independent validator: recomputing Phase 14 review and alert evidence")
        validation = self.validator.run(as_of_date=review_input.as_of_date)
        if validation.get("pass") is not True:
            raise Phase14CloseoutError("Phase 14 independent validation failed")
        checks = phase14_acceptance_checks(manifest=manifest, validation=validation)
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase14CloseoutError("Phase 14 closeout checks failed: " + ", ".join(failed))

        source_payload = {
            "contract_version": PHASE14_CLOSEOUT_CONTRACT_VERSION,
            "as_of_date": review_input.as_of_date.isoformat(),
            "phase13_acceptance_sha256": review_input.phase13_acceptance_sha256,
            "manifest_sha256": sha256_file(self.engine.manifest_path(review_input.as_of_date)),
            "validation_sha256": sha256_file(self.validator.report_path),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE14_CLOSEOUT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": review_input.as_of_date.isoformat(),
            "phase13_acceptance_sha256": review_input.phase13_acceptance_sha256,
            "phase14_manifest_sha256": source_payload["manifest_sha256"],
            "phase14_validation_sha256": source_payload["validation_sha256"],
            "phase13_case_count": review_input.phase13_case_count,
            "phase13_review_ready_count": review_input.review_ready_count,
            "ai_review_count": int(manifest["ai_review_count"]),
            "alert_artifact_count": int(manifest["alert_artifact_count"]),
            "disposition_counts": manifest["disposition_counts"],
            "provider_initialized": bool(manifest["provider_initialized"]),
            "provider_calls": int(manifest["provider_calls"]),
            "external_deliveries": 0,
            "zero_review_noop": review_input.review_ready_count == 0,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "position_writes": 0,
            "execution_present": False,
            "final_disposition": {
                "phase14_accepted": True,
                "ai_disposition_is_review_not_trade_signal": True,
                "deterministic_phase13_case_remains_immutable": True,
                "alert_records_are_artifacts_not_external_deliveries": True,
                "ai_has_no_broker_or_order_authority": True,
                "next_phase": PHASE14_NEXT_PHASE,
            },
            "pass": True,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
