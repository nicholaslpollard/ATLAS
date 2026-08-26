from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase24_gate2 import TrancheMetrics, holm_bonferroni, internal_checks, selection_checks
from .phase25_gate9 import (
    PHASE25_GATE9_FINALIST_LOCK_CONTRACT_VERSION,
    PHASE25_GATE9_REPORT_CONTRACT_VERSION,
    PHASE25_GATE9_SELECTION_LOCK_CONTRACT_VERSION,
    Phase25Gate9Robustness,
)
from .phase25_gate8_policy import (
    PHASE25_GATE9_MULTIPLE_TESTING_ALPHA,
    PHASE25_GATE9_MULTIPLE_TESTING_METHOD,
    phase25_gate9_policy_fingerprint,
)


PHASE25_GATE9_VALIDATION_CONTRACT_VERSION = (
    "phase25-gate9-validation-v1-locks-checks-global-holm-no-protected"
)


class Phase25Gate9IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate9IndependentValidationError(f"missing Gate9 evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate9IndependentValidationError(f"invalid Gate9 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate9IndependentValidationError("Gate9 JSON must be an object")
    return value


def _metrics(payload: dict[str, object]) -> TrancheMetrics:
    raw = dict(payload["metrics"])
    raw["fold_means"] = tuple(raw.get("fold_means", []))
    return TrancheMetrics(**raw)


class Phase25Gate9IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate9"

    def report_path(self, through_date: date) -> Path:
        return self.root / f"through={through_date}" / "independent_validation.json"

    def run(self, *, through_date: date) -> dict[str, object]:
        gate = Phase25Gate9Robustness(self.settings)
        report_path = gate.report_path(through_date)
        report = _read_json(report_path)
        selection_lock_path = gate.selection_lock_path(through_date)
        finalist_lock_path = gate.finalist_lock_path(through_date)
        selection_lock = _read_json(selection_lock_path)
        finalist_lock = _read_json(finalist_lock_path)
        if report.get("contract_version") != PHASE25_GATE9_REPORT_CONTRACT_VERSION:
            raise Phase25Gate9IndependentValidationError("Gate9 report contract mismatch")
        if report.get("phase25_gate9_policy_fingerprint") != phase25_gate9_policy_fingerprint():
            raise Phase25Gate9IndependentValidationError("Gate9 policy fingerprint mismatch")
        if selection_lock.get("contract_version") != PHASE25_GATE9_SELECTION_LOCK_CONTRACT_VERSION:
            raise Phase25Gate9IndependentValidationError("Gate9 selection lock contract mismatch")
        if finalist_lock.get("contract_version") != PHASE25_GATE9_FINALIST_LOCK_CONTRACT_VERSION:
            raise Phase25Gate9IndependentValidationError("Gate9 finalist lock contract mismatch")

        selection_results = [dict(item) for item in report.get("selection_results", [])]
        p_values = {
            str(item["strategy_id"]): float(dict(item["metrics"])["primary_bootstrap_p_value"])
            for item in selection_results
            if dict(item["metrics"]).get("primary_bootstrap_p_value") is not None
        }
        expected_holm = holm_bonferroni(p_values, alpha=PHASE25_GATE9_MULTIPLE_TESTING_ALPHA)
        recomputed_selected: list[str] = []
        bad_selection_checks = 0
        for item in selection_results:
            checks = selection_checks(_metrics(item))
            if checks != dict(item["checks"]):
                bad_selection_checks += 1
            sid = str(item["strategy_id"])
            passed = bool(all(checks.values()) and expected_holm.get(sid, {}).get("rejected_null", False))
            if passed:
                recomputed_selected.append(sid)

        internal_results = [dict(item) for item in report.get("internal_results", [])]
        recomputed_finalists: list[str] = []
        bad_internal_checks = 0
        for item in internal_results:
            checks = internal_checks(_metrics(item))
            if checks != dict(item["checks"]):
                bad_internal_checks += 1
            if all(checks.values()):
                recomputed_finalists.append(str(item["strategy_id"]))

        selected = sorted(str(item) for item in report.get("selected_strategy_ids", []))
        finalists = sorted(str(item) for item in report.get("finalist_strategy_ids", []))
        checks = {
            "policy_exact": report.get("phase25_gate9_policy_fingerprint") == phase25_gate9_policy_fingerprint(),
            "multiplicity_method_exact": report.get("multiple_testing_method") == PHASE25_GATE9_MULTIPLE_TESTING_METHOD,
            "holm_recomputed_exact": dict(report.get("multiplicity", {})) == expected_holm,
            "selection_checks_recomputed": bad_selection_checks == 0,
            "selected_ids_recomputed": selected == sorted(recomputed_selected),
            "selection_lock_hash_exact": report.get("selection_lock_sha256") == sha256_file(selection_lock_path),
            "selection_lock_ids_exact": sorted(selection_lock.get("selected_strategy_ids", [])) == selected,
            "selection_locked_before_internal": selection_lock.get("internal_validation_has_not_influenced_selection") is True,
            "internal_checks_recomputed": bad_internal_checks == 0,
            "finalists_recomputed": finalists == sorted(recomputed_finalists),
            "finalist_lock_hash_exact": report.get("finalist_lock_sha256") == sha256_file(finalist_lock_path),
            "finalist_lock_ids_exact": sorted(finalist_lock.get("finalist_strategy_ids", [])) == finalists,
            "finalists_locked_before_protected": finalist_lock.get("protected_confirmation_has_not_influenced_finalists") is True,
            "no_fallback": finalist_lock.get("fallback_after_internal_failure") is False,
            "protected_reads_zero": int(report.get("protected_evidence_reads", -1)) == 0 and int(selection_lock.get("protected_evidence_reads", -1)) == 0 and int(finalist_lock.get("protected_evidence_reads", -1)) == 0,
            "support_writes_zero": int(report.get("phase11_support_writes", -1)) == 0 and report.get("support_replacement_authority") is False,
            "report_pass": report.get("pass") is True,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate9IndependentValidationError("Gate9 independent validation failed: " + ", ".join(failed))

        path = self.report_path(through_date)
        validation: dict[str, object] = {
            "contract_version": PHASE25_GATE9_VALIDATION_CONTRACT_VERSION,
            "through_date": through_date.isoformat(),
            "gate9_report_sha256": sha256_file(report_path),
            "selection_lock_sha256": sha256_file(selection_lock_path),
            "finalist_lock_sha256": sha256_file(finalist_lock_path),
            "selected_strategy_ids": selected,
            "finalist_strategy_ids": finalists,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(path.resolve()),
            "pass": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(validation, indent=2, sort_keys=True) + "\n")
        return validation
