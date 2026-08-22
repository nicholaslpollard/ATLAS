from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from packages.core.settings import AtlasSettings
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.historical_backfill_long_history_dataset_validation import (
    GATE11C_DATASET_VALIDATION_CONTRACT_VERSION,
)
from packages.ml.historical_backfill_long_history_datasets import (
    GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION,
    GATE11C_DATASET_BUILD_CONTRACT_VERSION,
    GATE11C_EXPECTED_COMPOSITE_ROWS,
    HistoricalBackfillLongHistoryDatasetBuilder,
)
from packages.ml.historical_backfill_model_evaluation_design import (
    GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT,
    GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT,
)


STRATEGY_RESEARCH_SOURCE_CONTRACT_VERSION = (
    "strategy-research-source-v1-accepted-gate11c-c-composite"
)


class StrategyResearchSourceError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parquet_list(paths: tuple[Path, ...]) -> str:
    if not paths:
        raise StrategyResearchSourceError("strategy research source has no Parquet partitions")
    return "[" + ",".join(sql_string(path) for path in paths) + "]"


@dataclass(frozen=True, slots=True)
class StrategyResearchSource:
    contract_version: str
    source_fingerprint: str
    dataset_id: str
    dataset_lineage_fingerprint: str
    row_count: int
    first_session_date: str
    last_session_date: str
    builder_source_fingerprint: str
    validation_source_fingerprint: str
    b_manifest_sha256: str
    extension_manifest_sha256: str
    composite_manifest_sha256: str
    parquet_paths: tuple[Path, ...]

    @property
    def source_sql(self) -> str:
        return f"read_parquet({_parquet_list(self.parquet_paths)}, union_by_name=true)"

    def public_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["parquet_paths"] = [path.as_posix() for path in self.parquet_paths]
        return payload


class HistoricalStrategyResearchSourceResolver:
    """Resolve only the independently accepted Gate 11-C C composite.

    C is a manifest composition of the physical B dataset plus the accepted pre-seam
    extension. The model trained on C remains challenger-only; this resolver uses C as
    verified research data and does not alter model authority.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.builder = HistoricalBackfillLongHistoryDatasetBuilder(settings)
        self.validation_path = self.builder.root / "gate11c_dataset_validation_report.json"

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise StrategyResearchSourceError(f"missing {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StrategyResearchSourceError(f"invalid JSON for {label}: {path}") from exc

    def resolve(self) -> StrategyResearchSource:
        build = self._read_json(self.builder.report_path, "accepted Gate 11-C build report")
        validation = self._read_json(self.validation_path, "accepted Gate 11-C validation report")
        if build.get("contract_version") != GATE11C_DATASET_BUILD_CONTRACT_VERSION:
            raise StrategyResearchSourceError("Gate 11-C build contract changed")
        if build.get("source_fingerprint") != GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT:
            raise StrategyResearchSourceError("Gate 11-C build fingerprint is not accepted")
        if build.get("pass") is not True:
            raise StrategyResearchSourceError("Gate 11-C build report is not passing")
        if validation.get("contract_version") != GATE11C_DATASET_VALIDATION_CONTRACT_VERSION:
            raise StrategyResearchSourceError("Gate 11-C validation contract changed")
        if validation.get("source_fingerprint") != GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT:
            raise StrategyResearchSourceError("Gate 11-C validation fingerprint is not accepted")
        if validation.get("pass") is not True:
            raise StrategyResearchSourceError("Gate 11-C validation report is not passing")

        b = dict(build["B"])
        extension = dict(build["C_extension"])
        composite = dict(build["C_composite"])
        b_root = self.builder._dataset_root("B", str(b["dataset_id"]))  # noqa: SLF001
        extension_root = self.builder._dataset_root("C_extension", str(extension["dataset_id"]))  # noqa: SLF001
        composite_root = self.builder._dataset_root("C", str(composite["dataset_id"]))  # noqa: SLF001
        b_manifest_path = b_root / "manifest.json"
        extension_manifest_path = extension_root / "manifest.json"
        composite_manifest_path = composite_root / "manifest.json"
        b_manifest = self._read_json(b_manifest_path, "B manifest")
        extension_manifest = self._read_json(extension_manifest_path, "C-extension manifest")
        composite_manifest = self._read_json(composite_manifest_path, "C-composite manifest")

        if composite_manifest.get("contract_version") != GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION:
            raise StrategyResearchSourceError("C-composite manifest contract changed")
        if int(composite_manifest.get("physical_C_copy_of_B_rows", -1)) != 0:
            raise StrategyResearchSourceError("C-composite unexpectedly copied B rows")
        if composite_manifest.get("postseam_rows_are_exactly_parent_B") is not True:
            raise StrategyResearchSourceError("C-composite post-seam rows are not exact parent B")
        if int(composite_manifest.get("row_count", -1)) != GATE11C_EXPECTED_COMPOSITE_ROWS:
            raise StrategyResearchSourceError("C-composite accepted row count changed")

        b_paths = tuple(b_root / str(item["relative_path"]) for item in b_manifest.get("partitions", []))
        x_paths = tuple(
            extension_root / str(item["relative_path"])
            for item in extension_manifest.get("partitions", [])
        )
        parquet_paths = b_paths + x_paths
        if not parquet_paths or any(not path.is_file() for path in parquet_paths):
            raise StrategyResearchSourceError("C-composite physical partitions are incomplete")
        for root, manifest, paths in (
            (b_root, b_manifest, b_paths),
            (extension_root, extension_manifest, x_paths),
        ):
            by_path = {str(item["relative_path"]): str(item["sha256"]) for item in manifest["partitions"]}
            for path in paths:
                relative = path.relative_to(root).as_posix()
                if sha256_file(path) != by_path[relative]:
                    raise StrategyResearchSourceError(f"strategy research partition hash changed: {path}")

        source_payload = {
            "contract_version": STRATEGY_RESEARCH_SOURCE_CONTRACT_VERSION,
            "builder_source_fingerprint": build["source_fingerprint"],
            "validation_source_fingerprint": validation["source_fingerprint"],
            "dataset_id": composite_manifest["dataset_id"],
            "dataset_lineage_fingerprint": composite_manifest["dataset_lineage_fingerprint"],
            "row_count": composite_manifest["row_count"],
            "b_manifest_sha256": sha256_file(b_manifest_path),
            "extension_manifest_sha256": sha256_file(extension_manifest_path),
            "composite_manifest_sha256": sha256_file(composite_manifest_path),
            "partition_hashes": [sha256_file(path) for path in parquet_paths],
        }
        return StrategyResearchSource(
            contract_version=STRATEGY_RESEARCH_SOURCE_CONTRACT_VERSION,
            source_fingerprint=_stable_hash(source_payload),
            dataset_id=str(composite_manifest["dataset_id"]),
            dataset_lineage_fingerprint=str(composite_manifest["dataset_lineage_fingerprint"]),
            row_count=int(composite_manifest["row_count"]),
            first_session_date=str(composite_manifest["first_session_date"]),
            last_session_date=str(composite_manifest["last_session_date"]),
            builder_source_fingerprint=str(build["source_fingerprint"]),
            validation_source_fingerprint=str(validation["source_fingerprint"]),
            b_manifest_sha256=sha256_file(b_manifest_path),
            extension_manifest_sha256=sha256_file(extension_manifest_path),
            composite_manifest_sha256=sha256_file(composite_manifest_path),
            parquet_paths=parquet_paths,
        )
