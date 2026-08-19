from packages.ml.outcome_probe import (
    ML_MATERIAL_SPLIT_RATIO_CHANGE,
    ML_OUTCOME_FEASIBILITY_PROBE_CONTRACT_VERSION,
    ML_OUTCOME_HORIZONS,
    ML_SPLIT_RESIDUAL_TOLERANCE,
    MLOutcomeFeasibilityProbe,
    _normalized_split,
)


def test_phase10_outcome_probe_contract_is_explicit() -> None:
    assert ML_OUTCOME_FEASIBILITY_PROBE_CONTRACT_VERSION == (
        "ml-outcome-feasibility-probe-v1-contiguous-horizons-provider-split-adjustment-audit"
    )


def test_phase10_outcome_probe_horizon_grid_is_locked_for_evidence() -> None:
    assert ML_OUTCOME_HORIZONS == (1, 3, 5, 10, 20)
    assert ML_MATERIAL_SPLIT_RATIO_CHANGE == 0.20
    assert ML_SPLIT_RESIDUAL_TOLERANCE == 0.15


def test_phase10_outcome_probe_normalizes_provider_split() -> None:
    result = _normalized_split(
        {
            "id": "split-1",
            "ticker": "AAPL",
            "execution_date": "2024-01-02",
            "adjustment_type": "forward_split",
            "split_from": 1,
            "split_to": 4,
            "historical_adjustment_factor": 0.25,
        }
    )
    assert result is not None
    assert result["ticker"] == "AAPL"
    assert str(result["execution_date"]) == "2024-01-02"
    assert result["split_from"] == 1.0
    assert result["split_to"] == 4.0


def test_phase10_outcome_probe_rejects_split_without_identity_or_date() -> None:
    assert _normalized_split({"ticker": "AAPL"}) is None
    assert _normalized_split({"execution_date": "2024-01-02"}) is None
    assert _normalized_split({"ticker": "AAPL", "execution_date": "bad-date"}) is None


def test_phase10_outcome_probe_does_not_require_credentials_at_construction() -> None:
    probe = MLOutcomeFeasibilityProbe(object())
    assert probe.corporate_actions is None
