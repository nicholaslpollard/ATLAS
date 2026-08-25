from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .phase24_gate1_policy import phase24_gate1_policy_fingerprint
from .phase24_gate2 import PHASE24_GATE2_CONTRACT_VERSION


PHASE24_GATE2_VALIDATION_CONTRACT_VERSION = (
    "phase24-gate2-validation-v1-persisted-selection-finalist-lock-no-protected"
)


class Phase24Gate2ValidationError(RuntimeError):
    pass


class Phase24Gate2IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase24" / "v1" / "gate2"
        self.selection_report_path = self.root / "selection_report.json"
        self.selection_lock_path = self.root / "selection_lock.json"
        self.internal_report_path = self.root / "internal_validation_report.json"
        self.finalist_lock_path = self.root / "finalist_lock.json"
        self.validation_path = self.root / "independent_validation.json"

    @staticmethod
    def _read(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise Phase24Gate2ValidationError(f"missing {label}: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Phase24Gate2ValidationError(f"invalid JSON for {label}: {path}") from exc
        if not isinstance(payload, dict):
            raise Phase24Gate2ValidationError(f"{label} must be a JSON object")
        return payload

    def run(self) -> dict[str, object]:
        selection = self._read(self.selection_report_path, "selection report")
        selection_lock = self._read(self.selection_lock_path, "selection lock")
        internal = self._read(self.internal_report_path, "internal-validation report")
        finalist_lock = self._read(self.finalist_lock_path, "finalist lock")
        policy_fp = phase24_gate1_policy_fingerprint()
        selected = tuple(str(item) for item in selection_lock.get("selected_strategy_ids", []))
        finalists = tuple(str(item) for item in finalist_lock.get("fresh_finalist_strategy_ids", []))
        zero_keys = (
            "protected_evidence_reads",
            "provider_reads",
            "broker_reads",
            "order_writes",
            "paper_submits",
            "live_writes",
            "phase11_support_writes",
        )
        checks = {
            "selection_contract_exact": selection.get("contract_version") == PHASE24_GATE2_CONTRACT_VERSION,
            "internal_contract_exact": internal.get("contract_version") == PHASE24_GATE2_CONTRACT_VERSION,
            "policy_fingerprint_exact": all(
                payload.get("phase24_gate1_policy_fingerprint") == policy_fp
                for payload in (selection, selection_lock, internal, finalist_lock)
            ),
            "selection_report_hash_bound": selection_lock.get("selection_report_sha256")
            == sha256_file(self.selection_report_path),
            "selection_lock_hash_bound": internal.get("selection_lock_sha256")
            == sha256_file(self.selection_lock_path)
            == finalist_lock.get("selection_lock_sha256"),
            "internal_report_hash_bound": finalist_lock.get("internal_validation_report_sha256")
            == sha256_file(self.internal_report_path),
            "selection_frozen_before_internal": selection_lock.get(
                "internal_validation_has_not_influenced_selection"
            )
            is True,
            "no_second_best_fallback": internal.get("fallback_to_second_best_after_internal_failure")
            is False,
            "selected_count_bounded": len(selected) <= 8 and len(selected) == len(set(selected)),
            "fresh_finalists_subset_of_selected": set(finalists).issubset(set(selected)),
            "fresh_finalists_are_new_v2": all("_v2_" in item for item in finalists),
            "protected_authority_disabled": finalist_lock.get("protected_evaluation_authority") is False,
            "selection_pass": selection.get("pass") is True,
            "internal_pass": internal.get("pass") is True,
            "finalist_lock_pass": finalist_lock.get("pass") is True,
            "selection_zero_authority": all(int(selection.get(key, -1)) == 0 for key in zero_keys),
            "internal_zero_authority": all(int(internal.get(key, -1)) == 0 for key in zero_keys),
            "finalist_zero_authority": all(int(finalist_lock.get(key, -1)) == 0 for key in zero_keys),
        }
        report = {
            "contract_version": PHASE24_GATE2_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "phase24_gate1_policy_fingerprint": policy_fp,
            "selection_report_sha256": sha256_file(self.selection_report_path),
            "selection_lock_sha256": sha256_file(self.selection_lock_path),
            "internal_validation_report_sha256": sha256_file(self.internal_report_path),
            "finalist_lock_sha256": sha256_file(self.finalist_lock_path),
            "selected_strategy_ids": list(selected),
            "fresh_finalist_strategy_ids": list(finalists),
            "checks": checks,
            "pass": all(checks.values()),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.validation_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not report["pass"]:
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase24Gate2ValidationError("Gate 2 independent validation failed: " + ", ".join(failed))
        report["report_path"] = str(self.validation_path.resolve())
        return report
