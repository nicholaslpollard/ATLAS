from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.ai.case_builder import build_review_case_packet
from packages.ai.phase14_engine import (
    PHASE14_MANIFEST_CONTRACT_VERSION,
    PHASE14_NO_REVIEW_DISPOSITION,
    Phase14AuditEngine,
)
from packages.ai.phase14_policy import (
    PHASE14_BROKER_WRITES,
    PHASE14_EXTERNAL_DELIVERY_ENABLED,
    PHASE14_ORDER_WRITES,
    PHASE14_POSITION_WRITES,
    PHASE14_PRODUCTION_ML_WRITES,
    phase14_policy_fingerprint,
    phase14_policy_payload,
)
from packages.ai.phase14_source import Phase14ReviewInputResolver
from packages.ai.structured_output import validate_review_payload
from packages.alerts.builder import build_alert_artifact
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.schemas.ai_review import AIReviewRecord, AlertArtifactRecord


PHASE14_VALIDATION_CONTRACT_VERSION = (
    "phase14-validation-v1-independent-lineage-prompt-grounding-alert-recompute"
)

_FORBIDDEN_AI_KEYS = {
    "entry",
    "entry_price",
    "reference_entry",
    "stop",
    "stop_loss",
    "target",
    "take_profit",
    "quantity",
    "proposed_quantity",
    "position_size",
    "broker",
    "order",
    "order_id",
}


class Phase14ValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase14ValidationError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase14ValidationError(f"invalid JSON for {label}: {path}") from exc


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in _FORBIDDEN_AI_KEYS:
                return True
            if _contains_forbidden_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


class Phase14IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.input_resolver = Phase14ReviewInputResolver(settings)
        self.engine = Phase14AuditEngine(settings)
        self.root = self.engine.root
        self.report_path = self.root / "phase14_validation.json"

    def run(self, *, as_of_date: date | None = None) -> dict[str, object]:
        review_input = self.input_resolver.resolve(as_of_date)
        manifest_path = self.engine.manifest_path(review_input.as_of_date)
        manifest = _read_json(manifest_path, "Phase 14 manifest")
        if manifest.get("contract_version") != PHASE14_MANIFEST_CONTRACT_VERSION:
            raise Phase14ValidationError("Phase 14 manifest contract changed")
        if manifest.get("pass") is not True:
            raise Phase14ValidationError("Phase 14 manifest is not passing")

        checks: dict[str, bool] = {
            "accepted_phase13_input_reverified": (
                dict(manifest.get("phase14_input") or {}) == review_input.public_dict()
            ),
            "preregistered_policy_exact": (
                manifest.get("policy") == phase14_policy_payload()
                and manifest.get("policy_fingerprint") == phase14_policy_fingerprint()
            ),
            "review_count_exact": int(manifest.get("ai_review_count", -1))
            == review_input.review_ready_count,
            "alert_count_exact": int(manifest.get("alert_artifact_count", -1))
            == review_input.review_ready_count,
            "external_delivery_disabled": manifest.get("external_delivery_enabled") is False
            and PHASE14_EXTERNAL_DELIVERY_ENABLED is False
            and int(manifest.get("external_deliveries", -1)) == 0,
            "production_ml_writes_zero": int(manifest.get("production_ml_writes", -1)) == 0
            and PHASE14_PRODUCTION_ML_WRITES == 0,
            "broker_writes_zero": int(manifest.get("broker_writes", -1)) == 0
            and PHASE14_BROKER_WRITES == 0,
            "order_writes_zero": int(manifest.get("order_writes", -1)) == 0
            and PHASE14_ORDER_WRITES == 0,
            "position_writes_zero": int(manifest.get("position_writes", -1)) == 0
            and PHASE14_POSITION_WRITES == 0,
            "execution_absent": manifest.get("execution_present") is False,
        }
        records = manifest.get("records")
        if not isinstance(records, list):
            raise Phase14ValidationError("Phase 14 manifest records are malformed")
        if len(records) != review_input.review_ready_count:
            raise Phase14ValidationError("Phase 14 manifest record count changed")

        disposition_counts = {"APPROVE": 0, "CAUTIOUS": 0, "REJECT": 0}
        review_checks: list[bool] = []
        alert_checks: list[bool] = []
        no_mutation_checks: list[bool] = []
        for index, (record, case, research, case_sha) in enumerate(
            zip(
                records,
                review_input.review_ready_cases,
                review_input.phase12_research_cases,
                review_input.phase13_case_sha256,
                strict=True,
            )
        ):
            if not isinstance(record, dict):
                raise Phase14ValidationError(f"Phase 14 manifest record {index} is malformed")
            if record.get("instrument_id") != case.instrument_id or record.get("ticker") != case.ticker:
                raise Phase14ValidationError("Phase 14 manifest identity differs from accepted case")
            if record.get("phase13_case_sha256") != case_sha:
                raise Phase14ValidationError("Phase 14 record is not bound to accepted case hash")

            raw_path = Path(str(record.get("raw_response_path", "")))
            review_path = Path(str(record.get("review_path", "")))
            alert_path = Path(str(record.get("alert_path", "")))
            for path, key in (
                (raw_path, "raw_response_sha256"),
                (review_path, "review_sha256"),
                (alert_path, "alert_sha256"),
            ):
                if not path.is_file() or sha256_file(path) != record.get(key):
                    raise Phase14ValidationError(f"Phase 14 artifact hash mismatch: {path}")

            review_record = AIReviewRecord.model_validate_json(review_path.read_text(encoding="utf-8"))
            packet = build_review_case_packet(case, research)
            validated_payload = validate_review_payload(
                review_record.review.model_dump(mode="json"),
                allowed_evidence_paths=packet.evidence_paths,
            )
            review_ok = (
                review_record.instrument_id == case.instrument_id
                and review_record.ticker == case.ticker
                and review_record.as_of_date == case.as_of_date
                and review_record.phase13_case_sha256 == case_sha
                and review_record.prompt_contract_version == packet.contract_version
                and review_record.prompt_fingerprint == packet.fingerprint
                and record.get("prompt_fingerprint") == packet.fingerprint
                and validated_payload == review_record.review
                and review_record.disposition_is_trade_signal is False
                and review_record.ai_changed_deterministic_case is False
                and review_record.ai_created_order is False
            )
            review_checks.append(review_ok)
            no_mutation_checks.append(
                not _contains_forbidden_key(review_record.review.model_dump(mode="json"))
            )

            review_sha = sha256_file(review_path)
            expected_alert = build_alert_artifact(
                case,
                phase13_case_sha256=case_sha,
                review_record=review_record,
                ai_review_sha256=review_sha,
            )
            actual_alert = AlertArtifactRecord.model_validate_json(alert_path.read_text(encoding="utf-8"))
            alert_checks.append(expected_alert == actual_alert)
            disposition_counts[review_record.review.disposition.value] += 1

        if review_input.review_ready_count == 0:
            zero_noop = (
                manifest.get("provider_initialized") is False
                and int(manifest.get("provider_calls", -1)) == 0
                and int(manifest.get("ai_review_count", -1)) == 0
                and int(manifest.get("alert_artifact_count", -1)) == 0
                and manifest.get("no_review_disposition") == PHASE14_NO_REVIEW_DISPOSITION
            )
        else:
            zero_noop = True
            checks["provider_calls_exact"] = (
                manifest.get("provider_initialized") is True
                and int(manifest.get("provider_calls", -1)) == review_input.review_ready_count
            )

        checks.update(
            {
                "zero_review_noop_is_valid": zero_noop,
                "reviews_independently_revalidated": all(review_checks),
                "alerts_independently_recomputed": all(alert_checks),
                "ai_structured_mutation_fields_absent": all(no_mutation_checks),
                "disposition_counts_exact": manifest.get("disposition_counts") == disposition_counts,
            }
        )
        passed = all(checks.values())
        source_payload = {
            "contract_version": PHASE14_VALIDATION_CONTRACT_VERSION,
            "as_of_date": review_input.as_of_date.isoformat(),
            "manifest_sha256": sha256_file(manifest_path),
            "phase14_input_fingerprint": review_input.source_fingerprint,
            "policy_fingerprint": phase14_policy_fingerprint(),
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": PHASE14_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "as_of_date": review_input.as_of_date.isoformat(),
            "phase14_manifest_sha256": source_payload["manifest_sha256"],
            "phase14_input_fingerprint": review_input.source_fingerprint,
            "review_ready_count": review_input.review_ready_count,
            "checks": checks,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "position_writes": 0,
            "external_deliveries": 0,
            "execution_present": False,
            "pass": passed,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        if not passed:
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase14ValidationError("Phase 14 independent validation failed: " + ", ".join(failed))
        return report
