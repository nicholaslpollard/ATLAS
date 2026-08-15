from __future__ import annotations

from datetime import date

import pytest

from apps.market_ingestion.flat_file_service import FlatFileIngestionService
from packages.core.enums import DataProvider, DatasetType
from packages.core.settings import load_settings
from packages.ingestion.checkpoint import CheckpointStore
from packages.ingestion.downloader import AtomicDownloader
from packages.ingestion.manifest import DirectoryManifestStore
from packages.ingestion.staging import FlatFileValidator
from packages.schemas.ingestion import ProviderFileDescriptor


class BadProvider:
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.client = self

    def list_files(self, dataset, start_date, end_date):
        return [self.descriptor]

    def expected_columns(self, dataset):
        return ["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"]

    def iter_object_chunks(self, remote_key, chunk_size):
        yield b"definitely not a gzip file"


def test_invalid_file_is_not_considered_complete(tmp_path, monkeypatch):
    blob = b"definitely not a gzip file"
    descriptor = ProviderFileDescriptor(
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        trading_date=date(2026, 8, 14),
        remote_key="x/2026-08-14.csv.gz",
        expected_size_bytes=len(blob),
    )
    settings = load_settings(environment="development")
    monkeypatch.setattr(settings.data.paths, "provider", tmp_path / "provider")
    provider = BadProvider(descriptor)
    manifest = DirectoryManifestStore(tmp_path / "manifest")
    service = FlatFileIngestionService(
        settings,
        provider=provider,
        manifest=manifest,
        checkpoints=CheckpointStore(tmp_path / "checkpoints"),
        downloader=AtomicDownloader(provider, sleeper=lambda _: None),
        validator=FlatFileValidator(),
    )
    with pytest.raises(Exception):
        service.sync(descriptor.dataset, descriptor.trading_date, descriptor.trading_date)
    plan = service.plan(descriptor.dataset, descriptor.trading_date, descriptor.trading_date)
    assert plan.planned_count == 1
