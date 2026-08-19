from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.baseline_benchmark import MLBaselineBenchmark
from packages.ml.candidate_model_probe import ML_CANDIDATE_MODEL_HASH_BUCKETS
from packages.ml.candidate_model_policy import (
    ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
    ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS,
)
from packages.ml.dataset_policy import (
    ML_TRAINING_DATASET_ACCEPTED_ID,
    ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
)
from packages.ml.evaluation import ProbabilityMetrics, class_indices, probability_metrics, validate_probabilities
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.label_policy import ML_PREDICTION_LABEL_CLASSES, ML_PREDICTION_LABEL_PROBABILITY_FIELDS
from packages.ml.model_registry import (
    ML_MODEL_REGISTRY_MODEL_FAMILY,
    ML_MODEL_REGISTRY_SPEC,
    accepted_model_id,
    model_registry_fingerprint,
)
from packages.ml.model_registry_policy import (
    ML_MODEL_REGISTRY_ACCEPTED_FINGERPRINT,
    ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID,
    ML_MODEL_REGISTRY_ACCEPTED_OOS_ROWS,
    ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256,
    ML_MODEL_REGISTRY_POLICY_ACCEPTED,
    ML_MODEL_REGISTRY_POLICY_CONTRACT_VERSION,
)
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_FINAL_HOLDOUT_END,
    ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_PURGE_SESSIONS,
)


ML_FINAL_ACCEPTANCE_CONTRACT_VERSION = (
    "ml-final-acceptance-v1-purged-finalfit-replay-prior-untouched-holdout"
)
ML_FINAL_ACCEPTANCE_STATUS_PENDING = "EVIDENCE_ONLY"
ML_FINAL_ACCEPTANCE_MIN_MACRO_AUC = 0.52
ML_FINAL_ACCEPTANCE_REQUIRE_LOGLOSS_WIN_VS_PRIOR = True
ML_FINAL_ACCEPTANCE_REQUIRE_BRIER_WIN_VS_PRIOR = True
ML_FINAL_ACCEPTANCE_REPLAY_MAX_ABS_DIFF = 1e-12
ML_FINAL_ACCEPTANCE_TRAINING_SAMPLE_RULE = "DETERMINISTIC_OBSERVATION_KEY_HASH_CAP"
ML_FINAL_ACCEPTANCE_FINAL_MODEL_STATUS = "ACCEPTED_PRODUCTION_MODEL"
ML_FINAL_ACCEPTANCE_HOLDOUT_ROLE = "FINAL_UNTOUCHED_HOLDOUT"
ML_FINAL_ACCEPTANCE_OUTCOME_STATUS = "KNOWN_FINAL_HOLDOUT"


@dataclass(frozen=True, slots=True)
class FinalArtifact:
    relative_path: str
    sha256: str
    row_count: int | None = None


@dataclass(frozen=True, slots=True)
class MLFinalAcceptanceReport:
    contract_version: str
    generated_at_utc: str
    status: str
    accepted: bool
    model_registry_policy_contract: str
    model_id: str
    model_fingerprint: str
    model_family: str
    model_name: str
    model_spec: dict[str, object]
    sklearn_version: str
    dataset_id: str
    dataset_lineage_sha256: str
    feature_count: int
    training_sample_rule: str
    training_cap_rows: int
    train_start: str
    train_end: str
    full_train_rows: int
    sampled_train_rows: int
    sample_threshold: int
    purge_sessions: tuple[str, ...]
    training_rows_with_future_endpoint_in_holdout: int
    holdout_start: str
    holdout_end: str
    holdout_sessions: int
    holdout_rows: int
    holdout_accessed: bool
    train_class_probabilities: dict[str, float]
    prior_metrics: ProbabilityMetrics
    model_metrics: ProbabilityMetrics
    relative_log_loss_improvement_vs_prior: float
    relative_brier_improvement_vs_prior: float
    minimum_macro_auc: float
    replay_max_abs_probability_diff: float
    replay_passed: bool
    acceptance_checks: dict[str, bool]
    gate12_manifest_sha256: str
    gate12_prediction_artifacts_verified: int
    final_model_artifact: FinalArtifact | None
    final_prediction_artifact: FinalArtifact | None
    production_manifest_path: str | None
    report_path: str
    wall_seconds: float


class MLFinalAcceptance:
    """Run the one-time Phase 10 final holdout acceptance test.

    The accepted Gate 12 model specification is fit on a deterministic sample drawn
    from every eligible pre-holdout training observation. Three full exchange sessions
    are purged before the holdout so no training label endpoint enters the holdout.
    The final 63-session holdout is then scored once. A second ephemeral fit on the
    identical sample verifies deterministic reproducibility; only the primary fit can
    be serialized as the accepted production artifact.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        if not ML_MODEL_REGISTRY_POLICY_ACCEPTED:
            raise RuntimeError("Gate 13 requires accepted Gate 12 registry evidence")
        if accepted_model_id() != ML_MODEL_REGISTRY_ACCEPTED_MODEL_ID:
            raise RuntimeError("Gate 13 model id differs from accepted Gate 12 identity")
        if model_registry_fingerprint() != ML_MODEL_REGISTRY_ACCEPTED_FINGERPRINT:
            raise RuntimeError("Gate 13 model fingerprint differs from accepted Gate 12 identity")
        self.settings = settings
        self.baseline = MLBaselineBenchmark(settings)
        self.predictors = tuple(ML_PRODUCTION_CORE_FEATURE_NAMES)
        self.model_id = accepted_model_id()
        self.fingerprint = model_registry_fingerprint()

    def registry_root(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "model_registry" / self.model_id

    def gate12_manifest_path(self) -> Path:
        return self.registry_root() / "manifest.json"

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "final_acceptance" / "2026" / "2026-08-14.json"

    def final_model_path(self) -> Path:
        return self.registry_root() / "final_fit" / "model.joblib"

    def final_prediction_path(self) -> Path:
        return self.registry_root() / "predictions" / "role=final_holdout" / "part-000.parquet"

    def production_manifest_path(self) -> Path:
        return self.registry_root() / "production_manifest.json"

    def _verify_gate12(self) -> tuple[str, int]:
        manifest_path = self.gate12_manifest_path()
        if not manifest_path.exists():
            raise FileNotFoundError(f"Gate 13 requires Gate 12 manifest: {manifest_path}")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload.get("model_id") != self.model_id:
            raise RuntimeError("Gate 13 Gate 12 manifest model id mismatch")
        if payload.get("model_fingerprint") != self.fingerprint:
            raise RuntimeError("Gate 13 Gate 12 manifest fingerprint mismatch")
        if int(payload.get("oos_rows", 0)) != ML_MODEL_REGISTRY_ACCEPTED_OOS_ROWS:
            raise RuntimeError("Gate 13 Gate 12 OOS rows mismatch")
        if payload.get("final_holdout_accessed") is not False:
            raise RuntimeError("Gate 13 refuses a Gate 12 manifest that already accessed holdout")
        if payload.get("final_fit_artifact_present") is not False:
            raise RuntimeError("Gate 13 refuses a Gate 12 manifest with a pre-existing final fit")

        artifacts = payload.get("prediction_artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != len(ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256):
            raise RuntimeError("Gate 13 Gate 12 prediction artifact count mismatch")
        verified = 0
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                raise RuntimeError("Gate 13 malformed Gate 12 prediction artifact")
            fold = int(artifact["fold_index"])
            expected_hash = ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256.get(fold)
            if expected_hash is None or str(artifact.get("sha256")) != expected_hash:
                raise RuntimeError(f"Gate 13 Gate 12 manifest hash mismatch for fold {fold}")
            path = self.registry_root() / str(artifact["relative_path"])
            if not path.exists() or sha256_file(path) != expected_hash:
                raise RuntimeError(f"Gate 13 Gate 12 artifact verification failed for fold {fold}")
            verified += 1
        return sha256_file(manifest_path), verified

    def _session_boundaries(self, con) -> tuple[str, str, tuple[str, ...]]:
        rows = con.execute(
            f"""
            SELECT DISTINCT CAST(session_date AS VARCHAR)
            FROM read_parquet({sql_string(self.baseline.dataset_glob)}, hive_partitioning=true)
            ORDER BY 1
            """
        ).fetchall()
        sessions = [str(row[0]) for row in rows]
        try:
            holdout_index = sessions.index(ML_WALK_FORWARD_FINAL_HOLDOUT_START)
            holdout_end_index = sessions.index(ML_WALK_FORWARD_FINAL_HOLDOUT_END)
        except ValueError as exc:
            raise RuntimeError("Gate 13 locked holdout boundary is absent from dataset sessions") from exc
        holdout_sessions = sessions[holdout_index : holdout_end_index + 1]
        if len(holdout_sessions) != ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS:
            raise RuntimeError("Gate 13 holdout session count differs from Gate 7")
        purge_start = holdout_index - ML_WALK_FORWARD_PURGE_SESSIONS
        if purge_start <= 0:
            raise RuntimeError("Gate 13 dataset does not contain sufficient pre-holdout history")
        purge = tuple(sessions[purge_start:holdout_index])
        if len(purge) != ML_WALK_FORWARD_PURGE_SESSIONS:
            raise RuntimeError("Gate 13 purge session count mismatch")
        train_end = sessions[purge_start - 1]
        return sessions[0], train_end, purge

    @staticmethod
    def _sample_threshold(full_train_rows: int) -> int:
        fraction = min(1.0, ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS / max(1, full_train_rows))
        return max(
            1,
            min(
                ML_CANDIDATE_MODEL_HASH_BUCKETS,
                int(round(fraction * ML_CANDIDATE_MODEL_HASH_BUCKETS)),
            ),
        )

    def _training_population(self, con, train_start: str, train_end: str) -> tuple[int, dict[str, float], int]:
        row = con.execute(
            f"""
            SELECT
                count(*) AS rows,
                count(*) FILTER (WHERE prediction_label='DOWN') AS down_rows,
                count(*) FILTER (WHERE prediction_label='NEUTRAL') AS neutral_rows,
                count(*) FILTER (WHERE prediction_label='UP') AS up_rows,
                count(*) FILTER (WHERE future_date >= DATE '{ML_WALK_FORWARD_FINAL_HOLDOUT_START}') AS leakage_rows
            FROM read_parquet({sql_string(self.baseline.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{train_start}' AND DATE '{train_end}'
            """
        ).fetchone()
        rows = int(row[0])
        if rows <= 0:
            raise RuntimeError("Gate 13 has no eligible pre-holdout training rows")
        counts = [int(row[1]), int(row[2]), int(row[3])]
        probabilities = {
            label: count / rows
            for label, count in zip(ML_PREDICTION_LABEL_CLASSES, counts, strict=True)
        }
        return rows, probabilities, int(row[4])

    def _training_sample(self, con, train_start: str, train_end: str, full_train_rows: int) -> tuple[pd.DataFrame, int]:
        threshold = self._sample_threshold(full_train_rows)
        columns = ", ".join(self.predictors)
        frame = con.execute(
            f"""
            SELECT observation_key, prediction_label, {columns}
            FROM read_parquet({sql_string(self.baseline.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{train_start}' AND DATE '{train_end}'
              AND (hash(observation_key) % {ML_CANDIDATE_MODEL_HASH_BUCKETS}) < {threshold}
            ORDER BY session_date, symbol, instrument_id
            """
        ).fetch_df()
        if len(frame) < 750_000:
            raise RuntimeError("Gate 13 deterministic final training sample is unexpectedly small")
        return frame, threshold

    def _holdout_frame(self, con) -> pd.DataFrame:
        frame = self.baseline._evaluation_frame(
            con,
            ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            ML_WALK_FORWARD_FINAL_HOLDOUT_END,
        )
        if len(frame) != ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS:
            raise RuntimeError(
                f"Gate 13 holdout rows do not reconcile: {len(frame):,} != {ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS:,}"
            )
        if str(frame["session_date"].min())[:10] != ML_WALK_FORWARD_FINAL_HOLDOUT_START:
            raise RuntimeError("Gate 13 holdout start date mismatch")
        if str(frame["session_date"].max())[:10] != ML_WALK_FORWARD_FINAL_HOLDOUT_END:
            raise RuntimeError("Gate 13 holdout end date mismatch")
        return frame

    @staticmethod
    def _model() -> HistGradientBoostingClassifier:
        spec = ML_MODEL_REGISTRY_SPEC
        return HistGradientBoostingClassifier(
            loss="log_loss",
            learning_rate=float(spec["learning_rate"]),
            max_iter=int(spec["max_iter"]),
            max_leaf_nodes=int(spec["max_leaf_nodes"]),
            min_samples_leaf=int(spec["min_samples_leaf"]),
            l2_regularization=float(spec["l2_regularization"]),
            max_bins=int(spec["max_bins"]),
            early_stopping=bool(spec["early_stopping"]),
            random_state=int(spec["random_state"]),
        )

    def _xy(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = frame.loc[:, list(self.predictors)].to_numpy(dtype=np.float32, copy=True)
        y = class_indices(frame["prediction_label"].to_numpy())
        return x, y

    @staticmethod
    def _prior_probabilities(rows: int, class_probabilities: dict[str, float]) -> np.ndarray:
        vector = np.asarray(
            [class_probabilities[label] for label in ML_PREDICTION_LABEL_CLASSES],
            dtype=np.float64,
        )
        return np.repeat(vector.reshape(1, -1), int(rows), axis=0)

    def _write_model(self, model: HistGradientBoostingClassifier) -> FinalArtifact:
        target = self.final_model_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        try:
            joblib.dump(model, temp, compress=3)
            promote(temp, target)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        return FinalArtifact(
            relative_path=str(target.relative_to(self.registry_root())),
            sha256=sha256_file(target),
        )

    def _write_predictions(self, frame: pd.DataFrame, probabilities: np.ndarray) -> FinalArtifact:
        probabilities = validate_probabilities(probabilities)
        out = frame.loc[:, ["observation_key", "session_date", "symbol", "instrument_id", "prediction_label"]].copy()
        out = out.rename(columns={"prediction_label": "actual_label"})
        for index, field in enumerate(ML_PREDICTION_LABEL_PROBABILITY_FIELDS):
            out[field] = probabilities[:, index].astype(np.float64)

        target = self.final_prediction_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        con = connect_utc(":memory:")
        try:
            con.register("final_holdout_predictions", out)
            fields = tuple(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (
                    SELECT
                        sha256(
                            {sql_string(self.model_id)} || '|' ||
                            {sql_string(ML_FINAL_ACCEPTANCE_HOLDOUT_ROLE)} || '|' || observation_key
                        ) AS prediction_id,
                        {sql_string(self.model_id)} AS model_id,
                        {sql_string(self.fingerprint)} AS model_fingerprint,
                        {sql_string(ML_FINAL_ACCEPTANCE_HOLDOUT_ROLE)} AS evaluation_role,
                        observation_key,
                        session_date,
                        symbol,
                        instrument_id,
                        CAST({fields[0]} AS DOUBLE) AS {fields[0]},
                        CAST({fields[1]} AS DOUBLE) AS {fields[1]},
                        CAST({fields[2]} AS DOUBLE) AS {fields[2]},
                        actual_label,
                        {sql_string(ML_FINAL_ACCEPTANCE_OUTCOME_STATUS)} AS outcome_status,
                        TRUE AS final_holdout
                    FROM final_holdout_predictions
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
            if rows != ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS or distinct_ids != rows:
                raise RuntimeError("Gate 13 final prediction artifact does not reconcile")
            promote(temp, target)
        finally:
            con.close()
        return FinalArtifact(
            relative_path=str(target.relative_to(self.registry_root())),
            sha256=sha256_file(target),
            row_count=rows,
        )

    def _write_production_manifest(
        self,
        *,
        report: MLFinalAcceptanceReport,
    ) -> str:
        path = self.production_manifest_path()
        payload = {
            "status": ML_FINAL_ACCEPTANCE_FINAL_MODEL_STATUS,
            "model_id": report.model_id,
            "model_fingerprint": report.model_fingerprint,
            "model_family": report.model_family,
            "model_name": report.model_name,
            "model_spec": report.model_spec,
            "dataset_id": report.dataset_id,
            "dataset_lineage_sha256": report.dataset_lineage_sha256,
            "training_sample_rule": report.training_sample_rule,
            "full_train_rows": report.full_train_rows,
            "sampled_train_rows": report.sampled_train_rows,
            "train_start": report.train_start,
            "train_end": report.train_end,
            "purge_sessions": report.purge_sessions,
            "holdout_start": report.holdout_start,
            "holdout_end": report.holdout_end,
            "holdout_rows": report.holdout_rows,
            "holdout_metrics": asdict(report.model_metrics),
            "prior_metrics": asdict(report.prior_metrics),
            "acceptance_checks": report.acceptance_checks,
            "final_model_artifact": None if report.final_model_artifact is None else asdict(report.final_model_artifact),
            "final_prediction_artifact": None if report.final_prediction_artifact is None else asdict(report.final_prediction_artifact),
            "gate12_manifest_sha256": report.gate12_manifest_sha256,
            "final_holdout_accessed": True,
            "final_fit_artifact_present": True,
            "accepted_at_utc": report.generated_at_utc,
        }
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return str(path)

    def run(self, progress=None) -> MLFinalAcceptanceReport:
        started = perf_counter()
        gate12_manifest_hash, verified_artifacts = self._verify_gate12()
        con = connect_utc(":memory:")
        try:
            train_start, train_end, purge_sessions = self._session_boundaries(con)
            full_train_rows, train_class_probabilities, leakage_rows = self._training_population(
                con, train_start, train_end
            )
            training, sample_threshold = self._training_sample(
                con, train_start, train_end, full_train_rows
            )
        finally:
            con.close()

        if leakage_rows != 0:
            raise RuntimeError(
                f"Gate 13 leakage audit found {leakage_rows:,} training rows with endpoints in holdout"
            )

        x_train, y_train = self._xy(training)
        sampled_train_rows = len(training)
        del training

        if progress is not None:
            progress(
                f"training primary final fit: sample={sampled_train_rows:,}/{full_train_rows:,} "
                f"train={train_start}->{train_end} purge={purge_sessions}"
            )
        primary = self._model()
        primary.fit(x_train, y_train)

        if progress is not None:
            progress("training deterministic replay fit on identical sample")
        replay = self._model()
        replay.fit(x_train, y_train)
        del x_train, y_train

        con = connect_utc(":memory:")
        try:
            holdout = self._holdout_frame(con)
        finally:
            con.close()
        x_holdout, _ = self._xy(holdout)
        labels = holdout["prediction_label"].to_numpy()

        primary_probabilities = validate_probabilities(primary.predict_proba(x_holdout))
        replay_probabilities = validate_probabilities(replay.predict_proba(x_holdout))
        replay_diff = float(np.max(np.abs(primary_probabilities - replay_probabilities)))
        replay_passed = replay_diff <= ML_FINAL_ACCEPTANCE_REPLAY_MAX_ABS_DIFF
        del replay, replay_probabilities, x_holdout

        model_metrics = probability_metrics(labels, primary_probabilities)
        prior_probabilities = self._prior_probabilities(len(holdout), train_class_probabilities)
        prior_metrics = probability_metrics(labels, prior_probabilities)
        del prior_probabilities

        relative_logloss = (prior_metrics.log_loss - model_metrics.log_loss) / prior_metrics.log_loss
        relative_brier = (
            (prior_metrics.multiclass_brier - model_metrics.multiclass_brier)
            / prior_metrics.multiclass_brier
        )
        logloss_passed = (
            model_metrics.log_loss < prior_metrics.log_loss
            if ML_FINAL_ACCEPTANCE_REQUIRE_LOGLOSS_WIN_VS_PRIOR
            else True
        )
        brier_passed = (
            model_metrics.multiclass_brier < prior_metrics.multiclass_brier
            if ML_FINAL_ACCEPTANCE_REQUIRE_BRIER_WIN_VS_PRIOR
            else True
        )
        checks = {
            "gate12_identity_and_artifacts_verified": verified_artifacts == len(ML_MODEL_REGISTRY_ACCEPTED_PREDICTION_ARTIFACT_SHA256),
            "three_session_purge_applied": len(purge_sessions) == ML_WALK_FORWARD_PURGE_SESSIONS,
            "no_training_label_endpoint_enters_holdout": leakage_rows == 0,
            "holdout_rows_match_locked_gate7_count": len(holdout) == ML_WALK_FORWARD_FINAL_HOLDOUT_ROWS,
            "deterministic_replay_passed": replay_passed,
            "log_loss_beats_train_prior": logloss_passed,
            "brier_beats_train_prior": brier_passed,
            "macro_auc_meets_locked_floor": (
                model_metrics.macro_ovr_auc is not None
                and model_metrics.macro_ovr_auc >= ML_FINAL_ACCEPTANCE_MIN_MACRO_AUC
            ),
        }
        accepted = all(checks.values())

        model_artifact = None
        prediction_artifact = None
        production_manifest = None
        if accepted:
            model_artifact = self._write_model(primary)
            prediction_artifact = self._write_predictions(holdout, primary_probabilities)

        report = MLFinalAcceptanceReport(
            contract_version=ML_FINAL_ACCEPTANCE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            status=(ML_FINAL_ACCEPTANCE_FINAL_MODEL_STATUS if accepted else "REJECTED_FINAL_HOLDOUT"),
            accepted=accepted,
            model_registry_policy_contract=ML_MODEL_REGISTRY_POLICY_CONTRACT_VERSION,
            model_id=self.model_id,
            model_fingerprint=self.fingerprint,
            model_family=ML_MODEL_REGISTRY_MODEL_FAMILY,
            model_name=ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
            model_spec=dict(ML_MODEL_REGISTRY_SPEC),
            sklearn_version=sklearn.__version__,
            dataset_id=ML_TRAINING_DATASET_ACCEPTED_ID,
            dataset_lineage_sha256=ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
            feature_count=len(self.predictors),
            training_sample_rule=ML_FINAL_ACCEPTANCE_TRAINING_SAMPLE_RULE,
            training_cap_rows=ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS,
            train_start=train_start,
            train_end=train_end,
            full_train_rows=full_train_rows,
            sampled_train_rows=sampled_train_rows,
            sample_threshold=sample_threshold,
            purge_sessions=purge_sessions,
            training_rows_with_future_endpoint_in_holdout=leakage_rows,
            holdout_start=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            holdout_end=ML_WALK_FORWARD_FINAL_HOLDOUT_END,
            holdout_sessions=ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS,
            holdout_rows=len(holdout),
            holdout_accessed=True,
            train_class_probabilities=train_class_probabilities,
            prior_metrics=prior_metrics,
            model_metrics=model_metrics,
            relative_log_loss_improvement_vs_prior=relative_logloss,
            relative_brier_improvement_vs_prior=relative_brier,
            minimum_macro_auc=ML_FINAL_ACCEPTANCE_MIN_MACRO_AUC,
            replay_max_abs_probability_diff=replay_diff,
            replay_passed=replay_passed,
            acceptance_checks=checks,
            gate12_manifest_sha256=gate12_manifest_hash,
            gate12_prediction_artifacts_verified=verified_artifacts,
            final_model_artifact=model_artifact,
            final_prediction_artifact=prediction_artifact,
            production_manifest_path=None,
            report_path=str(self.report_path()),
            wall_seconds=perf_counter() - started,
        )

        if accepted:
            production_manifest = self._write_production_manifest(report=report)
            report = MLFinalAcceptanceReport(
                **{
                    **asdict(report),
                    "prior_metrics": prior_metrics,
                    "model_metrics": model_metrics,
                    "final_model_artifact": model_artifact,
                    "final_prediction_artifact": prediction_artifact,
                    "production_manifest_path": production_manifest,
                }
            )

        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
