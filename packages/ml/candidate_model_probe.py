from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.ml.baseline_benchmark import MLBaselineBenchmark
from packages.ml.baseline_policy import ML_BASELINE_POLICY_ACCEPTED
from packages.ml.evaluation import ProbabilityMetrics, class_indices, probability_metrics, validate_probabilities
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START


ML_CANDIDATE_MODEL_PROBE_CONTRACT_VERSION = (
    "ml-candidate-model-probe-v1-hgb-fold1-train-validation-sampled"
)
ML_CANDIDATE_MODEL_PROBE_STATUS = "EVIDENCE_ONLY"
ML_CANDIDATE_MODEL_FAMILY = "sklearn_hist_gradient_boosting"
ML_CANDIDATE_MODEL_PROBE_FOLD = 1
ML_CANDIDATE_MODEL_TRAIN_SAMPLE_TARGET = 500_000
ML_CANDIDATE_MODEL_HASH_BUCKETS = 1_000_000
ML_CANDIDATE_MODEL_RANDOM_STATE = 42
ML_CANDIDATE_MODEL_TEST_ACCESSED = False
ML_CANDIDATE_MODEL_FINAL_HOLDOUT_ACCESSED = False


@dataclass(frozen=True, slots=True)
class CandidateModelSpec:
    name: str
    max_leaf_nodes: int
    max_iter: int
    learning_rate: float
    min_samples_leaf: int
    l2_regularization: float


ML_CANDIDATE_MODEL_SPECS = (
    CandidateModelSpec(
        name="hgb_leaf15_iter100",
        max_leaf_nodes=15,
        max_iter=100,
        learning_rate=0.05,
        min_samples_leaf=100,
        l2_regularization=1.0,
    ),
    CandidateModelSpec(
        name="hgb_leaf31_iter100",
        max_leaf_nodes=31,
        max_iter=100,
        learning_rate=0.05,
        min_samples_leaf=100,
        l2_regularization=1.0,
    ),
    CandidateModelSpec(
        name="hgb_leaf31_iter200",
        max_leaf_nodes=31,
        max_iter=200,
        learning_rate=0.05,
        min_samples_leaf=100,
        l2_regularization=1.0,
    ),
)


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    name: str
    training_rows: int
    validation_rows: int
    fit_seconds: float
    predict_seconds: float
    validation_metrics: ProbabilityMetrics


@dataclass(frozen=True, slots=True)
class MLCandidateModelProbeReport:
    contract_version: str
    generated_at_utc: str
    status: str
    sklearn_version: str
    dataset_id: str
    fold_index: int
    train_start: str
    train_end: str
    full_train_rows: int
    sampled_train_rows: int
    sample_target_rows: int
    validation_start: str
    validation_end: str
    validation_rows: int
    prior_validation_metrics: ProbabilityMetrics
    candidates: tuple[CandidateEvidence, ...]
    test_accessed: bool
    final_holdout_start: str
    final_holdout_accessed: bool
    wall_seconds: float
    report_path: str


class MLCandidateModelProbe:
    """Bounded Gate 9 nonlinear feasibility probe using training + validation only.

    The probe deliberately does not query the fold test window or the protected Gate 13
    holdout. It uses a deterministic hash sample from Fold 1 training rows so model
    family capacity/runtime can be assessed before any full 10-fold candidate benchmark.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        if not ML_BASELINE_POLICY_ACCEPTED:
            raise RuntimeError("Gate 9 requires accepted Gate 8 baseline evidence")
        self.settings = settings
        self.baseline = MLBaselineBenchmark(settings)
        self.predictors = tuple(ML_PRODUCTION_CORE_FEATURE_NAMES)

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "candidate_model_probe" / "2026" / "2026-08-14.json"

    def _fold(self):
        candidate = self.baseline._accepted_candidate()
        fold = next(item for item in candidate.folds if item.fold_index == ML_CANDIDATE_MODEL_PROBE_FOLD)
        if fold.test_start >= ML_WALK_FORWARD_FINAL_HOLDOUT_START:
            raise RuntimeError("Gate 9 probe fold reaches protected final holdout")
        return fold

    def _sample_threshold(self, full_train_rows: int) -> int:
        fraction = min(1.0, ML_CANDIDATE_MODEL_TRAIN_SAMPLE_TARGET / max(1, full_train_rows))
        return max(1, min(ML_CANDIDATE_MODEL_HASH_BUCKETS, int(round(fraction * ML_CANDIDATE_MODEL_HASH_BUCKETS))))

    def _training_sample(self, con, fold):
        columns = ", ".join(self.predictors)
        threshold = self._sample_threshold(fold.train_rows)
        frame = con.execute(
            f"""
            SELECT prediction_label, {columns}
            FROM read_parquet({sql_string(self.baseline.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{fold.train_start}' AND DATE '{fold.train_end}'
              AND (hash(observation_key) % {ML_CANDIDATE_MODEL_HASH_BUCKETS}) < {threshold}
            ORDER BY session_date, symbol, instrument_id
            """
        ).fetch_df()
        if len(frame) < min(100_000, ML_CANDIDATE_MODEL_TRAIN_SAMPLE_TARGET // 2):
            raise RuntimeError("Gate 9 deterministic training sample is unexpectedly small")
        return frame

    def _xy(self, frame):
        x = frame.loc[:, list(self.predictors)].to_numpy(dtype=np.float32, copy=True)
        y = class_indices(frame["prediction_label"].to_numpy())
        return x, y

    @staticmethod
    def _prior_probabilities(rows: int, train_probabilities: dict[str, float]) -> np.ndarray:
        vector = np.asarray(
            [train_probabilities[label] for label in ("DOWN", "NEUTRAL", "UP")],
            dtype=np.float64,
        )
        return np.repeat(vector.reshape(1, -1), rows, axis=0)

    def run(self) -> MLCandidateModelProbeReport:
        started = perf_counter()
        fold = self._fold()
        con = connect_utc(":memory:")
        try:
            training = self._training_sample(con, fold)
            validation = self.baseline._evaluation_frame(con, fold.validation_start, fold.validation_end)
            train_probs = self.baseline._train_class_probabilities(con, fold)
        finally:
            con.close()

        x_train, y_train = self._xy(training)
        x_validation, y_validation = self._xy(validation)
        prior = self._prior_probabilities(len(validation), train_probs)
        prior_metrics = probability_metrics(validation["prediction_label"].to_numpy(), prior)

        evidence: list[CandidateEvidence] = []
        for spec in ML_CANDIDATE_MODEL_SPECS:
            model = HistGradientBoostingClassifier(
                loss="log_loss",
                learning_rate=spec.learning_rate,
                max_iter=spec.max_iter,
                max_leaf_nodes=spec.max_leaf_nodes,
                min_samples_leaf=spec.min_samples_leaf,
                l2_regularization=spec.l2_regularization,
                max_bins=255,
                early_stopping=False,
                random_state=ML_CANDIDATE_MODEL_RANDOM_STATE,
            )
            fit_started = perf_counter()
            model.fit(x_train, y_train)
            fit_seconds = perf_counter() - fit_started

            predict_started = perf_counter()
            probabilities = validate_probabilities(model.predict_proba(x_validation))
            predict_seconds = perf_counter() - predict_started
            metrics = probability_metrics(validation["prediction_label"].to_numpy(), probabilities)
            evidence.append(
                CandidateEvidence(
                    name=spec.name,
                    training_rows=len(training),
                    validation_rows=len(validation),
                    fit_seconds=fit_seconds,
                    predict_seconds=predict_seconds,
                    validation_metrics=metrics,
                )
            )

        report = MLCandidateModelProbeReport(
            contract_version=ML_CANDIDATE_MODEL_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            status=ML_CANDIDATE_MODEL_PROBE_STATUS,
            sklearn_version=sklearn.__version__,
            dataset_id=self.baseline.walk_forward._load_manifest(self.baseline.dataset_root).dataset_id,
            fold_index=fold.fold_index,
            train_start=fold.train_start,
            train_end=fold.train_end,
            full_train_rows=fold.train_rows,
            sampled_train_rows=len(training),
            sample_target_rows=ML_CANDIDATE_MODEL_TRAIN_SAMPLE_TARGET,
            validation_start=fold.validation_start,
            validation_end=fold.validation_end,
            validation_rows=len(validation),
            prior_validation_metrics=prior_metrics,
            candidates=tuple(evidence),
            test_accessed=ML_CANDIDATE_MODEL_TEST_ACCESSED,
            final_holdout_start=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            final_holdout_accessed=ML_CANDIDATE_MODEL_FINAL_HOLDOUT_ACCESSED,
            wall_seconds=perf_counter() - started,
            report_path=str(self.report_path()),
        )
        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
