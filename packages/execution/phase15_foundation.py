from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.validation.cumulative_acceptance import CUMULATIVE_FOUNDATION_VALIDATION_VERSION
from packages.validation.cumulative_policy import (
    CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
    CUMULATIVE_HISTORY_START,
    cumulative_policy_fingerprint,
)


PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT = (
    "6a3ff7ad3b6fc7dff95df42ec3cc89bfc38ab66f93bc4a125d4d1d87c85a63f6"
)
PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT = (
    "ad3039c63aceedab5176d674bcab5b7203cbb22b9440295a7a76bca7b9750375"
)
PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END = date(2026, 8, 14)
PHASE15_CUMULATIVE_FOUNDATION_BINDING_CONTRACT_VERSION = (
    "phase15-cumulative-foundation-binding-v1-exact-accepted-fingerprint-independent-validation"
)


class Phase15FoundationError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase15FoundationError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase15FoundationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Phase15FoundationError(f"{label} must be a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class Phase15CumulativeFoundationBinding:
    contract_version: str
    acceptance_path: Path
    acceptance_sha256: str
    validation_path: Path
    validation_sha256: str
    foundation_fingerprint: str
    policy_fingerprint: str
    history_start: date
    history_end: date

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "acceptance_path": str(self.acceptance_path.resolve()),
            "acceptance_sha256": self.acceptance_sha256,
            "validation_path": str(self.validation_path.resolve()),
            "validation_sha256": self.validation_sha256,
            "foundation_fingerprint": self.foundation_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "history_start": self.history_start.isoformat(),
            "history_end": self.history_end.isoformat(),
        }


class Phase15CumulativeFoundationResolver:
    """Bind Phase 15 to the exact target-machine cumulative foundation acceptance."""

    def __init__(self, settings: AtlasSettings) -> None:
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "validation" / "cumulative_foundation" / "v1"
        self.acceptance_path = self.root / "cumulative_foundation_acceptance.json"
        self.validation_path = self.root / "cumulative_foundation_validation.json"

    def resolve(self) -> Phase15CumulativeFoundationBinding:
        acceptance = _read_json(self.acceptance_path, "cumulative foundation acceptance")
        validation = _read_json(self.validation_path, "cumulative foundation independent validation")
        acceptance_sha = sha256_file(self.acceptance_path)
        validation_sha = sha256_file(self.validation_path)

        if cumulative_policy_fingerprint() != PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT:
            raise Phase15FoundationError("current cumulative policy fingerprint differs from Phase 15 accepted policy")
        if acceptance.get("contract_version") != CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION:
            raise Phase15FoundationError("cumulative foundation acceptance contract changed")
        if acceptance.get("pass") is not True:
            raise Phase15FoundationError("cumulative foundation acceptance is not passing")
        if acceptance.get("source_fingerprint") != PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT:
            raise Phase15FoundationError("cumulative foundation fingerprint differs from accepted Phase 15 authority")
        if acceptance.get("policy_fingerprint") != PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT:
            raise Phase15FoundationError("cumulative foundation policy fingerprint differs from accepted Phase 15 authority")
        if acceptance.get("history_start") != CUMULATIVE_HISTORY_START.isoformat():
            raise Phase15FoundationError("cumulative foundation history start changed")
        if acceptance.get("history_end") != PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END.isoformat():
            raise Phase15FoundationError("cumulative foundation history end changed")
        if acceptance.get("new_posthoc_statistical_thresholds") is not False:
            raise Phase15FoundationError("cumulative foundation introduced post-hoc statistical thresholds")
        for field in (
            "canonical_writes",
            "feature_writes",
            "regime_writes",
            "model_writes",
            "broker_writes",
            "external_provider_calls",
        ):
            if int(acceptance.get(field, -1)) != 0:
                raise Phase15FoundationError(f"cumulative foundation authority boundary changed: {field}")

        if validation.get("contract_version") != CUMULATIVE_FOUNDATION_VALIDATION_VERSION:
            raise Phase15FoundationError("cumulative foundation validation contract changed")
        if validation.get("pass") is not True:
            raise Phase15FoundationError("cumulative foundation independent validation is not passing")
        if validation.get("acceptance_sha256") != acceptance_sha:
            raise Phase15FoundationError("cumulative independent validation no longer binds acceptance artifact")
        checks = validation.get("checks")
        if not isinstance(checks, dict) or not checks or not all(bool(value) for value in checks.values()):
            raise Phase15FoundationError("cumulative independent validation checks are not all passing")

        return Phase15CumulativeFoundationBinding(
            contract_version=PHASE15_CUMULATIVE_FOUNDATION_BINDING_CONTRACT_VERSION,
            acceptance_path=self.acceptance_path,
            acceptance_sha256=acceptance_sha,
            validation_path=self.validation_path,
            validation_sha256=validation_sha,
            foundation_fingerprint=PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
            policy_fingerprint=PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
            history_start=CUMULATIVE_HISTORY_START,
            history_end=PHASE15_ACCEPTED_CUMULATIVE_HISTORY_END,
        )
