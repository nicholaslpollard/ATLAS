from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_native_population import (
    MOMSEASON_NATIVE_POPULATION_CONTRACT,
    MOMSEASON_NATIVE_POPULATION_ROOT,
    MOMSEASON_NATIVE_REPORT,
)
from .literature_momseason_policy import (
    LITERATURE_MOMSEASON_FAMILY,
    LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS,
    LITERATURE_MOMSEASON_PROTECTED_END,
    LITERATURE_MOMSEASON_PROTECTED_START,
    MOMSEASON_HYPOTHESES,
    formation_months,
    literature_momseason_source_fingerprint,
    temporal_capacity,
)
from .literature_momseason_source import MOMSEASON_SOURCE_ROOT_RELATIVE
from .phase26_policy import PHASE26_PRIMARY_COST_BPS, PHASE26_STRESS_COST_BPS
from .phase26_research import holm_bonferroni
from .research_gate_calibration import GateCapacityEvidence, GateReachabilitySpec
from .research_gate_freeze import (
    MechanismDensity,
    ProspectiveResearchFreezeSpec,
    assess_prospective_research_freeze,
)
from .research_population_coverage import (
    PopulationCoverageStage,
    PopulationScope,
    assess_population_coverage,
)


MOMSEASON_RESEARCH_FREEZE_CONTRACT = (
    "literature-momseason-research-freeze-v1-native-monthly-ew-decile-holm-pre-outcome"
)
MOMSEASON_RESEARCH_FREEZE_STATUS = "LIT01_RESEARCH_GATE_AND_SCIENTIFIC_FREEZE_READY"
MOMSEASON_RESEARCH_FREEZE_BLOCKED = "LIT01_RESEARCH_GATE_AND_SCIENTIFIC_FREEZE_BLOCKED"
MOMSEASON_RESEARCH_FREEZE_ROOT = "research_freeze"
MOMSEASON_RESEARCH_FREEZE_REPORT = "lit01_research_freeze.json"

# The two hypotheses are externally specified and form one fixed family.
MOMSEASON_FAMILY_ALPHA = 0.05
MOMSEASON_BOOTSTRAP_REPLICATES = 2000
MOMSEASON_BOOTSTRAP_BLOCK_MONTHS = 12
MOMSEASON_BOOTSTRAP_CONFIDENCE = 0.90
MOMSEASON_CALIBRATION_TRIALS = 256
MOMSEASON_CALIBRATION_SEED = 20260808
MOMSEASON_CALIBRATION_MONTHLY_VOLATILITY = 0.035
MOMSEASON_CALIBRATION_TARGET_FAMILY_DETECTION_RATE = 2.0 / 3.0
MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED = 56
MOMSEASON_LONG_SHORT_QUANTILE = 0.10
MOMSEASON_PORTFOLIO_WEIGHTING = "EQUAL_WEIGHT"
MOMSEASON_PORTFOLIO_HOLD_MONTHS = 1
MOMSEASON_ROBUSTNESS_FOLDS = 4

# SignalDoc/OpenSourceAP reports these gross monthly long-short effects. They are
# external calibration anchors only; ATLAS development outcomes are never used here.
MOMSEASON_EXTERNAL_GROSS_MONTHLY_EFFECT = {
    "momseason_short_year1": 0.0115,
    "momseason_years2_5": 0.0067,
}
MOMSEASON_EXTERNAL_SOURCE_COMMIT = "8db892442c2c3a3779b0f1eac4370d3655be15a1"

# ATLAS Phase26's retained convention is 10 bps primary and 25 bps stress per
# trade/leg. A two-leg long-short portfolio therefore has a conservative full-
# turnover calibration drag of 20/50 bps. Actual research applies cost to realized
# one-way turnover of each leg rather than blindly subtracting the full-turnover cap.
MOMSEASON_PRIMARY_COST_PER_LEG_BPS = float(PHASE26_PRIMARY_COST_BPS)
MOMSEASON_STRESS_COST_PER_LEG_BPS = float(PHASE26_STRESS_COST_BPS)
MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS = 2.0


@dataclass(frozen=True, slots=True)
class CalibrationHypothesisTrial:
    hypothesis_id: str
    primary_mean: float
    primary_lcb: float
    primary_p_value: float
    holm_threshold: float
    holm_rejected_null: bool
    stress_mean: float
    positive_folds: int
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CalibrationTrial:
    trial_index: int
    family_promoted: bool
    hypotheses: tuple[CalibrationHypothesisTrial, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "trial_index": self.trial_index,
            "family_promoted": self.family_promoted,
            "hypotheses": [item.to_dict() for item in self.hypotheses],
        }


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _derived_seed(label: str) -> int:
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return MOMSEASON_CALIBRATION_SEED + int(digest[:8], 16)


def _circular_block_bootstrap_positive(
    values: np.ndarray,
    *,
    label: str,
) -> tuple[float, float, float]:
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("LIT-01 bootstrap requires a nonempty monthly vector")
    n = len(values)
    block = min(MOMSEASON_BOOTSTRAP_BLOCK_MONTHS, n)
    block_count = int(math.ceil(n / block))
    rng = np.random.default_rng(_derived_seed(f"bootstrap:{label}"))
    starts = rng.integers(
        0,
        n,
        size=(MOMSEASON_BOOTSTRAP_REPLICATES, block_count),
    )
    offsets = np.arange(block, dtype=np.int64)
    indices = ((starts[:, :, None] + offsets) % n).reshape(
        MOMSEASON_BOOTSTRAP_REPLICATES, -1
    )[:, :n]
    sample_means = values[indices].mean(axis=1)
    observed = float(values.mean())
    lower = float(np.quantile(sample_means, 1.0 - MOMSEASON_BOOTSTRAP_CONFIDENCE))
    centered = values - observed
    null_means = centered[indices].mean(axis=1)
    p_value = float(
        (1 + np.count_nonzero(null_means >= observed))
        / (MOMSEASON_BOOTSTRAP_REPLICATES + 1)
    )
    return observed, lower, p_value


def _fold_means(values: np.ndarray) -> tuple[float, ...]:
    if len(values) < MOMSEASON_ROBUSTNESS_FOLDS:
        return ()
    return tuple(
        float(part.mean())
        for part in np.array_split(values, MOMSEASON_ROBUSTNESS_FOLDS)
        if len(part)
    )


def _calibration_trial(trial_index: int) -> CalibrationTrial:
    if trial_index < 0:
        raise ValueError("trial_index cannot be negative")
    provisional: dict[str, dict[str, object]] = {}
    primary_spread_cost = (
        MOMSEASON_PRIMARY_COST_PER_LEG_BPS
        * MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS
        / 10_000.0
    )
    stress_spread_cost = (
        MOMSEASON_STRESS_COST_PER_LEG_BPS
        * MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS
        / 10_000.0
    )

    for hypothesis in MOMSEASON_HYPOTHESES:
        hypothesis_id = hypothesis.hypothesis_id
        gross_edge = MOMSEASON_EXTERNAL_GROSS_MONTHLY_EFFECT[hypothesis_id]
        rng = np.random.default_rng(
            _derived_seed(f"synthetic:{trial_index}:{hypothesis_id}")
        )
        gross = gross_edge + rng.normal(
            0.0,
            MOMSEASON_CALIBRATION_MONTHLY_VOLATILITY,
            size=MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED,
        )
        primary = gross - primary_spread_cost
        stress = gross - stress_spread_cost
        primary_mean, primary_lcb, p_value = _circular_block_bootstrap_positive(
            primary,
            label=f"trial:{trial_index}:{hypothesis_id}",
        )
        fold_means = _fold_means(primary)
        provisional[hypothesis_id] = {
            "primary_mean": primary_mean,
            "primary_lcb": primary_lcb,
            "primary_p_value": p_value,
            "stress_mean": float(stress.mean()),
            "positive_folds": sum(value > 0.0 for value in fold_means),
        }

    holm = holm_bonferroni(
        {
            hypothesis_id: float(item["primary_p_value"])
            for hypothesis_id, item in provisional.items()
        },
        alpha=MOMSEASON_FAMILY_ALPHA,
    )
    results: list[CalibrationHypothesisTrial] = []
    for hypothesis in MOMSEASON_HYPOTHESES:
        hypothesis_id = hypothesis.hypothesis_id
        item = provisional[hypothesis_id]
        correction = holm[hypothesis_id]
        passed = bool(
            correction["rejected_null"]
            and float(item["primary_mean"]) > 0.0
            and float(item["primary_lcb"]) > 0.0
            and float(item["stress_mean"]) > 0.0
        )
        results.append(
            CalibrationHypothesisTrial(
                hypothesis_id=hypothesis_id,
                primary_mean=float(item["primary_mean"]),
                primary_lcb=float(item["primary_lcb"]),
                primary_p_value=float(item["primary_p_value"]),
                holm_threshold=float(correction["threshold"]),
                holm_rejected_null=bool(correction["rejected_null"]),
                stress_mean=float(item["stress_mean"]),
                positive_folds=int(item["positive_folds"]),
                passed=passed,
            )
        )
    return CalibrationTrial(
        trial_index=trial_index,
        family_promoted=any(item.passed for item in results),
        hypotheses=tuple(results),
    )


def positive_path_calibration() -> dict[str, object]:
    trials = tuple(_calibration_trial(index) for index in range(MOMSEASON_CALIBRATION_TRIALS))
    promotions = sum(item.family_promoted for item in trials)
    by_hypothesis: dict[str, int] = {item.hypothesis_id: 0 for item in MOMSEASON_HYPOTHESES}
    for trial in trials:
        for item in trial.hypotheses:
            by_hypothesis[item.hypothesis_id] += int(item.passed)
    rate = promotions / len(trials)
    return {
        "contract": "lit01-positive-path-power-v1-external-effect-monthly-block-bootstrap",
        "trials": len(trials),
        "family_promotions": promotions,
        "family_detection_rate": rate,
        "target_family_detection_rate": MOMSEASON_CALIBRATION_TARGET_FAMILY_DETECTION_RATE,
        "target_met": rate >= MOMSEASON_CALIBRATION_TARGET_FAMILY_DETECTION_RATE,
        "hypothesis_detection_rates": {
            key: value / len(trials) for key, value in sorted(by_hypothesis.items())
        },
        "synthetic_months_per_trial": MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED,
        "monthly_volatility": MOMSEASON_CALIBRATION_MONTHLY_VOLATILITY,
        "external_gross_monthly_effects": dict(sorted(MOMSEASON_EXTERNAL_GROSS_MONTHLY_EFFECT.items())),
        "primary_full_turnover_spread_cost_bps": (
            MOMSEASON_PRIMARY_COST_PER_LEG_BPS * MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS
        ),
        "stress_full_turnover_spread_cost_bps": (
            MOMSEASON_STRESS_COST_PER_LEG_BPS * MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS
        ),
        "bootstrap_replicates": MOMSEASON_BOOTSTRAP_REPLICATES,
        "bootstrap_block_months": MOMSEASON_BOOTSTRAP_BLOCK_MONTHS,
        "bootstrap_confidence": MOMSEASON_BOOTSTRAP_CONFIDENCE,
        "family_alpha": MOMSEASON_FAMILY_ALPHA,
        "family_size": len(MOMSEASON_HYPOTHESES),
        "seed": MOMSEASON_CALIBRATION_SEED,
        "calibration_is_external_synthetic_only": True,
        "atlas_development_outcomes_used": False,
    }


def _population_from_native_report(report: Mapping[str, object]):
    coverage = report.get("coverage")
    if not isinstance(coverage, Mapping):
        raise RuntimeError("native LIT-01 report is missing coverage")
    population = coverage.get("population_coverage")
    if not isinstance(population, Mapping):
        raise RuntimeError("native LIT-01 report is missing population coverage")
    raw_stages = population.get("stages")
    if not isinstance(raw_stages, list) or not raw_stages:
        raise RuntimeError("native LIT-01 population stages are unavailable")
    stages: list[PopulationCoverageStage] = []
    for raw in raw_stages:
        if not isinstance(raw, Mapping):
            raise RuntimeError("invalid native LIT-01 population stage")
        stages.append(
            PopulationCoverageStage(
                name=str(raw["name"]),
                rows=int(raw["rows"]),
                sessions=(None if raw.get("sessions") is None else int(raw["sessions"])),
                instruments=(None if raw.get("instruments") is None else int(raw["instruments"])),
                scope=PopulationScope(str(raw["scope"])),
                complete_scope=bool(raw.get("complete_scope", True)),
                comparable_to_previous=bool(raw.get("comparable_to_previous", True)),
                grain=str(raw.get("grain") or "candidate_key"),
                source=str(raw.get("source") or "UNSPECIFIED"),
            )
        )
    assessment = assess_population_coverage(stages)
    if not assessment.valid_contract or not assessment.source_scope_proven:
        raise RuntimeError("native LIT-01 source population is not freeze-ready")
    return assessment


def _require_native_source_report(report: Mapping[str, object]) -> None:
    if report.get("status") != "NATIVE_POPULATION_SOURCE_CAPACITY_READY_FOR_REVIEW":
        raise RuntimeError("native LIT-01 source report is not capacity-ready")
    if report.get("contract_version") != MOMSEASON_NATIVE_POPULATION_CONTRACT:
        raise RuntimeError("native LIT-01 source report contract mismatch")
    zero_fields = (
        "target_outcome_rows_read",
        "protected_return_rows_read",
        "broker_reads_performed",
        "broker_writes_performed",
        "order_writes_performed",
        "paper_submits_performed",
        "live_writes_performed",
    )
    for field in zero_fields:
        if int(report.get(field) or 0) != 0:
            raise RuntimeError(f"native LIT-01 source safety field is nonzero: {field}")
    false_fields = (
        "existing_canonical_market_data_mutated",
        "global_alpaca_adjustment_mutated",
        "protected_holdout_consumed",
    )
    for field in false_fields:
        if bool(report.get(field)):
            raise RuntimeError(f"native LIT-01 source safety field is true: {field}")


def _development_month_keys() -> tuple[str, ...]:
    return tuple(
        item.month_start.strftime("%Y-%m")
        for item in formation_months()
        if item.scope == "DEVELOPMENT"
    )


def build_research_freeze_report(native_report: Mapping[str, object]) -> dict[str, object]:
    _require_native_source_report(native_report)
    population = _population_from_native_report(native_report)
    development_months = _development_month_keys()
    if len(development_months) != MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED:
        raise RuntimeError(
            "LIT-01 development temporal capacity changed before freeze: "
            f"expected {MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED}, got {len(development_months)}"
        )
    temporal = temporal_capacity()
    if int(temporal["protected_complete_target_months"]) >= int(
        temporal["minimum_protected_complete_months"]
    ):
        raise RuntimeError("LIT-01 current protected window unexpectedly became sufficient")

    calibration = positive_path_calibration()
    gate = GateReachabilitySpec(
        name="lit01_monthly_portfolio_confirmation",
        candidate_count=len(MOMSEASON_HYPOTHESES),
        family_alpha=MOMSEASON_FAMILY_ALPHA,
        empirical_replicates=MOMSEASON_BOOTSTRAP_REPLICATES,
        min_rows=MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED,
        min_sessions=MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED,
        min_instruments=0,
        capacity=GateCapacityEvidence(
            rows=len(development_months),
            sessions=len(development_months),
            instruments=None,
            is_upper_bound=True,
            source="complete pre-protected LIT-01 development calendar-month census",
        ),
    )
    conservative_after_cost_edge = min(MOMSEASON_EXTERNAL_GROSS_MONTHLY_EFFECT.values()) - (
        MOMSEASON_PRIMARY_COST_PER_LEG_BPS
        * MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS
        / 10_000.0
    )
    freeze_assessment = assess_prospective_research_freeze(
        ProspectiveResearchFreezeSpec(
            name="LIT-01 Heston-Sadka calendar-month return seasonality",
            gate=gate,
            population=population,
            mechanism_density=MechanismDensity.CROSS_SECTIONAL,
            expected_after_cost_edge=conservative_after_cost_edge,
            primary_cost_bps=(
                MOMSEASON_PRIMARY_COST_PER_LEG_BPS
                * MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS
            ),
            calibration_trials=int(calibration["trials"]),
            calibration_promotions=int(calibration["family_promotions"]),
            target_detection_rate=MOMSEASON_CALIBRATION_TARGET_FAMILY_DETECTION_RATE,
            sample_size_rationale=(
                "The independent inferential unit is the calendar-month EW long-short portfolio return, "
                "not the underlying stock row. The source contract provides exactly 56 complete "
                "development months (2021-09 through 2026-04) before the May 2026 purge boundary."
            ),
            bottleneck_explanation=None,
            protected_outcome_reads=0,
        )
    )

    native_plan = native_report.get("native_plan")
    if not isinstance(native_plan, Mapping):
        raise RuntimeError("native LIT-01 plan evidence is missing")
    native_plan_fingerprint = str(native_plan.get("plan_fingerprint") or "")
    if not native_plan_fingerprint:
        raise RuntimeError("native LIT-01 plan fingerprint is missing")

    scientific_contract: dict[str, object] = {
        "contract_version": MOMSEASON_RESEARCH_FREEZE_CONTRACT,
        "family": LITERATURE_MOMSEASON_FAMILY,
        "external_specification": {
            "source": "Heston and Sadka (2008) via OpenSourceAP/CrossSection",
            "opensourceap_commit": MOMSEASON_EXTERNAL_SOURCE_COMMIT,
            "hypotheses": [
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "external_signal": hypothesis.external_signal,
                    "direction": hypothesis.direction,
                    "lag_years": list(hypothesis.lag_years),
                    "formula": (
                        "same-calendar-month total return one year earlier"
                        if hypothesis.hypothesis_id == "momseason_short_year1"
                        else "simple average of all available valid same-calendar-month total returns among years 2,3,4,5; at least one required"
                    ),
                    "portfolio_period_months": hypothesis.portfolio_period_months,
                }
                for hypothesis in MOMSEASON_HYPOTHESES
            ],
            "adaptive_hypothesis_deletion_allowed": False,
            "adaptive_lag_count_subgroup_selection_allowed": False,
        },
        "source_binding": {
            "source_policy_fingerprint": literature_momseason_source_fingerprint(),
            "native_population_contract": MOMSEASON_NATIVE_POPULATION_CONTRACT,
            "native_plan_fingerprint": native_plan_fingerprint,
            "native_endpoint_availability_counts": dict(
                sorted((native_report.get("endpoint_availability_counts") or {}).items())
            ),
            "population_coverage": population.to_dict(),
        },
        "portfolio": {
            "formation_universe": "PIT NYSE/NYSE-American Massive common-stock analogue (XNYS/XASE, security_type=CS)",
            "ranking": "cross-sectional ascending predictor value within each target month",
            "long_leg": "top decile",
            "short_leg": "bottom decile",
            "long_short_quantile": MOMSEASON_LONG_SHORT_QUANTILE,
            "weighting": MOMSEASON_PORTFOLIO_WEIGHTING,
            "holding_period_months": MOMSEASON_PORTFOLIO_HOLD_MONTHS,
            "gross_return": "equal-weight top-decile target-month total return minus equal-weight bottom-decile target-month total return",
            "target_month_return": "adjusted month-end close divided by prior month-end adjusted close minus one",
            "target_source_semantics": "Alpaca 1Day adjustment=all with PIT endpoint asof; stable ATLAS instrument identity remains identity authority",
            "native_signal_first": True,
            "phase25_warm_hot_filter_applied_to_primary": False,
        },
        "transaction_costs": {
            "retained_atlas_convention": "Phase26 per-trade/leg cost convention",
            "primary_bps_per_one_way_leg_turnover": MOMSEASON_PRIMARY_COST_PER_LEG_BPS,
            "stress_bps_per_one_way_leg_turnover": MOMSEASON_STRESS_COST_PER_LEG_BPS,
            "actual_cost_rule": "cost_bps * realized one-way turnover separately for long and short legs; total spread drag is the sum of both legs",
            "calibration_assumes_full_turnover_each_leg": True,
            "calibration_full_turnover_legs": MOMSEASON_CALIBRATION_FULL_TURNOVER_LEGS,
        },
        "development_gate": {
            "independent_unit": "target_calendar_month_long_short_portfolio_return",
            "development_months": list(development_months),
            "development_month_count": len(development_months),
            "family_size": len(MOMSEASON_HYPOTHESES),
            "family_alpha": MOMSEASON_FAMILY_ALPHA,
            "multiple_testing": "HOLM_BONFERRONI_FIXED_TWO_HYPOTHESES",
            "bootstrap": {
                "type": "circular_block_bootstrap",
                "block_months": MOMSEASON_BOOTSTRAP_BLOCK_MONTHS,
                "replicates": MOMSEASON_BOOTSTRAP_REPLICATES,
                "one_sided_direction": "POSITIVE",
                "confidence": MOMSEASON_BOOTSTRAP_CONFIDENCE,
            },
            "hypothesis_primary_pass": [
                "primary after-cost mean > 0",
                "90% one-sided circular-block bootstrap lower confidence bound > 0",
                "one-sided bootstrap p-value rejected after Holm correction across both fixed hypotheses",
                "25-bps-per-leg turnover stress mean > 0",
            ],
            "family_finalist_rule": "at least one fixed hypothesis passes all primary checks; both hypotheses remain reported regardless of result",
            "robustness_reported_not_used_for_adaptive_selection": {
                "chronological_folds": MOMSEASON_ROBUSTNESS_FOLDS,
                "calendar_month_of_year_slices": 12,
                "years2_5_valid_lag_count_slices": [1, 2, 3, 4],
                "gross_external_replication_result": True,
            },
            "stock_rows_are_not_independent_observations": True,
        },
        "outcome_missingness_and_delisting": {
            "formation_cohort_fixed_before_target_outcomes": True,
            "future_terminal_price_availability_may_not_filter_formation_cohort": True,
            "silent_drop_of_missing_or_delisted_holding": False,
            "zero_return_imputation": False,
            "last_price_imputation_without_source_grounding": False,
            "rule": (
                "Every formation holding remains in the target cohort. If a complete source-grounded total return cannot be reconstructed, "
                "the affected primary portfolio month is source-incomplete and cannot count as confirmatory evidence until a prospectively allowed, provider-grounded corporate-action/delisting resolution is established without using the return sign to choose the treatment."
            ),
        },
        "protected_policy": {
            "current_window_start": LITERATURE_MOMSEASON_PROTECTED_START.isoformat(),
            "current_window_end": LITERATURE_MOMSEASON_PROTECTED_END.isoformat(),
            "current_complete_target_months": int(temporal["protected_complete_target_months"]),
            "minimum_complete_target_months": LITERATURE_MOMSEASON_MIN_PROTECTED_COMPLETE_MONTHS,
            "current_window_sufficient": bool(temporal["current_protected_temporal_capacity_sufficient"]),
            "if_internal_finalist": "reserve a new prospective protected window containing at least 12 complete target calendar months before reading any of those returns",
            "protected_outcomes_before_finalist": False,
        },
        "authority": {
            "experimental_branch_only": True,
            "mainline_alpha_status_changed": False,
            "phase33_authority_changed": False,
            "paper_authority": False,
            "live_authority": False,
            "automatic_adoption": False,
        },
        "positive_path_calibration": calibration,
        "generic_freeze_assessment": freeze_assessment.to_dict(),
    }
    freeze_fingerprint = _fingerprint(scientific_contract)
    status = (
        MOMSEASON_RESEARCH_FREEZE_STATUS
        if freeze_assessment.ready_to_freeze
        else MOMSEASON_RESEARCH_FREEZE_BLOCKED
    )
    return {
        "status": status,
        "contract_version": MOMSEASON_RESEARCH_FREEZE_CONTRACT,
        "freeze_fingerprint": freeze_fingerprint,
        "scientific_contract": scientific_contract,
        "gate_assessment": freeze_assessment.to_dict(),
        "positive_path_calibration": calibration,
        "development_outcome_rows_read": 0,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "provider_reads_performed": 0,
        "provider_writes_performed": 0,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
    }


class MomSeasonResearchFreeze:
    """Freeze LIT-01 research gates from source-only evidence before outcomes."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        derived = settings.resolved_path(settings.data.paths.derived)
        self.native_root = (
            derived
            / MOMSEASON_SOURCE_ROOT_RELATIVE
            / "total_return_source"
            / MOMSEASON_NATIVE_POPULATION_ROOT
        )
        self.root = self.native_root / MOMSEASON_RESEARCH_FREEZE_ROOT

    def native_report_path(self) -> Path:
        return self.native_root / MOMSEASON_NATIVE_REPORT

    def report_path(self) -> Path:
        return self.root / MOMSEASON_RESEARCH_FREEZE_REPORT

    def run(self) -> dict[str, object]:
        native_path = self.native_report_path()
        if not native_path.is_file():
            raise RuntimeError(f"native LIT-01 source report is required: {native_path}")
        native_report = json.loads(native_path.read_text(encoding="utf-8"))
        if not isinstance(native_report, dict):
            raise RuntimeError("native LIT-01 source report is invalid")
        report = build_research_freeze_report(native_report)
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), _canonical_json(report) + "\n")
        report["report_path"] = str(self.report_path())
        return report


assert len(MOMSEASON_HYPOTHESES) == 2
assert MOMSEASON_PRIMARY_COST_PER_LEG_BPS == 10.0
assert MOMSEASON_STRESS_COST_PER_LEG_BPS == 25.0
assert MOMSEASON_BOOTSTRAP_BLOCK_MONTHS == 12
assert MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED == 56
