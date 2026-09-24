from packages.data import marketdata_massive_sparse_activity_v2 as v2


def test_v2_sample_is_disjoint() -> None:
    roots = {a["root"] for a in v2.CONTRACT["anchors"]}
    dates = {a["date"] for a in v2.CONTRACT["anchors"]}
    assert len(roots) == 12
    assert len(dates) == 12
    assert roots.isdisjoint(set(v2.CONTRACT["excluded_prior_roots"]))
    assert dates.isdisjoint(set(v2.CONTRACT["excluded_prior_dates"]))


def test_selector_is_third_farthest_otm_and_ignores_volume() -> None:
    rows = (
        {"side": "call", "optionSymbol": "A", "strike": 105, "underlyingPrice": 100, "volume": 0},
        {"side": "call", "optionSymbol": "B", "strike": 130, "underlyingPrice": 100, "volume": 0},
        {"side": "call", "optionSymbol": "C", "strike": 120, "underlyingPrice": 100, "volume": 999},
        {"side": "call", "optionSymbol": "D", "strike": 110, "underlyingPrice": 100, "volume": 1},
        {"side": "call", "optionSymbol": "E", "strike": 125, "underlyingPrice": 100, "volume": 5},
    )
    selected = v2._choose_third_farthest_otm(rows)
    assert selected is not None
    assert selected["optionSymbol"] == "C"


def test_thresholds_preserve_v1_support_requirements() -> None:
    t = v2.CONTRACT["preregistered_thresholds"]
    assert t["minimum_total_zero_volume_sessions"] == 10
    assert t["minimum_zero_volume_anchor_count"] == 3
    assert t["minimum_total_positive_volume_sessions"] == 20
    assert t["minimum_positive_volume_anchor_count"] == 3
    assert t["required_activity_concordance_rate"] == 1.0


def test_v2_cannot_grant_price_authority() -> None:
    a = v2.CONTRACT["authority_if_passed"]
    assert a["marketdata_massive_sparse_activity_concordance_confirmed"] is True
    assert a["marketdata_zero_volume_last_validated"] is False
    assert a["marketdata_positive_volume_eod_last_volume_semantics_validated"] is False
    assert a["execution_price_authority"] is False
