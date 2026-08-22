from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.partition_store import sha256_file
from packages.ml.datasets import (
    ML_TRAINING_DATASET_CONTEXT_COLUMNS,
    ML_TRAINING_DATASET_IDENTITY_COLUMNS,
    ML_TRAINING_DATASET_OUTCOME_COLUMNS,
)
from packages.ml.feature_policy import ML_MARKET_REGIME_CONTEXT_FIELDS, ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.historical_backfill_long_history_datasets import (
    GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
    GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
    GATE11C_B_ROLE,
    GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION,
    GATE11C_COMPOSITE_ROLE,
    GATE11C_DATASET_BUILD_CONTRACT_VERSION,
    GATE11C_EXPECTED_B_CLASSES,
    GATE11C_EXPECTED_B_ROWS,
    GATE11C_EXPECTED_COMPOSITE_CLASSES,
    GATE11C_EXPECTED_COMPOSITE_ROWS,
    GATE11C_EXPECTED_EXTENSION_CLASSES,
    GATE11C_EXPECTED_EXTENSION_ROWS,
    GATE11C_EXTENSION_ROLE,
    GATE11C_FINAL_HOLDOUT_USED_FOR_SELECTION,
    GATE11C_FINGERPRINT_SCOPE,
    GATE11C_PHYSICAL_DATASET_CONTRACT_VERSION,
    GATE11C_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
    GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION,
    HistoricalBackfillLongHistoryDatasetBuilder,
)
from packages.ml.historical_backfill_long_history_preflight import GATE11_PRESEAM_END_DATE
from packages.ml.label_policy import (
    ML_PREDICTION_LABEL_HORIZON_SESSIONS,
    ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER,
)


GATE11C_DATASET_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-ml-long-history-dataset-validation-v1-independent-disk-source-recompute"
)
GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT = (
    "e4aa283060d904995a73dc3c6dc06f9b59a383fd5d5fdf64484a603e357c4fa6"
)
GATE11C_EXPECTED_A_ROWS = 6_553_856
GATE11C_EXPECTED_A_TO_B_OVERLAP = 6_553_856
GATE11C_EXPECTED_B_ONLY_ROWS = 1_134_476
GATE11C_PRODUCTION_ML_WRITES = 0


class Gate11CDatasetValidationError(RuntimeError):
    pass


def stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def safe_relative(root: Path, relative_path: str) -> Path:
    rel = Path(str(relative_path))
    if rel.is_absolute():
        raise Gate11CDatasetValidationError("Gate 11-C manifest path must be relative")
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / rel).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise Gate11CDatasetValidationError("Gate 11-C manifest path escapes its dataset root") from exc
    return candidate


def parquet_list(paths: list[Path]) -> str:
    if not paths:
        raise Gate11CDatasetValidationError("Gate 11-C validator requires at least one Parquet partition")
    return "[" + ",".join(sql_string(path) for path in paths) + "]"


def checkpoint_lineage(*, dataset_lineage: str, role: str, year: int) -> str:
    return stable_hash(
        {
            "contract": GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION,
            "dataset_lineage": dataset_lineage,
            "role": role,
            "year": int(year),
        }
    )


def expected_dataset_columns() -> tuple[str, ...]:
    return tuple(
        list(ML_TRAINING_DATASET_IDENTITY_COLUMNS)
        + list(ML_PRODUCTION_CORE_FEATURE_NAMES)
        + list(ML_TRAINING_DATASET_OUTCOME_COLUMNS)
        + list(ML_TRAINING_DATASET_CONTEXT_COLUMNS)
    )


def recompute_builder_fingerprint(
    *,
    b_manifest: dict[str, Any],
    extension_manifest: dict[str, Any],
    composite_manifest: dict[str, Any],
    market_context_sha256: str,
    accepted_phase10: dict[str, Any],
) -> str:
    payload = {
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
        "market_context_sha256": market_context_sha256,
        "accepted_A_manifest_sha256": accepted_phase10["dataset_manifest_sha256"],
        "accepted_model_final_report_sha256": accepted_phase10["final_report_sha256"],
    }
    return stable_hash(payload)


class HistoricalBackfillLongHistoryDatasetValidator:
    """Independent Gate 11-C disk/source proof for the B/C dataset experiment.

    This validator does not call the Gate 11-C materializer. It reopens the immutable
    artifacts, verifies every partition/checkpoint/hash, recomputes source/value
    invariants from production canonical/features/regime history, proves A is a
    label-identical subset of B, and verifies C is only a manifest-bound B + extension
    composite with no physical copy of B.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.builder = HistoricalBackfillLongHistoryDatasetBuilder(settings)
        self.report_path = self.builder.root / "gate11c_dataset_validation_report.json"
        self.production_ml_write_count = 0

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not Path(path).is_file():
            raise Gate11CDatasetValidationError(f"Gate 11-C validator requires {label}: {path}")
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Gate11CDatasetValidationError(f"Gate 11-C validator found invalid JSON for {label}") from exc

    def _dataset_manifest(self, *, family: str, dataset_id: str, expected_role: str) -> tuple[Path, dict[str, Any]]:
        root = self.builder.root / family / dataset_id
        manifest_path = root / "manifest.json"
        manifest = self._read_json(manifest_path, f"{family} manifest")
        if manifest.get("contract_version") != GATE11C_PHYSICAL_DATASET_CONTRACT_VERSION:
            raise Gate11CDatasetValidationError(f"Gate 11-C {family} physical dataset contract mismatch")
        if manifest.get("role") != expected_role or manifest.get("immutable") is not True:
            raise Gate11CDatasetValidationError(f"Gate 11-C {family} role/immutability mismatch")
        if manifest.get("dataset_id") != dataset_id:
            raise Gate11CDatasetValidationError(f"Gate 11-C {family} dataset id mismatch")
        lineage = str(manifest.get("dataset_lineage_fingerprint", ""))
        if stable_hash(manifest.get("lineage_payload")) != lineage:
            raise Gate11CDatasetValidationError(f"Gate 11-C {family} lineage payload hash mismatch")
        return root, manifest

    def _audit_physical_dataset(
        self,
        *,
        root: Path,
        manifest: dict[str, Any],
        expected_rows: int,
        expected_classes: dict[str, int],
    ) -> dict[str, Any]:
        role = str(manifest["role"])
        lineage = str(manifest["dataset_lineage_fingerprint"])
        partitions = list(manifest.get("partitions") or [])
        if not partitions:
            raise Gate11CDatasetValidationError(f"Gate 11-C {role} has no partitions")

        paths: list[Path] = []
        partition_hash_failures = 0
        checkpoint_failures = 0
        partition_metadata_failures = 0
        expected_schema = expected_dataset_columns()
        schema_failures = 0

        con = connect_utc(":memory:")
        try:
            for item in partitions:
                year = int(item["year"])
                path = safe_relative(root, str(item["relative_path"]))
                if not path.is_file() or sha256_file(path) != str(item["sha256"]):
                    partition_hash_failures += 1
                    continue
                paths.append(path)

                checkpoint_path = root / f"year={year:04d}" / "_gate11c_year.json"
                checkpoint = self._read_json(checkpoint_path, f"{role} year {year} checkpoint")
                if (
                    checkpoint.get("contract_version") != GATE11C_YEAR_CHECKPOINT_CONTRACT_VERSION
                    or checkpoint.get("year_lineage_fingerprint")
                    != checkpoint_lineage(dataset_lineage=lineage, role=role, year=year)
                    or checkpoint.get("partition") != item
                ):
                    checkpoint_failures += 1

                columns = tuple(
                    str(row[0])
                    for row in con.execute(
                        f"DESCRIBE SELECT * FROM read_parquet({sql_string(path)}, hive_partitioning=false)"
                    ).fetchall()
                )
                if columns != expected_schema:
                    schema_failures += 1

                stats = con.execute(
                    f"""
                    SELECT
                        count(*), count(DISTINCT observation_key), count(DISTINCT symbol),
                        min(session_date), max(session_date),
                        count(*) FILTER (WHERE prediction_label='DOWN'),
                        count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                        count(*) FILTER (WHERE prediction_label='UP'),
                        count(*) FILTER (WHERE market_regime_available)
                    FROM read_parquet({sql_string(path)}, hive_partitioning=false)
                    """
                ).fetchone()
                assert stats is not None
                actual = {
                    "year": year,
                    "relative_path": str(item["relative_path"]),
                    "sha256": sha256_file(path),
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
                if actual != item:
                    partition_metadata_failures += 1

            if len(paths) != len(partitions):
                # Continue to report hash failures, but do not run incomplete global scans.
                return {
                    "partition_count": len(partitions),
                    "partition_hash_failures": partition_hash_failures,
                    "checkpoint_failures": checkpoint_failures,
                    "schema_failures": schema_failures,
                    "partition_metadata_failures": partition_metadata_failures,
                    "rows": -1,
                    "keys": -1,
                    "symbols": -1,
                    "first_session": None,
                    "last_session": None,
                    "class_rows": {},
                    "market_context_rows": -1,
                    "observation_key_mismatches": -1,
                    "predictor_value_failures": -1,
                    "outcome_integrity_failures": -1,
                    "context_nullability_failures": -1,
                }

            source = parquet_list(paths)
            predictor_bad = " OR ".join(
                f"{name} IS NULL OR NOT isfinite(CAST({name} AS DOUBLE))"
                for name in ML_PRODUCTION_CORE_FEATURE_NAMES
            )
            context_fields = [f"market_regime_{field}" for field in ML_MARKET_REGIME_CONTEXT_FIELDS]
            available_missing = " OR ".join(f"{field} IS NULL" for field in context_fields)
            unavailable_present = " OR ".join(f"{field} IS NOT NULL" for field in context_fields)
            threshold_scale = float(ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER) * math.sqrt(
                float(ML_PREDICTION_LABEL_HORIZON_SESSIONS)
            )
            row = con.execute(
                f"""
                SELECT
                    count(*), count(DISTINCT observation_key), count(DISTINCT symbol),
                    min(session_date), max(session_date),
                    count(*) FILTER (WHERE prediction_label='DOWN'),
                    count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                    count(*) FILTER (WHERE prediction_label='UP'),
                    count(*) FILTER (WHERE market_regime_available),
                    count(*) FILTER (
                        WHERE observation_key <> concat(instrument_id, '|', symbol, '|', CAST(session_date AS VARCHAR))
                    ),
                    count(*) FILTER (WHERE {predictor_bad}),
                    count(*) FILTER (
                        WHERE future_date IS NULL OR future_date <= session_date
                           OR future_close IS NULL OR future_close <= 0 OR NOT isfinite(CAST(future_close AS DOUBLE))
                           OR forward_return IS NULL OR NOT isfinite(CAST(forward_return AS DOUBLE))
                           OR abs(CAST(forward_return AS DOUBLE) - ((CAST(future_close AS DOUBLE)/CAST(observation_close AS DOUBLE))-1.0)) > 1e-12
                           OR label_threshold IS NULL OR NOT isfinite(CAST(label_threshold AS DOUBLE)) OR label_threshold <= 0
                           OR abs(CAST(label_threshold AS DOUBLE) - (CAST(natr_14 AS DOUBLE)*{threshold_scale:.17g})) > 1e-12
                           OR prediction_label <> CASE
                               WHEN CAST(forward_return AS DOUBLE) >= CAST(label_threshold AS DOUBLE) THEN 'UP'
                               WHEN CAST(forward_return AS DOUBLE) <= -CAST(label_threshold AS DOUBLE) THEN 'DOWN'
                               ELSE 'NEUTRAL' END
                    ),
                    count(*) FILTER (
                        WHERE (market_regime_available AND ({available_missing}))
                           OR ((NOT market_regime_available) AND ({unavailable_present}))
                    )
                FROM read_parquet({source}, hive_partitioning=false, union_by_name=true)
                """
            ).fetchone()
            assert row is not None
        finally:
            con.close()

        result = {
            "partition_count": len(partitions),
            "partition_hash_failures": partition_hash_failures,
            "checkpoint_failures": checkpoint_failures,
            "schema_failures": schema_failures,
            "partition_metadata_failures": partition_metadata_failures,
            "rows": int(row[0]),
            "keys": int(row[1]),
            "symbols": int(row[2]),
            "first_session": str(row[3]),
            "last_session": str(row[4]),
            "class_rows": {"DOWN": int(row[5]), "NEUTRAL": int(row[6]), "UP": int(row[7])},
            "market_context_rows": int(row[8]),
            "observation_key_mismatches": int(row[9]),
            "predictor_value_failures": int(row[10]),
            "outcome_integrity_failures": int(row[11]),
            "context_nullability_failures": int(row[12]),
        }
        result["manifest_totals_exact"] = bool(
            result["rows"] == int(manifest["row_count"])
            and result["keys"] == int(manifest["distinct_observation_keys"])
            and result["symbols"] == int(manifest["symbol_count"])
            and result["first_session"] == str(manifest["first_session_date"])
            and result["last_session"] == str(manifest["last_session_date"])
            and result["class_rows"] == dict(manifest["class_row_counts"])
            and result["market_context_rows"] == int(manifest["market_context_rows"])
        )
        result["accepted_totals_exact"] = bool(
            result["rows"] == expected_rows and result["keys"] == expected_rows
            and result["class_rows"] == expected_classes
        )
        return result

    def _source_value_audit(
        self,
        *,
        dataset_paths: list[Path],
        extension: bool,
        market_history: Path,
    ) -> dict[str, int]:
        source = parquet_list(dataset_paths)
        feature_glob = self.builder.paths.feature_glob(Timeframe.DAY_1)
        bar_glob = self.builder.paths.glob_for_timeframe(Timeframe.DAY_1)
        feature_diff = " OR ".join(
            f"d.{name} IS DISTINCT FROM f.{name}" for name in ML_PRODUCTION_CORE_FEATURE_NAMES
        )
        context_diff = " OR ".join(
            f"d.market_regime_{field} IS DISTINCT FROM CAST(m.{field} AS VARCHAR)"
            for field in ML_MARKET_REGIME_CONTEXT_FIELDS
        )
        con = connect_utc(":memory:")
        try:
            con.execute(
                f"""
                CREATE TEMP VIEW gate11cv_dataset AS
                SELECT * FROM read_parquet({source}, hive_partitioning=false, union_by_name=true)
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11cv_features AS
                SELECT symbol, CAST(timestamp_utc AS DATE) AS session_date,
                       {', '.join(ML_PRODUCTION_CORE_FEATURE_NAMES)}
                FROM read_parquet({sql_string(feature_glob)}, hive_partitioning=true, union_by_name=true)
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11cv_bars AS
                SELECT symbol, CAST(session_date AS DATE) AS session_date,
                       CAST(close AS DOUBLE) AS close
                FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true, union_by_name=true)
                """
            )
            con.execute(
                f"""
                CREATE TEMP VIEW gate11cv_market AS
                SELECT * FROM read_parquet({sql_string(market_history)}, hive_partitioning=false)
                """
            )
            con.execute(
                """
                CREATE TEMP VIEW gate11cv_sessions AS
                SELECT session_date, row_number() OVER (ORDER BY session_date) AS session_seq
                FROM (SELECT DISTINCT session_date FROM gate11cv_bars)
                """
            )
            row = con.execute(
                f"""
                SELECT
                    count(*) FILTER (WHERE f.symbol IS NULL),
                    count(*) FILTER (WHERE f.symbol IS NOT NULL AND ({feature_diff})),
                    count(*) FILTER (WHERE ob.symbol IS NULL OR d.observation_close IS DISTINCT FROM ob.close),
                    count(*) FILTER (WHERE fb.symbol IS NULL OR d.future_close IS DISTINCT FROM fb.close),
                    count(*) FILTER (WHERE fs.session_seq IS NULL OR fs.session_seq <> os.session_seq + {int(ML_PREDICTION_LABEL_HORIZON_SESSIONS)}),
                    count(*) FILTER (
                        WHERE d.market_regime_available IS DISTINCT FROM (m.trading_date IS NOT NULL)
                           OR (m.trading_date IS NOT NULL AND ({context_diff}))
                    )
                FROM gate11cv_dataset d
                LEFT JOIN gate11cv_features f USING (symbol, session_date)
                LEFT JOIN gate11cv_bars ob ON ob.symbol=d.symbol AND ob.session_date=d.session_date
                LEFT JOIN gate11cv_bars fb ON fb.symbol=d.symbol AND fb.session_date=d.future_date
                LEFT JOIN gate11cv_sessions os ON os.session_date=d.session_date
                LEFT JOIN gate11cv_sessions fs ON fs.session_date=d.future_date
                LEFT JOIN gate11cv_market m ON CAST(m.trading_date AS DATE)=d.session_date
                """
            ).fetchone()
            assert row is not None

            identity_mismatches = 0
            if extension:
                segment_path = self.builder.segment_policy.base.segment_path
                authority_path = self.builder.authority_audit.authority_path
                identity_mismatches = int(
                    con.execute(
                        f"""
                        SELECT count(*)
                        FROM gate11cv_dataset d
                        LEFT JOIN read_parquet({sql_string(segment_path)}) s
                          ON s.symbol=d.symbol
                         AND d.session_date BETWEEN CAST(s.first_date AS DATE) AND CAST(s.last_date AS DATE)
                        LEFT JOIN read_parquet({sql_string(authority_path)}) a
                          ON CAST(a.identity_chain_id AS VARCHAR)=CAST(s.identity_chain_id AS VARCHAR)
                        WHERE s.identity_chain_id IS NULL
                           OR coalesce(CAST(s.identity_ambiguous AS BOOLEAN), FALSE)
                           OR a.structural_eligible IS DISTINCT FROM TRUE
                           OR d.instrument_id IS DISTINCT FROM CAST(a.historical_instrument_id AS VARCHAR)
                        """
                    ).fetchone()[0]
                )
        finally:
            con.close()
        return {
            "missing_feature_rows": int(row[0]),
            "feature_value_mismatches": int(row[1]),
            "observation_close_mismatches": int(row[2]),
            "future_close_mismatches": int(row[3]),
            "horizon_mismatches": int(row[4]),
            "market_context_mismatches": int(row[5]),
            "extension_identity_authority_mismatches": identity_mismatches,
        }

    def _a_to_b_audit(self, *, b_paths: list[Path], accepted_dataset_id: str) -> dict[str, int]:
        accepted_root = self.builder.standard_training_root / accepted_dataset_id
        accepted_manifest = self._read_json(accepted_root / "manifest.json", "accepted A manifest")
        a_paths = [safe_relative(accepted_root, str(item["relative_path"])) for item in accepted_manifest["partitions"]]
        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                WITH a AS (
                    SELECT observation_key, prediction_label
                    FROM read_parquet({parquet_list(a_paths)}, hive_partitioning=false, union_by_name=true)
                ),
                b AS (
                    SELECT observation_key, prediction_label
                    FROM read_parquet({parquet_list(b_paths)}, hive_partitioning=false, union_by_name=true)
                )
                SELECT
                    (SELECT count(*) FROM a),
                    count(*) FILTER (WHERE a.observation_key IS NOT NULL),
                    count(*) FILTER (WHERE a.observation_key IS NULL),
                    count(*) FILTER (WHERE a.observation_key IS NOT NULL AND a.prediction_label <> b.prediction_label),
                    (SELECT count(*) FROM a LEFT JOIN b USING (observation_key) WHERE b.observation_key IS NULL)
                FROM b LEFT JOIN a USING (observation_key)
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        return {
            "A_rows": int(row[0]),
            "overlap_rows": int(row[1]),
            "B_only_rows": int(row[2]),
            "overlap_label_mismatches": int(row[3]),
            "A_only_rows": int(row[4]),
        }

    def run(self) -> dict[str, object]:
        build = self._read_json(self.builder.report_path, "Gate 11-C build report")
        if build.get("contract_version") != GATE11C_DATASET_BUILD_CONTRACT_VERSION:
            raise Gate11CDatasetValidationError("Gate 11-C build contract mismatch")
        if build.get("source_fingerprint") != GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT:
            raise Gate11CDatasetValidationError("Gate 11-C validator refuses an unaccepted builder fingerprint")
        if build.get("pass") is not True or int(build.get("production_ml_writes", -1)) != 0:
            raise Gate11CDatasetValidationError("Gate 11-C validator requires a passing zero-production-write build")

        gate11a, gate11b, end_date, authority_path = self.builder._load_parents()  # noqa: SLF001
        if sha256_file(authority_path) != str(dict(gate11b["authority"])["artifact_sha256"]):
            raise Gate11CDatasetValidationError("Gate 11-C authority artifact changed after the build")
        market_history, market_context_sha = self.builder._market_history(end_date, gate11b)  # noqa: SLF001

        b_report = dict(build["B"])
        x_report = dict(build["C_extension"])
        c_report = dict(build["C_composite"])
        b_root, b_manifest = self._dataset_manifest(
            family="B", dataset_id=str(b_report["dataset_id"]), expected_role=GATE11C_B_ROLE
        )
        x_root, x_manifest = self._dataset_manifest(
            family="C_extension", dataset_id=str(x_report["dataset_id"]), expected_role=GATE11C_EXTENSION_ROLE
        )
        c_root = self.builder.root / "C" / str(c_report["dataset_id"])
        c_manifest_path = c_root / "manifest.json"
        c_manifest = self._read_json(c_manifest_path, "C composite manifest")

        if c_manifest.get("contract_version") != GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION:
            raise Gate11CDatasetValidationError("Gate 11-C composite contract mismatch")
        composite_lineage = str(c_manifest.get("dataset_lineage_fingerprint", ""))
        if stable_hash(c_manifest.get("lineage_payload")) != composite_lineage:
            raise Gate11CDatasetValidationError("Gate 11-C composite lineage payload hash mismatch")

        b_audit = self._audit_physical_dataset(
            root=b_root, manifest=b_manifest, expected_rows=GATE11C_EXPECTED_B_ROWS,
            expected_classes=GATE11C_EXPECTED_B_CLASSES,
        )
        x_audit = self._audit_physical_dataset(
            root=x_root, manifest=x_manifest, expected_rows=GATE11C_EXPECTED_EXTENSION_ROWS,
            expected_classes=GATE11C_EXPECTED_EXTENSION_CLASSES,
        )
        b_paths = [safe_relative(b_root, str(item["relative_path"])) for item in b_manifest["partitions"]]
        x_paths = [safe_relative(x_root, str(item["relative_path"])) for item in x_manifest["partitions"]]

        con = connect_utc(":memory:")
        try:
            row = con.execute(
                f"""
                SELECT count(*), count(DISTINCT observation_key), count(DISTINCT symbol),
                       min(session_date), max(session_date),
                       count(*) FILTER (WHERE prediction_label='DOWN'),
                       count(*) FILTER (WHERE prediction_label='NEUTRAL'),
                       count(*) FILTER (WHERE prediction_label='UP'),
                       count(*) FILTER (WHERE market_regime_available)
                FROM read_parquet({parquet_list(b_paths + x_paths)}, hive_partitioning=false, union_by_name=true)
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        composite_recomputed = {
            "rows": int(row[0]), "keys": int(row[1]), "symbols": int(row[2]),
            "first_session": str(row[3]), "last_session": str(row[4]),
            "class_rows": {"DOWN": int(row[5]), "NEUTRAL": int(row[6]), "UP": int(row[7])},
            "market_context_rows": int(row[8]),
        }

        c_parquet_files = sorted(c_root.rglob("*.parquet")) if c_root.is_dir() else []
        b_manifest_sha = sha256_file(b_root / "manifest.json")
        x_manifest_sha = sha256_file(x_root / "manifest.json")
        c_parent_paths_exact = bool(
            safe_relative(self.builder.long_root, str(c_manifest["B_manifest_relative_path"])) == b_root / "manifest.json"
            and safe_relative(self.builder.long_root, str(c_manifest["extension_manifest_relative_path"])) == x_root / "manifest.json"
        )
        composite_parent_hashes_exact = bool(
            str(c_manifest.get("B_manifest_sha256")) == b_manifest_sha
            and str(c_manifest.get("extension_manifest_sha256")) == x_manifest_sha
        )

        expected_composite_lineage_payload = {
            "contract": GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION,
            "role": GATE11C_COMPOSITE_ROLE,
            "B_dataset_lineage": b_manifest["dataset_lineage_fingerprint"],
            "extension_dataset_lineage": x_manifest["dataset_lineage_fingerprint"],
            "predictor_columns": list(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "observation_key_contract": b_manifest["observation_key_contract"],
            "postseam_rows_are_exactly_parent_B": True,
            "accepted_model_replacement_allowed": False,
            "final_holdout_used_for_selection": False,
        }
        composite_lineage_exact = bool(
            c_manifest.get("lineage_payload") == expected_composite_lineage_payload
            and composite_lineage == stable_hash(expected_composite_lineage_payload)
        )

        b_source = self._source_value_audit(dataset_paths=b_paths, extension=False, market_history=market_history)
        x_source = self._source_value_audit(dataset_paths=x_paths, extension=True, market_history=market_history)
        a_to_b = self._a_to_b_audit(
            b_paths=b_paths,
            accepted_dataset_id=str(dict(build["accepted_phase10"])["dataset_id"]),
        )

        accepted_now = self.builder.preflight._accepted_phase10()  # noqa: SLF001
        accepted_build = dict(build["accepted_phase10"])
        accepted_phase10_exact = bool(
            accepted_now["dataset_id"] == accepted_build["dataset_id"]
            and accepted_now["dataset_manifest_sha256"] == accepted_build["dataset_manifest_sha256"]
            and accepted_now["dataset_partition_hash_failures"] == 0
            and accepted_now["model_id"] == accepted_build["model_id"]
            and accepted_now["final_report_sha256"] == accepted_build["final_report_sha256"]
            and accepted_now["production_manifest_sha256"] == accepted_build["production_manifest_sha256"]
            and accepted_now["model_hash_exact"] is True
        )
        standard_namespace_gate11_leaks = len(list(self.builder.standard_training_root.glob("mlhist-*")))

        recomputed_builder_fp = recompute_builder_fingerprint(
            b_manifest=b_manifest,
            extension_manifest=x_manifest,
            composite_manifest=c_manifest,
            market_context_sha256=market_context_sha,
            accepted_phase10=accepted_now,
        )

        gate11a_lineages = dict(gate11a["feature_lineage"])
        current_b_lineage = self.builder.preflight._feature_lineage(  # noqa: SLF001
            date.fromisoformat(str(dict(gate11a_lineages["B_rebase"])["start"])), end_date
        )
        current_c_lineage = self.builder.preflight._feature_lineage(  # noqa: SLF001
            date.fromisoformat(str(dict(gate11a_lineages["C_full"])["start"])), end_date
        )
        feature_lineages_current = bool(
            current_b_lineage["fingerprint"] == dict(gate11a_lineages["B_rebase"])["fingerprint"]
            and current_c_lineage["fingerprint"] == dict(gate11a_lineages["C_full"])["fingerprint"]
            and int(current_b_lineage["missing_count"]) == 0
            and int(current_c_lineage["missing_count"]) == 0
        )

        annual_gate11b = {
            int(item["year"]): item for item in dict(gate11b["population"])["annual_evidence"]
        }
        extension_annual_exact = all(
            int(item["row_count"]) == int(annual_gate11b[int(item["year"])]["eligible_rows"])
            and {
                "DOWN": int(item["down_rows"]),
                "NEUTRAL": int(item["neutral_rows"]),
                "UP": int(item["up_rows"]),
            } == dict(annual_gate11b[int(item["year"])]["class_rows"])
            for item in x_manifest["partitions"]
        ) and {int(item["year"]) for item in x_manifest["partitions"]} == set(annual_gate11b)

        checks = {
            "validation_contract": True,
            "builder_contract_current": build.get("contract_version") == GATE11C_DATASET_BUILD_CONTRACT_VERSION,
            "builder_report_pass": build.get("pass") is True,
            "builder_source_fingerprint_accepted": build.get("source_fingerprint")
            == GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT,
            "builder_source_fingerprint_recomputed": recomputed_builder_fp
            == GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT,
            "gate11a_fingerprint_exact": build.get("gate11a_source_fingerprint")
            == GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
            "gate11b_fingerprint_exact": build.get("gate11b_source_fingerprint")
            == GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
            "feature_lineages_current": feature_lineages_current,
            "B_partition_hashes_exact": int(b_audit["partition_hash_failures"]) == 0,
            "B_checkpoints_exact": int(b_audit["checkpoint_failures"]) == 0,
            "B_schema_exact": int(b_audit["schema_failures"]) == 0,
            "B_partition_metadata_exact": int(b_audit["partition_metadata_failures"]) == 0,
            "B_totals_exact": b_audit.get("accepted_totals_exact") is True and b_audit.get("manifest_totals_exact") is True,
            "B_observation_keys_exact": int(b_audit["observation_key_mismatches"]) == 0,
            "B_predictors_finite": int(b_audit["predictor_value_failures"]) == 0,
            "B_outcomes_exact": int(b_audit["outcome_integrity_failures"]) == 0,
            "B_context_nullability_exact": int(b_audit["context_nullability_failures"]) == 0,
            "extension_partition_hashes_exact": int(x_audit["partition_hash_failures"]) == 0,
            "extension_checkpoints_exact": int(x_audit["checkpoint_failures"]) == 0,
            "extension_schema_exact": int(x_audit["schema_failures"]) == 0,
            "extension_partition_metadata_exact": int(x_audit["partition_metadata_failures"]) == 0,
            "extension_totals_exact": x_audit.get("accepted_totals_exact") is True and x_audit.get("manifest_totals_exact") is True,
            "extension_observation_keys_exact": int(x_audit["observation_key_mismatches"]) == 0,
            "extension_predictors_finite": int(x_audit["predictor_value_failures"]) == 0,
            "extension_outcomes_exact": int(x_audit["outcome_integrity_failures"]) == 0,
            "extension_context_nullability_exact": int(x_audit["context_nullability_failures"]) == 0,
            "extension_annual_gate11b_exact": extension_annual_exact,
            "B_source_features_exact": sum(b_source.values()) == 0,
            "extension_source_features_identity_exact": sum(x_source.values()) == 0,
            "A_is_exact_label_subset_of_B": (
                a_to_b["A_rows"] == GATE11C_EXPECTED_A_ROWS
                and a_to_b["overlap_rows"] == GATE11C_EXPECTED_A_TO_B_OVERLAP
                and a_to_b["B_only_rows"] == GATE11C_EXPECTED_B_ONLY_ROWS
                and a_to_b["A_only_rows"] == 0
                and a_to_b["overlap_label_mismatches"] == 0
            ),
            "composite_parent_paths_exact": c_parent_paths_exact,
            "composite_parent_hashes_exact": composite_parent_hashes_exact,
            "composite_lineage_exact": composite_lineage_exact,
            "composite_rows_exact": composite_recomputed["rows"] == GATE11C_EXPECTED_COMPOSITE_ROWS,
            "composite_keys_unique": composite_recomputed["keys"] == GATE11C_EXPECTED_COMPOSITE_ROWS,
            "composite_classes_exact": composite_recomputed["class_rows"] == GATE11C_EXPECTED_COMPOSITE_CLASSES,
            "composite_manifest_totals_exact": (
                composite_recomputed["rows"] == int(c_manifest["row_count"])
                and composite_recomputed["keys"] == int(c_manifest["distinct_observation_keys"])
                and composite_recomputed["symbols"] == int(c_manifest["symbol_count"])
                and composite_recomputed["first_session"] == str(c_manifest["first_session_date"])
                and composite_recomputed["last_session"] == str(c_manifest["last_session_date"])
                and composite_recomputed["class_rows"] == dict(c_manifest["class_row_counts"])
                and composite_recomputed["market_context_rows"] == int(c_manifest["market_context_rows"])
            ),
            "composite_has_no_physical_parquet": len(c_parquet_files) == 0,
            "composite_postseam_is_parent_B": c_manifest.get("postseam_rows_are_exactly_parent_B") is True,
            "composite_physical_B_copy_zero": int(c_manifest.get("physical_C_copy_of_B_rows", -1)) == 0,
            "extension_preseam_boundary_exact": str(x_manifest["last_session_date"]) <= GATE11_PRESEAM_END_DATE.isoformat()
            and str(x_manifest["last_session_date"]) < str(b_manifest["first_session_date"]),
            "accepted_phase10_dataset_model_exact": accepted_phase10_exact,
            "standard_training_namespace_has_no_gate11_dataset": standard_namespace_gate11_leaks == 0,
            "predictor_matrix_core33_only": (
                int(b_manifest["predictor_count"]) == len(ML_PRODUCTION_CORE_FEATURE_NAMES)
                and tuple(b_manifest["predictor_columns"]) == tuple(ML_PRODUCTION_CORE_FEATURE_NAMES)
                and not set(ML_TRAINING_DATASET_CONTEXT_COLUMNS).intersection(b_manifest["predictor_columns"])
            ),
            "accepted_model_replacement_forbidden": GATE11C_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False,
            "final_holdout_not_used_for_selection": GATE11C_FINAL_HOLDOUT_USED_FOR_SELECTION is False,
            "production_ml_writes_zero": GATE11C_PRODUCTION_ML_WRITES == 0 and self.production_ml_write_count == 0,
        }

        fingerprint_payload = {
            "contract_version": GATE11C_DATASET_VALIDATION_CONTRACT_VERSION,
            "builder_source_fingerprint": GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT,
            "B_manifest_sha256": b_manifest_sha,
            "extension_manifest_sha256": x_manifest_sha,
            "composite_manifest_sha256": sha256_file(c_manifest_path),
            "B_audit": b_audit,
            "extension_audit": x_audit,
            "B_source_audit": b_source,
            "extension_source_audit": x_source,
            "A_to_B": a_to_b,
            "composite_recomputed": composite_recomputed,
            "accepted_A_manifest_sha256": accepted_now["dataset_manifest_sha256"],
            "accepted_model_final_report_sha256": accepted_now["final_report_sha256"],
        }
        source_fingerprint = stable_hash(fingerprint_payload)
        report: dict[str, object] = {
            "contract_version": GATE11C_DATASET_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": source_fingerprint,
            "fingerprint_scope": "CONTENT_ONLY_NO_ABSOLUTE_PATHS",
            "builder_source_fingerprint": GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT,
            "as_of_date": end_date.isoformat(),
            "B": b_audit,
            "C_extension": x_audit,
            "B_source_audit": b_source,
            "C_extension_source_audit": x_source,
            "A_to_B": a_to_b,
            "C_composite": composite_recomputed,
            "composite_manifest_sha256": sha256_file(c_manifest_path),
            "accepted_phase10": {
                "dataset_id": accepted_now["dataset_id"],
                "dataset_manifest_sha256": accepted_now["dataset_manifest_sha256"],
                "model_id": accepted_now["model_id"],
                "model_hash_exact": accepted_now["model_hash_exact"],
                "final_report_sha256": accepted_now["final_report_sha256"],
                "production_manifest_sha256": accepted_now["production_manifest_sha256"],
            },
            "checks": checks,
            "production_ml_writes": self.production_ml_write_count,
            "pass": all(bool(value) for value in checks.values()),
        }
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
