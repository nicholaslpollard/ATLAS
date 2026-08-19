from packages.ml.label_policy_probe import (
    ML_LABEL_POLICY_CANDIDATE_HORIZONS,
    ML_LABEL_POLICY_CANDIDATE_MULTIPLIERS,
    ML_LABEL_POLICY_PRIMARY_CANDIDATE_MULTIPLIER,
    ML_LABEL_POLICY_PROBE_CONTRACT_VERSION,
    stability_range,
)


def test_phase10_gate4_label_policy_probe_grid_is_bounded() -> None:
    assert ML_LABEL_POLICY_PROBE_CONTRACT_VERSION == (
        "ml-label-policy-probe-v1-annual-stability-3-5-10-natr-grid"
    )
    assert ML_LABEL_POLICY_CANDIDATE_HORIZONS == (3, 5, 10)
    assert ML_LABEL_POLICY_CANDIDATE_MULTIPLIERS == (0.5, 1.0)
    assert ML_LABEL_POLICY_PRIMARY_CANDIDATE_MULTIPLIER == 0.5


def test_phase10_gate4_stability_range_is_deterministic() -> None:
    assert stability_range([]) == 0.0
    assert stability_range([0.41, 0.46, 0.43]) == 0.05
