from __future__ import annotations

import os
from pathlib import Path

import pytest

from packages.core.exceptions import ConfigurationError
from packages.core.settings import load_settings
from packages.data.external_storage import (
    apply_external_storage_bindings,
    inspect_external_storage,
)


ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path):
    base = load_settings(ROOT, "development")
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def test_external_storage_migrates_only_secondary_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path / "project")
    settings.project_root.mkdir(parents=True)

    option_file = settings.project_root / "data/options/existing.txt"
    option_file.parent.mkdir(parents=True)
    option_file.write_text("option-data", encoding="utf-8")

    stock_file = settings.project_root / "data/canonical/stock.parquet"
    stock_file.parent.mkdir(parents=True)
    stock_file.write_text("stock-data", encoding="utf-8")

    external = tmp_path / "external"
    snapshot = apply_external_storage_bindings(
        settings,
        external_root=external,
        migrate_existing=True,
    )
    assert snapshot.status == "READY"

    assert (external / "options/existing.txt").read_text(encoding="utf-8") == "option-data"
    assert option_file.read_text(encoding="utf-8") == "option-data"
    assert os.path.samefile(settings.project_root / "data/options", external / "options")

    assert stock_file.read_text(encoding="utf-8") == "stock-data"
    assert not stock_file.is_symlink()
    assert not os.path.samefile(stock_file.parent, external / "options")

    monkeypatch.setenv("ATLAS_EXTERNAL_DATA_ROOT", str(external))
    assert settings.resolved_path("data/options/existing.txt").read_text(
        encoding="utf-8"
    ) == "option-data"
    assert settings.resolved_path("data/canonical/stock.parquet") == stock_file.resolve()


def test_external_binding_fails_closed_when_configured_but_not_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path / "project")
    settings.project_root.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    monkeypatch.setenv("ATLAS_EXTERNAL_DATA_ROOT", str(external))

    with pytest.raises(ConfigurationError, match="not ready"):
        settings.resolved_path("data/options/new-file.parquet")


def test_external_storage_snapshot_is_not_configured_without_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    settings = _settings(tmp_path / "project")
    snapshot = inspect_external_storage(settings)
    assert snapshot.status == "NOT_CONFIGURED"
    assert snapshot.configured is False


def test_external_bindings_exclude_primary_stock_paths() -> None:
    settings = load_settings(ROOT, "development")
    project_subdirs = {
        str(binding.project_subdir).replace("\\", "/")
        for binding in settings.data.external_storage.bindings.values()
    }
    assert "data/options" in project_subdirs
    assert "data/news" in project_subdirs
    assert "data/canonical" not in project_subdirs
    assert "data/provider" not in project_subdirs
    assert "data/duckdb" not in project_subdirs
    assert "data/checkpoints" not in project_subdirs
