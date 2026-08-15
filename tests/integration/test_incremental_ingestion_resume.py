from __future__ import annotations

import csv
import gzip
import io
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

HEADERS = ["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"]


def payload(symbol):
    raw = io.BytesIO()
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
        writer = csv.writer(text)
        writer.writerow(HEADERS)
        writer.writerow([symbol, 10, 1, 2, 2, 1, 123, 5])
        text.flush()
        text.detach()
    return raw.getvalue()


class FakeMassiveProvider:
    def __init__(self, descriptors, objects):
        self.descriptors = descriptors
        self.objects = objects
        self.client = self

    def list_files(self, dataset, start_date, end_date):
        return [x for x in self.descriptors if start_date <= x.trading_date <= end_date]

    def expected_columns(self, dataset):
        return HEADERS

    def iter_object_chunks(self, remote_key, chunk_size):
        blob = self.objects[remote_key]
        for i in range(0, len(blob), max(1, chunk_size)):
            yield blob[i:i + chunk_size]


def test_crash_resume_and_idempotent_rerun(tmp_path, monkeypatch):
    settings = load_settings(environment="development")
    monkeypatch.setattr(settings.data.paths, "provider", tmp_path / "provider")
    monkeypatch.setattr(settings.data.paths, "manifests", tmp_path / "manifests")
    monkeypatch.setattr(settings.data.paths, "checkpoints", tmp_path / "checkpoints")

    dates = [date(2026, 8, 12), date(2026, 8, 13), date(2026, 8, 14)]
    objects = {f"x/{d}.csv.gz": payload(str(i)) for i, d in enumerate(dates)}
    descriptors = [ProviderFileDescriptor(
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        trading_date=d,
        remote_key=f"x/{d}.csv.gz",
        expected_size_bytes=len(objects[f"x/{d}.csv.gz"]),
    ) for d in dates]
    provider = FakeMassiveProvider(descriptors, objects)
    manifest = DirectoryManifestStore(tmp_path / "manifests" / "ingestion")
    checkpoints = CheckpointStore(tmp_path / "checkpoints" / "ingestion")
    downloader = AtomicDownloader(provider, chunk_size=7, max_attempts=2, sleeper=lambda _: None)
    validator = FlatFileValidator(validate_gzip_crc=True, count_rows=True)
    service = FlatFileIngestionService(
        settings,
        provider=provider,
        manifest=manifest,
        checkpoints=checkpoints,
        downloader=downloader,
        validator=validator,
    )

    with pytest.raises(RuntimeError, match="simulated ingestion interruption"):
        service.sync(descriptors[0].dataset, dates[0], dates[-1], stop_after_completed=1)

    after_crash = service.plan(descriptors[0].dataset, dates[0], dates[-1])
    assert after_crash.already_complete == 1
    assert after_crash.planned_count == 2

    service.sync(descriptors[0].dataset, dates[0], dates[-1])
    complete = service.plan(descriptors[0].dataset, dates[0], dates[-1])
    assert complete.already_complete == 3
    assert complete.planned_count == 0

    # A third run must remain a no-op.
    service.sync(descriptors[0].dataset, dates[0], dates[-1])
    complete_again = service.plan(descriptors[0].dataset, dates[0], dates[-1])
    assert complete_again.planned_count == 0
