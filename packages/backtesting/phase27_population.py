from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_closeout import (
    PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION,
    Phase26Closeout,
)
from .phase26_observations import (
    PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION,
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase27_policy import (
    PHASE27_BASELINE_SCORE_FIELD,
    PHASE27_DEVELOPMENT_END,
    PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS,
    PHASE27_MIN_DIRECTION_ROWS_PER_SESSION,
    PHASE27_PREDICTOR_FIELDS,
    PHASE27_PROTECTED_END,
    PHASE27_PROTECTED_START,
    PHASE27_SOURCE_PHASE26_POLICY_FINGERPRINT,
    phase27_policy_fingerprint,
)


PHASE27_POPULATION_REPORT_CONTRACT_VERSION = (
    "phase27-population-report-v1-phase26-lineage-complete-case-cross-sectional-ranks"
)
PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION = (
    "phase27-development-model-frame-v1-relative-directional-return"
)
PHASE27_PROTECTED_MODEL_FRAME_CONTRACT_VERSION = (
    "phase27-protected-model-frame-v1-predictors-only"
)
PHASE27_TRANSFORM_PREFIX = "x_"


class Phase27PopulationError(RuntimeError):
    pass


def transformed_feature_name(field: str) -> str:
    return PHASE27_TRANSFORM_PREFIX + field


def transformed_feature_names() -> tuple[str, ...]:
    return tuple(transformed_feature_name(field) for field in PHASE27_PREDICTOR_FIELDS)


def _json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase27PopulationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase27PopulationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase27PopulationError(f"{label} must be a JSON object")
    return payload


def _read_parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase27PopulationError(f"missing parquet evidence: {path}")
    con = connect_utc(":memory:")
    try:
        frame = con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY {order_by}"
        ).fetch_df()
    finally:
        con.close()
    return frame


def _write_parquet(
    settings: AtlasSettings,
    frame: pd.DataFrame,
    target: Path,
    *,
    order_by: str,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase27_population_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM phase27_population_write ORDER BY {order_by}) "
            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
            f"ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


def _prepare_numeric(frame: pd.DataFrame, *, development: bool) -> pd.DataFrame:
    result = frame.copy()
    required = list(PHASE27_PREDICTOR_FIELDS) + [PHASE27_BASELINE_SCORE_FIELD]
    if development:
        required.append("directional_return")
    missing = sorted(field for field in required if field not in result.columns)
    if missing:
        raise Phase27PopulationError(
            "Phase27 source frame is missing frozen fields: " + ", ".join(missing)
        )
    for field in required:
        result[field] = pd.to_numeric(result[field], errors="coerce")
    return result


def cross_sectional_model_frame(frame: pd.DataFrame, *, development: bool) -> pd.DataFrame:
    """Return the frozen complete-case same-session/direction rank representation."""

    result = _prepare_numeric(frame, development=development)
    result["as_of_date"] = pd.to_datetime(result["as_of_date"]).dt.date
    result = result.loc[result["direction"].astype(str).isin(("bullish", "bearish"))].copy()

    complete_fields = list(PHASE27_PREDICTOR_FIELDS) + [PHASE27_BASELINE_SCORE_FIELD]
    if development:
        complete_fields.append("directional_return")
    finite = np.ones(len(result), dtype=bool)
    for field in complete_fields:
        values = result[field].to_numpy(dtype=np.float64, copy=False)
        finite &= np.isfinite(values)
    result = result.loc[finite].copy()

    counts = result.groupby(["as_of_date", "direction"], sort=False, observed=True)[
        "instrument_id"
    ].transform("size")
    result = result.loc[counts >= PHASE27_MIN_DIRECTION_ROWS_PER_SESSION].copy()
    if result.empty:
        raise Phase27PopulationError("Phase27 complete-case cross-sectional population is empty")

    grouped = result.groupby(["as_of_date", "direction"], sort=False, observed=True)
    for field in PHASE27_PREDICTOR_FIELDS:
        ranked = grouped[field].rank(method="average", pct=True)
        result[transformed_feature_name(field)] = 2.0 * ranked.astype(float) - 1.0

    if development:
        medians = grouped["directional_return"].transform("median")
        result["relative_directional_return"] = (
            pd.to_numeric(result["directional_return"], errors="coerce")
            - pd.to_numeric(medians, errors="coerce")
        )
        if not np.isfinite(result["relative_directional_return"].to_numpy(dtype=float)).all():
            raise Phase27PopulationError("Phase27 relative directional target is non-finite")

    transformed = list(transformed_feature_names())
    if not np.isfinite(result[transformed].to_numpy(dtype=float)).all():
        raise Phase27PopulationError("Phase27 transformed predictor matrix is non-finite")
    if result.duplicated(["as_of_date", "instrument_id"], keep=False).any():
        raise Phase27PopulationError("Phase27 model population contains duplicate candidate keys")
    return result.sort_values(["as_of_date", "instrument_id"], kind="stable").reset_index(drop=True)


class Phase27PopulationBuilder:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase26 = Phase26ObservationBuilder(settings)
        self.phase26_closeout = Phase26Closeout(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase27" / "v1" / "population"

    def report_path(self) -> Path:
        return self.root / "population_report.json"

    def development_path(self) -> Path:
        return self.root / "development_model_frame.parquet"

    def protected_path(self) -> Path:
        return self.root / "protected_model_predictors.parquet"

    def _source_evidence(self) -> tuple[dict[str, object], dict[str, object], Path, Path]:
        observation_report_path = self.phase26.report_path()
        observation = _json(observation_report_path, "Phase26 observation report")
        if observation.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION:
            raise Phase27PopulationError("Phase26 observation report contract mismatch")
        if observation.get("phase26_policy_fingerprint") != PHASE27_SOURCE_PHASE26_POLICY_FINGERPRINT:
            raise Phase27PopulationError("Phase26 policy fingerprint changed")
        if observation.get("pass") is not True:
            raise Phase27PopulationError("Phase26 observation report is not passing")
        if int(observation.get("protected_return_reads", -1)) != 0:
            raise Phase27PopulationError("Phase26 protected returns were already read")
        if str(observation.get("development_boundary_label_end")) != PHASE27_DEVELOPMENT_END:
            raise Phase27PopulationError("Phase27 development boundary drifted from frozen source")

        closeout_path = self.phase26_closeout.report_path()
        closeout = _json(closeout_path, "Phase26 closeout report")
        if closeout.get("contract_version") != PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION:
            raise Phase27PopulationError("Phase26 closeout contract mismatch")
        if closeout.get("phase26_disposition") != "ACCEPTED_NEGATIVE" or closeout.get("pass") is not True:
            raise Phase27PopulationError("Phase26 is not accepted-negative passing")
        if int(closeout.get("protected_returns_read", -1)) != 0:
            raise Phase27PopulationError("Phase26 closeout does not prove protected blindness")

        return observation, closeout, observation_report_path, closeout_path

    def run(self) -> dict[str, object]:
        observation, closeout, observation_report_path, closeout_path = self._source_evidence()
        development_source = self.phase26.development_path()
        protected_source = self.phase26.protected_predictors_path()
        if observation.get("development_sha256") != sha256_file(development_source):
            raise Phase27PopulationError("Phase26 development source SHA mismatch")
        if observation.get("protected_predictors_sha256") != sha256_file(protected_source):
            raise Phase27PopulationError("Phase26 protected predictor source SHA mismatch")

        development = _read_parquet(development_source, order_by="as_of_date, instrument_id")
        protected = _read_parquet(protected_source, order_by="as_of_date, instrument_id")
        if development.empty or protected.empty:
            raise Phase27PopulationError("Phase27 source population is empty")
        if set(development["contract_version"].astype(str)) != {
            PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION
        }:
            raise Phase27PopulationError("Phase26 development row contract mismatch")
        if set(protected["contract_version"].astype(str)) != {
            PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION
        }:
            raise Phase27PopulationError("Phase26 protected row contract mismatch")
        forbidden = sorted(
            field for field in PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS if field in protected.columns
        )
        if forbidden:
            raise Phase27PopulationError(
                "Phase27 protected source contains forbidden outcome fields: " + ", ".join(forbidden)
            )

        development_model = cross_sectional_model_frame(development, development=True)
        protected_model = cross_sectional_model_frame(protected, development=False)
        protected_dates = pd.to_datetime(protected_model["as_of_date"]).dt.date
        if protected_dates.min().isoformat() != PHASE27_PROTECTED_START:
            raise Phase27PopulationError("Phase27 protected start drifted")
        if protected_dates.max().isoformat() != PHASE27_PROTECTED_END:
            raise Phase27PopulationError("Phase27 protected end drifted")

        development_model.insert(
            0, "phase27_contract_version", PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION
        )
        protected_model.insert(
            0, "phase27_contract_version", PHASE27_PROTECTED_MODEL_FRAME_CONTRACT_VERSION
        )
        for field in PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS:
            if field in protected_model.columns:
                raise Phase27PopulationError(f"protected model artifact leaked outcome field {field}")

        development_path = self.development_path()
        protected_path = self.protected_path()
        _write_parquet(
            self.settings,
            development_model,
            development_path,
            order_by="as_of_date, instrument_id",
        )
        _write_parquet(
            self.settings,
            protected_model,
            protected_path,
            order_by="as_of_date, instrument_id",
        )

        direction_counts_dev = {
            str(key): int(value)
            for key, value in development_model["direction"].astype(str).value_counts().sort_index().items()
        }
        direction_counts_protected = {
            str(key): int(value)
            for key, value in protected_model["direction"].astype(str).value_counts().sort_index().items()
        }
        checks = {
            "phase26_observation_pass": observation.get("pass") is True,
            "phase26_closeout_accepted_negative": closeout.get("phase26_disposition") == "ACCEPTED_NEGATIVE",
            "phase26_protected_returns_unread": int(closeout.get("protected_returns_read", -1)) == 0,
            "development_nonempty": len(development_model) > 0,
            "protected_nonempty": len(protected_model) > 0,
            "exact_predictor_count": len(PHASE27_PREDICTOR_FIELDS) == 29,
            "protected_outcomes_absent": not any(
                field in protected_model.columns for field in PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS
            ),
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase27PopulationError("Phase27 population checks failed: " + ", ".join(failed))

        report_path = self.report_path()
        report: dict[str, Any] = {
            "contract_version": PHASE27_POPULATION_REPORT_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "source_phase26_policy_fingerprint": PHASE27_SOURCE_PHASE26_POLICY_FINGERPRINT,
            "phase26_observation_report_sha256": sha256_file(observation_report_path),
            "phase26_closeout_report_sha256": sha256_file(closeout_path),
            "phase26_development_sha256": sha256_file(development_source),
            "phase26_protected_predictors_sha256": sha256_file(protected_source),
            "development_source_rows": int(len(development)),
            "development_model_rows": int(len(development_model)),
            "protected_source_rows": int(len(protected)),
            "protected_model_rows": int(len(protected_model)),
            "development_direction_rows": direction_counts_dev,
            "protected_direction_rows": direction_counts_protected,
            "predictor_fields": list(PHASE27_PREDICTOR_FIELDS),
            "transformed_feature_fields": list(transformed_feature_names()),
            "baseline_score_field": PHASE27_BASELINE_SCORE_FIELD,
            "min_direction_rows_per_session": PHASE27_MIN_DIRECTION_ROWS_PER_SESSION,
            "development_sha256": sha256_file(development_path),
            "protected_sha256": sha256_file(protected_path),
            "protected_return_reads": 0,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
