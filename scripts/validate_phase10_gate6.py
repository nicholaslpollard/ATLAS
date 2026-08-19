from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
)
from packages.ml.feature_policy import (
    ML_FEATURE_POLICY_CONTRACT_VERSION,
    ML_MARKET_REGIME_EVALUATION_CONTEXT_ACCEPTED,
    ML_MARKET_REGIME_MODEL_INPUT_ACCEPTED,
    ML_PRODUCTION_CORE_FEATURE_NAMES,
)
from packages.ml.identity_policy import ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION
from packages.ml.label_policy import ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION


def main() -> int:
    assert ML_TRAINING_DATASET_SCHEMA_VERSION == 1
    assert ML_TRAINING_DATASET_CONTRACT_VERSION == (
        "ml-training-dataset-v1-year-partitioned-core33-threeclass-context-lineage"
    )
    assert ML_TRAINING_DATASET_IMMUTABLE is True
    assert ML_TRAINING_DATASET_PARTITIONING == "observation_year"
    assert ML_TRAINING_DATASET_ORDERING == ("session_date", "symbol", "instrument_id")
    assert ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT == (
        "instrument_id|provider_symbol|session_date"
    )
    assert ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE == "EVALUATION_METADATA_ONLY"
    assert len(ML_PRODUCTION_CORE_FEATURE_NAMES) == 33
    assert ML_MARKET_REGIME_EVALUATION_CONTEXT_ACCEPTED is True
    assert ML_MARKET_REGIME_MODEL_INPUT_ACCEPTED is False

    predictors = set(ML_PRODUCTION_CORE_FEATURE_NAMES)
    assert predictors.isdisjoint(ML_TRAINING_DATASET_IDENTITY_COLUMNS)
    assert predictors.isdisjoint(ML_TRAINING_DATASET_OUTCOME_COLUMNS)
    assert predictors.isdisjoint(ML_TRAINING_DATASET_CONTEXT_COLUMNS)

    print(f"ML Gate 6 dataset contract: {ML_TRAINING_DATASET_CONTRACT_VERSION}")
    print(f"ML Gate 6 dataset schema: {ML_TRAINING_DATASET_SCHEMA_VERSION}")
    print(f"ML Gate 6 feature policy: {ML_FEATURE_POLICY_CONTRACT_VERSION}")
    print(f"ML Gate 6 label policy: {ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION}")
    print(f"ML Gate 6 identity policy: {ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION}")
    print(f"ML Gate 6 predictors: {len(ML_PRODUCTION_CORE_FEATURE_NAMES)}")
    print(f"ML Gate 6 partitioning: {ML_TRAINING_DATASET_PARTITIONING}")
    print(f"ML Gate 6 ordering: {ML_TRAINING_DATASET_ORDERING}")
    print(f"ML Gate 6 stable key: {ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT}")
    print(f"ML Gate 6 market context: {ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE}")
    print("ML Gate 6 immutable dataset foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
