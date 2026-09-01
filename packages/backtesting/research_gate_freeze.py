from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from .research_gate_calibration import (
    GateReachabilityAssessment,
    GateReachabilitySpec,
    ReachabilityDisposition,
    assess_gate_reachability,
)
from .research_population_coverage import PopulationCoverageAssessment


RESEARCH_GATE_FREEZE_CONTRACT_VERSION = (
    "research-gate-freeze-v1-reachability-population-power-before-outcomes"
)


class ResearchFreezeDisposition(StrEnum):
    READY_TO_FREEZE = "READY_TO_FREEZE"
    BLOCKED_ARITHMETIC = "BLOCKED_ARITHMETIC"
    BLOCKED_CAPACITY = "BLOCKED_CAPACITY"
    BLOCKED_POPULATION_EVIDENCE = "BLOCKED_POPULATION_EVIDENCE"
    BLOCKED_POWER_PLAN = "BLOCKED_POWER_PLAN"
    BLOCKED_PROTECTED_CONTAMINATION = "BLOCKED_PROTECTED_CONTAMINATION"


class MechanismDensity(StrEnum):
    DENSE_TECHNICAL = "DENSE_TECHNICAL"
    CROSS_SECTIONAL = "CROSS_SECTIONAL"
    SPARSE_EVENT = "SPARSE_EVENT"
    RELATIVE_VALUE = "RELATIVE_VALUE"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class ProspectiveResearchFreezeSpec:
    """Pre-outcome contract for future ATLAS alpha experiments.

    This validator is intentionally prospective. Historical frozen experiments are not
    re-scored through it. The purpose is to ensure that a future scientific contract is
    capable of succeeding before development or protected outcomes are opened.
    """

    name: str
    gate: GateReachabilitySpec
    population: PopulationCoverageAssessment
    mechanism_density: MechanismDensity
    expected_after_cost_edge: float
    primary_cost_bps: float
    calibration_trials: int
    calibration_promotions: int
    target_detection_rate: float
    sample_size_rationale: str
    bottleneck_explanation: str | None = None
    protected_outcome_reads: int = 0


@dataclass(frozen=True, slots=True)
class ResearchFreezeAssessment:
    disposition: ResearchFreezeDisposition
    ready_to_freeze: bool
    gate_reachability: GateReachabilityAssessment
    calibrated_detection_rate: float | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["disposition"] = self.disposition.value
        payload["gate_reachability"] = self.gate_reachability.to_dict()
        return payload


def assess_prospective_research_freeze(
    spec: ProspectiveResearchFreezeSpec,
) -> ResearchFreezeAssessment:
    if not spec.name.strip():
        raise ValueError("research freeze name must be nonempty")
    if spec.primary_cost_bps < 0.0:
        raise ValueError("primary_cost_bps cannot be negative")
    if spec.calibration_trials < 0 or spec.calibration_promotions < 0:
        raise ValueError("calibration counts cannot be negative")
    if spec.calibration_promotions > spec.calibration_trials:
        raise ValueError("calibration_promotions cannot exceed calibration_trials")
    if not 0.0 < spec.target_detection_rate <= 1.0:
        raise ValueError("target_detection_rate must be in (0, 1]")
    if spec.protected_outcome_reads < 0:
        raise ValueError("protected_outcome_reads cannot be negative")

    reachability = assess_gate_reachability(spec.gate)
    detection_rate = (
        None
        if spec.calibration_trials == 0
        else spec.calibration_promotions / spec.calibration_trials
    )
    reasons: list[str] = []

    if spec.protected_outcome_reads != 0:
        reasons.append(
            "protected outcomes were opened before the prospective scientific contract was frozen"
        )
        return ResearchFreezeAssessment(
            disposition=ResearchFreezeDisposition.BLOCKED_PROTECTED_CONTAMINATION,
            ready_to_freeze=False,
            gate_reachability=reachability,
            calibrated_detection_rate=detection_rate,
            reasons=tuple(reasons),
        )

    if reachability.disposition is ReachabilityDisposition.UNPASSABLE_ARITHMETIC:
        reasons.extend(reachability.reasons)
        return ResearchFreezeAssessment(
            disposition=ResearchFreezeDisposition.BLOCKED_ARITHMETIC,
            ready_to_freeze=False,
            gate_reachability=reachability,
            calibrated_detection_rate=detection_rate,
            reasons=tuple(reasons),
        )

    if reachability.disposition in {
        ReachabilityDisposition.CAPACITY_UNREACHABLE,
        ReachabilityDisposition.REACHABLE_CAPACITY_UNPROVEN,
    }:
        reasons.extend(reachability.reasons)
        reasons.append(
            "future science may not be frozen until source-only evidence proves the declared sample minima are attainable"
        )
        return ResearchFreezeAssessment(
            disposition=ResearchFreezeDisposition.BLOCKED_CAPACITY,
            ready_to_freeze=False,
            gate_reachability=reachability,
            calibrated_detection_rate=detection_rate,
            reasons=tuple(reasons),
        )

    population = spec.population
    if not population.valid_contract:
        reasons.extend(population.reasons)
        reasons.append("population coverage contract is invalid")
        return ResearchFreezeAssessment(
            disposition=ResearchFreezeDisposition.BLOCKED_POPULATION_EVIDENCE,
            ready_to_freeze=False,
            gate_reachability=reachability,
            calibrated_detection_rate=detection_rate,
            reasons=tuple(reasons),
        )
    if not population.source_scope_proven:
        reasons.extend(population.reasons)
        reasons.append(
            "complete eligible-universe or natural-event source scope is not yet proven"
        )
        return ResearchFreezeAssessment(
            disposition=ResearchFreezeDisposition.BLOCKED_POPULATION_EVIDENCE,
            ready_to_freeze=False,
            gate_reachability=reachability,
            calibrated_detection_rate=detection_rate,
            reasons=tuple(reasons),
        )
    if population.requires_bottleneck_explanation and not (
        spec.bottleneck_explanation and spec.bottleneck_explanation.strip()
    ):
        reasons.append(
            "severe source-to-signal attrition exists but no causal bottleneck explanation is frozen"
        )
        return ResearchFreezeAssessment(
            disposition=ResearchFreezeDisposition.BLOCKED_POPULATION_EVIDENCE,
            ready_to_freeze=False,
            gate_reachability=reachability,
            calibrated_detection_rate=detection_rate,
            reasons=tuple(reasons),
        )

    power_failures: list[str] = []
    if spec.expected_after_cost_edge <= 0.0:
        power_failures.append("expected_after_cost_edge must be positive")
    if not spec.sample_size_rationale.strip():
        power_failures.append("sample-size/effective-sample rationale is missing")
    if spec.calibration_trials < 8:
        power_failures.append(
            "positive-path calibration requires at least 8 deterministic trials before freeze"
        )
    if detection_rate is None or detection_rate < spec.target_detection_rate:
        power_failures.append(
            "calibrated detection rate is below the preregistered target detection rate"
        )
    if power_failures:
        reasons.extend(power_failures)
        return ResearchFreezeAssessment(
            disposition=ResearchFreezeDisposition.BLOCKED_POWER_PLAN,
            ready_to_freeze=False,
            gate_reachability=reachability,
            calibrated_detection_rate=detection_rate,
            reasons=tuple(reasons),
        )

    reasons.extend(
        (
            "gate arithmetic is reachable",
            "source-only capacity satisfies declared minima",
            "complete population source scope is explicit",
            f"mechanism density is preregistered as {spec.mechanism_density.value}",
            "positive after-cost effect target and transaction-cost assumption are explicit",
            "positive-path calibration meets the preregistered detection-rate target",
            "protected outcome reads remain zero",
        )
    )
    if population.requires_bottleneck_explanation:
        reasons.append("severe population attrition has an explicit causal explanation")
    return ResearchFreezeAssessment(
        disposition=ResearchFreezeDisposition.READY_TO_FREEZE,
        ready_to_freeze=True,
        gate_reachability=reachability,
        calibrated_detection_rate=detection_rate,
        reasons=tuple(reasons),
    )
