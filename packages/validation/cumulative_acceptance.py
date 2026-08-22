from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .cumulative_policy import (
    CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
    CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION,
    cumulative_policy_fingerprint,
    cumulative_policy_payload,
)


CUMULATIVE_FOUNDATION_VALIDATION_VERSION = (
    "cumulative-foundation-validation-v1-independent-component-hash-authority-recheck"
)


class CumulativeFoundationValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise CumulativeFoundationValidationError(f"missing cumulative audit artifact: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CumulativeFoundationValidationError(f"invalid cumulative audit JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CumulativeFoundationValidationError(f"cumulative audit artifact is not an object: {path}")
    return value


class CumulativeFoundationIndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "validation" / "cumulative_foundation" / "v1"
        self.acceptance_path = self.root / "cumulative_foundation_acceptance.json"
        self.report_path = self.root / "cumulative_foundation_validation.json"

    def run(self) -> dict[str, object]:
        acceptance = _read(self.acceptance_path)
        component_hashes = acceptance.get("component_hashes")
        components = acceptance.get("components")
        if not isinstance(component_hashes, dict) or not isinstance(components, dict):
            raise CumulativeFoundationValidationError("cumulative acceptance component maps are malformed")

        hash_checks: dict[str, bool] = {}
        component_pass_checks: dict[str, bool] = {}
        for name, expected_sha in sorted(component_hashes.items()):
            path = self.root / str(name)
            payload = _read(path)
            hash_checks[str(name)] = sha256_file(path) == str(expected_sha)
            component_pass_checks[str(name)] = payload.get("pass") is True

        checks = {
            "acceptance_contract_exact": acceptance.get("contract_version")
            == CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
            "audit_contract_exact": acceptance.get("audit_contract_version")
            == CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION,
            "policy_exact": acceptance.get("policy") == cumulative_policy_payload(),
            "policy_fingerprint_exact": acceptance.get("policy_fingerprint")
            == cumulative_policy_fingerprint(),
            "all_component_hashes_exact": all(hash_checks.values()),
            "all_component_artifacts_pass": all(component_pass_checks.values()),
            "component_map_all_true": bool(components) and all(bool(v) for v in components.values()),
            "acceptance_pass": acceptance.get("pass") is True,
            "no_new_posthoc_thresholds": acceptance.get("new_posthoc_statistical_thresholds") is False,
            "canonical_writes_zero": int(acceptance.get("canonical_writes", -1)) == 0,
            "feature_writes_zero": int(acceptance.get("feature_writes", -1)) == 0,
            "regime_writes_zero": int(acceptance.get("regime_writes", -1)) == 0,
            "model_writes_zero": int(acceptance.get("model_writes", -1)) == 0,
            "broker_writes_zero": int(acceptance.get("broker_writes", -1)) == 0,
            "external_provider_calls_zero": int(acceptance.get("external_provider_calls", -1)) == 0,
        }
        passed = all(checks.values())
        source = {
            "contract_version": CUMULATIVE_FOUNDATION_VALIDATION_VERSION,
            "acceptance_sha256": sha256_file(self.acceptance_path),
            "policy_fingerprint": cumulative_policy_fingerprint(),
            "hash_checks": hash_checks,
            "component_pass_checks": component_pass_checks,
            "checks": checks,
        }
        report: dict[str, object] = {
            "contract_version": CUMULATIVE_FOUNDATION_VALIDATION_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source),
            "acceptance_sha256": source["acceptance_sha256"],
            "history_start": acceptance.get("history_start"),
            "history_end": acceptance.get("history_end"),
            "hash_checks": hash_checks,
            "component_pass_checks": component_pass_checks,
            "checks": checks,
            "pass": passed,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        if not passed:
            failed = sorted(name for name, value in checks.items() if not value)
            raise CumulativeFoundationValidationError(
                "cumulative independent validation failed: " + ", ".join(failed)
            )
        return report
