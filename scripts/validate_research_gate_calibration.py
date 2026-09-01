from __future__ import annotations

import json

from packages.backtesting.research_gate_calibration import (
    RESEARCH_GATE_CALIBRATION_CONTRACT_VERSION,
    GateCapacityEvidence,
    GateReachabilitySpec,
    ReachabilityDisposition,
    assess_gate_reachability,
    phase26_selection_reachability,
    phase26_synthetic_power,
)
from packages.backtesting.research_gate_freeze import (
    RESEARCH_GATE_FREEZE_CONTRACT_VERSION,
    MechanismDensity,
    ProspectiveResearchFreezeSpec,
    ResearchFreezeDisposition,
    assess_prospective_research_freeze,
)
from packages.backtesting.research_population_coverage import (
    RESEARCH_POPULATION_COVERAGE_CONTRACT_VERSION,
    PopulationCoverageStage,
    PopulationScope,
    assess_population_coverage,
)


def main() -> int:
    seeds = tuple(range(8))
    phase26 = phase26_selection_reachability()
    null = phase26_synthetic_power(
        gross_edge=0.0,
        volatility=0.012,
        seeds=(1000 + seed for seed in seeds),
    )
    moderate = phase26_synthetic_power(
        gross_edge=0.0035,
        volatility=0.012,
        seeds=(3000 + seed for seed in seeds),
    )
    strong = phase26_synthetic_power(
        gross_edge=0.006,
        volatility=0.008,
        seeds=(2000 + seed for seed in seeds),
    )

    impossible_resolution = assess_gate_reachability(
        GateReachabilitySpec(
            name="synthetic_impossible_resolution",
            candidate_count=100,
            family_alpha=0.01,
            empirical_replicates=99,
            min_rows=100,
            min_sessions=20,
        )
    )
    complete_capacity_failure = assess_gate_reachability(
        GateReachabilitySpec(
            name="synthetic_complete_capacity_failure",
            candidate_count=4,
            family_alpha=0.05,
            empirical_replicates=2000,
            min_rows=300,
            min_sessions=16,
            min_instruments=200,
            capacity=GateCapacityEvidence(
                rows=257,
                sessions=26,
                instruments=211,
                is_upper_bound=True,
                source="complete_source_only_census",
            ),
        )
    )
    bounded_probe = assess_gate_reachability(
        GateReachabilitySpec(
            name="synthetic_bounded_probe",
            candidate_count=5,
            family_alpha=0.05,
            empirical_replicates=2000,
            min_rows=500,
            min_sessions=250,
            min_instruments=20,
            capacity=GateCapacityEvidence(
                rows=46,
                sessions=33,
                instruments=40,
                is_upper_bound=False,
                source="bounded_probe_window",
            ),
        )
    )

    broad_universe_funnel = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="eligible_universe",
                rows=1_000_000,
                sessions=250,
                instruments=5_000,
                scope=PopulationScope.FULL_ELIGIBLE_UNIVERSE,
            ),
            PopulationCoverageStage(
                name="discovery_population",
                rows=20_000,
                sessions=250,
                instruments=1_200,
                scope=PopulationScope.FILTERED_POPULATION,
            ),
            PopulationCoverageStage(
                name="route_eligible",
                rows=12_000,
                sessions=240,
                instruments=900,
                scope=PopulationScope.FILTERED_POPULATION,
            ),
        )
    )
    probe_funnel = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="source_probe",
                rows=500,
                sessions=5,
                instruments=300,
                scope=PopulationScope.PROBE_ONLY,
                complete_scope=False,
            ),
            PopulationCoverageStage(
                name="probe_signals",
                rows=100,
                sessions=5,
                instruments=80,
                scope=PopulationScope.FILTERED_POPULATION,
                complete_scope=False,
            ),
        )
    )
    invalid_expansion = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="eligible",
                rows=100,
                scope=PopulationScope.FULL_ELIGIBLE_UNIVERSE,
            ),
            PopulationCoverageStage(
                name="filtered",
                rows=120,
                scope=PopulationScope.FILTERED_POPULATION,
            ),
        )
    )

    freeze_gate = GateReachabilitySpec(
        name="synthetic_future_sparse_event_alpha",
        candidate_count=4,
        family_alpha=0.05,
        empirical_replicates=2_000,
        min_rows=750,
        min_sessions=250,
        min_instruments=100,
        capacity=GateCapacityEvidence(
            rows=2_500,
            sessions=500,
            instruments=700,
            is_upper_bound=True,
            source="complete_source_only_census",
        ),
    )
    complete_event_source = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="complete_event_source",
                rows=10_000,
                sessions=500,
                instruments=1_000,
                scope=PopulationScope.NATURAL_EVENT_SOURCE,
                complete_scope=True,
                source="point_in_time_source_census",
            ),
        )
    )
    prospective_ready = assess_prospective_research_freeze(
        ProspectiveResearchFreezeSpec(
            name="synthetic_future_sparse_event_alpha",
            gate=freeze_gate,
            population=complete_event_source,
            mechanism_density=MechanismDensity.SPARSE_EVENT,
            expected_after_cost_edge=0.003,
            primary_cost_bps=10.0,
            calibration_trials=10,
            calibration_promotions=9,
            target_detection_rate=0.80,
            sample_size_rationale=(
                "Effective sample and session floors are calibrated for the sparse event mechanism."
            ),
            protected_outcome_reads=0,
        )
    )
    prospective_probe_block = assess_prospective_research_freeze(
        ProspectiveResearchFreezeSpec(
            name="synthetic_probe_must_not_freeze",
            gate=freeze_gate,
            population=probe_funnel,
            mechanism_density=MechanismDensity.SPARSE_EVENT,
            expected_after_cost_edge=0.003,
            primary_cost_bps=10.0,
            calibration_trials=10,
            calibration_promotions=9,
            target_detection_rate=0.80,
            sample_size_rationale="Probe-only source coverage is deliberately insufficient for freeze.",
            protected_outcome_reads=0,
        )
    )
    prospective_underpowered = assess_prospective_research_freeze(
        ProspectiveResearchFreezeSpec(
            name="synthetic_underpowered_future_alpha",
            gate=freeze_gate,
            population=complete_event_source,
            mechanism_density=MechanismDensity.SPARSE_EVENT,
            expected_after_cost_edge=0.003,
            primary_cost_bps=10.0,
            calibration_trials=10,
            calibration_promotions=6,
            target_detection_rate=0.80,
            sample_size_rationale=(
                "This intentionally weak calibration demonstrates a freeze-time power failure."
            ),
            protected_outcome_reads=0,
        )
    )

    checks = {
        "phase26_arithmetic_passable": phase26.arithmetic_passable,
        "phase26_null_rejected": null.promotions == 0,
        "phase26_strong_edge_detected_all_trials": strong.promotions == strong.trials,
        "impossible_resolution_detected": (
            impossible_resolution.disposition
            is ReachabilityDisposition.UNPASSABLE_ARITHMETIC
        ),
        "complete_capacity_failure_detected": (
            complete_capacity_failure.disposition
            is ReachabilityDisposition.CAPACITY_UNREACHABLE
        ),
        "bounded_probe_not_mislabeled_impossible": (
            bounded_probe.disposition
            is ReachabilityDisposition.REACHABLE_CAPACITY_UNPROVEN
        ),
        "full_universe_scope_proven": broad_universe_funnel.source_scope_proven,
        "severe_population_narrowing_is_visible": (
            broad_universe_funnel.requires_bottleneck_explanation
            and broad_universe_funnel.bottleneck_stages == ("discovery_population",)
        ),
        "probe_cannot_claim_full_coverage": (
            probe_funnel.valid_contract and not probe_funnel.source_scope_proven
        ),
        "same_grain_population_expansion_rejected": not invalid_expansion.valid_contract,
        "prospective_complete_powered_gate_can_freeze": (
            prospective_ready.disposition is ResearchFreezeDisposition.READY_TO_FREEZE
        ),
        "prospective_probe_is_blocked_before_freeze": (
            prospective_probe_block.disposition
            is ResearchFreezeDisposition.BLOCKED_POPULATION_EVIDENCE
        ),
        "prospective_underpowered_gate_is_blocked": (
            prospective_underpowered.disposition
            is ResearchFreezeDisposition.BLOCKED_POWER_PLAN
        ),
    }
    payload = {
        "contract_version": RESEARCH_GATE_CALIBRATION_CONTRACT_VERSION,
        "population_coverage_contract_version": RESEARCH_POPULATION_COVERAGE_CONTRACT_VERSION,
        "prospective_freeze_contract_version": RESEARCH_GATE_FREEZE_CONTRACT_VERSION,
        "pass": all(checks.values()),
        "checks": checks,
        "phase26_reachability": phase26.to_dict(),
        "null_power": null.to_dict(),
        "moderate_power_diagnostic": moderate.to_dict(),
        "strong_power": strong.to_dict(),
        "synthetic_impossible_resolution": impossible_resolution.to_dict(),
        "synthetic_complete_capacity_failure": complete_capacity_failure.to_dict(),
        "synthetic_bounded_probe": bounded_probe.to_dict(),
        "synthetic_full_universe_funnel": broad_universe_funnel.to_dict(),
        "synthetic_probe_funnel": probe_funnel.to_dict(),
        "synthetic_invalid_expansion": invalid_expansion.to_dict(),
        "synthetic_prospective_ready": prospective_ready.to_dict(),
        "synthetic_prospective_probe_block": prospective_probe_block.to_dict(),
        "synthetic_prospective_underpowered": prospective_underpowered.to_dict(),
        "protected_outcome_reads": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_writes": 0,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        raise SystemExit("research gate calibration failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
