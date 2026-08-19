from datetime import date

import pytest

from packages.ml.datasets import (
    ML_TRAINING_DATASET_CONTEXT_COLUMNS,
    ML_TRAINING_DATASET_CONTRACT_VERSION,
    ML_TRAINING_DATASET_IDENTITY_COLUMNS,
    ML_TRAINING_DATASET_IMMUTABLE,
    ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE,
    ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
    ML_TRAINING_DATASET_ORDERING,
    ML_TRAINING_DATASET_OUTCOME_COLUMNS,
    ML_TRAINING_DATASET_PARTITIONING,
    ML_TRAINING_DATASET_SCHEMA_VERSION,
    stable_observation_key,
    training_dataset_id,
    training_dataset_lineage_fingerprint,
)
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES


def test_phase10_gate6_dataset_contract_separates_column_roles() -> None:
    assert ML_TRAINING_DATASET_SCHEMA_VERSION == 1
    assert ML_TRAINING_DATASET_CONTRACT_VERSION == (
        "ml-training-dataset-v1-year-partitioned-core33-threeclass-context-lineage"
    )
    assert ML_TRAINING_DATASET_IMMUTABLE is True
    assert ML_TRAINING_DATASET_PARTITIONING == "observation_year"
    assert ML_TRAINING_DATASET_ORDERING == ("session_date", "symbol", "instrument_id")
    assert ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE == "EVALUATION_METADATA_ONLY"
    assert len(ML_PRODUCTION_CORE_FEATURE_NAMES) == 33
    predictors = set(ML_PRODUCTION_CORE_FEATURE_NAMES)
    assert predictors.isdisjoint(ML_TRAINING_DATASET_IDENTITY_COLUMNS)
    assert predictors.isdisjoint(ML_TRAINING_DATASET_OUTCOME_COLUMNS)
    assert predictors.isdisjoint(ML_TRAINING_DATASET_CONTEXT_COLUMNS)


def test_phase10_gate6_observation_key_is_deterministic_and_provider_native() -> None:
    assert ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT == (
        "instrument_id|provider_symbol|session_date"
    )
    key = stable_observation_key(
        instrument_id="figi:BBG000B9XRY4",
        symbol="BRK.B",
        session_date=date(2026, 8, 14),
    )
    assert key == "figi:BBG000B9XRY4|BRK.B|2026-08-14"
    assert stable_observation_key(
        instrument_id="figi:BBG000B9XRY4",
        symbol="BRK.B",
        session_date="2026-08-14",
    ) == key


def test_phase10_gate6_observation_key_rejects_missing_identity() -> None:
    with pytest.raises(ValueError, match="instrument_id"):
        stable_observation_key(
            instrument_id="",
            symbol="AAPL",
            session_date="2026-08-14",
        )


def test_phase10_gate6_lineage_and_dataset_id_are_deterministic() -> None:
    first = training_dataset_lineage_fingerprint({"b": 2, "a": [1, 2, 3]})
    second = training_dataset_lineage_fingerprint({"a": [1, 2, 3], "b": 2})
    changed = training_dataset_lineage_fingerprint({"a": [1, 2, 4], "b": 2})
    assert first == second
    assert first != changed
    dataset_id = training_dataset_id(
        end_date=date(2026, 8, 14),
        lineage_fingerprint=first,
    )
    assert dataset_id == f"mltrain-2026-08-14-{first[:16]}"
