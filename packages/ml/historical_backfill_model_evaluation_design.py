from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.baseline_benchmark import MLBaselineBenchmark
from packages.ml.candidate_model_policy import (
    ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
    ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS,
)
from packages.ml.candidate_model_probe import ML_CANDIDATE_MODEL_HASH_BUCKETS
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.historical_backfill_long_history_dataset_validation import (
    GATE11C_DATASET_VALIDATION_CONTRACT_VERSION,
)
from packages.ml.historical_backfill_long_history_datasets import (
    GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION,
    GATE11C_DATASET_BUILD_CONTRACT_VERSION,
    HistoricalBackfillLongHistoryDatasetBuilder,
)
from packages.ml.model_registry import ML_MODEL_REGISTRY_MODEL_FAMILY, ML_MODEL_REGISTRY_SPEC
from packages.ml.walk_forward_policy import (
    ML_WALK_FORWARD_ACCEPTED_CANDIDATE,
    ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
    ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS,
    ML_WALK_FORWARD_FINAL_HOLDOUT_END,
    ML_WALK_FORWARD_FINAL_HOLDOUT_START,
    ML_WALK_FORWARD_MINIMUM_TRAIN_SESSIONS,
    ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
    ML_WALK_FORWARD_PURGE_SESSIONS,
    ML_WALK_FORWARD_STEP_SESSIONS,
    ML_WALK_FORWARD_TEST_SESSIONS,
    ML_WALK_FORWARD_VALIDATION_SESSIONS,
)


GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION = (
    "historical-backfill-ml-evaluation-design-v1-paired-fixed-budget-plus-nested-history"
)
GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT = (
    "e4aa283060d904995a73dc3c6dc06f9b59a383fd5d5fdf64484a603e357c4fa6"
)
GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT = (
    "a5e8d99697e0ffc2979b2616eb9b2ab42a94a5170a5e4e5639fc009aa5e19123"
)
GATE11D_FINGERPRINT_SCOPE = "CONTENT_ONLY_NO_ABSOLUTE_PATHS"
GATE11D_PRIMARY_COMPARISON = "FIXED_1M_TRAIN_BUDGET_PAIRED_POST2021_OOS"
GATE11D_SENSITIVITY_COMPARISON = "NESTED_B_SAMPLE_PLUS_UP_TO_1M_PRESEAM_EXTENSION"
GATE11D_PRIMARY_SELECTION_METRICS = ("log_loss", "multiclass_brier")
GATE11D_DIAGNOSTIC_METRICS = ("accuracy", "macro_ovr_auc", "macro_ece")
GATE11D_FINAL_HOLDOUT_USED_FOR_SELECTION = False
GATE11D_PRODUCTION_MODEL_REPLACEMENT_ALLOWED = False
GATE11D_MODEL_TRAINING_ALLOWED = False
GATE11D_PRODUCTION_ML_WRITES = 0
GATE11D_FIXED_BUDGET_ROWS = ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS
GATE11D_NESTED_EXTENSION_CAP_ROWS = ML_CANDIDATE_MODEL_ACCEPTED_TRAIN_CAP_ROWS


class Gate11DEvaluationDesignError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parquet_list(paths: list[Path]) -> str:
    if not paths:
        raise Gate11DEvaluationDesignError("Gate 11-D requires at least one Parquet path")
    return "[" + ",".join(sql_string(path) for path in paths) + "]"


def _sample_threshold(full_rows: int, target_rows: int) -> int:
    fraction = min(1.0, float(target_rows) / max(1, int(full_rows)))
    return max(
        1,
        min(
            ML_CANDIDATE_MODEL_HASH_BUCKETS,
            int(round(fraction * ML_CANDIDATE_MODEL_HASH_BUCKETS)),
        ),
    )


class HistoricalBackfillModelEvaluationDesign:
    """Gate 11-D read-only preregistration for paired B-vs-C model evaluation.

    The accepted Phase-10 fold calendar is retained so every B/C validation and test
    observation is identical. The primary comparison keeps the accepted one-million-row
    training budget for each candidate. Because independently capped B/C samples change
    composition, a second nested-history sensitivity retains the exact B sample and adds
    only a bounded pre-seam extension. The sensitivity is attribution evidence only and
    cannot itself promote a model because its total training rows can exceed the accepted
    one-million-row registry budget.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.builder = HistoricalBackfillLongHistoryDatasetBuilder(settings)
        self.baseline = MLBaselineBenchmark(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = (
            derived
            / "historical_backfill"
            / "alpaca"
            / "ml_long_history"
            / "v1"
            / "evaluation"
            / "v1"
        )
        self.report_path = self.root / "gate11d_evaluation_design_report.json"
        self.validation_report_path = (
            self.builder.root / "gate11c_dataset_validation_report.json"
        )
        self.production_ml_write_count = 0

    @staticmethod
    def _read_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise Gate11DEvaluationDesignError(f"Gate 11-D requires {label}: {path}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise Gate11DEvaluationDesignError(f"Gate 11-D invalid JSON for {label}: {path}") from exc

    def _load_gate11c(self) -> tuple[dict[str, Any], dict[str, Any], Path, Path, Path]:
        build = self._read_json(self.builder.report_path, "accepted Gate 11-C builder report")
        validation = self._read_json(
            self.validation_report_path, "accepted Gate 11-C validation report"
        )
        if build.get("contract_version") != GATE11C_DATASET_BUILD_CONTRACT_VERSION:
            raise Gate11DEvaluationDesignError("Gate 11-D Gate 11-C builder contract changed")
        if build.get("source_fingerprint") != GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT:
            raise Gate11DEvaluationDesignError("Gate 11-D Gate 11-C builder fingerprint changed")
        if build.get("pass") is not True:
            raise Gate11DEvaluationDesignError("Gate 11-D requires passing Gate 11-C builder")
        if validation.get("contract_version") != GATE11C_DATASET_VALIDATION_CONTRACT_VERSION:
            raise Gate11DEvaluationDesignError("Gate 11-D Gate 11-C validation contract changed")
        if validation.get("source_fingerprint") != GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT:
            raise Gate11DEvaluationDesignError("Gate 11-D Gate 11-C validation fingerprint changed")
        if validation.get("pass") is not True:
            raise Gate11DEvaluationDesignError("Gate 11-D requires passing Gate 11-C validation")

        b = dict(build["B"])
        x = dict(build["C_extension"])
        c = dict(build["C_composite"])
        b_root = self.builder._dataset_root("B", str(b["dataset_id"]))  # noqa: SLF001
        x_root = self.builder._dataset_root("C_extension", str(x["dataset_id"]))  # noqa: SLF001
        c_root = self.builder._dataset_root("C", str(c["dataset_id"]))  # noqa: SLF001
        for root, label in ((b_root, "B"), (x_root, "C-extension"), (c_root, "C")):
            if not (root / "manifest.json").is_file():
                raise Gate11DEvaluationDesignError(f"Gate 11-D missing {label} manifest: {root}")
        return build, validation, b_root, x_root, c_root

    @staticmethod
    def _manifest_paths(root: Path) -> tuple[dict[str, Any], list[Path]]:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        paths = [root / str(item["relative_path"]) for item in manifest.get("partitions", [])]
        if not paths or any(not path.is_file() for path in paths):
            raise Gate11DEvaluationDesignError(f"Gate 11-D physical dataset incomplete: {root}")
        return manifest, paths

    @staticmethod
    def _key_hash(con: Any, source_sql: str, start: str, end: str) -> tuple[int, str]:
        cursor = con.execute(
            f"""
            SELECT observation_key
            FROM {source_sql}
            WHERE session_date BETWEEN DATE '{start}' AND DATE '{end}'
            ORDER BY observation_key
            """
        )
        digest = hashlib.sha256()
        count = 0
        while True:
            rows = cursor.fetchmany(100_000)
            if not rows:
                break
            for row in rows:
                digest.update(str(row[0]).encode("utf-8"))
                digest.update(b"\n")
                count += 1
        return count, digest.hexdigest()

    @staticmethod
    def _count_range(con: Any, source_sql: str, start: str, end: str) -> int:
        return int(
            con.execute(
                f"SELECT count(*) FROM {source_sql} "
                f"WHERE session_date BETWEEN DATE '{start}' AND DATE '{end}'"
            ).fetchone()[0]
        )

    @staticmethod
    def _sample_count(
        con: Any,
        source_sql: str,
        *,
        start: str,
        end: str,
        threshold: int,
    ) -> int:
        return int(
            con.execute(
                f"""
                SELECT count(*) FROM {source_sql}
                WHERE session_date BETWEEN DATE '{start}' AND DATE '{end}'
                  AND (hash(observation_key) % {ML_CANDIDATE_MODEL_HASH_BUCKETS}) < {threshold}
                """
            ).fetchone()[0]
        )

    def run(self) -> dict[str, object]:
        build, validation, b_root, x_root, c_root = self._load_gate11c()
        b_manifest, b_paths = self._manifest_paths(b_root)
        x_manifest, x_paths = self._manifest_paths(x_root)
        c_manifest = self._read_json(c_root / "manifest.json", "Gate 11-C composite manifest")
        if c_manifest.get("contract_version") != GATE11C_COMPOSITE_DATASET_CONTRACT_VERSION:
            raise Gate11DEvaluationDesignError("Gate 11-D composite contract changed")
        if c_manifest.get("physical_C_copy_of_B_rows") != 0:
            raise Gate11DEvaluationDesignError("Gate 11-D requires parent-bound C without copied B")

        accepted_candidate = self.baseline._accepted_candidate()  # noqa: SLF001
        if accepted_candidate.name != ML_WALK_FORWARD_ACCEPTED_CANDIDATE:
            raise Gate11DEvaluationDesignError("Gate 11-D accepted walk-forward candidate changed")
        if accepted_candidate.fold_count != ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT:
            raise Gate11DEvaluationDesignError("Gate 11-D accepted fold count changed")

        b_source = f"read_parquet({_parquet_list(b_paths)}, union_by_name=true)"
        x_source = f"read_parquet({_parquet_list(x_paths)}, union_by_name=true)"
        c_source = f"read_parquet({_parquet_list(b_paths + x_paths)}, union_by_name=true)"
        con = connect_utc(":memory:")
        folds: list[dict[str, object]] = []
        try:
            for fold in accepted_candidate.folds:
                if fold.validation_start >= ML_WALK_FORWARD_FINAL_HOLDOUT_START:
                    raise Gate11DEvaluationDesignError("Gate 11-D validation reaches final holdout")
                if fold.test_end >= ML_WALK_FORWARD_FINAL_HOLDOUT_START:
                    raise Gate11DEvaluationDesignError("Gate 11-D test reaches final holdout")

                b_validation_rows, b_validation_hash = self._key_hash(
                    con, b_source, fold.validation_start, fold.validation_end
                )
                c_validation_rows, c_validation_hash = self._key_hash(
                    con, c_source, fold.validation_start, fold.validation_end
                )
                b_test_rows, b_test_hash = self._key_hash(
                    con, b_source, fold.test_start, fold.test_end
                )
                c_test_rows, c_test_hash = self._key_hash(
                    con, c_source, fold.test_start, fold.test_end
                )

                b_full_train = self._count_range(
                    con, b_source, str(b_manifest["first_session_date"]), fold.train_end
                )
                extension_full_train = self._count_range(
                    con, x_source, str(x_manifest["first_session_date"]), fold.train_end
                )
                c_full_train = b_full_train + extension_full_train

                b_threshold = _sample_threshold(b_full_train, GATE11D_FIXED_BUDGET_ROWS)
                c_threshold = _sample_threshold(c_full_train, GATE11D_FIXED_BUDGET_ROWS)
                nested_x_threshold = _sample_threshold(
                    extension_full_train, GATE11D_NESTED_EXTENSION_CAP_ROWS
                )

                b_fixed_sample = self._sample_count(
                    con,
                    b_source,
                    start=str(b_manifest["first_session_date"]),
                    end=fold.train_end,
                    threshold=b_threshold,
                )
                c_fixed_b_sample = self._sample_count(
                    con,
                    b_source,
                    start=str(b_manifest["first_session_date"]),
                    end=fold.train_end,
                    threshold=c_threshold,
                )
                c_fixed_x_sample = self._sample_count(
                    con,
                    x_source,
                    start=str(x_manifest["first_session_date"]),
                    end=fold.train_end,
                    threshold=c_threshold,
                )
                nested_x_sample = self._sample_count(
                    con,
                    x_source,
                    start=str(x_manifest["first_session_date"]),
                    end=fold.train_end,
                    threshold=nested_x_threshold,
                )

                folds.append(
                    {
                        "fold_index": int(fold.fold_index),
                        "accepted_train_start": fold.train_start,
                        "accepted_train_end": fold.train_end,
                        "B_train_start": str(b_manifest["first_session_date"]),
                        "C_extension_train_start": str(x_manifest["first_session_date"]),
                        "validation_start": fold.validation_start,
                        "validation_end": fold.validation_end,
                        "test_start": fold.test_start,
                        "test_end": fold.test_end,
                        "B_validation_rows": b_validation_rows,
                        "C_validation_rows": c_validation_rows,
                        "validation_key_sha256": b_validation_hash,
                        "validation_key_hash_equal": b_validation_hash == c_validation_hash,
                        "B_test_rows": b_test_rows,
                        "C_test_rows": c_test_rows,
                        "test_key_sha256": b_test_hash,
                        "test_key_hash_equal": b_test_hash == c_test_hash,
                        "B_full_train_rows": b_full_train,
                        "C_extension_full_train_rows": extension_full_train,
                        "C_full_train_rows": c_full_train,
                        "fixed_budget": {
                            "target_rows": GATE11D_FIXED_BUDGET_ROWS,
                            "B_hash_threshold": b_threshold,
                            "C_hash_threshold": c_threshold,
                            "B_sample_rows": b_fixed_sample,
                            "C_B_component_rows": c_fixed_b_sample,
                            "C_extension_component_rows": c_fixed_x_sample,
                            "C_sample_rows": c_fixed_b_sample + c_fixed_x_sample,
                            "composition_changes_by_design": True,
                        },
                        "nested_history_sensitivity": {
                            "B_base_hash_threshold": b_threshold,
                            "B_base_sample_rows": b_fixed_sample,
                            "extension_hash_threshold": nested_x_threshold,
                            "extension_sample_rows": nested_x_sample,
                            "C_nested_sample_rows": b_fixed_sample + nested_x_sample,
                            "B_base_retained_exactly": True,
                            "registry_training_cap_compliant": (
                                b_fixed_sample + nested_x_sample <= GATE11D_FIXED_BUDGET_ROWS
                            ),
                        },
                    }
                )
        finally:
            con.close()

        eval_pairs_exact = all(
            bool(item["validation_key_hash_equal"])
            and bool(item["test_key_hash_equal"])
            and int(item["B_validation_rows"]) == int(item["C_validation_rows"])
            and int(item["B_test_rows"]) == int(item["C_test_rows"])
            for item in folds
        )
        test_dates = [str(item["test_start"]) for item in folds] + [str(item["test_end"]) for item in folds]
        final_holdout_overlap = sum(
            1
            for item in folds
            if str(item["validation_end"]) >= ML_WALK_FORWARD_FINAL_HOLDOUT_START
            or str(item["test_end"]) >= ML_WALK_FORWARD_FINAL_HOLDOUT_START
        )
        nested_cap_compliance = all(
            bool(dict(item["nested_history_sensitivity"])["registry_training_cap_compliant"])
            for item in folds
        )

        fixed_budget_policy = {
            "role": "PRIMARY_PRACTICAL_MODEL_SELECTION",
            "training_budget_rows_per_fold": GATE11D_FIXED_BUDGET_ROWS,
            "sampling": "INDEPENDENT_DETERMINISTIC_OBSERVATION_KEY_HASH_TO_COMMON_ROW_BUDGET",
            "interpretation": "CONTROLS_TRAINING_COMPUTE_BUT_C_REPLACES_SOME_B_ROWS_WITH_OLDER_HISTORY",
            "selection_metrics": list(GATE11D_PRIMARY_SELECTION_METRICS),
            "diagnostic_metrics": list(GATE11D_DIAGNOSTIC_METRICS),
            "selection_rule": (
                "C_MAY_ADVANCE_ONLY_IF_AGGREGATE_LOG_LOSS_AND_BRIER_BOTH_IMPROVE_VS_B; "
                "MIXED_OR_WORSE_PROPER_SCORES_DEFAULT_TO_B"
            ),
        }
        nested_policy = {
            "role": "ATTRIBUTION_SENSITIVITY_ONLY",
            "B_base_sample": "EXACT_PRIMARY_B_HASH_SAMPLE",
            "extension_cap_rows_per_fold": GATE11D_NESTED_EXTENSION_CAP_ROWS,
            "interpretation": "ONLY_ADDS_PRESEAM_ROWS_TO_IDENTICAL_B_BASE_SAMPLE",
            "can_promote_model": False,
            "reason": "TOTAL_TRAINING_ROWS_CAN_EXCEED_ACCEPTED_1M_REGISTRY_CAP",
        }
        experiment = {
            "model_family": ML_MODEL_REGISTRY_MODEL_FAMILY,
            "model_name": ML_CANDIDATE_MODEL_ACCEPTED_MODEL,
            "model_spec": dict(ML_MODEL_REGISTRY_SPEC),
            "predictor_count": len(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "predictor_columns": list(ML_PRODUCTION_CORE_FEATURE_NAMES),
            "walk_forward_policy": ML_WALK_FORWARD_POLICY_CONTRACT_VERSION,
            "walk_forward_candidate": ML_WALK_FORWARD_ACCEPTED_CANDIDATE,
            "minimum_train_sessions": ML_WALK_FORWARD_MINIMUM_TRAIN_SESSIONS,
            "validation_sessions": ML_WALK_FORWARD_VALIDATION_SESSIONS,
            "test_sessions": ML_WALK_FORWARD_TEST_SESSIONS,
            "step_sessions": ML_WALK_FORWARD_STEP_SESSIONS,
            "purge_sessions": ML_WALK_FORWARD_PURGE_SESSIONS,
            "additional_embargo_sessions": ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS,
            "fold_count": len(folds),
            "final_holdout_start": ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            "final_holdout_end": ML_WALK_FORWARD_FINAL_HOLDOUT_END,
            "final_holdout_used_for_selection": GATE11D_FINAL_HOLDOUT_USED_FOR_SELECTION,
            "production_model_replacement_allowed": GATE11D_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
            "model_training_allowed_in_gate11d": GATE11D_MODEL_TRAINING_ALLOWED,
            "primary_fixed_budget": fixed_budget_policy,
            "nested_history_sensitivity": nested_policy,
        }

        checks = {
            "design_contract": True,
            "gate11c_builder_pass": build.get("pass") is True,
            "gate11c_validation_pass": validation.get("pass") is True,
            "gate11c_builder_fingerprint_exact": build.get("source_fingerprint")
            == GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT,
            "gate11c_validation_fingerprint_exact": validation.get("source_fingerprint")
            == GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT,
            "B_manifest_hash_exact": sha256_file(b_root / "manifest.json")
            == str(dict(build["B"])["manifest_sha256"]),
            "extension_manifest_hash_exact": sha256_file(x_root / "manifest.json")
            == str(dict(build["C_extension"])["manifest_sha256"]),
            "composite_manifest_hash_exact": sha256_file(c_root / "manifest.json")
            == str(dict(build["C_composite"])["manifest_sha256"]),
            "model_family_retained": ML_MODEL_REGISTRY_MODEL_FAMILY
            == "sklearn_hist_gradient_boosting",
            "accepted_model_spec_retained": int(ML_MODEL_REGISTRY_SPEC["training_cap_rows"])
            == GATE11D_FIXED_BUDGET_ROWS,
            "core33_predictors_only": len(ML_PRODUCTION_CORE_FEATURE_NAMES) == 33,
            "walk_forward_policy_retained": accepted_candidate.name
            == ML_WALK_FORWARD_ACCEPTED_CANDIDATE,
            "fold_count_retained": len(folds) == ML_WALK_FORWARD_ACCEPTED_FOLD_COUNT,
            "paired_validation_test_keys_exact": eval_pairs_exact,
            "all_evaluation_postseam": all(
                str(item["validation_start"]) > str(x_manifest["last_session_date"])
                and str(item["test_start"]) > str(x_manifest["last_session_date"])
                for item in folds
            ),
            "final_holdout_overlap_zero": final_holdout_overlap == 0,
            "final_holdout_not_used_for_selection": GATE11D_FINAL_HOLDOUT_USED_FOR_SELECTION is False,
            "fixed_budget_primary_registered": fixed_budget_policy["role"]
            == "PRIMARY_PRACTICAL_MODEL_SELECTION",
            "nested_history_attribution_registered": nested_policy["role"]
            == "ATTRIBUTION_SENSITIVITY_ONLY",
            "nested_history_not_registry_cap_compliant": nested_cap_compliance is False,
            "nested_history_cannot_promote": nested_policy["can_promote_model"] is False,
            "model_training_forbidden_in_design_gate": GATE11D_MODEL_TRAINING_ALLOWED is False,
            "production_model_replacement_forbidden": GATE11D_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False,
            "production_ml_writes_zero": self.production_ml_write_count == 0,
        }

        fingerprint_payload = {
            "contract_version": GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION,
            "fingerprint_scope": GATE11D_FINGERPRINT_SCOPE,
            "gate11c_builder_fingerprint": GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT,
            "gate11c_validation_fingerprint": GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT,
            "B_lineage": b_manifest["dataset_lineage_fingerprint"],
            "extension_lineage": x_manifest["dataset_lineage_fingerprint"],
            "C_lineage": c_manifest["dataset_lineage_fingerprint"],
            "experiment": experiment,
            "folds": folds,
            "evaluation_test_date_bounds": [min(test_dates), max(test_dates)],
        }
        source_fingerprint = _stable_hash(fingerprint_payload)
        report: dict[str, object] = {
            "contract_version": GATE11D_EVALUATION_DESIGN_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": source_fingerprint,
            "fingerprint_scope": GATE11D_FINGERPRINT_SCOPE,
            "as_of_date": str(build["as_of_date"]),
            "gate11c_builder_fingerprint": GATE11D_ACCEPTED_GATE11C_BUILDER_FINGERPRINT,
            "gate11c_validation_fingerprint": GATE11D_ACCEPTED_GATE11C_VALIDATION_FINGERPRINT,
            "datasets": {
                "B_dataset_id": b_manifest["dataset_id"],
                "B_lineage": b_manifest["dataset_lineage_fingerprint"],
                "extension_dataset_id": x_manifest["dataset_id"],
                "extension_lineage": x_manifest["dataset_lineage_fingerprint"],
                "C_dataset_id": c_manifest["dataset_id"],
                "C_lineage": c_manifest["dataset_lineage_fingerprint"],
            },
            "experiment": experiment,
            "folds": folds,
            "paired_evaluation": {
                "all_pairs_exact": eval_pairs_exact,
                "folds": len(folds),
                "first_validation": min(str(item["validation_start"]) for item in folds),
                "last_test": max(str(item["test_end"]) for item in folds),
                "final_holdout_overlap_windows": final_holdout_overlap,
            },
            "checks": checks,
            "production_ml_writes": self.production_ml_write_count,
            "pass": all(bool(value) for value in checks.values()),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
