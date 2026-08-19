from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import duckdb
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import SGDClassifier

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.dataset_policy import (
    ML_TRAINING_DATASET_ACCEPTED_ID,
    ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
)
from packages.ml.evaluation import (
    ML_PROBABILITY_EVALUATION_CONTRACT_VERSION,
    ProbabilityMetrics,
    class_indices,
    probability_metrics,
)
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.label_policy import (
    ML_PREDICTION_LABEL_CLASSES,
    ML_PREDICTION_LABEL_PROBABILITY_FIELDS,
)
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_CANDIDATE,
    ML_WALK_FORWARD_ACCEPTED_DISTINCT_TEST_SESSIONS,
    ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
    ML_WALK_FORWARD_ACCEPTED_TOTAL_TEST_ROWS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
)
from packages.ml.walk_forward_probe import (
    ML_WALK_FORWARD_CANDIDATE_SPECS,
    MLWalkForwardProbe,
    WalkForwardCandidateEvidence,
    WalkForwardFoldEvidence,
)


ML_BASELINE_BENCHMARK_CONTRACT_VERSION = (
    "ml-baseline-benchmark-v1-train-prior-sgd-l2-streaming-oos"
)
ML_BASELINE_BENCHMARK_STATUS = "EVIDENCE_ONLY"
ML_BASELINE_PRIOR_MODEL = "train_class_prior"
ML_BASELINE_LINEAR_MODEL = "sgd_logistic_l2"
ML_BASELINE_MODELS = (ML_BASELINE_PRIOR_MODEL, ML_BASELINE_LINEAR_MODEL)

# Gate 8 deliberately fixes one scalable linear baseline rather than searching a grid.
# Validation metrics are diagnostic only. Hyperparameter family selection belongs to Gate 9.
ML_BASELINE_LINEAR_LOSS = "log_loss"
ML_BASELINE_LINEAR_PENALTY = "l2"
ML_BASELINE_LINEAR_ALPHA = 1e-4
ML_BASELINE_LINEAR_LEARNING_RATE = "optimal"
ML_BASELINE_LINEAR_AVERAGE = True
ML_BASELINE_LINEAR_RANDOM_STATE = 42
ML_BASELINE_LINEAR_TRAINING_EPOCHS = 1
ML_BASELINE_LINEAR_CHUNK_SESSIONS = 21
ML_BASELINE_LINEAR_CLASS_WEIGHT = None
ML_BASELINE_LINEAR_RESAMPLING = "NONE"
ML_BASELINE_LINEAR_FEATURE_SCALING = "TRAIN_ONLY_MEAN_STD"
ML_BASELINE_FINAL_HOLDOUT_ACCESSED = False


@dataclass(frozen=True, slots=True)
class BaselinePredictionArtifact:
    model_name: str
    fold_index: int
    relative_path: str
    sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class BaselineModelFoldEvidence:
    model_name: str
    fold_index: int
    train_start: str
    train_end: str
    train_rows: int
    validation_start: str
    validation_end: str
    validation_rows: int
    test_start: str
    test_end: str
    test_rows: int
    train_class_probabilities: dict[str, float]
    validation_metrics: ProbabilityMetrics
    test_metrics: ProbabilityMetrics
    fit_seconds: float
    validation_predict_seconds: float
    test_predict_seconds: float
    zero_scale_feature_count: int
    prediction_artifact: BaselinePredictionArtifact


@dataclass(frozen=True, slots=True)
class BaselineAggregateEvidence:
    model_name: str
    folds: int
    test_rows: int
    weighted_log_loss: float
    weighted_multiclass_brier: float
    weighted_accuracy: float
    weighted_macro_ovr_auc: float | None
    weighted_macro_ece: float
    minimum_fold_log_loss: float
    maximum_fold_log_loss: float
    minimum_fold_brier: float
    maximum_fold_brier: float


@dataclass(frozen=True, slots=True)
class BaselineComparisonEvidence:
    linear_minus_prior_log_loss: float
    linear_minus_prior_brier: float
    relative_log_loss_improvement: float
    relative_brier_improvement: float
    linear_log_loss_fold_wins: int
    linear_brier_fold_wins: int


@dataclass(frozen=True, slots=True)
class MLBaselineBenchmarkReport:
    contract_version: str
    generated_at_utc: str
    status: str
    dataset_id: str
    dataset_lineage_sha256: str
    walk_forward_policy_contract: str
    walk_forward_candidate: str
    probability_evaluation_contract: str
    sklearn_version: str
    duckdb_version: str
    numpy_version: str
    predictor_count: int
    class_order: tuple[str, ...]
    probability_fields: tuple[str, ...]
    models: tuple[str, ...]
    linear_model_spec: dict[str, object]
    final_holdout_start: str
    final_holdout_accessed: bool
    fold_evidence: tuple[BaselineModelFoldEvidence, ...]
    aggregate_evidence: tuple[BaselineAggregateEvidence, ...]
    comparison: BaselineComparisonEvidence
    wall_seconds: float
    report_path: str


def _weighted(values: list[tuple[float, int]]) -> float:
    denominator = sum(weight for _, weight in values)
    if denominator <= 0:
        raise ValueError("weighted metric has no rows")
    return float(sum(value * weight for value, weight in values) / denominator)


def _aggregate(model_name: str, folds: list[BaselineModelFoldEvidence]) -> BaselineAggregateEvidence:
    selected = [item for item in folds if item.model_name == model_name]
    if not selected:
        raise ValueError(f"missing Gate 8 evidence for {model_name}")
    auc_values = [
        (item.test_metrics.macro_ovr_auc, item.test_rows)
        for item in selected
        if item.test_metrics.macro_ovr_auc is not None
    ]
    return BaselineAggregateEvidence(
        model_name=model_name,
        folds=len(selected),
        test_rows=sum(item.test_rows for item in selected),
        weighted_log_loss=_weighted([(item.test_metrics.log_loss, item.test_rows) for item in selected]),
        weighted_multiclass_brier=_weighted(
            [(item.test_metrics.multiclass_brier, item.test_rows) for item in selected]
        ),
        weighted_accuracy=_weighted([(item.test_metrics.accuracy, item.test_rows) for item in selected]),
        weighted_macro_ovr_auc=(None if not auc_values else _weighted([(float(value), rows) for value, rows in auc_values])),
        weighted_macro_ece=_weighted([(item.test_metrics.macro_ece, item.test_rows) for item in selected]),
        minimum_fold_log_loss=min(item.test_metrics.log_loss for item in selected),
        maximum_fold_log_loss=max(item.test_metrics.log_loss for item in selected),
        minimum_fold_brier=min(item.test_metrics.multiclass_brier for item in selected),
        maximum_fold_brier=max(item.test_metrics.multiclass_brier for item in selected),
    )


class MLBaselineBenchmark:
    """Run Gate 8 simple probability baselines on the accepted Gate 7 OOS folds.

    The final Gate 13 holdout is never queried. The empirical baseline uses only each
    fold's training class prevalence. The linear baseline uses the same full training
    rows, train-only standardization, one deterministic out-of-core SGD pass, natural
    class prevalence, and no resampling or class weighting.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.walk_forward = MLWalkForwardProbe(settings)
        self.dataset_root = self.walk_forward.dataset_root()
        self.dataset_glob = (self.dataset_root / "year=*" / "*.parquet").as_posix()
        self.predictors = tuple(ML_PRODUCTION_CORE_FEATURE_NAMES)
        self.class_order = tuple(ML_PREDICTION_LABEL_CLASSES)
        self.class_values = np.arange(len(self.class_order), dtype=np.int8)

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "baseline_benchmark" / "2026" / "2026-08-14.json"

    def prediction_root(self) -> Path:
        return self.report_path().parent / "predictions"

    def _accepted_candidate(self) -> WalkForwardCandidateEvidence:
        manifest = self.walk_forward._load_manifest(self.dataset_root)
        if manifest.dataset_id != ML_TRAINING_DATASET_ACCEPTED_ID:
            raise ValueError("Gate 8 dataset id is not the accepted Gate 6 dataset")
        if manifest.dataset_lineage_fingerprint != ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256:
            raise ValueError("Gate 8 dataset lineage is not accepted")
        sessions = self.walk_forward._session_evidence(self.dataset_root)
        spec = next(
            item for item in ML_WALK_FORWARD_CANDIDATE_SPECS
            if item.name == ML_WALK_FORWARD_ACCEPTED_CANDIDATE
        )
        candidate = self.walk_forward._candidate_evidence(sessions, spec)
        if candidate.fold_count != ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT:
            raise ValueError("Gate 8 reconstructed fold count differs from Gate 7")
        if candidate.distinct_test_sessions != ML_WALK_FORWARD_ACCEPTED_DISTINCT_TEST_SESSIONS:
            raise ValueError("Gate 8 reconstructed OOS sessions differ from Gate 7")
        if candidate.total_test_rows != ML_WALK_FORWARD_ACCEPTED_TOTAL_TEST_ROWS:
            raise ValueError("Gate 8 reconstructed OOS rows differ from Gate 7")
        if any(fold.test_end >= ML_WALK_FORWARD_FINAL_HOLDOUT_START for fold in candidate.folds):
            raise ValueError("Gate 8 fold schedule reaches the protected Gate 13 holdout")
        return candidate

    def _train_class_probabilities(self, con: Any, fold: WalkForwardFoldEvidence) -> dict[str, float]:
        row = con.execute(
            f"""
            SELECT
                count(*) AS rows,
                count(*) FILTER (WHERE prediction_label = 'DOWN') AS down_rows,
                count(*) FILTER (WHERE prediction_label = 'NEUTRAL') AS neutral_rows,
                count(*) FILTER (WHERE prediction_label = 'UP') AS up_rows
            FROM read_parquet({sql_string(self.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{fold.train_start}' AND DATE '{fold.train_end}'
            """
        ).fetchone()
        rows = int(row[0])
        if rows != fold.train_rows:
            raise RuntimeError(
                f"Gate 8 fold {fold.fold_index} train rows do not reconcile: {rows:,} != {fold.train_rows:,}"
            )
        counts = [int(row[1]), int(row[2]), int(row[3])]
        return {
            label: count / rows
            for label, count in zip(self.class_order, counts, strict=True)
        }

    def _feature_stats(self, con: Any, fold: WalkForwardFoldEvidence) -> tuple[np.ndarray, np.ndarray, int]:
        avg_sql = ", ".join(f"avg(CAST({name} AS DOUBLE))" for name in self.predictors)
        std_sql = ", ".join(f"stddev_pop(CAST({name} AS DOUBLE))" for name in self.predictors)
        row = con.execute(
            f"""
            SELECT {avg_sql}, {std_sql}
            FROM read_parquet({sql_string(self.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{fold.train_start}' AND DATE '{fold.train_end}'
            """
        ).fetchone()
        count = len(self.predictors)
        means = np.asarray(row[:count], dtype=np.float64)
        scales = np.asarray(row[count:], dtype=np.float64)
        if not bool(np.isfinite(means).all()) or not bool(np.isfinite(scales).all()):
            raise RuntimeError("Gate 8 train-only scaling produced non-finite statistics")
        zero = scales <= np.finfo(np.float64).eps
        zero_count = int(zero.sum())
        scales[zero] = 1.0
        return means, scales, zero_count

    def _all_session_dates(self, con: Any) -> list[str]:
        rows = con.execute(
            f"""
            SELECT DISTINCT CAST(session_date AS VARCHAR)
            FROM read_parquet({sql_string(self.dataset_glob)}, hive_partitioning=true)
            ORDER BY 1
            """
        ).fetchall()
        return [str(row[0]) for row in rows]

    @staticmethod
    def _date_chunks(
        all_sessions: list[str],
        *,
        start: str,
        end: str,
        chunk_sessions: int,
    ) -> list[tuple[str, str]]:
        selected = [session for session in all_sessions if start <= session <= end]
        if not selected:
            raise ValueError(f"no dataset sessions in requested range {start} -> {end}")
        return [
            (selected[index], selected[min(index + chunk_sessions - 1, len(selected) - 1)])
            for index in range(0, len(selected), chunk_sessions)
        ]

    def _training_frame(self, con: Any, start: str, end: str) -> pd.DataFrame:
        columns = ", ".join(self.predictors)
        return con.execute(
            f"""
            SELECT prediction_label, {columns}
            FROM read_parquet({sql_string(self.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{start}' AND DATE '{end}'
            ORDER BY session_date, symbol, instrument_id
            """
        ).fetch_df()

    def _evaluation_frame(self, con: Any, start: str, end: str) -> pd.DataFrame:
        columns = ", ".join(self.predictors)
        return con.execute(
            f"""
            SELECT observation_key, session_date, symbol, instrument_id, prediction_label, {columns}
            FROM read_parquet({sql_string(self.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{start}' AND DATE '{end}'
            ORDER BY session_date, symbol, instrument_id
            """
        ).fetch_df()

    def _scaled_xy(
        self,
        frame: pd.DataFrame,
        means: np.ndarray,
        scales: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        x = frame.loc[:, list(self.predictors)].to_numpy(dtype=np.float32, copy=True)
        x -= means.astype(np.float32)
        x /= scales.astype(np.float32)
        y = class_indices(frame["prediction_label"].to_numpy())
        return x, y

    def _fit_linear(
        self,
        con: Any,
        fold: WalkForwardFoldEvidence,
        all_sessions: list[str],
        means: np.ndarray,
        scales: np.ndarray,
    ) -> tuple[SGDClassifier, float]:
        model = SGDClassifier(
            loss=ML_BASELINE_LINEAR_LOSS,
            penalty=ML_BASELINE_LINEAR_PENALTY,
            alpha=ML_BASELINE_LINEAR_ALPHA,
            fit_intercept=True,
            shuffle=True,
            random_state=ML_BASELINE_LINEAR_RANDOM_STATE,
            learning_rate=ML_BASELINE_LINEAR_LEARNING_RATE,
            average=ML_BASELINE_LINEAR_AVERAGE,
            class_weight=ML_BASELINE_LINEAR_CLASS_WEIGHT,
            tol=None,
        )
        chunks = self._date_chunks(
            all_sessions,
            start=fold.train_start,
            end=fold.train_end,
            chunk_sessions=ML_BASELINE_LINEAR_CHUNK_SESSIONS,
        )
        started = perf_counter()
        fitted = False
        for _ in range(ML_BASELINE_LINEAR_TRAINING_EPOCHS):
            for chunk_start, chunk_end in chunks:
                frame = self._training_frame(con, chunk_start, chunk_end)
                x, y = self._scaled_xy(frame, means, scales)
                if not fitted:
                    model.partial_fit(x, y, classes=self.class_values)
                    fitted = True
                else:
                    model.partial_fit(x, y)
        if not fitted:
            raise RuntimeError("Gate 8 linear baseline received no training rows")
        if tuple(int(value) for value in model.classes_) != tuple(int(value) for value in self.class_values):
            raise RuntimeError("Gate 8 linear model class order differs from the locked label order")
        return model, perf_counter() - started

    @staticmethod
    def _prior_probabilities(rows: int, train_probabilities: dict[str, float]) -> np.ndarray:
        vector = np.asarray(
            [train_probabilities[label] for label in ML_PREDICTION_LABEL_CLASSES],
            dtype=np.float64,
        )
        return np.repeat(vector.reshape(1, -1), int(rows), axis=0)

    def _linear_probabilities(
        self,
        model: SGDClassifier,
        frame: pd.DataFrame,
        means: np.ndarray,
        scales: np.ndarray,
    ) -> np.ndarray:
        x, _ = self._scaled_xy(frame, means, scales)
        return np.asarray(model.predict_proba(x), dtype=np.float64)

    def _write_predictions(
        self,
        *,
        model_name: str,
        fold_index: int,
        frame: pd.DataFrame,
        probabilities: np.ndarray,
    ) -> BaselinePredictionArtifact:
        if probabilities.shape != (len(frame), len(self.class_order)):
            raise ValueError("Gate 8 prediction matrix shape mismatch")
        out = frame.loc[:, ["observation_key", "session_date", "symbol", "instrument_id", "prediction_label"]].copy()
        out = out.rename(columns={"prediction_label": "actual_label"})
        out.insert(0, "fold_index", int(fold_index))
        out.insert(1, "model_name", model_name)
        for index, field in enumerate(ML_PREDICTION_LABEL_PROBABILITY_FIELDS):
            out[field] = probabilities[:, index].astype(np.float32)

        target = (
            self.prediction_root()
            / f"model={model_name}"
            / f"fold={fold_index:02d}"
            / "part-000.parquet"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        con = connect_utc(":memory:")
        try:
            con.register("gate8_predictions", out)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (
                    SELECT * FROM gate8_predictions
                    ORDER BY session_date, symbol, instrument_id
                )
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, target)
        finally:
            con.close()
        return BaselinePredictionArtifact(
            model_name=model_name,
            fold_index=int(fold_index),
            relative_path=str(target.relative_to(self.report_path().parent)),
            sha256=sha256_file(target),
            row_count=int(len(out)),
        )

    def _fold(
        self,
        con: Any,
        fold: WalkForwardFoldEvidence,
        all_sessions: list[str],
    ) -> list[BaselineModelFoldEvidence]:
        train_probabilities = self._train_class_probabilities(con, fold)
        means, scales, zero_count = self._feature_stats(con, fold)
        linear_model, fit_seconds = self._fit_linear(con, fold, all_sessions, means, scales)

        validation = self._evaluation_frame(con, fold.validation_start, fold.validation_end)
        if len(validation) != fold.validation_rows:
            raise RuntimeError(f"Gate 8 fold {fold.fold_index} validation rows do not reconcile")
        test = self._evaluation_frame(con, fold.test_start, fold.test_end)
        if len(test) != fold.test_rows:
            raise RuntimeError(f"Gate 8 fold {fold.fold_index} test rows do not reconcile")

        labels_val = validation["prediction_label"].to_numpy()
        labels_test = test["prediction_label"].to_numpy()

        prior_val_started = perf_counter()
        prior_val = self._prior_probabilities(len(validation), train_probabilities)
        prior_val_seconds = perf_counter() - prior_val_started
        prior_test_started = perf_counter()
        prior_test = self._prior_probabilities(len(test), train_probabilities)
        prior_test_seconds = perf_counter() - prior_test_started

        linear_val_started = perf_counter()
        linear_val = self._linear_probabilities(linear_model, validation, means, scales)
        linear_val_seconds = perf_counter() - linear_val_started
        linear_test_started = perf_counter()
        linear_test = self._linear_probabilities(linear_model, test, means, scales)
        linear_test_seconds = perf_counter() - linear_test_started

        prior_artifact = self._write_predictions(
            model_name=ML_BASELINE_PRIOR_MODEL,
            fold_index=fold.fold_index,
            frame=test,
            probabilities=prior_test,
        )
        linear_artifact = self._write_predictions(
            model_name=ML_BASELINE_LINEAR_MODEL,
            fold_index=fold.fold_index,
            frame=test,
            probabilities=linear_test,
        )

        return [
            BaselineModelFoldEvidence(
                model_name=ML_BASELINE_PRIOR_MODEL,
                fold_index=fold.fold_index,
                train_start=fold.train_start,
                train_end=fold.train_end,
                train_rows=fold.train_rows,
                validation_start=fold.validation_start,
                validation_end=fold.validation_end,
                validation_rows=fold.validation_rows,
                test_start=fold.test_start,
                test_end=fold.test_end,
                test_rows=fold.test_rows,
                train_class_probabilities=train_probabilities,
                validation_metrics=probability_metrics(labels_val, prior_val),
                test_metrics=probability_metrics(labels_test, prior_test),
                fit_seconds=0.0,
                validation_predict_seconds=prior_val_seconds,
                test_predict_seconds=prior_test_seconds,
                zero_scale_feature_count=0,
                prediction_artifact=prior_artifact,
            ),
            BaselineModelFoldEvidence(
                model_name=ML_BASELINE_LINEAR_MODEL,
                fold_index=fold.fold_index,
                train_start=fold.train_start,
                train_end=fold.train_end,
                train_rows=fold.train_rows,
                validation_start=fold.validation_start,
                validation_end=fold.validation_end,
                validation_rows=fold.validation_rows,
                test_start=fold.test_start,
                test_end=fold.test_end,
                test_rows=fold.test_rows,
                train_class_probabilities=train_probabilities,
                validation_metrics=probability_metrics(labels_val, linear_val),
                test_metrics=probability_metrics(labels_test, linear_test),
                fit_seconds=fit_seconds,
                validation_predict_seconds=linear_val_seconds,
                test_predict_seconds=linear_test_seconds,
                zero_scale_feature_count=zero_count,
                prediction_artifact=linear_artifact,
            ),
        ]

    def run(self) -> MLBaselineBenchmarkReport:
        started = perf_counter()
        candidate = self._accepted_candidate()
        con = connect_utc(":memory:")
        try:
            all_sessions = self._all_session_dates(con)
            evidence: list[BaselineModelFoldEvidence] = []
            for fold in candidate.folds:
                evidence.extend(self._fold(con, fold, all_sessions))
        finally:
            con.close()

        prior = _aggregate(ML_BASELINE_PRIOR_MODEL, evidence)
        linear = _aggregate(ML_BASELINE_LINEAR_MODEL, evidence)
        prior_folds = {item.fold_index: item for item in evidence if item.model_name == ML_BASELINE_PRIOR_MODEL}
        linear_folds = {item.fold_index: item for item in evidence if item.model_name == ML_BASELINE_LINEAR_MODEL}
        comparison = BaselineComparisonEvidence(
            linear_minus_prior_log_loss=linear.weighted_log_loss - prior.weighted_log_loss,
            linear_minus_prior_brier=linear.weighted_multiclass_brier - prior.weighted_multiclass_brier,
            relative_log_loss_improvement=(prior.weighted_log_loss - linear.weighted_log_loss) / prior.weighted_log_loss,
            relative_brier_improvement=(prior.weighted_multiclass_brier - linear.weighted_multiclass_brier) / prior.weighted_multiclass_brier,
            linear_log_loss_fold_wins=sum(
                linear_folds[index].test_metrics.log_loss < prior_folds[index].test_metrics.log_loss
                for index in prior_folds
            ),
            linear_brier_fold_wins=sum(
                linear_folds[index].test_metrics.multiclass_brier < prior_folds[index].test_metrics.multiclass_brier
                for index in prior_folds
            ),
        )

        target = self.report_path()
        report = MLBaselineBenchmarkReport(
            contract_version=ML_BASELINE_BENCHMARK_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            status=ML_BASELINE_BENCHMARK_STATUS,
            dataset_id=ML_TRAINING_DATASET_ACCEPTED_ID,
            dataset_lineage_sha256=ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
            walk_forward_policy_contract=ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
            walk_forward_candidate=ML_WALK_FORWARD_ACCEPTED_CANDIDATE,
            probability_evaluation_contract=ML_PROBABILITY_EVALUATION_CONTRACT_VERSION,
            sklearn_version=sklearn.__version__,
            duckdb_version=duckdb.__version__,
            numpy_version=np.__version__,
            predictor_count=len(self.predictors),
            class_order=self.class_order,
            probability_fields=tuple(ML_PREDICTION_LABEL_PROBABILITY_FIELDS),
            models=ML_BASELINE_MODELS,
            linear_model_spec={
                "loss": ML_BASELINE_LINEAR_LOSS,
                "penalty": ML_BASELINE_LINEAR_PENALTY,
                "alpha": ML_BASELINE_LINEAR_ALPHA,
                "learning_rate": ML_BASELINE_LINEAR_LEARNING_RATE,
                "average": ML_BASELINE_LINEAR_AVERAGE,
                "random_state": ML_BASELINE_LINEAR_RANDOM_STATE,
                "epochs": ML_BASELINE_LINEAR_TRAINING_EPOCHS,
                "chunk_sessions": ML_BASELINE_LINEAR_CHUNK_SESSIONS,
                "class_weight": ML_BASELINE_LINEAR_CLASS_WEIGHT,
                "resampling": ML_BASELINE_LINEAR_RESAMPLING,
                "feature_scaling": ML_BASELINE_LINEAR_FEATURE_SCALING,
            },
            final_holdout_start=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            final_holdout_accessed=ML_BASELINE_FINAL_HOLDOUT_ACCESSED,
            fold_evidence=tuple(evidence),
            aggregate_evidence=(prior, linear),
            comparison=comparison,
            wall_seconds=perf_counter() - started,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
