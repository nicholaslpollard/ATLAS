from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Mapping

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

from .phase28_blindness import (
    PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION,
    Phase28ProtectedBlindnessAudit,
)
from .phase28_confirmation import (
    PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE28_PROTECTED_PREDICTION_CONTRACT_VERSION,
    PHASE28_PROTECTED_READ_PLAN_CONTRACT_VERSION,
    PHASE28_PROTECTED_SCORE_SIGNAL_CONTRACT_VERSION,
    PHASE28_PROTECTED_SIGNAL_CONTRACT_VERSION,
    PHASE28_SUPPORT_OVERLAY_CONTRACT_VERSION,
    Phase28ProtectedConfirmation,
)
from .phase28_policy import (
    PHASE28_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE28_BOOTSTRAP_REPLICATES,
    PHASE28_BOOTSTRAP_SEED,
    PHASE28_CANDIDATES,
    PHASE28_COMMON_RETURN_MIN_PEERS,
    PHASE28_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE28_INTERNAL_MIN_RAW_ROWS,
    PHASE28_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE28_LEAD_LAG_PAIRS,
    PHASE28_MAX_LEADERS,
    PHASE28_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE28_MIN_LEADERS,
    PHASE28_MIN_POSITIVE_REGIME_FRACTION,
    PHASE28_MIN_POSITIVE_YEAR_FRACTION,
    PHASE28_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE28_MIN_VALID_LAG_PAIRS,
    PHASE28_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE28_MULTIPLE_TESTING_ALPHA,
    PHASE28_PRIMARY_COST_BPS,
    PHASE28_PROTECTED_END,
    PHASE28_RAW_SIGNAL_FIELDS,
    PHASE28_RESIDUAL_MOMENTUM_SESSIONS,
    PHASE28_PEER_MOMENTUM_SESSIONS,
    PHASE28_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE28_SELECTION_MIN_RAW_ROWS,
    PHASE28_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE28_SIGNAL_TAIL_FRACTION,
    PHASE28_STRESS_COST_BPS,
    Phase28CandidateSpec,
    phase28_policy_fingerprint,
)
from .phase28_population import (
    PHASE28_DEVELOPMENT_FRAME_CONTRACT_VERSION,
    PHASE28_POPULATION_REPORT_CONTRACT_VERSION,
    PHASE28_PROTECTED_FRAME_CONTRACT_VERSION,
    PHASE28_REQUIRED_CLOSES,
    Phase28PopulationBuilder,
)
from .phase28_research import (
    PHASE28_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE28_PREDICTION_ARTIFACT_CONTRACT_VERSION,
    PHASE28_RESEARCH_REPORT_CONTRACT_VERSION,
    PHASE28_SIGNAL_ARTIFACT_CONTRACT_VERSION,
    Phase28DevelopmentResearch,
)


PHASE28_VALIDATION_CONTRACT_VERSION = (
    "phase28-validation-v1-independent-network-sample-tail-economics-protected-reconciliation"
)
PHASE28_INDEPENDENT_NETWORK_SAMPLE_PER_TRANCHE = 12


class Phase28IndependentValidationError(RuntimeError):
    pass


def _load_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase28IndependentValidationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase28IndependentValidationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase28IndependentValidationError(f"{label} must be an object")
    return payload


def _load_parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase28IndependentValidationError(f"missing parquet evidence: {path}")
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


def _candidate(candidate_id: str) -> Phase28CandidateSpec:
    try:
        return next(item for item in PHASE28_CANDIDATES if item.candidate_id == candidate_id)
    except StopIteration as exc:
        raise Phase28IndependentValidationError(f"unknown Phase28 candidate: {candidate_id}") from exc


def _hash_sample(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame.copy()
    work["_sample_hash"] = [
        hashlib.sha256(f"{session}|{instrument}".encode("utf-8")).hexdigest()
        for session, instrument in zip(work["as_of_date"], work["instrument_id"], strict=True)
    ]
    return work.sort_values(
        ["_sample_hash", "as_of_date", "instrument_id"], kind="stable"
    ).head(count).drop(columns=["_sample_hash"]).copy()


def _independent_residuals(raw_returns: pd.DataFrame) -> pd.DataFrame:
    values = raw_returns.apply(pd.to_numeric, errors="coerce").astype(float)
    finite_counts = np.isfinite(values.to_numpy(dtype=float)).sum(axis=1)
    medians = values.median(axis=1, skipna=True)
    medians.loc[finite_counts < PHASE28_COMMON_RETURN_MIN_PEERS] = np.nan
    result = values.sub(medians, axis=0)
    result.loc[finite_counts < PHASE28_COMMON_RETURN_MIN_PEERS, :] = np.nan
    return result


def _corr(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) < 2 or len(x) != len(y):
        return None
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        return None
    if np.std(x) <= 0 or np.std(y) <= 0:
        return None
    value = float(np.corrcoef(x, y)[0, 1])
    return value if np.isfinite(value) else None


def _independent_leaders(
    residuals: pd.DataFrame,
    *,
    focal_id: str,
    estimation_end: date,
) -> tuple[dict[str, float | int | str], ...]:
    edges: list[dict[str, float | int | str]] = []
    for peer_id in sorted(str(value) for value in residuals.columns if str(value) != focal_id):
        work = residuals.loc[
            pd.to_datetime(residuals.index).date <= estimation_end,
            [focal_id, peer_id],
        ].tail(PHASE28_LEAD_LAG_PAIRS + 1)
        if len(work) < PHASE28_MIN_VALID_LAG_PAIRS + 1:
            continue
        focal = pd.to_numeric(work[focal_id], errors="coerce").to_numpy(dtype=float)
        peer = pd.to_numeric(work[peer_id], errors="coerce").to_numpy(dtype=float)
        aligned = (
            np.isfinite(peer[:-1])
            & np.isfinite(focal[1:])
            & np.isfinite(focal[:-1])
            & np.isfinite(peer[1:])
        )
        valid_pairs = int(aligned.sum())
        if valid_pairs < PHASE28_MIN_VALID_LAG_PAIRS:
            continue
        forward = _corr(peer[:-1][aligned], focal[1:][aligned])
        reverse = _corr(focal[:-1][aligned], peer[1:][aligned])
        if forward is None or reverse is None:
            continue
        asymmetry = float(forward - reverse)
        if forward <= 0.0 or asymmetry <= 0.0:
            continue
        edges.append(
            {
                "peer_id": peer_id,
                "forward_corr": forward,
                "reverse_corr": reverse,
                "asymmetry": asymmetry,
                "valid_pairs": valid_pairs,
            }
        )
    edges.sort(key=lambda item: (-float(item["asymmetry"]), str(item["peer_id"])))
    chosen = edges[:PHASE28_MAX_LEADERS]
    if len(chosen) < PHASE28_MIN_LEADERS:
        return ()
    total = float(sum(float(item["asymmetry"]) for item in chosen))
    for item in chosen:
        item["weight"] = float(item["asymmetry"]) / total
    return tuple(chosen)


def _independent_signals(
    residuals: pd.DataFrame,
    *,
    focal_id: str,
    leaders: tuple[dict[str, float | int | str], ...],
    observation_date: date,
) -> dict[str, float] | None:
    if len(leaders) < PHASE28_MIN_LEADERS:
        return None
    focal = residuals.loc[
        pd.to_datetime(residuals.index).date <= observation_date,
        focal_id,
    ].tail(PHASE28_RESIDUAL_MOMENTUM_SESSIONS)
    if len(focal) != PHASE28_RESIDUAL_MOMENTUM_SESSIONS:
        return None
    focal_values = pd.to_numeric(focal, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(focal_values).all():
        return None
    peer_1d = 0.0
    peer_5d = 0.0
    for leader in leaders:
        peer_id = str(leader["peer_id"])
        values = residuals.loc[
            pd.to_datetime(residuals.index).date <= observation_date,
            peer_id,
        ].tail(PHASE28_PEER_MOMENTUM_SESSIONS)
        if len(values) != PHASE28_PEER_MOMENTUM_SESSIONS:
            return None
        array = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(array).all():
            return None
        weight = float(leader["weight"])
        peer_1d += weight * float(array[-1])
        peer_5d += weight * float(array.sum())
    return {
        "residual_momentum_20d": float(focal_values.sum()),
        "peer_lead_1d": float(peer_1d),
        "peer_lead_5d": float(peer_5d),
        "peer_diffusion_gap_1d": float(peer_1d - focal_values[-1]),
    }


def _split_dates(splits: pd.DataFrame) -> dict[str, tuple[date, ...]]:
    if splits.empty:
        return {}
    work = splits.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"]).dt.date
    return {
        str(ticker): tuple(sorted(set(group["execution_date"])))
        for ticker, group in work.groupby("ticker", sort=False, observed=True)
    }


def _history_start_map(calendar_sessions: tuple[date, ...], dates: set[date]) -> dict[date, date]:
    index = {session: position for position, session in enumerate(calendar_sessions)}
    result: dict[date, date] = {}
    for observation_date in dates:
        position = index.get(observation_date)
        if position is None or position < PHASE28_REQUIRED_CLOSES - 1:
            raise Phase28IndependentValidationError("sample observation lacks frozen history window")
        result[observation_date] = calendar_sessions[position - (PHASE28_REQUIRED_CLOSES - 1)]
    return result


def _network_sample_reconciliation(
    settings: AtlasSettings,
    population: Phase28PopulationBuilder,
    development_frame: pd.DataFrame,
    protected_frame: pd.DataFrame,
) -> tuple[list[str], int]:
    dev_sample = _hash_sample(development_frame, PHASE28_INDEPENDENT_NETWORK_SAMPLE_PER_TRANCHE)
    protected_sample = _hash_sample(protected_frame, PHASE28_INDEPENDENT_NETWORK_SAMPLE_PER_TRANCHE)
    samples = pd.concat(
        [dev_sample.assign(_source="development"), protected_sample.assign(_source="protected")],
        ignore_index=True,
        sort=False,
    )
    if samples.empty:
        return ["network_sample_empty"], 0
    sample_dates = set(samples["as_of_date"])

    phase26_dev = _load_parquet(population.phase26.development_path(), order_by="as_of_date, instrument_id")
    phase26_protected = _load_parquet(
        population.phase26.protected_predictors_path(), order_by="as_of_date, instrument_id"
    )
    source = pd.concat(
        [
            phase26_dev.loc[phase26_dev["as_of_date"].isin(sample_dates)].copy(),
            phase26_protected.loc[phase26_protected["as_of_date"].isin(sample_dates)].copy(),
        ],
        ignore_index=True,
        sort=False,
    )
    for field in ("safe_start_date", "safe_end_date"):
        source[field] = pd.to_datetime(source[field]).dt.date

    calendar = get_market_calendar(settings.data.calendar.exchange)
    sessions = tuple(
        calendar.sessions_in_range(date(2021, 1, 4), date.fromisoformat(PHASE28_PROTECTED_END))
    )
    starts = _history_start_map(sessions, sample_dates)
    prior = {sessions[index]: sessions[index - 1] for index in range(1, len(sessions))}
    splits, _, _ = population.phase26._split_evidence()
    split_map = _split_dates(splits)

    plan: list[dict[str, object]] = []
    for observation_date, group in source.groupby("as_of_date", sort=True, observed=True):
        history_start = starts[observation_date]
        for row in group.itertuples(index=False):
            if row.safe_start_date > history_start or row.safe_end_date < observation_date:
                continue
            ticker = str(row.ticker)
            if any(
                history_start < split_date <= observation_date
                for split_date in split_map.get(ticker, ())
            ):
                continue
            plan.append(
                {
                    "observation_date": observation_date,
                    "history_start": history_start,
                    "peer_instrument_id": str(row.instrument_id),
                    "ticker": ticker,
                }
            )
    peer_plan = pd.DataFrame(plan)
    if peer_plan.empty:
        return ["network_sample_peer_plan_empty"], 0

    con = connect_utc(":memory:")
    try:
        con.register("p28_validation_peer_plan", peer_plan)
        bars = MarketDataPaths(settings).glob_for_timeframe(Timeframe.DAY_1)
        history = con.execute(
            f"""
            SELECT
                CAST(p.observation_date AS DATE) AS observation_date,
                p.peer_instrument_id,
                CAST(b.session_date AS DATE) AS history_date,
                CAST(b.close AS DOUBLE) AS close
            FROM p28_validation_peer_plan p
            INNER JOIN read_parquet(
                {sql_string(bars)}, union_by_name=true, hive_partitioning=false
            ) b
              ON b.symbol = p.ticker
             AND CAST(b.session_date AS DATE) BETWEEN CAST(p.history_start AS DATE)
                                                   AND CAST(p.observation_date AS DATE)
            WHERE b.close IS NOT NULL
              AND isfinite(CAST(b.close AS DOUBLE))
              AND CAST(b.close AS DOUBLE) > 0
            ORDER BY p.observation_date, p.peer_instrument_id, b.session_date
            """
        ).fetch_df()
    finally:
        con.close()
    history["observation_date"] = pd.to_datetime(history["observation_date"]).dt.date
    history["history_date"] = pd.to_datetime(history["history_date"]).dt.date
    by_date = {
        session: group.copy()
        for session, group in history.groupby("observation_date", sort=True, observed=True)
    }

    mismatches: list[str] = []
    checked = 0
    for row in samples.itertuples(index=False):
        history_group = by_date.get(row.as_of_date)
        if history_group is None or history_group.empty:
            mismatches.append(f"{row.as_of_date}:{row.instrument_id}:missing_history")
            continue
        matrix = history_group.pivot(
            index="history_date", columns="peer_instrument_id", values="close"
        ).sort_index()
        returns = matrix.pct_change(fill_method=None).iloc[1:]
        residuals = _independent_residuals(returns)
        focal_id = str(row.instrument_id)
        if focal_id not in residuals.columns:
            mismatches.append(f"{row.as_of_date}:{focal_id}:missing_focal")
            continue
        leaders = _independent_leaders(
            residuals,
            focal_id=focal_id,
            estimation_end=prior[row.as_of_date],
        )
        stored_leaders = json.loads(str(row.phase28_leaders_json))
        if [str(item["peer_id"]) for item in leaders] != [
            str(item["peer_id"]) for item in stored_leaders
        ]:
            mismatches.append(f"{row.as_of_date}:{focal_id}:leader_ids")
            continue
        for actual, stored in zip(leaders, stored_leaders, strict=True):
            for field in ("forward_corr", "reverse_corr", "asymmetry", "weight"):
                if not math.isclose(
                    float(actual[field]), float(stored[field]), rel_tol=1e-11, abs_tol=1e-11
                ):
                    mismatches.append(f"{row.as_of_date}:{focal_id}:{field}")
                    break
            if int(actual["valid_pairs"]) != int(stored["valid_pairs"]):
                mismatches.append(f"{row.as_of_date}:{focal_id}:valid_pairs")
        signals = _independent_signals(
            residuals,
            focal_id=focal_id,
            leaders=leaders,
            observation_date=row.as_of_date,
        )
        if signals is None:
            mismatches.append(f"{row.as_of_date}:{focal_id}:missing_signals")
            continue
        for field in PHASE28_RAW_SIGNAL_FIELDS:
            if not math.isclose(
                float(signals[field]), float(getattr(row, field)), rel_tol=1e-11, abs_tol=1e-11
            ):
                mismatches.append(f"{row.as_of_date}:{focal_id}:{field}")
        checked += 1
    return sorted(set(mismatches)), checked


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
    result: set[tuple[str, date, str]] = set()
    work = predictions.copy()
    work["as_of_date"] = pd.to_datetime(work["as_of_date"]).dt.date
    for (candidate_id, session), group in work.groupby(
        ["candidate_id", "as_of_date"], sort=True, observed=True
    ):
        ordered = group.sort_values(
            ["phase28_score", "instrument_id"], ascending=[False, True], kind="stable"
        )
        count = max(1, int(math.ceil(PHASE28_SIGNAL_TAIL_FRACTION * len(ordered))))
        for instrument_id in ordered.iloc[:count]["instrument_id"].astype(str):
            result.add((str(candidate_id), session, instrument_id))
    return result


def independent_holm(
    p_values: Mapping[str, float], *, alpha: float = PHASE28_MULTIPLE_TESTING_ALPHA
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


def _session_net_mean(frame: pd.DataFrame, cost_bps: float) -> float | None:
    if frame.empty:
        return None
    grouped = frame.groupby("as_of_date", sort=True, observed=True)["directional_return"].mean()
    if grouped.empty:
        return None
    return float(grouped.mean() - cost_bps / 10_000.0)


def _float_match(a: float | None, b: object) -> bool:
    if a is None:
        return b is None
    if b is None:
        return False
    return math.isclose(a, float(b), rel_tol=1e-11, abs_tol=1e-11)


class Phase28IndependentValidator:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.population = Phase28PopulationBuilder(settings)
        self.research = Phase28DevelopmentResearch(settings)
        self.blindness = Phase28ProtectedBlindnessAudit(settings)
        self.confirmation = Phase28ProtectedConfirmation(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase28" / "v1" / "validation"

    def report_path(self) -> Path:
        return self.root / "independent_validation.json"

    def run(self) -> dict[str, object]:
        population_report = _load_json(self.population.report_path(), "Phase28 population report")
        research_report = _load_json(self.research.report_path(), "Phase28 research report")
        finalists = _load_json(self.research.finalists_path(), "Phase28 finalists")
        blindness = _load_json(self.blindness.report_path(), "Phase28 blindness audit")
        confirmation = _load_json(self.confirmation.report_path(), "Phase28 confirmation")
        support = _load_json(self.confirmation.support_overlay_path(), "Phase28 support overlay")

        development = _load_parquet(
            self.population.development_path(), order_by="as_of_date, instrument_id"
        )
        protected = _load_parquet(
            self.population.protected_path(), order_by="as_of_date, instrument_id"
        )
        if set(development["phase28_contract_version"].astype(str)) != {
            PHASE28_DEVELOPMENT_FRAME_CONTRACT_VERSION
        }:
            raise Phase28IndependentValidationError("Phase28 development row contract mismatch")
        if set(protected["phase28_contract_version"].astype(str)) != {
            PHASE28_PROTECTED_FRAME_CONTRACT_VERSION
        }:
            raise Phase28IndependentValidationError("Phase28 protected row contract mismatch")
        network_mismatches, network_sample_rows = _network_sample_reconciliation(
            self.settings, self.population, development, protected
        )

        predictions = _load_parquet(
            self.research.predictions_path(),
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )
        signals = _load_parquet(
            self.research.signals_path(),
            order_by="research_stage, candidate_id, as_of_date, instrument_id",
        )
        research_mismatches: list[str] = []
        if set(predictions["prediction_contract_version"].astype(str)) != {
            PHASE28_PREDICTION_ARTIFACT_CONTRACT_VERSION
        }:
            research_mismatches.append("prediction_contract")
        if set(signals["signal_contract_version"].astype(str)) != {
            PHASE28_SIGNAL_ARTIFACT_CONTRACT_VERSION
        }:
            research_mismatches.append("signal_contract")

        selection_predictions = predictions.loc[
            predictions["research_stage"].astype(str) == "SELECTION"
        ].copy()
        selection_signals = signals.loc[
            signals["research_stage"].astype(str) == "SELECTION"
        ].copy()
        if independent_fixed_tail_keys(selection_predictions) != _keys(selection_signals):
            research_mismatches.append("selection_fixed_tail_keys")

        selection_metrics = research_report.get("selection_metrics")
        selection_checks = research_report.get("selection_checks")
        holm_report = research_report.get("holm_bonferroni")
        if not isinstance(selection_metrics, dict) or not isinstance(selection_checks, dict) or not isinstance(holm_report, dict):
            raise Phase28IndependentValidationError("Phase28 selection evidence is malformed")
        p_values: dict[str, float] = {}
        independently_passing: set[str] = set()
        for candidate in PHASE28_CANDIDATES:
            candidate_id = candidate.candidate_id
            pred = selection_predictions.loc[
                selection_predictions["candidate_id"].astype(str) == candidate_id
            ].copy()
            sig = selection_signals.loc[
                selection_signals["candidate_id"].astype(str) == candidate_id
            ].copy()
            expected_direction = "bullish" if candidate.direction == "LONG" else "bearish"
            if set(pred["direction"].astype(str)) - {expected_direction}:
                research_mismatches.append(f"{candidate_id}:direction")
            raw = pd.to_numeric(pred[candidate.family], errors="coerce").to_numpy(dtype=float)
            expected_score = raw if candidate.direction == "LONG" else -raw
            if not np.allclose(
                expected_score,
                pd.to_numeric(pred["phase28_score"], errors="coerce").to_numpy(dtype=float),
                rtol=1e-12,
                atol=1e-12,
            ):
                research_mismatches.append(f"{candidate_id}:score")
            reported = selection_metrics.get(candidate_id)
            checks = selection_checks.get(candidate_id)
            if not isinstance(reported, dict) or not isinstance(checks, dict):
                research_mismatches.append(f"{candidate_id}:missing_metrics")
                continue
            primary = _session_net_mean(sig, PHASE28_PRIMARY_COST_BPS)
            stress = _session_net_mean(sig, PHASE28_STRESS_COST_BPS)
            if int(reported.get("raw_rows", -1)) != len(sig):
                research_mismatches.append(f"{candidate_id}:selection_rows")
            if int(reported.get("signal_sessions", -1)) != sig["as_of_date"].nunique():
                research_mismatches.append(f"{candidate_id}:selection_sessions")
            if not _float_match(primary, reported.get("primary_mean_return")):
                research_mismatches.append(f"{candidate_id}:selection_primary")
            if not _float_match(stress, reported.get("stress_mean_return")):
                research_mismatches.append(f"{candidate_id}:selection_stress")
            p_value = reported.get("primary_bootstrap_p_value")
            p_values[candidate_id] = 1.0 if p_value is None else float(p_value)
            if all(bool(value) for value in checks.values()):
                independently_passing.add(candidate_id)

        independent_holm_map = independent_holm(p_values)
        for candidate_id, reject in independent_holm_map.items():
            item = holm_report.get(candidate_id)
            if not isinstance(item, dict) or bool(item.get("rejected_null")) != reject:
                research_mismatches.append(f"{candidate_id}:holm")
        independent_survivors = {
            candidate_id
            for candidate_id in independently_passing
            if independent_holm_map.get(candidate_id, False)
        }
        reported_survivors = set(
            str(value) for value in research_report.get("selection_survivor_ids", [])
        )
        if independent_survivors != reported_survivors:
            research_mismatches.append("selection_survivors")

        independent_winners: list[str] = []
        for direction in ("LONG", "SHORT"):
            eligible = [
                _candidate(candidate_id)
                for candidate_id in independent_survivors
                if _candidate(candidate_id).direction == direction
            ]
            eligible.sort(
                key=lambda item: (
                    -float(selection_metrics[item.candidate_id].get("primary_lcb") or -math.inf),
                    -float(selection_metrics[item.candidate_id].get("primary_mean_return") or -math.inf),
                    item.candidate_id,
                )
            )
            if eligible:
                independent_winners.append(eligible[0].candidate_id)
        reported_winners = [str(value) for value in research_report.get("selection_winner_ids", [])]
        if independent_winners != reported_winners:
            research_mismatches.append("selection_winners")

        internal_predictions = predictions.loc[
            predictions["research_stage"].astype(str) == "INTERNAL_VALIDATION"
        ].copy()
        internal_signals = signals.loc[
            signals["research_stage"].astype(str) == "INTERNAL_VALIDATION"
        ].copy()
        if independent_fixed_tail_keys(internal_predictions) != _keys(internal_signals):
            research_mismatches.append("internal_fixed_tail_keys")
        if set(internal_predictions["candidate_id"].astype(str)) != set(reported_winners):
            research_mismatches.append("internal_winner_population")

        internal_checks_report = research_report.get("internal_checks")
        if not isinstance(internal_checks_report, dict):
            raise Phase28IndependentValidationError("Phase28 internal checks malformed")
        independent_finalists = {
            candidate_id
            for candidate_id in reported_winners
            if isinstance(internal_checks_report.get(candidate_id), dict)
            and all(bool(value) for value in internal_checks_report[candidate_id].values())
        }
        reported_finalists = set(str(value) for value in research_report.get("finalist_ids", []))
        if independent_finalists != reported_finalists:
            research_mismatches.append("finalists")
        if set(str(value) for value in finalists.get("finalist_ids", [])) != reported_finalists:
            research_mismatches.append("finalist_artifact_ids")

        confirmation_mismatches: list[str] = []
        confirmed_ids = tuple(str(value) for value in confirmation.get("confirmed_candidate_ids", []))
        if not reported_finalists:
            if confirmation.get("status") != "SKIPPED_ZERO_FINALISTS":
                confirmation_mismatches.append("zero_finalist_status")
            if int(confirmation.get("protected_candidate_rows_read", -1)) != 0:
                confirmation_mismatches.append("zero_finalist_candidate_reads")
            if int(confirmation.get("protected_returns_read", -1)) != 0:
                confirmation_mismatches.append("zero_finalist_return_reads")
            if confirmation.get("protected_holdout_consumed") is not False:
                confirmation_mismatches.append("zero_finalist_consumed")
            if self.confirmation.read_plan_path().exists():
                confirmation_mismatches.append("zero_finalist_read_plan_exists")
        else:
            protected_predictions = _load_parquet(
                self.confirmation.protected_predictions_path(),
                order_by="candidate_id, as_of_date, instrument_id",
            )
            protected_score_signals = _load_parquet(
                self.confirmation.protected_score_signals_path(),
                order_by="candidate_id, as_of_date, instrument_id",
            )
            protected_signals = _load_parquet(
                self.confirmation.protected_signals_path(),
                order_by="candidate_id, as_of_date, instrument_id",
            )
            read_plan = _load_json(self.confirmation.read_plan_path(), "Phase28 read plan")
            if set(protected_predictions["prediction_contract_version"].astype(str)) != {
                PHASE28_PROTECTED_PREDICTION_CONTRACT_VERSION
            }:
                confirmation_mismatches.append("protected_prediction_contract")
            if set(protected_score_signals["score_signal_contract_version"].astype(str)) != {
                PHASE28_PROTECTED_SCORE_SIGNAL_CONTRACT_VERSION
            }:
                confirmation_mismatches.append("protected_score_signal_contract")
            if independent_fixed_tail_keys(protected_predictions) != _keys(protected_score_signals):
                confirmation_mismatches.append("protected_fixed_tail_keys")
            if read_plan.get("contract_version") != PHASE28_PROTECTED_READ_PLAN_CONTRACT_VERSION:
                confirmation_mismatches.append("protected_read_plan_contract")
            if not _keys(protected_signals).issubset(_keys(protected_score_signals)):
                confirmation_mismatches.append("protected_outcome_key_subset")
            if not protected_signals.empty and set(
                protected_signals["signal_contract_version"].astype(str)
            ) != {PHASE28_PROTECTED_SIGNAL_CONTRACT_VERSION}:
                confirmation_mismatches.append("protected_signal_contract")
            if len(protected_signals) != int(confirmation.get("protected_returns_read", -1)):
                confirmation_mismatches.append("protected_return_count")
            if int(read_plan.get("outcome_query_rows_after_split_censor", -1)) != int(
                confirmation.get("protected_candidate_rows_read", -2)
            ):
                confirmation_mismatches.append("protected_candidate_count")
            if not protected_signals.empty:
                forward = (
                    pd.to_numeric(protected_signals["future_close"], errors="coerce")
                    / pd.to_numeric(protected_signals["daily_close"], errors="coerce")
                    - 1.0
                )
                expected = np.where(
                    protected_signals["strategy_direction"].astype(str) == "LONG",
                    forward,
                    -forward,
                )
                if not np.allclose(
                    expected,
                    pd.to_numeric(
                        protected_signals["directional_return"], errors="coerce"
                    ).to_numpy(dtype=float),
                    rtol=1e-12,
                    atol=1e-12,
                ):
                    confirmation_mismatches.append("protected_return_geometry")

        support_ids = tuple(str(value) for value in support.get("supported_candidate_ids", []))
        if support_ids != confirmed_ids:
            confirmation_mismatches.append("support_ids")
        if not set(confirmed_ids).issubset(reported_finalists):
            confirmation_mismatches.append("confirmed_subset_finalists")

        contracts_ok = bool(
            population_report.get("contract_version") == PHASE28_POPULATION_REPORT_CONTRACT_VERSION
            and research_report.get("contract_version") == PHASE28_RESEARCH_REPORT_CONTRACT_VERSION
            and finalists.get("contract_version") == PHASE28_FINALIST_ARTIFACT_CONTRACT_VERSION
            and blindness.get("contract_version") == PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION
            and confirmation.get("contract_version") == PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION
            and support.get("contract_version") == PHASE28_SUPPORT_OVERLAY_CONTRACT_VERSION
        )
        policy_ok = all(
            payload.get("phase28_policy_fingerprint") == phase28_policy_fingerprint()
            for payload in (
                population_report,
                research_report,
                finalists,
                blindness,
                confirmation,
                support,
            )
        )
        external_fields = (
            "provider_reads",
            "provider_writes",
            "broker_reads",
            "broker_writes",
            "order_writes",
            "paper_submits",
            "live_writes",
        )
        external_zero = all(
            int(payload.get(field, -1)) == 0
            for payload in (population_report, research_report, blindness, confirmation)
            for field in external_fields
        )
        pass_value = bool(
            contracts_ok
            and policy_ok
            and population_report.get("pass") is True
            and research_report.get("pass") is True
            and blindness.get("pass") is True
            and confirmation.get("pass") is True
            and not network_mismatches
            and network_sample_rows > 0
            and not research_mismatches
            and not confirmation_mismatches
            and external_zero
        )
        if not pass_value:
            failures = []
            if not contracts_ok:
                failures.append("contracts")
            if not policy_ok:
                failures.append("policy")
            failures.extend(f"network:{item}" for item in network_mismatches)
            failures.extend(f"research:{item}" for item in research_mismatches)
            failures.extend(f"confirmation:{item}" for item in confirmation_mismatches)
            if not external_zero:
                failures.append("external_activity")
            raise Phase28IndependentValidationError(
                "Phase28 independent validation failed: " + ", ".join(failures)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE28_VALIDATION_CONTRACT_VERSION,
            "phase28_policy_fingerprint": phase28_policy_fingerprint(),
            "population_report_sha256": sha256_file(self.population.report_path()),
            "development_population_sha256": sha256_file(self.population.development_path()),
            "protected_population_sha256": sha256_file(self.population.protected_path()),
            "research_report_sha256": sha256_file(self.research.report_path()),
            "finalists_sha256": sha256_file(self.research.finalists_path()),
            "blindness_audit_sha256": sha256_file(self.blindness.report_path()),
            "confirmation_report_sha256": sha256_file(self.confirmation.report_path()),
            "support_overlay_sha256": sha256_file(self.confirmation.support_overlay_path()),
            "independent_network_sample_rows": network_sample_rows,
            "network_mismatches": network_mismatches,
            "research_mismatches": research_mismatches,
            "confirmation_mismatches": confirmation_mismatches,
            "supported_candidate_ids": list(confirmed_ids),
            "external_activity_zero": external_zero,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
