from __future__ import annotations

from packages.backtesting.research_gate_calibration import (
    GateCapacityEvidence,
    GateReachabilitySpec,
)
from packages.backtesting.research_gate_freeze import (
    MechanismDensity,
    ProspectiveResearchFreezeSpec,
    ResearchFreezeDisposition,
    assess_prospective_research_freeze,
)
from packages.backtesting.research_population_coverage import (
    PopulationCoverageStage,
    PopulationScope,
    assess_population_coverage,
)


def _gate(*, capacity: GateCapacityEvidence | None = None, empirical_replicates: int = 2_000):
    return GateReachabilitySpec(
        name="future_alpha",
        candidate_count=4,
        family_alpha=0.05,
        empirical_replicates=empirical_replicates,
        min_rows=750,
        min_sessions=250,
        min_instruments=100,
        capacity=capacity,
    )


def _capacity() -> GateCapacityEvidence:
    return GateCapacityEvidence(
        rows=2_500,
        sessions=500,
        instruments=700,
        is_upper_bound=True,
        source="complete_source_only_census",
    )


def _complete_population(*, bottleneck: bool = False):
    stages = [
        PopulationCoverageStage(
            name="complete_event_source",
            rows=10_000,
            sessions=500,
            instruments=1_000,
            scope=PopulationScope.NATURAL_EVENT_SOURCE,
            complete_scope=True,
            source="point_in_time_source_census",
        )
    ]
    if bottleneck:
        stages.append(
            PopulationCoverageStage(
                name="mechanism_complete_case",
                rows=400,
                sessions=300,
                instruments=250,
                scope=PopulationScope.FILTERED_POPULATION,
                complete_scope=True,
                source="deterministic_filter",
            )
        )
    return assess_population_coverage(tuple(stages))


def _spec(**overrides):
    payload = {
        "name": "future_sparse_event_alpha",
        "gate": _gate(capacity=_capacity()),
        "population": _complete_population(),
        "mechanism_density": MechanismDensity.SPARSE_EVENT,
        "expected_after_cost_edge": 0.003,
        "primary_cost_bps": 10.0,
        "calibration_trials": 10,
        "calibration_promotions": 9,
        "target_detection_rate": 0.80,
        "sample_size_rationale": "Effective sample and session floors are calibrated for a sparse event mechanism.",
        "protected_outcome_reads": 0,
    }
    payload.update(overrides)
    return ProspectiveResearchFreezeSpec(**payload)


def test_future_gate_can_be_ready_to_freeze() -> None:
    result = assess_prospective_research_freeze(_spec())
    assert result.ready_to_freeze is True
    assert result.disposition is ResearchFreezeDisposition.READY_TO_FREEZE
    assert result.calibrated_detection_rate == 0.9


def test_impossible_p_value_math_blocks_freeze() -> None:
    result = assess_prospective_research_freeze(
        _spec(gate=_gate(capacity=_capacity(), empirical_replicates=19))
    )
    assert result.ready_to_freeze is False
    assert result.disposition is ResearchFreezeDisposition.BLOCKED_ARITHMETIC


def test_unproven_or_insufficient_capacity_blocks_freeze() -> None:
    unproven = assess_prospective_research_freeze(_spec(gate=_gate(capacity=None)))
    assert unproven.disposition is ResearchFreezeDisposition.BLOCKED_CAPACITY

    insufficient = assess_prospective_research_freeze(
        _spec(
            gate=_gate(
                capacity=GateCapacityEvidence(
                    rows=500,
                    sessions=300,
                    instruments=200,
                    is_upper_bound=True,
                    source="complete_source_only_census",
                )
            )
        )
    )
    assert insufficient.disposition is ResearchFreezeDisposition.BLOCKED_CAPACITY


def test_probe_cannot_masquerade_as_complete_population_at_freeze() -> None:
    probe = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="probe",
                rows=1_000,
                sessions=20,
                instruments=800,
                scope=PopulationScope.PROBE_ONLY,
                complete_scope=False,
                source="bounded_probe",
            ),
        )
    )
    result = assess_prospective_research_freeze(_spec(population=probe))
    assert result.disposition is ResearchFreezeDisposition.BLOCKED_POPULATION_EVIDENCE


def test_severe_attrition_requires_explanation_but_is_not_automatically_rejected() -> None:
    population = _complete_population(bottleneck=True)
    assert population.requires_bottleneck_explanation is True

    unexplained = assess_prospective_research_freeze(_spec(population=population))
    assert unexplained.disposition is ResearchFreezeDisposition.BLOCKED_POPULATION_EVIDENCE

    explained = assess_prospective_research_freeze(
        _spec(
            population=population,
            bottleneck_explanation=(
                "The preregistered event definition and point-in-time production-path intersection "
                "deterministically remove noncomparable source events."
            ),
        )
    )
    assert explained.disposition is ResearchFreezeDisposition.READY_TO_FREEZE


def test_power_plan_must_detect_the_effect_it_claims_to_target() -> None:
    weak = assess_prospective_research_freeze(
        _spec(calibration_trials=10, calibration_promotions=6, target_detection_rate=0.80)
    )
    assert weak.disposition is ResearchFreezeDisposition.BLOCKED_POWER_PLAN

    too_few_trials = assess_prospective_research_freeze(
        _spec(calibration_trials=4, calibration_promotions=4, target_detection_rate=0.80)
    )
    assert too_few_trials.disposition is ResearchFreezeDisposition.BLOCKED_POWER_PLAN


def test_protected_outcome_read_before_freeze_fails_closed() -> None:
    result = assess_prospective_research_freeze(_spec(protected_outcome_reads=1))
    assert result.disposition is ResearchFreezeDisposition.BLOCKED_PROTECTED_CONTAMINATION
