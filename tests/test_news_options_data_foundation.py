from __future__ import annotations

import json
from collections import namedtuple
from pathlib import Path

import pytest

from packages.core.settings import load_settings
from packages.data.news_options_source_preflight import (
    DOCUMENTED_SOURCE_COVERAGE,
    run_news_options_data_preflight,
)
from packages.data.research_storage import (
    GIB,
    ResearchStorageError,
    assert_category_acquisition_allowed,
    inspect_research_storage,
)


DiskUsage = namedtuple("DiskUsage", "total used free")


def _settings(tmp_path: Path):
    base = load_settings(Path(__file__).resolve().parents[1])
    return base.model_copy(update={"project_root": tmp_path.resolve()})


def test_storage_policy_preserves_minimum_free_space(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        "packages.data.research_storage.shutil.disk_usage",
        lambda _path: DiskUsage(500 * GIB, 381 * GIB, 119 * GIB),
    )
    snapshot = inspect_research_storage(settings)
    assert snapshot.status == "SAFE"
    assert snapshot.disk_free_gib == pytest.approx(119.0)
    assert snapshot.minimum_free_gib == pytest.approx(50.0)
    assert snapshot.warning_free_gib == pytest.approx(65.0)
    assert snapshot.acquisition_budget_gib == pytest.approx(40.0)
    assert snapshot.maximum_safe_additional_gib == pytest.approx(40.0)


def test_category_quota_blocks_oversized_candidate_cache_acquisition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        "packages.data.research_storage.shutil.disk_usage",
        lambda _path: DiskUsage(500 * GIB, 381 * GIB, 119 * GIB),
    )
    with pytest.raises(ResearchStorageError, match="20.00 GiB quota"):
        assert_category_acquisition_allowed(
            settings,
            category="options_candidate_cache",
            projected_additional_bytes=21 * GIB,
        )


def test_source_preflight_without_provider_probe_performs_no_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        "packages.data.research_storage.shutil.disk_usage",
        lambda _path: DiskUsage(500 * GIB, 381 * GIB, 119 * GIB),
    )
    output = tmp_path / "preflight.json"
    report = run_news_options_data_preflight(
        settings,
        initialize_layout=True,
        probe_providers=False,
        output_path=output,
    )
    assert report["bulk_downloads_performed"] == 0
    assert report["provider_records_persisted"] == 0
    assert report["secrets_persisted"] is False
    assert report["provider_probes"] == {"performed": False}
    assert output.is_file()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["fingerprint"] == report["fingerprint"]
    assert (tmp_path / "data/news/raw").is_dir()
    assert (tmp_path / "data/options/candidate_cache/minute_bars").is_dir()


def test_documented_coverage_keeps_quote_gap_explicit() -> None:
    assert DOCUMENTED_SOURCE_COVERAGE["alpaca_news"]["historical_start"] == "2015-01-01"
    assert DOCUMENTED_SOURCE_COVERAGE["alpaca_options"]["historical_start"] == "2024-02-01"
    assert (
        DOCUMENTED_SOURCE_COVERAGE["massive_option_minute_aggregates"]["historical_start"]
        == "2014-06-02"
    )
    assert DOCUMENTED_SOURCE_COVERAGE["massive_option_quotes"]["historical_start"] == "2022-03-07"
