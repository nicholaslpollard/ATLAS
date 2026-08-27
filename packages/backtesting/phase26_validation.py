from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

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
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    PHASE26_OUTCOME_FIELDS,
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


def _load_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase26IndependentValidationError(f"missing Phase26 evidence: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Phase26IndependentValidationError(f"Phase26 JSON evidence must be an object: {path}")
    return payload


def _load_parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase26IndependentValidationError(f"missing Phase26 parquet evidence: {path}")
    con = connect_utc(":memory:")
    try:
        return con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY {order_by}"
        ).fetch_df()
    finally:
        con.close()


def _condition_mask(frame: pd.DataFrame, condition: SignalCondition) -> pd.Series:
    if condition.feature not in frame.columns:
        raise Phase26IndependentValidationError(
            f"missing independently validated signal field: {condition.feature}"
        )
    values = pd.to_numeric(frame[condition.feature], errors="coerce")
    if condition.operator == "GT":
        mask = values > condition.value
    elif condition.operator == "GE":
        mask = values >= condition.value
    elif condition.operator == "LT":
        mask = values < condition.value
    elif condition.operator == "LE":
        mask = values <= condition.value
    elif condition.operator == "BETWEEN":
        if condition.upper is None:
            raise Phase26IndependentValidationError("BETWEEN condition lacks upper bound")
        mask = (values >= condition.value) & (values <= condition.upper)
    else:  # pragma: no cover
        raise Phase26IndependentValidationError(f"unsupported condition operator: {condition.operator}")
    return mask.fillna(False).astype(bool)


def independent_candidate_mask(frame: pd.DataFrame, candidate: Phase26CandidateSpec) -> pd.Series:
    if "direction" not in frame.columns:
        raise Phase26IndependentValidationError("Phase26 frame is missing direction")
    expected = "bullish" if candidate.direction == "LONG" else "bearish"
    mask = frame["direction"].astype("string").eq(expected).fillna(False)
    for condition in candidate.conditions:
        mask &= _condition_mask(frame, condition)
    return mask.astype(bool)


def _session_net_mean(frame: pd.DataFrame, *, cost_bps: float) -> float | None:
    if frame.empty:
        return None
    values = pd.to_numeric(frame["directional_return"], errors="coerce")
    data = frame.loc[values.notna(), ["as_of_date"]].copy()
    data["directional_return"] = values.loc[values.notna()].to_numpy()
    if data.empty:
        return None
    gross = data.groupby("as_of_date", sort=True)["directional_return"].mean().mean()
    return float(gross - cost_bps / 10_000.0)


def _float_matches(actual: float | None, reported: object) -> bool:
    if actual is None:
        return reported is None
    if reported is None:
        return False
    try:
        return math.isclose(actual, float(reported), rel_tol=1e-11, abs_tol=1e-11)
    except (TypeError, ValueError):
        return False


def _candidate_keys(frame: pd.DataFrame) -> set[tuple[date, str]]:
    if frame.empty:
        return set()
    return set(
        zip(
            pd.to_datetime(frame["as_of_date"]).dt.date,
            frame["instrument_id"].astype(str),
            strict=False,
        )
    )


class Phase26IndependentValidator:
    """Independently reconcile persisted Phase26 artifacts and reported economics."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.observations = Phase26ObservationBuilder(settings)
        self.research = Phase26DevelopmentResearch(settings)
        self.confirmation = Phase26ProtectedConfirmation(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase26" / "v1" / "validation"

    def report_path(self) -> Path:
        return self.root / "independent_validation.json"

    def _observations(self) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, bool]]:
        report = _load_json(self.observations.report_path())
        development_path = self.observations.development_path()
        protected_path = self.observations.protected_predictors_path()
        development = _load_parquet(development_path, order_by="as_of_date, instrument_id")
        protected = _load_parquet(protected_path, order_by="as_of_date, instrument_id")
        development["as_of_date"] = pd.to_datetime(development["as_of_date"]).dt.date
        development["future_date"] = pd.to_datetime(development["future_date"]).dt.date
        protected["as_of_date"] = pd.to_datetime(protected["as_of_date"]).dt.date
        checks = {
            "report_contract": report.get("contract_version") == PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
            "report_pass": report.get("pass") is True,
            "policy_fingerprint": report.get("phase26_policy_fingerprint") == phase26_policy_fingerprint(),
            "development_sha": report.get("development_sha256") == sha256_file(development_path),
            "protected_sha": report.get("protected_predictors_sha256") == sha256_file(protected_path),
            "development_contract": set(development["contract_version"].astype(str))
            == {PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION},
            "protected_contract": set(protected["contract_version"].astype(str))
            == {PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION},
            "development_unique": not development.duplicated(["as_of_date", "instrument_id"]).any(),
            "protected_unique": not protected.duplicated(["as_of_date", "instrument_id"]).any(),
            "development_future_preprotected": bool(
                not development.empty
                and development["future_date"].max() < date.fromisoformat(PHASE26_PROTECTED_START)
            ),
            "protected_outcomes_absent": not any(field in protected.columns for field in PHASE26_OUTCOME_FIELDS),
            "protected_returns_unread": int(report.get("protected_return_reads", -1)) == 0,
        }
        return development, protected, checks

    def _research(self, development: pd.DataFrame) -> tuple[dict[str, object], dict[str, bool], list[str]]:
        report = _load_json(self.research.report_path())
        finalists = _load_json(self.research.finalists_path())
        signals_path = self.research.signals_path()
        signals = _load_parquet(signals_path, order_by="candidate_id, as_of_date, instrument_id")
        boundaries = report.get("boundaries")
        selection_metrics = report.get("selection_metrics")
        internal_metrics = report.get("internal_metrics")
        if not isinstance(boundaries, dict) or not isinstance(selection_metrics, dict) or not isinstance(internal_metrics, dict):
            raise Phase26IndependentValidationError("malformed Phase26 development report")
        selection_start = date.fromisoformat(str(boundaries["selection_start"]))
        selection_end = date.fromisoformat(str(boundaries["selection_end"]))
        internal_start = date.fromisoformat(str(boundaries["internal_start"]))
        internal_end = date.fromisoformat(str(boundaries["internal_end"]))
        selected_ids = tuple(str(value) for value in report.get("selected_candidate_ids", []))
        finalist_ids = tuple(str(value) for value in report.get("finalist_candidate_ids", []))
        candidate_map = {candidate.candidate_id: candidate for candidate in PHASE26_CANDIDATES}
        mismatches: list[str] = []

        for candidate in PHASE26_CANDIDATES:
            independent = development.loc[independent_candidate_mask(development, candidate)].copy()
            persisted = signals.loc[signals["candidate_id"].astype(str) == candidate.candidate_id].copy()
            if _candidate_keys(independent) != _candidate_keys(persisted):
                mismatches.append(f"{candidate.candidate_id}:signal_keys")
                continue
            selection = independent.loc[
                (independent["as_of_date"] >= selection_start)
                & (independent["as_of_date"] <= selection_end)
            ]
            metrics = selection_metrics.get(candidate.candidate_id)
            if not isinstance(metrics, dict):
                mismatches.append(f"{candidate.candidate_id}:selection_metrics")
                continue
            if int(metrics.get("raw_rows", -1)) != len(selection):
                mismatches.append(f"{candidate.candidate_id}:selection_rows")
            if int(metrics.get("signal_sessions", -1)) != selection["as_of_date"].nunique():
                mismatches.append(f"{candidate.candidate_id}:selection_sessions")
            if not _float_matches(
                _session_net_mean(selection, cost_bps=PHASE26_PRIMARY_COST_BPS),
                metrics.get("primary_mean_return"),
            ):
                mismatches.append(f"{candidate.candidate_id}:selection_primary")
            if not _float_matches(
                _session_net_mean(selection, cost_bps=PHASE26_STRESS_COST_BPS),
                metrics.get("stress_mean_return"),
            ):
                mismatches.append(f"{candidate.candidate_id}:selection_stress")

        for candidate_id in selected_ids:
            candidate = candidate_map[candidate_id]
            internal = development.loc[
                independent_candidate_mask(development, candidate)
                & (development["as_of_date"] >= internal_start)
                & (development["as_of_date"] <= internal_end)
            ]
            metrics = internal_metrics.get(candidate_id)
            if not isinstance(metrics, dict):
                mismatches.append(f"{candidate_id}:internal_metrics")
                continue
            if int(metrics.get("raw_rows", -1)) != len(internal):
                mismatches.append(f"{candidate_id}:internal_rows")
            if int(metrics.get("signal_sessions", -1)) != internal["as_of_date"].nunique():
                mismatches.append(f"{candidate_id}:internal_sessions")
            if not _float_matches(
                _session_net_mean(internal, cost_bps=PHASE26_PRIMARY_COST_BPS),
                metrics.get("primary_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:internal_primary")
            if not _float_matches(
                _session_net_mean(internal, cost_bps=PHASE26_STRESS_COST_BPS),
                metrics.get("stress_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:internal_stress")

        family_direction = [
            (candidate_map[candidate_id].family, candidate_map[candidate_id].direction)
            for candidate_id in selected_ids
        ]
        checks = {
            "report_contract": report.get("contract_version") == PHASE26_RESEARCH_REPORT_CONTRACT_VERSION,
            "report_pass": report.get("pass") is True,
            "policy_fingerprint": report.get("phase26_policy_fingerprint") == phase26_policy_fingerprint(),
            "signals_sha": report.get("development_signals_sha256") == sha256_file(signals_path),
            "signal_contract": bool(
                signals.empty
                or set(signals["signal_contract_version"].astype(str)) == {PHASE26_SIGNAL_ARTIFACT_CONTRACT_VERSION}
            ),
            "all_24_candidates_reported": len(selection_metrics) == 24,
            "holm_24": isinstance(report.get("holm_bonferroni"), dict)
            and len(report["holm_bonferroni"]) == 24,
            "one_per_family_direction": len(family_direction) == len(set(family_direction)),
            "finalists_subset_selected": set(finalist_ids).issubset(set(selected_ids)),
            "frozen_finalist_contract": finalists.get("contract_version")
            == PHASE26_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "frozen_finalists_match": finalists.get("finalist_candidate_ids") == list(finalist_ids),
            "protected_unread": int(report.get("protected_returns_read", -1)) == 0
            and int(finalists.get("protected_returns_read", -1)) == 0,
            "independent_reconciliation": not mismatches,
        }
        return report, checks, mismatches

    def _confirmation(
        self, protected: pd.DataFrame, research_report: dict[str, object]
    ) -> tuple[dict[str, bool], list[str], list[str]]:
        report = _load_json(self.confirmation.report_path())
        support_path = self.confirmation.support_overlay_path()
        support = _load_json(support_path)
        finalists = tuple(str(value) for value in research_report.get("finalist_candidate_ids", []))
        confirmed = [str(value) for value in report.get("confirmed_candidate_ids", [])]
        supported = [str(value) for value in support.get("supported_candidate_ids", [])]
        mismatches: list[str] = []
        checks = {
            "report_contract": report.get("contract_version") == PHASE26_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "report_pass": report.get("pass") is True,
            "policy_fingerprint": report.get("phase26_policy_fingerprint") == phase26_policy_fingerprint(),
            "support_contract": support.get("contract_version") == PHASE26_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "support_matches_confirmed": supported == confirmed,
            "confirmed_subset_finalists": set(confirmed).issubset(set(finalists)),
            "analytical_only": support.get("authority") == "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY"
            and support.get("paper_authority") is False
            and support.get("live_authority") is False,
            "incumbent_support_unchanged": support.get("incumbent_phase11_support_unchanged") is True,
            "support_sha": report.get("support_overlay_sha256") == sha256_file(support_path),
        }
        if not finalists:
            checks["zero_finalist_skip"] = report.get("status") == "SKIPPED_ZERO_FINALISTS"
            checks["zero_finalist_protected_unread"] = int(report.get("protected_returns_read", -1)) == 0
            checks["zero_finalist_support_empty"] = not supported
            return checks, mismatches, confirmed

        signals_path = self.confirmation.protected_signals_path()
        signals = _load_parquet(signals_path, order_by="candidate_id, as_of_date, instrument_id")
        if not signals.empty:
            signals["as_of_date"] = pd.to_datetime(signals["as_of_date"]).dt.date
        candidate_map = {candidate.candidate_id: candidate for candidate in PHASE26_CANDIDATES}
        metrics_map = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
        for candidate_id in finalists:
            expected = protected.loc[
                independent_candidate_mask(protected, candidate_map[candidate_id])
            ].copy()
            actual = signals.loc[signals["candidate_id"].astype(str) == candidate_id].copy()
            if not _candidate_keys(actual).issubset(_candidate_keys(expected)):
                mismatches.append(f"{candidate_id}:protected_signal_keys")
            metrics = metrics_map.get(candidate_id)
            if not isinstance(metrics, dict):
                mismatches.append(f"{candidate_id}:protected_metrics")
                continue
            if int(metrics.get("raw_rows", -1)) != len(actual):
                mismatches.append(f"{candidate_id}:protected_rows")
            if int(metrics.get("signal_sessions", -1)) != actual["as_of_date"].nunique():
                mismatches.append(f"{candidate_id}:protected_sessions")
            if not _float_matches(
                _session_net_mean(actual, cost_bps=PHASE26_PRIMARY_COST_BPS),
                metrics.get("primary_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:protected_primary")
            if not _float_matches(
                _session_net_mean(actual, cost_bps=PHASE26_STRESS_COST_BPS),
                metrics.get("stress_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:protected_stress")
        checks["protected_signals_sha"] = report.get("protected_signals_sha256") == sha256_file(signals_path)
        checks["protected_only_finalists"] = set(signals["candidate_id"].astype(str).unique()).issubset(set(finalists))
        checks["independent_reconciliation"] = not mismatches
        checks["protected_reads_bounded"] = int(report.get("protected_returns_read", -1)) == int(
            report.get("protected_candidate_rows_read", -2)
        )
        return checks, mismatches, confirmed

    def run(self) -> dict[str, object]:
        development, protected, observation_checks = self._observations()
        research_report, research_checks, research_mismatches = self._research(development)
        confirmation_checks, protected_mismatches, confirmed = self._confirmation(
            protected, research_report
        )
        grouped = {
            "observations": observation_checks,
            "research": research_checks,
            "confirmation": confirmation_checks,
        }
        failures = [
            f"{group}.{name}"
            for group, checks in grouped.items()
            for name, passed in checks.items()
            if not passed
        ]
        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_VALIDATION_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "checks": grouped,
            "research_reconciliation_mismatches": research_mismatches,
            "protected_reconciliation_mismatches": protected_mismatches,
            "supported_candidate_ids": confirmed,
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
