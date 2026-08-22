from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.analogues.engine import (
    PHASE12_NO_CANDIDATE_DISPOSITION,
    PHASE12_RESEARCH_MANIFEST_CONTRACT_VERSION,
    DeepCandidateResearchEngine,
)
from packages.analogues.phase12_closeout import (
    PHASE12_CLOSEOUT_CONTRACT_VERSION,
    PHASE12_NEXT_PHASE,
    Phase12Closeout,
)
from packages.analogues.phase12_validation import Phase12IndependentValidator
from packages.analogues.source import Phase12ResearchInputResolver
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.schemas.deep_research import DeepResearchCase


PHASE13_INPUT_CONTRACT_VERSION = "phase13-input-v1-accepted-phase12-case-files-only"


class Phase13InputError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase13InputError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase13InputError(f"invalid JSON for {label}: {path}") from exc


@dataclass(frozen=True, slots=True)
class Phase13PlanningInput:
    contract_version: str
    source_fingerprint: str
    as_of_date: date
    phase12_acceptance_path: Path
    phase12_acceptance_sha256: str
    phase12_manifest_path: Path
    phase12_manifest_sha256: str
    phase12_validation_path: Path
    phase12_validation_sha256: str
    feature_path: Path
    feature_sha256: str
    canonical_path: Path
    canonical_sha256: str
    research_cases: tuple[DeepResearchCase, ...]
    research_case_paths: tuple[Path, ...]
    research_case_sha256: tuple[str, ...]

    @property
    def case_count(self) -> int:
        return len(self.research_cases)

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "source_fingerprint": self.source_fingerprint,
            "as_of_date": self.as_of_date.isoformat(),
            "phase12_acceptance_path": str(self.phase12_acceptance_path.resolve()),
            "phase12_acceptance_sha256": self.phase12_acceptance_sha256,
            "phase12_manifest_path": str(self.phase12_manifest_path.resolve()),
            "phase12_manifest_sha256": self.phase12_manifest_sha256,
            "phase12_validation_path": str(self.phase12_validation_path.resolve()),
            "phase12_validation_sha256": self.phase12_validation_sha256,
            "feature_path": str(self.feature_path.resolve()),
            "feature_sha256": self.feature_sha256,
            "canonical_path": str(self.canonical_path.resolve()),
            "canonical_sha256": self.canonical_sha256,
            "case_count": self.case_count,
            "case_instrument_ids": [item.instrument_id for item in self.research_cases],
            "research_case_sha256": list(self.research_case_sha256),
        }


class Phase13PlanningInputResolver:
    """Resolve Phase 13 exclusively from the accepted Phase 12 final disposition."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase12 = Phase12Closeout(settings)
        self.engine = DeepCandidateResearchEngine(settings)
        self.validator = Phase12IndependentValidator(settings)
        self.phase12_input = Phase12ResearchInputResolver(settings)

    def resolve(self, as_of_date: date | None = None) -> Phase13PlanningInput:
        acceptance = _read_json(self.phase12.report_path, "Phase 12 final acceptance")
        if acceptance.get("contract_version") != PHASE12_CLOSEOUT_CONTRACT_VERSION:
            raise Phase13InputError("Phase 12 final acceptance contract changed")
        if acceptance.get("pass") is not True:
            raise Phase13InputError("Phase 12 final acceptance is not passing")
        disposition = dict(acceptance.get("final_disposition") or {})
        if disposition.get("phase12_accepted") is not True:
            raise Phase13InputError("Phase 12 final disposition is not accepted")
        if disposition.get("next_phase") != PHASE12_NEXT_PHASE:
            raise Phase13InputError("Phase 12 final disposition does not hand off to Phase 13")
        accepted_date = date.fromisoformat(str(acceptance["as_of_date"]))
        if as_of_date is not None and as_of_date != accepted_date:
            raise Phase13InputError("requested Phase 13 date differs from accepted Phase 12 date")

        manifest_path = self.engine.manifest_path(accepted_date)
        manifest = _read_json(manifest_path, "Phase 12 research manifest")
        if manifest.get("contract_version") != PHASE12_RESEARCH_MANIFEST_CONTRACT_VERSION:
            raise Phase13InputError("Phase 12 research manifest contract changed")
        if manifest.get("pass") is not True:
            raise Phase13InputError("Phase 12 research manifest is not passing")
        manifest_sha = sha256_file(manifest_path)
        if acceptance.get("phase12_research_manifest_sha256") != manifest_sha:
            raise Phase13InputError("Phase 12 acceptance no longer binds its research manifest")

        validation_path = self.validator.report_path
        validation = _read_json(validation_path, "Phase 12 independent validation")
        if validation.get("pass") is not True:
            raise Phase13InputError("Phase 12 independent validation is not passing")
        validation_sha = sha256_file(validation_path)
        if acceptance.get("phase12_validation_sha256") != validation_sha:
            raise Phase13InputError("Phase 12 acceptance no longer binds independent validation")

        upstream = self.phase12_input.resolve(accepted_date)
        records = manifest.get("cases")
        if not isinstance(records, list):
            raise Phase13InputError("Phase 12 case manifest records are malformed")
        cases: list[DeepResearchCase] = []
        case_paths: list[Path] = []
        case_hashes: list[str] = []
        for record in records:
            if not isinstance(record, dict):
                raise Phase13InputError("Phase 12 case manifest record is malformed")
            path = Path(str(record.get("case_path", "")))
            if not path.is_file():
                raise Phase13InputError(f"Phase 12 research case is missing: {path}")
            digest = sha256_file(path)
            if record.get("case_sha256") != digest:
                raise Phase13InputError("Phase 12 research case hash changed")
            case = DeepResearchCase.model_validate_json(path.read_text(encoding="utf-8"))
            if case.as_of_date != accepted_date:
                raise Phase13InputError("Phase 12 case date changed")
            cases.append(case)
            case_paths.append(path)
            case_hashes.append(digest)

        expected_count = int(acceptance.get("research_case_count", -1))
        if len(cases) != expected_count or len(cases) != int(manifest.get("research_case_count", -1)):
            raise Phase13InputError("accepted Phase 12 research case count changed")
        if len({item.instrument_id for item in cases}) != len(cases):
            raise Phase13InputError("Phase 12 research case identities are duplicated")
        if expected_count == 0:
            if acceptance.get("zero_candidate_noop") is not True:
                raise Phase13InputError("zero-case Phase 12 acceptance lost no-op disposition")
            if manifest.get("historical_source_accessed") is not False:
                raise Phase13InputError("zero-case Phase 12 unexpectedly accessed historical source")
            if manifest.get("no_candidate_disposition") != PHASE12_NO_CANDIDATE_DISPOSITION:
                raise Phase13InputError("zero-case Phase 12 disposition changed")

        source_payload = {
            "contract_version": PHASE13_INPUT_CONTRACT_VERSION,
            "as_of_date": accepted_date.isoformat(),
            "phase12_acceptance_sha256": sha256_file(self.phase12.report_path),
            "phase12_manifest_sha256": manifest_sha,
            "phase12_validation_sha256": validation_sha,
            "feature_sha256": upstream.feature_sha256,
            "canonical_sha256": upstream.canonical_sha256,
            "case_hashes": case_hashes,
        }
        return Phase13PlanningInput(
            contract_version=PHASE13_INPUT_CONTRACT_VERSION,
            source_fingerprint=_stable_hash(source_payload),
            as_of_date=accepted_date,
            phase12_acceptance_path=self.phase12.report_path,
            phase12_acceptance_sha256=sha256_file(self.phase12.report_path),
            phase12_manifest_path=manifest_path,
            phase12_manifest_sha256=manifest_sha,
            phase12_validation_path=validation_path,
            phase12_validation_sha256=validation_sha,
            feature_path=upstream.feature_path,
            feature_sha256=upstream.feature_sha256,
            canonical_path=upstream.canonical_path,
            canonical_sha256=upstream.canonical_sha256,
            research_cases=tuple(cases),
            research_case_paths=tuple(case_paths),
            research_case_sha256=tuple(case_hashes),
        )
