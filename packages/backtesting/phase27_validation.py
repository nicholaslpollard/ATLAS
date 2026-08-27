from __future__ import annotations

import json
import math
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

from .phase27_blindness import (
    PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase27ProtectedBlindnessAudit,
)
from .phase27_confirmation import (
    PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE27_PROTECTED_PREDICTION_CONTRACT_VERSION,
    PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION,
    PHASE27_PROTECTED_SCORE_SIGNAL_CONTRACT_VERSION,
    PHASE27_PROTECTED_SIGNAL_CONTRACT_VERSION,
    PHASE27_SUPPORT_OVERLAY_CONTRACT_VERSION,
    Phase27ProtectedConfirmation,
)
from .phase27_policy import (
    PHASE27_CANDIDATES,
    PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS,
    PHASE27_MULTIPLE_TESTING_ALPHA,
    PHASE27_PREDICTOR_FIELDS,
    PHASE27_PRIMARY_COST_BPS,
    PHASE27_SIGNAL_TAIL_FRACTION,
    PHASE27_STRESS_COST_BPS,
    phase27_policy_fingerprint,
)
from .phase27_population import (
    PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION,
    PHASE27_POPULATION_REPORT_CONTRACT_VERSION,
    PHASE27_PROTECTED_MODEL_FRAME_CONTRACT_VERSION,
    Phase27PopulationBuilder,
    transformed_feature_names,
)
from .phase27_research import (
    PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE27_PREDICTION_ARTIFACT_CONTRACT_VERSION,
    PHASE27_RESEARCH_REPORT_CONTRACT_VERSION,
    PHASE27_SIGNAL_ARTIFACT_CONTRACT_VERSION,
    Phase27DevelopmentResearch,
)


PHASE27_VALIDATION_CONTRACT_VERSION = (
    "phase27-validation-v1-independent-tail-economics-protected-artifact-reconciliation"
)


class Phase27IndependentValidationError(RuntimeError):
    pass


def _load_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase27IndependentValidationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase27IndependentValidationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase27IndependentValidationError(f"{label} must be an object")
    return payload


def _load_parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase27IndependentValidationError(f"missing parquet evidence: {path}")
    con = connect_utc(":memory:")
    try:
        frame = con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY {order_by}"
        ).fetch_df()
    finally:
        con.close()
    if "as_of_date" in frame.columns:
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
    if "future_date" in frame.columns:
        frame["future_date"] = pd.to_datetime(frame["future_date"]).dt.date
    return frame


def _float_matches(actual: float | None, reported: object) -> bool:
    if actual is None:
        return reported is None
    if reported is None:
        return False
    try:
        return math.isclose(actual, float(reported), rel_tol=1e-11, abs_tol=1e-11)
    except (TypeError, ValueError):
        return False


def _session_net_mean(frame: pd.DataFrame, *, cost_bps: float) -> float | None:
    if frame.empty:
        return None
    values = pd.to_numeric(frame["directional_return"], errors="coerce")
    data = frame.loc[values.notna(), ["as_of_date"]].copy()
    data["directional_return"] = values.loc[values.notna()].to_numpy()
    if data.empty:
        return None
    gross = (
        data.groupby("as_of_date", sort=True, observed=True)["directional_return"]
        .mean()
        .mean()
    )
    return float(gross - cost_bps / 10_000.0)


def _keys(frame: pd.DataFrame) -> set[tuple[str, date, str]]:
    if frame.empty:
        return set()
    return set(
        zip(
            frame["candidate_id"].astype(str),
            pd.to_datetime(frame["as_of_date"]).dt.date,
            frame["instrument_id"].astype(str),
            strict=False,
        )
    )


def independent_fixed_tail_keys(predictions: pd.DataFrame) -> set[tuple[str, date, str]]:
    if predictions.empty:
        return set()
    required = {"candidate_id", "as_of_date", "instrument_id", "phase27_score"}
    if not required.issubset(predictions.columns):
        raise Phase27IndependentValidationError("prediction artifact lacks fixed-tail fields")
    result: set[tuple[str, date, str]] = set()
    work = predictions.copy()
    work["as_of_date"] = pd.to_datetime(work["as_of_date"]).dt.date
    for (candidate_id, session), group in work.groupby(
        ["candidate_id", "as_of_date"], sort=True, observed=True
    ):
        ordered = group.sort_values(
            ["phase27_score", "instrument_id"],
            ascending=[False, True],
            kind="stable",
        )
        count = max(1, int(math.ceil(PHASE27_SIGNAL_TAIL_FRACTION * len(ordered))))
        for instrument_id in ordered.iloc[:count]["instrument_id"].astype(str):
            result.add((str(candidate_id), session, instrument_id))
    return result


def independent_holm(
    p_values: Mapping[str, float], *, alpha: float = PHASE27_MULTIPLE_TESTING_ALPHA
) -> dict[str, bool]:
    ordered = sorted((float(value), str(key)) for key, value in p_values.items())
    result: dict[str, bool] = {}
    active = True
    total = len(ordered)
    for index, (p_value, key) in enumerate(ordered):
        threshold = alpha / (total - index) if total else 0.0
        reject = bool(active and p_value <= threshold)
        result[key] = reject
        if not reject:
            active = False
    return result


class Phase27IndependentValidator:
    """Reconcile Phase27 persisted evidence without trusting its selection helpers."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase27PopulationBuilder(settings)
        self.research = Phase27DevelopmentResearch(settings)
        self.blindness = Phase27ProtectedBlindnessAudit(settings)
        self.confirmation = Phase27ProtectedConfirmation(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase27" / "v1" / "validation"

    def report_path(self) -> Path:
        return self.root / "independent_validation.json"

    def _population_checks(self) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, bool]]:
        report = _load_json(self.population.report_path(), "Phase27 population report")
        development_path = self.population.development_path()
        protected_path = self.population.protected_path()
        development = _load_parquet(
            development_path, order_by="as_of_date, instrument_id"
        )
        protected = _load_parquet(
            protected_path, order_by="as_of_date, instrument_id"
        )
        transformed = list(transformed_feature_names())
        checks = {
            "population_contract": report.get("contract_version")
            == PHASE27_POPULATION_REPORT_CONTRACT_VERSION,
            "population_pass": report.get("pass") is True,
            "population_policy": report.get("phase27_policy_fingerprint")
            == phase27_policy_fingerprint(),
            "development_sha": report.get("development_sha256")
            == sha256_file(development_path),
            "protected_sha": report.get("protected_sha256")
            == sha256_file(protected_path),
            "development_contract": set(
                development["phase27_contract_version"].astype(str)
            )
            == {PHASE27_DEVELOPMENT_MODEL_FRAME_CONTRACT_VERSION},
            "protected_contract": set(protected["phase27_contract_version"].astype(str))
            == {PHASE27_PROTECTED_MODEL_FRAME_CONTRACT_VERSION},
            "development_unique": not bool(
                development.duplicated(["as_of_date", "instrument_id"]).any()
            ),
            "protected_unique": not bool(
                protected.duplicated(["as_of_date", "instrument_id"]).any()
            ),
            "exact_predictor_count": len(PHASE27_PREDICTOR_FIELDS) == 29
            and len(transformed) == 29,
            "transformed_finite": bool(
                np.isfinite(development[transformed].to_numpy(dtype=float)).all()
                and np.isfinite(protected[transformed].to_numpy(dtype=float)).all()
            ),
            "transformed_bounded": bool(
                development[transformed].to_numpy(dtype=float).min() >= -1.0
                and development[transformed].to_numpy(dtype=float).max() <= 1.0
                and protected[transformed].to_numpy(dtype=float).min() >= -1.0
                and protected[transformed].to_numpy(dtype=float).max() <= 1.0
            ),
            "protected_outcomes_absent": not any(
                field in protected.columns
                for field in PHASE27_FORBIDDEN_PROTECTED_OUTCOME_FIELDS
            ),
            "population_protected_reads_zero": int(
                report.get("protected_return_reads", -1)
            )
            == 0,
        }
        return development, protected, checks

    def _research_checks(self) -> tuple[dict[str, object], dict[str, object], dict[str, bool], list[str]]:
        report = _load_json(self.research.report_path(), "Phase27 research report")
        finalists = _load_json(self.research.finalists_path(), "Phase27 finalists")
        predictions_path = self.research.predictions_path()
        signals_path = self.research.signals_path()
        predictions = _load_parquet(
            predictions_path,
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )
        signals = _load_parquet(
            signals_path,
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )
        mismatches: list[str] = []
        selection_metrics = report.get("selection_metrics")
        internal_metrics = report.get("internal_metrics")
        selection_checks = report.get("selection_checks")
        holm_report = report.get("holm_bonferroni")
        if not all(
            isinstance(value, dict)
            for value in (selection_metrics, internal_metrics, selection_checks, holm_report)
        ):
            raise Phase27IndependentValidationError("Phase27 research metrics are malformed")
        assert isinstance(selection_metrics, dict)
        assert isinstance(internal_metrics, dict)
        assert isinstance(selection_checks, dict)
        assert isinstance(holm_report, dict)

        candidate_ids = {candidate.candidate_id for candidate in PHASE27_CANDIDATES}
        selection_predictions = predictions.loc[
            predictions["research_stage"].astype(str) == "SELECTION_OOS"
        ].copy()
        selection_signals = signals.loc[
            signals["research_stage"].astype(str) == "SELECTION_OOS"
        ].copy()
        if set(selection_predictions["candidate_id"].astype(str)) != candidate_ids:
            mismatches.append("selection_prediction_candidate_coverage")
        if independent_fixed_tail_keys(selection_predictions) != _keys(selection_signals):
            mismatches.append("selection_fixed_tail_keys")

        p_values: dict[str, float] = {}
        for candidate in PHASE27_CANDIDATES:
            candidate_id = candidate.candidate_id
            rows = selection_signals.loc[
                selection_signals["candidate_id"].astype(str) == candidate_id
            ].copy()
            metrics = selection_metrics.get(candidate_id)
            if not isinstance(metrics, dict):
                mismatches.append(f"{candidate_id}:selection_metrics_missing")
                continue
            if int(metrics.get("raw_rows", -1)) != len(rows):
                mismatches.append(f"{candidate_id}:selection_rows")
            if int(metrics.get("signal_sessions", -1)) != rows["as_of_date"].nunique():
                mismatches.append(f"{candidate_id}:selection_sessions")
            if not _float_matches(
                _session_net_mean(rows, cost_bps=PHASE27_PRIMARY_COST_BPS),
                metrics.get("primary_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:selection_primary")
            if not _float_matches(
                _session_net_mean(rows, cost_bps=PHASE27_STRESS_COST_BPS),
                metrics.get("stress_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:selection_stress")
            p_value = metrics.get("primary_bootstrap_p_value")
            p_values[candidate_id] = 1.0 if p_value is None else float(p_value)

        holm_independent = independent_holm(p_values)
        for candidate_id, rejected in holm_independent.items():
            item = holm_report.get(candidate_id)
            if not isinstance(item, dict) or bool(item.get("rejected_null")) != rejected:
                mismatches.append(f"{candidate_id}:holm")

        reported_survivors = set(
            str(value) for value in report.get("selection_survivor_ids", [])
        )
        expected_survivors = {
            candidate.candidate_id
            for candidate in PHASE27_CANDIDATES
            if isinstance(selection_checks.get(candidate.candidate_id), dict)
            and all(bool(value) for value in selection_checks[candidate.candidate_id].values())
            and holm_independent.get(candidate.candidate_id) is True
        }
        if reported_survivors != expected_survivors:
            mismatches.append("selection_survivor_set")

        winner_ids = tuple(str(value) for value in report.get("selection_winner_ids", []))
        winner_directions = [
            next(
                candidate.direction
                for candidate in PHASE27_CANDIDATES
                if candidate.candidate_id == candidate_id
            )
            for candidate_id in winner_ids
        ]
        if len(winner_directions) != len(set(winner_directions)):
            mismatches.append("selection_winner_direction_limit")

        internal_predictions = predictions.loc[
            predictions["research_stage"].astype(str) == "INTERNAL_VALIDATION"
        ].copy()
        internal_signals = signals.loc[
            signals["research_stage"].astype(str) == "INTERNAL_VALIDATION"
        ].copy()
        if set(internal_predictions["candidate_id"].astype(str)) != set(winner_ids):
            mismatches.append("internal_only_selection_winners")
        if independent_fixed_tail_keys(internal_predictions) != _keys(internal_signals):
            mismatches.append("internal_fixed_tail_keys")
        for candidate_id in winner_ids:
            rows = internal_signals.loc[
                internal_signals["candidate_id"].astype(str) == candidate_id
            ].copy()
            metrics = internal_metrics.get(candidate_id)
            if not isinstance(metrics, dict):
                mismatches.append(f"{candidate_id}:internal_metrics_missing")
                continue
            if int(metrics.get("raw_rows", -1)) != len(rows):
                mismatches.append(f"{candidate_id}:internal_rows")
            if not _float_matches(
                _session_net_mean(rows, cost_bps=PHASE27_PRIMARY_COST_BPS),
                metrics.get("primary_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:internal_primary")
            if not _float_matches(
                _session_net_mean(rows, cost_bps=PHASE27_STRESS_COST_BPS),
                metrics.get("stress_mean_return"),
            ):
                mismatches.append(f"{candidate_id}:internal_stress")

        finalist_ids = tuple(str(value) for value in report.get("finalist_ids", []))
        finalist_payload_ids = tuple(
            str(value) for value in finalists.get("finalist_ids", [])
        )
        if finalist_ids != finalist_payload_ids:
            mismatches.append("finalist_ids_report_artifact")
        if not set(finalist_ids).issubset(set(winner_ids)):
            mismatches.append("finalists_subset_winners")

        checks = {
            "research_contract": report.get("contract_version")
            == PHASE27_RESEARCH_REPORT_CONTRACT_VERSION,
            "research_pass": report.get("pass") is True,
            "research_policy": report.get("phase27_policy_fingerprint")
            == phase27_policy_fingerprint(),
            "prediction_sha": report.get("predictions_sha256")
            == sha256_file(predictions_path),
            "signal_sha": report.get("signals_sha256") == sha256_file(signals_path),
            "prediction_contract": set(
                predictions["prediction_contract_version"].astype(str)
            )
            == {PHASE27_PREDICTION_ARTIFACT_CONTRACT_VERSION},
            "signal_contract": set(signals["signal_contract_version"].astype(str))
            == {PHASE27_SIGNAL_ARTIFACT_CONTRACT_VERSION},
            "finalist_contract": finalists.get("contract_version")
            == PHASE27_FINALIST_ARTIFACT_CONTRACT_VERSION,
            "finalists_frozen": finalists.get("frozen") is True,
            "runner_up_disabled": finalists.get("runner_up_substitution_allowed") is False,
            "protected_unread": int(report.get("protected_return_reads", -1)) == 0
            and int(finalists.get("protected_returns_read", -1)) == 0
            and int(finalists.get("protected_candidate_rows_read", -1)) == 0,
            "reconciliation_clean": not mismatches,
        }
        return report, finalists, checks, mismatches

    def _blindness_checks(self, finalists: dict[str, object]) -> dict[str, bool]:
        report_path = self.blindness.report_path()
        report = _load_json(report_path, "Phase27 blindness audit")
        return {
            "blindness_contract": report.get("contract_version")
            == PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION,
            "blindness_pass": report.get("pass") is True,
            "blindness_policy": report.get("phase27_policy_fingerprint")
            == phase27_policy_fingerprint(),
            "blindness_eligible": report.get("eligible_for_phase27_protected_reuse")
            is True,
            "blindness_pre_read": report.get("protected_holdout_consumed") is False
            and int(report.get("protected_returns_read", -1)) == 0,
            "blindness_finalist_binding": report.get("phase27_finalists_sha256")
            == sha256_file(self.research.finalists_path()),
        }

    def _confirmation_checks(
        self, finalists: dict[str, object]
    ) -> tuple[dict[str, bool], list[str], tuple[str, ...]]:
        report = _load_json(self.confirmation.report_path(), "Phase27 confirmation report")
        support = _load_json(self.confirmation.support_overlay_path(), "Phase27 support overlay")
        mismatches: list[str] = []
        finalist_ids = tuple(str(value) for value in finalists.get("finalist_ids", []))
        confirmed_ids = tuple(
            str(value) for value in report.get("confirmed_candidate_ids", [])
        )

        if not finalist_ids:
            if report.get("status") != "SKIPPED_ZERO_FINALISTS":
                mismatches.append("zero_finalist_status")
            if int(report.get("protected_returns_read", -1)) != 0:
                mismatches.append("zero_finalist_return_reads")
            if int(report.get("protected_candidate_rows_read", -1)) != 0:
                mismatches.append("zero_finalist_candidate_reads")
            if report.get("protected_holdout_consumed") is not False:
                mismatches.append("zero_finalist_holdout_consumed")
        else:
            predictions_path = self.confirmation.protected_predictions_path()
            score_signals_path = self.confirmation.protected_score_signals_path()
            signals_path = self.confirmation.protected_signals_path()
            plan_path = self.confirmation.read_plan_path()
            predictions = _load_parquet(
                predictions_path,
                order_by="candidate_id, as_of_date, instrument_id",
            )
            score_signals = _load_parquet(
                score_signals_path,
                order_by="candidate_id, as_of_date, instrument_id",
            )
            signals = _load_parquet(
                signals_path,
                order_by="candidate_id, as_of_date, instrument_id",
            )
            plan = _load_json(plan_path, "Phase27 protected read plan")
            if set(predictions["prediction_contract_version"].astype(str)) != {
                PHASE27_PROTECTED_PREDICTION_CONTRACT_VERSION
            }:
                mismatches.append("protected_prediction_contract")
            if set(score_signals["score_signal_contract_version"].astype(str)) != {
                PHASE27_PROTECTED_SCORE_SIGNAL_CONTRACT_VERSION
            }:
                mismatches.append("protected_score_signal_contract")
            if independent_fixed_tail_keys(predictions) != _keys(score_signals):
                mismatches.append("protected_fixed_tail_keys")
            if not _keys(signals).issubset(_keys(score_signals)):
                mismatches.append("protected_outcome_keys_not_subset")
            if not signals.empty and set(signals["signal_contract_version"].astype(str)) != {
                PHASE27_PROTECTED_SIGNAL_CONTRACT_VERSION
            }:
                mismatches.append("protected_signal_contract")
            if plan.get("contract_version") != PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION:
                mismatches.append("protected_read_plan_contract")
            if plan.get("protected_score_signals_sha256") != sha256_file(score_signals_path):
                mismatches.append("protected_read_plan_signal_binding")
            if int(plan.get("outcome_query_rows_after_split_censor", -1)) != int(
                report.get("protected_candidate_rows_read", -2)
            ):
                mismatches.append("protected_candidate_read_count")
            if len(signals) != int(report.get("protected_returns_read", -1)):
                mismatches.append("protected_return_read_count")

            protected_metrics = report.get("protected_metrics")
            if not isinstance(protected_metrics, dict):
                mismatches.append("protected_metrics_malformed")
                protected_metrics = {}
            for candidate_id in finalist_ids:
                rows = signals.loc[
                    signals["candidate_id"].astype(str) == candidate_id
                ].copy()
                if not rows.empty:
                    computed_forward = (
                        pd.to_numeric(rows["future_close"], errors="coerce")
                        / pd.to_numeric(rows["daily_close"], errors="coerce")
                        - 1.0
                    )
                    direction = next(
                        candidate.direction
                        for candidate in PHASE27_CANDIDATES
                        if candidate.candidate_id == candidate_id
                    )
                    expected_directional = (
                        computed_forward if direction == "LONG" else -computed_forward
                    )
                    if not np.allclose(
                        expected_directional.to_numpy(dtype=float),
                        pd.to_numeric(rows["directional_return"], errors="coerce").to_numpy(dtype=float),
                        rtol=1e-12,
                        atol=1e-12,
                    ):
                        mismatches.append(f"{candidate_id}:protected_return_geometry")
                metrics = protected_metrics.get(candidate_id)
                if not isinstance(metrics, dict):
                    mismatches.append(f"{candidate_id}:protected_metrics_missing")
                    continue
                if int(metrics.get("raw_rows", -1)) != len(rows):
                    mismatches.append(f"{candidate_id}:protected_rows")
                if not _float_matches(
                    _session_net_mean(rows, cost_bps=PHASE27_PRIMARY_COST_BPS),
                    metrics.get("primary_mean_return"),
                ):
                    mismatches.append(f"{candidate_id}:protected_primary")
                if not _float_matches(
                    _session_net_mean(rows, cost_bps=PHASE27_STRESS_COST_BPS),
                    metrics.get("stress_mean_return"),
                ):
                    mismatches.append(f"{candidate_id}:protected_stress")

        support_ids = tuple(str(value) for value in support.get("supported_candidate_ids", []))
        if support_ids != confirmed_ids:
            mismatches.append("support_confirmed_ids")
        if not set(confirmed_ids).issubset(set(finalist_ids)):
            mismatches.append("confirmed_subset_finalists")

        checks = {
            "confirmation_contract": report.get("contract_version")
            == PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
            "confirmation_pass": report.get("pass") is True,
            "confirmation_policy": report.get("phase27_policy_fingerprint")
            == phase27_policy_fingerprint(),
            "support_contract": support.get("contract_version")
            == PHASE27_SUPPORT_OVERLAY_CONTRACT_VERSION,
            "support_policy": support.get("phase27_policy_fingerprint")
            == phase27_policy_fingerprint(),
            "support_authority_analytical_only": support.get("authority")
            == "HISTORICAL_ANALYTICAL_STRATEGY_SUPPORT_ONLY",
            "support_no_paper": support.get("paper_authority") is False,
            "support_no_live": support.get("live_authority") is False,
            "support_no_auto_failover": support.get("automatic_broker_failover") is False,
            "reconciliation_clean": not mismatches,
        }
        return checks, mismatches, confirmed_ids

    def run(self) -> dict[str, object]:
        _, _, population_checks = self._population_checks()
        research, finalists, research_checks, research_mismatches = self._research_checks()
        blindness_checks = self._blindness_checks(finalists)
        confirmation_checks, confirmation_mismatches, confirmed_ids = (
            self._confirmation_checks(finalists)
        )
        all_checks = {
            "population": population_checks,
            "research": research_checks,
            "blindness": blindness_checks,
            "confirmation": confirmation_checks,
        }
        external_fields = (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
        )
        confirmation = _load_json(
            self.confirmation.report_path(), "Phase27 confirmation report"
        )
        external_activity_zero = all(
            int(research.get(name, -1)) == 0 and int(confirmation.get(name, -1)) == 0
            for name in external_fields
        )
        pass_value = bool(
            external_activity_zero
            and all(all(group.values()) for group in all_checks.values())
        )
        if not pass_value:
            failed = [
                f"{group}.{name}"
                for group, checks in all_checks.items()
                for name, value in checks.items()
                if not value
            ]
            if not external_activity_zero:
                failed.append("external_activity_zero")
            raise Phase27IndependentValidationError(
                "Phase27 independent validation failed: " + ", ".join(failed)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE27_VALIDATION_CONTRACT_VERSION,
            "phase27_policy_fingerprint": phase27_policy_fingerprint(),
            "population_report_sha256": sha256_file(self.population.report_path()),
            "research_report_sha256": sha256_file(self.research.report_path()),
            "finalists_sha256": sha256_file(self.research.finalists_path()),
            "blindness_audit_sha256": sha256_file(self.blindness.report_path()),
            "confirmation_report_sha256": sha256_file(self.confirmation.report_path()),
            "support_overlay_sha256": sha256_file(self.confirmation.support_overlay_path()),
            "supported_candidate_ids": list(confirmed_ids),
            "research_mismatches": research_mismatches,
            "confirmation_mismatches": confirmation_mismatches,
            "checks": all_checks,
            "external_activity_zero": external_activity_zero,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
