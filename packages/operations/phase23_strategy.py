from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.discovery.current_candidates import CurrentCandidateMaterializer
from packages.features.partition_store import sha256_file
from packages.ml.model_registry import accepted_model_id, model_registry_fingerprint
from packages.operations.phase23_policy import (
    PHASE23_ACCEPTED_ML_MODEL_ID,
    PHASE23_FROZEN_STRATEGY_SUPPORT,
    PHASE23_FROZEN_SUPPORTED_STRATEGIES,
    phase23_policy_fingerprint,
)


PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION = (
    "phase23-current-strategy-handoff-v1-frozen-phase11-support-current-evaluation"
)


class Phase23StrategyHandoffError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase23StrategyHandoffError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase23StrategyHandoffError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase23StrategyHandoffError(f"{label} must be a JSON object")
    return payload


def _support_statuses(study: dict[str, Any]) -> dict[str, str]:
    rows = study.get("studies")
    if not isinstance(rows, list):
        raise Phase23StrategyHandoffError("historical strategy study has no studies list")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("support"), dict):
            raise Phase23StrategyHandoffError("historical strategy study row is malformed")
        strategy_id = str(row.get("strategy_id") or "")
        support = dict(row["support"])
        if not strategy_id:
            raise Phase23StrategyHandoffError("historical strategy study row has no strategy id")
        result[strategy_id] = str(support.get("status") or "")
    return dict(sorted(result.items()))


@dataclass(frozen=True, slots=True)
class Phase23CurrentStrategyHandoff:
    as_of_date: date
    path: Path
    sha256: str
    source_fingerprint: str
    current_candidate_manifest_sha256: str
    promoted_count: int


class Phase23CurrentStrategyHandoffStore:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "operations" / "phase23" / "v1" / "strategy_handoffs"
        self.candidates = CurrentCandidateMaterializer(settings)

    def path(self, as_of_date: date) -> Path:
        return self.root / f"year={as_of_date.year:04d}" / f"{as_of_date}.json"

    def verify_frozen_study(self, historical_study_path: Path) -> dict[str, Any]:
        study = _read_json(historical_study_path, "accepted Phase 11 historical strategy study")
        if study.get("pass") is not True:
            raise Phase23StrategyHandoffError("accepted Phase 11 historical strategy study is not passing")
        statuses = _support_statuses(study)
        if statuses != dict(sorted(PHASE23_FROZEN_STRATEGY_SUPPORT.items())):
            raise Phase23StrategyHandoffError("Phase 11 historical support differs from frozen Phase 23 authority")
        supported = tuple(sorted(key for key, value in statuses.items() if value == "SUPPORTED"))
        if supported != PHASE23_FROZEN_SUPPORTED_STRATEGIES:
            raise Phase23StrategyHandoffError("Phase 23 supported-strategy set changed")
        if accepted_model_id() != PHASE23_ACCEPTED_ML_MODEL_ID:
            raise Phase23StrategyHandoffError("accepted production ML model changed")
        return study

    def write(
        self,
        *,
        as_of_date: date,
        historical_study_path: Path,
        current_manifest_path: Path,
    ) -> Phase23CurrentStrategyHandoff:
        self.verify_frozen_study(historical_study_path)
        current = _read_json(current_manifest_path, "Phase 23 current candidate manifest")
        if current.get("pass") is not True or current.get("as_of_date") != as_of_date.isoformat():
            raise Phase23StrategyHandoffError("current candidate manifest is not passing for requested date")
        lineage = dict(current.get("lineage") or {})
        if lineage.get("historical_strategy_study_sha256") != sha256_file(historical_study_path):
            raise Phase23StrategyHandoffError("current candidate manifest does not bind frozen historical support")
        if lineage.get("accepted_ml_model_id") != PHASE23_ACCEPTED_ML_MODEL_ID:
            raise Phase23StrategyHandoffError("current candidate manifest production model changed")
        if lineage.get("accepted_ml_model_fingerprint") != model_registry_fingerprint():
            raise Phase23StrategyHandoffError("current candidate manifest model fingerprint changed")
        promoted_count = int(current.get("promoted_count", -1))
        if PHASE23_FROZEN_SUPPORTED_STRATEGIES == () and promoted_count != 0:
            raise Phase23StrategyHandoffError(
                "current candidates promoted despite frozen zero-SUPPORTED strategy authority"
            )
        source_payload = {
            "contract_version": PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION,
            "phase23_policy_fingerprint": phase23_policy_fingerprint(),
            "as_of_date": as_of_date.isoformat(),
            "historical_strategy_study_sha256": sha256_file(historical_study_path),
            "current_candidate_manifest_sha256": sha256_file(current_manifest_path),
            "accepted_ml_model_id": PHASE23_ACCEPTED_ML_MODEL_ID,
            "accepted_ml_model_fingerprint": model_registry_fingerprint(),
            "frozen_strategy_support": dict(sorted(PHASE23_FROZEN_STRATEGY_SUPPORT.items())),
            "supported_strategy_ids": list(PHASE23_FROZEN_SUPPORTED_STRATEGIES),
            "promoted_count": promoted_count,
        }
        payload: dict[str, object] = {
            **source_payload,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(source_payload),
            "historical_strategy_study_rerun": False,
            "production_ml_writes": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "pass": True,
        }
        path = self.path(as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
        return self.resolve(as_of_date)

    def resolve(self, as_of_date: date) -> Phase23CurrentStrategyHandoff:
        path = self.path(as_of_date)
        payload = _read_json(path, "Phase 23 current strategy handoff")
        if payload.get("contract_version") != PHASE23_CURRENT_STRATEGY_HANDOFF_CONTRACT_VERSION:
            raise Phase23StrategyHandoffError("Phase 23 current strategy handoff contract changed")
        if payload.get("pass") is not True or payload.get("phase23_policy_fingerprint") != phase23_policy_fingerprint():
            raise Phase23StrategyHandoffError("Phase 23 current strategy handoff is not accepted")
        if payload.get("as_of_date") != as_of_date.isoformat():
            raise Phase23StrategyHandoffError("Phase 23 current strategy handoff date changed")
        if payload.get("historical_strategy_study_rerun") is not False:
            raise Phase23StrategyHandoffError("routine Phase 23 unexpectedly reran historical strategy study")
        if payload.get("frozen_strategy_support") != dict(sorted(PHASE23_FROZEN_STRATEGY_SUPPORT.items())):
            raise Phase23StrategyHandoffError("Phase 23 current strategy handoff support changed")
        if tuple(payload.get("supported_strategy_ids") or ()) != PHASE23_FROZEN_SUPPORTED_STRATEGIES:
            raise Phase23StrategyHandoffError("Phase 23 current supported-strategy set changed")
        if payload.get("accepted_ml_model_id") != PHASE23_ACCEPTED_ML_MODEL_ID:
            raise Phase23StrategyHandoffError("Phase 23 current strategy handoff model changed")
        if payload.get("accepted_ml_model_fingerprint") != model_registry_fingerprint():
            raise Phase23StrategyHandoffError("Phase 23 current strategy handoff model fingerprint changed")
        for field in ("production_ml_writes", "broker_writes", "order_writes"):
            if int(payload.get(field, -1)) != 0:
                raise Phase23StrategyHandoffError(f"Phase 23 current strategy handoff write boundary changed: {field}")
        source_payload = {
            key: payload[key]
            for key in (
                "contract_version",
                "phase23_policy_fingerprint",
                "as_of_date",
                "historical_strategy_study_sha256",
                "current_candidate_manifest_sha256",
                "accepted_ml_model_id",
                "accepted_ml_model_fingerprint",
                "frozen_strategy_support",
                "supported_strategy_ids",
                "promoted_count",
            )
        }
        if payload.get("source_fingerprint") != _stable_hash(source_payload):
            raise Phase23StrategyHandoffError("Phase 23 current strategy handoff fingerprint changed")
        return Phase23CurrentStrategyHandoff(
            as_of_date=as_of_date,
            path=path,
            sha256=sha256_file(path),
            source_fingerprint=str(payload["source_fingerprint"]),
            current_candidate_manifest_sha256=str(payload["current_candidate_manifest_sha256"]),
            promoted_count=int(payload["promoted_count"]),
        )
