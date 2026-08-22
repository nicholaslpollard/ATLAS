from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity import AlpacaBackfillIdentityBuilder
from packages.data.alpaca_backfill_identity_segments_policy import (
    AlpacaBackfillIdentitySegmentPolicyBuilder,
)
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY
from packages.features.partition_store import sha256_file
from packages.ml.datasets import (
    ML_TRAINING_DATASET_CONTEXT_COLUMNS,
    ML_TRAINING_DATASET_IDENTITY_COLUMNS,
    ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
    ML_TRAINING_DATASET_ORDERING,
    ML_TRAINING_DATASET_OUTCOME_COLUMNS,
    MLTrainingDatasetMaterializer,
)
from packages.ml.feature_policy import (
    ML_FEATURE_POLICY_CONTRACT_VERSION,
    ML_MARKET_REGIME_CONTEXT_FIELDS,
    ML_PRODUCTION_CORE_FEATURE_NAMES,
)
from packages.ml.historical_backfill_long_history_preflight import (
    GATE11_LONG_HISTORY_ORIGIN_DATE,
    GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION,
    GATE11_PRESEAM_END_DATE,
)
from packages.ml.historical_backfill_long_history_preflight_runtime import (
    HistoricalBackfillLongHistoryMLPreflightRuntime,
)
from packages.ml.historical_backfill_structural_authority import (
    AUTH_ELIGIBLE,
    GATE11B_AUTHORITY_ARTIFACT_CONTRACT_VERSION,
    GATE11B_STRUCTURAL_AUTHORITY_CONTRACT_VERSION,
    HistoricalBackfillStructuralAuthorityAudit,
)
from packages.ml.identity_policy import ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION
from packages.ml.label_policy import (
    ML_PREDICTION_LABEL_CLASSES,
    ML_PREDICTION_LABEL_HORIZON_SESSIONS,
    ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
    ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER,
)
from packages.ml.universe_probe import ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS, ML_HISTORY_ORIGIN_DATE
from packages.regimes.split_origin_state_engine import SplitOriginRegimeStateEngine


GATE11C_DATASET_BUILD_CONTRACT_VERSION = (
    "historical-backfill-ml-long-history-datasets-v1-composite-b-plus-preseam-extension"
)
GATE11C_PHYSICAL_DATASET_CONTRACT_VERSION = (
    "historical-backfill-ml-physical-dataset-v1-core33-threeclass-split-origin-context"
)
GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION = (
    "historical-backfill-ml-composite-dataset-v1-parent-b-plus-preseam-extension"
)
GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION = (
    "historical-backfill-ml-dataset-year-v1-lineage-hash-checkpoint"
)
GATE11C_FINGERPRINT_SCOPE = "CONTENT_ONLY_NO_ABSOLUTE_PATHS"
GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT = (
    "fd1ec38495115a72f16d3a1d53bddfca48b7a2972b25ee502054072564e9ad3a"
)
GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT = (
    "3ac4217c34bd0279f67e759d589b58128b31dacf91985decb89af0fe059fbdf9"
)
GATE11C_EXPECTED_B_ROWS = 7_688_332
GATE11C_EXPECTED_EXTENSION_ROWS = 5_709_331
GATE11C_EXPECTED_COMPOSITE_ROWS = GATE11C_EXPECTED_B_ROWS + GATE11C_EXPECTED_EXTENSION_ROWS
GATE11C_EXPECTED_B_CLASSES = {
    "DOWN": 1_594_650,
    "NEUTRAL": 4_402_535,
    "UP": 1_691_147,
}
GATE11C_EXPECTED_EXTENSION_CLASSES = {
    "DOWN": 1_082_217,
    "NEUTRAL": 3_360_480,
    "UP": 1_266_634,
}
GATE11C_EXPECTED_COMPOSITE_CLASSES = {
    label: GATE11C_EXPECTED_B_CLASSES[label] + GATE11C_EXPECTED_EXTENSION_CLASSES[label]
    for label in ML_PREDICTION_LABEL_CLASSES
}
GATE11C_B_ROLE = "B_NEW_FEATURE_LINEAGE_PHASE10_ORIGIN_REBASE"
GATE11C_EXTENSION_ROLE = "C_PRESEAM_STRUCTURALLY_ELIGIBLE_EXTENSION"
GATE11C_COMPOSITE_ROLE = "C_COMPOSITE_B_PLUS_PRESEAM_EXTENSION"
GATE11C_PRODUCTION_MODEL_REPLACEMENT_ALLOWED = False
GATE11C_FINAL_HOLDOUT_USED_FOR_SELECTION = False


class Gate11CLongHistoryDatasetError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _path_is_isolated(candidate: Path, protected: Path) -> bool:
    candidate = candidate.resolve()
    protected = protected.resolve()
    try:
        candidate.relative_to(protected)
        return False
    except ValueError:
        pass
    try:
        protected.relative_to(candidate)
        return False
    except ValueError:
        return candidate != protected


def _parquet_list(paths: list[Path]) -> str:
    if not paths:
        raise ValueError("at least one Parquet path is required")
    return "[" + ",".join(sql_string(path) for path in paths) + "]"


def _dataset_id(prefix: str, end_date: date, lineage: str) -> str:
    digest = str(lineage).strip().lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("dataset lineage must be a SHA-256 digest")
    return f"mlhist-{prefix}-{end_date.isoformat()}-{digest[:16]}"


class HistoricalBackfillLongHistoryDatasetBuilder:
    """Gate 11-C isolated materializer for the lineage-controlled B/C comparison.

    B is physically materialized once using the current 2021-origin Phase-10 identity
    and label semantics on the promoted long-warmup feature lineage. The C physical
    extension contains only accepted pre-seam Gate-11-B rows. C itself is a composite
    manifest binding B + the extension, so the B->C experiment cannot silently rebuild
    or alter the post-seam rows and does not duplicate B on disk.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.materializer = MLTrainingDatasetMaterializer(settings)
        self.preflight = HistoricalBackfillLongHistoryMLPreflightRuntime(settings)
        self.authority_audit = HistoricalBackfillStructuralAuthorityAudit(settings)
        self.segment_policy = AlpacaBackfillIdentitySegmentPolicyBuilder(settings)
        self.identity = AlpacaBackfillIdentityBuilder(settings)
        self.market_engine = SplitOriginRegimeStateEngine(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.long_root = derived / "historical_backfill" / "alpaca" / "ml_long_history" / "v1"
        self.root = self.long_root / "datasets" / "v1"
        self.report_path = self.root / "gate11c_dataset_build_report.json"
        self.standard_training_root = self.materializer.dataset_parent()
        self.model_registry_root = derived / "ml" / "model_registry"
        self.production_ml_write_count = 0

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise Gate11CLongHistoryDatasetError(f"Gate 11-C requires {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Gate11CLongHistoryDatasetError(f"Gate 11-C invalid JSON for {label}: {path}") from exc

    def _standard_dataset_inventory(self) -> list[dict[str, str]]:
        if not self.standard_training_root.is_dir():
            return []
        rows: list[dict[str, str]] = []
        for path in sorted(self.standard_training_root.glob("*/manifest.json")):
            rows.append(
                {
                    "relative_path": path.relative_to(self.standard_training_root).as_posix(),
                    "sha256": sha256_file(path),
                }
            )
        return rows

    def _load_parents(self) -> tuple[dict[str, Any], dict[str, Any], date, Path]:
        gate11a = self._read_json(self.preflight.report_path, "accepted Gate 11-A report")
        gate11b = self._read_json(self.authority_audit.report_path, "accepted Gate 11-B report")
        if gate11a.get("contract_version") != GATE11_LONG_HISTORY_PREFLIGHT_CONTRACT_VERSION:
            raise Gate11CLongHistoryDatasetError("Gate 11-C Gate 11-A contract mismatch")
        if gate11a.get("source_fingerprint") != GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT:
            raise Gate11CLongHistoryDatasetError("Gate 11-C refuses an unaccepted Gate 11-A fingerprint")
        if gate11a.get("pass") is not True:
            raise Gate11CLongHistoryDatasetError("Gate 11-C requires a passing Gate 11-A report")
        if gate11b.get("contract_version") != GATE11B_STRUCTURAL_AUTHORITY_CONTRACT_VERSION:
            raise Gate11CLongHistoryDatasetError("Gate 11-C Gate 11-B contract mismatch")
        if gate11b.get("source_fingerprint") != GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT:
            raise Gate11CLongHistoryDatasetError("Gate 11-C refuses an unaccepted Gate 11-B fingerprint")
        if gate11b.get("pass") is not True:
            raise Gate11CLongHistoryDatasetError("Gate 11-C requires a passing Gate 11-B report")

        end_date = date.fromisoformat(str(gate11a["as_of_date"]))
        if str(gate11b.get("as_of_date")) != end_date.isoformat():
            raise Gate11CLongHistoryDatasetError("Gate 11-A/Gate 11-B evidence horizons differ")
        authority = dict(gate11b["authority"])
        authority_path = self.authority_audit.authority_path
        if not authority_path.is_file():
            raise Gate11CLongHistoryDatasetError("Gate 11-C Gate 11-B authority artifact is missing")
        if sha256_file(authority_path) != str(authority["artifact_sha256"]):
            raise Gate11CLongHistoryDatasetError("Gate 11-C Gate 11-B authority artifact hash changed")
        return gate11a, gate11b, end_date, authority_path

    def _verify_feature_lineages(self, gate11a: dict[str, Any], end_date: date) -> tuple[str, str]:
        expected = dict(gate11a["feature_lineage"])
        expected_b = str(dict(expected["B_rebase"])["fingerprint"])
        expected_c = str(dict(expected["C_full"])["fingerprint"])
        current_b = self.preflight._feature_lineage(ML_HISTORY_ORIGIN_DATE, end_date)  # noqa: SLF001
        current_c = self.preflight._feature_lineage(GATE11_LONG_HISTORY_ORIGIN_DATE, end_date)  # noqa: SLF001
        if current_b.get("fingerprint") != expected_b or int(current_b.get("missing_count", -1)) != 0:
            raise Gate11CLongHistoryDatasetError("Gate 11-C B feature lineage changed after Gate 11-A")
        if current_c.get("fingerprint") != expected_c or int(current_c.get("missing_count", -1)) != 0:
            raise Gate11CLongHistoryDatasetError("Gate 11-C C feature lineage changed after Gate 11-A")
        return expected_b, expected_c

    def _market_history(self, end_date: date, gate11b: dict[str, Any]) -> tuple[Path, str]:
        path = self.market_engine.history_paths(end_date)["market_effective"]
        if not path.is_file():
            raise Gate11CLongHistoryDatasetError(f"Gate 11-C split-origin market history missing: {path}")
        digest = sha256_file(path)
        population = dict(gate11b["population"])
        if digest != str(population["market_history_sha256"]):
            raise Gate11CLongHistoryDatasetError("Gate 11-C market-context history changed after Gate 11-B")
        return path, digest

    @staticmethod
    def _dataset_lineage_payload(
        *,
        role: str,
        end_date: date,
        feature_lineage: str,
        identity_lineage: str,
        split_sha256: str,
        market_context_sha256: str,
        parent_fingerprints: dict[str, str],
    ) -> dict[str, object]:
        return {
            "physical_dataset_contract": GATE11C_PHYSICAL_DATASET_CONTRACT_VERSION,
            "role": role,
            "history_end": end_date.isoformat(),
            "observation_key_contract": ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
            "ordering": list(ML_TRAINING_DATASET_ORDERING),
            "predictor_columns": list(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "identity_columns": list(ML_TRAINING_DATASET_IDENTITY_COLUMNS),
            "outcome_columns": list(ML_TRAINING_DATASET_OUTCOME_COLUMNS),
            "context_columns": list(ML_TRAINING_DATASET_CONTEXT_COLUMNS),
            "feature_policy_contract": ML_FEATURE_POLICY_CONTRACT_VERSION,
            "label_policy_contract": ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
            "feature_contract": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "feature_source_lineage_fingerprint": feature_lineage,
            "identity_source_lineage_fingerprint": identity_lineage,
            "split_evidence_sha256": split_sha256,
            "market_context_sha256": market_context_sha256,
            "parent_fingerprints": dict(sorted(parent_fingerprints.items())),
            "accepted_model_replacement_allowed": GATE11C_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
            "final_holdout_used_for_selection": GATE11C_FINAL_HOLDOUT_USED_FOR_SELECTION,
        }

    def _dataset_root(self, family: str, dataset_id: str) -> Path:
        return self.root / family / dataset_id

    @staticmethod
    def _manifest_path(dataset_root: Path) -> Path:
        return dataset_root / "manifest.json"

    @staticmethod
    def _checkpoint_path(dataset_root: Path, year: int) -> Path:
        return dataset_root / f"year={year:04d}" / "_gate11c_year.json"

    @staticmethod
    def _partition_path(dataset_root: Path, year: int) -> Path:
        return dataset_root / f"year={year:04d}" / "part-000.parquet"

    def _validate_existing_dataset(
        self,
        *,
        dataset_root: Path,
        expected_lineage: str,
        role: str,
    ) -> dict[str, Any] | None:
        manifest_path = self._manifest_path(dataset_root)
        if not manifest_path.is_file():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if manifest.get("contract_version") != GATE11C_PHYSICAL_DATASET_CONTRACT_VERSION:
            return None
        if manifest.get("dataset_lineage_fingerprint") != expected_lineage:
            return None
        if manifest.get("role") != role or manifest.get("immutable") is not True:
            return None
        rows = 0
        keys = 0
        for item in manifest.get("partitions") or []:
            path = dataset_root / str(item["relative_path"])
            if not path.is_file() or sha256_file(path) != str(item["sha256"]):
                return None
            rows += int(item["row_count"])
            keys += int(item["distinct_observation_keys"])
        if rows != int(manifest.get("row_count", -1)) or keys != int(manifest.get("distinct_observation_keys", -1)):
            return None
        if rows != keys:
            return None
        return manifest

    def _reuse_year(
        self,
        *,
        dataset_root: Path,
        year: int,
        dataset_lineage: str,
        role: str,
    ) -> dict[str, Any] | None:
        checkpoint_path = self._checkpoint_path(dataset_root, year)
        partition_path = self._partition_path(dataset_root, year)
        if not checkpoint_path.is_file() or not partition_path.is_file():
            return None
        try:
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        expected_year_lineage = _stable_hash(
            {
                "contract": GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION,
                "dataset_lineage": dataset_lineage,
                "role": role,
                "year": year,
            }
        )
        if checkpoint.get("contract_version") != GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION:
            return None
        if checkpoint.get("year_lineage_fingerprint") != expected_year_lineage:
            return None
        partition = checkpoint.get("partition")
        if not isinstance(partition, dict):
            return None
        if sha256_file(partition_path) != str(partition.get("sha256")):
            return None
        return dict(partition)

    def _write_year(
        self,
        con: Any,
        *,
        dataset_root: Path,
        year: int,
        dataset_lineage: str,
        role: str,
        query: str,
    ) -> tuple[dict[str, Any], bool]:
        reused = self._reuse_year(
            dataset_root=dataset_root,
            year=year,
            dataset_lineage=dataset_lineage,
            role=role,
        )
        if reused is not None:
            return reused, True

        target = self._partition_path(dataset_root, year)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        compression = self.settings.data.parquet.compression.upper()
        row_group_size = int(self.settings.data.parquet.row_group_size)
        con.execute(
            f"COPY ({query}) TO {sql_string(temp)} "
            f"(FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})"
        )
        stats = con.execute(
            f"""
            SELECT
                count(*), count(DISTINCT observation_key), count(DISTINCT symbol),
                min(session_date), max(session_date),
                count(*) FILTER (WHERE prediction_label='DOWN'),
                count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                count(*) FILTER (WHERE prediction_label='UP'),
                count(*) FILTER (WHERE market_regime_available)
            FROM read_parquet({sql_string(temp)})
            """
        ).fetchone()
        if stats is None or int(stats[0]) <= 0:
            temp.unlink(missing_ok=True)
            raise Gate11CLongHistoryDatasetError(f"Gate 11-C {role} year {year} produced no rows")
        if int(stats[0]) != int(stats[1]):
            temp.unlink(missing_ok=True)
            raise Gate11CLongHistoryDatasetError(f"Gate 11-C {role} year {year} has duplicate observation keys")
        promote(temp, target)
        partition = {
            "year": year,
            "relative_path": f"year={year:04d}/part-000.parquet",
            "sha256": sha256_file(target),
            "row_count": int(stats[0]),
            "distinct_observation_keys": int(stats[1]),
            "symbol_count": int(stats[2]),
            "first_session_date": str(stats[3]),
            "last_session_date": str(stats[4]),
            "down_rows": int(stats[5]),
            "neutral_rows": int(stats[6]),
            "up_rows": int(stats[7]),
            "market_context_rows": int(stats[8]),
        }
        checkpoint = {
            "contract_version": GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION,
            "year_lineage_fingerprint": _stable_hash(
                {
                    "contract": GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION,
                    "dataset_lineage": dataset_lineage,
                    "role": role,
                    "year": year,
                }
            ),
            "partition": partition,
        }
        atomic_write_text(
            self._checkpoint_path(dataset_root, year),
            json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
        )
        return partition, False

    def _summarize_partitions(self, dataset_root: Path, partitions: list[dict[str, Any]]) -> dict[str, Any]:
        paths = [dataset_root / str(item["relative_path"]) for item in partitions]
        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                SELECT
                    count(*), count(DISTINCT observation_key), count(DISTINCT symbol),
                    min(session_date), max(session_date),
                    count(*) FILTER (WHERE prediction_label='DOWN'),
                    count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                    count(*) FILTER (WHERE prediction_label='UP'),
                    count(*) FILTER (WHERE market_regime_available)
                FROM read_parquet({_parquet_list(paths)}, union_by_name=true)
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        return {
            "row_count": int(row[0]),
            "distinct_observation_keys": int(row[1]),
            "symbol_count": int(row[2]),
            "first_session_date": str(row[3]),
            "last_session_date": str(row[4]),
            "class_row_counts": {
                "DOWN": int(row[5]),
                "NEUTRAL": int(row[6]),
                "UP": int(row[7]),
            },
            "market_context_rows": int(row[8]),
        }

    def _build_physical_dataset(
        self,
        con: Any,
        *,
        family: str,
        role: str,
        dataset_id: str,
        dataset_lineage: str,
        years: list[int],
        query_for_year: Callable[[int], str],
        lineage_payload: dict[str, object],
        expected_rows: int,
        expected_classes: dict[str, int],
    ) -> tuple[dict[str, Any], bool, list[int], list[int]]:
        dataset_root = self._dataset_root(family, dataset_id)
        if not _path_is_isolated(dataset_root, self.standard_training_root):
            raise Gate11CLongHistoryDatasetError("Gate 11-C dataset root overlaps standard ML training namespace")
        if not _path_is_isolated(dataset_root, self.model_registry_root):
            raise Gate11CLongHistoryDatasetError("Gate 11-C dataset root overlaps model registry")

        existing = self._validate_existing_dataset(
            dataset_root=dataset_root,
            expected_lineage=dataset_lineage,
            role=role,
        )
        if existing is not None:
            if int(existing["row_count"]) != expected_rows or dict(existing["class_row_counts"]) != expected_classes:
                raise Gate11CLongHistoryDatasetError(f"Gate 11-C existing {role} totals differ from accepted evidence")
            return existing, True, [], years

        dataset_root.mkdir(parents=True, exist_ok=True)
        unexpected = {
            path.name
            for path in dataset_root.glob("year=*")
            if path.is_dir() and int(path.name.split("=", 1)[1]) not in set(years)
        }
        if unexpected:
            raise Gate11CLongHistoryDatasetError(
                f"Gate 11-C {role} root contains unexpected year directories: {sorted(unexpected)}"
            )

        partitions: list[dict[str, Any]] = []
        rebuilt_years: list[int] = []
        reused_years: list[int] = []
        for year in years:
            partition, reused = self._write_year(
                con,
                dataset_root=dataset_root,
                year=year,
                dataset_lineage=dataset_lineage,
                role=role,
                query=query_for_year(year),
            )
            partitions.append(partition)
            (reused_years if reused else rebuilt_years).append(year)

        summary = self._summarize_partitions(dataset_root, partitions)
        if int(summary["row_count"]) != int(summary["distinct_observation_keys"]):
            raise Gate11CLongHistoryDatasetError(f"Gate 11-C {role} contains duplicate observation keys")
        if int(summary["row_count"]) != expected_rows:
            raise Gate11CLongHistoryDatasetError(
                f"Gate 11-C {role} row count changed: expected={expected_rows:,} actual={int(summary['row_count']):,}"
            )
        if dict(summary["class_row_counts"]) != expected_classes:
            raise Gate11CLongHistoryDatasetError(
                f"Gate 11-C {role} class counts changed: expected={expected_classes} actual={summary['class_row_counts']}"
            )

        manifest = {
            "schema_version": 1,
            "contract_version": GATE11C_PHYSICAL_DATASET_CONTRACT_VERSION,
            "role": role,
            "dataset_id": dataset_id,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "immutable": True,
            "partitioning": "observation_year",
            "ordering": list(ML_TRAINING_DATASET_ORDERING),
            "observation_key_contract": ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
            **summary,
            "market_context_fraction": (
                0.0 if int(summary["row_count"]) <= 0
                else int(summary["market_context_rows"]) / int(summary["row_count"])
            ),
            "predictor_count": len(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "predictor_columns": list(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "identity_columns": list(ML_TRAINING_DATASET_IDENTITY_COLUMNS),
            "outcome_columns": list(ML_TRAINING_DATASET_OUTCOME_COLUMNS),
            "context_columns": list(ML_TRAINING_DATASET_CONTEXT_COLUMNS),
            "feature_policy_contract": ML_FEATURE_POLICY_CONTRACT_VERSION,
            "label_policy_contract": ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
            "feature_contract": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "dataset_lineage_fingerprint": dataset_lineage,
            "lineage_payload": lineage_payload,
            "partitions": partitions,
            "production_model_replacement_allowed": False,
            "final_holdout_used_for_selection": False,
        }
        atomic_write_text(
            self._manifest_path(dataset_root),
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )
        return manifest, False, rebuilt_years, reused_years

    def _prepare_market_context(self, con: Any, market_history: Path) -> None:
        fields = ", ".join(
            f"CAST({field} AS VARCHAR) AS {field}" for field in ML_MARKET_REGIME_CONTEXT_FIELDS
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11c_market_context AS
            SELECT CAST(trading_date AS DATE) AS trading_date, {fields}
            FROM read_parquet({sql_string(market_history)})
            """
        )
        duplicates = int(
            con.execute(
                """
                SELECT count(*) FROM (
                    SELECT trading_date FROM gate11c_market_context
                    GROUP BY trading_date HAVING count(*) > 1
                )
                """
            ).fetchone()[0]
        )
        if duplicates:
            raise Gate11CLongHistoryDatasetError("Gate 11-C market context contains duplicate dates")

    def _partition_query(self, *, source_table: str, year: int) -> str:
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        predictors = ",\n                ".join(
            f"CAST(f.{name} AS DOUBLE) AS {name}" for name in ML_PRODUCTION_CORE_FEATURE_NAMES
        )
        context = ",\n                ".join(
            f"CAST(m.{field} AS VARCHAR) AS market_regime_{field}"
            for field in ML_MARKET_REGIME_CONTEXT_FIELDS
        )
        return f"""
            WITH features AS (
                SELECT symbol, CAST(timestamp_utc AS DATE) AS session_date,
                       {', '.join(ML_PRODUCTION_CORE_FEATURE_NAMES)}
                FROM read_parquet(
                    {sql_string(feature_glob)}, hive_partitioning=true, union_by_name=true
                )
                WHERE year(CAST(timestamp_utc AS DATE)) = {year}
            )
            SELECT
                concat(l.instrument_id, '|', l.symbol, '|', CAST(l.session_date AS VARCHAR))
                    AS observation_key,
                l.session_date,
                l.symbol,
                l.instrument_id,
                l.observation_close,
                {predictors},
                l.future_date,
                l.future_close,
                l.forward_return,
                l.label_threshold,
                l.prediction_label,
                (m.trading_date IS NOT NULL) AS market_regime_available,
                {context}
            FROM {source_table} l
            INNER JOIN features f
              ON f.symbol=l.symbol
             AND f.session_date=l.session_date
            LEFT JOIN gate11c_market_context m
              ON m.trading_date=l.session_date
            WHERE year(l.session_date)={year}
            ORDER BY l.session_date, l.symbol, l.instrument_id
        """

    def _prepare_extension_labeled(
        self,
        con: Any,
        *,
        authority_path: Path,
        end_date: date,
    ) -> dict[str, Any]:
        segment_path = self.segment_policy.base.segment_path
        event_path = self.identity.event_ledger_path
        if not segment_path.is_file() or not event_path.is_file():
            raise Gate11CLongHistoryDatasetError("Gate 11-C pre-seam identity/split evidence is missing")
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        complete = " AND ".join(
            f"f.{name} IS NOT NULL AND isfinite(CAST(f.{name} AS DOUBLE))"
            for name in ML_PRODUCTION_CORE_FEATURE_NAMES
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11c_daily AS
            SELECT symbol, CAST(session_date AS DATE) AS session_date,
                   CAST(close AS DOUBLE) AS close, CAST(volume AS DOUBLE) AS volume,
                   CAST(provider AS VARCHAR) AS provider
            FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true)
            WHERE CAST(session_date AS DATE)
                BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}' AND DATE '{end_date}'
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11c_segments AS
            SELECT CAST(identity_chain_id AS VARCHAR) AS identity_chain_id,
                   CAST(symbol AS VARCHAR) AS symbol,
                   CAST(first_date AS DATE) AS first_date,
                   CAST(last_date AS DATE) AS last_date,
                   coalesce(CAST(identity_ambiguous AS BOOLEAN), FALSE) AS identity_ambiguous
            FROM read_parquet({sql_string(segment_path)})
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11c_authority AS
            SELECT CAST(identity_chain_id AS VARCHAR) AS identity_chain_id,
                   CAST(historical_instrument_id AS VARCHAR) AS historical_instrument_id,
                   CAST(authority_status AS VARCHAR) AS authority_status,
                   CAST(structural_eligible AS BOOLEAN) AS structural_eligible
            FROM read_parquet({sql_string(authority_path)})
            """
        )
        con.execute(
            f"""
            CREATE TEMP TABLE gate11c_extension_candidates AS
            SELECT b.symbol, b.session_date, b.close, b.volume,
                   s.identity_chain_id, CAST(f.natr_14 AS DOUBLE) AS natr_14
            FROM gate11c_daily b
            INNER JOIN gate11c_segments s
              ON s.symbol=b.symbol
             AND b.session_date BETWEEN s.first_date AND s.last_date
            INNER JOIN read_parquet(
                {sql_string(feature_glob)}, hive_partitioning=true, union_by_name=true
            ) f
              ON f.symbol=b.symbol
             AND CAST(f.timestamp_utc AS DATE)=b.session_date
            WHERE b.session_date BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                                     AND DATE '{GATE11_PRESEAM_END_DATE}'
              AND b.provider='alpaca'
              AND NOT s.identity_ambiguous
              AND ({complete})
              AND b.close*b.volume >= {float(ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS):.17g}
              AND f.natr_14 IS NOT NULL
              AND isfinite(CAST(f.natr_14 AS DOUBLE))
              AND CAST(f.natr_14 AS DOUBLE) > 0
            """
        )
        con.execute(
            """
            CREATE TEMP TABLE gate11c_sessions AS
            SELECT session_date, row_number() OVER (ORDER BY session_date) AS session_seq
            FROM (SELECT DISTINCT session_date FROM gate11c_daily)
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW gate11c_splits AS
            SELECT source_symbol AS symbol, try_cast(event_date AS DATE) AS event_date
            FROM read_parquet({sql_string(event_path)})
            WHERE event_type IN ('forward_splits','reverse_splits')
              AND source_symbol IS NOT NULL
              AND try_cast(event_date AS DATE) IS NOT NULL
              AND try_cast(event_date AS DATE) BETWEEN DATE '{GATE11_LONG_HISTORY_ORIGIN_DATE}'
                                                   AND DATE '{GATE11_PRESEAM_END_DATE}'
            """
        )
        horizon = int(ML_PREDICTION_LABEL_HORIZON_SESSIONS)
        con.execute(
            f"""
            CREATE TEMP TABLE gate11c_extension_outcomes AS
            SELECT c.*, fs.session_date AS future_date, fb.close AS future_close,
                   EXISTS (
                       SELECT 1 FROM gate11c_splits sp
                       WHERE sp.symbol=c.symbol
                         AND sp.event_date > c.session_date
                         AND sp.event_date <= fs.session_date
                   ) AS split_crossing
            FROM gate11c_extension_candidates c
            INNER JOIN gate11c_sessions s ON s.session_date=c.session_date
            LEFT JOIN gate11c_sessions fs ON fs.session_seq=s.session_seq+{horizon}
            LEFT JOIN gate11c_daily fb
              ON fb.symbol=c.symbol
             AND fb.session_date=fs.session_date
             AND fb.provider='alpaca'
            """
        )
        threshold_scale = float(ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER) * math.sqrt(float(horizon))
        con.execute(
            f"""
            CREATE TEMP TABLE gate11c_extension_labeled AS
            SELECT
                o.symbol,
                o.session_date,
                a.historical_instrument_id AS instrument_id,
                o.close AS observation_close,
                o.future_date,
                o.future_close,
                (o.future_close/o.close)-1.0 AS forward_return,
                o.natr_14*{threshold_scale:.17g} AS label_threshold,
                CASE
                    WHEN (o.future_close/o.close)-1.0 >= o.natr_14*{threshold_scale:.17g}
                        THEN 'UP'
                    WHEN (o.future_close/o.close)-1.0 <= -(o.natr_14*{threshold_scale:.17g})
                        THEN 'DOWN'
                    ELSE 'NEUTRAL'
                END AS prediction_label
            FROM gate11c_extension_outcomes o
            INNER JOIN gate11c_authority a USING (identity_chain_id)
            WHERE o.future_date <= DATE '{GATE11_PRESEAM_END_DATE}'
              AND o.future_close IS NOT NULL
              AND o.future_close > 0
              AND NOT o.split_crossing
              AND a.structural_eligible
              AND a.authority_status='{AUTH_ELIGIBLE}'
            """
        )
        row = con.execute(
            """
            SELECT count(*), count(DISTINCT (instrument_id, symbol, session_date)),
                   count(DISTINCT symbol), min(session_date), max(session_date),
                   count(*) FILTER (WHERE prediction_label='DOWN'),
                   count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                   count(*) FILTER (WHERE prediction_label='UP')
            FROM gate11c_extension_labeled
            """
        ).fetchone()
        assert row is not None
        return {
            "rows": int(row[0]),
            "keys": int(row[1]),
            "symbols": int(row[2]),
            "first_session": str(row[3]),
            "last_session": str(row[4]),
            "class_rows": {"DOWN": int(row[5]), "NEUTRAL": int(row[6]), "UP": int(row[7])},
            "segment_sha256": sha256_file(segment_path),
            "event_sha256": sha256_file(event_path),
        }

    def _build_composite(
        self,
        *,
        end_date: date,
        b_root: Path,
        b_manifest: dict[str, Any],
        extension_root: Path,
        extension_manifest: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        b_lineage = str(b_manifest["dataset_lineage_fingerprint"])
        extension_lineage = str(extension_manifest["dataset_lineage_fingerprint"])
        lineage_payload = {
            "contract": GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION,
            "role": GATE11C_COMPOSITE_ROLE,
            "B_dataset_lineage": b_lineage,
            "extension_dataset_lineage": extension_lineage,
            "predictor_columns": list(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "observation_key_contract": ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
            "postseam_rows_are_exactly_parent_B": True,
            "accepted_model_replacement_allowed": False,
            "final_holdout_used_for_selection": False,
        }
        lineage = _stable_hash(lineage_payload)
        dataset_id = _dataset_id("c", end_date, lineage)
        root = self._dataset_root("C", dataset_id)
        manifest_path = self._manifest_path(root)
        if manifest_path.is_file():
            existing = self._read_json(manifest_path, "existing Gate 11-C composite manifest")
            if (
                existing.get("contract_version") == GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION
                and existing.get("dataset_lineage_fingerprint") == lineage
                and existing.get("B_dataset_lineage") == b_lineage
                and existing.get("extension_dataset_lineage") == extension_lineage
            ):
                return existing, True

        if str(extension_manifest["last_session_date"]) >= str(b_manifest["first_session_date"]):
            raise Gate11CLongHistoryDatasetError("Gate 11-C extension overlaps B observation dates")

        b_paths = [b_root / str(item["relative_path"]) for item in b_manifest["partitions"]]
        x_paths = [extension_root / str(item["relative_path"]) for item in extension_manifest["partitions"]]
        con = connect_utc(":memory:")
        try:
            union_source = _parquet_list(b_paths + x_paths)
            row = con.execute(
                f"""
                SELECT count(*), count(DISTINCT observation_key), count(DISTINCT symbol),
                       min(session_date), max(session_date),
                       count(*) FILTER (WHERE prediction_label='DOWN'),
                       count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                       count(*) FILTER (WHERE prediction_label='UP'),
                       count(*) FILTER (WHERE market_regime_available)
                FROM read_parquet({union_source}, union_by_name=true)
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        if int(row[0]) != int(row[1]):
            raise Gate11CLongHistoryDatasetError("Gate 11-C composite contains duplicate observation keys")
        class_counts = {"DOWN": int(row[5]), "NEUTRAL": int(row[6]), "UP": int(row[7])}
        if int(row[0]) != GATE11C_EXPECTED_COMPOSITE_ROWS or class_counts != GATE11C_EXPECTED_COMPOSITE_CLASSES:
            raise Gate11CLongHistoryDatasetError("Gate 11-C composite totals differ from accepted B + extension evidence")

        root.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": 1,
            "contract_version": GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION,
            "role": GATE11C_COMPOSITE_ROLE,
            "dataset_id": dataset_id,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "immutable": True,
            "dataset_lineage_fingerprint": lineage,
            "lineage_payload": lineage_payload,
            "row_count": int(row[0]),
            "distinct_observation_keys": int(row[1]),
            "symbol_count": int(row[2]),
            "first_session_date": str(row[3]),
            "last_session_date": str(row[4]),
            "class_row_counts": class_counts,
            "market_context_rows": int(row[8]),
            "market_context_fraction": 0.0 if int(row[0]) <= 0 else int(row[8]) / int(row[0]),
            "predictor_count": len(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "predictor_columns": list(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "observation_key_contract": ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
            "B_dataset_id": str(b_manifest["dataset_id"]),
            "B_dataset_lineage": b_lineage,
            "B_manifest_sha256": sha256_file(self._manifest_path(b_root)),
            "B_manifest_relative_path": self._manifest_path(b_root).relative_to(self.long_root).as_posix(),
            "extension_dataset_id": str(extension_manifest["dataset_id"]),
            "extension_dataset_lineage": extension_lineage,
            "extension_manifest_sha256": sha256_file(self._manifest_path(extension_root)),
            "extension_manifest_relative_path": self._manifest_path(extension_root).relative_to(self.long_root).as_posix(),
            "postseam_rows_are_exactly_parent_B": True,
            "physical_B_rows": int(b_manifest["row_count"]),
            "physical_extension_rows": int(extension_manifest["row_count"]),
            "physical_C_copy_of_B_rows": 0,
            "production_model_replacement_allowed": False,
            "final_holdout_used_for_selection": False,
        }
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return manifest, False

    def run(self) -> dict[str, object]:
        gate11a, gate11b, end_date, authority_path = self._load_parents()
        feature_lineage_b, feature_lineage_c = self._verify_feature_lineages(gate11a, end_date)
        market_history, market_context_sha = self._market_history(end_date, gate11b)
        accepted_before = self.preflight._accepted_phase10()  # noqa: SLF001
        standard_inventory_before = self._standard_dataset_inventory()

        b_evidence = dict(gate11a["B_rebase_evidence"])
        if int(b_evidence["rows"]) != GATE11C_EXPECTED_B_ROWS:
            raise Gate11CLongHistoryDatasetError("Gate 11-C accepted Gate 11-A B row count changed")
        if dict(b_evidence["class_rows"]) != GATE11C_EXPECTED_B_CLASSES:
            raise Gate11CLongHistoryDatasetError("Gate 11-C accepted Gate 11-A B class counts changed")
        gate11b_population = dict(gate11b["population"])
        if int(gate11b_population["eligible_rows"]) != GATE11C_EXPECTED_EXTENSION_ROWS:
            raise Gate11CLongHistoryDatasetError("Gate 11-C accepted Gate 11-B eligible row count changed")
        if dict(gate11b_population["class_rows"]) != GATE11C_EXPECTED_EXTENSION_CLASSES:
            raise Gate11CLongHistoryDatasetError("Gate 11-C accepted Gate 11-B class counts changed")

        splits, split_path = self.materializer.family._load_split_evidence(end_date)  # noqa: SLF001
        split_sha = sha256_file(split_path)
        if split_sha != str(b_evidence["split_evidence_sha256"]):
            raise Gate11CLongHistoryDatasetError("Gate 11-C Massive split evidence changed after Gate 11-A")
        identity_lineage_b = self.materializer._identity_source_lineage(end_date)  # noqa: SLF001

        b_lineage_payload = self._dataset_lineage_payload(
            role=GATE11C_B_ROLE,
            end_date=end_date,
            feature_lineage=feature_lineage_b,
            identity_lineage=identity_lineage_b,
            split_sha256=split_sha,
            market_context_sha256=market_context_sha,
            parent_fingerprints={"gate11a": GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT},
        )
        b_lineage = _stable_hash(b_lineage_payload)
        b_id = _dataset_id("b", end_date, b_lineage)

        b_root = self._dataset_root("B", b_id)
        existing_b = self._validate_existing_dataset(
            dataset_root=b_root,
            expected_lineage=b_lineage,
            role=GATE11C_B_ROLE,
        )
        if existing_b is None:
            con = connect_utc(":memory:")
            try:
                self.materializer.base._prepare_label_views(con, end_date, splits)  # noqa: SLF001
                self.materializer._prepare_labeled_candidates(con)  # noqa: SLF001
                self._prepare_market_context(con, market_history)
                b_summary = con.execute(
                    """
                    SELECT count(*), count(DISTINCT (instrument_id, symbol, session_date)),
                           count(DISTINCT symbol), min(session_date), max(session_date),
                           count(*) FILTER (WHERE prediction_label='DOWN'),
                           count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                           count(*) FILTER (WHERE prediction_label='UP')
                    FROM ml_gate6_labeled_candidates
                    """
                ).fetchone()
                assert b_summary is not None
                if int(b_summary[0]) != GATE11C_EXPECTED_B_ROWS or int(b_summary[0]) != int(b_summary[1]):
                    raise Gate11CLongHistoryDatasetError("Gate 11-C B reconstruction differs from Gate 11-A")
                if {
                    "DOWN": int(b_summary[5]),
                    "NEUTRAL": int(b_summary[6]),
                    "UP": int(b_summary[7]),
                } != GATE11C_EXPECTED_B_CLASSES:
                    raise Gate11CLongHistoryDatasetError("Gate 11-C B reconstructed class counts differ")
                b_years = [
                    int(row[0])
                    for row in con.execute(
                        "SELECT DISTINCT year(session_date) FROM ml_gate6_labeled_candidates ORDER BY 1"
                    ).fetchall()
                ]
                b_manifest, b_reused, b_rebuilt_years, b_reused_years = self._build_physical_dataset(
                    con,
                    family="B",
                    role=GATE11C_B_ROLE,
                    dataset_id=b_id,
                    dataset_lineage=b_lineage,
                    years=b_years,
                    query_for_year=lambda year: self._partition_query(
                        source_table="ml_gate6_labeled_candidates", year=year
                    ),
                    lineage_payload=b_lineage_payload,
                    expected_rows=GATE11C_EXPECTED_B_ROWS,
                    expected_classes=GATE11C_EXPECTED_B_CLASSES,
                )
            finally:
                con.close()
        else:
            b_manifest = existing_b
            b_reused = True
            b_rebuilt_years = []
            b_reused_years = [int(item["year"]) for item in b_manifest["partitions"]]

        segment_sha = sha256_file(self.segment_policy.base.segment_path)
        event_sha = sha256_file(self.identity.event_ledger_path)
        authority_sha = sha256_file(authority_path)
        extension_identity_lineage = _stable_hash(
            {
                "gate11b_source_fingerprint": GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
                "authority_artifact_contract": GATE11B_AUTHORITY_ARTIFACT_CONTRACT_VERSION,
                "authority_sha256": authority_sha,
                "segment_sha256": segment_sha,
                "corporate_action_event_sha256": event_sha,
                "historical_instrument_id_contract": "alpaca-gate4-chain:<identity_chain_id>",
            }
        )
        extension_lineage_payload = self._dataset_lineage_payload(
            role=GATE11C_EXTENSION_ROLE,
            end_date=end_date,
            feature_lineage=feature_lineage_c,
            identity_lineage=extension_identity_lineage,
            split_sha256=event_sha,
            market_context_sha256=market_context_sha,
            parent_fingerprints={
                "gate11a": GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
                "gate11b": GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
            },
        )
        extension_lineage = _stable_hash(extension_lineage_payload)
        extension_id = _dataset_id("cx", end_date, extension_lineage)
        extension_root = self._dataset_root("C_extension", extension_id)
        existing_extension = self._validate_existing_dataset(
            dataset_root=extension_root,
            expected_lineage=extension_lineage,
            role=GATE11C_EXTENSION_ROLE,
        )
        if existing_extension is None:
            con = connect_utc(":memory:")
            try:
                self._prepare_market_context(con, market_history)
                extension_summary = self._prepare_extension_labeled(
                    con,
                    authority_path=authority_path,
                    end_date=end_date,
                )
                if int(extension_summary["rows"]) != GATE11C_EXPECTED_EXTENSION_ROWS:
                    raise Gate11CLongHistoryDatasetError("Gate 11-C extension row count differs from Gate 11-B")
                if int(extension_summary["rows"]) != int(extension_summary["keys"]):
                    raise Gate11CLongHistoryDatasetError("Gate 11-C extension has duplicate source keys")
                if dict(extension_summary["class_rows"]) != GATE11C_EXPECTED_EXTENSION_CLASSES:
                    raise Gate11CLongHistoryDatasetError("Gate 11-C extension class counts differ from Gate 11-B")
                if extension_summary["segment_sha256"] != segment_sha or extension_summary["event_sha256"] != event_sha:
                    raise Gate11CLongHistoryDatasetError("Gate 11-C extension identity/split evidence changed during build")
                extension_years = [
                    int(row[0])
                    for row in con.execute(
                        "SELECT DISTINCT year(session_date) FROM gate11c_extension_labeled ORDER BY 1"
                    ).fetchall()
                ]
                extension_manifest, extension_reused, extension_rebuilt_years, extension_reused_years = (
                    self._build_physical_dataset(
                        con,
                        family="C_extension",
                        role=GATE11C_EXTENSION_ROLE,
                        dataset_id=extension_id,
                        dataset_lineage=extension_lineage,
                        years=extension_years,
                        query_for_year=lambda year: self._partition_query(
                            source_table="gate11c_extension_labeled", year=year
                        ),
                        lineage_payload=extension_lineage_payload,
                        expected_rows=GATE11C_EXPECTED_EXTENSION_ROWS,
                        expected_classes=GATE11C_EXPECTED_EXTENSION_CLASSES,
                    )
                )
            finally:
                con.close()
        else:
            extension_manifest = existing_extension
            extension_reused = True
            extension_rebuilt_years = []
            extension_reused_years = [int(item["year"]) for item in extension_manifest["partitions"]]

        composite_manifest, composite_reused = self._build_composite(
            end_date=end_date,
            b_root=b_root,
            b_manifest=b_manifest,
            extension_root=extension_root,
            extension_manifest=extension_manifest,
        )

        accepted_after = self.preflight._accepted_phase10()  # noqa: SLF001
        standard_inventory_after = self._standard_dataset_inventory()
        accepted_A_unchanged = (
            accepted_before["dataset_manifest_sha256"] == accepted_after["dataset_manifest_sha256"]
            and accepted_before["dataset_partition_hash_failures"] == 0
            and accepted_after["dataset_partition_hash_failures"] == 0
        )
        accepted_model_unchanged = (
            accepted_before["final_report_sha256"] == accepted_after["final_report_sha256"]
            and accepted_before["production_manifest_sha256"] == accepted_after["production_manifest_sha256"]
            and accepted_after["model_hash_exact"] is True
        )
        standard_inventory_unchanged = standard_inventory_before == standard_inventory_after

        checks = {
            "build_contract": True,
            "gate11a_fingerprint_accepted": gate11a.get("source_fingerprint")
            == GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
            "gate11b_fingerprint_accepted": gate11b.get("source_fingerprint")
            == GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
            "B_rows_exact": int(b_manifest["row_count"]) == GATE11C_EXPECTED_B_ROWS,
            "B_keys_unique": int(b_manifest["row_count"]) == int(b_manifest["distinct_observation_keys"]),
            "B_classes_exact": dict(b_manifest["class_row_counts"]) == GATE11C_EXPECTED_B_CLASSES,
            "extension_rows_exact": int(extension_manifest["row_count"]) == GATE11C_EXPECTED_EXTENSION_ROWS,
            "extension_keys_unique": int(extension_manifest["row_count"])
            == int(extension_manifest["distinct_observation_keys"]),
            "extension_classes_exact": dict(extension_manifest["class_row_counts"])
            == GATE11C_EXPECTED_EXTENSION_CLASSES,
            "composite_rows_exact": int(composite_manifest["row_count"])
            == GATE11C_EXPECTED_COMPOSITE_ROWS,
            "composite_keys_unique": int(composite_manifest["row_count"])
            == int(composite_manifest["distinct_observation_keys"]),
            "composite_classes_exact": dict(composite_manifest["class_row_counts"])
            == GATE11C_EXPECTED_COMPOSITE_CLASSES,
            "composite_postseam_is_exact_parent_B": composite_manifest.get("postseam_rows_are_exactly_parent_B") is True,
            "composite_does_not_copy_B": int(composite_manifest["physical_C_copy_of_B_rows"]) == 0,
            "accepted_A_dataset_unchanged": accepted_A_unchanged,
            "accepted_phase10_model_unchanged": accepted_model_unchanged,
            "standard_training_dataset_namespace_unchanged": standard_inventory_unchanged,
            "accepted_model_replacement_forbidden": GATE11C_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False,
            "final_holdout_not_used_for_selection": GATE11C_FINAL_HOLDOUT_USED_FOR_SELECTION is False,
            "production_ml_writes_zero": self.production_ml_write_count == 0,
        }

        fingerprint_payload = {
            "contract_version": GATE11C_DATASET_BUILD_CONTRACT_VERSION,
            "fingerprint_scope": GATE11C_FINGERPRINT_SCOPE,
            "gate11a_source_fingerprint": GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
            "gate11b_source_fingerprint": GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
            "B": {
                "dataset_id": b_manifest["dataset_id"],
                "dataset_lineage": b_manifest["dataset_lineage_fingerprint"],
                "row_count": b_manifest["row_count"],
                "class_row_counts": b_manifest["class_row_counts"],
                "partition_hashes": [item["sha256"] for item in b_manifest["partitions"]],
            },
            "extension": {
                "dataset_id": extension_manifest["dataset_id"],
                "dataset_lineage": extension_manifest["dataset_lineage_fingerprint"],
                "row_count": extension_manifest["row_count"],
                "class_row_counts": extension_manifest["class_row_counts"],
                "partition_hashes": [item["sha256"] for item in extension_manifest["partitions"]],
            },
            "C": {
                "dataset_id": composite_manifest["dataset_id"],
                "dataset_lineage": composite_manifest["dataset_lineage_fingerprint"],
                "row_count": composite_manifest["row_count"],
                "class_row_counts": composite_manifest["class_row_counts"],
            },
            "market_context_sha256": market_context_sha,
            "accepted_A_manifest_sha256": accepted_after["dataset_manifest_sha256"],
            "accepted_model_final_report_sha256": accepted_after["final_report_sha256"],
        }
        source_fingerprint = _stable_hash(fingerprint_payload)
        report: dict[str, object] = {
            "contract_version": GATE11C_DATASET_BUILD_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": source_fingerprint,
            "fingerprint_scope": GATE11C_FINGERPRINT_SCOPE,
            "as_of_date": end_date.isoformat(),
            "gate11a_source_fingerprint": GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
            "gate11b_source_fingerprint": GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
            "B": {
                "dataset_id": b_manifest["dataset_id"],
                "dataset_lineage_fingerprint": b_manifest["dataset_lineage_fingerprint"],
                "row_count": b_manifest["row_count"],
                "distinct_observation_keys": b_manifest["distinct_observation_keys"],
                "symbol_count": b_manifest["symbol_count"],
                "first_session_date": b_manifest["first_session_date"],
                "last_session_date": b_manifest["last_session_date"],
                "class_row_counts": b_manifest["class_row_counts"],
                "market_context_rows": b_manifest["market_context_rows"],
                "market_context_fraction": b_manifest["market_context_fraction"],
                "manifest_sha256": sha256_file(self._manifest_path(b_root)),
                "manifest_path": str(self._manifest_path(b_root).resolve()),
                "fully_reused": b_reused,
                "rebuilt_years": b_rebuilt_years,
                "reused_years": b_reused_years,
            },
            "C_extension": {
                "dataset_id": extension_manifest["dataset_id"],
                "dataset_lineage_fingerprint": extension_manifest["dataset_lineage_fingerprint"],
                "row_count": extension_manifest["row_count"],
                "distinct_observation_keys": extension_manifest["distinct_observation_keys"],
                "symbol_count": extension_manifest["symbol_count"],
                "first_session_date": extension_manifest["first_session_date"],
                "last_session_date": extension_manifest["last_session_date"],
                "class_row_counts": extension_manifest["class_row_counts"],
                "market_context_rows": extension_manifest["market_context_rows"],
                "market_context_fraction": extension_manifest["market_context_fraction"],
                "manifest_sha256": sha256_file(self._manifest_path(extension_root)),
                "manifest_path": str(self._manifest_path(extension_root).resolve()),
                "fully_reused": extension_reused,
                "rebuilt_years": extension_rebuilt_years,
                "reused_years": extension_reused_years,
            },
            "C_composite": {
                "dataset_id": composite_manifest["dataset_id"],
                "dataset_lineage_fingerprint": composite_manifest["dataset_lineage_fingerprint"],
                "row_count": composite_manifest["row_count"],
                "distinct_observation_keys": composite_manifest["distinct_observation_keys"],
                "symbol_count": composite_manifest["symbol_count"],
                "first_session_date": composite_manifest["first_session_date"],
                "last_session_date": composite_manifest["last_session_date"],
                "class_row_counts": composite_manifest["class_row_counts"],
                "market_context_rows": composite_manifest["market_context_rows"],
                "market_context_fraction": composite_manifest["market_context_fraction"],
                "B_rows": composite_manifest["physical_B_rows"],
                "extension_rows": composite_manifest["physical_extension_rows"],
                "duplicated_B_rows": composite_manifest["physical_C_copy_of_B_rows"],
                "manifest_sha256": sha256_file(
                    self._manifest_path(self._dataset_root("C", str(composite_manifest["dataset_id"])))
                ),
                "manifest_path": str(
                    self._manifest_path(self._dataset_root("C", str(composite_manifest["dataset_id"]))).resolve()
                ),
                "reused": composite_reused,
            },
            "market_context_sha256": market_context_sha,
            "accepted_phase10": {
                "dataset_id": accepted_after["dataset_id"],
                "dataset_manifest_sha256": accepted_after["dataset_manifest_sha256"],
                "model_id": accepted_after["model_id"],
                "model_hash_exact": accepted_after["model_hash_exact"],
                "final_report_sha256": accepted_after["final_report_sha256"],
                "production_manifest_sha256": accepted_after["production_manifest_sha256"],
            },
            "checks": checks,
            "production_ml_writes": self.production_ml_write_count,
            "pass": all(bool(value) for value in checks.values()),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
