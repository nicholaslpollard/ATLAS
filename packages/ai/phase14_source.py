from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.portfolio.phase13_closeout import (
    PHASE13_CLOSEOUT_CONTRACT_VERSION,
    PHASE13_NEXT_PHASE,
    Phase13Closeout,
)
from packages.portfolio.phase13_engine import PHASE13_MANIFEST_CONTRACT_VERSION, Phase13CaseEngine
from packages.portfolio.phase13_source import Phase13PlanningInputResolver
from packages.portfolio.phase13_validation import Phase13IndependentValidator
from packages.schemas.case_file import PHASE13_CASE_FILE_CONTRACT_VERSION, Phase13CaseFile
from packages.schemas.deep_research import DeepResearchCase


PHASE14_INPUT_CONTRACT_VERSION = (
    "phase14-input-v1-accepted-phase13-review-ready-plus-hash-matched-phase12-research"
)


class Phase14InputError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase14InputError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase14InputError(f"invalid JSON for {label}: {path}") from exc


@dataclass(frozen=True, slots=True)
class Phase14ReviewInput:
    contract_version: str
    source_fingerprint: str
    as_of_date: date
    phase13_acceptance_path: Path
    phase13_acceptance_sha256: str
    phase13_manifest_path: Path
    phase13_manifest_sha256: str
    phase13_validation_path: Path
    phase13_validation_sha256: str
    phase13_case_count: int
    review_ready_cases: tuple[Phase13CaseFile, ...]
    phase13_case_paths: tuple[Path, ...]
    phase13_case_sha256: tuple[str, ...]
    phase12_research_cases: tuple[DeepResearchCase, ...]
    phase12_research_sha256: tuple[str, ...]

    @property
    def review_ready_count(self) -> int:
        return len(self.review_ready_cases)

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "source_fingerprint": self.source_fingerprint,
            "as_of_date": self.as_of_date.isoformat(),
            "phase13_acceptance_path": str(self.phase13_acceptance_path.resolve()),
            "phase13_acceptance_sha256": self.phase13_acceptance_sha256,
            "phase13_manifest_path": str(self.phase13_manifest_path.resolve()),
            "phase13_manifest_sha256": self.phase13_manifest_sha256,
            "phase13_validation_path": str(self.phase13_validation_path.resolve()),
            "phase13_validation_sha256": self.phase13_validation_sha256,
            "phase13_case_count": self.phase13_case_count,
            "review_ready_count": self.review_ready_count,
            "instrument_ids": [item.instrument_id for item in self.review_ready_cases],
            "phase13_case_sha256": list(self.phase13_case_sha256),
            "phase12_research_sha256": list(self.phase12_research_sha256),
        }


class Phase14ReviewInputResolver:
    """Resolve AI review inputs only from an independently accepted Phase 13 closeout."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.closeout = Phase13Closeout(settings)
        self.engine = Phase13CaseEngine(settings)
        self.validator = Phase13IndependentValidator(settings)
        self.phase13_input = Phase13PlanningInputResolver(settings)

    def resolve(self, as_of_date: date | None = None) -> Phase14ReviewInput:
        acceptance = _read_json(self.closeout.report_path, "Phase 13 final acceptance")
        if acceptance.get("contract_version") != PHASE13_CLOSEOUT_CONTRACT_VERSION:
            raise Phase14InputError("Phase 13 final acceptance contract changed")
        if acceptance.get("pass") is not True:
            raise Phase14InputError("Phase 13 final acceptance is not passing")
        disposition = dict(acceptance.get("final_disposition") or {})
        if disposition.get("phase13_accepted") is not True:
            raise Phase14InputError("Phase 13 final disposition is not accepted")
        if disposition.get("next_phase") != PHASE13_NEXT_PHASE:
            raise Phase14InputError("Phase 13 final disposition does not hand off to Phase 14")
        accepted_date = date.fromisoformat(str(acceptance["as_of_date"]))
        if as_of_date is not None and as_of_date != accepted_date:
            raise Phase14InputError("requested Phase 14 date differs from accepted Phase 13 date")

        manifest_path = self.engine.manifest_path(accepted_date)
        manifest = _read_json(manifest_path, "Phase 13 case manifest")
        if manifest.get("contract_version") != PHASE13_MANIFEST_CONTRACT_VERSION:
            raise Phase14InputError("Phase 13 case manifest contract changed")
        if manifest.get("pass") is not True:
            raise Phase14InputError("Phase 13 case manifest is not passing")
        manifest_sha = sha256_file(manifest_path)
        if acceptance.get("phase13_manifest_sha256") != manifest_sha:
            raise Phase14InputError("Phase 13 acceptance no longer binds its case manifest")

        validation_path = self.validator.report_path
        validation = _read_json(validation_path, "Phase 13 independent validation")
        if validation.get("pass") is not True:
            raise Phase14InputError("Phase 13 independent validation is not passing")
        validation_sha = sha256_file(validation_path)
        if acceptance.get("phase13_validation_sha256") != validation_sha:
            raise Phase14InputError("Phase 13 acceptance no longer binds independent validation")

        upstream = self.phase13_input.resolve(accepted_date)
        research_by_key = {
            (item.instrument_id, digest): item
            for item, digest in zip(
                upstream.research_cases,
                upstream.research_case_sha256,
                strict=True,
            )
        }

        records = manifest.get("cases")
        if not isinstance(records, list):
            raise Phase14InputError("Phase 13 case manifest records are malformed")
        expected_case_count = int(acceptance.get("case_file_count", -1))
        if len(records) != expected_case_count or len(records) != int(manifest.get("case_file_count", -1)):
            raise Phase14InputError("accepted Phase 13 case count changed")

        review_cases: list[Phase13CaseFile] = []
        case_paths: list[Path] = []
        case_hashes: list[str] = []
        research_cases: list[DeepResearchCase] = []
        research_hashes: list[str] = []
        seen_ids: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise Phase14InputError("Phase 13 case manifest record is malformed")
            path = Path(str(record.get("case_path", "")))
            if not path.is_file():
                raise Phase14InputError(f"Phase 13 case file is missing: {path}")
            digest = sha256_file(path)
            if record.get("case_sha256") != digest:
                raise Phase14InputError("Phase 13 case hash changed")
            case = Phase13CaseFile.model_validate_json(path.read_text(encoding="utf-8"))
            if case.contract_version != PHASE13_CASE_FILE_CONTRACT_VERSION:
                raise Phase14InputError("Phase 13 case contract changed")
            if case.as_of_date != accepted_date:
                raise Phase14InputError("Phase 13 case date changed")
            if bool(record.get("phase14_review_ready")) != case.phase14_review_ready:
                raise Phase14InputError("Phase 13 manifest review-ready flag changed")
            if not case.phase14_review_ready:
                continue
            if case.instrument_id in seen_ids:
                raise Phase14InputError("Phase 14 review-ready identities are duplicated")
            key = (case.instrument_id, case.phase12_case_sha256)
            research = research_by_key.get(key)
            if research is None:
                raise Phase14InputError("Phase 13 case no longer matches accepted Phase 12 research evidence")
            seen_ids.add(case.instrument_id)
            review_cases.append(case)
            case_paths.append(path)
            case_hashes.append(digest)
            research_cases.append(research)
            research_hashes.append(case.phase12_case_sha256)

        expected_ready = int(acceptance.get("phase14_review_ready_count", -1))
        if len(review_cases) != expected_ready or len(review_cases) != int(manifest.get("phase14_review_ready_count", -1)):
            raise Phase14InputError("accepted Phase 13 review-ready count changed")
        if expected_ready == 0:
            if expected_case_count == 0 and acceptance.get("zero_case_noop") is not True:
                raise Phase14InputError("zero-case Phase 13 acceptance lost no-op disposition")

        source_payload = {
            "contract_version": PHASE14_INPUT_CONTRACT_VERSION,
            "as_of_date": accepted_date.isoformat(),
            "phase13_acceptance_sha256": sha256_file(self.closeout.report_path),
            "phase13_manifest_sha256": manifest_sha,
            "phase13_validation_sha256": validation_sha,
            "phase13_case_hashes": case_hashes,
            "phase12_research_hashes": research_hashes,
        }
        return Phase14ReviewInput(
            contract_version=PHASE14_INPUT_CONTRACT_VERSION,
            source_fingerprint=_stable_hash(source_payload),
            as_of_date=accepted_date,
            phase13_acceptance_path=self.closeout.report_path,
            phase13_acceptance_sha256=sha256_file(self.closeout.report_path),
            phase13_manifest_path=manifest_path,
            phase13_manifest_sha256=manifest_sha,
            phase13_validation_path=validation_path,
            phase13_validation_sha256=validation_sha,
            phase13_case_count=expected_case_count,
            review_ready_cases=tuple(review_cases),
            phase13_case_paths=tuple(case_paths),
            phase13_case_sha256=tuple(case_hashes),
            phase12_research_cases=tuple(research_cases),
            phase12_research_sha256=tuple(research_hashes),
        )
