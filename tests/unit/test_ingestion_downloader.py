from __future__ import annotations

from datetime import date

import pytest

from packages.core.enums import DataProvider, DatasetType
from packages.core.exceptions import ProviderError
from packages.ingestion.downloader import AtomicDownloader
from packages.schemas.ingestion import IngestionPlanItem, ProviderFileDescriptor


class FlakyProvider:
    def __init__(self, payload: bytes, failures: int = 0):
        self.payload = payload
        self.failures = failures
        self.calls = 0

    def iter_object_chunks(self, remote_key, chunk_size):
        self.calls += 1
        if self.calls <= self.failures:
            raise ProviderError("simulated")
        for i in range(0, len(self.payload), chunk_size):
            yield self.payload[i:i + chunk_size]


def make_item(tmp_path, payload):
    descriptor = ProviderFileDescriptor(
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        trading_date=date(2026, 8, 14),
        remote_key="remote.csv.gz",
        expected_size_bytes=len(payload),
    )
    return IngestionPlanItem(descriptor=descriptor, local_path=tmp_path / "out.csv.gz", reason="test")


def test_atomic_downloader_retries_and_finishes(tmp_path):
    payload = b"abcdefghijk"
    provider = FlakyProvider(payload, failures=1)
    downloader = AtomicDownloader(provider, chunk_size=3, max_attempts=3, sleeper=lambda _: None)
    result = downloader.download(make_item(tmp_path, payload))
    assert result.attempts == 2
    assert result.local_path.read_bytes() == payload
    assert not list(tmp_path.glob("*.part"))


def test_atomic_downloader_never_promotes_partial_file(tmp_path):
    payload = b"abc"
    provider = FlakyProvider(payload, failures=99)
    downloader = AtomicDownloader(provider, max_attempts=2, sleeper=lambda _: None)
    item = make_item(tmp_path, payload)
    with pytest.raises(Exception):
        downloader.download(item)
    assert not item.local_path.exists()
    assert not list(tmp_path.glob("*.part"))
