from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.feature_leakage_audit import (
    ML_ALLOWED_CORE_RAW_DEPENDENCIES,
    ML_FEATURE_LEAKAGE_AUDIT_CONTRACT_VERSION,
    ML_FEATURE_PARQUET_READ_MODE_GATE5,
    ML_MARKET_REGIME_CANDIDATE_FIELDS,
    ML_OBSERVATION_AVAILABILITY_RULE,
    ML_PROHIBITED_MODEL_INPUT_FIELDS,
    core_registry_dependencies_are_point_in_time_safe,
)


def test_phase10_gate5_feature_audit_contract_is_explicit() -> None:
    assert ML_FEATURE_LEAKAGE_AUDIT_CONTRACT_VERSION == (
        "ml-feature-leakage-audit-v1-core33-postclose-market-regime-availability"
    )
    assert ML_FEATURE_PARQUET_READ_MODE_GATE5 == "union_by_name"
    assert ML_OBSERVATION_AVAILABILITY_RULE == (
        "POST_SESSION_CLOSE_AFTER_DAILY_FEATURE_MATERIALIZATION"
    )


def test_phase10_gate5_core_registry_dependencies_are_point_in_time_raw_inputs() -> None:
    assert len(CORE_FEATURE_REGISTRY.all()) == 33
    assert ML_ALLOWED_CORE_RAW_DEPENDENCIES == frozenset({"high", "low", "close", "volume"})
    assert core_registry_dependencies_are_point_in_time_safe() is True


def test_phase10_gate5_context_and_prohibited_fields_are_bounded() -> None:
    assert ML_MARKET_REGIME_CANDIDATE_FIELDS == (
        "composite",
        "structure",
        "momentum",
        "volatility",
        "efficiency",
        "participation",
    )
    assert set(ML_PROHIBITED_MODEL_INPUT_FIELDS).isdisjoint(
        definition.name for definition in CORE_FEATURE_REGISTRY.all()
    )
