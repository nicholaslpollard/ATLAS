from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_observations import (
    PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION,
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase30_policy import (
    PHASE30_CANDIDATES,
    PHASE30_CURRENT_REACTION_FIELD,
    PHASE30_DEVELOPMENT_END,
    PHASE30_MIN_DIRECTION_ROWS_PER_SESSION,
    PHASE30_PRIMARY_COST_BPS,
    PHASE30_PURGE_SESSIONS,
    PHASE30_RESEARCH_START,
    PHASE30_SELECTION_FRACTION,
    PHASE30_SELECTION_MIN_RAW_ROWS,
    PHASE30_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE30_SIGNAL_TAIL_FRACTION,
    Phase30CandidateSpec,
    phase30_policy_fingerprint,
)
from .phase30_predictors import (
    PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION,
    PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION,
    Phase30NewsPredictorBuilder,
)


PHASE30_INDEPENDENT_VALIDATION_CONTRACT_VERSION = (
    "phase30-independent-negative-validation-v1-source-reconstruction-sample-gate-proof-protected-unread"
)


class Phase30IndependentValidationError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase30IndependentValidationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase30IndependentValidationError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase30IndependentValidationError(f"{label} must be a JSON object")
    return payload


def independent_signal_summary(
    selection: pd.DataFrame, candidate: Phase30CandidateSpec
) -> dict[str, float | int | None]:
    """Rebuild the frozen tail/reaction signal without importing Phase30 development code."""
    direction_label = "bullish" if candidate.direction == "LONG" else "bearish"
    frame = selection.loc[selection["direction"].astype(str) == direction_label].copy()
    frame["news_surprise"] = pd.to_numeric(frame["news_surprise"], errors="coerce")
    frame[PHASE30_CURRENT_REACTION_FIELD] = pd.to_numeric(
        frame[PHASE30_CURRENT_REACTION_FIELD], errors="coerce"
    )
    frame["directional_return"] = pd.to_numeric(
        frame["directional_return"], errors="coerce"
    )
    frame = frame.loc[
        np.isfinite(frame["news_surprise"].to_numpy(dtype=float))
        & np.isfinite(frame[PHASE30_CURRENT_REACTION_FIELD].to_numpy(dtype=float))
        & np.isfinite(frame["directional_return"].to_numpy(dtype=float))
    ].copy()

    fired_parts: list[pd.DataFrame] = []
    for _, group in frame.groupby("as_of_date", sort=True, observed=True):
        if len(group) < PHASE30_MIN_DIRECTION_ROWS_PER_SESSION:
            continue
        ordered = group.sort_values(
            ["news_surprise", "instrument_id"],
            ascending=[False, True],
            kind="stable",
        )
        tail_count = max(1, int(math.ceil(PHASE30_SIGNAL_TAIL_FRACTION * len(ordered))))
        tail = ordered.iloc[:tail_count].copy()
        reaction = tail[PHASE30_CURRENT_REACTION_FIELD]
        if candidate.required_reaction_sign == "POSITIVE":
            tail = tail.loc[reaction.gt(0)].copy()
        elif candidate.required_reaction_sign == "NEGATIVE":
            tail = tail.loc[reaction.lt(0)].copy()
        else:
            raise Phase30IndependentValidationError(
                f"unknown frozen reaction sign: {candidate.required_reaction_sign}"
            )
        if not tail.empty:
            fired_parts.append(tail)

    if not fired_parts:
        return {
            "raw_rows": 0,
            "signal_sessions": 0,
            "primary_mean_return": None,
        }
    fired = pd.concat(fired_parts, ignore_index=True, sort=False)
    session_means = (
        fired.groupby("as_of_date", sort=True, observed=True)["directional_return"]
        .mean()
        .to_numpy(dtype=float)
    )
    primary_cost = PHASE30_PRIMARY_COST_BPS / 10_000.0
    return {
        "raw_rows": int(len(fired)),
        "signal_sessions": int(fired["as_of_date"].nunique()),
        "primary_mean_return": float(np.mean(session_means - primary_cost)),
    }


class Phase30IndependentNegativeValidator:
    """Independent source-level proof that the frozen Phase30 study cannot promote a finalist.

    Because every frozen candidate failed the preregistered minimum sample gates, a
    full independent reimplementation of bootstrap inference is unnecessary for the
    negative conclusion. This validator reconstructs the source join and exact
    tail-before-reaction signal counts directly from Phase26 + Phase30 predictor
    evidence and proves each candidate is below at least one mandatory sample gate.
    It never imports phase30_development and never reads protected returns.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase26 = Phase26ObservationBuilder(settings)
        self.news = Phase30NewsPredictorBuilder(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase30" / "v1"
        self.development_root = self.root / "development"

    def development_report_path(self) -> Path:
        return self.development_root / "development_study.json"

    def finalists_path(self) -> Path:
        return self.development_root / "finalists.json"

    def report_path(self) -> Path:
        return self.root / "phase30_independent_validation.json"

    def _load_sources(self) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
        news_report = _read_json(self.news.report_path(), "Phase30 predictor report")
        phase26_report = _read_json(self.phase26.report_path(), "Phase26 observation report")
        if news_report.get("contract_version") != PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION:
            raise Phase30IndependentValidationError("Phase30 predictor contract mismatch")
        if phase26_report.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION:
            raise Phase30IndependentValidationError("Phase26 observation contract mismatch")
        if news_report.get("pass") is not True or phase26_report.get("pass") is not True:
            raise Phase30IndependentValidationError("source report is not passing")
        if news_report.get("phase30_policy_fingerprint") != phase30_policy_fingerprint():
            raise Phase30IndependentValidationError("Phase30 predictor policy mismatch")
        if int(news_report.get("target_outcome_rows_read", -1)) != 0:
            raise Phase30IndependentValidationError("predictor stage read target outcomes")
        if int(news_report.get("protected_return_rows_read", -1)) != 0:
            raise Phase30IndependentValidationError("predictor stage read protected returns")
        if int(phase26_report.get("protected_return_reads", -1)) != 0:
            raise Phase30IndependentValidationError("Phase26 protected returns were consumed")

        news_path = self.news.development_path()
        phase26_path = self.phase26.development_path()
        if not news_path.is_file() or news_report.get("development_sha256") != sha256_file(news_path):
            raise Phase30IndependentValidationError("Phase30 development predictor SHA mismatch")
        if not phase26_path.is_file() or phase26_report.get("development_sha256") != sha256_file(phase26_path):
            raise Phase30IndependentValidationError("Phase26 development observation SHA mismatch")

        con = connect_utc(":memory:")
        try:
            news = con.execute(
                f"SELECT * FROM read_parquet({sql_string(news_path)}) ORDER BY session_date, ticker"
            ).fetch_df()
            phase26 = con.execute(
                f"SELECT * FROM read_parquet({sql_string(phase26_path)}) ORDER BY as_of_date, instrument_id"
            ).fetch_df()
        finally:
            con.close()
        if news.empty or phase26.empty:
            raise Phase30IndependentValidationError("independent validation source is empty")
        if set(news["contract_version"].astype(str)) != {PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION}:
            raise Phase30IndependentValidationError("Phase30 predictor row contract mismatch")
        if set(phase26["contract_version"].astype(str)) != {PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION}:
            raise Phase30IndependentValidationError("Phase26 development row contract mismatch")
        return news, phase26, news_report, phase26_report

    @staticmethod
    def _join(news: pd.DataFrame, phase26: pd.DataFrame) -> pd.DataFrame:
        con = connect_utc(":memory:")
        try:
            con.register("ind_news", news)
            con.register("ind_phase26", phase26)
            joined = con.execute(
                """
                SELECT
                    CAST(p.as_of_date AS DATE) AS as_of_date,
                    p.instrument_id,
                    p.ticker,
                    p.direction,
                    CAST(p.d1_return_1 AS DOUBLE) AS d1_return_1,
                    CAST(p.directional_return AS DOUBLE) AS directional_return,
                    CAST(n.news_surprise AS DOUBLE) AS news_surprise
                FROM ind_phase26 p
                INNER JOIN ind_news n
                  ON n.ticker = p.ticker
                 AND CAST(n.session_date AS DATE) = CAST(p.as_of_date AS DATE)
                ORDER BY p.as_of_date, p.instrument_id
                """
            ).fetch_df()
        finally:
            con.close()
        if joined.empty:
            raise Phase30IndependentValidationError("independent exact join is empty")
        joined["as_of_date"] = pd.to_datetime(joined["as_of_date"]).dt.date
        if joined.duplicated(["as_of_date", "instrument_id"], keep=False).any():
            raise Phase30IndependentValidationError("duplicate independent candidate key")
        if joined.duplicated(["as_of_date", "ticker"], keep=False).any():
            raise Phase30IndependentValidationError("exact ticker/session join is not one-to-one")
        return joined

    def run(self) -> dict[str, Any]:
        development = _read_json(self.development_report_path(), "Phase30 development study")
        finalists = _read_json(self.finalists_path(), "Phase30 finalists")
        news, phase26, news_report, phase26_report = self._load_sources()
        joined = self._join(news, phase26)

        sessions = tuple(
            self.calendar.sessions_in_range(
                date.fromisoformat(PHASE30_RESEARCH_START),
                date.fromisoformat(PHASE30_DEVELOPMENT_END),
            )
        )
        selection_count = int(math.floor(len(sessions) * PHASE30_SELECTION_FRACTION))
        purge = tuple(sessions[selection_count : selection_count + PHASE30_PURGE_SESSIONS])
        internal = tuple(sessions[selection_count + PHASE30_PURGE_SESSIONS :])
        if not sessions or len(purge) != PHASE30_PURGE_SESSIONS or not internal:
            raise Phase30IndependentValidationError("independent chronology reconstruction failed")
        selection_end = sessions[selection_count - 1]
        selection = joined.loc[joined["as_of_date"] <= selection_end].copy()
        if selection["as_of_date"].isin(purge).any():
            raise Phase30IndependentValidationError("purge leaked into independent selection")

        reconstructed: dict[str, dict[str, float | int | None]] = {}
        exact_metric_matches: dict[str, bool] = {}
        mandatory_sample_gate_failures: dict[str, bool] = {}
        report_metrics = development.get("selection_metrics")
        if not isinstance(report_metrics, dict):
            raise Phase30IndependentValidationError("development selection metrics are invalid")
        for candidate in PHASE30_CANDIDATES:
            summary = independent_signal_summary(selection, candidate)
            reconstructed[candidate.candidate_id] = summary
            reported = report_metrics.get(candidate.candidate_id)
            if not isinstance(reported, dict):
                exact_metric_matches[candidate.candidate_id] = False
                mandatory_sample_gate_failures[candidate.candidate_id] = False
                continue
            reported_mean = reported.get("primary_mean_return")
            reconstructed_mean = summary["primary_mean_return"]
            mean_match = (
                reported_mean is None
                and reconstructed_mean is None
                or reported_mean is not None
                and reconstructed_mean is not None
                and math.isclose(
                    float(reported_mean), float(reconstructed_mean), rel_tol=0.0, abs_tol=1e-12
                )
            )
            exact_metric_matches[candidate.candidate_id] = (
                int(reported.get("raw_rows", -1)) == int(summary["raw_rows"])
                and int(reported.get("signal_sessions", -1)) == int(summary["signal_sessions"])
                and mean_match
            )
            mandatory_sample_gate_failures[candidate.candidate_id] = (
                int(summary["raw_rows"]) < PHASE30_SELECTION_MIN_RAW_ROWS
                or int(summary["signal_sessions"]) < PHASE30_SELECTION_MIN_SIGNAL_SESSIONS
            )

        development_bounds = development.get("boundaries")
        checks = {
            "development_report_pass": development.get("pass") is True,
            "policy_fingerprint_exact": development.get("phase30_policy_fingerprint")
            == phase30_policy_fingerprint(),
            "joined_rows_match": int(development.get("development_population_rows", -1))
            == len(joined),
            "joined_tickers_match": int(development.get("development_population_tickers", -1))
            == joined["ticker"].nunique(),
            "joined_sessions_match": int(development.get("development_population_sessions", -1))
            == joined["as_of_date"].nunique(),
            "selection_boundary_match": isinstance(development_bounds, dict)
            and development_bounds.get("selection_end") == selection_end.isoformat()
            and development_bounds.get("purge_sessions") == [item.isoformat() for item in purge]
            and development_bounds.get("internal_start") == internal[0].isoformat(),
            "all_reconstructed_metrics_match": all(exact_metric_matches.values())
            and len(exact_metric_matches) == len(PHASE30_CANDIDATES),
            "all_candidates_fail_mandatory_sample_gate": all(
                mandatory_sample_gate_failures.values()
            )
            and len(mandatory_sample_gate_failures) == len(PHASE30_CANDIDATES),
            "development_survivors_empty": development.get("selection_survivor_ids") == [],
            "development_winners_empty": development.get("selection_winner_ids") == [],
            "development_finalists_empty": development.get("finalist_ids") == [],
            "finalist_artifact_empty": finalists.get("finalist_ids") == []
            and finalists.get("finalists") == [],
            "protected_candidates_unread": int(development.get("protected_candidate_rows_read", -1)) == 0
            and int(finalists.get("protected_candidate_rows_read", -1)) == 0,
            "protected_returns_unread": int(development.get("protected_return_rows_read", -1)) == 0
            and int(finalists.get("protected_returns_read", -1)) == 0
            and int(news_report.get("protected_return_rows_read", -1)) == 0
            and int(phase26_report.get("protected_return_reads", -1)) == 0,
            "protected_holdout_unconsumed": development.get("protected_holdout_consumed") is False
            and finalists.get("protected_holdout_consumed") is False,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase30IndependentValidationError(
                "Phase30 independent validation failed: " + ", ".join(failed)
            )

        report: dict[str, Any] = {
            "contract_version": PHASE30_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
            "phase30_policy_fingerprint": phase30_policy_fingerprint(),
            "status": "PASS_NEGATIVE_SAMPLE_GATE_PROOF",
            "reconstructed_population_rows": int(len(joined)),
            "reconstructed_population_tickers": int(joined["ticker"].nunique()),
            "reconstructed_population_sessions": int(joined["as_of_date"].nunique()),
            "selection_end": selection_end.isoformat(),
            "purge_sessions": [item.isoformat() for item in purge],
            "internal_start": internal[0].isoformat(),
            "reconstructed_selection": reconstructed,
            "exact_metric_matches": exact_metric_matches,
            "mandatory_sample_gate_failures": mandatory_sample_gate_failures,
            "selection_min_raw_rows": PHASE30_SELECTION_MIN_RAW_ROWS,
            "selection_min_signal_sessions": PHASE30_SELECTION_MIN_SIGNAL_SESSIONS,
            "selection_survivor_ids": [],
            "selection_winner_ids": [],
            "finalist_ids": [],
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
        atomic_write_text(
            self.report_path(), json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        return report
