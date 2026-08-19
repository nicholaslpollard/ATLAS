from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import duckdb
import numpy as np
import sklearn
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.candidate_model_benchmark import (
    ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION,
    MLCandidateModelBenchmark,
)
from packages.ml.candidate_model_policy import (
    ML_CANDIDATE_MODEL_ACCEPTED_FOLDS,
    ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
    ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS,
    ML_CANDIDATE_MODEL_FINAL_HOLDOUT_ACCESSED,
    ML_CANDIDATE_MODEL_POLICY_ACCEPTED,
    ML_CANDIDATE_MODEL_POLICY_CONTRACT_VERSION,
)
from packages.ml.evaluation import ProbabilityMetrics, class_indices, probability_metrics, validate_probabilities
from packages.ml.label_policy import ML_PREDICTION_LABEL_CLASSES, ML_PREDICTION_LABEL_PROBABILITY_FIELDS
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START


ML_CALIBRATION_BENCHMARK_CONTRACT_VERSION = (
    "ml-calibration-benchmark-v1-raw-platt-isotonic-validation-fit-test-score"
)
ML_CALIBRATION_BENCHMARK_STATUS = "EVIDENCE_ONLY"
ML_CALIBRATION_METHODS = ("raw", "ovr_platt", "ovr_isotonic")
ML_CALIBRATION_PLATT_C = 1_000_000.0
ML_CALIBRATION_PLATT_MAX_ITER = 200
ML_CALIBRATION_EPSILON = 1e-8
ML_CALIBRATION_VALIDATION_ONLY_FIT = True
ML_CALIBRATION_TEST_ONLY_SCORE = True
ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED = False


@dataclass(frozen=True, slots=True)
class CalibrationPredictionArtifact:
    method: str
    fold_index: int
    relative_path: str
    sha256: str
    row_count: int


@dataclass(frozen=True, slots=True)
class CalibrationFoldEvidence:
    method: str
    fold_index: int
    validation_rows: int
    test_rows: int
    fit_seconds: float
    predict_seconds: float
    test_metrics: ProbabilityMetrics
    platt_coefficients: tuple[float, ...] | None
    platt_intercepts: tuple[float, ...] | None
    isotonic_knot_counts: tuple[int, ...] | None
    prediction_artifact: CalibrationPredictionArtifact


@dataclass(frozen=True, slots=True)
class CalibrationAggregateEvidence:
    method: str
    folds: int
    test_rows: int
    weighted_log_loss: float
    weighted_multiclass_brier: float
    weighted_accuracy: float
    weighted_macro_ovr_auc: float | None
    weighted_macro_ece: float
    relative_log_loss_improvement_vs_raw: float
    relative_brier_improvement_vs_raw: float
    log_loss_fold_wins_vs_raw: int
    brier_fold_wins_vs_raw: int


@dataclass(frozen=True, slots=True)
class MLCalibrationBenchmarkReport:
    contract_version: str
    generated_at_utc: str
    status: str
    candidate_policy_contract: str
    gate9_benchmark_contract: str
    accepted_model: str
    sklearn_version: str
    duckdb_version: str
    numpy_version: str
    methods: tuple[str, ...]
    validation_only_fit: bool
    test_only_score: bool
    fold_count: int
    total_test_rows: int
    final_holdout_start: str
    final_holdout_accessed: bool
    fold_evidence: tuple[CalibrationFoldEvidence, ...]
    aggregate_evidence: tuple[CalibrationAggregateEvidence, ...]
    wall_seconds: float
    report_path: str


def _weighted(values: list[tuple[float, int]]) -> float:
    total = sum(weight for _, weight in values)
    if total <= 0:
        raise ValueError("calibration metric has no rows")
    return float(sum(value * weight for value, weight in values) / total)


def _normalize_scores(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(ML_PREDICTION_LABEL_CLASSES):
        raise ValueError("calibration score matrix shape mismatch")
    if not bool(np.isfinite(values).all()):
        raise ValueError("calibration produced non-finite scores")
    values = np.clip(values, ML_CALIBRATION_EPSILON, None)
    row_sums = values.sum(axis=1, keepdims=True)
    if bool((row_sums <= 0.0).any()):
        raise ValueError("calibration produced a zero probability row")
    return validate_probabilities(values / row_sums)


class MLCalibrationBenchmark:
    """Fit point-in-time calibrators on Gate 9 validation predictions and score test.

    The accepted nonlinear model is never retrained here. Each fold's calibrator sees
    only that fold's validation predictions and labels, then transforms the already
    frozen test predictions. The final Gate 13 holdout is not present in Gate 9
    artifacts and is never queried by this benchmark.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        if not ML_CANDIDATE_MODEL_POLICY_ACCEPTED:
            raise RuntimeError("Gate 10 requires accepted Gate 9 candidate evidence")
        if ML_CANDIDATE_MODEL_FINAL_HOLDOUT_ACCESSED:
            raise RuntimeError("Gate 9 candidate evidence touched the protected holdout")
        self.settings = settings
        self.gate9 = MLCandidateModelBenchmark(settings)

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "calibration_benchmark" / "2026" / "2026-08-14.json"

    def prediction_root(self) -> Path:
        return self.report_path().parent / "predictions"

    def _load_gate9_report(self) -> dict[str, object]:
        path = self.gate9.report_path()
        if not path.exists():
            raise FileNotFoundError(f"Gate 10 requires Gate 9 report: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("contract_version") != ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION:
            raise RuntimeError("Gate 10 Gate 9 benchmark contract mismatch")
        if payload.get("final_holdout_accessed") is not False:
            raise RuntimeError("Gate 10 refuses Gate 9 evidence that accessed final holdout")
        if int(payload.get("fold_count", 0)) != ML_CANDIDATE_MODEL_ACCEPTED_FOLDS:
            raise RuntimeError("Gate 10 Gate 9 fold count mismatch")
        if int(payload.get("total_test_rows", 0)) != ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS:
            raise RuntimeError("Gate 10 Gate 9 OOS row count mismatch")
        return payload

    def _fold_item(self, payload: dict[str, object], fold_index: int) -> dict[str, object]:
        items = payload.get("fold_evidence")
        if not isinstance(items, list):
            raise RuntimeError("Gate 9 report has no fold evidence")
        matches = [
            item for item in items
            if isinstance(item, dict)
            and item.get("model_name") == ML_CANDIDATE_MODEL_ACCEPTED_MODEL
            and int(item.get("fold_index", -1)) == fold_index
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Gate 10 expected exactly one Gate 9 fold item for {fold_index}")
        return matches[0]

    def _read_prediction_artifact(
        self,
        item: dict[str, object],
        role: str,
    ) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
        artifact = item.get(f"{role}_artifact")
        if not isinstance(artifact, dict):
            raise RuntimeError(f"Gate 9 fold item missing {role} artifact")
        path = self.gate9.report_path().parent / str(artifact["relative_path"])
        if not path.exists():
            raise FileNotFoundError(path)
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Gate 10 {role} artifact hash mismatch: {path}")

        con = connect_utc(":memory:")
        try:
            fields = ", ".join(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)
            frame = con.execute(
                f"""
                SELECT actual_label, {fields}
                FROM read_parquet({sql_string(path.as_posix())})
                ORDER BY session_date, symbol, instrument_id
                """
            ).fetch_df()
        finally:
            con.close()
        if len(frame) != int(artifact["row_count"]):
            raise RuntimeError(f"Gate 10 {role} artifact row count mismatch")
        labels = frame["actual_label"].to_numpy()
        probabilities = validate_probabilities(
            frame.loc[:, list(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)].to_numpy(dtype=np.float64)
        )
        return labels, probabilities, artifact

    @staticmethod
    def _platt(
        validation_labels: np.ndarray,
        validation_probabilities: np.ndarray,
        test_probabilities: np.ndarray,
    ) -> tuple[np.ndarray, tuple[float, ...], tuple[float, ...]]:
        y = class_indices(validation_labels)
        calibrated = np.zeros_like(test_probabilities, dtype=np.float64)
        coefficients: list[float] = []
        intercepts: list[float] = []
        eps = ML_CALIBRATION_EPSILON
        for class_index in range(len(ML_PREDICTION_LABEL_CLASSES)):
            p_val = np.clip(validation_probabilities[:, class_index], eps, 1.0 - eps)
            p_test = np.clip(test_probabilities[:, class_index], eps, 1.0 - eps)
            x_val = np.log(p_val / (1.0 - p_val)).reshape(-1, 1)
            x_test = np.log(p_test / (1.0 - p_test)).reshape(-1, 1)
            target = (y == class_index).astype(np.int8)
            model = LogisticRegression(
                C=ML_CALIBRATION_PLATT_C,
                solver="lbfgs",
                max_iter=ML_CALIBRATION_PLATT_MAX_ITER,
                fit_intercept=True,
            )
            model.fit(x_val, target)
            calibrated[:, class_index] = model.predict_proba(x_test)[:, 1]
            coefficients.append(float(model.coef_[0, 0]))
            intercepts.append(float(model.intercept_[0]))
        return _normalize_scores(calibrated), tuple(coefficients), tuple(intercepts)

    @staticmethod
    def _isotonic(
        validation_labels: np.ndarray,
        validation_probabilities: np.ndarray,
        test_probabilities: np.ndarray,
    ) -> tuple[np.ndarray, tuple[int, ...]]:
        y = class_indices(validation_labels)
        calibrated = np.zeros_like(test_probabilities, dtype=np.float64)
        knot_counts: list[int] = []
        for class_index in range(len(ML_PREDICTION_LABEL_CLASSES)):
            target = (y == class_index).astype(np.float64)
            model = IsotonicRegression(out_of_bounds="clip")
            model.fit(validation_probabilities[:, class_index], target)
            calibrated[:, class_index] = model.predict(test_probabilities[:, class_index])
            knot_counts.append(int(len(model.X_thresholds_)))
        return _normalize_scores(calibrated), tuple(knot_counts)

    def _write_predictions(
        self,
        *,
        method: str,
        fold_index: int,
        item: dict[str, object],
        probabilities: np.ndarray,
    ) -> CalibrationPredictionArtifact:
        test_artifact = item["test_artifact"]
        source = self.gate9.report_path().parent / str(test_artifact["relative_path"])
        target = (
            self.prediction_root()
            / f"method={method}"
            / f"fold={fold_index:02d}"
            / "part-000.parquet"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        con = connect_utc(":memory:")
        try:
            con.execute(
                f"CREATE TEMP TABLE source AS SELECT * FROM read_parquet({sql_string(source.as_posix())}) ORDER BY session_date, symbol, instrument_id"
            )
            if int(con.execute("SELECT count(*) FROM source").fetchone()[0]) != len(probabilities):
                raise RuntimeError("Gate 10 calibrated prediction/source row mismatch")
            con.register("calibrated", probabilities)
            fields = list(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (
                    SELECT
                        s.fold_index,
                        {sql_string(method)} AS calibration_method,
                        s.model_name,
                        s.observation_key,
                        s.session_date,
                        s.symbol,
                        s.instrument_id,
                        s.actual_label,
                        c.column0 AS {fields[0]},
                        c.column1 AS {fields[1]},
                        c.column2 AS {fields[2]}
                    FROM source AS s
                    JOIN calibrated AS c ON c.rowid = s.rowid
                    ORDER BY s.session_date, s.symbol, s.instrument_id
                )
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, target)
        finally:
            con.close()
        return CalibrationPredictionArtifact(
            method=method,
            fold_index=int(fold_index),
            relative_path=str(target.relative_to(self.report_path().parent)),
            sha256=sha256_file(target),
            row_count=int(len(probabilities)),
        )

    @staticmethod
    def _aggregate(
        method: str,
        evidence: list[CalibrationFoldEvidence],
        raw_by_fold: dict[int, CalibrationFoldEvidence],
    ) -> CalibrationAggregateEvidence:
        selected = [item for item in evidence if item.method == method]
        if len(selected) != ML_CANDIDATE_MODEL_ACCEPTED_FOLDS:
            raise RuntimeError(f"Gate 10 aggregate missing folds for {method}")
        rows = sum(item.test_rows for item in selected)
        auc_values = [
            (item.test_metrics.macro_ovr_auc, item.test_rows)
            for item in selected if item.test_metrics.macro_ovr_auc is not None
        ]
        logloss = _weighted([(item.test_metrics.log_loss, item.test_rows) for item in selected])
        brier = _weighted([(item.test_metrics.multiclass_brier, item.test_rows) for item in selected])
        raw_logloss = _weighted([
            (raw_by_fold[item.fold_index].test_metrics.log_loss, item.test_rows) for item in selected
        ])
        raw_brier = _weighted([
            (raw_by_fold[item.fold_index].test_metrics.multiclass_brier, item.test_rows) for item in selected
        ])
        return CalibrationAggregateEvidence(
            method=method,
            folds=len(selected),
            test_rows=rows,
            weighted_log_loss=logloss,
            weighted_multiclass_brier=brier,
            weighted_accuracy=_weighted([(item.test_metrics.accuracy, item.test_rows) for item in selected]),
            weighted_macro_ovr_auc=(None if not auc_values else _weighted([(float(v), r) for v, r in auc_values])),
            weighted_macro_ece=_weighted([(item.test_metrics.macro_ece, item.test_rows) for item in selected]),
            relative_log_loss_improvement_vs_raw=(raw_logloss - logloss) / raw_logloss,
            relative_brier_improvement_vs_raw=(raw_brier - brier) / raw_brier,
            log_loss_fold_wins_vs_raw=sum(
                item.test_metrics.log_loss < raw_by_fold[item.fold_index].test_metrics.log_loss
                for item in selected
            ),
            brier_fold_wins_vs_raw=sum(
                item.test_metrics.multiclass_brier < raw_by_fold[item.fold_index].test_metrics.multiclass_brier
                for item in selected
            ),
        )

    def run(self, progress=None) -> MLCalibrationBenchmarkReport:
        started = perf_counter()
        payload = self._load_gate9_report()
        evidence: list[CalibrationFoldEvidence] = []

        for fold_index in range(1, ML_CANDIDATE_MODEL_ACCEPTED_FOLDS + 1):
            item = self._fold_item(payload, fold_index)
            validation_labels, validation_probs, _ = self._read_prediction_artifact(item, "validation")
            test_labels, test_probs, _ = self._read_prediction_artifact(item, "test")
            if progress is not None:
                progress(
                    f"fold {fold_index}/{ML_CANDIDATE_MODEL_ACCEPTED_FOLDS}: "
                    f"validation={len(validation_labels):,} test={len(test_labels):,}"
                )

            raw_started = perf_counter()
            raw = validate_probabilities(test_probs)
            raw_seconds = perf_counter() - raw_started
            raw_metrics = probability_metrics(test_labels, raw)
            raw_artifact = self._write_predictions(
                method="raw", fold_index=fold_index, item=item, probabilities=raw
            )
            raw_item = CalibrationFoldEvidence(
                method="raw",
                fold_index=fold_index,
                validation_rows=len(validation_labels),
                test_rows=len(test_labels),
                fit_seconds=0.0,
                predict_seconds=raw_seconds,
                test_metrics=raw_metrics,
                platt_coefficients=None,
                platt_intercepts=None,
                isotonic_knot_counts=None,
                prediction_artifact=raw_artifact,
            )
            evidence.append(raw_item)

            platt_started = perf_counter()
            platt, coefficients, intercepts = self._platt(validation_labels, validation_probs, test_probs)
            platt_seconds = perf_counter() - platt_started
            platt_metrics = probability_metrics(test_labels, platt)
            platt_artifact = self._write_predictions(
                method="ovr_platt", fold_index=fold_index, item=item, probabilities=platt
            )
            evidence.append(
                CalibrationFoldEvidence(
                    method="ovr_platt",
                    fold_index=fold_index,
                    validation_rows=len(validation_labels),
                    test_rows=len(test_labels),
                    fit_seconds=platt_seconds,
                    predict_seconds=0.0,
                    test_metrics=platt_metrics,
                    platt_coefficients=coefficients,
                    platt_intercepts=intercepts,
                    isotonic_knot_counts=None,
                    prediction_artifact=platt_artifact,
                )
            )

            isotonic_started = perf_counter()
            isotonic, knot_counts = self._isotonic(validation_labels, validation_probs, test_probs)
            isotonic_seconds = perf_counter() - isotonic_started
            isotonic_metrics = probability_metrics(test_labels, isotonic)
            isotonic_artifact = self._write_predictions(
                method="ovr_isotonic", fold_index=fold_index, item=item, probabilities=isotonic
            )
            evidence.append(
                CalibrationFoldEvidence(
                    method="ovr_isotonic",
                    fold_index=fold_index,
                    validation_rows=len(validation_labels),
                    test_rows=len(test_labels),
                    fit_seconds=isotonic_seconds,
                    predict_seconds=0.0,
                    test_metrics=isotonic_metrics,
                    platt_coefficients=None,
                    platt_intercepts=None,
                    isotonic_knot_counts=knot_counts,
                    prediction_artifact=isotonic_artifact,
                )
            )

            if progress is not None:
                progress(
                    f"  raw:          logloss={raw_metrics.log_loss:.6f} brier={raw_metrics.multiclass_brier:.6f} "
                    f"auc={raw_metrics.macro_ovr_auc:.6f} ece={raw_metrics.macro_ece:.6f}"
                )
                progress(
                    f"  ovr_platt:    logloss={platt_metrics.log_loss:.6f} brier={platt_metrics.multiclass_brier:.6f} "
                    f"auc={platt_metrics.macro_ovr_auc:.6f} ece={platt_metrics.macro_ece:.6f}"
                )
                progress(
                    f"  ovr_isotonic: logloss={isotonic_metrics.log_loss:.6f} brier={isotonic_metrics.multiclass_brier:.6f} "
                    f"auc={isotonic_metrics.macro_ovr_auc:.6f} ece={isotonic_metrics.macro_ece:.6f}"
                )

        raw_by_fold = {item.fold_index: item for item in evidence if item.method == "raw"}
        aggregates = tuple(
            self._aggregate(method, evidence, raw_by_fold) for method in ML_CALIBRATION_METHODS
        )
        if any(item.test_rows != ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS for item in aggregates):
            raise RuntimeError("Gate 10 aggregate OOS rows do not reconcile")

        report = MLCalibrationBenchmarkReport(
            contract_version=ML_CALIBRATION_BENCHMARK_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            status=ML_CALIBRATION_BENCHMARK_STATUS,
            candidate_policy_contract=ML_CANDIDATE_MODEL_POLICY_CONTRACT_VERSION,
            gate9_benchmark_contract=ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION,
            accepted_model=ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
            sklearn_version=sklearn.__version__,
            duckdb_version=duckdb.__version__,
            numpy_version=np.__version__,
            methods=ML_CALIBRATION_METHODS,
            validation_only_fit=ML_CALIBRATION_VALIDATION_ONLY_FIT,
            test_only_score=ML_CALIBRATION_TEST_ONLY_SCORE,
            fold_count=ML_CANDIDATE_MODEL_ACCEPTED_FOLDS,
            total_test_rows=ML_CANDIDATE_MODEL_ACCEPTED_OOS_ROWS,
            final_holdout_start=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            final_holdout_accessed=ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED,
            fold_evidence=tuple(evidence),
            aggregate_evidence=aggregates,
            wall_seconds=perf_counter() - started,
            report_path=str(self.report_path()),
        )
        atomic_write_text(self.report_path(), json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
