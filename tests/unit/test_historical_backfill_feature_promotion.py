from __future__ import annotations

from pathlib import Path

import pytest

from packages.features.historical_backfill_feature_promotion import (
    COPY_NEW,
    FAIL_UNMANAGED_TARGET,
    REPLACE_PROTECTED_BASELINE,
    REUSE_EXACT,
    feature_inventory_fingerprint,
    feature_promotion_action,
    feature_promotion_source_fingerprint,
    rollback_feature_path,
)


def _row(session: str, *, feature_sha: str = "feature") -> dict[str, object]:
    return {
        "session_date": session,
        "feature_sha256": feature_sha,
        "source_sha256": "source",
        "manifest_sha256": "manifest",
        "row_count": 10,
        "symbol_count": 5,
    }


def test_gate9c_action_copies_missing_target() -> None:
    assert (
        feature_promotion_action(
            target_exists=False,
            target_in_locked_baseline=False,
            target_sha256=None,
            candidate_sha256="candidate",
        )
        == COPY_NEW
    )


def test_gate9c_action_reuses_exact_target_even_when_baselined() -> None:
    assert (
        feature_promotion_action(
            target_exists=True,
            target_in_locked_baseline=True,
            target_sha256="same",
            candidate_sha256="same",
        )
        == REUSE_EXACT
    )


def test_gate9c_action_replaces_only_locked_baseline_difference() -> None:
    assert (
        feature_promotion_action(
            target_exists=True,
            target_in_locked_baseline=True,
            target_sha256="old",
            candidate_sha256="new",
        )
        == REPLACE_PROTECTED_BASELINE
    )
    assert (
        feature_promotion_action(
            target_exists=True,
            target_in_locked_baseline=False,
            target_sha256="old",
            candidate_sha256="new",
        )
        == FAIL_UNMANAGED_TARGET
    )


def test_gate9c_candidate_inventory_fingerprint_is_order_independent_and_content_bound() -> None:
    first = _row("2021-08-13", feature_sha="a")
    second = _row("2021-08-16", feature_sha="b")
    assert feature_inventory_fingerprint([first, second]) == feature_inventory_fingerprint(
        [second, first]
    )
    changed = dict(second)
    changed["feature_sha256"] = "changed"
    assert feature_inventory_fingerprint([first, second]) != feature_inventory_fingerprint(
        [first, changed]
    )


def test_gate9c_source_fingerprint_binds_candidate_baseline_and_state() -> None:
    values = {
        "replay_source_fingerprint": "replay",
        "candidate_inventory_fingerprint": "candidate",
        "production_baseline_fingerprint": "baseline",
        "candidate_current_state_sha256": "state-sha",
        "candidate_current_state_fingerprint": "state-fingerprint",
        "candidate_year_checkpoint_fingerprint": "year-checkpoints",
    }
    baseline = feature_promotion_source_fingerprint(**values)
    assert len(baseline) == 64
    for field in values:
        changed = dict(values)
        changed[field] = f"changed-{field}"
        assert feature_promotion_source_fingerprint(**changed) != baseline


def test_gate9c_rollback_feature_path_uses_frozen_relative_path(tmp_path: Path) -> None:
    row = {"relative_path": "features/1d/year=2021/month=08/date=2021-08-16/part-000.parquet"}
    assert rollback_feature_path(derived_root=tmp_path, baseline_row=row) == (
        tmp_path / "features/1d/year=2021/month=08/date=2021-08-16/part-000.parquet"
    )


def test_gate9c_rollback_feature_path_rejects_missing_or_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="lacks relative_path"):
        rollback_feature_path(derived_root=tmp_path, baseline_row={})
    with pytest.raises(ValueError, match="must be relative"):
        rollback_feature_path(
            derived_root=tmp_path,
            baseline_row={"relative_path": str((tmp_path / "escape.parquet").resolve())},
        )