from __future__ import annotations

from datetime import date

from packages.core.enums import DataProvider, DatasetType, IngestionStatus, ValidationStatus
from packages.core.settings import load_settings
from packages.ingestion.manifest import DirectoryManifestStore
from packages.ingestion.planner import IngestionPlanner
from packages.schemas.ingestion import IngestionManifestRecord, ProviderFileDescriptor


class FakeProvider:
    def __init__(self, descriptors):
        self.descriptors = descriptors

    def list_files(self, dataset, start_date, end_date):
        return [d for d in self.descriptors if start_date <= d.trading_date <= end_date]


def desc(d):
    return ProviderFileDescriptor(
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        trading_date=d,
        remote_key=f"x/{d}.csv.gz",
        expected_size_bytes=3,
    )


def test_planner_ignores_weekend_and_identifies_remote_gap(tmp_path, monkeypatch):
    settings = load_settings(environment="development")
    monkeypatch.setattr(settings.data.paths, "provider", tmp_path / "provider")
    manifest = DirectoryManifestStore(tmp_path / "manifest")
    # Fri 8/7, Mon 8/10, Tue 8/11 are sessions. Monday is intentionally absent remotely.
    provider = FakeProvider([desc(date(2026, 8, 7)), desc(date(2026, 8, 11))])
    plan = IngestionPlanner(settings, provider, manifest).plan(
        DatasetType.STOCK_DAILY_AGGREGATES, date(2026, 8, 7), date(2026, 8, 11)
    )
    assert date(2026, 8, 8) not in plan.expected_sessions
    assert date(2026, 8, 9) not in plan.expected_sessions
    assert plan.unavailable_remote_sessions == [date(2026, 8, 10)]
    assert plan.planned_count == 2


def test_planner_skips_valid_complete_existing_file(tmp_path, monkeypatch):
    settings = load_settings(environment="development")
    monkeypatch.setattr(settings.data.paths, "provider", tmp_path / "provider")
    manifest = DirectoryManifestStore(tmp_path / "manifest")
    descriptor = desc(date(2026, 8, 14))
    provider = FakeProvider([descriptor])
    planner = IngestionPlanner(settings, provider, manifest)
    local = planner.local_path_for(descriptor)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(b"abc")
    manifest.put(IngestionManifestRecord(
        source_id=descriptor.source_id,
        provider=descriptor.provider,
        dataset=descriptor.dataset,
        trading_date=descriptor.trading_date,
        remote_key=descriptor.remote_key,
        local_path=local,
        status=IngestionStatus.COMPLETE,
        validation_status=ValidationStatus.VALID,
        size_bytes=3,
    ))
    plan = planner.plan(descriptor.dataset, descriptor.trading_date, descriptor.trading_date)
    assert plan.planned_count == 0
    assert plan.already_complete == 1
