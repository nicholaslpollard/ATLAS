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
    }
    payload = {
        "contract_version": RESEARCH_GATE_CALIBRATION_CONTRACT_VERSION,
        "pass": all(checks.values()),
        "checks": checks,
        "phase26_reachability": phase26.to_dict(),
        "null_power": null.to_dict(),
        "moderate_power_diagnostic": moderate.to_dict(),
        "strong_power": strong.to_dict(),
        "synthetic_impossible_resolution": impossible_resolution.to_dict(),
        "synthetic_complete_capacity_failure": complete_capacity_failure.to_dict(),
        "synthetic_bounded_probe": bounded_probe.to_dict(),
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
