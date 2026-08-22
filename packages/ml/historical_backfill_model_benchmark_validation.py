from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.historical_backfill_model_benchmark import (
    HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT,
    HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION,
    HISTORICAL_BACKFILL_NESTED_C_ROLE,
    HISTORICAL_BACKFILL_PRIMARY_B_ROLE,
    HISTORICAL_BACKFILL_PRIMARY_C_ROLE,
    HistoricalBackfillModelBenchmark,
)
from packages.ml.historical_backfill_model_evaluation_design import (
    GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION,
    HistoricalBackfillModelEvaluationDesign,
)
from packages.ml.label_policy import ML_PREDICTION_LABEL_CLASSES, ML_PREDICTION_LABEL_PROBABILITY_FIELDS


HISTORICAL_BACKFILL_MODEL_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-ml-benchmark-validation-v1-independent-artifact-recompute"
)
HISTORICAL_BACKFILL_VALIDATION_TOLERANCE = 1e-12
HISTORICAL_BACKFILL_PROBABILITY_SUM_TOLERANCE = 1e-6
HISTORICAL_BACKFILL_ECE_BINS = 15


class HistoricalBackfillModelBenchmarkValidationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _key_hash(values: list[object]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _class_indices(labels: np.ndarray) -> np.ndarray:
    mapping = {label: index for index, label in enumerate(ML_PREDICTION_LABEL_CLASSES)}
    values = np.asarray(labels)
    unknown = ~np.isin(values, np.asarray(ML_PREDICTION_LABEL_CLASSES, dtype=object))
    if bool(np.any(unknown)):
        raise HistoricalBackfillModelBenchmarkValidationError("prediction artifact contains unknown labels")
    return np.asarray([mapping[str(value)] for value in values], dtype=np.int8)


def _macro_ece(y_index: np.ndarray, probabilities: np.ndarray) -> float:
    rows = int(len(y_index))
    edges = np.linspace(0.0, 1.0, HISTORICAL_BACKFILL_ECE_BINS + 1)
    class_values: list[float] = []
    for class_index in range(probabilities.shape[1]):
        confidence = probabilities[:, class_index]
        truth = (y_index == class_index).astype(np.float64)
        assignments = np.minimum(
            np.searchsorted(edges, confidence, side="right") - 1,
            HISTORICAL_BACKFILL_ECE_BINS - 1,
        )
        assignments = np.maximum(assignments, 0)
        ece = 0.0
        for bin_index in range(HISTORICAL_BACKFILL_ECE_BINS):
            mask = assignments == bin_index
            count = int(mask.sum())
            if count:
                ece += (count / rows) * abs(
                    float(confidence[mask].mean()) - float(truth[mask].mean())
                )
        class_values.append(ece)
    return float(np.mean(class_values))


def _independent_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, object]:
    probs = np.asarray(probabilities, dtype=np.float64)
    if probs.ndim != 2 or probs.shape[1] != len(ML_PREDICTION_LABEL_CLASSES):
        raise HistoricalBackfillModelBenchmarkValidationError("prediction matrix shape changed")
    if not bool(np.isfinite(probs).all()):
        raise HistoricalBackfillModelBenchmarkValidationError("prediction artifact contains non-finite values")
    if bool((probs < 0.0).any()) or bool((probs > 1.0).any()):
        raise HistoricalBackfillModelBenchmarkValidationError("prediction artifact probabilities outside [0,1]")
    row_sums = probs.sum(axis=1)
    if not bool(
        np.allclose(
            row_sums,
            1.0,
            atol=HISTORICAL_BACKFILL_PROBABILITY_SUM_TOLERANCE,
            rtol=HISTORICAL_BACKFILL_PROBABILITY_SUM_TOLERANCE,
        )
    ):
        raise HistoricalBackfillModelBenchmarkValidationError("prediction artifact rows do not sum to one")
    probs = probs / row_sums[:, np.newaxis]
    y_index = _class_indices(labels)
    rows = int(len(y_index))
    clipped = np.clip(probs, np.finfo(np.float64).eps, 1.0)
    log_loss = float(-np.log(clipped[np.arange(rows), y_index]).mean())
    one_hot = np.eye(probs.shape[1], dtype=np.float64)[y_index]
    brier = float(np.square(probs - one_hot).sum(axis=1).mean())
    accuracy = float((np.argmax(probs, axis=1) == y_index).mean())
    auc: float | None
    if np.unique(y_index).size != probs.shape[1]:
        auc = None
    else:
        try:
            value = float(
                roc_auc_score(
                    y_index,
                    probs,
                    labels=np.arange(probs.shape[1]),
                    multi_class="ovr",
                    average="macro",
                )
            )
            auc = value if np.isfinite(value) else None
        except ValueError:
            auc = None
    return {
        "rows": rows,
        "log_loss": log_loss,
        "multiclass_brier": brier,
        "accuracy": accuracy,
        "macro_ovr_auc": auc,
        "macro_ece": _macro_ece(y_index, probs),
    }


def _weighted(values: list[tuple[float, int]]) -> float:
    rows = sum(weight for _, weight in values)
    if rows <= 0:
        raise HistoricalBackfillModelBenchmarkValidationError("cannot aggregate zero rows")
    return float(sum(value * weight for value, weight in values) / rows)


def _close(left: float, right: float) -> bool:
    return abs(float(left) - float(right)) <= HISTORICAL_BACKFILL_VALIDATION_TOLERANCE


class HistoricalBackfillModelBenchmarkValidator:
    """Independently validate persisted historical-extension probability evidence.

    This validator does not fit models and does not use the benchmark's metric helper.
    It hashes each persisted artifact, recomputes observation-key identity and primary
    probability metrics from the Parquet predictions, reconstructs aggregates, and
    independently applies the preregistered B-vs-C proper-score rule.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.design = HistoricalBackfillModelEvaluationDesign(settings)
        self.benchmark = HistoricalBackfillModelBenchmark(settings)
        self.report_path = self.benchmark.root / "historical_extension_model_validation_report.json"

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise HistoricalBackfillModelBenchmarkValidationError(f"missing {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HistoricalBackfillModelBenchmarkValidationError(f"invalid JSON for {label}: {path}") from exc

    def _artifact_metrics(
        self,
        artifact: dict[str, Any],
        expected_key_hash: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        path = self.benchmark.root / str(artifact["relative_path"])
        if not path.is_file():
            raise HistoricalBackfillModelBenchmarkValidationError(f"missing prediction artifact: {path}")
        digest = sha256_file(path)
        if digest != str(artifact["sha256"]):
            raise HistoricalBackfillModelBenchmarkValidationError(f"prediction artifact hash changed: {path}")
        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"""
                SELECT observation_key, actual_label, {', '.join(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)}
                FROM read_parquet({sql_string(path)})
                ORDER BY observation_key
                """
            ).fetch_df()
        finally:
            con.close()
        if len(frame) != int(artifact["row_count"]):
            raise HistoricalBackfillModelBenchmarkValidationError("prediction artifact row count changed")
        if int(frame["observation_key"].nunique(dropna=False)) != len(frame):
            raise HistoricalBackfillModelBenchmarkValidationError("prediction artifact contains duplicate keys")
        key_hash = _key_hash(frame["observation_key"].tolist())
        if key_hash != expected_key_hash:
            raise HistoricalBackfillModelBenchmarkValidationError("prediction artifact test population changed")
        probabilities = frame.loc[:, list(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)].to_numpy(dtype=np.float64)
        metrics = _independent_metrics(frame["actual_label"].to_numpy(), probabilities)
        proof = {
            "relative_path": artifact["relative_path"],
            "sha256": digest,
            "row_count": len(frame),
            "distinct_observation_keys": int(frame["observation_key"].nunique(dropna=False)),
            "observation_key_sha256": key_hash,
            "probability_rows_valid": True,
        }
        return metrics, proof

    def run(self) -> dict[str, object]:
        design = self._read_json(self.design.report_path, "Gate 11-D design report")
        benchmark = self._read_json(self.benchmark.report_path, "historical model benchmark report")
        if design.get("contract_version") != GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION:
            raise HistoricalBackfillModelBenchmarkValidationError("Gate 11-D contract changed")
        if design.get("source_fingerprint") != HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT:
            raise HistoricalBackfillModelBenchmarkValidationError("Gate 11-D fingerprint changed")
        if benchmark.get("contract_version") != HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION:
            raise HistoricalBackfillModelBenchmarkValidationError("benchmark contract changed")
        if benchmark.get("design_source_fingerprint") != HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT:
            raise HistoricalBackfillModelBenchmarkValidationError("benchmark is not bound to accepted design")
        if benchmark.get("pass") is not True:
            raise HistoricalBackfillModelBenchmarkValidationError("benchmark did not pass its own safety checks")

        design_folds = {int(item["fold_index"]): dict(item) for item in list(design["folds"])}
        benchmark_folds = {int(item["fold_index"]): dict(item) for item in list(benchmark["folds"])}
        if sorted(design_folds) != list(range(1, 11)) or sorted(benchmark_folds) != list(range(1, 11)):
            raise HistoricalBackfillModelBenchmarkValidationError("expected exactly ten accepted folds")

        role_metrics: dict[str, list[dict[str, object]]] = {
            HISTORICAL_BACKFILL_PRIMARY_B_ROLE: [],
            HISTORICAL_BACKFILL_PRIMARY_C_ROLE: [],
            HISTORICAL_BACKFILL_NESTED_C_ROLE: [],
        }
        artifacts: list[dict[str, object]] = []
        metric_checks: list[bool] = []
        sample_checks: list[bool] = []
        for fold_index in range(1, 11):
            d = design_folds[fold_index]
            b = benchmark_folds[fold_index]
            if str(b["expected_test_key_sha256"]) != str(d["test_key_sha256"]):
                raise HistoricalBackfillModelBenchmarkValidationError("fold checkpoint expected-key hash changed")
            roles = dict(b["roles"])
            fixed = dict(d["fixed_budget"])
            nested_design = dict(d["nested_history_sensitivity"])
            expected_samples = {
                HISTORICAL_BACKFILL_PRIMARY_B_ROLE: int(fixed["B_sample_rows"]),
                HISTORICAL_BACKFILL_PRIMARY_C_ROLE: int(fixed["C_sample_rows"]),
                HISTORICAL_BACKFILL_NESTED_C_ROLE: int(nested_design["C_nested_sample_rows"]),
            }
            for role in role_metrics:
                item = dict(roles[role])
                sample_checks.append(int(item["sampled_train_rows"]) == expected_samples[role])
                recomputed, proof = self._artifact_metrics(
                    dict(item["test_artifact"]), str(d["test_key_sha256"])
                )
                reported = dict(item["test_metrics"])
                for metric in ("log_loss", "multiclass_brier", "accuracy", "macro_ece"):
                    metric_checks.append(_close(float(recomputed[metric]), float(reported[metric])))
                if recomputed["macro_ovr_auc"] is None or reported["macro_ovr_auc"] is None:
                    metric_checks.append(recomputed["macro_ovr_auc"] is reported["macro_ovr_auc"])
                else:
                    metric_checks.append(
                        _close(float(recomputed["macro_ovr_auc"]), float(reported["macro_ovr_auc"]))
                    )
                role_metrics[role].append(recomputed)
                proof.update({"fold_index": fold_index, "role": role})
                artifacts.append(proof)

        aggregates: dict[str, dict[str, object]] = {}
        aggregate_checks: list[bool] = []
        reported_aggregates = dict(benchmark["aggregates"])
        for role, metrics in role_metrics.items():
            rows = sum(int(item["rows"]) for item in metrics)
            auc_values = [
                (float(item["macro_ovr_auc"]), int(item["rows"]))
                for item in metrics
                if item["macro_ovr_auc"] is not None
            ]
            aggregate = {
                "role": role,
                "folds": len(metrics),
                "test_rows": rows,
                "weighted_log_loss": _weighted(
                    [(float(item["log_loss"]), int(item["rows"])) for item in metrics]
                ),
                "weighted_multiclass_brier": _weighted(
                    [(float(item["multiclass_brier"]), int(item["rows"])) for item in metrics]
                ),
                "weighted_accuracy": _weighted(
                    [(float(item["accuracy"]), int(item["rows"])) for item in metrics]
                ),
                "weighted_macro_ovr_auc": None if not auc_values else _weighted(auc_values),
                "weighted_macro_ece": _weighted(
                    [(float(item["macro_ece"]), int(item["rows"])) for item in metrics]
                ),
            }
            aggregates[role] = aggregate
            reported = dict(reported_aggregates[role])
            for metric in (
                "weighted_log_loss",
                "weighted_multiclass_brier",
                "weighted_accuracy",
                "weighted_macro_ece",
            ):
                aggregate_checks.append(_close(float(aggregate[metric]), float(reported[metric])))
            if aggregate["weighted_macro_ovr_auc"] is None or reported["weighted_macro_ovr_auc"] is None:
                aggregate_checks.append(
                    aggregate["weighted_macro_ovr_auc"] is reported["weighted_macro_ovr_auc"]
                )
            else:
                aggregate_checks.append(
                    _close(
                        float(aggregate["weighted_macro_ovr_auc"]),
                        float(reported["weighted_macro_ovr_auc"]),
                    )
                )

        b_primary = aggregates[HISTORICAL_BACKFILL_PRIMARY_B_ROLE]
        c_primary = aggregates[HISTORICAL_BACKFILL_PRIMARY_C_ROLE]
        c_improves_both = (
            float(c_primary["weighted_log_loss"]) < float(b_primary["weighted_log_loss"])
            and float(c_primary["weighted_multiclass_brier"])
            < float(b_primary["weighted_multiclass_brier"])
        )
        independent_decision = (
            "REGISTER_C_AS_VERSIONED_CHALLENGER_EVIDENCE"
            if c_improves_both
            else "RETAIN_ACCEPTED_PHASE10_PRODUCTION_MODEL"
        )
        reported_decision = str(dict(benchmark["primary_selection"])["decision"])
        nested = aggregates[HISTORICAL_BACKFILL_NESTED_C_ROLE]
        checks = {
            "design_contract_exact": design.get("contract_version")
            == GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION,
            "design_fingerprint_exact": design.get("source_fingerprint")
            == HISTORICAL_BACKFILL_ACCEPTED_GATE11D_SOURCE_FINGERPRINT,
            "benchmark_contract_exact": benchmark.get("contract_version")
            == HISTORICAL_BACKFILL_MODEL_BENCHMARK_CONTRACT_VERSION,
            "benchmark_pass": benchmark.get("pass") is True,
            "fold_count_exact": len(benchmark_folds) == 10,
            "artifact_count_exact": len(artifacts) == 30,
            "all_training_sample_counts_exact": all(sample_checks),
            "all_artifact_keys_exact": all(
                item["observation_key_sha256"]
                == str(design_folds[int(item["fold_index"])]["test_key_sha256"])
                for item in artifacts
            ),
            "all_fold_metrics_recompute_exact": all(metric_checks),
            "all_aggregate_metrics_recompute_exact": all(aggregate_checks),
            "selection_rule_recomputed_exact": independent_decision == reported_decision,
            "nested_is_attribution_only": dict(benchmark["nested_history_attribution"])["can_promote_model"]
            is False,
            "nested_does_not_override_primary": independent_decision == reported_decision,
            "final_holdout_not_accessed": benchmark.get("final_holdout_accessed") is False,
            "production_model_replacement_forbidden": benchmark.get(
                "production_model_replacement_allowed"
            )
            is False,
            "production_registry_unchanged": benchmark.get("production_registry_inventory_unchanged")
            is True,
            "production_ml_writes_zero": int(benchmark.get("production_ml_writes", -1)) == 0,
        }
        validation_fingerprint = _stable_hash(
            {
                "contract_version": HISTORICAL_BACKFILL_MODEL_VALIDATION_CONTRACT_VERSION,
                "benchmark_result_fingerprint": benchmark["result_fingerprint"],
                "artifacts": artifacts,
                "aggregates": aggregates,
                "independent_decision": independent_decision,
                "nested_attribution": {
                    "nested_minus_B_log_loss": float(nested["weighted_log_loss"])
                    - float(b_primary["weighted_log_loss"]),
                    "nested_minus_B_multiclass_brier": float(nested["weighted_multiclass_brier"])
                    - float(b_primary["weighted_multiclass_brier"]),
                },
            }
        )
        report: dict[str, object] = {
            "contract_version": HISTORICAL_BACKFILL_MODEL_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": validation_fingerprint,
            "benchmark_result_fingerprint": benchmark["result_fingerprint"],
            "design_source_fingerprint": design["source_fingerprint"],
            "artifacts": artifacts,
            "aggregates": aggregates,
            "independent_primary_decision": {
                "C_improves_both_primary_scores": c_improves_both,
                "decision": independent_decision,
            },
            "nested_history_attribution": {
                "can_promote_model": False,
                "nested_minus_B_log_loss": float(nested["weighted_log_loss"])
                - float(b_primary["weighted_log_loss"]),
                "nested_minus_B_multiclass_brier": float(nested["weighted_multiclass_brier"])
                - float(b_primary["weighted_multiclass_brier"]),
            },
            "checks": checks,
            "production_ml_writes": 0,
            "pass": all(bool(value) for value in checks.values()),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
