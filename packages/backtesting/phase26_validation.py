from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_confirmation import (
    PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE26_SUPPORT_OVERLAY_CONTRACT_VERSION,
    Phase26ProtectedConfirmation,
)
from .phase26_observations import (
    PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION,
    PHASE26_OBSERVATION_FIELDS if False else PHASE26_OUTCOME_FIELDS,
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase26_policy import (
    PHASE26_CANDIDATES,
    PHASE26_PRIMARY_COST_BPS,
    PHASE26_PROTECTED_START,
    PHASE26_STRESS_COST_BPS,
    Phase26CandidateSpec,
    SignalCondition,
    phase26_policy_fingerprint,
)
from .phase26_research import (
    PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
    PHASE26_SIGNAL_ARTIFACT_CONTRACT_VERSION,
    Phase26DevelopmentResearch,
)


PHASE26_VALIDATION_CONTRACT_VERSION = (
    "phase26-validation-v1-independent-persisted-artifact-reconciliation"
)


class Phase26IndependentValidationError(RuntimeError):
    pass


def _json_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase26IndependentValidationError(f"missing Phase26 evidence: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase26IndependentValidationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase26IndependentValidationError(f"JSON evidence is not an object: {path}")
    return payload


def _parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase26IndependentValidationError(f"missing parquet evidence: {path}")
    con = connect_utc(":memory:")
    try:
        return con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY {order_by}"
        ).fetch_df()
    finally:
        con.close()


def _independent_condition(frame: pd.DataFrame, condition: SignalCondition) -> pd.Series:
    if condition.feature not in frame.columns:
        raise Phase26IndependentValidationError(
            f"candidate field missing during independent validation: {condition.feature}"
        )
    value = pd.to_numeric(frame[condition.feature], errors="coerce")
    if condition.operator == "GT":
        result = value > condition.value
    elif condition.operator == "GE":
        result = value >= condition.value
    elif condition.operator == "LT":
        result = value < condition.value
    elif condition.operator == "LE":
        result = value <= condition.value
    elif condition.operator == "BETWEEN":
        if condition.upper is None:
            raise Phase26IndependentValidationError("BETWEEN condition is missing upper bound")
        result = (value >= condition.value) & (value <= condition.upper)
    else:  # pragma: no cover - frozen Literal/policy prevents this.
        raise Phase26IndependentValidationError(
            f"unknown Phase26 operator: {condition.operator}"
        )
    return result.fillna(False).astype(bool)


def independent_candidate_mask(
    frame: pd.DataFrame, candidate: Phase26CandidateSpec
) -> pd.Series:
    expected = "bullish" if candidate.direction == "LONG" else "bearish"
    if "direction" not in frame.columns:
        raise Phase26IndependentValidationError("Phase26 frame is missing direction")
    result = frame["direction"].astype("string").eq(expected).fillna(False)
    for condition in candidate.conditions:
        result &= _independent_condition(frame, condition)
    return result.astype(bool)


def _session_primary_mean(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    values = pd.to_numeric(frame["directional_return"], errors="coerce")
    data = frame.loc[values.notna(), ["as_of_date"]].copy()
    data["directional_return"] = values.loc[values.notna()].to_numpy()
    if data.empty:
        return None
    session = data.groupby("as_of_date", sort=True)["directional_return"].mean()
    return float(session.mean() - PHASE26_PRIMARY_COST_BPS / 10_000.0)


def _session_stress_mean(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    values = pd.to_numeric(frame["directional_return"], errors="coerce")
    data = frame.loc[values.notna(), ["as_of_date"]].copy()
    data["directional_return"] = values.loc[values.notna()].to_numpy()
    if data.empty:
        return None
    session = data.groupby("as_of_date", sort=True)["directional_return"].mean()
    return float(session.mean() - PHASE26_STRESS_COST_BPS / 10_000.0)


def _close(left: float | None, right: object, *, tol: float = 1e-12) -> bool:
    if left is None:
        return right is None
    if right is None:
        return False
    try:
        return math.isclose(left, float(right), rel_tol=tol, abs_tol=tol)
    except (TypeError, ValueError):
        return False


class Phase26IndependentValidator:
    """Reconcile persisted Phase26 evidence without calling the research signal engine."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.observations = Phase26ObservationBuilder(settings)
        self.research = Phase26DevelopmentResearch(settings)
        self.confirmation = Phase26ProtectedConfirmation(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase26" / "v1" / "validation"

    def report_path(self) -> Path:
        return self.root / "independent_validation.json"

    def _validate_observations(self) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], dict[str, bool]]:
        report_path = self.observations.report_path()
        report = _json_object(report_path)
        development_path = self.observations.development_path()
        protected_path = self.observations.protected_predictors_path()
        development = _parquet(development_path, order_by="as_of_date, instrument_id")
        protected = _parquet(protected_path, order_by="as_of_date, instrument_id")
        development["as_of_date"] = pd.to_datetime(development["as_of_date"]).dt.date
        development["future_date"] = pd.to_datetime(development["future_date"]).dt.date
        protected["as_of_date"] = pd.to_datetime(protected["as_of_date"]).dt.date
        outcome_fields = tuple(PHASE26_OUTCOME_FIELDS)
        checks = {
            "observation_contract": report.get("contract_version")
            == PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
            "observation_pass": report.get("pass") is True,
            "policy_fingerprint": report.get("phase26_policy_fingerprint")
            == phase26_policy_fingerprint(),
            "development_sha": report.get("development_sha256") == sha256_file(development_path),
            "protected_sha": report.get("protected_predictors_sha256") == sha256_file(protected_path),
            "development_contract": set(development["contract_version"].astype(str))
            == {PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION},
            "protected_contract": set(protected["contract_version"].astype(str))
            == {PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION},
            "development_unique": not development.duplicated(
                ["as_of_date", "instrument_id"], keep=False
            ).any(),
            "protected_unique": not protected.duplicated(
                ["as_of_date", "instrument_id"], keep=False
            ).any(),
            "development_preprotected": bool(
                not development.empty
                and development["future_date"].max() < date.fromisoformat(PHASE26_PROTECTED_START)
            ),
            "protected_dates_correct": bool(
                not protected.empty
                and protected["as_of_date"].min() >= date.fromisoformat(PHASE26_PROTECTED_START)
            ),
            "protected_outcomes_absent": not any(field in protected.columns for field in outcome_fields),
            "protected_reads_zero_before_confirmation": int(report.get("protected_return_reads", -1)) == 0,
            "external_activity_zero": all(
                int(report.get(field, -1)) == 0
                for field in (
                    "provider_reads",
                    "provider_writes",
                    "broker_reads",
                    "broker_writes",
                    "order_writes",
                    "paper_submits",
                    "live_writes",
                    "automation_writes",
                )
            ),
        }
        return development, protected, report, checks

    def _validate_research(
        self, development: pd.DataFrame
    ) -> tuple[dict[str, object], dict[str, bool], dict[str, object]]:
        report_path = self.research.report_path()
        report = _json_object(report_path)
        finalists_path = self.research.finalists_path()
        finalists = _json_object(finalists_path)
        signals_path = self.research.signals_path()
        signals = _parquet(signals_path, order_by="candidate_id, as_of_date, instrument_id")
        if not signals.empty:
            signals["as_of_date"] = pd.to_datetime(signals["as_of_date"]).dt.date
        boundaries = report.get("boundaries")
        if not isinstance(boundaries, dict):
            raise Phase26IndependentValidationError("Phase26 research boundaries are malformed")
        selection_start = date.fromisoformat(str(boundaries["selection_start"]))
        selection_end = date.fromisoformat(str(boundaries["selection_end"]))
        internal_start = date.fromisoformat(str(boundaries["internal_start"]))
        internal_end = date.fromisoformat(str(boundaries["internal_end"]))
        selection_report = report.get("selection_metrics")
        internal_report = report.get("internal_metrics")
        if not isinstance(selection_report, dict) or not isinstance(internal_report, dict):
            raise Phase26IndependentValidationError("Phase26 research metrics are malformed")

        mismatches: list[str] = []
        candidate_by_id = {candidate.candidate_id: candidate for candidate in PHASE26_CANDIDATES}
        for candidate in PHASE26_CANDIDATES:
            independent = development.loc[independent_candidate_mask(development, candidate)].copy()
            persisted = signals.loc[signals["candidate_id"].astype(str) == candidate.candidate_id].copy()
            independent_keys = set(
                zip(independent["as_of_date"], independent["instrument_id"].astype(str), strict=False)
            )
            persisted_keys = set(
                zip(persisted["as_of_date"], persisted["instrument_id"].astype(str), strict=False)
            )
            if independent_keys != persisted_keys:
                mismatches.append(f"{candidate.candidate_id}:signal_keys")
                continue
            selection = independent.loc[
                (independent["as_of_date"] >= selection_start)
                & (independent["as_of_date"] <= selection_end)
            ]
            reported = selection_report.get(candidate.candidate_id)
            if not isinstance(reported, dict):
                mismatches.append(f"{candidate.candidate_id}:selection_report")
                continue
            if int(reported.get("raw_rows", -1)) != len(selection):
                mismatches.append(f"{candidate.candidate_id}:selection_rows")
            if int(reported.get("signal_sessions", -1)) != selection["as_of_date"].nunique():
                mismatches.append(f"{candidate.candidate_id}:selection_sessions")
            if not _close(_session_primary_mean(selection), reported.get("primary_mean_return")):
                mismatches.append(f"{candidate.candidate_id}:selection_primary_mean")
            if not _close(_session_stress_mean(selection), reported.get("stress_mean_return")):
                mismatches.append(f"{candidate.candidate_id}:selection_stress_mean")

        selected = tuple(str(item) for item in report.get("selected_candidate_ids", []))
        finalist_ids = tuple(str(item) for item in report.get("finalist_candidate_ids", []))
        for candidate_id in selected:
            candidate = candidate_by_id[candidate_id]
            internal = development.loc[
                independent_candidate_mask(development, candidate)
                & (development["as_of_date"] >= internal_start)
                & (development["as_of_date"] <= internal_end)
            ].copy()
            reported = internal_report.get(candidate_id)
            if not isinstance(reported, dict):
                mismatches.append(f"{candidate_id}:internal_report")
                continue
            if int(reported.get("raw_rows", -1)) != len(internal):
                mismatches.append(f"{candidate_id}:internal_rows")
            if int(reported.get("signal_sessions", -1)) != internal["as_of_date"].nunique():
                mismatches.append(f"{candidate_id}:internal_sessions")
            if not _close(_session_primary_mean(internal), reported.get("primary_mean_return")):
                mismatches.append(f"{candidate_id}:internal_primary_mean")
            if not _close(_session_stress_mean(internal), reported.get("stress_mean_return")):
                mismatches.append(f"{candidate_id}:internal_stress_mean")

        family_direction = [
            (candidate_by_id[candidate_id].family, candidate_by_id[candidate_id].direction)
            for candidate_id in selected
        ]
        checks = {
            "research_contract": report.get("contract_version") == PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
            "research_pass": report.get("pass") is True,
            "policy_fingerprint": report.get("phase26_policy_fingerprint") == phase26_policy_fingerprint(),
            "signals_sha": report.get("development_signals_sha256") == sha256_file(signals_path),
            "finalists_sha": report.get("finalists_sha256") == sha256_file(finalists_path),
            "signal_contract": bool(
                signals.empty
                or set(signals["signal_contract_version"].astype(str))
                == {PHASE26_SIGNAL_ARTIFACT_CONTRACT_VERSION}
            ),
            "all_24_reported": len(selection_report) == len(PHASE26_CANDIDATES) == 24,
            "global_holm_24": isinstance(report.get("holm_bonferroni"), dict)
            and len(report["holm_bonferroni"]) == 24,
            "independent_signal_reconciliation": not mismatches,
            "one_selected_per_family_direction": len(family_direction) == len(set(family_direction)),
            "finalists_subset_selected": set(finalist_ids).issubset(set(selected)),
            "frozen_finalist_contract": finalists.get("contract_version")
            == PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "frozen_finalist_ids_match": finalists.get("finalist_candidate_ids") == list(finalist_ids),
            "protected_unread_during_research": int(report.get("protected_returns_read", -1)) == 0
            and int(finalists.get("protected_returns_read", -1)) == 0,
        }
        detail: dict[str, object] = {"reconciliation_mismatches": mismatches}
        return report, checks, detail

    def _validate_confirmation(
        self, protected: pd.DataFrame, research_report: dict[str, object]
    ) -> tuple[dict[str, object], dict[str, bool], dict[str, object]]:
        report_path = self.confirmation.report_path()
        report = _json_object(report_path)
        support_path = self.confirmation.support_overlay_path()
        support = _json_object(support_path)
        finalists = tuple(str(item) for item in research_report.get("finalist_candidate_ids", []))
        confirmed = tuple(str(item) for item in report.get("confirmed_candidate_ids", []))
        supported = tuple(str(item) for item in support.get("supported_candidate_ids", []))
        detail: dict[str, object] = {}
        checks: dict[str, bool] = {
            "confirmation_contract": report.get("contract_version")
            == PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "confirmation_pass": report.get("pass") is True,
            "policy_fingerprint": report.get("phase26_policy_fingerprint") == phase26_policy_fingerprint(),
            "support_contract": support.get("contract_version") == PHASE26_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "support_policy_fingerprint": support.get("phase26_policy_fingerprint")
            == phase26_policy_fingerprint(),
            "support_matches_confirmed": supported == confirmed,
            "confirmed_subset_finalists": set(confirmed).issubset(set(finalists)),
            "analytical_only_authority": support.get("authority")
            == "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY"
            and support.get("paper_authority") is False
            and support.get("live_authority") is False,
            "incumbent_support_unchanged": support.get("incumbent_phase11_support_unchanged") is True,
            "external_activity_zero": all(
                int(report.get(field, -1)) == 0
                for field in (
                    "provider_reads",
                    "provider_writes",
                    "broker_reads",
                    "broker_writes",
                    "order_writes",
                    "paper_submits",
                    "live_writes",
                )
            ),
        }
        if not finalists:
            checks.update(
                {
                    "zero_finalist_status": report.get("status") == "SKIPPED_ZERO_FINALISTS",
                    "zero_finalist_protected_reads": int(report.get("protected_returns_read", -1)) == 0,
                    "zero_finalist_support_empty": not supported,
                }
            )
            return report, checks, detail

        signals_path = self.confirmation.protected_signals_path()
        signals = _parquet(signals_path, order_by="candidate_id, as_of_date, instrument_id")
        if not signals.empty:
            signals["as_of_date"] = pd.to_datetime(signals["as_of_date"]).dt.date
            signals["future_date"] = pd.to_datetime(signals["future_date"]).dt.date
        candidate_by_id = {candidate.candidate_id: candidate for candidate in PHASE26_CANDIDATES}
        mismatches: list[str] = []
        for candidate_id in finalists:
            candidate = candidate_by_id[candidate_id]
            expected = protected.loc[independent_candidate_mask(protected, candidate)].copy()
            actual = signals.loc[signals["candidate_id"].astype(str) == candidate_id].copy()
            # Split/missing endpoints can censor actual rows, so actual must be a subset
            # of independently fired predictor keys; it may not include any non-fired key.
            expected_keys = set(
                zip(expected["as_of_date"], expected["instrument_id"].astype(str), strict=False)
            )
            actual_keys = set(
                zip(actual["as_of_date"], actual["instrument_id"].astype(str), strict=False)
            )
            if not actual_keys.issubset(expected_keys):
                mismatches.append(f"{candidate_id}:protected_signal_keys")
                continue
            metrics = report.get("metrics", {}).get(candidate_id) if isinstance(report.get("metrics"), dict) else None
            if not isinstance(metrics, dict):
                mismatches.append(f"{candidate_id}:protected_metrics")
                continue
            if int(metrics.get("raw_rows", -1)) != len(actual):
                mismatches.append(f"{candidate_id}:protected_rows")
            if int(metrics.get("signal_sessions", -1)) != actual["as_of_date"].nunique():
                mismatches.append(f"{candidate_id}:protected_sessions")
            if not _close(_session_primary_mean(actual), metrics.get("primary_mean_return")):
                mismatches.append(f"{candidate_id}:protected_primary_mean")
            if not _close(_session_stress_mean(actual), metrics.get("stress_mean_return")):
                mismatches.append(f"{candidate_id}:protected_stress_mean")
        checks.update(
            {
                "protected_signals_sha": report.get("protected_signals_sha256") == sha256_file(signals_path),
                "protected_only_finalists": set(signals["candidate_id"].astype(str).unique()).issubset(set(finalists)),
                "independent_protected_reconciliation": not mismatches,
                "protected_reads_bounded": int(report.get("protected_returns_read", -1))
                == int(report.get("protected_candidate_rows_read", -2)),
                "support_overlay_sha": report.get("support_overlay_sha256") == sha256_file(support_path),
            }
        )
        detail["protected_reconciliation_mismatches"] = mismatches
        return report, checks, detail

    def run(self) -> dict[str, object]:
        development, protected, observation_report, observation_checks = self._validate_observations()
        research_report, research_checks, research_detail = self._validate_research(development)
        confirmation_report, confirmation_checks, confirmation_detail = self._validate_confirmation(
            protected, research_report
        )
        checks = {
            "observations": observation_checks,
            "research": research_checks,
            "confirmation": confirmation_checks,
        }
        failures = [
            f"{group}.{name}"
            for group, group_checks in checks.items()
            for name, passed in group_checks.items()
            if not passed
        ]
        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_VALIDATION_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "observation_report_sha256": sha256_file(self.observations.report_path()),
            "research_report_sha256": sha256_file(self.research.report_path()),
            "confirmation_report_sha256": sha256_file(self.confirmation.report_path()),
            "supported_candidate_ids": confirmation_report.get("confirmed_candidate_ids", []),
            "finalist_candidate_ids": research_report.get("finalist_candidate_ids", []),
            "checks": checks,
            "details": {**research_detail, **confirmation_detail},
            "failures": failures,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": not failures,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        if failures:
            raise Phase26IndependentValidationError(
                "Phase26 independent validation failed: " + ", ".join(failures)
            )
        return report
