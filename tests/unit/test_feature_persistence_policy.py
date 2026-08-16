from packages.core.enums import Timeframe
from packages.features.materialization import ACTIVE_FEATURE_PERSISTENCE_POLICY


def test_measured_feature_persistence_tiers_are_disjoint_and_expected():
    policy = ACTIVE_FEATURE_PERSISTENCE_POLICY
    assert policy.tier_for(Timeframe.DAY_1) == "permanent"
    assert policy.tier_for(Timeframe.HOUR_4) == "permanent"
    assert policy.tier_for(Timeframe.HOUR_1) == "permanent"
    assert policy.tier_for(Timeframe.MINUTE_15) == "on_demand"
    assert policy.tier_for(Timeframe.MINUTE_1) == "current_state_only"
    assert policy.benchmark_candidates == ()


def test_policy_cannot_place_a_timeframe_in_multiple_tiers():
    from packages.features.materialization import FeaturePersistencePolicy

    try:
        FeaturePersistencePolicy(
            permanently_materialized=(Timeframe.HOUR_4,),
            current_state_only=(Timeframe.HOUR_4,),
            on_demand_history=(),
            benchmark_candidates=(),
            rationale="invalid",
        )
    except ValueError as exc:
        assert "only one" in str(exc)
    else:
        raise AssertionError("overlapping persistence tiers must be rejected")
