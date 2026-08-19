from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import sklearn

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.calibration_policy import (
    ML_CALIBRATION_ACCEPTED_METHOD,
    ML_CALIBRATION_POLICY_CONTRACT_VERSION,
)
from packages.ml.candidate_model_benchmark import MLCandidateModelBenchmark
from packages.ml.candidate_model_policy import (
    ML_CANDIDATE_MODEL_ACCEPTED_ACCURACY,
    ML_CANDIDATE_MODEL_ACCEPTED_BRIER,
    ML_CANDIDATE_MODEL_ACCEPTED_ECE,
    ML_CANDIDATE_MODEL_ACCEPTED_LOG_LOSS,
    ML_CANDIDATE_MODEL_ACCEPTED_MACRO_AUC,
    ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
    ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS,
    ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS,
    ML_CANDIDATE_MODEL_POLICY_CONTRACT_VERSION,
)
from packages.ml.dataset_policy import (
    ML_TRAINING_DATASET_ACCEPTED_ID,
    ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
    ML_TRAINING_DATASET_POLICY_CONTRACT_VERSION,
)
from packages.ml.feature_policy import (
    ML_FEATURE_POLICY_CONTRACT_VERSION,
    ML_PRODUCTION_CORE_FEATURE_COUNT,
)
from packages.ml.label_policy import (
    ML_PREDICTION_LABEL_HORIZON_SESSIONS,
    ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
    ML_PREDICTION_LABEL_PROBABILITY_FIELDS,
)
from packages.ml.robustness_policy import (
    ML_ROBUSTNESS_ARGMAX_IS_PRODUCTION_SIGNAL,
    ML_ROBUSTNESS_HIGHEST_SUPPORTED_ECE,
    ML_ROBUSTNESS_POLICY_CONTRACT_VERSION,
    ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC,
)
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
)


ML_MODEL_REGISTRY_CONTRACT_VERSION = (
    "ml-model-registry-v1-policy-lineage-oos-artifacts-finalfit-deferred"
)
ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION = (
    "ml-prediction-record-v1-stable-id-raw-threeclass-oos-outcome-known"
)
ML_MODEL_REGISTRY_STATUS = "ACCEPTED_CANDIDATE_AWAITING_GATE13_FINAL_FIT"
ML_MODEL_REGISTRY_FINAL_FIT_ARTIFACT_PRESENT = False
ML_MODEL_REGISTRY_FINAL_HOLDOUT_ACCESSED = False
ML_MODEL_REGISTRY_EVALUATION_ROLE = "OOS_TEST"
ML_MODEL_REGISTRY_OUTCOME_STATUS = "KNOWN_HISTORICAL_OOS"
ML_MODEL_REGISTRY_AVAILABILITY = "POST_SESSION_CLOSE_AFTER_DAILY_FEATURE_MATERIALIZATION"
ML_MODEL_REGISTRY_RANDOM_STATE = 42
ML_MODEL_REGISTRY_MODEL_FAMILY = "sklearn_hist_gradient_boosting"
ML_MODEL_REGISTRY_SPEC = {
    "max_leaf_nodes": 15,
    "max_iter": 100,
    "learning_rate": 0.05,
    "min_samples_leaf": 100,
    "l2_regularization": 1.0,
    "max_bins": 255,
    "early_stopping": False,
    "random_state": ML_MODEL_REGISTRY_RANDOM_STATE,
    "training_cap_rows": ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS,
}


@dataclass(frozen=True, slots=True)
class RegistryPredictionArtifact:
    fold_index: int
    source_relative_path: str
    source_sha256: str
    relative_path: str
    sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class MLModelRegistryManifest:
    contract_version: str
    prediction_contract_version: str
    generated_at_utc: str
    model_id: str
    model_fingerprint: str
    status: str
    model_family: str
    model_name: str
    model_spec: dict[str, object]
    sklearn_version: str
    dataset_policy_contract: str
    dataset_id: str
    dataset_lineage_sha256: str
    feature_policy_contract: str
    feature_count: int
    label_policy_contract: str
    label_horizon_sessions: int
    probability_fields: tuple[str, ...]
    walk_forward_policy_contract: str
    calibration_policy_contract: str
    calibration_method: str
    robustness_policy_contract: str
    oos_fold_count: int
    oos_rows: int
    oos_metrics: dict[str, float]
    risk_caveats: dict[str, object]
    evaluation_role: str
    outcome_status: str
    prediction_availability: str
    final_holdout_start: str
    final_holdout_accessed: bool
    final_fit_artifact_present: bool
    prediction_artifacts: tuple[RegistryPredictionArtifact, ...]
    report_path: str
    wall_seconds: float


def _stable_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def model_registry_fingerprint() -> str:
    return _stable_sha256(
        {
            "registry_contract": ML_MODEL_REGISTRY_CONTRACT_VERSION,
            "prediction_contract": ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION,
            "model_family": ML_MODEL_REGISTRY_MODEL_FAMILY,
            "model_name": ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
            "model_spec": ML_MODEL_REGISTRY_SPEC,
            "sklearn_version": sklearn.__version__,
            "dataset_id": ML_TRAINING_DATASET_ACCEPTED_ID,
            "dataset_lineage": ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
            "dataset_policy": ML_TRAINING_DATASET_POLICY_CONTRACT_VERSION,
            "feature_policy": ML_FEATURE_POLICY_CONTRACT_VERSION,
            "label_policy": ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
            "candidate_policy": ML_CANDIDATE_MODEL_POLICY_CONTRACT_VERSION,
            "walk_forward_policy": ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
            "calibration_policy": ML_CALIBRATION_POLICY_CONTRACT_VERSION,
            "robustness_policy": ML_ROBUSTNESS_POLICY_CONTRACT_VERSION,
        }
    )


def accepted_model_id() -> str:
    return f"mlmodel-hgb15-2026-08-14-{model_registry_fingerprint()[:16]}"


class MLModelRegistryMaterializer:
    """Materialize Gate 12 registry metadata and immutable historical OOS predictions.

    Gate 12 does not fit the final production model and never reads the Gate 13 holdout.
    It binds the accepted candidate specification and all Phase 10 policy lineage to
    hash-verified historical OOS prediction records. The final fitted model artifact is
    deliberately deferred until Gate 13 acceptance.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.gate9 = MLCandidateModelBenchmark(settings)
        self.model_id = accepted_model_id()
        self.fingerprint = model_registry_fingerprint()

    def registry_root(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "model_registry" / self.model_id

    def report_path(self) -> Path:
        return self.registry_root() / "manifest.json"

    def prediction_root(self) -> Path:
        return self.registry_root() / "predictions" / "role=oos_test"

    def _gate9_payload(self) -> dict[str, object]:
        path = self.gate9.report_path()
        if not path.exists():
            raise FileNotFoundError(f"Gate 12 requires Gate 9 report: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("final_holdout_accessed") is not False:
            raise RuntimeError("Gate 12 refuses Gate 9 evidence that accessed the final holdout")
        if int(payload.get("fold_count", 0)) != ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT:
            raise RuntimeError("Gate 12 Gate 9 fold count mismatch")
        if int(payload.get("total_test_rows", 0)) != ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS:
            raise RuntimeError("Gate 12 Gate 9 OOS row count mismatch")
        return payload

    @staticmethod
    def _accepted_fold_item(payload: dict[str, object], fold_index: int) -> dict[str, object]:
        items = payload.get("fold_evidence")
        if not isinstance(items, list):
            raise RuntimeError("Gate 12 Gate 9 report has no fold evidence")
        matches = [
            item for item in items
            if isinstance(item, dict)
            and item.get("model_name") == ML_CANDIDATE_MODEL_ACCEPTED_MODEL
            and int(item.get("fold_index", -1)) == fold_index
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Gate 12 expected one accepted fold item for {fold_index}")
        return matches[0]

    def _materialize_fold(
        self,
        *,
        fold_index: int,
        item: dict[str, object],
    ) -> RegistryPredictionArtifact:
        artifact = item.get("test_artifact")
        if not isinstance(artifact, dict):
            raise RuntimeError("Gate 12 Gate 9 fold item is missing test artifact")
        source = self.gate9.report_path().parent / str(artifact["relative_path"])
        if not source.exists():
            raise FileNotFoundError(source)
        source_hash = sha256_file(source)
        if source_hash != str(artifact["sha256"]):
            raise RuntimeError(f"Gate 12 source prediction hash mismatch: {source}")

        target = self.prediction_root() / f"fold={fold_index:02d}" / "part-000.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        fields = tuple(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)
        con = connect_utc(":memory:")
        try:
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (
                    SELECT
                        sha256(
                            {sql_string(self.model_id)} || '|' ||
                            {sql_string(ML_MODEL_REGISTRY_EVALUATION_ROLE)} || '|' ||
                            CAST(fold_index AS VARCHAR) || '|' || observation_key
                        ) AS prediction_id,
                        {sql_string(ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION)} AS prediction_contract_version,
                        {sql_string(self.model_id)} AS model_id,
                        {sql_string(self.fingerprint)} AS model_fingerprint,
                        {sql_string(ML_TRAINING_DATASET_ACCEPTED_ID)} AS dataset_id,
                        {sql_string(ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256)} AS dataset_lineage_sha256,
                        fold_index,
                        {sql_string(ML_MODEL_REGISTRY_EVALUATION_ROLE)} AS evaluation_role,
                        observation_key,
                        session_date,
                        symbol,
                        instrument_id,
                        {int(ML_PREDICTION_LABEL_HORIZON_SESSIONS)} AS horizon_sessions,
                        {sql_string(ML_MODEL_REGISTRY_AVAILABILITY)} AS probability_availability,
                        {sql_string(ML_CALIBRATION_ACCEPTED_METHOD)} AS calibration_method,
                        CAST({fields[0]} AS DOUBLE) AS {fields[0]},
                        CAST({fields[1]} AS DOUBLE) AS {fields[1]},
                        CAST({fields[2]} AS DOUBLE) AS {fields[2]},
                        actual_label,
                        {sql_string(ML_MODEL_REGISTRY_OUTCOME_STATUS)} AS outcome_status,
                        FALSE AS final_holdout
                    FROM read_parquet({sql_string(source.as_posix())})
                    ORDER BY session_date, symbol, instrument_id
                )
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            rows = int(con.execute(
                f"SELECT count(*) FROM read_parquet({sql_string(temp.as_posix())})"
            ).fetchone()[0])
            distinct_ids = int(con.execute(
                f"SELECT count(DISTINCT prediction_id) FROM read_parquet({sql_string(temp.as_posix())})"
            ).fetchone()[0])
            holdout_rows = int(con.execute(
                f"SELECT count(*) FROM read_parquet({sql_string(temp.as_posix())}) WHERE final_holdout"
            ).fetchone()[0])
            if rows != int(artifact["row_count"]):
                raise RuntimeError(f"Gate 12 fold {fold_index} row count mismatch")
            if distinct_ids != rows:
                raise RuntimeError(f"Gate 12 fold {fold_index} prediction ids are not unique")
            if holdout_rows != 0:
                raise RuntimeError("Gate 12 immutable prediction artifact contains final holdout rows")
            promote(temp, target)
        finally:
            con.close()

        return RegistryPredictionArtifact(
            fold_index=int(fold_index),
            source_relative_path=str(artifact["relative_path"]),
            source_sha256=source_hash,
            relative_path=str(target.relative_to(self.registry_root())),
            sha256=sha256_file(target),
            row_count=rows,
        )

    def materialize(self) -> MLModelRegistryManifest:
        started = perf_counter()
        payload = self._gate9_payload()
        artifacts = tuple(
            self._materialize_fold(
                fold_index=fold_index,
                item=self._accepted_fold_item(payload, fold_index),
            )
            for fold_index in range(1, ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT + 1)
        )
        rows = sum(item.row_count for item in artifacts)
        if rows != ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS:
            raise RuntimeError(f"Gate 12 prediction rows do not reconcile: {rows:,}")

        manifest = MLModelRegistryManifest(
            contract_version=ML_MODEL_REGISTRY_CONTRACT_VERSION,
            prediction_contract_version=ML_IMMUTABLE_PREDICTION_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            model_id=self.model_id,
            model_fingerprint=self.fingerprint,
            status=ML_MODEL_REGISTRY_STATUS,
            model_family=ML_MODEL_REGISTRY_MODEL_FAMILY,
            model_name=ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
            model_spec=dict(ML_MODEL_REGISTRY_SPEC),
            sklearn_version=sklearn.__version__,
            dataset_policy_contract=ML_TRAINING_DATASET_POLICY_CONTRACT_VERSION,
            dataset_id=ML_TRAINING_DATASET_ACCEPTED_ID,
            dataset_lineage_sha256=ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
            feature_policy_contract=ML_FEATURE_POLICY_CONTRACT_VERSION,
            feature_count=ML_PRODUCTION_CORE_FEATURE_COUNT,
            label_policy_contract=ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
            label_horizon_sessions=ML_PREDICTION_LABEL_HORIZON_SESSIONS,
            probability_fields=tuple(ML_PREDICTION_LABEL_PROBABILITY_FIELDS),
            walk_forward_policy_contract=ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
            calibration_policy_contract=ML_CALIBRATION_POLICY_CONTRACT_VERSION,
            calibration_method=ML_CALIBRATION_ACCEPTED_METHOD,
            robustness_policy_contract=ML_ROBUSTNESS_POLICY_CONTRACT_VERSION,
            oos_fold_count=ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
            oos_rows=rows,
            oos_metrics={
                "log_loss": ML_CANDIDATE_MODEL_ACCEPTED_LOG_LOSS,
                "multiclass_brier": ML_CANDIDATE_MODEL_ACCEPTED_BRIER,
                "accuracy": ML_CANDIDATE_MODEL_ACCEPTED_ACCURACY,
                "macro_ovr_auc": ML_CANDIDATE_MODEL_ACCEPTED_MACRO_AUC,
                "macro_ece": ML_CANDIDATE_MODEL_ACCEPTED_ECE,
            },
            risk_caveats={
                "argmax_is_production_signal": ML_ROBUSTNESS_ARGMAX_IS_PRODUCTION_SIGNAL,
                "weakest_supported_auc": ML_ROBUSTNESS_WEAKEST_SUPPORTED_AUC,
                "highest_supported_ece": ML_ROBUSTNESS_HIGHEST_SUPPORTED_ECE,
            },
            evaluation_role=ML_MODEL_REGISTRY_EVALUATION_ROLE,
            outcome_status=ML_MODEL_REGISTRY_OUTCOME_STATUS,
            prediction_availability=ML_MODEL_REGISTRY_AVAILABILITY,
            final_holdout_start=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            final_holdout_accessed=ML_MODEL_REGISTRY_FINAL_HOLDOUT_ACCESSED,
            final_fit_artifact_present=ML_MODEL_REGISTRY_FINAL_FIT_ARTIFACT_PRESENT,
            prediction_artifacts=artifacts,
            report_path=str(self.report_path()),
            wall_seconds=perf_counter() - started,
        )
        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
        )
        return manifest
