from __future__ import annotations

from pathlib import Path

import pytest

from packages.ml.historical_backfill_long_history_dataset_validation import (
    GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT,
    Gate11CDatasetValidationError,
    checkpoint_lineage,
    expected_dataset_columns,
    recompute_builder_fingerprint,
    safe_relative,
    stable_hash,
)
from packages.ml.historical_backfill_long_history_datasets import (
    GATE11C_B_ROLE,
    GATE11C_EXPECTED_B_CLASSES,
    GATE11C_EXPECTED_B_ROWS,
    GATE11C_EXPECTED_COMPOSITE_CLASSES,
    GATE11C_EXPECTED_COMPOSITE_ROWS,
    GATE11C_EXPECTED_EXTENSION_CLASSES,
    GATE11C_EXPECTED_EXTENSION_ROWS,
    GATE11C_EXTENSION_ROLE,
)
from packages.ml.feature_policy import ML_PRODUCTION_CORE_FEATURE_NAMES
from packages.ml.datasets import ML_TRAINING_DATASET_CONTEXT_COLUMNS


def test_gate11c_expected_totals_reconcile() -> None:
    assert GATE11C_EXPECTED_COMPOSITE_ROWS == GATE11C_EXPECTED_B_ROWS + GATE11C_EXPECTED_EXTENSION_ROWS
    assert GATE11C_EXPECTED_COMPOSITE_CLASSES == {
        label: GATE11C_EXPECTED_B_CLASSES[label] + GATE11C_EXPECTED_EXTENSION_CLASSES[label]
        for label in GATE11C_EXPECTED_COMPOSITE_CLASSES
    }


def test_gate11c_validation_accepted_builder_fingerprint_is_sha256() -> None:
    assert len(GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT) == 64
    int(GATE11C_ACCEPTED_BUILDER_SOURCE_FINGERPRINT, 16)


def test_safe_relative_accepts_child_and_rejects_escape(tmp_path: Path) -> None:
    assert safe_relative(tmp_path, "year=2021/part-000.parquet") == (
        tmp_path / "year=2021" / "part-000.parquet"
    ).resolve()
    with pytest.raises(Gate11CDatasetValidationError):
        safe_relative(tmp_path, "../escape.parquet")
    with pytest.raises(Gate11CDatasetValidationError):
        safe_relative(tmp_path, str((tmp_path.parent / "absolute.parquet").resolve()))


def test_checkpoint_lineage_binds_dataset_role_and_year() -> None:
    lineage = "a" * 64
    base = checkpoint_lineage(dataset_lineage=lineage, role=GATE11C_B_ROLE, year=2021)
    assert base == checkpoint_lineage(dataset_lineage=lineage, role=GATE11C_B_ROLE, year=2021)
    assert base != checkpoint_lineage(dataset_lineage=lineage, role=GATE11C_EXTENSION_ROLE, year=2021)
    assert base != checkpoint_lineage(dataset_lineage=lineage, role=GATE11C_B_ROLE, year=2022)


def test_expected_dataset_columns_keep_context_out_of_predictors() -> None:
    columns = expected_dataset_columns()
    assert len(columns) == len(set(columns))
    assert set(ML_PRODUCTION_CORE_FEATURE_NAMES).issubset(columns)
    assert set(ML_TRAINING_DATASET_CONTEXT_COLUMNS).issubset(columns)
    assert not set(ML_TRAINING_DATASET_CONTEXT_COLUMNS).intersection(ML_PRODUCTION_CORE_FEATURE_NAMES)


def test_stable_hash_is_order_independent_for_mapping_keys() -> None:
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
    assert stable_hash({"a": 1, "b": 2}) != stable_hash({"a": 1, "b": 3})


def test_recompute_builder_fingerprint_binds_partition_hashes() -> None:
    b = {
        "dataset_id": "b",
        "dataset_lineage_fingerprint": "1" * 64,
        "row_count": GATE11C_EXPECTED_B_ROWS,
        "class_row_counts": GATE11C_EXPECTED_B_CLASSES,
        "partitions": [{"sha256": "a" * 64}],
    }
    x = {
        "dataset_id": "x",
        "dataset_lineage_fingerprint": "2" * 64,
        "row_count": GATE11C_EXPECTED_EXTENSION_ROWS,
        "class_row_counts": GATE11C_EXPECTED_EXTENSION_CLASSES,
        "partitions": [{"sha256": "b" * 64}],
    }
    c = {
        "dataset_id": "c",
        "dataset_lineage_fingerprint": "3" * 64,
        "row_count": GATE11C_EXPECTED_COMPOSITE_ROWS,
        "class_row_counts": GATE11C_EXPECTED_COMPOSITE_CLASSES,
    }
    accepted = {"dataset_manifest_sha256": "c" * 64, "final_report_sha256": "d" * 64}
    first = recompute_builder_fingerprint(
        b_manifest=b,
        extension_manifest=x,
        composite_manifest=c,
        market_context_sha256="e" * 64,
        accepted_phase10=accepted,
    )
    b["partitions"] = [{"sha256": "f" * 64}]
    second = recompute_builder_fingerprint(
        b_manifest=b,
        extension_manifest=x,
        composite_manifest=c,
        market_context_sha256="e" * 64,
        accepted_phase10=accepted,
    )
    assert first != second
