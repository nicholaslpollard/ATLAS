from __future__ import annotations

from pathlib import Path

from packages.features.historical_backfill_feature_handoff import (
    COMPONENT_MANIFESTS,
    STATE_INITIAL,
    STATE_INVALID,
    STATE_OLD_MOVED,
    STATE_PROMOTED,
    _inventory,
    component_disk_state,
    handoff_source_fingerprint,
    inventory_fingerprint,
)
from packages.features.historical_backfill_feature_handoff_runtime import (
    HistoricalBackfillDailyFeatureHandoffRuntime,
)


def test_gate9c_component_state_initial() -> None:
    assert (
        component_disk_state(
            live_matches_old=True,
            live_matches_new=False,
            live_missing=False,
            rollback_matches_old=False,
            rollback_missing=True,
            source_matches_new=True,
            source_missing=False,
        )
        == STATE_INITIAL
    )


def test_gate9c_component_state_old_moved() -> None:
    assert (
        component_disk_state(
            live_matches_old=False,
            live_matches_new=False,
            live_missing=True,
            rollback_matches_old=True,
            rollback_missing=False,
            source_matches_new=True,
            source_missing=False,
        )
        == STATE_OLD_MOVED
    )


def test_gate9c_component_state_promoted() -> None:
    assert (
        component_disk_state(
            live_matches_old=False,
            live_matches_new=True,
            live_missing=False,
            rollback_matches_old=True,
            rollback_missing=False,
            source_matches_new=False,
            source_missing=True,
        )
        == STATE_PROMOTED
    )


def test_gate9c_component_state_rejects_ambiguous_duplicate_new_source() -> None:
    assert (
        component_disk_state(
            live_matches_old=False,
            live_matches_new=True,
            live_missing=False,
            rollback_matches_old=True,
            rollback_missing=False,
            source_matches_new=True,
            source_missing=False,
        )
        == STATE_INVALID
    )


def test_gate9c_inventory_fingerprint_is_order_independent_and_content_bound() -> None:
    rows = [
        {"relative_path": "b", "sha256": "two", "bytes": 2},
        {"relative_path": "a", "sha256": "one", "bytes": 1},
    ]
    baseline = inventory_fingerprint(rows)
    assert baseline == inventory_fingerprint(list(reversed(rows)))
    changed = [dict(row) for row in rows]
    changed[0]["sha256"] = "changed"
    assert baseline != inventory_fingerprint(changed)


def test_gate9c_handoff_fingerprint_binds_all_parent_evidence() -> None:
    values = {
        "stage_source_fingerprint": "stage",
        "stage_report_sha256": "stage-report",
        "stage_validation_sha256": "stage-validation",
        "preflight_source_fingerprint": "preflight",
        "production_baseline_fingerprint": "baseline",
        "rollback_inventory_fingerprint": "rollback",
        "promotion_inventory_fingerprint": "promotion",
    }
    baseline = handoff_source_fingerprint(**values)
    assert len(baseline) == 64
    for key in values:
        changed = dict(values)
        changed[key] = f"changed-{key}"
        assert handoff_source_fingerprint(**changed) != baseline


def test_gate9c_runtime_does_not_recreate_consumed_manifest_source(tmp_path: Path) -> None:
    live = tmp_path / "live"
    rollback = tmp_path / "rollback"
    prepared = tmp_path / "prepared"
    stage_source = tmp_path / "stage"
    live.mkdir()
    rollback.mkdir()
    stage_source.mkdir()
    (live / "new.json").write_text("new", encoding="utf-8")
    (rollback / "old.json").write_text("old", encoding="utf-8")
    (stage_source / "new.json").write_text("new", encoding="utf-8")

    new_inventory = _inventory(live, "**/*.json")
    old_inventory = _inventory(rollback, "**/*.json")
    journal = {
        "components": {
            COMPONENT_MANIFESTS: {
                "live": str(live),
                "rollback": str(rollback),
                "source": str(prepared),
                "stage_source": str(stage_source),
                "pattern": "**/*.json",
            }
        },
        "promotion_inventory": {COMPONENT_MANIFESTS: new_inventory},
        "rollback_inventory": {COMPONENT_MANIFESTS: old_inventory},
        "steps": {"prepared_manifests": False},
    }
    runtime = object.__new__(HistoricalBackfillDailyFeatureHandoffRuntime)
    writes: list[bool] = []
    runtime._write_journal = lambda _journal: writes.append(True)  # type: ignore[method-assign]
    runtime._prepare_manifests(journal)

    assert journal["steps"]["prepared_manifests"] is True
    assert writes == [True]
    assert not prepared.exists()


def test_gate9c_runtime_completed_apply_is_read_only() -> None:
    runtime = object.__new__(HistoricalBackfillDailyFeatureHandoffRuntime)
    journal = {"status": "COMPLETE"}
    proof = {"component_states": {}}
    expected = {"pass": True}

    runtime._load_or_create_journal = lambda: journal  # type: ignore[method-assign]
    runtime._verify_complete = lambda _journal: proof  # type: ignore[method-assign]
    runtime._finalize_report = lambda _journal, _proof: expected  # type: ignore[method-assign]
    runtime._prepare_manifests = lambda _journal: (_ for _ in ()).throw(  # type: ignore[method-assign]
        AssertionError("completed apply must not prepare manifests")
    )

    assert runtime.apply() == expected
