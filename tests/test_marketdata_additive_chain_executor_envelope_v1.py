from packages.data.marketdata_candidate_batch_plan_v1 import MAX_CHAIN_GROUPS


def test_additive_group_capacity():
    assert MAX_CHAIN_GROUPS >= 40
