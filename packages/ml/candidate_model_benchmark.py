from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable

import duckdb
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
from packages.ml.baseline_policy import (
    ML_BASELINE_LINEAR_WEIGHTED_MACRO_AUC,
    ML_BASELINE_POLICY_ACCEPTED,
    ML_BASELINE_PRIOR_WEIGHTED_BRIER,
    ML_BASELINE_PRIOR_WEIGHTED_ECE,
    ML_BASELINE_PRIOR_WEIGHTED_LOG_LOSS,
)
from packages.ml.candidate_model_probe import (
    ML_CANDIDATE_MODEL_HASH_BUCKETS,
    ML_CANDIDATE_MODEL_PROBE_CONTRACT_VERSION,
    ML_CANDIDATE_MODEL_SPECS,
    CandidateModelSpec,
)
from packages.ml.dataset_policy import (
    ML_TRAINING_DATASET_ACCEPTED_ID,
    ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
)
from packages.ml.evaluation import ProbabilityMetrics, class_indices, probability_metrics, validate_probabilities
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.label_policy import ML_PREDICTION_LABEL_PROBABILITY_FIELDS
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
    ML_WALK_FORWARD_ACCEPTED_TOTAL_TEST_ROWS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
)


ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION = (
    "ml-candidate-model-benchmark-v1-hgb-two-capacities-1m-sampled-10fold-oos"
)
ML_CANDIDATE_MODEL_BENCHMARK_STATUS = "EVIDENCE_ONLY"
ML_CANDIDATE_MODEL_BENCHMARK_TRAIN_CAP_ROWS = 1_000_000
ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES = (
    "hgb_leaf15_iter100",
    "hgb_leaf31_iter100",
)
ML_CANDIDATE_MODEL_BENCHMARK_FINAL_HOLDOUT_ACCESSED = False
ML_CANDIDATE_MODEL_BENCHMARK_FOLD_TEST_ACCESSED = True

# The 200-iteration feasibility candidate is intentionally excluded from the full
# walk-forward benchmark because Fold-1 validation showed worse log loss and Brier
# at materially higher runtime. Gate 9 tests only the two bounded capacities that
# remained defensible after the feasibility probe.
ML_CANDIDATE_MODEL_BENCHMARK_SPECS = tuple(
    spec for spec in ML_CANDIDATE_MODEL_SPECS
    if spec.name in ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES
)
if tuple(spec.name for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS) != ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES:
    raise RuntimeError("Gate 9 benchmark specs do not match the selected feasibility candidates")


@dataclass(frozen=True, slots=True)
class CandidatePredictionArtifact:
    model_name: str
    fold_index: int
    role: str
    relative_path: str
    sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class CandidateFoldEvidence:
    model_name: str
    fold_index: int
    train_start: str
    train_end: str
    full_train_rows: int
    sampled_train_rows: int
    sample_fraction: float
    validation_start: str
    validation_end: str
    validation_rows: int
    test_start: str
    test_end: str
    test_rows: int
    fit_seconds: float
    validation_predict_seconds: float
    test_predict_seconds: float
    validation_metrics: ProbabilityMetrics
    test_metrics: ProbabilityMetrics
    validation_artifact: CandidatePredictionArtifact
    test_artifact: CandidatePredictionArtifact


@dataclass(frozen=True, slots=True)
class CandidateAggregateEvidence:
    model_name: str
    folds: int
    test_rows: int
    weighted_log_loss: float
    weighted_multiclass_brier: float
    weighted_accuracy: float
    weighted_macro_ovr_auc: float | None
    weighted_macro_ece: float
    relative_log_loss_improvement_vs_prior: float
    relative_brier_improvement_vs_prior: float
    log_loss_fold_wins_vs_prior: int
    brier_fold_wins_vs_prior: int
    minimum_fold_log_loss: float
    maximum_fold_log_loss: float
    minimum_fold_brier: float
    maximum_fold_brier: float


@dataclass(frozen=True, slots=True)
class MLCandidateModelBenchmarkReport:
    contract_version: str
    generated_at_utc: str
    status: str
    dataset_id: str
    dataset_lineage_sha256: str
    walk_forward_policy_contract: str
    feasibility_probe_contract: str
    sklearn_version: str
    duckdb_version: str
    numpy_version: str
    predictor_count: int
    models: tuple[str, ...]
    model_specs: tuple[dict[str, object], ...]
    training_cap_rows: int
    fold_count: int
    total_test_rows: int
    fold_test_accessed: bool
    final_holdout_start: str
    final_holdout_accessed: bool
    prior_reference: dict[str, float]
    linear_reference: dict[str, float]
    fold_evidence: tuple[CandidateFoldEvidence, ...]
    aggregate_evidence: tuple[CandidateAggregateEvidence, ...]
    wall_seconds: float
    report_path: str


def _weighted(values: list[tuple[float, int]]) -> float:
    denominator = sum(weight for _, weight in values)
    if denominator <= 0:
        raise ValueError("weighted metric has no rows")
    return float(sum(value * weight for value, weight in values) / denominator)


class MLCandidateModelBenchmark:
    """Run the selected Gate 9 nonlinear candidates over all accepted Gate 7 folds.

    Training is bounded by a deterministic observation-key hash sample capped at one
    million rows per fold. Validation and test windows are always evaluated in full.
    Validation and test raw probabilities are persisted separately so Gate 10 can fit
    point-in-time calibrators on validation predictions and score them on test output
    without retraining the candidate model. The protected Gate 13 holdout is never read.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        if not ML_BASELINE_POLICY_ACCEPTED:
            raise RuntimeError("Gate 9 full benchmark requires accepted Gate 8 evidence")
        self.settings = settings
        self.baseline = MLBaselineBenchmark(settings)
        self.predictors = tuple(ML_PRODUCTION_CORE_FEATURE_NAMES)

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "candidate_model_benchmark" / "2026" / "2026-08-14.json"

    def prediction_root(self) -> Path:
        return self.report_path().parent / "predictions"

    @staticmethod
    def _sample_threshold(full_train_rows: int) -> int:
        fraction = min(1.0, ML_CANDIDATE_MODEL_BENCHMARK_TRAIN_CAP_ROWS / max(1, full_train_rows))
        return max(
            1,
            min(
                ML_CANDIDATE_MODEL_HASH_BUCKETS,
                int(round(fraction * ML_CANDIDATE_MODEL_HASH_BUCKETS)),
            ),
        )

    def _training_sample(self, con, fold) -> pd.DataFrame:
        columns = ", ".join(self.predictors)
        if fold.train_rows <= ML_CANDIDATE_MODEL_BENCHMARK_TRAIN_CAP_ROWS:
            predicate = "TRUE"
        else:
            threshold = self._sample_threshold(fold.train_rows)
            predicate = (
                f"(hash(observation_key) % {ML_CANDIDATE_MODEL_HASH_BUCKETS}) < {threshold}"
            )
        frame = con.execute(
            f"""
            SELECT prediction_label, {columns}
            FROM read_parquet({sql_string(self.baseline.dataset_glob)}, hive_partitioning=true)
            WHERE session_date BETWEEN DATE '{fold.train_start}' AND DATE '{fold.train_end}'
              AND {predicate}
            ORDER BY session_date, symbol, instrument_id
            """
        ).fetch_df()
        if len(frame) < min(250_000, fold.train_rows // 2):
            raise RuntimeError(f"Gate 9 fold {fold.fold_index} training sample is unexpectedly small")
        return frame

    def _xy(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = frame.loc[:, list(self.predictors)].to_numpy(dtype=np.float32, copy=True)
        y = class_indices(frame["prediction_label"].to_numpy())
        return x, y

    @staticmethod
    def _model(spec: CandidateModelSpec) -> HistGradientBoostingClassifier:
        return HistGradientBoostingClassifier(
            loss="log_loss",
            learning_rate=spec.learning_rate,
            max_iter=spec.max_iter,
            max_leaf_nodes=spec.max_leaf_nodes,
            min_samples_leaf=spec.min_samples_leaf,
            l2_regularization=spec.l2_regularization,
            max_bins=255,
            early_stopping=False,
            random_state=42,
        )

    def _write_predictions(
        self,
        *,
        model_name: str,
        fold_index: int,
        role: str,
        frame: pd.DataFrame,
        probabilities: np.ndarray,
    ) -> CandidatePredictionArtifact:
        probabilities = validate_probabilities(probabilities)
        if role not in {"validation", "test"}:
            raise ValueError(f"unsupported Gate 9 prediction role: {role}")
        if probabilities.shape != (len(frame), len(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)):
            raise ValueError("Gate 9 prediction matrix shape mismatch")

        out = frame.loc[
            :, ["observation_key", "session_date", "symbol", "instrument_id", "prediction_label"]
        ].copy()
        out = out.rename(columns={"prediction_label": "actual_label"})
        out.insert(0, "fold_index", int(fold_index))
        out.insert(1, "model_name", model_name)
        out.insert(2, "prediction_role", role)
        for index, field in enumerate(ML_PREDICTION_LABEL_PROBABILITY_FIELDS):
            out[field] = probabilities[:, index].astype(np.float32)

        target = (
            self.prediction_root()
            / f"model={model_name}"
            / f"role={role}"
            / f"fold={fold_index:02d}"
            / "part-000.parquet"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        writer = connect_utc(":memory:")
        try:
            writer.register("gate9_predictions", out)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            writer.execute(
                f"""
                COPY (
                    SELECT * FROM gate9_predictions
                    ORDER BY session_date, symbol, instrument_id
                )
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, target)
        finally:
            writer.close()

        return CandidatePredictionArtifact(
            model_name=model_name,
            fold_index=int(fold_index),
            role=role,
            relative_path=str(target.relative_to(self.report_path().parent)),
            sha256=sha256_file(target),
            row_count=int(len(out)),
        )

    @staticmethod
    def _prior_probabilities(rows: int, train_probabilities: dict[str, float]) -> np.ndarray:
        vector = np.asarray(
            [train_probabilities[label] for label in ("DOWN", "NEUTRAL", "UP")],
            dtype=np.float64,
        )
        return np.repeat(vector.reshape(1, -1), rows, axis=0)

    def _fold(
        self,
        con,
        fold,
        progress: Callable[[str], None] | None,
    ) -> tuple[list[CandidateFoldEvidence], ProbabilityMetrics]:
        training = self._training_sample(con, fold)
        sampled_rows = len(training)
        x_train, y_train = self._xy(training)
        del training

        validation = self.baseline._evaluation_frame(con, fold.validation_start, fold.validation_end)
        if len(validation) != fold.validation_rows:
            raise RuntimeError(f"Gate 9 fold {fold.fold_index} validation rows do not reconcile")
        test = self.baseline._evaluation_frame(con, fold.test_start, fold.test_end)
        if len(test) != fold.test_rows:
            raise RuntimeError(f"Gate 9 fold {fold.fold_index} test rows do not reconcile")

        x_validation, _ = self._xy(validation)
        x_test, _ = self._xy(test)
        validation_labels = validation["prediction_label"].to_numpy()
        test_labels = test["prediction_label"].to_numpy()

        train_probabilities = self.baseline._train_class_probabilities(con, fold)
        prior_test = self._prior_probabilities(len(test), train_probabilities)
        prior_test_metrics = probability_metrics(test_labels, prior_test)
        del prior_test

        if progress is not None:
            progress(
                f"fold {fold.fold_index}/{ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT}: "
                f"train_sample={sampled_rows:,}/{fold.train_rows:,} "
                f"validation={len(validation):,} test={len(test):,}"
            )

        evidence: list[CandidateFoldEvidence] = []
        for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS:
            model = self._model(spec)
            fit_started = perf_counter()
            model.fit(x_train, y_train)
            fit_seconds = perf_counter() - fit_started

            validation_started = perf_counter()
            validation_probabilities = validate_probabilities(model.predict_proba(x_validation))
            validation_predict_seconds = perf_counter() - validation_started
            validation_metrics = probability_metrics(validation_labels, validation_probabilities)

            test_started = perf_counter()
            test_probabilities = validate_probabilities(model.predict_proba(x_test))
            test_predict_seconds = perf_counter() - test_started
            test_metrics = probability_metrics(test_labels, test_probabilities)

            validation_artifact = self._write_predictions(
                model_name=spec.name,
                fold_index=fold.fold_index,
                role="validation",
                frame=validation,
                probabilities=validation_probabilities,
            )
            test_artifact = self._write_predictions(
                model_name=spec.name,
                fold_index=fold.fold_index,
                role="test",
                frame=test,
                probabilities=test_probabilities,
            )

            item = CandidateFoldEvidence(
                model_name=spec.name,
                fold_index=fold.fold_index,
                train_start=fold.train_start,
                train_end=fold.train_end,
                full_train_rows=fold.train_rows,
                sampled_train_rows=sampled_rows,
                sample_fraction=sampled_rows / fold.train_rows,
                validation_start=fold.validation_start,
                validation_end=fold.validation_end,
                validation_rows=len(validation),
                test_start=fold.test_start,
                test_end=fold.test_end,
                test_rows=len(test),
                fit_seconds=fit_seconds,
                validation_predict_seconds=validation_predict_seconds,
                test_predict_seconds=test_predict_seconds,
                validation_metrics=validation_metrics,
                test_metrics=test_metrics,
                validation_artifact=validation_artifact,
                test_artifact=test_artifact,
            )
            evidence.append(item)
            if progress is not None:
                progress(
                    f"  {spec.name}: logloss={test_metrics.log_loss:.6f} "
                    f"brier={test_metrics.multiclass_brier:.6f} "
                    f"auc={test_metrics.macro_ovr_auc:.6f} "
                    f"ece={test_metrics.macro_ece:.6f} fit={fit_seconds:.2f}s"
                )

        return evidence, prior_test_metrics

    @staticmethod
    def _aggregate(
        model_name: str,
        fold_evidence: list[CandidateFoldEvidence],
        prior_metrics: dict[int, ProbabilityMetrics],
    ) -> CandidateAggregateEvidence:
        selected = [item for item in fold_evidence if item.model_name == model_name]
        if len(selected) != ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT:
            raise RuntimeError(f"Gate 9 aggregate missing folds for {model_name}")
        auc_values = [
            (item.test_metrics.macro_ovr_auc, item.test_rows)
            for item in selected
            if item.test_metrics.macro_ovr_auc is not None
        ]
        test_rows = sum(item.test_rows for item in selected)
        log_loss = _weighted([(item.test_metrics.log_loss, item.test_rows) for item in selected])
        brier = _weighted([(item.test_metrics.multiclass_brier, item.test_rows) for item in selected])
        prior_log_loss = _weighted(
            [(prior_metrics[item.fold_index].log_loss, item.test_rows) for item in selected]
        )
        prior_brier = _weighted(
            [(prior_metrics[item.fold_index].multiclass_brier, item.test_rows) for item in selected]
        )
        return CandidateAggregateEvidence(
            model_name=model_name,
            folds=len(selected),
            test_rows=test_rows,
            weighted_log_loss=log_loss,
            weighted_multiclass_brier=brier,
            weighted_accuracy=_weighted([(item.test_metrics.accuracy, item.test_rows) for item in selected]),
            weighted_macro_ovr_auc=(
                None
                if not auc_values
                else _weighted([(float(value), rows) for value, rows in auc_values])
            ),
            weighted_macro_ece=_weighted([(item.test_metrics.macro_ece, item.test_rows) for item in selected]),
            relative_log_loss_improvement_vs_prior=(prior_log_loss - log_loss) / prior_log_loss,
            relative_brier_improvement_vs_prior=(prior_brier - brier) / prior_brier,
            log_loss_fold_wins_vs_prior=sum(
                item.test_metrics.log_loss < prior_metrics[item.fold_index].log_loss
                for item in selected
            ),
            brier_fold_wins_vs_prior=sum(
                item.test_metrics.multiclass_brier < prior_metrics[item.fold_index].multiclass_brier
                for item in selected
            ),
            minimum_fold_log_loss=min(item.test_metrics.log_loss for item in selected),
            maximum_fold_log_loss=max(item.test_metrics.log_loss for item in selected),
            minimum_fold_brier=min(item.test_metrics.multiclass_brier for item in selected),
            maximum_fold_brier=max(item.test_metrics.multiclass_brier for item in selected),
        )

    def run(
        self,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> MLCandidateModelBenchmarkReport:
        started = perf_counter()
        candidate = self.baseline._accepted_candidate()
        if candidate.fold_count != ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT:
            raise RuntimeError("Gate 9 fold count differs from accepted Gate 7 policy")
        if candidate.total_test_rows != ML_WALK_FORWARD_ACCEPTED_TOTAL_TEST_ROWS:
            raise RuntimeError("Gate 9 test rows differ from accepted Gate 7 policy")
        if any(fold.test_end >= ML_WALK_FORWARD_FINAL_HOLDOUT_START for fold in candidate.folds):
            raise RuntimeError("Gate 9 accepted fold reaches the protected Gate 13 holdout")

        con = connect_utc(":memory:")
        fold_evidence: list[CandidateFoldEvidence] = []
        prior_metrics: dict[int, ProbabilityMetrics] = {}
        try:
            for fold in candidate.folds:
                items, prior = self._fold(con, fold, progress)
                fold_evidence.extend(items)
                prior_metrics[fold.fold_index] = prior
        finally:
            con.close()

        aggregates = tuple(
            self._aggregate(model_name, fold_evidence, prior_metrics)
            for model_name in ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES
        )
        if any(item.test_rows != ML_WALK_FORWARD_ACCEPTED_TOTAL_TEST_ROWS for item in aggregates):
            raise RuntimeError("Gate 9 aggregate OOS rows do not reconcile")

        target = self.report_path()
        report = MLCandidateModelBenchmarkReport(
            contract_version=ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            status=ML_CANDIDATE_MODEL_BENCHMARK_STATUS,
            dataset_id=ML_TRAINING_DATASET_ACCEPTED_ID,
            dataset_lineage_sha256=ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
            walk_forward_policy_contract=ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
            feasibility_probe_contract=ML_CANDIDATE_MODEL_PROBE_CONTRACT_VERSION,
            sklearn_version=sklearn.__version__,
            duckdb_version=duckdb.__version__,
            numpy_version=np.__version__,
            predictor_count=len(self.predictors),
            models=ML_CANDIDATE_MODEL_BENCHMARK_MODEL_NAMES,
            model_specs=tuple(asdict(spec) for spec in ML_CANDIDATE_MODEL_BENCHMARK_SPECS),
            training_cap_rows=ML_CANDIDATE_MODEL_BENCHMARK_TRAIN_CAP_ROWS,
            fold_count=candidate.fold_count,
            total_test_rows=candidate.total_test_rows,
            fold_test_accessed=ML_CANDIDATE_MODEL_BENCHMARK_FOLD_TEST_ACCESSED,
            final_holdout_start=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            final_holdout_accessed=ML_CANDIDATE_MODEL_BENCHMARK_FINAL_HOLDOUT_ACCESSED,
            prior_reference={
                "weighted_log_loss": ML_BASELINE_PRIOR_WEIGHTED_LOG_LOSS,
                "weighted_multiclass_brier": ML_BASELINE_PRIOR_WEIGHTED_BRIER,
                "weighted_ece": ML_BASELINE_PRIOR_WEIGHTED_ECE,
            },
            linear_reference={
                "weighted_macro_ovr_auc": ML_BASELINE_LINEAR_WEIGHTED_MACRO_AUC,
            },
            fold_evidence=tuple(fold_evidence),
            aggregate_evidence=aggregates,
            wall_seconds=perf_counter() - started,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
