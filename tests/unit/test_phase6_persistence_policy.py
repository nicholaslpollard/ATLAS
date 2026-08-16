from packages.core.enums import Timeframe
from packages.features.materialization import ACTIVE_FEATURE_PERSISTENCE_POLICY


def test_phase6_uses_target_machine_measured_persistence_policy():
    policy = ACTIVE_FEATURE_PERSISTENCE_POLICY
    assert policy.permanently_materialized == (Timeframe.DAY_1, Timeframe.HOUR_4)
    assert policy.current_state_only == (Timeframe.MINUTE_1,)
    assert policy.on_demand_history == (Timeframe.MINUTE_15,)
    assert policy.benchmark_candidates == (Timeframe.HOUR_1,)
