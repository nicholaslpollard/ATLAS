from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.backtesting.phase11_closeout import (
    PHASE11_CLOSEOUT_CONTRACT_VERSION,
    PHASE11_NEXT_PHASE,
    Phase11Closeout,
)
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.discovery.current_candidates import (
    CURRENT_CANDIDATE_MATERIALIZATION_CONTRACT_VERSION,
    CurrentCandidateMaterializer,
)
from packages.features.partition_store import FeaturePartitionManifest, sha256_file
from packages.schemas.candidate_promotion import CandidatePromotionRecord


PHASE12_INPUT_CONTRACT_VERSION = "phase12-input-v1-accepted-phase11-promoted-only"


class Phase12InputError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase12InputError(f"missing {label}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase12InputError(f"invalid JSON for {label}: {path}") from exc


@dataclass(frozen=True, slots=True)
class Phase12ResearchInput:
    contract_version: str
    source_fingerprint: str
    as_of_date: date
    phase11_acceptance_path: Path
    phase11_acceptance_sha256: str
    current_manifest_path: Path
    current_manifest_sha256: str
    promoted_path: Path
    promoted_sha256: str
    feature_path: Path
    feature_sha256: str
    canonical_path: Path
    canonical_sha256: str
    promoted_candidates: tuple[CandidatePromotionRecord, ...]

    @property
    def promoted_count(self) -> int:
        return len(self.promoted_candidates)

    def public_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "source_fingerprint": self.source_fingerprint,
            "as_of_date": self.as_of_date.isoformat(),
            "phase11_acceptance_path": str(self.phase11_acceptance_path.resolve()),
            "phase11_acceptance_sha256": self.phase11_acceptance_sha256,
            "current_manifest_path": str(self.current_manifest_path.resolve()),
            "current_manifest_sha256": self.current_manifest_sha256,
            "promoted_path": str(self.promoted_path.resolve()),
            "promoted_sha256": self.promoted_sha256,
            "feature_path": str(self.feature_path.resolve()),
            "feature_sha256": self.feature_sha256,
            "canonical_path": str(self.canonical_path.resolve()),
            "canonical_sha256": self.canonical_sha256,
            "promoted_count": self.promoted_count,
            "promoted_instrument_ids": [item.instrument_id for item in self.promoted_candidates],
        }


class Phase12ResearchInputResolver:
    """Resolve Phase 12 strictly from the accepted Phase 11 promoted artifact."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.phase11 = Phase11Closeout(settings)
        self.candidates = CurrentCandidateMaterializer(settings)

    def resolve(self, as_of_date: date | None = None) -> Phase12ResearchInput:
        acceptance = _read_json(self.phase11.report_path, "Phase 11 final acceptance")
        if acceptance.get("contract_version") != PHASE11_CLOSEOUT_CONTRACT_VERSION:
            raise Phase12InputError("Phase 11 final acceptance contract changed")
        if acceptance.get("pass") is not True:
            raise Phase12InputError("Phase 11 final acceptance is not passing")
        disposition = dict(acceptance.get("final_disposition") or {})
        if disposition.get("phase11_accepted") is not True or disposition.get("next_phase") != PHASE11_NEXT_PHASE:
            raise Phase12InputError("Phase 11 final disposition does not hand off to Phase 12")
        accepted_date = date.fromisoformat(str(acceptance["as_of_date"]))
        if as_of_date is not None and as_of_date != accepted_date:
            raise Phase12InputError("requested Phase 12 date differs from accepted Phase 11 date")

        current_manifest_path = self.candidates.manifest_path(accepted_date)
        current = _read_json(current_manifest_path, "Phase 11 current candidate manifest")
        if current.get("contract_version") != CURRENT_CANDIDATE_MATERIALIZATION_CONTRACT_VERSION:
            raise Phase12InputError("Phase 11 current candidate contract changed")
        current_sha = sha256_file(current_manifest_path)
        if acceptance.get("current_candidate_manifest_sha256") != current_sha:
            raise Phase12InputError("Phase 11 acceptance no longer binds the current candidate manifest")
        if current.get("pass") is not True:
            raise Phase12InputError("Phase 11 current candidate manifest is not passing")

        promoted_path = Path(str(current["promoted_path"]))
        if not promoted_path.is_file():
            raise Phase12InputError(f"Phase 11 promoted artifact is missing: {promoted_path}")
        promoted_sha = sha256_file(promoted_path)
        if current.get("promoted_sha256") != promoted_sha:
            raise Phase12InputError("Phase 11 promoted artifact hash changed")

        promoted: list[CandidatePromotionRecord] = []
        if promoted_path.stat().st_size:
            for line in promoted_path.read_text(encoding="utf-8").splitlines():
                record = CandidatePromotionRecord.model_validate_json(line)
                if not record.promoted:
                    raise Phase12InputError("Phase 11 promoted artifact contains a rejected candidate")
                promoted.append(record)
        if len(promoted) != int(current.get("promoted_count", -1)):
            raise Phase12InputError("Phase 11 promoted candidate count changed")
        if len(promoted) != int(acceptance.get("promoted_count", -1)):
            raise Phase12InputError("Phase 11 acceptance promoted count disagrees with artifact")
        if len({item.instrument_id for item in promoted}) != len(promoted):
            raise Phase12InputError("Phase 11 promoted candidate identities are duplicated")

        feature_path = self.paths.feature_file(Timeframe.DAY_1, accepted_date)
        feature_manifest_path = self.paths.feature_manifest_file(Timeframe.DAY_1, accepted_date)
        feature_manifest = FeaturePartitionManifest.from_dict(
            _read_json(feature_manifest_path, "accepted 1d feature manifest")
        )
        feature_manifest.validate_contract(Timeframe.DAY_1, accepted_date)
        feature_sha = sha256_file(feature_path)
        if feature_manifest.feature_sha256 != feature_sha:
            raise Phase12InputError("accepted 1d feature snapshot hash changed")
        lineage = dict(current.get("lineage") or {})
        if lineage.get("feature_1d_sha256") != feature_sha:
            raise Phase12InputError("Phase 11 candidate lineage no longer binds current features")

        canonical_path = self.paths.canonical_file(Timeframe.DAY_1, accepted_date)
        canonical_sha = sha256_file(canonical_path)
        if Path(feature_manifest.source_path).resolve() != canonical_path.resolve():
            raise Phase12InputError("feature manifest canonical source path changed")
        if feature_manifest.source_sha256 != canonical_sha:
            raise Phase12InputError("feature manifest canonical source hash changed")
        if lineage.get("canonical_1d_source_sha256") != canonical_sha:
            raise Phase12InputError("Phase 11 candidate lineage no longer binds canonical 1d source")

        source_payload = {
            "contract_version": PHASE12_INPUT_CONTRACT_VERSION,
            "as_of_date": accepted_date.isoformat(),
            "phase11_acceptance_sha256": sha256_file(self.phase11.report_path),
            "current_candidate_manifest_sha256": current_sha,
            "promoted_sha256": promoted_sha,
            "feature_sha256": feature_sha,
            "canonical_sha256": canonical_sha,
            "promoted_instrument_ids": [item.instrument_id for item in promoted],
        }
        return Phase12ResearchInput(
            contract_version=PHASE12_INPUT_CONTRACT_VERSION,
            source_fingerprint=_stable_hash(source_payload),
            as_of_date=accepted_date,
            phase11_acceptance_path=self.phase11.report_path,
            phase11_acceptance_sha256=sha256_file(self.phase11.report_path),
            current_manifest_path=current_manifest_path,
            current_manifest_sha256=current_sha,
            promoted_path=promoted_path,
            promoted_sha256=promoted_sha,
            feature_path=feature_path,
            feature_sha256=feature_sha,
            canonical_path=canonical_path,
            canonical_sha256=canonical_sha,
            promoted_candidates=tuple(promoted),
        )
