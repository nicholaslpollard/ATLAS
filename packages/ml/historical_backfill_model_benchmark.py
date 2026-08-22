from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

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
from packages.ml.candidate_model_probe import (
    ML_CANDIDATE_MODEL_RANDOM_STATE,
    ML_CANDIDATE_MODEL_SPECS,
    CandidateModelSpec,
)
from packages.ml.evaluation import ProbabilityMetrics, class_indices, probability_metrics, validate_probabilities
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.historical_backfill_model_evaluation_design import (
    GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION,
    HistoricalBackfillModelEvaluationDesign,
)
from packages.ml.label_policy import ML_PREDICTION_LABEL_PROBABILITY_FIELDS


HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION = (
    "historical-backfill-ml-benchmark-v1-paired-fixed-budget-plus-nested-history"
)
HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT = (
    "798cc974d06863116c02a8b09c46b2935b5e633793bd34288ef27638dd22238e"
)
HISTORICAL_BACKFILL_PRIMARY_B_ROLE = "B_FIXED_1M"
HISTORICAL_BACKFILL_PRIMARY_C_ROLE = "C_FIXED_1M"
HISTORICAL_BACKFILL_NESTED_C_ROLE = "C_NESTED_B_PLUS_PRESEAM"
HISTORICAL_BACKFILL_MODEL_NAME = "hgb_leaf15_iter100"
HISTORICAL_BACKFILL_PRODUCTION_MODEL_REPLACEMENT_ALLOWED = False
HISTORICAL_BACKFILL_FINAL_HOLDOUT_ACCESSED = False


class HistoricalBackfillModelBenchmarkError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parquet_list(paths: list[Path]) -> str:
    if not paths:
        raise HistoricalBackfillModelBenchmarkError("historical benchmark requires Parquet input")
    return "[" + ",".join(sql_string(path) for path in paths) + "]"


def _weighted(values: list[tuple[float, int]]) -> float:
    rows = sum(weight for _, weight in values)
    if rows <= 0:
        raise HistoricalBackfillModelBenchmarkError("cannot aggregate zero rows")
    return float(sum(value * weight for value, weight in values) / rows)


def _accepted_spec() -> CandidateModelSpec:
    matches = [spec for spec in ML_CANDIDATE_MODEL_SPECS if spec.name == HISTORICAL_BACKFILL_MODEL_NAME]
    if len(matches) != 1:
        raise HistoricalBackfillModelBenchmarkError("accepted HGB specification is unavailable or ambiguous")
    return matches[0]


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
        random_state=ML_CANDIDATE_MODEL_RANDOM_STATE,
    )


def _metrics_dict(metrics: ProbabilityMetrics) -> dict[str, object]:
    return asdict(metrics)


def _aggregate_role(role: str, folds: list[dict[str, object]]) -> dict[str, object]:
    selected = [dict(item["roles"])[role] for item in folds]
    if not selected:
        raise HistoricalBackfillModelBenchmarkError(f"no fold evidence for role {role}")
    test_rows = sum(int(item["test_rows"]) for item in selected)
    auc_values = [
        (float(dict(item["test_metrics"])["macro_ovr_auc"]), int(item["test_rows"]))
        for item in selected
        if dict(item["test_metrics"])["macro_ovr_auc"] is not None
    ]
    aggregate = {
        "role": role,
        "folds": len(selected),
        "test_rows": test_rows,
        "weighted_log_loss": _weighted(
            [(float(dict(item["test_metrics"])["log_loss"]), int(item["test_rows"])) for item in selected]
        ),
        "weighted_multiclass_brier": _weighted(
            [
                (float(dict(item["test_metrics"])["multiclass_brier"]), int(item["test_rows"]))
                for item in selected
            ]
        ),
        "weighted_accuracy": _weighted(
            [(float(dict(item["test_metrics"])["accuracy"]), int(item["test_rows"])) for item in selected]
        ),
        "weighted_macro_ovr_auc": None if not auc_values else _weighted(auc_values),
        "weighted_macro_ece": _weighted(
            [(float(dict(item["test_metrics"])["macro_ece"]), int(item["test_rows"])) for item in selected]
        ),
        "minimum_fold_log_loss": min(float(dict(item["test_metrics"])["log_loss"]) for item in selected),
        "maximum_fold_log_loss": max(float(dict(item["test_metrics"])["log_loss"]) for item in selected),
        "minimum_fold_brier": min(
            float(dict(item["test_metrics"])["multiclass_brier"]) for item in selected
        ),
        "maximum_fold_brier": max(
            float(dict(item["test_metrics"])["multiclass_brier"]) for item in selected
        ),
    }
    return aggregate


def primary_selection_decision(aggregates: dict[str, dict[str, object]]) -> dict[str, object]:
    b = aggregates[HISTORICAL_BACKFILL_PRIMARY_B_ROLE]
    c = aggregates[HISTORICAL_BACKFILL_PRIMARY_C_ROLE]
    log_loss_delta = float(c["weighted_log_loss"]) - float(b["weighted_log_loss"])
    brier_delta = float(c["weighted_multiclass_brier"]) - float(b["weighted_multiclass_brier"])
    c_improves_both = log_loss_delta < 0.0 and brier_delta < 0.0
    return {
        "rule": (
            "C_MAY_ADVANCE_ONLY_IF_AGGREGATE_LOG_LOSS_AND_BRIER_BOTH_IMPROVE_VS_B;"
            "MIXED_OR_WORSE_PROPER_SCORES_DEFAULT_TO_B"
        ),
        "B_role": HISTORICAL_BACKFILL_PRIMARY_B_ROLE,
        "C_role": HISTORICAL_BACKFILL_PRIMARY_C_ROLE,
        "C_minus_B_log_loss": log_loss_delta,
        "C_minus_B_multiclass_brier": brier_delta,
        "C_improves_both_primary_scores": c_improves_both,
        "decision": (
            "REGISTER_C_AS_VERSIONED_CHALLENGER_EVIDENCE"
            if c_improves_both
            else "RETAIN_ACCEPTED_PHASE10_PRODUCTION_MODEL"
        ),
        "production_model_replacement_allowed": False,
    }


class HistoricalBackfillModelBenchmark:
    """Execute the locked B-vs-C comparison and nested-history attribution sensitivity.

    The Gate 11-D report is the immutable experiment specification. All model fitting is
    isolated beneath the historical-backfill evaluation namespace. The accepted Phase-10
    registry and protected final holdout are not written or read.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.design = HistoricalBackfillModelEvaluationDesign(settings)
        self.predictors = tuple(ML_PRODUCTION_CORE_FEATURE_NAMES)
        self.spec = _accepted_spec()
        self.root = self.design.root / "benchmark" / "v1"
        self.prediction_root = self.root / "predictions"
        self.checkpoint_root = self.root / "fold_checkpoints"
        self.report_path = self.root / "historical_extension_model_benchmark_report.json"
        derived = settings.resolved_path(settings.data.paths.derived)
        self.production_registry_root = derived / "ml" / "model_registry"

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise HistoricalBackfillModelBenchmarkError(f"missing {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HistoricalBackfillModelBenchmarkError(f"invalid JSON for {label}: {path}") from exc

    @staticmethod
    def _inventory(root: Path) -> list[dict[str, str]]:
        if not root.is_dir():
            return []
        return [
            {"relative_path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
            for path in sorted(root.rglob("*"))
            if path.is_file()
        ]

    @staticmethod
    def _xy(frame: pd.DataFrame, predictors: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
        x = frame.loc[:, list(predictors)].to_numpy(dtype=np.float32, copy=True)
        y = class_indices(frame["prediction_label"].to_numpy())
        return x, y

    def _evaluation_frame(self, con: Any, source_sql: str, start: str, end: str) -> pd.DataFrame:
        columns = ", ".join(self.predictors)
        return con.execute(
            f"""
            SELECT observation_key, session_date, symbol, instrument_id, prediction_label, {columns}
            FROM {source_sql}
            WHERE session_date BETWEEN DATE '{start}' AND DATE '{end}'
            ORDER BY observation_key
            """
        ).fetch_df()

    def _training_frame(
        self,
        con: Any,
        *,
        b_source: str,
        x_source: str,
        fold_design: dict[str, Any],
        role: str,
    ) -> pd.DataFrame:
        columns = ", ".join(self.predictors)
        train_end = str(fold_design["accepted_train_end"])
        fixed = dict(fold_design["fixed_budget"])
        nested = dict(fold_design["nested_history_sensitivity"])
        b_start = str(fold_design["B_train_start"])
        x_start = str(fold_design["C_extension_train_start"])
        if role == HISTORICAL_BACKFILL_PRIMARY_B_ROLE:
            query = f"""
                SELECT prediction_label, {columns}
                FROM {b_source}
                WHERE session_date BETWEEN DATE '{b_start}' AND DATE '{train_end}'
                  AND (hash(observation_key) % 1000000) < {int(fixed['B_hash_threshold'])}
                ORDER BY session_date, observation_key
            """
            expected = int(fixed["B_sample_rows"])
        elif role == HISTORICAL_BACKFILL_PRIMARY_C_ROLE:
            threshold = int(fixed["C_hash_threshold"])
            query = f"""
                SELECT prediction_label, {columns}
                FROM (
                    SELECT observation_key, session_date, prediction_label, {columns}
                    FROM {b_source}
                    WHERE session_date BETWEEN DATE '{b_start}' AND DATE '{train_end}'
                    UNION ALL
                    SELECT observation_key, session_date, prediction_label, {columns}
                    FROM {x_source}
                    WHERE session_date BETWEEN DATE '{x_start}' AND DATE '{train_end}'
                )
                WHERE (hash(observation_key) % 1000000) < {threshold}
                ORDER BY session_date, observation_key
            """
            expected = int(fixed["C_sample_rows"])
        elif role == HISTORICAL_BACKFILL_NESTED_C_ROLE:
            query = f"""
                SELECT prediction_label, {columns}
                FROM (
                    SELECT observation_key, session_date, prediction_label, {columns}
                    FROM {b_source}
                    WHERE session_date BETWEEN DATE '{b_start}' AND DATE '{train_end}'
                      AND (hash(observation_key) % 1000000) < {int(nested['B_base_hash_threshold'])}
                    UNION ALL
                    SELECT observation_key, session_date, prediction_label, {columns}
                    FROM {x_source}
                    WHERE session_date BETWEEN DATE '{x_start}' AND DATE '{train_end}'
                      AND (hash(observation_key) % 1000000) < {int(nested['extension_hash_threshold'])}
                )
                ORDER BY session_date, observation_key
            """
            expected = int(nested["C_nested_sample_rows"])
        else:
            raise HistoricalBackfillModelBenchmarkError(f"unsupported comparison role: {role}")
        frame = con.execute(query).fetch_df()
        if len(frame) != expected:
            raise HistoricalBackfillModelBenchmarkError(
                f"fold {fold_design['fold_index']} {role} sample mismatch: {len(frame):,} != {expected:,}"
            )
        return frame

    def _write_test_predictions(
        self,
        *,
        fold_index: int,
        role: str,
        evaluation: pd.DataFrame,
        probabilities: np.ndarray,
    ) -> dict[str, object]:
        probs = validate_probabilities(probabilities)
        if probs.shape[0] != len(evaluation):
            raise HistoricalBackfillModelBenchmarkError("prediction row count mismatch")
        out = evaluation.loc[:, ["observation_key", "prediction_label"]].copy()
        out = out.rename(columns={"prediction_label": "actual_label"})
        for index, field in enumerate(ML_PREDICTION_LABEL_PROBABILITY_FIELDS):
            out[field] = probs[:, index]
        target = self.prediction_root / f"role={role}" / f"fold={fold_index:02d}" / "test.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        writer = connect_utc(":memory:")
        try:
            writer.register("historical_test_predictions", out)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            writer.execute(
                f"""
                COPY (
                    SELECT * FROM historical_test_predictions ORDER BY observation_key
                ) TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, target)
        finally:
            writer.close()
        return {
            "relative_path": target.relative_to(self.root).as_posix(),
            "sha256": sha256_file(target),
            "row_count": len(out),
        }

    def _checkpoint_path(self, fold_index: int) -> Path:
        return self.checkpoint_root / f"fold={fold_index:02d}.json"

    def _load_checkpoint(self, fold_design: dict[str, Any], design_fingerprint: str) -> dict[str, object] | None:
        path = self._checkpoint_path(int(fold_design["fold_index"]))
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if payload.get("contract_version") != HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION:
            return None
        if payload.get("design_source_fingerprint") != design_fingerprint:
            return None
        if int(payload.get("fold_index", -1)) != int(fold_design["fold_index"]):
            return None
        roles = dict(payload.get("roles") or {})
        for role in (
            HISTORICAL_BACKFILL_PRIMARY_B_ROLE,
            HISTORICAL_BACKFILL_PRIMARY_C_ROLE,
            HISTORICAL_BACKFILL_NESTED_C_ROLE,
        ):
            item = dict(roles.get(role) or {})
            artifact = dict(item.get("test_artifact") or {})
            target = self.root / str(artifact.get("relative_path", ""))
            if not target.is_file() or sha256_file(target) != artifact.get("sha256"):
                return None
        return payload

    def _run_fold(
        self,
        con: Any,
        *,
        b_source: str,
        x_source: str,
        fold_design: dict[str, Any],
        design_fingerprint: str,
        progress: Callable[[str], None] | None,
    ) -> dict[str, object]:
        fold_index = int(fold_design["fold_index"])
        cached = self._load_checkpoint(fold_design, design_fingerprint)
        if cached is not None:
            if progress is not None:
                progress(f"fold {fold_index:02d}: checkpoint verified; skipping completed fits")
            return cached

        validation = self._evaluation_frame(
            con, b_source, str(fold_design["validation_start"]), str(fold_design["validation_end"])
        )
        test = self._evaluation_frame(
            con, b_source, str(fold_design["test_start"]), str(fold_design["test_end"])
        )
        if len(validation) != int(fold_design["B_validation_rows"]):
            raise HistoricalBackfillModelBenchmarkError(f"fold {fold_index} validation rows changed")
        if len(test) != int(fold_design["B_test_rows"]):
            raise HistoricalBackfillModelBenchmarkError(f"fold {fold_index} test rows changed")
        x_validation, _ = self._xy(validation, self.predictors)
        x_test, _ = self._xy(test, self.predictors)
        validation_labels = validation["prediction_label"].to_numpy()
        test_labels = test["prediction_label"].to_numpy()

        roles: dict[str, object] = {}
        for role in (
            HISTORICAL_BACKFILL_PRIMARY_B_ROLE,
            HISTORICAL_BACKFILL_PRIMARY_C_ROLE,
            HISTORICAL_BACKFILL_NESTED_C_ROLE,
        ):
            training = self._training_frame(
                con, b_source=b_source, x_source=x_source, fold_design=fold_design, role=role
            )
            x_train, y_train = self._xy(training, self.predictors)
            sampled_rows = len(training)
            del training
            model = _model(self.spec)
            fit_started = perf_counter()
            model.fit(x_train, y_train)
            fit_seconds = perf_counter() - fit_started
            if not np.array_equal(model.classes_, np.asarray([0, 1, 2])):
                raise HistoricalBackfillModelBenchmarkError(
                    f"fold {fold_index} {role} model classes differ from locked three-class order"
                )
            del x_train, y_train

            validation_started = perf_counter()
            validation_probabilities = validate_probabilities(model.predict_proba(x_validation))
            validation_predict_seconds = perf_counter() - validation_started
            validation_metrics = probability_metrics(validation_labels, validation_probabilities)
            del validation_probabilities

            test_started = perf_counter()
            test_probabilities = validate_probabilities(model.predict_proba(x_test))
            test_predict_seconds = perf_counter() - test_started
            test_metrics = probability_metrics(test_labels, test_probabilities)
            artifact = self._write_test_predictions(
                fold_index=fold_index,
                role=role,
                evaluation=test,
                probabilities=test_probabilities,
            )
            del test_probabilities, model
            roles[role] = {
                "role": role,
                "sampled_train_rows": sampled_rows,
                "validation_rows": len(validation),
                "test_rows": len(test),
                "fit_seconds": fit_seconds,
                "validation_predict_seconds": validation_predict_seconds,
                "test_predict_seconds": test_predict_seconds,
                "validation_metrics": _metrics_dict(validation_metrics),
                "test_metrics": _metrics_dict(test_metrics),
                "test_artifact": artifact,
            }
            if progress is not None:
                progress(
                    f"fold {fold_index:02d} {role}: train={sampled_rows:,} "
                    f"test_logloss={test_metrics.log_loss:.6f} "
                    f"test_brier={test_metrics.multiclass_brier:.6f} fit={fit_seconds:.2f}s"
                )

        payload: dict[str, object] = {
            "contract_version": HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION,
            "design_source_fingerprint": design_fingerprint,
            "fold_index": fold_index,
            "validation_start": fold_design["validation_start"],
            "validation_end": fold_design["validation_end"],
            "test_start": fold_design["test_start"],
            "test_end": fold_design["test_end"],
            "expected_test_key_sha256": fold_design["test_key_sha256"],
            "roles": roles,
        }
        path = self._checkpoint_path(fold_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return payload

    def run(self, *, progress: Callable[[str], None] | None = None) -> dict[str, object]:
        started = perf_counter()
        design_report = self.design.run()
        if design_report.get("pass") is not True:
            raise HistoricalBackfillModelBenchmarkError("Gate 11-D design no longer passes")
        if design_report.get("contract_version") != GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION:
            raise HistoricalBackfillModelBenchmarkError("Gate 11-D design contract changed")
        design_fingerprint = str(design_report["source_fingerprint"])
        if design_fingerprint != HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT:
            raise HistoricalBackfillModelBenchmarkError(
                "Gate 11-D source fingerprint changed after target-machine acceptance"
            )

        build, _, b_root, x_root, _ = self.design._load_gate11c()  # noqa: SLF001
        _, b_paths = self.design._manifest_paths(b_root)  # noqa: SLF001
        _, x_paths = self.design._manifest_paths(x_root)  # noqa: SLF001
        b_source = f"read_parquet({_parquet_list(b_paths)}, union_by_name=true)"
        x_source = f"read_parquet({_parquet_list(x_paths)}, union_by_name=true)"

        registry_before = self._inventory(self.production_registry_root)
        folds: list[dict[str, object]] = []
        con = connect_utc(":memory:")
        try:
            for fold_design in list(design_report["folds"]):
                folds.append(
                    self._run_fold(
                        con,
                        b_source=b_source,
                        x_source=x_source,
                        fold_design=dict(fold_design),
                        design_fingerprint=design_fingerprint,
                        progress=progress,
                    )
                )
        finally:
            con.close()
        registry_after = self._inventory(self.production_registry_root)
        if registry_before != registry_after:
            raise HistoricalBackfillModelBenchmarkError("production model registry changed during benchmark")

        aggregates = {
            role: _aggregate_role(role, folds)
            for role in (
                HISTORICAL_BACKFILL_PRIMARY_B_ROLE,
                HISTORICAL_BACKFILL_PRIMARY_C_ROLE,
                HISTORICAL_BACKFILL_NESTED_C_ROLE,
            )
        }
        decision = primary_selection_decision(aggregates)
        nested = aggregates[HISTORICAL_BACKFILL_NESTED_C_ROLE]
        b = aggregates[HISTORICAL_BACKFILL_PRIMARY_B_ROLE]
        nested_attribution = {
            "role": "ATTRIBUTION_SENSITIVITY_ONLY",
            "can_promote_model": False,
            "nested_minus_B_log_loss": float(nested["weighted_log_loss"]) - float(b["weighted_log_loss"]),
            "nested_minus_B_multiclass_brier": float(nested["weighted_multiclass_brier"])
            - float(b["weighted_multiclass_brier"]),
        }
        result_fingerprint = _stable_hash(
            {
                "contract_version": HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION,
                "design_source_fingerprint": design_fingerprint,
                "model_spec": asdict(self.spec),
                "folds": folds,
                "aggregates": aggregates,
                "decision": decision,
                "nested_attribution": nested_attribution,
            }
        )
        report: dict[str, object] = {
            "contract_version": HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": _stable_hash(
                {
                    "contract_version": HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION,
                    "design_source_fingerprint": design_fingerprint,
                    "model_spec": asdict(self.spec),
                    "predictors": list(self.predictors),
                }
            ),
            "result_fingerprint": result_fingerprint,
            "design_source_fingerprint": design_fingerprint,
            "as_of_date": build["as_of_date"],
            "model_family": "sklearn_hist_gradient_boosting",
            "model_name": self.spec.name,
            "model_spec": asdict(self.spec),
            "predictor_count": len(self.predictors),
            "predictor_columns": list(self.predictors),
            "sklearn_version": sklearn.__version__,
            "duckdb_version": duckdb.__version__,
            "numpy_version": np.__version__,
            "fold_count": len(folds),
            "folds": folds,
            "aggregates": aggregates,
            "primary_selection": decision,
            "nested_history_attribution": nested_attribution,
            "final_holdout_accessed": HISTORICAL_BACKFILL_FINAL_HOLDOUT_ACCESSED,
            "production_model_replacement_allowed": HISTORICAL_BACKFILL_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
            "production_registry_inventory_unchanged": registry_before == registry_after,
            "production_ml_writes": 0,
            "wall_seconds": perf_counter() - started,
            "pass": (
                len(folds) == 10
                and registry_before == registry_after
                and HISTORICAL_BACKFILL_FINAL_HOLDOUT_ACCESSED is False
                and HISTORICAL_BACKFILL_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False
            ),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
