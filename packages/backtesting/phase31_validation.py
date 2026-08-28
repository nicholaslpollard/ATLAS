from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.outcome_probe import MLOutcomeFeasibilityProbe

from .phase26_observations import (
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    PHASE26_OUTCOME_EVIDENCE_END,
    Phase26ObservationBuilder,
)
from .phase31_policy import (
    PHASE31_CANDIDATES,
    PHASE31_DEVELOPMENT_LAST_SIGNAL,
    PHASE31_INTERNAL_PURGE_SESSIONS,
    PHASE31_RESEARCH_SIGNAL_START,
    PHASE31_SELECTION_FRACTION,
    PHASE31_SELECTION_MIN_RAW_ROWS,
    PHASE31_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE31_SELECTION_MIN_UNIQUE_TICKERS,
    Phase31CandidateSpec,
    phase31_policy_fingerprint,
)
from .phase31_predictor_evidence import (
    PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS,
    PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
    PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
    validate_phase31_predictor_report,
)
from .phase31_predictors import (
    PHASE31_DEVELOPMENT_PREDICTOR_CONTRACT_VERSION,
    PHASE31_FORBIDDEN_MARKET_FIELDS,
    PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION,
    Phase31Form4PredictorBuilder,
)


PHASE31_INDEPENDENT_VALIDATION_CONTRACT_VERSION = (
    "phase31-independent-negative-validation-v1-source-reconstruction-mandatory-sample-gate-proof-protected-unread"
)
PHASE31_EXPECTED_DEVELOPMENT_STUDY_CONTRACT_VERSION = (
    "phase31-development-study-v1-open-t20-spy-relative-four-hypothesis-protected-blind"
)
PHASE31_EXPECTED_FINALIST_ARTIFACT_CONTRACT_VERSION = (
    "phase31-finalists-v1-selection-internal-protected-unread"
)


class Phase31IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase31IndependentValidationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase31IndependentValidationError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase31IndependentValidationError(f"{label} must be a JSON object")
    return payload


def independent_sample_summary(frame: pd.DataFrame) -> dict[str, float | int | None]:
    if frame.empty:
        return {
            "raw_rows": 0,
            "signal_sessions": 0,
            "unique_tickers": 0,
            "max_single_session_row_fraction": None,
            "max_single_ticker_row_fraction": None,
        }
    raw_rows = int(len(frame))
    session_counts = frame.groupby("decision_session", sort=True, observed=True).size()
    ticker_counts = frame.groupby("ticker", sort=True, observed=True).size()
    return {
        "raw_rows": raw_rows,
        "signal_sessions": int(frame["decision_session"].nunique()),
        "unique_tickers": int(frame["ticker"].nunique()),
        "max_single_session_row_fraction": float(session_counts.max() / raw_rows),
        "max_single_ticker_row_fraction": float(ticker_counts.max() / raw_rows),
    }


def fails_mandatory_sample_gate(summary: dict[str, float | int | None]) -> bool:
    return (
        int(summary["raw_rows"] or 0) < PHASE31_SELECTION_MIN_RAW_ROWS
        or int(summary["signal_sessions"] or 0) < PHASE31_SELECTION_MIN_SIGNAL_SESSIONS
        or int(summary["unique_tickers"] or 0) < PHASE31_SELECTION_MIN_UNIQUE_TICKERS
    )


def _candidate_view(frame: pd.DataFrame, candidate: Phase31CandidateSpec) -> pd.DataFrame:
    field = "cluster_candidate_id" if candidate.requires_cluster else "broad_candidate_id"
    mask = frame[field].astype("string").eq(candidate.candidate_id).fillna(False)
    result = frame.loc[mask].copy()
    if not result.empty and set(result["direction"].astype(str)) != {candidate.direction}:
        raise Phase31IndependentValidationError(
            f"independent candidate direction drifted: {candidate.candidate_id}"
        )
    return result


class Phase31IndependentNegativeValidator:
    """Independent source-level proof that the frozen Phase31 study cannot promote a finalist.

    The negative conclusion does not depend on reproducing bootstrap inference: every
    frozen candidate fails at least one preregistered mandatory sample gate. This
    validator reconstructs the exact development predictor population, split/path
    admissibility, chronological selection tranche, and candidate sample counts from
    source artifacts without importing phase31_development. The protected predictor is
    hash-bound only; protected predictor rows and protected returns are never parsed.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.predictors = Phase31Form4PredictorBuilder(settings)
        self.phase26 = Phase26ObservationBuilder(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase31" / "v1"
        self.development_root = self.root / "development"

    def development_report_path(self) -> Path:
        return self.development_root / "development_study.json"

    def finalists_path(self) -> Path:
        return self.development_root / "finalists.json"

    def report_path(self) -> Path:
        return self.root / "phase31_independent_validation.json"

    def _load_development_predictors(
        self,
    ) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any], pd.DataFrame]:
        predictor_report = _read_json(self.predictors.report_path(), "Phase31 predictor report")
        if predictor_report.get("contract_version") != PHASE31_PREDICTOR_REPORT_CONTRACT_VERSION:
            raise Phase31IndependentValidationError("Phase31 predictor report contract mismatch")
        try:
            validate_phase31_predictor_report(predictor_report)
        except ValueError as exc:
            raise Phase31IndependentValidationError(str(exc)) from exc
        if predictor_report.get("phase31_policy_fingerprint") != phase31_policy_fingerprint():
            raise Phase31IndependentValidationError("Phase31 predictor policy fingerprint mismatch")
        if int(predictor_report.get("target_outcome_rows_read", -1)) != 0:
            raise Phase31IndependentValidationError("predictor stage read target outcomes")
        if int(predictor_report.get("protected_return_rows_read", -1)) != 0:
            raise Phase31IndependentValidationError("predictor stage read protected returns")

        development_path = self.predictors.development_path()
        protected_path = self.predictors.protected_path()
        if (
            not development_path.is_file()
            or sha256_file(development_path) != PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256
            or predictor_report.get("development_sha256")
            != PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256
        ):
            raise Phase31IndependentValidationError("frozen development predictor SHA mismatch")
        if (
            not protected_path.is_file()
            or sha256_file(protected_path) != PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256
            or predictor_report.get("protected_sha256")
            != PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256
        ):
            raise Phase31IndependentValidationError("frozen protected predictor SHA mismatch")

        con = connect_utc(":memory:")
        try:
            predictors = con.execute(
                f"SELECT * FROM read_parquet({sql_string(development_path)}) "
                "ORDER BY decision_session, ticker"
            ).fetch_df()
        finally:
            con.close()
        if len(predictors) != PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS:
            raise Phase31IndependentValidationError("frozen development predictor row count drifted")
        if set(predictors["contract_version"].astype(str)) != {
            PHASE31_DEVELOPMENT_PREDICTOR_CONTRACT_VERSION
        }:
            raise Phase31IndependentValidationError("development predictor row contract mismatch")
        if set(predictors["phase31_policy_fingerprint"].astype(str)) != {
            phase31_policy_fingerprint()
        }:
            raise Phase31IndependentValidationError("development predictor row policy mismatch")
        forbidden = [field for field in PHASE31_FORBIDDEN_MARKET_FIELDS if field in predictors.columns]
        if forbidden:
            raise Phase31IndependentValidationError(
                "development predictor unexpectedly contains market outcomes: " + ", ".join(forbidden)
            )
        predictors["decision_session"] = pd.to_datetime(predictors["decision_session"]).dt.date
        predictors["exit_session"] = pd.to_datetime(predictors["exit_session"]).dt.date
        if predictors.duplicated(["ticker", "decision_session"], keep=False).any():
            raise Phase31IndependentValidationError("development predictors duplicate ticker/session")

        phase26_report = _read_json(self.phase26.report_path(), "accepted Phase26 observation report")
        if (
            phase26_report.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION
            or phase26_report.get("pass") is not True
            or int(phase26_report.get("protected_return_reads", -1)) != 0
        ):
            raise Phase31IndependentValidationError("accepted split lineage is invalid or consumed")
        split_path = MLOutcomeFeasibilityProbe(self.settings).split_evidence_path(
            PHASE26_OUTCOME_EVIDENCE_END
        )
        split_sha = str(phase26_report.get("split_evidence_sha256") or "")
        if not split_path.is_file() or len(split_sha) != 64 or sha256_file(split_path) != split_sha:
            raise Phase31IndependentValidationError("accepted split evidence SHA mismatch")
        split_records: list[dict[str, object]] = []
        with split_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    continue
                ticker = str(payload.get("ticker") or "").strip()
                raw_date = str(payload.get("execution_date") or "").strip()
                if not ticker or not raw_date:
                    continue
                try:
                    execution_date = date.fromisoformat(raw_date)
                except ValueError:
                    continue
                split_records.append({"ticker": ticker, "execution_date": execution_date})
        splits = pd.DataFrame.from_records(
            split_records, columns=["ticker", "execution_date"]
        )
        return predictors, predictor_report, phase26_report, splits

    def _reconstruct_usable_population(
        self, predictors: pd.DataFrame, splits: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        con = connect_utc(":memory:")
        try:
            con.execute("SET preserve_insertion_order=false")
            con.register("p31_ind_predictors", predictors)
            con.register("p31_ind_splits", splits)
            result = con.execute(
                f"""
                WITH needed AS (
                    SELECT ticker AS symbol, CAST(decision_session AS DATE) AS session_date
                    FROM p31_ind_predictors
                    UNION
                    SELECT ticker, CAST(exit_session AS DATE) FROM p31_ind_predictors
                    UNION
                    SELECT 'SPY', CAST(decision_session AS DATE) FROM p31_ind_predictors
                    UNION
                    SELECT 'SPY', CAST(exit_session AS DATE) FROM p31_ind_predictors
                ), bars AS (
                    SELECT b.symbol,
                           CAST(b.session_date AS DATE) AS session_date,
                           CAST(b.open AS DOUBLE) AS session_open,
                           CAST(b.close AS DOUBLE) AS session_close
                    FROM read_parquet(
                        {sql_string(bar_glob)},
                        union_by_name=true,
                        hive_partitioning=false
                    ) b
                    INNER JOIN needed n
                      ON n.symbol = b.symbol
                     AND n.session_date = CAST(b.session_date AS DATE)
                )
                SELECT p.*,
                       se.session_open AS entry_open,
                       sx.session_close AS exit_close,
                       pe.session_open AS spy_entry_open,
                       px.session_close AS spy_exit_close,
                       EXISTS (
                           SELECT 1
                           FROM p31_ind_splits s
                           WHERE s.ticker = p.ticker
                             AND CAST(s.execution_date AS DATE) > CAST(p.decision_session AS DATE)
                             AND CAST(s.execution_date AS DATE) <= CAST(p.exit_session AS DATE)
                       ) AS split_crossing
                FROM p31_ind_predictors p
                LEFT JOIN bars se
                  ON se.symbol = p.ticker
                 AND se.session_date = CAST(p.decision_session AS DATE)
                LEFT JOIN bars sx
                  ON sx.symbol = p.ticker
                 AND sx.session_date = CAST(p.exit_session AS DATE)
                LEFT JOIN bars pe
                  ON pe.symbol = 'SPY'
                 AND pe.session_date = CAST(p.decision_session AS DATE)
                LEFT JOIN bars px
                  ON px.symbol = 'SPY'
                 AND px.session_date = CAST(p.exit_session AS DATE)
                ORDER BY p.decision_session, p.ticker
                """
            ).fetch_df()
        finally:
            con.close()
        if len(result) != len(predictors):
            raise Phase31IndependentValidationError(
                "independent exact path join cardinality drifted; duplicate daily keys suspected"
            )
        result["decision_session"] = pd.to_datetime(result["decision_session"]).dt.date
        result["exit_session"] = pd.to_datetime(result["exit_session"]).dt.date
        for field in ("entry_open", "exit_close", "spy_entry_open", "spy_exit_close"):
            result[field] = pd.to_numeric(result[field], errors="coerce")
        spy_missing = (
            result["spy_entry_open"].isna()
            | result["spy_exit_close"].isna()
            | ~np.isfinite(result["spy_entry_open"].to_numpy(dtype=float))
            | ~np.isfinite(result["spy_exit_close"].to_numpy(dtype=float))
            | result["spy_entry_open"].le(0)
            | result["spy_exit_close"].le(0)
        )
        if bool(spy_missing.any()):
            raise Phase31IndependentValidationError(
                "independent SPY benchmark path is incomplete on frozen sessions"
            )
        stock_missing = (
            result["entry_open"].isna()
            | result["exit_close"].isna()
            | ~np.isfinite(result["entry_open"].to_numpy(dtype=float))
            | ~np.isfinite(result["exit_close"].to_numpy(dtype=float))
            | result["entry_open"].le(0)
            | result["exit_close"].le(0)
        )
        split_crossing = result["split_crossing"].fillna(False).astype(bool)
        usable = result.loc[~stock_missing & ~split_crossing].copy()
        if usable.empty:
            raise Phase31IndependentValidationError(
                "independent usable development population is empty"
            )
        return usable, {
            "exact_stock_path_missing_rows": int(stock_missing.sum()),
            "split_crossing_censored_rows": int(split_crossing.sum()),
            "usable_development_rows": int(len(usable)),
        }

    def _boundaries(self) -> dict[str, object]:
        sessions = tuple(
            self.calendar.sessions_in_range(
                date.fromisoformat(PHASE31_RESEARCH_SIGNAL_START),
                date.fromisoformat(PHASE31_DEVELOPMENT_LAST_SIGNAL),
            )
        )
        if not sessions:
            raise Phase31IndependentValidationError("independent development calendar is empty")
        selection_count = int(math.floor(len(sessions) * PHASE31_SELECTION_FRACTION))
        internal_offset = selection_count + PHASE31_INTERNAL_PURGE_SESSIONS
        if selection_count <= 0 or internal_offset >= len(sessions):
            raise Phase31IndependentValidationError("independent chronology partition is invalid")
        selection = sessions[:selection_count]
        purge = sessions[selection_count:internal_offset]
        internal = sessions[internal_offset:]
        if len(purge) != PHASE31_INTERNAL_PURGE_SESSIONS or not internal:
            raise Phase31IndependentValidationError("independent purge/internal partition is incomplete")
        return {
            "selection_start": selection[0].isoformat(),
            "selection_end": selection[-1].isoformat(),
            "purge_sessions": [item.isoformat() for item in purge],
            "internal_start": internal[0].isoformat(),
            "internal_end": internal[-1].isoformat(),
            "development_session_count": len(sessions),
            "selection_session_count": len(selection),
            "internal_session_count": len(internal),
        }

    def run(self) -> dict[str, Any]:
        development = _read_json(self.development_report_path(), "Phase31 development study")
        finalists = _read_json(self.finalists_path(), "Phase31 finalist artifact")
        predictors, predictor_report, phase26_report, splits = self._load_development_predictors()
        usable, path_diagnostics = self._reconstruct_usable_population(predictors, splits)
        boundaries = self._boundaries()

        selection_start = date.fromisoformat(str(boundaries["selection_start"]))
        selection_end = date.fromisoformat(str(boundaries["selection_end"]))
        selection = usable.loc[
            (usable["decision_session"] >= selection_start)
            & (usable["decision_session"] <= selection_end)
        ].copy()
        if selection.empty:
            raise Phase31IndependentValidationError("independent selection tranche is empty")

        reconstructed: dict[str, dict[str, float | int | None]] = {}
        exact_metric_matches: dict[str, bool] = {}
        mandatory_sample_gate_failures: dict[str, bool] = {}
        reported_metrics = development.get("selection_metrics")
        if not isinstance(reported_metrics, dict):
            raise Phase31IndependentValidationError("development selection metrics are invalid")
        for candidate in PHASE31_CANDIDATES:
            summary = independent_sample_summary(_candidate_view(selection, candidate))
            reconstructed[candidate.candidate_id] = summary
            mandatory_sample_gate_failures[candidate.candidate_id] = fails_mandatory_sample_gate(
                summary
            )
            reported = reported_metrics.get(candidate.candidate_id)
            if not isinstance(reported, dict):
                exact_metric_matches[candidate.candidate_id] = False
                continue
            session_fraction = reported.get("max_single_session_row_fraction")
            ticker_fraction = reported.get("max_single_ticker_row_fraction")
            reconstructed_session_fraction = summary["max_single_session_row_fraction"]
            reconstructed_ticker_fraction = summary["max_single_ticker_row_fraction"]
            exact_metric_matches[candidate.candidate_id] = (
                int(reported.get("raw_rows", -1)) == int(summary["raw_rows"] or 0)
                and int(reported.get("signal_sessions", -1))
                == int(summary["signal_sessions"] or 0)
                and int(reported.get("unique_tickers", -1))
                == int(summary["unique_tickers"] or 0)
                and session_fraction is not None
                and reconstructed_session_fraction is not None
                and math.isclose(
                    float(session_fraction),
                    float(reconstructed_session_fraction),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                and ticker_fraction is not None
                and reconstructed_ticker_fraction is not None
                and math.isclose(
                    float(ticker_fraction),
                    float(reconstructed_ticker_fraction),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            )

        outcome_exclusions = development.get("outcome_path_exclusions")
        checks = {
            "development_contract_exact": development.get("contract_version")
            == PHASE31_EXPECTED_DEVELOPMENT_STUDY_CONTRACT_VERSION,
            "development_report_pass": development.get("pass") is True,
            "finalist_contract_exact": finalists.get("contract_version")
            == PHASE31_EXPECTED_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "policy_fingerprint_exact": all(
                payload.get("phase31_policy_fingerprint") == phase31_policy_fingerprint()
                for payload in (predictor_report, development, finalists)
            ),
            "development_predictor_rows_match": int(
                development.get("development_target_rows_read", -1)
            )
            == len(predictors),
            "usable_rows_match": int(development.get("development_usable_outcome_rows", -1))
            == len(usable),
            "path_exclusions_match": isinstance(outcome_exclusions, dict)
            and int(outcome_exclusions.get("exact_stock_path_missing_rows", -1))
            == path_diagnostics["exact_stock_path_missing_rows"]
            and int(outcome_exclusions.get("split_crossing_censored_rows", -1))
            == path_diagnostics["split_crossing_censored_rows"]
            and int(outcome_exclusions.get("usable_development_rows", -1))
            == path_diagnostics["usable_development_rows"],
            "chronology_boundary_match": development.get("boundaries") == boundaries,
            "all_reconstructed_sample_metrics_match": all(exact_metric_matches.values())
            and len(exact_metric_matches) == len(PHASE31_CANDIDATES),
            "all_candidates_fail_mandatory_sample_gate": all(
                mandatory_sample_gate_failures.values()
            )
            and len(mandatory_sample_gate_failures) == len(PHASE31_CANDIDATES),
            "development_survivors_empty": development.get("selection_survivor_ids") == [],
            "development_winners_empty": development.get("selection_winner_ids") == [],
            "development_finalists_empty": development.get("finalist_ids") == [],
            "finalist_artifact_empty": finalists.get("finalist_ids") == []
            and finalists.get("finalists") == [],
            "protected_predictor_hash_bound_only": predictor_report.get("protected_sha256")
            == PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
            "protected_candidates_unread": int(
                development.get("protected_candidate_rows_read", -1)
            )
            == 0
            and int(finalists.get("protected_candidate_rows_read", -1)) == 0,
            "protected_returns_unread": int(
                predictor_report.get("protected_return_rows_read", -1)
            )
            == 0
            and int(development.get("protected_return_rows_read", -1)) == 0
            and int(finalists.get("protected_returns_read", -1)) == 0
            and int(phase26_report.get("protected_return_reads", -1)) == 0,
            "protected_holdout_unconsumed": development.get("protected_holdout_consumed")
            is False
            and finalists.get("protected_holdout_consumed") is False,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31IndependentValidationError(
                "Phase31 independent validation failed: " + ", ".join(failed)
            )

        report: dict[str, Any] = {
            "contract_version": PHASE31_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "phase31_policy_fingerprint": phase31_policy_fingerprint(),
            "status": "PASS_NEGATIVE_MANDATORY_SAMPLE_GATE_PROOF",
            "reconstructed_development_predictor_rows": int(len(predictors)),
            "reconstructed_usable_outcome_rows": int(len(usable)),
            "reconstructed_path_diagnostics": path_diagnostics,
            "reconstructed_boundaries": boundaries,
            "reconstructed_selection": reconstructed,
            "exact_metric_matches": exact_metric_matches,
            "mandatory_sample_gate_failures": mandatory_sample_gate_failures,
            "selection_survivor_ids": [],
            "selection_winner_ids": [],
            "finalist_ids": [],
            "protected_artifact_hash_reads": 1,
            "protected_predictor_rows_read": 0,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(self.report_path().resolve()),
            "pass": True,
        }
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
