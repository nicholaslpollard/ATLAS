from __future__ import annotations

from pathlib import Path

import pytest

from packages.features.historical_backfill_feature_handoff import Gate9FeatureHandoffError
from packages.features.historical_backfill_feature_handoff_runtime import (
    HistoricalBackfillDailyFeatureHandoffRuntime,
)


def test_gate9c_runtime_moves_directory_atomically_on_same_filesystem(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    (source / "proof.txt").write_text("proof", encoding="utf-8")

    HistoricalBackfillDailyFeatureHandoffRuntime._move_with_retry(source, target)

    assert not source.exists()
    assert (target / "proof.txt").read_text(encoding="utf-8") == "proof"


def test_gate9c_runtime_refuses_to_replace_existing_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()

    with pytest.raises(Gate9FeatureHandoffError, match="target already exists"):
        HistoricalBackfillDailyFeatureHandoffRuntime._move_with_retry(source, target)

    assert source.is_dir()
    assert target.is_dir()
