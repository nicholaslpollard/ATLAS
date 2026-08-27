from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_observations import (
    PHASE26_OUTCOME_EVIDENCE_END,
    PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase26_policy import (
    PHASE26_CANDIDATES,
    PHASE26_PRIMARY_COST_BPS,
    PHASE26_PROTECTED_CONFIDENCE,
    PHASE26_PROTECTED_FOLDS,
    PHASE26_PROTECTED_MIN_POSITIVE_FOLDS,
    PHASE26_PROTECTED_MIN_RAW_ROWS,
    PHASE26_PROTECTED_MIN_SIGNAL_SESSIONS,
    PHASE26_STRESS_COST_BPS,
    phase26_policy_fingerprint,
)
from .phase26_research import (
    PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
    Phase26DevelopmentResearch,
    Phase26TrancheMetrics,
    tranche_metrics,
)
from .phase26_signals import candidate_mask


PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION = (
    "phase26-confirmation-v1-finalist-only-protected-three-session-return"
)
PHASE26_PROTECTED_SIGNAL_CONTRACT_VERSION = "phase26-protected-signal-v1-finalists-only"
PHASE26_SUPPORT_OVERLAY_CONTRACT_VERSION = "phase26-support-overlay-v1-historical-analytical-only"


class Phase26ConfirmationError(RuntimeError):
    pass


def protected_checks(metrics: Phase26TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE26_PROTECTED_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE26_PROTECTED_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE26_PROTECTED_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None and metrics.stress_mean_return > 0
        ),
    }


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
        con.register("p26_confirmation_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM p26_confirmation_write ORDER BY {order_by}) "
            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
            f"ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


class Phase26ProtectedConfirmation:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.observations = Phase26ObservationBuilder(settings)
        self.research = Phase26DevelopmentResearch(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase26" / "v1" / "confirmation"

    def report_path(self) -> Path:
        return self.root / "protected_confirmation.json"

    def protected_signals_path(self) -> Path:
        return self.root / "protected_signals.parquet"

    def support_overlay_path(self) -> Path:
        return self.root / "support_overlay.json"

    def _finalists(self) -> tuple[tuple[str, ...], Path]:
        path = self.research.finalists_path()
        if not path.is_file():
            raise Phase26ConfirmationError("Phase26 frozen finalist artifact is missing")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise Phase26ConfirmationError("Phase26 finalist artifact must be an object")
        if payload.get("contract_version") != PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION:
            raise Phase26ConfirmationError("Phase26 finalist artifact contract mismatch")
        if payload.get("phase26_policy_fingerprint") != phase26_policy_fingerprint():
            raise Phase26ConfirmationError("Phase26 finalist policy fingerprint mismatch")
        if payload.get("finalists_frozen") is not True:
            raise Phase26ConfirmationError("Phase26 finalists are not frozen")
        if int(payload.get("protected_returns_read", -1)) != 0:
            raise Phase26ConfirmationError("protected returns were read before confirmation")
        raw_ids = payload.get("finalist_candidate_ids")
        if not isinstance(raw_ids, list):
            raise Phase26ConfirmationError("Phase26 finalist IDs are malformed")
        ids = tuple(str(value) for value in raw_ids)
        known = {candidate.candidate_id for candidate in PHASE26_CANDIDATES}
        if len(ids) != len(set(ids)) or not set(ids).issubset(known):
            raise Phase26ConfirmationError("Phase26 finalist IDs are invalid")
        return ids, path

    def _protected_predictors(self) -> tuple[pd.DataFrame, Path]:
        report_path = self.observations.report_path()
        if not report_path.is_file():
            raise Phase26ConfirmationError("Phase26 observation report is missing")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise Phase26ConfirmationError("Phase26 observation report is malformed")
        if report.get("pass") is not True or int(report.get("protected_return_reads", -1)) != 0:
            raise Phase26ConfirmationError("Phase26 protected predictors are not blind/passing")
        path = self.observations.protected_predictors_path()
        if not path.is_file() or report.get("protected_predictors_sha256") != sha256_file(path):
            raise Phase26ConfirmationError("Phase26 protected predictor SHA mismatch")
        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY as_of_date, instrument_id"
            ).fetch_df()
        finally:
            con.close()
        if set(frame["contract_version"].astype(str)) != {
            PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION
        }:
            raise Phase26ConfirmationError("Phase26 protected predictor contract mismatch")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        return frame, path

    def _support_overlay(
        self,
        *,
        confirmed_ids: tuple[str, ...],
        finalist_sha: str,
    ) -> dict[str, object]:
        return {
            "contract_version": PHASE26_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "authority": "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY",
            "supported_candidate_ids": list(confirmed_ids),
            "candidate_definitions": [
                asdict(candidate)
                for candidate in PHASE26_CANDIDATES
                if candidate.candidate_id in confirmed_ids
            ],
            "finalists_sha256": finalist_sha,
            "incumbent_phase11_support_unchanged": True,
            "paper_authority": False,
            "live_authority": False,
        }

    def _write_support(
        self,
        *,
        confirmed_ids: tuple[str, ...],
        finalist_path: Path,
    ) -> Path:
        path = self.support_overlay_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._support_overlay(
            confirmed_ids=confirmed_ids,
            finalist_sha=sha256_file(finalist_path),
        )
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path

    def _zero_finalists(
        self,
        *,
        finalist_path: Path,
        protected_predictor_path: Path,
    ) -> dict[str, object]:
        support_path = self._write_support(confirmed_ids=(), finalist_path=finalist_path)
        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "status": "SKIPPED_ZERO_FINALISTS",
            "finalists_sha256": sha256_file(finalist_path),
            "protected_predictors_sha256": sha256_file(protected_predictor_path),
            "finalist_count": 0,
            "protected_candidate_rows_read": 0,
            "protected_returns_read": 0,
            "confirmed_candidate_ids": [],
            "support_overlay_sha256": sha256_file(support_path),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report

    def run(self) -> dict[str, object]:
        finalist_ids, finalist_path = self._finalists()
        protected, protected_predictor_path = self._protected_predictors()
        if not finalist_ids:
            return self._zero_finalists(
                finalist_path=finalist_path,
                protected_predictor_path=protected_predictor_path,
            )

        fired_frames: list[pd.DataFrame] = []
        for candidate_id in finalist_ids:
            candidate = next(
                candidate
                for candidate in PHASE26_CANDIDATES
                if candidate.candidate_id == candidate_id
            )
            fired = protected.loc[candidate_mask(protected, candidate)].copy()
            if fired.empty:
                continue
            fired.insert(0, "signal_contract_version", PHASE26_PROTECTED_SIGNAL_CONTRACT_VERSION)
            fired.insert(1, "candidate_id", candidate.candidate_id)
            fired.insert(2, "candidate_family", candidate.family)
            fired.insert(3, "strategy_direction", candidate.direction)
            fired_frames.append(fired)

        if fired_frames:
            fired_predictors = pd.concat(fired_frames, ignore_index=True)
        else:
            fired_predictors = protected.head(0).copy()
            fired_predictors.insert(0, "signal_contract_version", pd.Series(dtype="string"))
            fired_predictors.insert(1, "candidate_id", pd.Series(dtype="string"))
            fired_predictors.insert(2, "candidate_family", pd.Series(dtype="string"))
            fired_predictors.insert(3, "strategy_direction", pd.Series(dtype="string"))

        sessions = self.observations._session_frame()
        splits, _, _ = self.observations._split_evidence()
        con = connect_utc(":memory:")
        try:
            con.register("p26_protected_fired", fired_predictors)
            con.register("p26_sessions_input", sessions)
            con.register("p26_splits_input", splits)
            con.execute(
                """
                CREATE TEMP TABLE p26_sessions AS
                SELECT CAST(session_date AS DATE) AS session_date, CAST(session_seq AS BIGINT) AS session_seq
                FROM p26_sessions_input
                """
            )
            con.execute(
                """
                CREATE TEMP TABLE p26_splits AS
                SELECT CAST(ticker AS VARCHAR) AS ticker, CAST(execution_date AS DATE) AS execution_date
                FROM p26_splits_input
                """
            )
            bar_1d = self.observations.paths.glob_for_timeframe(Timeframe.DAY_1)
            con.execute(
                f"""
                CREATE TEMP VIEW p26_label_bars AS
                SELECT
                    b.symbol,
                    CAST(b.session_date AS DATE) AS session_date,
                    CAST(b.close AS DOUBLE) AS close
                FROM read_parquet({sql_string(bar_1d)}, union_by_name=true, hive_partitioning=false) b
                WHERE b.close IS NOT NULL
                  AND isfinite(CAST(b.close AS DOUBLE))
                  AND b.close > 0
                """
            )
            raw = con.execute(
                """
                SELECT
                    p.*,
                    fs.session_date AS future_date,
                    fb.close AS future_close,
                    CASE WHEN fb.close > 0 AND p.daily_close > 0
                         THEN fb.close / p.daily_close - 1.0 ELSE NULL END AS forward_return,
                    EXISTS (
                        SELECT 1
                        FROM p26_splits s
                        WHERE s.ticker = p.ticker
                          AND s.execution_date > p.as_of_date
                          AND s.execution_date <= fs.session_date
                    ) AS split_crossing
                FROM p26_protected_fired p
                LEFT JOIN p26_sessions fs ON fs.session_seq = p.session_seq + 3
                LEFT JOIN p26_label_bars fb
                  ON fb.symbol = p.ticker AND fb.session_date = fs.session_date
                ORDER BY p.candidate_id, p.as_of_date, p.instrument_id
                """
            ).fetch_df()
        finally:
            con.close()

        raw["as_of_date"] = pd.to_datetime(raw["as_of_date"]).dt.date
        raw["future_date"] = pd.to_datetime(raw["future_date"], errors="coerce").dt.date
        usable = raw.loc[
            raw["future_date"].notna()
            & pd.to_numeric(raw["future_close"], errors="coerce").gt(0)
            & ~raw["split_crossing"].fillna(False).astype(bool)
        ].copy()
        if not usable.empty and max(usable["future_date"]) > PHASE26_OUTCOME_EVIDENCE_END:
            raise Phase26ConfirmationError("protected outcome exceeded frozen evidence endpoint")

        usable["forward_return"] = pd.to_numeric(usable["forward_return"], errors="coerce")
        usable["directional_return"] = np.where(
            usable["strategy_direction"].astype(str) == "LONG",
            usable["forward_return"],
            -usable["forward_return"],
        )
        usable["primary_net_return"] = (
            usable["directional_return"] - PHASE26_PRIMARY_COST_BPS / 10_000.0
        )
        usable["stress_net_return"] = (
            usable["directional_return"] - PHASE26_STRESS_COST_BPS / 10_000.0
        )
        usable = usable.drop(columns=["split_crossing"])

        protected_signals_path = self.protected_signals_path()
        _write_parquet(
            self.settings,
            usable,
            protected_signals_path,
            order_by="candidate_id, as_of_date, instrument_id",
        )

        metrics: dict[str, Phase26TrancheMetrics] = {}
        checks: dict[str, dict[str, bool]] = {}
        for candidate_id in finalist_ids:
            rows = usable.loc[usable["candidate_id"].astype(str) == candidate_id].copy()
            item = tranche_metrics(
                rows,
                confidence=PHASE26_PROTECTED_CONFIDENCE,
                folds=PHASE26_PROTECTED_FOLDS,
                label=f"protected:{candidate_id}",
            )
            metrics[candidate_id] = item
            checks[candidate_id] = protected_checks(item)

        confirmed_ids = tuple(
            sorted(
                candidate_id
                for candidate_id in finalist_ids
                if all(checks[candidate_id].values())
            )
        )
        support_path = self._write_support(
            confirmed_ids=confirmed_ids,
            finalist_path=finalist_path,
        )
        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "status": (
                "PROTECTED_CONFIRMED"
                if confirmed_ids
                else "PROTECTED_NO_CONFIRMED_CANDIDATES"
            ),
            "finalists_sha256": sha256_file(finalist_path),
            "protected_predictors_sha256": sha256_file(protected_predictor_path),
            "finalist_count": len(finalist_ids),
            "protected_candidate_rows_read": int(len(raw)),
            "protected_returns_read": int(len(raw)),
            "protected_usable_signal_rows": int(len(usable)),
            "confirmed_candidate_ids": list(confirmed_ids),
            "metrics": {key: value.to_dict() for key, value in sorted(metrics.items())},
            "checks": dict(sorted(checks.items())),
            "protected_signals_sha256": sha256_file(protected_signals_path),
            "support_overlay_sha256": sha256_file(support_path),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
