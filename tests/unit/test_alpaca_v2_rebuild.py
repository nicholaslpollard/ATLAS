from pathlib import Path

import pytest

from packages.data.alpaca_v2_rebuild import (
    V1_HISTORICAL_TARGETS,
    V2Layout,
    build_decommission_plan,
    execute_decommission,
    execute_decommission_with_journal,
)
from scripts import run_alpaca_v2_rebuild


def test_plan_targets_only_allowlisted_historical_namespaces(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "canonical" / "stocks").mkdir(parents=True)
    (data / "canonical" / "stocks" / "part.parquet").write_bytes(b"old")
    (data / "derived" / "research" / "accepted").mkdir(parents=True)
    (data / "derived" / "research" / "accepted" / "evidence.json").write_text("{}")
    (data / "live").mkdir(parents=True)
    (data / "live" / "state.json").write_text("{}")

    plan = build_decommission_plan(data)

    assert [item.relative_path for item in plan.entries] == ["canonical"]
    assert all(item.relative_path in V1_HISTORICAL_TARGETS for item in plan.entries)
    assert plan.total_files == 1


def test_residual_cleanup_removes_database_layers_but_preserves_accepted_evidence(
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    targets = (
        "raw/day_aggs_v1",
        "provider/alpaca/probe",
        "derived/ml/training_datasets/run",
        "derived/discovery",
        "derived/universe",
        "manifests/features",
        "checkpoints/ingestion",
    )
    for relative in targets:
        path = data / relative
        path.mkdir(parents=True)
        (path / "old.bin").write_bytes(b"old")
    preserved = (
        "derived/strategy_evaluation/phase31/evidence",
        "provider/pre_phase33_beneficial_ownership/v1",
        "provider/phase32_sec_8k_predictor_acquisition/v1",
        "live/journal",
    )
    for relative in preserved:
        path = data / relative
        path.mkdir(parents=True)
        (path / "keep.bin").write_bytes(b"keep")

    plan = build_decommission_plan(data)
    planned = {entry.relative_path for entry in plan.entries}

    assert "raw/day_aggs_v1" in planned
    assert "provider/alpaca" in planned
    assert "derived/ml/training_datasets" in planned
    assert "derived/discovery" in planned
    assert "derived/universe" in planned
    assert "manifests/features" in planned
    assert "checkpoints/ingestion" in planned
    assert all(not any(item.startswith(relative) for item in planned) for relative in preserved)


def test_decommission_is_hash_bound_and_preserves_live_and_research(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "derived" / "features").mkdir(parents=True)
    (data / "derived" / "features" / "old.parquet").write_bytes(b"old")
    (data / "derived" / "research").mkdir(parents=True)
    (data / "derived" / "research" / "keep.json").write_text("{}")
    (data / "live").mkdir(parents=True)
    (data / "live" / "keep.json").write_text("{}")
    plan = build_decommission_plan(data)

    with pytest.raises(RuntimeError, match="confirmation token"):
        execute_decommission(plan, confirmation_token="wrong")

    assert execute_decommission(plan, confirmation_token=plan.confirmation_token) == 1
    assert not (data / "derived" / "features").exists()
    assert (data / "derived" / "research" / "keep.json").exists()
    assert (data / "live" / "keep.json").exists()


def test_decommission_fails_if_inventory_changes(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "canonical").mkdir(parents=True)
    target = data / "canonical" / "old.parquet"
    target.write_bytes(b"old")
    plan = build_decommission_plan(data)
    target.write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="inventory changed"):
        execute_decommission(plan, confirmation_token=plan.confirmation_token)


def test_v2_layout_is_generation_isolated(tmp_path: Path) -> None:
    layout = V2Layout.beneath(tmp_path / "data")
    layout.create()

    assert layout.root.name == "alpaca_sip_v2"
    assert layout.canonical_daily.is_dir()
    assert layout.canonical_minute.is_dir()
    assert layout.checkpoints.is_dir()


def test_plan_refuses_symlink_target(tmp_path: Path) -> None:
    data = tmp_path / "data"
    outside = tmp_path / "outside"
    outside.mkdir()
    data.mkdir()
    (data / "canonical").symlink_to(outside, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        build_decommission_plan(data)


def test_coordinator_unlocks_only_after_native_acquisition_exists() -> None:
    assert run_alpaca_v2_rebuild.REBUILD_ACQUISITION_READY is True
    assert run_alpaca_v2_rebuild.parser().parse_args(["--build-v2"]).build_v2 is True


def test_database_only_mode_deletes_v1_and_retains_receipt_and_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    (data / "canonical").mkdir(parents=True)
    (data / "canonical" / "old.parquet").write_bytes(b"old")
    (data / "live").mkdir(parents=True)
    (data / "live" / "state.json").write_text("{}")
    plan = build_decommission_plan(data)
    monkeypatch.setattr(run_alpaca_v2_rebuild, "PROJECT_ROOT", tmp_path)

    assert (
        run_alpaca_v2_rebuild.main(
            [
                "--decommission-v1-only",
                "--confirmation-token",
                plan.confirmation_token,
            ]
        )
        == 0
    )

    receipts = list(
        (data / "checkpoints" / "alpaca_v2_migration").glob(
            "v1_decommission_receipt_*.json"
        )
    )
    assert len(receipts) == 1
    receipt = receipts[0]
    assert not (data / "canonical").exists()
    assert (data / "live" / "state.json").exists()
    assert '"status": "COMPLETE"' in receipt.read_text()


def test_decommission_journal_records_completion(tmp_path: Path) -> None:
    data = tmp_path / "data"
    (data / "canonical").mkdir(parents=True)
    (data / "canonical" / "old.parquet").write_bytes(b"old")
    plan = build_decommission_plan(data)
    journal = data / "checkpoints" / "receipt.json"

    assert execute_decommission_with_journal(
        plan,
        confirmation_token=plan.confirmation_token,
        journal_path=journal,
    ) == 1
    assert '"completed_targets": [\n    "canonical"' in journal.read_text()


def test_preflight_prints_each_exact_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data = tmp_path / "data"
    (data / "canonical").mkdir(parents=True)
    (data / "canonical" / "old.parquet").write_bytes(b"old")
    monkeypatch.setattr(run_alpaca_v2_rebuild, "PROJECT_ROOT", tmp_path)

    assert run_alpaca_v2_rebuild.main([]) == 0

    output = capsys.readouterr().out
    assert "exact historical targets:" in output
    assert "canonical (directory; 1 files; 3.00 B)" in output
