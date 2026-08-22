from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.ai.phase14_closeout import (
    PHASE14_CLOSEOUT_CONTRACT_VERSION,
    PHASE14_NEXT_PHASE,
    Phase14Closeout,
)
from packages.ai.phase14_engine import (
    PHASE14_MANIFEST_CONTRACT_VERSION,
    PHASE14_NO_REVIEW_DISPOSITION,
    Phase14AuditEngine,
)
from packages.ai.phase14_source import Phase14ReviewInputResolver
from packages.ai.phase14_validation import Phase14IndependentValidator
from packages.core.settings import AtlasSettings
from packages.execution.phase15_foundation import (
    Phase15CumulativeFoundationBinding,
    Phase15CumulativeFoundationResolver,
)
from packages.features.partition_store import sha256_file
from packages.schemas.ai_review import AIReviewRecord, AlertArtifactRecord
from packages.schemas.case_file import Phase13CaseFile
from packages.schemas.deep_research import DeepResearchCase


PHASE15_INPUT_CONTRACT_VERSION = (
    "phase15-input-v2-cumulative-foundation-plus-accepted-phase14-immutable-phase13-lineage"
)


class Phase15InputError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase15InputError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase15InputError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Phase15InputError(f"{label} must be a JSON object")
    return value


@dataclass(frozen=True, slots=True)
class Phase15ExecutionInput:
    contract_version: str
    source_fingerprint: str
    as_of_date: date
    cumulative_foundation: Phase15CumulativeFoundationBinding
    phase14_acceptance_path: Path
    phase14_acceptance_sha256: str
    phase14_manifest_path: Path
    phase14_manifest_sha256: str
    phase14_validation_path: Path
    phase14_validation_sha256: str
    phase13_cases: tuple[Phase13CaseFile, ...]
    phase13_case_paths: tuple[Path, ...]
    phase13_case_sha256: tuple[str, ...]
    phase12_research_cases: tuple[DeepResearchCase, ...]
    reviews: tuple[AIReviewRecord, ...]
    review_paths: tuple[Path, ...]
    review_sha256: tuple[str, ...]
    alerts: tuple[AlertArtifactRecord, ...]
    alert_paths: tuple[Path, ...]
    alert_sha256: tuple[str, ...]

    @property
    def execution_case_count(self) -> int:
        return len(self.phase13_cases)

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "source_fingerprint": self.source_fingerprint,
            "as_of_date": self.as_of_date.isoformat(),
            "cumulative_foundation": self.cumulative_foundation.public_dict(),
            "phase14_acceptance_path": str(self.phase14_acceptance_path.resolve()),
            "phase14_acceptance_sha256": self.phase14_acceptance_sha256,
            "phase14_manifest_path": str(self.phase14_manifest_path.resolve()),
            "phase14_manifest_sha256": self.phase14_manifest_sha256,
            "phase14_validation_path": str(self.phase14_validation_path.resolve()),
            "phase14_validation_sha256": self.phase14_validation_sha256,
            "execution_case_count": self.execution_case_count,
            "instrument_ids": [item.instrument_id for item in self.phase13_cases],
            "phase13_case_sha256": list(self.phase13_case_sha256),
            "review_sha256": list(self.review_sha256),
            "alert_sha256": list(self.alert_sha256),
        }


class Phase15ExecutionInputResolver:
    """Resolve execution inputs only from accepted cumulative and Phase 14 authority."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.foundation = Phase15CumulativeFoundationResolver(settings)
        self.closeout = Phase14Closeout(settings)
        self.engine = Phase14AuditEngine(settings)
        self.validator = Phase14IndependentValidator(settings)
        self.phase14_input = Phase14ReviewInputResolver(settings)

    def resolve(self, as_of_date: date | None = None) -> Phase15ExecutionInput:
        try:
            cumulative = self.foundation.resolve()
        except RuntimeError as exc:
            raise Phase15InputError("Phase 15 cumulative foundation prerequisite failed") from exc

        acceptance = _read_json(self.closeout.report_path, "Phase 14 final acceptance")
        if acceptance.get("contract_version") != PHASE14_CLOSEOUT_CONTRACT_VERSION:
            raise Phase15InputError("Phase 14 final acceptance contract changed")
        if acceptance.get("pass") is not True:
            raise Phase15InputError("Phase 14 final acceptance is not passing")
        disposition = dict(acceptance.get("final_disposition") or {})
        if disposition.get("phase14_accepted") is not True:
            raise Phase15InputError("Phase 14 final disposition is not accepted")
        if disposition.get("next_phase") != PHASE14_NEXT_PHASE:
            raise Phase15InputError("Phase 14 final disposition does not hand off to Phase 15")
        if disposition.get("ai_disposition_is_review_not_trade_signal") is not True:
            raise Phase15InputError("Phase 14 AI authority boundary changed")
        if disposition.get("ai_has_no_broker_or_order_authority") is not True:
            raise Phase15InputError("Phase 14 AI broker/order boundary changed")

        accepted_date = date.fromisoformat(str(acceptance["as_of_date"]))
        if as_of_date is not None and as_of_date != accepted_date:
            raise Phase15InputError("requested Phase 15 date differs from accepted Phase 14 date")
        if accepted_date != cumulative.history_end:
            raise Phase15InputError("Phase 14 accepted date differs from cumulative foundation endpoint")

        manifest_path = self.engine.manifest_path(accepted_date)
        manifest = _read_json(manifest_path, "Phase 14 manifest")
        if manifest.get("contract_version") != PHASE14_MANIFEST_CONTRACT_VERSION:
            raise Phase15InputError("Phase 14 manifest contract changed")
        if manifest.get("pass") is not True:
            raise Phase15InputError("Phase 14 manifest is not passing")
        manifest_sha = sha256_file(manifest_path)
        if acceptance.get("phase14_manifest_sha256") != manifest_sha:
            raise Phase15InputError("Phase 14 acceptance no longer binds its manifest")

        validation_path = self.validator.report_path
        validation = _read_json(validation_path, "Phase 14 independent validation")
        if validation.get("pass") is not True:
            raise Phase15InputError("Phase 14 independent validation is not passing")
        validation_sha = sha256_file(validation_path)
        if acceptance.get("phase14_validation_sha256") != validation_sha:
            raise Phase15InputError("Phase 14 acceptance no longer binds independent validation")

        upstream = self.phase14_input.resolve(accepted_date)
        records = manifest.get("records")
        if not isinstance(records, list):
            raise Phase15InputError("Phase 14 manifest records are malformed")
        if len(records) != upstream.review_ready_count:
            raise Phase15InputError("Phase 14 record count differs from review-ready case count")
        if int(acceptance.get("ai_review_count", -1)) != len(records):
            raise Phase15InputError("Phase 14 acceptance review count changed")
        if int(acceptance.get("alert_artifact_count", -1)) != len(records):
            raise Phase15InputError("Phase 14 acceptance alert count changed")

        cases: list[Phase13CaseFile] = []
        case_paths: list[Path] = []
        case_hashes: list[str] = []
        research_cases: list[DeepResearchCase] = []
        reviews: list[AIReviewRecord] = []
        review_paths: list[Path] = []
        review_hashes: list[str] = []
        alerts: list[AlertArtifactRecord] = []
        alert_paths: list[Path] = []
        alert_hashes: list[str] = []

        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise Phase15InputError("Phase 14 manifest record is malformed")
            case = upstream.review_ready_cases[index]
            research = upstream.phase12_research_cases[index]
            case_path = upstream.phase13_case_paths[index]
            case_sha = upstream.phase13_case_sha256[index]
            if record.get("instrument_id") != case.instrument_id or record.get("ticker") != case.ticker:
                raise Phase15InputError("Phase 14 record identity differs from immutable Phase 13 case")
            if record.get("phase13_case_sha256") != case_sha:
                raise Phase15InputError("Phase 14 record no longer binds Phase 13 case")
            if not case.phase14_review_ready:
                raise Phase15InputError("Phase 15 received a non-review-ready Phase 13 case")

            review_path = Path(str(record.get("review_path", "")))
            alert_path = Path(str(record.get("alert_path", "")))
            if not review_path.is_file() or not alert_path.is_file():
                raise Phase15InputError("Phase 14 review/alert artifact is missing")
            review_sha = sha256_file(review_path)
            alert_sha = sha256_file(alert_path)
            if record.get("review_sha256") != review_sha or record.get("alert_sha256") != alert_sha:
                raise Phase15InputError("Phase 14 review/alert artifact hash changed")
            review = AIReviewRecord.model_validate_json(review_path.read_text(encoding="utf-8"))
            alert = AlertArtifactRecord.model_validate_json(alert_path.read_text(encoding="utf-8"))
            if review.phase13_case_sha256 != case_sha or alert.phase13_case_sha256 != case_sha:
                raise Phase15InputError("Phase 14 artifacts no longer bind immutable Phase 13 case")
            if alert.ai_review_sha256 != review_sha:
                raise Phase15InputError("Phase 14 alert no longer binds AI review")
            if review.disposition_is_trade_signal or review.ai_created_order:
                raise Phase15InputError("Phase 14 AI authority boundary changed")
            if alert.execution_present:
                raise Phase15InputError("Phase 14 alert unexpectedly contains execution state")

            cases.append(case)
            case_paths.append(case_path)
            case_hashes.append(case_sha)
            research_cases.append(research)
            reviews.append(review)
            review_paths.append(review_path)
            review_hashes.append(review_sha)
            alerts.append(alert)
            alert_paths.append(alert_path)
            alert_hashes.append(alert_sha)

        if not records:
            if acceptance.get("zero_review_noop") is not True:
                raise Phase15InputError("zero-review Phase 14 acceptance lost no-op disposition")
            if manifest.get("no_review_disposition") != PHASE14_NO_REVIEW_DISPOSITION:
                raise Phase15InputError("Phase 14 zero-review disposition changed")
            if manifest.get("provider_initialized") is not False or int(manifest.get("provider_calls", -1)) != 0:
                raise Phase15InputError("zero-review Phase 14 unexpectedly initialized/called AI provider")

        phase14_acceptance_sha = sha256_file(self.closeout.report_path)
        source_payload = {
            "contract_version": PHASE15_INPUT_CONTRACT_VERSION,
            "as_of_date": accepted_date.isoformat(),
            "cumulative_foundation_fingerprint": cumulative.foundation_fingerprint,
            "cumulative_acceptance_sha256": cumulative.acceptance_sha256,
            "cumulative_validation_sha256": cumulative.validation_sha256,
            "phase14_acceptance_sha256": phase14_acceptance_sha,
            "phase14_manifest_sha256": manifest_sha,
            "phase14_validation_sha256": validation_sha,
            "phase13_case_hashes": case_hashes,
            "review_hashes": review_hashes,
            "alert_hashes": alert_hashes,
        }
        return Phase15ExecutionInput(
            contract_version=PHASE15_INPUT_CONTRACT_VERSION,
            source_fingerprint=_stable_hash(source_payload),
            as_of_date=accepted_date,
            cumulative_foundation=cumulative,
            phase14_acceptance_path=self.closeout.report_path,
            phase14_acceptance_sha256=phase14_acceptance_sha,
            phase14_manifest_path=manifest_path,
            phase14_manifest_sha256=manifest_sha,
            phase14_validation_path=validation_path,
            phase14_validation_sha256=validation_sha,
            phase13_cases=tuple(cases),
            phase13_case_paths=tuple(case_paths),
            phase13_case_sha256=tuple(case_hashes),
            phase12_research_cases=tuple(research_cases),
            reviews=tuple(reviews),
            review_paths=tuple(review_paths),
            review_sha256=tuple(review_hashes),
            alerts=tuple(alerts),
            alert_paths=tuple(alert_paths),
            alert_sha256=tuple(alert_hashes),
        )
