from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from packages.ml.historical_backfill_long_history_datasets import (
    GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT,
    GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT,
    GATE11C_B_ROLE,
    GATE11C_COMPOSITE_ROLE,
    GATE11C_EXPECTED_B_CLASSES,
    GATE11C_EXPECTED_B_ROWS,
    GATE11C_EXPECTED_COMPOSITE_CLASSES,
    GATE11C_EXPECTED_COMPOSITE_ROWS,
    GATE11C_EXPECTED_EXTENSION_CLASSES,
    GATE11C_EXPECTED_EXTENSION_ROWS,
    GATE11C_EXTENSION_ROLE,
    GATE11C_FINAL_HOLDOUT_USED_FOR_SELECTION,
    GATE11C_PRODUCTION_MODEL_REPLACEMENT_ALLOWED,
    _dataset_id,
    _path_is_isolated,
    _stable_hash,
)


def test_gate11c_accepted_parent_fingerprints_are_locked_sha256() -> None:
    assert GATE11C_ACCEPTED_GATE11A_SOURCE_FINGERPRINT == (
        "fd1ec38495115a72f16d3a1d53bddfca48b7a2972b25ee502054072564e9ad3a"
    )
    assert GATE11C_ACCEPTED_GATE11B_SOURCE_FINGERPRINT == (
        "3ac4217c34bd0279f67e759d589b58128b31dacf91985decb89af0fe059fbdf9"
    )


def test_gate11c_three_dataset_roles_are_distinct() -> None:
    assert len({GATE11C_B_ROLE, GATE11C_EXTENSION_ROLE, GATE11C_COMPOSITE_ROLE}) == 3


def test_gate11c_composite_accounting_is_exact_sum() -> None:
    assert GATE11C_EXPECTED_COMPOSITE_ROWS == (
        GATE11C_EXPECTED_B_ROWS + GATE11C_EXPECTED_EXTENSION_ROWS
    )
    assert GATE11C_EXPECTED_COMPOSITE_ROWS == 13_397_663
    for label in ("DOWN", "NEUTRAL", "UP"):
        assert GATE11C_EXPECTED_COMPOSITE_CLASSES[label] == (
            GATE11C_EXPECTED_B_CLASSES[label] + GATE11C_EXPECTED_EXTENSION_CLASSES[label]
        )


def test_gate11c_composite_class_counts_reconcile_to_rows() -> None:
    assert sum(GATE11C_EXPECTED_B_CLASSES.values()) == GATE11C_EXPECTED_B_ROWS
    assert sum(GATE11C_EXPECTED_EXTENSION_CLASSES.values()) == GATE11C_EXPECTED_EXTENSION_ROWS
    assert sum(GATE11C_EXPECTED_COMPOSITE_CLASSES.values()) == GATE11C_EXPECTED_COMPOSITE_ROWS


def test_gate11c_dataset_ids_are_lineage_bound() -> None:
    lineage_a = _stable_hash({"role": "B", "source": "a"})
    lineage_b = _stable_hash({"role": "B", "source": "b"})
    first = _dataset_id("b", date(2026, 8, 14), lineage_a)
    second = _dataset_id("b", date(2026, 8, 14), lineage_b)
    assert first.startswith("mlhist-b-2026-08-14-")
    assert first != second
    with pytest.raises(ValueError):
        _dataset_id("b", date(2026, 8, 14), "not-a-sha")


def test_gate11c_isolation_rejects_nested_protected_paths(tmp_path: Path) -> None:
    protected = tmp_path / "derived" / "ml" / "training_datasets"
    candidate = tmp_path / "derived" / "historical_backfill" / "alpaca" / "ml_long_history"
    protected.mkdir(parents=True)
    candidate.mkdir(parents=True)
    assert _path_is_isolated(candidate, protected) is True
    assert _path_is_isolated(protected / "bad", protected) is False
    assert _path_is_isolated(protected, protected / "bad") is False


def test_gate11c_cannot_replace_model_or_use_final_holdout_for_selection() -> None:
    assert GATE11C_PRODUCTION_MODEL_REPLACEMENT_ALLOWED is False
    assert GATE11C_FINAL_HOLDOUT_USED_FOR_SELECTION is False
