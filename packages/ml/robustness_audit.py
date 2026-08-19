from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.calibration_policy import (
    ML_CALIBRATION_ACCEPTED_METHOD,
    ML_CALIBRATION_ACCEPTED_MODEL,
    ML_CALIBRATION_ACCEPTED_OOS_ROWS,
    ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED,
    ML_CALIBRATION_POLICY_ACCEPTED,
    ML_CALIBRATION_POLICY_CONTRACT_VERSION,
    ML_CALIBRATION_RAW_BRIER,
    ML_CALIBRATION_RAW_ECE,
    ML_CALIBRATION_RAW_LOG_LOSS,
    ML_CALIBRATION_RAW_MACRO_AUC,
)
from packages.ml.candidate_model_benchmark import (
    ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION,
    MLCandidateModelBenchmark,
)
from packages.ml.candidate_model_policy import (
    ML_CANDIDATE_MODEL_ACCEPTED_FOLDS,
    ML_CANDIDATE_MODEL_POLICY_ACCEPTED,
)
from packages.ml.evaluation import ProbabilityMetrics, probability_metrics, validate_probabilities
from packages.ml.label_policy import ML_PREDICTION_LABEL_CLASSES, ML_PREDICTION_LABEL_PROBABILITY_FIELDS
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START


ML_ROBUSTNESS_AUDIT_CONTRACT_VERSION = (
    "ml-robustness-audit-v1-raw-hgb-oos-market-liquidity-volatility-direction-time"
)
ML_ROBUSTNESS_AUDIT_STATUS = "EVIDENCE_ONLY"
ML_ROBUSTNESS_SOURCE_PROBABILITIES = "GATE9_RAW_TEST_ARTIFACTS"
ML_ROBUSTNESS_MIN_SUPPORTED_ROWS = 25_000
ML_ROBUSTNESS_MIN_SUPPORTED_FOLDS = 2
ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED = False

ML_ROBUSTNESS_LIQUIDITY_BUCKETS = (
    "250K_TO_1M",
    "1M_TO_5M",
    "5M_TO_25M",
    "25M_PLUS",
)
ML_ROBUSTNESS_VOLATILITY_BUCKETS = (
    "LT_1PCT",
    "1_TO_2PCT",
    "2_TO_4PCT",
    "4PCT_PLUS",
)
ML_ROBUSTNESS_CONFIDENCE_BUCKETS = (
    "LT_50PCT",
    "50_TO_60PCT",
    "60_TO_70PCT",
    "70PCT_PLUS",
)
ML_ROBUSTNESS_SEGMENT_FAMILIES = (
    "market_regime_composite",
    "market_regime_structure",
    "market_regime_momentum",
    "market_regime_volatility",
    "market_regime_efficiency",
    "market_regime_participation",
    "liquidity_bucket",
    "volatility_bucket",
    "predicted_class",
    "actual_class",
    "confidence_bucket",
    "calendar_year",
)
ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS = (
    "sector_regime",
    "ticker_regime",
    "risk_mode",
    "security_type",
)
ML_ROBUSTNESS_UNAVAILABLE_REASON = (
    "NOT_PRESENT_IN_ACCEPTED_GATE6_POINT_IN_TIME_EVALUATION_METADATA"
)


@dataclass(frozen=True, slots=True)
class RobustnessFoldSegmentEvidence:
    family: str
    value: str
    fold_index: int
    rows: int
    down_rows: int
    neutral_rows: int
    up_rows: int
    metrics: ProbabilityMetrics


@dataclass(frozen=True, slots=True)
class RobustnessAggregateEvidence:
    family: str
    value: str
    rows: int
    fold_count: int
    support_status: str
    down_fraction: float
    neutral_fraction: float
    up_fraction: float
    weighted_log_loss: float
    weighted_multiclass_brier: float
    weighted_accuracy: float
    weighted_macro_ovr_auc: float | None
    auc_coverage_rows: int
    weighted_macro_ece: float
    log_loss_delta_vs_global: float
    brier_delta_vs_global: float
    auc_delta_vs_global: float | None
    ece_delta_vs_global: float


@dataclass(frozen=True, slots=True)
class MLRobustnessAuditReport:
    contract_version: str
    generated_at_utc: str
    status: str
    calibration_policy_contract: str
    accepted_calibration_method: str
    accepted_model: str
    gate9_benchmark_contract: str
    source_probabilities: str
    total_oos_rows: int
    fold_count: int
    market_context_rows: int
    market_context_fraction: float
    segment_families: tuple[str, ...]
    unavailable_segments: tuple[str, ...]
    unavailable_reason: str
    minimum_supported_rows: int
    minimum_supported_folds: int
    final_holdout_start: str
    final_holdout_accessed: bool
    fold_segment_evidence: tuple[RobustnessFoldSegmentEvidence, ...]
    aggregate_evidence: tuple[RobustnessAggregateEvidence, ...]
    wall_seconds: float
    report_path: str


def _weighted(values: list[tuple[float, int]]) -> float:
    total = sum(weight for _, weight in values)
    if total <= 0:
        raise ValueError("robustness metric has no rows")
    return float(sum(value * weight for value, weight in values) / total)


def _liquidity_bucket(values: pd.Series) -> pd.Series:
    x = values.to_numpy(dtype=np.float64)
    labels = np.select(
        [x < 1_000_000.0, x < 5_000_000.0, x < 25_000_000.0],
        ML_ROBUSTNESS_LIQUIDITY_BUCKETS[:3],
        default=ML_ROBUSTNESS_LIQUIDITY_BUCKETS[3],
    )
    return pd.Series(labels, index=values.index, dtype="object")


def _volatility_bucket(values: pd.Series) -> pd.Series:
    x = values.to_numpy(dtype=np.float64)
    labels = np.select(
        [x < 0.01, x < 0.02, x < 0.04],
        ML_ROBUSTNESS_VOLATILITY_BUCKETS[:3],
        default=ML_ROBUSTNESS_VOLATILITY_BUCKETS[3],
    )
    return pd.Series(labels, index=values.index, dtype="object")


def _confidence_bucket(probabilities: np.ndarray) -> np.ndarray:
    confidence = np.max(probabilities, axis=1)
    return np.select(
        [confidence < 0.50, confidence < 0.60, confidence < 0.70],
        ML_ROBUSTNESS_CONFIDENCE_BUCKETS[:3],
        default=ML_ROBUSTNESS_CONFIDENCE_BUCKETS[3],
    )


class MLRobustnessAudit:
    """Audit the accepted raw HGB probabilities across point-in-time-safe OOS segments.

    Gate 11 does not retrain or recalibrate the model. It reads the hash-recorded Gate 9
    test predictions selected by Gate 10's raw/no-calibration policy and joins them by
    stable observation key to the immutable Gate 6 dataset. Only metadata already in
    that dataset may define a segment. Snapshot-only sector/ticker/risk/security-type
    fields remain explicitly unavailable rather than being projected backward.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        if not ML_CANDIDATE_MODEL_POLICY_ACCEPTED:
            raise RuntimeError("Gate 11 requires accepted Gate 9 candidate evidence")
        if not ML_CALIBRATION_POLICY_ACCEPTED:
            raise RuntimeError("Gate 11 requires accepted Gate 10 calibration policy")
        if ML_CALIBRATION_ACCEPTED_METHOD != "raw":
            raise RuntimeError("Gate 11 v1 contract expects raw Gate 9 probabilities")
        if ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED:
            raise RuntimeError("Gate 10 evidence touched the protected final holdout")
        self.settings = settings
        self.gate9 = MLCandidateModelBenchmark(settings)

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "robustness_audit" / "2026" / "2026-08-14.json"

    def _gate9_payload(self) -> dict[str, object]:
        path = self.gate9.report_path()
        if not path.exists():
            raise FileNotFoundError(f"Gate 11 requires Gate 9 report: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("contract_version") != ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION:
            raise RuntimeError("Gate 11 Gate 9 benchmark contract mismatch")
        if payload.get("final_holdout_accessed") is not False:
            raise RuntimeError("Gate 11 refuses evidence that accessed the final holdout")
        if int(payload.get("fold_count", 0)) != ML_CANDIDATE_MODEL_ACCEPTED_FOLDS:
            raise RuntimeError("Gate 11 Gate 9 fold count mismatch")
        if int(payload.get("total_test_rows", 0)) != ML_CALIBRATION_ACCEPTED_OOS_ROWS:
            raise RuntimeError("Gate 11 Gate 9 OOS row count mismatch")
        return payload

    @staticmethod
    def _fold_item(payload: dict[str, object], fold_index: int) -> dict[str, object]:
        items = payload.get("fold_evidence")
        if not isinstance(items, list):
            raise RuntimeError("Gate 9 report has no fold evidence")
        matches = [
            item for item in items
            if isinstance(item, dict)
            and item.get("model_name") == ML_CALIBRATION_ACCEPTED_MODEL
            and int(item.get("fold_index", -1)) == fold_index
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Gate 11 expected one accepted Gate 9 item for fold {fold_index}")
        return matches[0]

    def _fold_frame(self, item: dict[str, object]) -> pd.DataFrame:
        artifact = item.get("test_artifact")
        if not isinstance(artifact, dict):
            raise RuntimeError("Gate 9 fold item is missing test artifact")
        source = self.gate9.report_path().parent / str(artifact["relative_path"])
        if not source.exists():
            raise FileNotFoundError(source)
        if sha256_file(source) != str(artifact["sha256"]):
            raise RuntimeError(f"Gate 11 Gate 9 artifact hash mismatch: {source}")

        fields = ", ".join(f"p.{field}" for field in ML_PREDICTION_LABEL_PROBABILITY_FIELDS)
        context = ", ".join(
            f"d.{field}"
            for field in (
                "market_regime_available",
                "market_regime_composite",
                "market_regime_structure",
                "market_regime_momentum",
                "market_regime_volatility",
                "market_regime_efficiency",
                "market_regime_participation",
                "dollar_volume",
                "natr_14",
            )
        )
        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"""
                SELECT
                    p.fold_index,
                    p.observation_key,
                    p.session_date,
                    p.symbol,
                    p.instrument_id,
                    p.actual_label,
                    {fields},
                    {context}
                FROM read_parquet({sql_string(source.as_posix())}) AS p
                INNER JOIN read_parquet(
                    {sql_string(self.gate9.baseline.dataset_glob)},
                    hive_partitioning=true
                ) AS d
                  ON d.observation_key = p.observation_key
                 AND d.session_date = p.session_date
                 AND d.symbol = p.symbol
                 AND d.instrument_id = p.instrument_id
                ORDER BY p.session_date, p.symbol, p.instrument_id
                """
            ).fetch_df()
        finally:
            con.close()

        expected = int(artifact["row_count"])
        if len(frame) != expected:
            raise RuntimeError(
                f"Gate 11 stable-key join does not reconcile: {len(frame):,} != {expected:,}"
            )
        if frame["observation_key"].duplicated().any():
            raise RuntimeError("Gate 11 stable-key join produced duplicate observations")
        if not bool(np.isfinite(frame["dollar_volume"].to_numpy(dtype=np.float64)).all()):
            raise RuntimeError("Gate 11 liquidity segmentation contains non-finite dollar volume")
        if not bool(np.isfinite(frame["natr_14"].to_numpy(dtype=np.float64)).all()):
            raise RuntimeError("Gate 11 volatility segmentation contains non-finite NATR")
        return frame

    @staticmethod
    def _decorate(frame: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
        probabilities = validate_probabilities(
            frame.loc[:, list(ML_PREDICTION_LABEL_PROBABILITY_FIELDS)].to_numpy(dtype=np.float64)
        )
        result = frame.copy()
        class_array = np.asarray(ML_PREDICTION_LABEL_CLASSES, dtype=object)
        result["predicted_class"] = class_array[np.argmax(probabilities, axis=1)]
        result["actual_class"] = result["actual_label"].astype(str)
        result["liquidity_bucket"] = _liquidity_bucket(result["dollar_volume"])
        result["volatility_bucket"] = _volatility_bucket(result["natr_14"])
        result["confidence_bucket"] = _confidence_bucket(probabilities)
        result["calendar_year"] = pd.to_datetime(result["session_date"]).dt.year.astype(str)
        for column in ML_ROBUSTNESS_SEGMENT_FAMILIES[:6]:
            result[column] = result[column].where(result[column].notna(), "MISSING").astype(str)
        return result, probabilities

    @staticmethod
    def _fold_segments(
        frame: pd.DataFrame,
        probabilities: np.ndarray,
        fold_index: int,
    ) -> list[RobustnessFoldSegmentEvidence]:
        evidence: list[RobustnessFoldSegmentEvidence] = []
        for family in ML_ROBUSTNESS_SEGMENT_FAMILIES:
            groups = frame.groupby(family, sort=True, dropna=False).indices
            for raw_value, indices in groups.items():
                idx = np.asarray(indices, dtype=np.int64)
                labels = frame.iloc[idx]["actual_label"].to_numpy()
                metrics = probability_metrics(labels, probabilities[idx])
                down = int(np.sum(labels == "DOWN"))
                neutral = int(np.sum(labels == "NEUTRAL"))
                up = int(np.sum(labels == "UP"))
                value = "MISSING" if pd.isna(raw_value) else str(raw_value)
                evidence.append(
                    RobustnessFoldSegmentEvidence(
                        family=family,
                        value=value,
                        fold_index=int(fold_index),
                        rows=int(len(idx)),
                        down_rows=down,
                        neutral_rows=neutral,
                        up_rows=up,
                        metrics=metrics,
                    )
                )
        return evidence

    @staticmethod
    def _aggregate(
        evidence: list[RobustnessFoldSegmentEvidence],
    ) -> tuple[RobustnessAggregateEvidence, ...]:
        grouped: dict[tuple[str, str], list[RobustnessFoldSegmentEvidence]] = {}
        for item in evidence:
            grouped.setdefault((item.family, item.value), []).append(item)

        output: list[RobustnessAggregateEvidence] = []
        for (family, value), items in sorted(grouped.items()):
            rows = sum(item.rows for item in items)
            down = sum(item.down_rows for item in items)
            neutral = sum(item.neutral_rows for item in items)
            up = sum(item.up_rows for item in items)
            auc_values = [
                (float(item.metrics.macro_ovr_auc), item.rows)
                for item in items
                if item.metrics.macro_ovr_auc is not None
            ]
            auc = None if not auc_values else _weighted(auc_values)
            support = (
                "SUPPORTED"
                if rows >= ML_ROBUSTNESS_MIN_SUPPORTED_ROWS
                and len(items) >= ML_ROBUSTNESS_MIN_SUPPORTED_FOLDS
                else "LOW_SUPPORT"
            )
            output.append(
                RobustnessAggregateEvidence(
                    family=family,
                    value=value,
                    rows=rows,
                    fold_count=len(items),
                    support_status=support,
                    down_fraction=down / rows,
                    neutral_fraction=neutral / rows,
                    up_fraction=up / rows,
                    weighted_log_loss=_weighted([(item.metrics.log_loss, item.rows) for item in items]),
                    weighted_multiclass_brier=_weighted(
                        [(item.metrics.multiclass_brier, item.rows) for item in items]
                    ),
                    weighted_accuracy=_weighted([(item.metrics.accuracy, item.rows) for item in items]),
                    weighted_macro_ovr_auc=auc,
                    auc_coverage_rows=sum(weight for _, weight in auc_values),
                    weighted_macro_ece=_weighted([(item.metrics.macro_ece, item.rows) for item in items]),
                    log_loss_delta_vs_global=(
                        _weighted([(item.metrics.log_loss, item.rows) for item in items])
                        - ML_CALIBRATION_RAW_LOG_LOSS
                    ),
                    brier_delta_vs_global=(
                        _weighted([(item.metrics.multiclass_brier, item.rows) for item in items])
                        - ML_CALIBRATION_RAW_BRIER
                    ),
                    auc_delta_vs_global=(None if auc is None else auc - ML_CALIBRATION_RAW_MACRO_AUC),
                    ece_delta_vs_global=(
                        _weighted([(item.metrics.macro_ece, item.rows) for item in items])
                        - ML_CALIBRATION_RAW_ECE
                    ),
                )
            )
        return tuple(output)

    def run(self, progress=None) -> MLRobustnessAuditReport:
        started = perf_counter()
        payload = self._gate9_payload()
        fold_evidence: list[RobustnessFoldSegmentEvidence] = []
        total_rows = 0
        market_context_rows = 0

        for fold_index in range(1, ML_CANDIDATE_MODEL_ACCEPTED_FOLDS + 1):
            item = self._fold_item(payload, fold_index)
            frame = self._fold_frame(item)
            decorated, probabilities = self._decorate(frame)
            total_rows += len(decorated)
            market_context_rows += int(decorated["market_regime_available"].fillna(False).astype(bool).sum())
            if progress is not None:
                progress(
                    f"fold {fold_index}/{ML_CANDIDATE_MODEL_ACCEPTED_FOLDS}: "
                    f"rows={len(decorated):,} market_context="
                    f"{int(decorated['market_regime_available'].fillna(False).astype(bool).sum()):,}"
                )
            fold_evidence.extend(self._fold_segments(decorated, probabilities, fold_index))

        if total_rows != ML_CALIBRATION_ACCEPTED_OOS_ROWS:
            raise RuntimeError(
                f"Gate 11 OOS rows do not reconcile: {total_rows:,} != {ML_CALIBRATION_ACCEPTED_OOS_ROWS:,}"
            )

        report = MLRobustnessAuditReport(
            contract_version=ML_ROBUSTNESS_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            status=ML_ROBUSTNESS_AUDIT_STATUS,
            calibration_policy_contract=ML_CALIBRATION_POLICY_CONTRACT_VERSION,
            accepted_calibration_method=ML_CALIBRATION_ACCEPTED_METHOD,
            accepted_model=ML_CALIBRATION_ACCEPTED_MODEL,
            gate9_benchmark_contract=ML_CANDIDATE_MODEL_BENCHMARK_CONTRACT_VERSION,
            source_probabilities=ML_ROBUSTNESS_SOURCE_PROBABILITIES,
            total_oos_rows=total_rows,
            fold_count=ML_CANDIDATE_MODEL_ACCEPTED_FOLDS,
            market_context_rows=market_context_rows,
            market_context_fraction=market_context_rows / total_rows,
            segment_families=ML_ROBUSTNESS_SEGMENT_FAMILIES,
            unavailable_segments=ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS,
            unavailable_reason=ML_ROBUSTNESS_UNAVAILABLE_REASON,
            minimum_supported_rows=ML_ROBUSTNESS_MIN_SUPPORTED_ROWS,
            minimum_supported_folds=ML_ROBUSTNESS_MIN_SUPPORTED_FOLDS,
            final_holdout_start=ML_WALK_FORWARD_FINAL_HOLDOUT_START,
            final_holdout_accessed=ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED,
            fold_segment_evidence=tuple(fold_evidence),
            aggregate_evidence=self._aggregate(fold_evidence),
            wall_seconds=perf_counter() - started,
            report_path=str(self.report_path()),
        )
        atomic_write_text(
            self.report_path(),
            json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
        )
        return report
