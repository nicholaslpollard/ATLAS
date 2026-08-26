from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY

from .phase25_gate11 import PHASE25_GATE11_REPORT_CONTRACT_VERSION, Phase25Gate11Closeout
from .phase25_gate8_policy import phase25_gate11_policy_fingerprint


PHASE25_GATE11_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate11-validation-v1-upstream-hashes-verdict-no-support-write"
)


class Phase25Gate11IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate11IndependentValidationError(f"missing Gate11 evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate11IndependentValidationError(f"invalid Gate11 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate11IndependentValidationError("Gate11 report must be an object")
    return value


class Phase25Gate11IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate11"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate = Phase25Gate11Closeout(self.settings)
        report_path = gate.report_path(through_date)
        report = _read_json(report_path)
        if report.get("contract_version") != PHASE25_GATE11_REPORT_CONTRACT_VERSION:
            raise Phase25Gate11IndependentValidationError("Gate11 report contract mismatch")
        if report.get("phase25_gate11_policy_fingerprint") != phase25_gate11_policy_fingerprint():
            raise Phase25Gate11IndependentValidationError("Gate11 policy fingerprint mismatch")
        selected = sorted(str(item) for item in report.get("selected_strategy_ids", []))
        finalists = sorted(str(item) for item in report.get("finalist_strategy_ids", []))
        confirmed = sorted(str(item) for item in report.get("confirmed_strategy_ids", []))
        if not finalists:
            expected_verdict = "NO_SUPPORT_REPLACEMENT_DEVELOPMENT_ROBUSTNESS_FAILED"
        elif not confirmed:
            expected_verdict = "NO_SUPPORT_REPLACEMENT_PROTECTED_CONFIRMATION_FAILED"
        else:
            expected_verdict = "RESEARCH_CANDIDATES_REQUIRE_FUTURE_PROSPECTIVE_CONFIRMATION"
        diagnostics = [dict(item) for item in report.get("strategy_diagnostics", [])]
        diagnostic_ids = sorted(str(item.get("strategy_id")) for item in diagnostics)
        expected_ids = sorted(strategy.metadata.strategy_id for strategy in DEFAULT_STRATEGY_REGISTRY.all())
        checks = {
            "policy_exact": report.get("phase25_gate11_policy_fingerprint") == phase25_gate11_policy_fingerprint(),
            "strategy_diagnostics_complete": diagnostic_ids == expected_ids,
            "selected_subset_registry": set(selected).issubset(set(expected_ids)),
            "finalists_subset_selected": set(finalists).issubset(set(selected)),
            "confirmed_subset_finalists": set(confirmed).issubset(set(finalists)),
            "verdict_recomputed": report.get("verdict") == expected_verdict,
            "support_map_unchanged": report.get("phase11_support_map_unchanged") is True,
            "support_authority_false": report.get("support_replacement_authority") is False,
            "support_writes_zero": int(report.get("phase11_support_writes", -1)) == 0,
            "future_prospective_required": report.get("future_prospective_required_for_authority") is True,
            "report_pass": report.get("pass") is True,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate11IndependentValidationError("Gate11 independent validation failed: " + ", ".join(failed))

        path = self.report_path(through_date)
        validation: dict[str, object] = {
            "contract_version": PHASE25_GATE11_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "gate11_report_sha256": sha256_file(report_path),
            "selected_strategy_ids": selected,
            "finalist_strategy_ids": finalists,
            "confirmed_strategy_ids": confirmed,
            "verdict": expected_verdict,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(validation, indent=2, sort_keys=True) + "\n")
        return validation
