from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from packages.core.settings import load_settings
from packages.data.offline_workstation_review_v1 import (
    build_offline_workstation_review,
    inspect_artifact_group,
)
from scripts import review_offline_workstation_v1 as command


ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    settings = load_settings(ROOT, "development").model_copy(update={"project_root": tmp_path})
    tmp_path.mkdir(parents=True, exist_ok=True)
    return settings


def test_inventory_missing_inputs_is_complete_without_source_or_network_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch)

    def forbidden(*args, **kwargs):
        raise AssertionError("inventory attempted network access")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    before = set(tmp_path.rglob("*"))
    report = build_offline_workstation_review(settings)
    assert report["status"] == "COMPLETE_METADATA_INVENTORY_WITH_GAPS"
    assert report["storage"]["status"] == "NOT_CONFIGURED"
    assert all(group["status"] == "DIRECTORY_MISSING" for group in report["artifact_groups"])
    assert report["authority"]["provider_requests"] == 0
    assert report["authority"]["historical_bar_scans"] == 0
    assert set(tmp_path.rglob("*")) == before


def test_inventory_reports_only_headers_and_does_not_open_raw_or_other_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    directory = tmp_path / "data/options/manifests"
    directory.mkdir(parents=True)
    path = directory / "plan_a.json"
    raw = json.dumps({"status": "COMPLETE", "plan_fingerprint": "a" * 64, "api_key": "PRIVATE_KEY_SENTINEL", "realized_pnl": "UNREAD_PERFORMANCE_SENTINEL"})
    path.write_text(raw)
    (directory / "raw.bin").write_bytes(b"DO_NOT_SCAN_RAW")
    group = inspect_artifact_group(settings, "plans", "data/options/manifests", ("plan_*.json",))
    assert group["status"] == "CANDIDATES_PRESENT_NOT_VALIDATED"
    assert len(group["files"]) == 1
    assert group["active_artifact_selected"] is False
    assert group["files"][0]["reported_headers"]["plan_fingerprint"] == "a" * 64
    serialized = json.dumps(group)
    assert "PRIVATE_KEY_SENTINEL" not in serialized
    assert "UNREAD_PERFORMANCE_SENTINEL" not in serialized
    assert "DO_NOT_SCAN_RAW" not in serialized
    assert path.read_text() == raw


def test_missing_metadata_and_multiple_candidates_remain_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    directory = tmp_path / "metadata"
    directory.mkdir()
    empty = inspect_artifact_group(settings, "plans", "metadata", ("*.json",))
    assert empty["status"] == "NO_MATCHING_METADATA"
    assert empty["missing_patterns"] == ["*.json"]
    for name in ["plan_a.json", "plan_b.json"]:
        (directory / name).write_text('{"status":"COMPLETE"}')
    found = inspect_artifact_group(settings, "plans", "metadata", ("plan_*.json", "missing_*.json"))
    assert found["status"] == "PARTIAL_METADATA_INVENTORY"
    assert len(found["files"]) == 2
    assert found["active_artifact_selected"] is False
    assert found["missing_patterns"] == ["missing_*.json"]


def test_wrong_secondary_binding_blocks_local_spillover_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _settings(tmp_path / "project", monkeypatch)
    external = tmp_path / "external"
    (external / "options").mkdir(parents=True)
    monkeypatch.setenv("ATLAS_EXTERNAL_DATA_ROOT", str(external))
    local = settings.project_root / "data/options/manifests"
    local.mkdir(parents=True)
    (local / "plan.json").write_text('{"status":"WRONG_LOCAL_COPY"}')
    group = inspect_artifact_group(settings, "plans", "data/options/manifests", ("*.json",))
    assert group["status"] == "BLOCKED_STORAGE_BINDING"
    assert group["files"] == []


def test_malformed_oversized_and_linked_metadata_do_not_gain_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from packages.data import offline_workstation_review_v1 as module

    settings = _settings(tmp_path, monkeypatch)
    directory = tmp_path / "metadata"
    directory.mkdir()
    (directory / "bad.json").write_text("not json")
    (directory / "large.json").write_text("x" * 513)
    monkeypatch.setattr(module, "MAX_METADATA_BYTES", 512)
    group = inspect_artifact_group(settings, "plans", "metadata", ("*.json",))
    states = {Path(row["path"]).name: row["inspection"] for row in group["files"]}
    assert states == {"bad.json": "UNREADABLE_METADATA", "large.json": "SIZE_ONLY_METADATA_TOO_LARGE"}
    target = tmp_path / "outside.json"
    target.write_text('{"status":"OUTSIDE"}')
    link = directory / "linked.json"
    try:
        link.symlink_to(target)
    except OSError:
        return  # Windows runners may not permit file symlink creation.
    linked = inspect_artifact_group(settings, "plans", "metadata", ("linked.json",))
    assert linked["files"][0]["inspection"] == "BLOCKED_PATH_LINK"


def test_candidate_limit_is_explicit_without_choosing_newest_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from packages.data import offline_workstation_review_v1 as module

    settings = _settings(tmp_path, monkeypatch)
    directory = tmp_path / "metadata"
    directory.mkdir()
    for i in range(5):
        (directory / f"plan_{i}.json").write_text('{"status":"COMPLETE"}')
    monkeypatch.setattr(module, "MAX_CANDIDATES", 2)
    group = inspect_artifact_group(settings, "plans", "metadata", ("plan_*.json",))
    assert group["candidate_set_truncated"] is True
    assert len(group["files"]) == 2
    assert group["active_artifact_selected"] is False
    assert group["status"] == "PARTIAL_METADATA_INVENTORY"


def test_command_is_read_only_by_default_and_saves_only_new_report_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _settings(tmp_path, monkeypatch)
    monkeypatch.setattr(command, "load_settings", lambda *args: settings)
    assert command.main([]) == 0
    assert not (tmp_path / "data").exists()
    assert command.main(["--save-report"]) == 0
    assert command.main(["--save-report"]) == 0
    paths = list((tmp_path / "data/research/offline_workstation_review_v1").glob("*.json"))
    assert len(paths) == 2
    assert all(json.loads(path.read_text())["authority"]["simulations_run"] == 0 for path in paths)
    assert "COMPLETE_METADATA_INVENTORY_WITH_GAPS" in capsys.readouterr().out
