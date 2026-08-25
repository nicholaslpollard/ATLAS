from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START
from packages.schemas.strategy import StrategyDirection
from packages.strategies.metadata import StrategyMetadata
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY, StrategyRegistry
from packages.strategies.rules import Comparison, FeatureCondition, RuleStrategy

from .historical_source import HistoricalStrategyResearchSourceResolver
from .phase24_gate1_policy import (
    PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS,
    PHASE24_GATE1_BOOTSTRAP_REPLICATES,
    PHASE24_GATE1_BOOTSTRAP_SEED,
    PHASE24_GATE1_CHALLENGER_VARIANTS,
    PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION,
    PHASE24_GATE1_INTERNAL_MIN_POSITIVE_FOLDS,
    PHASE24_GATE1_INTERNAL_MIN_RAW_ROWS,
    PHASE24_GATE1_INTERNAL_MIN_SIGNAL_SESSIONS,
    PHASE24_GATE1_INTERNAL_VALIDATION_CONFIDENCE,
    PHASE24_GATE1_INTERNAL_VALIDATION_FOLDS,
    PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION,
    PHASE24_GATE1_MAX_SINGLE_SESSION_ROW_FRACTION,
    PHASE24_GATE1_MIN_POSITIVE_REGIME_FRACTION,
    PHASE24_GATE1_MIN_POSITIVE_YEAR_FRACTION,
    PHASE24_GATE1_MIN_REGIME_SIGNAL_SESSIONS,
    PHASE24_GATE1_MIN_YEAR_SIGNAL_SESSIONS,
    PHASE24_GATE1_MULTIPLE_TESTING_ALPHA,
    PHASE24_GATE1_MULTIPLE_TESTING_METHOD,
    PHASE24_GATE1_PRIMARY_COST_BPS,
    PHASE24_GATE1_PROTECTED_EVIDENCE_READS,
    PHASE24_GATE1_PURGE_SESSIONS,
    PHASE24_GATE1_SELECTION_CONFIDENCE,
    PHASE24_GATE1_SELECTION_FOLDS,
    PHASE24_GATE1_SELECTION_FRACTION,
    PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS,
    PHASE24_GATE1_SELECTION_MIN_RAW_ROWS,
    PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE24_GATE1_STRESS_COST_BPS,
    ChallengerVariantSpec,
    phase24_gate1_policy_fingerprint,
)
from .strategy_evaluation import historical_market_route_sql, strategy_condition_sql


PHASE24_GATE2_CONTRACT_VERSION = (
    "phase24-gate2-v1-development-selection-internal-validation-no-protected"
)
PHASE24_PROTECTED_START_DATE = date.fromisoformat(ML_WALK_FORWARD_FINAL_HOLDOUT_START)


class Phase24Gate2Error(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _derived_seed(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return PHASE24_GATE1_BOOTSTRAP_SEED + int(digest[:8], 16)


@dataclass(frozen=True, slots=True)
class DevelopmentBoundaries:
    selection_start: date
    selection_end: date
    purged_sessions: tuple[date, ...]
    internal_start: date
    internal_end: date
    development_session_count: int
    selection_session_count: int
    internal_session_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "selection_start": self.selection_start.isoformat(),
            "selection_end": self.selection_end.isoformat(),
            "purged_sessions": [item.isoformat() for item in self.purged_sessions],
            "internal_start": self.internal_start.isoformat(),
            "internal_end": self.internal_end.isoformat(),
            "development_session_count": self.development_session_count,
            "selection_session_count": self.selection_session_count,
            "internal_session_count": self.internal_session_count,
        }


@dataclass(frozen=True, slots=True)
class SessionSignal:
    session_date: date
    regime: str
    raw_rows: int
    gross_mean_return: float


@dataclass(frozen=True, slots=True)
class TrancheMetrics:
    raw_rows: int
    signal_sessions: int
    primary_mean_return: float | None
    primary_median_return: float | None
    primary_positive_rate: float | None
    primary_lcb: float | None
    primary_bootstrap_p_value: float | None
    stress_mean_return: float | None
    max_single_session_row_fraction: float | None
    fold_means: tuple[float, ...]
    positive_folds: int
    eligible_year_means: dict[str, float]
    positive_year_fraction: float | None
    eligible_regime_means: dict[str, float]
    positive_regime_fraction: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _comparison(value: str) -> Comparison:
    try:
        return Comparison[value]
    except KeyError as exc:
        raise Phase24Gate2Error(f"unknown preregistered comparison: {value}") from exc


def build_challenger_strategy(spec: ChallengerVariantSpec) -> RuleStrategy:
    base = DEFAULT_STRATEGY_REGISTRY.get(spec.base_strategy_id)
    if not isinstance(base, RuleStrategy):
        raise Phase24Gate2Error(f"challenger base is not a RuleStrategy: {spec.base_strategy_id}")
    if base.metadata.family.value != spec.family or base.metadata.direction.value != spec.direction:
        raise Phase24Gate2Error(f"challenger metadata mismatch: {spec.variant_id}")
    conditions = list(base.conditions)
    for mutation in spec.mutations:
        if mutation.kind == "replace_right_value":
            matches = [i for i, item in enumerate(conditions) if item.reason_code == mutation.reason_code]
            if len(matches) != 1 or mutation.right_value is None:
                raise Phase24Gate2Error(
                    f"replacement is not uniquely resolvable: {spec.variant_id}:{mutation.reason_code}"
                )
            current = conditions[matches[0]]
            if current.right_value is None:
                raise Phase24Gate2Error("replacement target is not a constant-valued condition")
            conditions[matches[0]] = FeatureCondition(
                left=current.left,
                comparison=current.comparison,
                right_value=float(mutation.right_value),
                reason_code=current.reason_code,
            )
        elif mutation.kind == "add_condition":
            if mutation.left is None or mutation.comparison is None or mutation.right_value is None:
                raise Phase24Gate2Error("add-condition mutation is incomplete")
            conditions.append(
                FeatureCondition(
                    left=mutation.left,
                    comparison=_comparison(mutation.comparison),
                    right_value=float(mutation.right_value),
                    reason_code=mutation.reason_code,
                )
            )
        else:
            raise Phase24Gate2Error(f"unsupported mutation kind: {mutation.kind}")
    required = tuple(sorted({name for condition in conditions for name in condition.required_features}))
    return RuleStrategy(
        StrategyMetadata(
            strategy_id=spec.variant_id,
            family=base.metadata.family,
            direction=base.metadata.direction,
            required_features=required,
            description=f"Phase24 preregistered challenger derived from {spec.base_strategy_id}.",
        ),
        tuple(conditions),
    )


def build_challenger_registry() -> StrategyRegistry:
    return StrategyRegistry(tuple(build_challenger_strategy(spec) for spec in PHASE24_GATE1_CHALLENGER_VARIANTS))


def chronological_boundaries(sessions: Iterable[date]) -> DevelopmentBoundaries:
    ordered = tuple(sorted(set(sessions)))
    if len(ordered) < 20:
        raise Phase24Gate2Error("too few development sessions")
    selection_count = int(math.floor(len(ordered) * PHASE24_GATE1_SELECTION_FRACTION))
    internal_offset = selection_count + PHASE24_GATE1_PURGE_SESSIONS
    if selection_count <= 0 or internal_offset >= len(ordered):
        raise Phase24Gate2Error("invalid development split")
    selection = ordered[:selection_count]
    purge = ordered[selection_count:internal_offset]
    internal = ordered[internal_offset:]
    if len(purge) != PHASE24_GATE1_PURGE_SESSIONS or not internal:
        raise Phase24Gate2Error("purged/internal partition is incomplete")
    return DevelopmentBoundaries(
        selection_start=selection[0],
        selection_end=selection[-1],
        purged_sessions=tuple(purge),
        internal_start=internal[0],
        internal_end=internal[-1],
        development_session_count=len(ordered),
        selection_session_count=len(selection),
        internal_session_count=len(internal),
    )


def _bootstrap(values: np.ndarray, *, confidence: float, label: str) -> tuple[float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise Phase24Gate2Error("bootstrap requires a nonempty vector")
    n = len(values)
    block = min(PHASE24_GATE1_BOOTSTRAP_BLOCK_SESSIONS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(label))
    starts = rng.integers(0, n, size=(PHASE24_GATE1_BOOTSTRAP_REPLICATES, block_count))
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(PHASE24_GATE1_BOOTSTRAP_REPLICATES, -1)[:, :n]
    sample_means = values[indices].mean(axis=1)
    lower = float(np.quantile(sample_means, 1.0 - confidence))
    observed = float(values.mean())
    null_means = (values - observed)[indices].mean(axis=1)
    p_value = float((1 + np.count_nonzero(null_means >= observed)) / (len(null_means) + 1))
    return lower, p_value


def _fold_means(values: np.ndarray, folds: int) -> tuple[float, ...]:
    if len(values) < folds:
        return ()
    return tuple(float(part.mean()) for part in np.array_split(values, folds) if len(part))


def tranche_metrics(
    signals: tuple[SessionSignal, ...],
    *,
    confidence: float,
    folds: int,
    label: str,
) -> TrancheMetrics:
    if not signals:
        return TrancheMetrics(0, 0, None, None, None, None, None, None, None, (), 0, {}, None, {}, None)
    raw_rows = sum(item.raw_rows for item in signals)
    gross = np.asarray([item.gross_mean_return for item in signals], dtype=np.float64)
    primary = gross - PHASE24_GATE1_PRIMARY_COST_BPS / 10_000.0
    stress = gross - PHASE24_GATE1_STRESS_COST_BPS / 10_000.0
    lower, p_value = _bootstrap(primary, confidence=confidence, label=label)
    folds_out = _fold_means(primary, folds)
    years: dict[int, list[float]] = defaultdict(list)
    regimes: dict[str, list[float]] = defaultdict(list)
    for signal, value in zip(signals, primary, strict=True):
        years[signal.session_date.year].append(float(value))
        regimes[signal.regime].append(float(value))
    year_means = {
        str(key): float(np.mean(values))
        for key, values in sorted(years.items())
        if len(values) >= PHASE24_GATE1_MIN_YEAR_SIGNAL_SESSIONS
    }
    regime_means = {
        key: float(np.mean(values))
        for key, values in sorted(regimes.items())
        if len(values) >= PHASE24_GATE1_MIN_REGIME_SIGNAL_SESSIONS
    }
    year_fraction = None if not year_means else sum(v > 0 for v in year_means.values()) / len(year_means)
    regime_fraction = None if not regime_means else sum(v > 0 for v in regime_means.values()) / len(regime_means)
    return TrancheMetrics(
        raw_rows=raw_rows,
        signal_sessions=len(signals),
        primary_mean_return=float(primary.mean()),
        primary_median_return=float(np.median(primary)),
        primary_positive_rate=float(np.mean(primary > 0)),
        primary_lcb=lower,
        primary_bootstrap_p_value=p_value,
        stress_mean_return=float(stress.mean()),
        max_single_session_row_fraction=float(max(item.raw_rows for item in signals) / raw_rows),
        fold_means=folds_out,
        positive_folds=sum(v > 0 for v in folds_out),
        eligible_year_means=year_means,
        positive_year_fraction=None if year_fraction is None else float(year_fraction),
        eligible_regime_means=regime_means,
        positive_regime_fraction=None if regime_fraction is None else float(regime_fraction),
    )


def selection_checks(metrics: TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE24_GATE1_SELECTION_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE24_GATE1_SELECTION_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE24_GATE1_SELECTION_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(metrics.primary_mean_return is not None and metrics.primary_mean_return > 0),
        "primary_median_positive": bool(metrics.primary_median_return is not None and metrics.primary_median_return > 0),
        "positive_rate_half": bool(metrics.primary_positive_rate is not None and metrics.primary_positive_rate >= 0.5),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(metrics.stress_mean_return is not None and metrics.stress_mean_return > 0),
        "year_robustness": bool(metrics.positive_year_fraction is not None and metrics.positive_year_fraction >= PHASE24_GATE1_MIN_POSITIVE_YEAR_FRACTION),
        "regime_robustness": bool(metrics.positive_regime_fraction is not None and metrics.positive_regime_fraction >= PHASE24_GATE1_MIN_POSITIVE_REGIME_FRACTION),
        "session_concentration": bool(metrics.max_single_session_row_fraction is not None and metrics.max_single_session_row_fraction <= PHASE24_GATE1_MAX_SINGLE_SESSION_ROW_FRACTION),
    }


def internal_checks(metrics: TrancheMetrics) -> dict[str, bool]:
    return {
        "min_raw_rows": metrics.raw_rows >= PHASE24_GATE1_INTERNAL_MIN_RAW_ROWS,
        "min_signal_sessions": metrics.signal_sessions >= PHASE24_GATE1_INTERNAL_MIN_SIGNAL_SESSIONS,
        "positive_folds": metrics.positive_folds >= PHASE24_GATE1_INTERNAL_MIN_POSITIVE_FOLDS,
        "primary_mean_positive": bool(metrics.primary_mean_return is not None and metrics.primary_mean_return > 0),
        "primary_median_positive": bool(metrics.primary_median_return is not None and metrics.primary_median_return > 0),
        "positive_rate_half": bool(metrics.primary_positive_rate is not None and metrics.primary_positive_rate >= 0.5),
        "primary_lcb_positive": bool(metrics.primary_lcb is not None and metrics.primary_lcb > 0),
        "stress_mean_positive": bool(metrics.stress_mean_return is not None and metrics.stress_mean_return > 0),
        "session_concentration": bool(metrics.max_single_session_row_fraction is not None and metrics.max_single_session_row_fraction <= PHASE24_GATE1_MAX_SINGLE_SESSION_ROW_FRACTION),
    }


def holm_bonferroni(p_values: Mapping[str, float], *, alpha: float) -> dict[str, dict[str, object]]:
    ordered = sorted((float(value), key) for key, value in p_values.items())
    total = len(ordered)
    result: dict[str, dict[str, object]] = {}
    rejecting = True
    for index, (p_value, key) in enumerate(ordered):
        threshold = alpha / (total - index) if total else 0.0
        reject = bool(rejecting and p_value <= threshold)
        result[key] = {"p_value": p_value, "threshold": threshold, "rejected_null": reject}
        if not reject:
            rejecting = False
    return result


class Phase24Gate2Research:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.source_resolver = HistoricalStrategyResearchSourceResolver(settings)
        self.challengers = build_challenger_registry()
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase24" / "v1" / "gate2"
        self.selection_report_path = self.root / "selection_report.json"
        self.selection_lock_path = self.root / "selection_lock.json"
        self.internal_report_path = self.root / "internal_validation_report.json"
        self.finalist_lock_path = self.root / "finalist_lock.json"

    @staticmethod
    def _development_sessions(con: Any, source_sql: str) -> tuple[date, ...]:
        rows = con.execute(
            f"SELECT DISTINCT CAST(session_date AS DATE) FROM {source_sql} "
            f"WHERE session_date < DATE {sql_string(PHASE24_PROTECTED_START_DATE.isoformat())} ORDER BY 1"
        ).fetchall()
        sessions = tuple(row[0] for row in rows)
        if any(item >= PHASE24_PROTECTED_START_DATE for item in sessions):
            raise Phase24Gate2Error("development session query crossed protected holdout")
        return sessions

    @staticmethod
    def _signals(
        con: Any,
        *,
        source_sql: str,
        strategy: RuleStrategy,
        start_date: date,
        end_date: date,
    ) -> tuple[SessionSignal, ...]:
        if end_date >= PHASE24_PROTECTED_START_DATE:
            raise Phase24Gate2Error("Gate 2 cannot query protected evidence")
        condition = strategy_condition_sql(strategy)
        route = historical_market_route_sql(strategy.metadata.direction)
        sign = 1.0 if strategy.metadata.direction == StrategyDirection.LONG else -1.0
        rows = con.execute(
            f"""
            SELECT CAST(session_date AS DATE),
                   min(coalesce(CAST(market_regime_composite AS VARCHAR), 'UNAVAILABLE')),
                   max(coalesce(CAST(market_regime_composite AS VARCHAR), 'UNAVAILABLE')),
                   count(*),
                   avg(CAST(forward_return AS DOUBLE) * {sign:.1f})
            FROM {source_sql}
            WHERE session_date >= DATE {sql_string(start_date.isoformat())}
              AND session_date <= DATE {sql_string(end_date.isoformat())}
              AND session_date < DATE {sql_string(PHASE24_PROTECTED_START_DATE.isoformat())}
              AND forward_return IS NOT NULL
              AND isfinite(CAST(forward_return AS DOUBLE))
              AND {condition}
              AND {route}
            GROUP BY 1 ORDER BY 1
            """
        ).fetchall()
        output: list[SessionSignal] = []
        for session_date, min_regime, max_regime, raw_rows, gross_mean in rows:
            if str(min_regime) != str(max_regime):
                raise Phase24Gate2Error(f"session market regime is inconsistent: {session_date}")
            if gross_mean is None or not math.isfinite(float(gross_mean)):
                raise Phase24Gate2Error("non-finite session return")
            output.append(SessionSignal(session_date, str(min_regime), int(raw_rows), float(gross_mean)))
        return tuple(output)

    @staticmethod
    def _payload(strategy: RuleStrategy, metrics: TrancheMetrics, checks: Mapping[str, bool], role: str) -> dict[str, object]:
        return {
            "strategy_id": strategy.metadata.strategy_id,
            "family": strategy.metadata.family.value,
            "direction": strategy.metadata.direction.value,
            "role": role,
            "metrics": metrics.to_dict(),
            "checks": dict(checks),
            "basic_pass": all(checks.values()),
        }

    def run(self, *, progress: Callable[[str], None] | None = None) -> dict[str, object]:
        if PHASE24_GATE1_PROTECTED_EVIDENCE_READS or PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION:
            raise Phase24Gate2Error("Gate 2 selection boundary changed")
        if PHASE24_GATE1_MAX_FINALISTS_PER_FAMILY_DIRECTION != 1:
            raise Phase24Gate2Error("Gate 2 requires one finalist maximum per family/direction")
        if PHASE24_GATE1_MULTIPLE_TESTING_METHOD != "HOLM_BONFERRONI_WITHIN_FAMILY_DIRECTION":
            raise Phase24Gate2Error("Gate 2 multiple-testing policy changed")

        source = self.source_resolver.resolve()
        con = connect_utc(":memory:")
        try:
            boundaries = chronological_boundaries(self._development_sessions(con, source.source_sql))
            if boundaries.internal_end >= PHASE24_PROTECTED_START_DATE:
                raise Phase24Gate2Error("internal validation crosses protected holdout")

            challenger_results: list[dict[str, object]] = []
            groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
            for strategy in self.challengers.all():
                if progress:
                    progress(f"selection {strategy.metadata.strategy_id}")
                metrics = tranche_metrics(
                    self._signals(con, source_sql=source.source_sql, strategy=strategy, start_date=boundaries.selection_start, end_date=boundaries.selection_end),
                    confidence=PHASE24_GATE1_SELECTION_CONFIDENCE,
                    folds=PHASE24_GATE1_SELECTION_FOLDS,
                    label=f"selection:{strategy.metadata.strategy_id}",
                )
                payload = self._payload(strategy, metrics, selection_checks(metrics), "CHALLENGER_SELECTION")
                challenger_results.append(payload)
                groups[(strategy.metadata.family.value, strategy.metadata.direction.value)].append(payload)

            multiplicity: dict[str, object] = {}
            selected_ids: list[str] = []
            for (family, direction), items in sorted(groups.items()):
                p_values = {
                    str(item["strategy_id"]): float(item["metrics"]["primary_bootstrap_p_value"])
                    for item in items
                    if item["metrics"]["primary_bootstrap_p_value"] is not None
                }
                decisions = holm_bonferroni(p_values, alpha=PHASE24_GATE1_MULTIPLE_TESTING_ALPHA)
                for item in items:
                    sid = str(item["strategy_id"])
                    item["multiplicity"] = decisions.get(sid, {"p_value": None, "threshold": None, "rejected_null": False})
                    item["selection_pass"] = bool(item["basic_pass"] and item["multiplicity"]["rejected_null"])
                passing = [item for item in items if item["selection_pass"]]
                passing.sort(key=lambda item: (-float(item["metrics"]["primary_lcb"]), -float(item["metrics"]["stress_mean_return"]), str(item["strategy_id"])))
                chosen = passing[:1]
                selected_ids.extend(str(item["strategy_id"]) for item in chosen)
                multiplicity[f"{family}:{direction}"] = {"decisions": decisions, "selected": [str(item["strategy_id"]) for item in chosen]}

            incumbent_selection: list[dict[str, object]] = []
            for strategy in DEFAULT_STRATEGY_REGISTRY.all():
                metrics = tranche_metrics(
                    self._signals(con, source_sql=source.source_sql, strategy=strategy, start_date=boundaries.selection_start, end_date=boundaries.selection_end),
                    confidence=PHASE24_GATE1_SELECTION_CONFIDENCE,
                    folds=PHASE24_GATE1_SELECTION_FOLDS,
                    label=f"incumbent-selection:{strategy.metadata.strategy_id}",
                )
                incumbent_selection.append(self._payload(strategy, metrics, selection_checks(metrics), "INCUMBENT_BENCHMARK_NONFRESH"))

            selection_core = {
                "contract_version": PHASE24_GATE2_CONTRACT_VERSION,
                "phase24_gate1_policy_fingerprint": phase24_gate1_policy_fingerprint(),
                "research_source_fingerprint": source.source_fingerprint,
                "development_boundaries": boundaries.to_dict(),
                "challenger_results": challenger_results,
                "incumbent_selection_benchmark": incumbent_selection,
                "multiplicity": multiplicity,
                "selected_strategy_ids": sorted(selected_ids),
                "protected_evidence_reads": 0,
                "provider_reads": 0,
                "broker_reads": 0,
                "order_writes": 0,
                "paper_submits": 0,
                "live_writes": 0,
                "phase11_support_writes": 0,
            }
            selection_report = {**selection_core, "generated_at_utc": datetime.now(UTC).isoformat(), "source_fingerprint": _stable_hash(selection_core), "pass": True}
            self.root.mkdir(parents=True, exist_ok=True)
            atomic_write_text(self.selection_report_path, json.dumps(selection_report, indent=2, sort_keys=True, default=str) + "\n")
            selection_lock = {
                "contract_version": "phase24-gate2-selection-lock-v1-before-internal-validation",
                "phase24_gate1_policy_fingerprint": phase24_gate1_policy_fingerprint(),
                "research_source_fingerprint": source.source_fingerprint,
                "selection_report_sha256": sha256_file(self.selection_report_path),
                "selected_strategy_ids": sorted(selected_ids),
                "internal_validation_has_not_influenced_selection": True,
                "protected_evidence_reads": 0,
                "phase11_support_writes": 0,
            }
            atomic_write_text(self.selection_lock_path, json.dumps(selection_lock, indent=2, sort_keys=True) + "\n")
            selection_lock_sha = sha256_file(self.selection_lock_path)

            selected_set = set(selected_ids)
            internal_results: list[dict[str, object]] = []
            for strategy in self.challengers.all():
                if strategy.metadata.strategy_id not in selected_set:
                    continue
                if progress:
                    progress(f"internal validation {strategy.metadata.strategy_id}")
                metrics = tranche_metrics(
                    self._signals(con, source_sql=source.source_sql, strategy=strategy, start_date=boundaries.internal_start, end_date=boundaries.internal_end),
                    confidence=PHASE24_GATE1_INTERNAL_VALIDATION_CONFIDENCE,
                    folds=PHASE24_GATE1_INTERNAL_VALIDATION_FOLDS,
                    label=f"internal:{strategy.metadata.strategy_id}",
                )
                internal_results.append(self._payload(strategy, metrics, internal_checks(metrics), "FROZEN_FINALIST_INTERNAL_VALIDATION"))

            incumbent_internal: list[dict[str, object]] = []
            for strategy in DEFAULT_STRATEGY_REGISTRY.all():
                metrics = tranche_metrics(
                    self._signals(con, source_sql=source.source_sql, strategy=strategy, start_date=boundaries.internal_start, end_date=boundaries.internal_end),
                    confidence=PHASE24_GATE1_INTERNAL_VALIDATION_CONFIDENCE,
                    folds=PHASE24_GATE1_INTERNAL_VALIDATION_FOLDS,
                    label=f"incumbent-internal:{strategy.metadata.strategy_id}",
                )
                incumbent_internal.append(self._payload(strategy, metrics, internal_checks(metrics), "INCUMBENT_BENCHMARK_NONFRESH"))
        finally:
            con.close()

        finalist_ids = sorted(str(item["strategy_id"]) for item in internal_results if item["basic_pass"])
        internal_core = {
            "contract_version": PHASE24_GATE2_CONTRACT_VERSION,
            "phase24_gate1_policy_fingerprint": phase24_gate1_policy_fingerprint(),
            "research_source_fingerprint": source.source_fingerprint,
            "selection_lock_sha256": selection_lock_sha,
            "selected_strategy_ids": sorted(selected_ids),
            "internal_results": internal_results,
            "incumbent_internal_benchmark": incumbent_internal,
            "fresh_finalist_strategy_ids": finalist_ids,
            "fallback_to_second_best_after_internal_failure": False,
            "protected_evidence_reads": 0,
            "provider_reads": 0,
            "broker_reads": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "phase11_support_writes": 0,
        }
        internal_report = {**internal_core, "generated_at_utc": datetime.now(UTC).isoformat(), "source_fingerprint": _stable_hash(internal_core), "pass": True}
        atomic_write_text(self.internal_report_path, json.dumps(internal_report, indent=2, sort_keys=True, default=str) + "\n")
        finalist_lock = {
            "contract_version": "phase24-gate2-finalist-lock-v1-protected-still-unread",
            "phase24_gate1_policy_fingerprint": phase24_gate1_policy_fingerprint(),
            "research_source_fingerprint": source.source_fingerprint,
            "selection_lock_sha256": selection_lock_sha,
            "internal_validation_report_sha256": sha256_file(self.internal_report_path),
            "fresh_finalist_strategy_ids": finalist_ids,
            "protected_evaluation_authority": False,
            "protected_evidence_reads": 0,
            "provider_reads": 0,
            "broker_reads": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "phase11_support_writes": 0,
            "pass": True,
        }
        atomic_write_text(self.finalist_lock_path, json.dumps(finalist_lock, indent=2, sort_keys=True) + "\n")
        return {
            "contract_version": PHASE24_GATE2_CONTRACT_VERSION,
            "phase24_gate1_policy_fingerprint": phase24_gate1_policy_fingerprint(),
            "selection_report_path": str(self.selection_report_path.resolve()),
            "selection_lock_path": str(self.selection_lock_path.resolve()),
            "internal_validation_report_path": str(self.internal_report_path.resolve()),
            "finalist_lock_path": str(self.finalist_lock_path.resolve()),
            "challenger_count": len(PHASE24_GATE1_CHALLENGER_VARIANTS),
            "selection_basic_pass_count": sum(bool(item["basic_pass"]) for item in challenger_results),
            "selection_multiplicity_pass_count": sum(bool(item.get("selection_pass")) for item in challenger_results),
            "selected_count": len(selected_ids),
            "fresh_finalist_count": len(finalist_ids),
            "fresh_finalist_strategy_ids": finalist_ids,
            "protected_evidence_reads": 0,
            "provider_reads": 0,
            "broker_reads": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "phase11_support_writes": 0,
            "pass": True,
        }
