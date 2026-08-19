from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.dataset_policy import (
    ML_TRAINING_DATASET_ACCEPTED_CLASS_ROWS,
    ML_TRAINING_DATASET_ACCEPTED_DISTINCT_KEYS,
    ML_TRAINING_DATASET_ACCEPTED_ID,
    ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256,
    ML_TRAINING_DATASET_ACCEPTED_PARTITION_SHA256,
    ML_TRAINING_DATASET_ACCEPTED_ROWS,
)
from packages.ml.datasets import MLTrainingDatasetManifest
from packages.ml.label_policy import ML_PREDICTION_LABEL_HORIZON_SESSIONS


ML_WALK_FORWARD_PROBE_CONTRACT_VERSION = (
    "ml-walk-forward-probe-v1-expanding-session-folds-purged-final-holdout"
)
ML_WALK_FORWARD_SPLIT_UNIT = "EXCHANGE_SESSION_CROSS_SECTION"
ML_WALK_FORWARD_RANDOM_ROW_SPLIT_ALLOWED = False
ML_WALK_FORWARD_PURGE_SESSIONS = ML_PREDICTION_LABEL_HORIZON_SESSIONS
ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS = 0
ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS = 63
ML_WALK_FORWARD_FINAL_HOLDOUT_ROLE = "UNTOUCHED_GATE13_ACCEPTANCE"
ML_WALK_FORWARD_POLICY_LOCKED = True


@dataclass(frozen=True, slots=True)
class WalkForwardCandidateSpec:
    name: str
    minimum_train_sessions: int
    validation_sessions: int
    test_sessions: int
    step_sessions: int


ML_WALK_FORWARD_CANDIDATE_SPECS = (
    WalkForwardCandidateSpec("quarterly-train252", 252, 63, 63, 63),
    WalkForwardCandidateSpec("quarterly-train378", 378, 63, 63, 63),
    WalkForwardCandidateSpec("quarterly-train504", 504, 63, 63, 63),
    WalkForwardCandidateSpec("halfyear-train252", 252, 126, 126, 126),
)


@dataclass(frozen=True, slots=True)
class SessionClassEvidence:
    session_date: str
    rows: int
    down_rows: int
    neutral_rows: int
    up_rows: int


@dataclass(frozen=True, slots=True)
class WalkForwardFoldEvidence:
    fold_index: int
    train_start: str
    train_end: str
    train_sessions: int
    train_rows: int
    purge1_start: str
    purge1_end: str
    validation_start: str
    validation_end: str
    validation_sessions: int
    validation_rows: int
    purge2_start: str
    purge2_end: str
    test_start: str
    test_end: str
    test_sessions: int
    test_rows: int
    test_down_fraction: float
    test_neutral_fraction: float
    test_up_fraction: float


@dataclass(frozen=True, slots=True)
class WalkForwardCandidateEvidence:
    name: str
    minimum_train_sessions: int
    validation_sessions: int
    test_sessions: int
    step_sessions: int
    fold_count: int
    first_test_date: str | None
    last_test_date: str | None
    minimum_train_rows: int
    maximum_train_rows: int
    total_test_rows: int
    distinct_test_sessions: int
    test_down_fraction_range: float
    test_neutral_fraction_range: float
    test_up_fraction_range: float
    folds: tuple[WalkForwardFoldEvidence, ...]


@dataclass(frozen=True, slots=True)
class MLWalkForwardProbeReport:
    contract_version: str
    generated_at_utc: str
    dataset_id: str
    dataset_lineage_sha256: str
    wall_seconds: float
    probe_status: str
    split_unit: str
    random_row_split_allowed: bool
    label_horizon_sessions: int
    purge_sessions: int
    additional_embargo_sessions: int
    final_holdout_sessions: int
    final_holdout_role: str
    dataset_sessions: int
    dataset_rows: int
    dataset_first_session: str
    dataset_last_session: str
    final_holdout_start: str
    final_holdout_end: str
    final_holdout_rows: int
    final_holdout_down_fraction: float
    final_holdout_neutral_fraction: float
    final_holdout_up_fraction: float
    candidates: tuple[WalkForwardCandidateEvidence, ...]
    walk_forward_policy_locked: bool
    report_path: str


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else float(numerator) / float(denominator)


def _range(values: list[float]) -> float:
    return 0.0 if not values else max(values) - min(values)


def _sum_range(prefix: list[int], start: int, end_exclusive: int) -> int:
    return prefix[end_exclusive] - prefix[start]


def _prefix(values: list[int]) -> list[int]:
    result = [0]
    total = 0
    for value in values:
        total += int(value)
        result.append(total)
    return result


class MLWalkForwardProbe:
    """Measure chronological Gate 7 fold candidates over the accepted Gate 6 dataset.

    Splits operate on complete exchange-session cross sections; rows from one session
    are never randomized across train/validation/test. A full label-horizon purge is
    inserted before validation, before test, and before the final untouched holdout.
    No extra embargo is required for the candidate design because every fold is
    strictly forward and expanding: no observation after an evaluation window can
    enter the training set for that earlier window.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings

    def dataset_root(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "training_datasets" / ML_TRAINING_DATASET_ACCEPTED_ID

    def report_path(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "walk_forward_probe" / "2026" / "2026-08-14.json"

    def _load_manifest(self, dataset_root: Path) -> MLTrainingDatasetManifest:
        path = dataset_root / "manifest.json"
        if not path.is_file():
            raise FileNotFoundError(
                "Accepted Gate 6 dataset is missing; materialize/verify Gate 6 first: "
                f"{path}"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = MLTrainingDatasetManifest.from_dict(payload)
        if manifest.dataset_id != ML_TRAINING_DATASET_ACCEPTED_ID:
            raise ValueError("Gate 7 dataset id does not match accepted Gate 6 evidence")
        if manifest.dataset_lineage_fingerprint != ML_TRAINING_DATASET_ACCEPTED_LINEAGE_SHA256:
            raise ValueError("Gate 7 dataset lineage does not match accepted Gate 6 evidence")
        if manifest.row_count != ML_TRAINING_DATASET_ACCEPTED_ROWS:
            raise ValueError("Gate 7 dataset row count does not match accepted Gate 6 evidence")
        if manifest.distinct_observation_keys != ML_TRAINING_DATASET_ACCEPTED_DISTINCT_KEYS:
            raise ValueError("Gate 7 dataset key count does not match accepted Gate 6 evidence")
        if manifest.class_row_counts != ML_TRAINING_DATASET_ACCEPTED_CLASS_ROWS:
            raise ValueError("Gate 7 dataset class counts do not match accepted Gate 6 evidence")
        for partition in manifest.partitions:
            expected = ML_TRAINING_DATASET_ACCEPTED_PARTITION_SHA256.get(partition.year)
            if expected != partition.sha256:
                raise ValueError(f"Gate 7 partition manifest hash is not accepted for {partition.year}")
            file_path = dataset_root / partition.relative_path
            if not file_path.is_file() or sha256_file(file_path) != partition.sha256:
                raise ValueError(f"Gate 7 partition file hash mismatch: {file_path}")
        return manifest

    @staticmethod
    def _session_evidence(dataset_root: Path) -> list[SessionClassEvidence]:
        glob = (dataset_root / "year=*" / "*.parquet").as_posix()
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                f"""
                SELECT
                    session_date,
                    count(*) AS rows,
                    count(*) FILTER (WHERE prediction_label = 'DOWN') AS down_rows,
                    count(*) FILTER (WHERE prediction_label = 'NEUTRAL') AS neutral_rows,
                    count(*) FILTER (WHERE prediction_label = 'UP') AS up_rows
                FROM read_parquet({sql_string(glob)}, hive_partitioning=true)
                GROUP BY session_date
                ORDER BY session_date
                """
            ).fetchall()
        finally:
            con.close()
        return [
            SessionClassEvidence(
                session_date=str(row[0]),
                rows=int(row[1]),
                down_rows=int(row[2]),
                neutral_rows=int(row[3]),
                up_rows=int(row[4]),
            )
            for row in rows
        ]

    @staticmethod
    def _candidate_evidence(
        sessions: list[SessionClassEvidence],
        spec: WalkForwardCandidateSpec,
    ) -> WalkForwardCandidateEvidence:
        purge = int(ML_WALK_FORWARD_PURGE_SESSIONS)
        holdout = int(ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS)
        usable_end = len(sessions) - holdout - purge
        if usable_end <= 0:
            raise ValueError("Gate 7 dataset is too short for the final holdout contract")

        row_prefix = _prefix([item.rows for item in sessions])
        down_prefix = _prefix([item.down_rows for item in sessions])
        neutral_prefix = _prefix([item.neutral_rows for item in sessions])
        up_prefix = _prefix([item.up_rows for item in sessions])

        folds: list[WalkForwardFoldEvidence] = []
        validation_start = spec.minimum_train_sessions + purge
        fold_index = 1
        while True:
            train_end_exclusive = validation_start - purge
            validation_end_exclusive = validation_start + spec.validation_sessions
            test_start = validation_end_exclusive + purge
            test_end_exclusive = test_start + spec.test_sessions
            if test_end_exclusive > usable_end:
                break

            train_rows = _sum_range(row_prefix, 0, train_end_exclusive)
            validation_rows = _sum_range(
                row_prefix, validation_start, validation_end_exclusive
            )
            test_rows = _sum_range(row_prefix, test_start, test_end_exclusive)
            down = _sum_range(down_prefix, test_start, test_end_exclusive)
            neutral = _sum_range(neutral_prefix, test_start, test_end_exclusive)
            up = _sum_range(up_prefix, test_start, test_end_exclusive)
            folds.append(
                WalkForwardFoldEvidence(
                    fold_index=fold_index,
                    train_start=sessions[0].session_date,
                    train_end=sessions[train_end_exclusive - 1].session_date,
                    train_sessions=train_end_exclusive,
                    train_rows=train_rows,
                    purge1_start=sessions[train_end_exclusive].session_date,
                    purge1_end=sessions[validation_start - 1].session_date,
                    validation_start=sessions[validation_start].session_date,
                    validation_end=sessions[validation_end_exclusive - 1].session_date,
                    validation_sessions=spec.validation_sessions,
                    validation_rows=validation_rows,
                    purge2_start=sessions[validation_end_exclusive].session_date,
                    purge2_end=sessions[test_start - 1].session_date,
                    test_start=sessions[test_start].session_date,
                    test_end=sessions[test_end_exclusive - 1].session_date,
                    test_sessions=spec.test_sessions,
                    test_rows=test_rows,
                    test_down_fraction=_fraction(down, test_rows),
                    test_neutral_fraction=_fraction(neutral, test_rows),
                    test_up_fraction=_fraction(up, test_rows),
                )
            )
            fold_index += 1
            validation_start += spec.step_sessions

        down_fracs = [fold.test_down_fraction for fold in folds]
        neutral_fracs = [fold.test_neutral_fraction for fold in folds]
        up_fracs = [fold.test_up_fraction for fold in folds]
        distinct_test_dates = {
            item.session_date
            for fold in folds
            for item in sessions[
                next(i for i, session in enumerate(sessions) if session.session_date == fold.test_start):
                next(i for i, session in enumerate(sessions) if session.session_date == fold.test_end) + 1
            ]
        }
        return WalkForwardCandidateEvidence(
            name=spec.name,
            minimum_train_sessions=spec.minimum_train_sessions,
            validation_sessions=spec.validation_sessions,
            test_sessions=spec.test_sessions,
            step_sessions=spec.step_sessions,
            fold_count=len(folds),
            first_test_date=None if not folds else folds[0].test_start,
            last_test_date=None if not folds else folds[-1].test_end,
            minimum_train_rows=0 if not folds else min(fold.train_rows for fold in folds),
            maximum_train_rows=0 if not folds else max(fold.train_rows for fold in folds),
            total_test_rows=sum(fold.test_rows for fold in folds),
            distinct_test_sessions=len(distinct_test_dates),
            test_down_fraction_range=_range(down_fracs),
            test_neutral_fraction_range=_range(neutral_fracs),
            test_up_fraction_range=_range(up_fracs),
            folds=tuple(folds),
        )

    def run(self) -> MLWalkForwardProbeReport:
        started = perf_counter()
        dataset_root = self.dataset_root()
        manifest = self._load_manifest(dataset_root)
        sessions = self._session_evidence(dataset_root)
        if not sessions:
            raise RuntimeError("Gate 7 accepted dataset has no session observations")
        if sum(item.rows for item in sessions) != manifest.row_count:
            raise RuntimeError("Gate 7 per-session aggregation does not reconcile to Gate 6")

        holdout = ML_WALK_FORWARD_FINAL_HOLDOUT_SESSIONS
        holdout_start = len(sessions) - holdout
        holdout_rows = sum(item.rows for item in sessions[holdout_start:])
        holdout_down = sum(item.down_rows for item in sessions[holdout_start:])
        holdout_neutral = sum(item.neutral_rows for item in sessions[holdout_start:])
        holdout_up = sum(item.up_rows for item in sessions[holdout_start:])
        candidates = tuple(
            self._candidate_evidence(sessions, spec)
            for spec in ML_WALK_FORWARD_CANDIDATE_SPECS
        )

        target = self.report_path()
        report = MLWalkForwardProbeReport(
            contract_version=ML_WALK_FORWARD_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            dataset_id=manifest.dataset_id,
            dataset_lineage_sha256=manifest.dataset_lineage_fingerprint,
            wall_seconds=perf_counter() - started,
            probe_status="EVIDENCE_ONLY",
            split_unit=ML_WALK_FORWARD_SPLIT_UNIT,
            random_row_split_allowed=ML_WALK_FORWARD_RANDOM_ROW_SPLIT_ALLOWED,
            label_horizon_sessions=ML_PREDICTION_LABEL_HORIZON_SESSIONS,
            purge_sessions=ML_WALK_FORWARD_PURGE_SESSIONS,
            additional_embargo_sessions=ML_WALK_FORWARD_ADDITIONAL_EMBARGO_SESSIONS,
            final_holdout_sessions=holdout,
            final_holdout_role=ML_WALK_FORWARD_FINAL_HOLDOUT_ROLE,
            dataset_sessions=len(sessions),
            dataset_rows=manifest.row_count,
            dataset_first_session=sessions[0].session_date,
            dataset_last_session=sessions[-1].session_date,
            final_holdout_start=sessions[holdout_start].session_date,
            final_holdout_end=sessions[-1].session_date,
            final_holdout_rows=holdout_rows,
            final_holdout_down_fraction=_fraction(holdout_down, holdout_rows),
            final_holdout_neutral_fraction=_fraction(holdout_neutral, holdout_rows),
            final_holdout_up_fraction=_fraction(holdout_up, holdout_rows),
            candidates=candidates,
            walk_forward_policy_locked=ML_WALK_FORWARD_POLICY_LOCKED,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
