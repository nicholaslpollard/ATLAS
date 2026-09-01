from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable

import numpy as np
import pandas as pd

from .phase26_policy import (
    PHASE26_BOOTSTRAP_REPLICATES,
    PHASE26_CANDIDATES,
    PHASE26_MULTIPLE_TESTING_ALPHA,
    PHASE26_SELECTION_CONFIDENCE,
    PHASE26_SELECTION_FOLDS,
    PHASE26_SELECTION_MIN_RAW_ROWS,
    PHASE26_SELECTION_MIN_SIGNAL_SESSIONS,
)
from .phase26_research import holm_bonferroni, selection_checks, tranche_metrics


RESEARCH_GATE_CALIBRATION_CONTRACT_VERSION = (
    "research-gate-calibration-v1-positive-path-capacity-and-power"
)


class ReachabilityDisposition(StrEnum):
    REACHABLE = "REACHABLE"
    REACHABLE_CAPACITY_UNPROVEN = "REACHABLE_CAPACITY_UNPROVEN"
    UNPASSABLE_ARITHMETIC = "UNPASSABLE_ARITHMETIC"
    CAPACITY_UNREACHABLE = "CAPACITY_UNREACHABLE"


@dataclass(frozen=True, slots=True)
class GateCapacityEvidence:
    rows: int | None = None
    sessions: int | None = None
    instruments: int | None = None
    is_upper_bound: bool = False
    source: str = "UNSPECIFIED"


@dataclass(frozen=True, slots=True)
class GateReachabilitySpec:
    name: str
    candidate_count: int
    family_alpha: float
    empirical_replicates: int
    min_rows: int
    min_sessions: int
    min_instruments: int = 0
    capacity: GateCapacityEvidence | None = None


@dataclass(frozen=True, slots=True)
class GateReachabilityAssessment:
    disposition: ReachabilityDisposition
    strictest_holm_threshold: float
    empirical_p_value_floor: float
    arithmetic_passable: bool
    capacity_passable: bool | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["disposition"] = self.disposition.value
        return payload


def assess_gate_reachability(spec: GateReachabilitySpec) -> GateReachabilityAssessment:
    if spec.candidate_count <= 0:
        raise ValueError("candidate_count must be positive")
    if not 0.0 < spec.family_alpha < 1.0:
        raise ValueError("family_alpha must be between zero and one")
    if spec.empirical_replicates <= 0:
        raise ValueError("empirical_replicates must be positive")
    if min(spec.min_rows, spec.min_sessions, spec.min_instruments) < 0:
        raise ValueError("minimum sample requirements cannot be negative")

    strictest = spec.family_alpha / spec.candidate_count
    p_floor = 1.0 / (spec.empirical_replicates + 1.0)
    arithmetic_passable = p_floor <= strictest
    reasons: list[str] = []
    if not arithmetic_passable:
        reasons.append(
            "empirical p-value floor exceeds the strictest Holm-Bonferroni threshold"
        )
        return GateReachabilityAssessment(
            disposition=ReachabilityDisposition.UNPASSABLE_ARITHMETIC,
            strictest_holm_threshold=strictest,
            empirical_p_value_floor=p_floor,
            arithmetic_passable=False,
            capacity_passable=None,
            reasons=tuple(reasons),
        )

    capacity = spec.capacity
    if capacity is None:
        reasons.append("no source-only capacity evidence supplied")
        return GateReachabilityAssessment(
            disposition=ReachabilityDisposition.REACHABLE_CAPACITY_UNPROVEN,
            strictest_holm_threshold=strictest,
            empirical_p_value_floor=p_floor,
            arithmetic_passable=True,
            capacity_passable=None,
            reasons=tuple(reasons),
        )

    observed_below = []
    for field, minimum in (
        ("rows", spec.min_rows),
        ("sessions", spec.min_sessions),
        ("instruments", spec.min_instruments),
    ):
        value = getattr(capacity, field)
        if value is not None and value < minimum:
            observed_below.append(f"{field}={value} < minimum={minimum}")

    if observed_below and capacity.is_upper_bound:
        reasons.extend(observed_below)
        reasons.append(f"capacity evidence is a declared upper bound: {capacity.source}")
        return GateReachabilityAssessment(
            disposition=ReachabilityDisposition.CAPACITY_UNREACHABLE,
            strictest_holm_threshold=strictest,
            empirical_p_value_floor=p_floor,
            arithmetic_passable=True,
            capacity_passable=False,
            reasons=tuple(reasons),
        )

    if observed_below:
        reasons.extend(observed_below)
        reasons.append(
            "capacity evidence is not an upper bound; a probe or partial census cannot prove impossibility"
        )
        return GateReachabilityAssessment(
            disposition=ReachabilityDisposition.REACHABLE_CAPACITY_UNPROVEN,
            strictest_holm_threshold=strictest,
            empirical_p_value_floor=p_floor,
            arithmetic_passable=True,
            capacity_passable=None,
            reasons=tuple(reasons),
        )

    reasons.append(f"known capacity satisfies frozen minima: {capacity.source}")
    return GateReachabilityAssessment(
        disposition=ReachabilityDisposition.REACHABLE,
        strictest_holm_threshold=strictest,
        empirical_p_value_floor=p_floor,
        arithmetic_passable=True,
        capacity_passable=True,
        reasons=tuple(reasons),
    )


def phase26_selection_reachability() -> GateReachabilityAssessment:
    return assess_gate_reachability(
        GateReachabilitySpec(
            name="phase26_selection",
            candidate_count=len(PHASE26_CANDIDATES),
            family_alpha=PHASE26_MULTIPLE_TESTING_ALPHA,
            empirical_replicates=PHASE26_BOOTSTRAP_REPLICATES,
            min_rows=PHASE26_SELECTION_MIN_RAW_ROWS,
            min_sessions=PHASE26_SELECTION_MIN_SIGNAL_SESSIONS,
        )
    )


@dataclass(frozen=True, slots=True)
class SyntheticGateTrial:
    seed: int
    gross_edge: float
    volatility: float
    promoted: bool
    p_value: float | None
    holm_threshold: float | None
    primary_mean_return: float | None
    stress_mean_return: float | None
    primary_lcb: float | None
    failed_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SyntheticPowerResult:
    gross_edge: float
    volatility: float
    trials: int
    promotions: int
    promotion_rate: float
    trial_results: tuple[SyntheticGateTrial, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "gross_edge": self.gross_edge,
            "volatility": self.volatility,
            "trials": self.trials,
            "promotions": self.promotions,
            "promotion_rate": self.promotion_rate,
            "trial_results": [item.to_dict() for item in self.trial_results],
        }


def _synthetic_phase26_frame(
    *,
    gross_edge: float,
    volatility: float,
    seed: int,
    sessions: int = 300,
    rows_per_session: int = 4,
) -> pd.DataFrame:
    if sessions < PHASE26_SELECTION_MIN_SIGNAL_SESSIONS:
        raise ValueError("synthetic calibration must meet the Phase26 session floor")
    if sessions * rows_per_session < PHASE26_SELECTION_MIN_RAW_ROWS:
        raise ValueError("synthetic calibration must meet the Phase26 row floor")
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=sessions).date
    session_returns = gross_edge + rng.normal(0.0, volatility, size=sessions)
    market_states = ("BULL", "BEAR", "NEUTRAL")
    ticker_states = ("UPTREND", "DOWNTREND", "RANGE")
    rows: list[dict[str, object]] = []
    for index, (session_date, directional_return) in enumerate(
        zip(dates, session_returns, strict=True)
    ):
        for row_index in range(rows_per_session):
            rows.append(
                {
                    "as_of_date": session_date,
                    "directional_return": float(directional_return),
                    "market_state": market_states[index % len(market_states)],
                    "effective_ticker_state": ticker_states[
                        (index + row_index) % len(ticker_states)
                    ],
                }
            )
    return pd.DataFrame(rows)


def phase26_synthetic_trial(
    *,
    gross_edge: float,
    volatility: float,
    seed: int,
) -> SyntheticGateTrial:
    frame = _synthetic_phase26_frame(
        gross_edge=gross_edge,
        volatility=volatility,
        seed=seed,
    )
    label = f"research_gate_calibration:phase26:{gross_edge:.8f}:{volatility:.8f}:{seed}"
    metrics = tranche_metrics(
        frame,
        confidence=PHASE26_SELECTION_CONFIDENCE,
        folds=PHASE26_SELECTION_FOLDS,
        label=label,
    )
    checks = selection_checks(metrics)
    failed_checks = tuple(sorted(key for key, value in checks.items() if not value))

    target_p = 1.0 if metrics.primary_bootstrap_p_value is None else metrics.primary_bootstrap_p_value
    p_values = {"synthetic_target": target_p}
    for index in range(len(PHASE26_CANDIDATES) - 1):
        p_values[f"synthetic_null_{index:02d}"] = 1.0
    holm = holm_bonferroni(p_values)
    target_holm = holm["synthetic_target"]
    promoted = bool(not failed_checks and target_holm["rejected_null"])
    return SyntheticGateTrial(
        seed=seed,
        gross_edge=gross_edge,
        volatility=volatility,
        promoted=promoted,
        p_value=metrics.primary_bootstrap_p_value,
        holm_threshold=float(target_holm["threshold"]),
        primary_mean_return=metrics.primary_mean_return,
        stress_mean_return=metrics.stress_mean_return,
        primary_lcb=metrics.primary_lcb,
        failed_checks=failed_checks,
    )


def phase26_synthetic_power(
    *,
    gross_edge: float,
    volatility: float,
    seeds: Iterable[int],
) -> SyntheticPowerResult:
    trials = tuple(
        phase26_synthetic_trial(
            gross_edge=gross_edge,
            volatility=volatility,
            seed=int(seed),
        )
        for seed in seeds
    )
    if not trials:
        raise ValueError("at least one seed is required")
    promotions = sum(item.promoted for item in trials)
    return SyntheticPowerResult(
        gross_edge=gross_edge,
        volatility=volatility,
        trials=len(trials),
        promotions=promotions,
        promotion_rate=promotions / len(trials),
        trial_results=trials,
    )
