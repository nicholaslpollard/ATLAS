from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.execution.phase15_foundation import (
    PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
    PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END,
    Phase15CumulativeFoundationBinding,
)
from packages.features.partition_store import sha256_file
from packages.operations.phase23_policy import (
    PHASE23_ACCEPTED_ML_MODEL_ID,
    PHASE23_FROZEN_STRATEGY_SUPPORT,
    phase23_policy_fingerprint,
)


PHASE23_ANALYSIS_HANDOFF_CONTRACT_VERSION = (
    "phase23-analysis-handoff-v1-cumulative-baseline-extended-current-lineage"
)


class Phase23HandoffError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase23HandoffError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase23HandoffError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase23HandoffError(f"{label} must be a JSON object")
    return payload


@dataclass(frozen=True, slots=True)
class Phase23AnalysisHandoffBinding:
    as_of_date: date
    path: Path
    sha256: str
    source_fingerprint: str
    phase14_acceptance_sha256: str
    baseline_foundation_fingerprint: str
    baseline_history_end: date

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": PHASE23_ANALYSIS_HANDOFF_CONTRACT_VERSION,
            "as_of_date": self.as_of_date.isoformat(),
            "path": str(self.path.resolve()),
            "sha256": self.sha256,
            "source_fingerprint": self.source_fingerprint,
            "phase14_acceptance_sha256": self.phase14_acceptance_sha256,
            "baseline_foundation_fingerprint": self.baseline_foundation_fingerprint,
            "baseline_history_end": self.baseline_history_end.isoformat(),
        }


class Phase23AnalysisHandoffStore:
    def __init__(self, settings: AtlasSettings) -> None:
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "operations" / "phase23" / "v1" / "handoffs"

    def path(self, as_of_date: date) -> Path:
        return self.root / f"year={as_of_date.year:04d}" / f"{as_of_date}.json"

    def write(
        self,
        *,
        as_of_date: date,
        phase14_acceptance_path: Path,
        stage_hashes: dict[str, str],
        sessions_advanced: tuple[date, ...],
        external_read_classes_used: tuple[str, ...],
    ) -> Phase23AnalysisHandoffBinding:
        if as_of_date <= PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END:
            raise Phase23HandoffError("Phase 23 operational handoff must extend beyond the frozen cumulative endpoint")
        if not phase14_acceptance_path.is_file():
            raise Phase23HandoffError("Phase 14 acceptance is missing for Phase 23 handoff")
        bad_hashes = sorted(
            key for key, value in stage_hashes.items() if len(str(value)) != 64
        )
        if bad_hashes:
            raise Phase23HandoffError("Phase 23 stage hashes are malformed: " + ", ".join(bad_hashes))
        phase14_sha = sha256_file(phase14_acceptance_path)
        source_payload = {
            "contract_version": PHASE23_ANALYSIS_HANDOFF_CONTRACT_VERSION,
            "phase23_policy_fingerprint": phase23_policy_fingerprint(),
            "as_of_date": as_of_date.isoformat(),
            "baseline_foundation_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
            "baseline_history_end": PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END.isoformat(),
            "accepted_ml_model_id": PHASE23_ACCEPTED_ML_MODEL_ID,
            "frozen_strategy_support": dict(sorted(PHASE23_FROZEN_STRATEGY_SUPPORT.items())),
            "phase14_acceptance_sha256": phase14_sha,
            "sessions_advanced": [item.isoformat() for item in sessions_advanced],
            "external_read_classes_used": list(external_read_classes_used),
            "stage_hashes": dict(sorted(stage_hashes.items())),
        }
        report: dict[str, object] = {
            **source_payload,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "canonical_writes": 0,
            "model_writes": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automatic_broker_failover": False,
            "pass": True,
        }
        path = self.path(as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
        return Phase23AnalysisHandoffBinding(
            as_of_date=as_of_date,
            path=path,
            sha256=sha256_file(path),
            source_fingerprint=str(report["source_fingerprint"]),
            phase14_acceptance_sha256=phase14_sha,
            baseline_foundation_fingerprint=PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
            baseline_history_end=PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END,
        )

    def resolve(
        self,
        *,
        as_of_date: date,
        cumulative: Phase15CumulativeFoundationBinding,
        expected_phase14_acceptance_sha256: str,
    ) -> Phase23AnalysisHandoffBinding:
        path = self.path(as_of_date)
        payload = _read_json(path, "Phase 23 current-analysis handoff")
        if payload.get("contract_version") != PHASE23_ANALYSIS_HANDOFF_CONTRACT_VERSION:
            raise Phase23HandoffError("Phase 23 handoff contract changed")
        if payload.get("pass") is not True:
            raise Phase23HandoffError("Phase 23 handoff is not passing")
        if payload.get("phase23_policy_fingerprint") != phase23_policy_fingerprint():
            raise Phase23HandoffError("Phase 23 handoff policy fingerprint changed")
        if payload.get("as_of_date") != as_of_date.isoformat():
            raise Phase23HandoffError("Phase 23 handoff date mismatch")
        if as_of_date <= cumulative.history_end:
            raise Phase23HandoffError("Phase 23 handoff does not extend the cumulative foundation")
        if payload.get("baseline_foundation_fingerprint") != cumulative.foundation_fingerprint:
            raise Phase23HandoffError("Phase 23 handoff cumulative foundation mismatch")
        if payload.get("baseline_history_end") != cumulative.history_end.isoformat():
            raise Phase23HandoffError("Phase 23 handoff cumulative endpoint mismatch")
        if payload.get("accepted_ml_model_id") != PHASE23_ACCEPTED_ML_MODEL_ID:
            raise Phase23HandoffError("Phase 23 handoff production model changed")
        if payload.get("frozen_strategy_support") != dict(sorted(PHASE23_FROZEN_STRATEGY_SUPPORT.items())):
            raise Phase23HandoffError("Phase 23 handoff strategy-support authority changed")
        if payload.get("phase14_acceptance_sha256") != expected_phase14_acceptance_sha256:
            raise Phase23HandoffError("Phase 23 handoff no longer binds current Phase 14 acceptance")
        for field in ("model_writes", "broker_writes", "order_writes", "paper_submits", "live_writes"):
            if int(payload.get(field, -1)) != 0:
                raise Phase23HandoffError(f"Phase 23 handoff mutation boundary changed: {field}")
        if payload.get("automatic_broker_failover") is not False:
            raise Phase23HandoffError("Phase 23 handoff enabled automatic broker failover")
        stage_hashes = payload.get("stage_hashes")
        if not isinstance(stage_hashes, dict) or not stage_hashes:
            raise Phase23HandoffError("Phase 23 handoff stage lineage is missing")
        if any(len(str(value)) != 64 for value in stage_hashes.values()):
            raise Phase23HandoffError("Phase 23 handoff stage lineage contains malformed hashes")
        source_payload = {
            key: payload[key]
            for key in (
                "contract_version",
                "phase23_policy_fingerprint",
                "as_of_date",
                "baseline_foundation_fingerprint",
                "baseline_history_end",
                "accepted_ml_model_id",
                "frozen_strategy_support",
                "phase14_acceptance_sha256",
                "sessions_advanced",
                "external_read_classes_used",
                "stage_hashes",
            )
        }
        if payload.get("source_fingerprint") != _stable_hash(source_payload):
            raise Phase23HandoffError("Phase 23 handoff source fingerprint changed")
        return Phase23AnalysisHandoffBinding(
            as_of_date=as_of_date,
            path=path,
            sha256=sha256_file(path),
            source_fingerprint=str(payload["source_fingerprint"]),
            phase14_acceptance_sha256=expected_phase14_acceptance_sha256,
            baseline_foundation_fingerprint=cumulative.foundation_fingerprint,
            baseline_history_end=cumulative.history_end,
        )
