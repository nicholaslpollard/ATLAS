from packages.core.enums import Timeframe
from packages.features.materialization import PENDING_BENCHMARK_POLICY


def test_phase6_does_not_precommit_full_historical_feature_materialization():
    assert PENDING_BENCHMARK_POLICY.permanently_materialized == ()
    assert PENDING_BENCHMARK_POLICY.current_state_only == (Timeframe.MINUTE_1,)
    assert Timeframe.MINUTE_15 in PENDING_BENCHMARK_POLICY.on_demand_history
    assert Timeframe.HOUR_1 in PENDING_BENCHMARK_POLICY.on_demand_history
    assert Timeframe.HOUR_4 in PENDING_BENCHMARK_POLICY.on_demand_history
    assert Timeframe.DAY_1 in PENDING_BENCHMARK_POLICY.on_demand_history
