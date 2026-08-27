from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Mapping

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
    Phase26ObservationBuilder,
)
from .phase27_blindness import (
    PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase27ProtectedBlindnessAudit,
)
from .phase27_models import (
    candidate_direction_frame,
    fit_learned_model,
    score_candidate,
    select_fixed_tail,
)
from .phase27_policy import (
    PHASE27_CANDIDATES,
    PHASE27_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE27_OUTCOME_HORIZON_SESSIONS,
    PHASE27_PRIMARY_COST_BPS,
    PHASE27_PROTECTED_CONFIDENCE,
    PHASE27_PROTECTED_FOLDS,
    PHASE27_PROTECTED_MIN_POSITIVE_FOLDS,
    PHASE27_PROTECTED_MIN_RAW_ROWS,
    PHASE27_PROTECTED_MIN_SIGNAL_SESSIONS,
    PHASE27_STRESS_COST_BPS,
    Phase27CandidateSpec,
    phase27_policy_fingerprint,
)
from .phase27_population import (
    PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION,
    PHASE27_POPULATION_REPORT_CONTRACT_VERSION,
    PHASE27_PROTECTED_MODEL_FRAME_CONTRACT_VERSION,
    Phase27PopulationBuilder,
)
from .phase27_research import (
    PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION,
    Phase27DevelopmentResearch,
    Phase27TrancheMetrics,
    tranche_metrics,
)


PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION = (
    "phase27-confirmation-v1-frozen-finalist-tail-only-protected-outcomes"
)
PHASE27_PROTECTED_PREDICTION_CONTRACT_VERSION = (
    "phase27-protected-prediction-v1-no-outcomes"
)
PHASE27_PROTECTED_SCORE_SIGNAL_CONTRACT_VERSION = (
    "phase27-protected-score-signal-v1-frozen-before-outcome-read"
)
PHASE27_PROTECTED_SIGNAL_CONTRACT_VERSION = (
    "phase27-protected-signal-v1-finalist-tail-outcomes-only"
)
PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION = (
    "phase27-protected-read-plan-v1-immutable-resumable-exact-signal-keys"
)
PHASE27_SUPPORT_OVERLAY_CONTRACT_VERSION = (
    "phase27-support-overlay-v1-historical-analytical-only"
)


class Phase27ConfirmationError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase27ConfirmationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase27ConfirmationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase27ConfirmationError(f"{label} must be a JSON object")
    return payload


def _read_parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase27ConfirmationError(f"missing parquet evidence: {path}")
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
        con.register("phase27_confirmation_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM phase27_confirmation_write ORDER BY {order_by}) "
            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
            f"ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


def protected_checks(metrics: Phase27TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE27_PROTECTED_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE27_PROTECTED_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE27_PROTECTED_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(
            metrics.primary_mean_return is not None and metrics.primary_mean_return > 0
        ),
        "primary_lcb_positive": bool(
            metrics.primary_lcb is not None and metrics.primary_lcb > 0
        ),
        "stress_mean_positive": bool(
            metrics.stress_mean_return is not None and metrics.stress_mean_return > 0
        ),
        "session_concentration": bool(
            metrics.max_single_session_row_fraction is not None
            and metrics.max_single_session_row_fraction
            <= PHASE27_MAX_SINGLE_SESSION_ROW_FRACTION
        ),
    }


def _assign_fold(frame: pd.DataFrame, *, field: str, desired_folds: int) -> pd.DataFrame:
    result = frame.copy()
    if result.empty:
        result[field] = pd.Series(dtype="int64")
        return result
    result["as_of_date"] = pd.to_datetime(result["as_of_date"]).dt.date
    sessions = tuple(sorted(set(result["as_of_date"])))
    fold_count = min(desired_folds, len(sessions))
    blocks = [
        tuple(block.tolist())
        for block in np.array_split(np.asarray(sessions, dtype=object), fold_count)
    ]
    mapping = {session: index for index, block in enumerate(blocks) for session in block}
    result[field] = result["as_of_date"].map(mapping).astype(int)
    return result


def _candidate_by_id(candidate_id: str) -> Phase27CandidateSpec:
    try:
        return next(
            candidate
            for candidate in PHASE27_CANDIDATES
            if candidate.candidate_id == candidate_id
        )
    except StopIteration as exc:
        raise Phase27ConfirmationError(
            f"unknown Phase27 finalist candidate: {candidate_id}"
        ) from exc


class Phase27ProtectedConfirmation:
    """Confirm only frozen Phase27 finalist tail keys against the one-time holdout."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase27PopulationBuilder(settings)
        self.research = Phase27DevelopmentResearch(settings)
        self.blindness = Phase27ProtectedBlindnessAudit(settings)
        self.phase26_observations = Phase26ObservationBuilder(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase27" / "v1" / "confirmation"

    def report_path(self) -> Path:
        return self.root / "protected_confirmation.json"

    def protected_predictions_path(self) -> Path:
        return self.root / "protected_predictions.parquet"

    def protected_score_signals_path(self) -> Path:
        return self.root / "protected_score_signals.parquet"

    def protected_signals_path(self) -> Path:
        return self.root / "protected_signals.parquet"

    def read_plan_path(self) -> Path:
        return self.root / "protected_read_plan.json"

    def support_overlay_path(self) -> Path:
        return self.root / "support_overlay.json"

    def _finalists(self) -> tuple[tuple[dict[str, object], ...], Path]:
        path = self.research.finalists_path()
        payload = _read_json(path, "Phase27 frozen finalists")
        if payload.get("contract_version") != PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION:
            raise Phase27ConfirmationError("Phase27 finalist contract mismatch")
        if payload.get("phase27_policy_fingerprint") != phase27_policy_fingerprint():
            raise Phase27ConfirmationError("Phase27 finalist policy fingerprint mismatch")
        if payload.get("frozen") is not True:
            raise Phase27ConfirmationError("Phase27 finalist artifact is not frozen")
        if int(payload.get("protected_returns_read", -1)) != 0 or int(
            payload.get("protected_candidate_rows_read", -1)
        ) != 0:
            raise Phase27ConfirmationError("Phase27 finalists were not frozen protected-blind")
        entries = payload.get("finalists")
        if not isinstance(entries, list):
            raise Phase27ConfirmationError("Phase27 finalist entries are malformed")
        normalized: list[dict[str, object]] = []
        seen: set[str] = set()
        directions: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise Phase27ConfirmationError("Phase27 finalist entry must be an object")
            candidate_id = str(entry.get("candidate_id") or "")
            candidate = _candidate_by_id(candidate_id)
            if candidate_id in seen or candidate.direction in directions:
                raise Phase27ConfirmationError("Phase27 finalist direction/cardinality invalid")
            if str(entry.get("direction")) != candidate.direction:
                raise Phase27ConfirmationError("Phase27 finalist direction drift")
            if str(entry.get("family")) != candidate.family:
                raise Phase27ConfirmationError("Phase27 finalist family drift")
            params = entry.get("chosen_hyperparameters")
            if not isinstance(params, dict):
                raise Phase27ConfirmationError("Phase27 finalist hyperparameters malformed")
            normalized.append(entry)
            seen.add(candidate_id)
            directions.add(candidate.direction)
        return tuple(normalized), path

    def _blindness_report(self, finalist_path: Path) -> tuple[dict[str, object], Path]:
        path = self.blindness.report_path()
        payload = _read_json(path, "Phase27 protected blindness audit")
        if payload.get("contract_version") != PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION:
            raise Phase27ConfirmationError("Phase27 blindness audit contract mismatch")
        if payload.get("phase27_policy_fingerprint") != phase27_policy_fingerprint():
            raise Phase27ConfirmationError("Phase27 blindness policy fingerprint mismatch")
        if payload.get("pass") is not True or payload.get(
            "eligible_for_phase27_protected_reuse"
        ) is not True:
            raise Phase27ConfirmationError("Phase27 holdout reuse was not independently approved")
        if payload.get("protected_holdout_consumed") is not False or int(
            payload.get("protected_returns_read", -1)
        ) != 0:
            raise Phase27ConfirmationError("Phase27 blindness audit is not pre-read")
        if payload.get("phase27_finalists_sha256") != sha256_file(finalist_path):
            raise Phase27ConfirmationError("Phase27 blindness audit finalist SHA mismatch")
        return payload, path

    def _population_frames(self) -> tuple[pd.DataFrame, pd.DataFrame, Path, Path]:
        report = _read_json(self.population.report_path(), "Phase27 population report")
        if report.get("contract_version") != PHASE27_POPULATION_REPORT_CONTRACT_VERSION:
            raise Phase27ConfirmationError("Phase27 population report contract mismatch")
        if report.get("phase27_policy_fingerprint") != phase27_policy_fingerprint():
            raise Phase27ConfirmationError("Phase27 population policy fingerprint mismatch")
        if report.get("pass") is not True or int(report.get("protected_return_reads", -1)) != 0:
            raise Phase27ConfirmationError("Phase27 population is not protected-blind passing")
        development_path = self.population.development_path()
        protected_path = self.population.protected_path()
        if report.get("development_sha256") != sha256_file(development_path):
            raise Phase27ConfirmationError("Phase27 development model SHA mismatch")
        if report.get("protected_sha256") != sha256_file(protected_path):
            raise Phase27ConfirmationError("Phase27 protected model SHA mismatch")
        development = _read_parquet(
            development_path, order_by="as_of_date, instrument_id"
        )
        protected = _read_parquet(
            protected_path, order_by="as_of_date, instrument_id"
        )
        if set(development["phase27_contract_version"].astype(str)) != {
            PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION
        }:
            raise Phase27ConfirmationError("Phase27 development model contract mismatch")
        if set(protected["phase27_contract_version"].astype(str)) != {
            PHASE27_PROTECTED_MODEL_FRAME_CONTRACT_VERSION
        }:
            raise Phase27ConfirmationError("Phase27 protected model contract mismatch")
        development["as_of_date"] = pd.to_datetime(development["as_of_date"]).dt.date
        protected["as_of_date"] = pd.to_datetime(protected["as_of_date"]).dt.date
        return development, protected, development_path, protected_path

    def _score_finalists(
        self,
        *,
        finalist_entries: tuple[dict[str, object], ...],
        development: pd.DataFrame,
        protected: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        predictions: list[pd.DataFrame] = []
        signals: list[pd.DataFrame] = []
        for entry in finalist_entries:
            candidate = _candidate_by_id(str(entry["candidate_id"]))
            params = entry["chosen_hyperparameters"]
            if not isinstance(params, Mapping):
                raise Phase27ConfirmationError("Phase27 finalist params are not a mapping")
            if candidate.learned:
                train = candidate_direction_frame(development, candidate)
                model = fit_learned_model(train, candidate, params)
            else:
                model = None
            scored = score_candidate(protected, candidate, model=model)
            scored.insert(0, "prediction_contract_version", PHASE27_PROTECTED_PREDICTION_CONTRACT_VERSION)
            scored.insert(1, "candidate_id", candidate.candidate_id)
            scored.insert(2, "candidate_family", candidate.family)
            scored.insert(3, "strategy_direction", candidate.direction)
            predictions.append(scored)
            fired = select_fixed_tail(scored)
            fired.insert(0, "score_signal_contract_version", PHASE27_PROTECTED_SCORE_SIGNAL_CONTRACT_VERSION)
            signals.append(fired)
        if predictions:
            combined_predictions = pd.concat(predictions, ignore_index=True, sort=False)
        else:
            combined_predictions = protected.iloc[0:0].copy()
            combined_predictions.insert(
                0,
                "prediction_contract_version",
                pd.Series(dtype="string"),
            )
            combined_predictions.insert(1, "candidate_id", pd.Series(dtype="string"))
            combined_predictions.insert(2, "candidate_family", pd.Series(dtype="string"))
            combined_predictions.insert(3, "strategy_direction", pd.Series(dtype="string"))
            combined_predictions["phase27_score"] = pd.Series(dtype=float)
        if signals:
            combined_signals = pd.concat(signals, ignore_index=True, sort=False)
        else:
            combined_signals = combined_predictions.iloc[0:0].copy()
            combined_signals.insert(
                0,
                "score_signal_contract_version",
                pd.Series(dtype="string"),
            )
        return combined_predictions, combined_signals

    def _write_scored_artifacts(
        self,
        predictions: pd.DataFrame,
        score_signals: pd.DataFrame,
    ) -> tuple[Path, Path]:
        predictions_path = self.protected_predictions_path()
        score_signals_path = self.protected_score_signals_path()
        _write_parquet(
            self.settings,
            predictions,
            predictions_path,
            order_by="candidate_id, as_of_date, instrument_id",
        )
        _write_parquet(
            self.settings,
            score_signals,
            score_signals_path,
            order_by="candidate_id, as_of_date, instrument_id",
        )
        return predictions_path, score_signals_path

    def _future_query_keys(self, score_signals: pd.DataFrame) -> pd.DataFrame:
        if score_signals.empty:
            return score_signals.assign(future_date=pd.Series(dtype="object"))
        sessions = self.phase26_observations._session_frame()
        future_by_seq = {
            int(row.session_seq): row.session_date
            for row in sessions.itertuples(index=False)
        }
        splits, _, _ = self.phase26_observations._split_evidence()
        split_dates: dict[str, tuple[date, ...]] = {}
        if not splits.empty:
            for ticker, group in splits.groupby("ticker", sort=False, observed=True):
                split_dates[str(ticker)] = tuple(
                    sorted(pd.to_datetime(group["execution_date"]).dt.date)
                )

        result = score_signals.copy()
        result["as_of_date"] = pd.to_datetime(result["as_of_date"]).dt.date
        result["future_date"] = result["session_seq"].map(
            lambda value: future_by_seq.get(
                int(value) + PHASE27_OUTCOME_HORIZON_SESSIONS
            )
        )
        result = result.loc[result["future_date"].notna()].copy()
        if not result.empty and max(result["future_date"]) > PHASE26_OUTCOME_EVIDENCE_END:
            raise Phase27ConfirmationError("Phase27 protected future date exceeds frozen evidence")

        def crosses_split(row: pd.Series) -> bool:
            dates = split_dates.get(str(row["ticker"]), ())
            return any(row["as_of_date"] < split_date <= row["future_date"] for split_date in dates)

        result["split_crossing"] = result.apply(crosses_split, axis=1)
        result = result.loc[~result["split_crossing"].astype(bool)].drop(
            columns=["split_crossing"]
        )
        return result

    def _read_plan_payload(
        self,
        *,
        blindness_path: Path,
        finalist_path: Path,
        protected_path: Path,
        predictions_path: Path,
        score_signals_path: Path,
        query_keys: pd.DataFrame,
    ) -> dict[str, object]:
        return {
            "contract_version": PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "blindness_audit_sha256": sha256_file(blindness_path),
            "finalists_sha256": sha256_file(finalist_path),
            "protected_model_predictors_sha256": sha256_file(protected_path),
            "protected_predictions_sha256": sha256_file(predictions_path),
            "protected_score_signals_sha256": sha256_file(score_signals_path),
            "finalist_ids": sorted(set(query_keys["candidate_id"].astype(str)))
            if not query_keys.empty
            else [],
            "selected_score_signal_rows": int(
                len(_read_parquet(score_signals_path, order_by="candidate_id, as_of_date, instrument_id"))
            ),
            "outcome_query_rows_after_split_censor": int(len(query_keys)),
            "outcome_evidence_end": PHASE26_OUTCOME_EVIDENCE_END.isoformat(),
            "holdout_consumption_committed": bool(len(query_keys) > 0),
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }

    def _ensure_read_plan(
        self,
        *,
        blindness_path: Path,
        finalist_path: Path,
        protected_path: Path,
        predictions_path: Path,
        score_signals_path: Path,
        query_keys: pd.DataFrame,
    ) -> tuple[dict[str, object], Path]:
        path = self.read_plan_path()
        expected = self._read_plan_payload(
            blindness_path=blindness_path,
            finalist_path=finalist_path,
            protected_path=protected_path,
            predictions_path=predictions_path,
            score_signals_path=score_signals_path,
            query_keys=query_keys,
        )
        if path.is_file():
            existing = _read_json(path, "Phase27 protected read plan")
            stable_fields = tuple(key for key in expected if key != "generated_at_utc")
            if any(existing.get(key) != expected.get(key) for key in stable_fields):
                raise Phase27ConfirmationError(
                    "Phase27 protected read plan changed after holdout commitment"
                )
            return existing, path
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(expected, indent=2, sort_keys=True) + "\n")
        return expected, path

    def _join_outcomes(self, query_keys: pd.DataFrame) -> pd.DataFrame:
        if query_keys.empty:
            result = query_keys.copy()
            result["future_close"] = pd.Series(dtype=float)
            result["forward_return"] = pd.Series(dtype=float)
            result["directional_return"] = pd.Series(dtype=float)
            return result
        con = connect_utc(":memory:")
        try:
            con.register("phase27_query_keys", query_keys)
            bars = self.phase26_observations.paths.glob_for_timeframe(Timeframe.DAY_1)
            result = con.execute(
                f"""
                SELECT
                    q.*,
                    CAST(b.close AS DOUBLE) AS future_close
                FROM phase27_query_keys q
                LEFT JOIN read_parquet(
                    {sql_string(bars)},
                    union_by_name=true,
                    hive_partitioning=false
                ) b
                  ON b.symbol = q.ticker
                 AND CAST(b.session_date AS DATE) = CAST(q.future_date AS DATE)
                ORDER BY q.candidate_id, q.as_of_date, q.instrument_id
                """
            ).fetch_df()
        finally:
            con.close()
        result["as_of_date"] = pd.to_datetime(result["as_of_date"]).dt.date
        result["future_date"] = pd.to_datetime(result["future_date"]).dt.date
        if result.duplicated(
            ["candidate_id", "as_of_date", "instrument_id"], keep=False
        ).any():
            raise Phase27ConfirmationError("Phase27 protected outcome join is non-unique")
        result["future_close"] = pd.to_numeric(result["future_close"], errors="coerce")
        result["daily_close"] = pd.to_numeric(result["daily_close"], errors="coerce")
        result = result.loc[
            result["future_close"].gt(0) & result["daily_close"].gt(0)
        ].copy()
        result["forward_return"] = result["future_close"] / result["daily_close"] - 1.0
        result["directional_return"] = np.where(
            result["strategy_direction"].astype(str) == "LONG",
            result["forward_return"],
            -result["forward_return"],
        )
        result["primary_net_return"] = (
            result["directional_return"] - PHASE27_PRIMARY_COST_BPS / 10_000.0
        )
        result["stress_net_return"] = (
            result["directional_return"] - PHASE27_STRESS_COST_BPS / 10_000.0
        )
        result.insert(0, "signal_contract_version", PHASE27_PROTECTED_SIGNAL_CONTRACT_VERSION)
        return result

    def _support_payload(
        self,
        *,
        confirmed_ids: tuple[str, ...],
        finalist_entries: tuple[dict[str, object], ...],
        finalist_path: Path,
        confirmation_signal_sha: str | None,
    ) -> dict[str, object]:
        entry_by_id = {
            str(entry["candidate_id"]): entry for entry in finalist_entries
        }
        return {
            "contract_version": PHASE27_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "authority": "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY",
            "supported_candidate_ids": list(confirmed_ids),
            "candidate_definitions": [
                {
                    **asdict(_candidate_by_id(candidate_id)),
                    "chosen_hyperparameters": entry_by_id[candidate_id][
                        "chosen_hyperparameters"
                    ],
                }
                for candidate_id in confirmed_ids
            ],
            "finalists_sha256": sha256_file(finalist_path),
            "protected_signals_sha256": confirmation_signal_sha,
            "phase11_provenance_unchanged": True,
            "paper_authority": False,
            "live_authority": False,
            "automatic_broker_failover": False,
        }

    def _write_support(
        self,
        *,
        confirmed_ids: tuple[str, ...],
        finalist_entries: tuple[dict[str, object], ...],
        finalist_path: Path,
        confirmation_signal_sha: str | None,
    ) -> Path:
        path = self.support_overlay_path()
        payload = self._support_payload(
            confirmed_ids=confirmed_ids,
            finalist_entries=finalist_entries,
            finalist_path=finalist_path,
            confirmation_signal_sha=confirmation_signal_sha,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path

    def _zero_finalists(
        self,
        *,
        finalist_entries: tuple[dict[str, object], ...],
        finalist_path: Path,
        blindness_path: Path,
        protected_path: Path,
    ) -> dict[str, object]:
        support_path = self._write_support(
            confirmed_ids=(),
            finalist_entries=finalist_entries,
            finalist_path=finalist_path,
            confirmation_signal_sha=None,
        )
        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "status": "SKIPPED_ZERO_FINALISTS",
            "blindness_audit_sha256": sha256_file(blindness_path),
            "finalists_sha256": sha256_file(finalist_path),
            "protected_model_predictors_sha256": sha256_file(protected_path),
            "finalist_count": 0,
            "protected_candidate_rows_read": 0,
            "protected_returns_read": 0,
            "protected_holdout_consumed": False,
            "confirmed_candidate_ids": [],
            "support_overlay_sha256": sha256_file(support_path),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report

    def run(self) -> dict[str, object]:
        if self.report_path().is_file():
            existing = _read_json(self.report_path(), "Phase27 protected confirmation")
            if existing.get("contract_version") != PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION:
                raise Phase27ConfirmationError("existing Phase27 confirmation contract mismatch")
            if existing.get("phase27_policy_fingerprint") != phase27_policy_fingerprint():
                raise Phase27ConfirmationError("existing Phase27 confirmation policy mismatch")
            if existing.get("pass") is not True:
                raise Phase27ConfirmationError("existing Phase27 confirmation is not passing")
            return existing

        finalist_entries, finalist_path = self._finalists()
        _, blindness_path = self._blindness_report(finalist_path)
        development, protected, _, protected_path = self._population_frames()
        if not finalist_entries:
            return self._zero_finalists(
                finalist_entries=finalist_entries,
                finalist_path=finalist_path,
                blindness_path=blindness_path,
                protected_path=protected_path,
            )

        predictions_path = self.protected_predictions_path()
        score_signals_path = self.protected_score_signals_path()
        if self.read_plan_path().is_file():
            predictions = _read_parquet(
                predictions_path, order_by="candidate_id, as_of_date, instrument_id"
            )
            score_signals = _read_parquet(
                score_signals_path, order_by="candidate_id, as_of_date, instrument_id"
            )
        else:
            predictions, score_signals = self._score_finalists(
                finalist_entries=finalist_entries,
                development=development,
                protected=protected,
            )
            predictions_path, score_signals_path = self._write_scored_artifacts(
                predictions, score_signals
            )

        query_keys = self._future_query_keys(score_signals)
        read_plan, read_plan_path = self._ensure_read_plan(
            blindness_path=blindness_path,
            finalist_path=finalist_path,
            protected_path=protected_path,
            predictions_path=predictions_path,
            score_signals_path=score_signals_path,
            query_keys=query_keys,
        )
        usable = self._join_outcomes(query_keys)
        protected_signals_path = self.protected_signals_path()
        _write_parquet(
            self.settings,
            usable,
            protected_signals_path,
            order_by="candidate_id, as_of_date, instrument_id",
        )

        metrics: dict[str, Phase27TrancheMetrics] = {}
        check_map: dict[str, dict[str, bool]] = {}
        for entry in finalist_entries:
            candidate_id = str(entry["candidate_id"])
            rows = usable.loc[usable["candidate_id"].astype(str) == candidate_id].copy()
            rows = _assign_fold(
                rows,
                field="protected_fold",
                desired_folds=PHASE27_PROTECTED_FOLDS,
            )
            item = tranche_metrics(
                rows,
                predictions=pd.DataFrame(),
                confidence=PHASE27_PROTECTED_CONFIDENCE,
                fold_field="protected_fold",
                label=f"protected:{candidate_id}",
                tuning_trial_count=0,
            )
            metrics[candidate_id] = item
            check_map[candidate_id] = protected_checks(item)

        confirmed_ids = tuple(
            sorted(
                candidate_id
                for candidate_id, checks in check_map.items()
                if all(checks.values())
            )
        )
        support_path = self._write_support(
            confirmed_ids=confirmed_ids,
            finalist_entries=finalist_entries,
            finalist_path=finalist_path,
            confirmation_signal_sha=sha256_file(protected_signals_path),
        )
        report_path = self.report_path()
        candidate_rows_read = int(read_plan["outcome_query_rows_after_split_censor"])
        return_rows_read = int(len(usable))
        consumed = bool(read_plan["holdout_consumption_committed"])
        report: dict[str, object] = {
            "contract_version": PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "status": "PROTECTED_CONFIRMATION_COMPLETE",
            "blindness_audit_sha256": sha256_file(blindness_path),
            "finalists_sha256": sha256_file(finalist_path),
            "protected_model_predictors_sha256": sha256_file(protected_path),
            "protected_predictions_sha256": sha256_file(predictions_path),
            "protected_score_signals_sha256": sha256_file(score_signals_path),
            "protected_read_plan_sha256": sha256_file(read_plan_path),
            "protected_signals_sha256": sha256_file(protected_signals_path),
            "finalist_count": len(finalist_entries),
            "protected_candidate_rows_read": candidate_rows_read,
            "protected_returns_read": return_rows_read,
            "protected_holdout_consumed": consumed,
            "protected_metrics": {
                key: value.to_dict() for key, value in metrics.items()
            },
            "protected_checks": check_map,
            "confirmed_candidate_ids": list(confirmed_ids),
            "support_overlay_sha256": sha256_file(support_path),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
