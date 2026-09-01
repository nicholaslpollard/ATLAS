from packages.backtesting.research_gate_calibration import (
    GateCapacityEvidence,
    GateReachabilitySpec,
    ReachabilityDisposition,
    assess_gate_reachability,
    phase26_selection_reachability,
    phase26_synthetic_power,
)


def test_phase26_holm_is_arithmetically_reachable() -> None:
    result = phase26_selection_reachability()
    assert result.arithmetic_passable is True
    assert result.empirical_p_value_floor < result.strictest_holm_threshold
    assert result.disposition is ReachabilityDisposition.REACHABLE_CAPACITY_UNPROVEN


def test_reachability_detects_impossible_empirical_p_value_resolution() -> None:
    result = assess_gate_reachability(
        GateReachabilitySpec(
            name="impossible_resolution",
            candidate_count=100,
            family_alpha=0.01,
            empirical_replicates=99,
            min_rows=100,
            min_sessions=20,
        )
    )
    assert result.disposition is ReachabilityDisposition.UNPASSABLE_ARITHMETIC
    assert result.arithmetic_passable is False


def test_reachability_detects_declared_capacity_upper_bound_below_gate() -> None:
    result = assess_gate_reachability(
        GateReachabilitySpec(
            name="sparse_event_gate",
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
    assert result.disposition is ReachabilityDisposition.CAPACITY_UNREACHABLE
    assert result.capacity_passable is False


def test_probe_below_minimum_is_not_mislabeled_impossible() -> None:
    result = assess_gate_reachability(
        GateReachabilitySpec(
            name="probe_only",
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
    assert result.disposition is ReachabilityDisposition.REACHABLE_CAPACITY_UNPROVEN
    assert result.capacity_passable is None


def test_phase26_real_gate_rejects_null_synthetic_evidence() -> None:
    result = phase26_synthetic_power(
        gross_edge=0.0,
        volatility=0.012,
        seeds=range(1000, 1008),
    )
    assert result.promotions == 0
    assert result.promotion_rate == 0.0


def test_phase26_real_gate_accepts_strong_synthetic_edge() -> None:
    result = phase26_synthetic_power(
        gross_edge=0.006,
        volatility=0.008,
        seeds=range(2000, 2008),
    )
    assert result.promotions == result.trials
    assert result.promotion_rate == 1.0


def test_phase26_moderate_edge_power_is_measurable_without_becoming_a_gate() -> None:
    result = phase26_synthetic_power(
        gross_edge=0.0035,
        volatility=0.012,
        seeds=range(3000, 3008),
    )
    assert result.trials == 8
    assert 0 <= result.promotions <= result.trials
    assert 0.0 <= result.promotion_rate <= 1.0
