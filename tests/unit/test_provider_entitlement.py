from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from packages.core.enums import DataProvider, DatasetType
from packages.core.exceptions import DownloadError, ProviderAccessDeniedError
from packages.core.settings import load_settings
from packages.ingestion.downloader import AtomicDownloader
from packages.providers.massive.client import MassiveS3Client
from packages.schemas.ingestion import IngestionPlanItem, ProviderFileDescriptor


class _Body:
    def __init__(self, data: bytes = b"x") -> None:
        self.data = data
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if not self.data:
            return b""
        if size < 0:
            out, self.data = self.data, b""
        else:
            out, self.data = self.data[:size], self.data[size:]
        return out

    def close(self) -> None:
        self.closed = True


class _FakeS3:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def get_object(self, *, Bucket: str, Key: str, Range: str | None = None):
        self.calls.append((Key, Range))
        if Key == "denied":
            raise ClientError(
                {
                    "Error": {"Code": "403", "Message": "Forbidden"},
                    "ResponseMetadata": {"HTTPStatusCode": 403},
                },
                "GetObject",
            )
        return {"Body": _Body(b"abcdef")}


class _DeniedProvider:
    def __init__(self) -> None:
        self.calls = 0

    def iter_object_chunks(self, remote_key: str, chunk_size: int):
        self.calls += 1
        raise ProviderAccessDeniedError("outside subscription history")
        yield b""  # pragma: no cover


def test_massive_access_probe_distinguishes_listed_but_denied_object():
    fake = _FakeS3()
    client = MassiveS3Client(load_settings(), s3_client=fake)
    assert client.can_read_object("readable") is True
    assert client.can_read_object("denied") is False
    assert ("readable", "bytes=0-0") in fake.calls
    assert ("denied", "bytes=0-0") in fake.calls


def test_massive_read_raises_specific_access_denied_error():
    client = MassiveS3Client(load_settings(), s3_client=_FakeS3())
    with pytest.raises(ProviderAccessDeniedError):
        list(client.iter_object_chunks("denied", 1024))


def test_downloader_does_not_retry_subscription_access_denial(tmp_path: Path):
    provider = _DeniedProvider()
    descriptor = ProviderFileDescriptor(
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        trading_date=date(2021, 1, 4),
        remote_key="denied",
    )
    item = IngestionPlanItem(
        descriptor=descriptor,
        local_path=tmp_path / "2021-01-04.csv.gz",
        reason="missing",
    )
    sleeps: list[float] = []
    downloader = AtomicDownloader(provider, max_attempts=4, sleeper=sleeps.append)

    with pytest.raises(DownloadError, match="historical entitlement"):
        downloader.download(item)

    assert provider.calls == 1
    assert sleeps == []
