from __future__ import annotations

import re
from datetime import date
from pathlib import PurePosixPath

from packages.core.enums import DataProvider, DatasetType
from packages.core.exceptions import ConfigurationError, ProviderError
from packages.core.settings import AtlasSettings
from packages.schemas.ingestion import ProviderFileDescriptor

from .client import MassiveS3Client

_DATE_FILE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})\.csv\.gz$")


class MassiveFlatFileProvider:
    def __init__(self, settings: AtlasSettings, *, client: MassiveS3Client | None = None) -> None:
        self.settings = settings
        self.client = client or MassiveS3Client(settings)

    def dataset_config(self, dataset: DatasetType):
        try:
            return self.settings.massive.flat_files.datasets[dataset.value]
        except KeyError as exc:
            raise ConfigurationError(f"Massive flat-file dataset is not configured: {dataset.value}") from exc

    def expected_columns(self, dataset: DatasetType) -> list[str]:
        return list(self.dataset_config(dataset).expected_columns)

    def local_subdir(self, dataset: DatasetType) -> str:
        return self.dataset_config(dataset).local_subdir

    @staticmethod
    def trading_date_from_key(key: str) -> date | None:
        match = _DATE_FILE_RE.search(PurePosixPath(key).name)
        if not match:
            return None
        return date.fromisoformat(match.group("date"))

    def list_files(self, dataset: DatasetType, start_date: date, end_date: date) -> list[ProviderFileDescriptor]:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")

        cfg = self.dataset_config(dataset)
        # Listing by year/month prefixes drastically reduces remote inventory work
        # for small date ranges while remaining robust to provider object naming.
        prefixes: list[str] = []
        cursor = date(start_date.year, start_date.month, 1)
        while cursor <= end_date:
            prefixes.append(f"{cfg.prefix}/{cursor.year:04d}/{cursor.month:02d}/")
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)

        by_key: dict[str, ProviderFileDescriptor] = {}
        for prefix in prefixes:
            for obj in self.client.list_objects(prefix):
                key = str(obj.get("Key", ""))
                trading_date = self.trading_date_from_key(key)
                if trading_date is None or not (start_date <= trading_date <= end_date):
                    continue
                descriptor = ProviderFileDescriptor(
                    provider=DataProvider.MASSIVE,
                    dataset=dataset,
                    trading_date=trading_date,
                    remote_key=key,
                    expected_size_bytes=int(obj["Size"]) if obj.get("Size") is not None else None,
                    etag=str(obj.get("ETag", "")).strip('"') or None,
                    last_modified_utc=obj.get("LastModified"),
                )
                by_key[key] = descriptor

        return sorted(by_key.values(), key=lambda item: (item.trading_date, item.remote_key))

    def first_readable_file(
        self,
        dataset: DatasetType,
        start_date: date,
        end_date: date,
    ) -> tuple[ProviderFileDescriptor | None, int, int]:
        """Find the first listed object readable under the current S3 entitlement.

        Massive can list objects outside an account's historical GetObject window.
        Access is expected to be monotonic by trading date: older sessions may be
        denied while newer sessions are readable. We binary-search that boundary
        using one-byte range reads.

        Returns ``(first_readable, inaccessible_count, listed_count)``. If even the
        newest listed object is denied, ``first_readable`` is ``None``.
        """
        files = self.list_files(dataset, start_date, end_date)
        if not files:
            return None, 0, 0

        if not self.client.can_read_object(files[-1].remote_key):
            return None, len(files), len(files)

        if self.client.can_read_object(files[0].remote_key):
            return files[0], 0, len(files)

        low = 0
        high = len(files) - 1
        while low < high:
            mid = (low + high) // 2
            if self.client.can_read_object(files[mid].remote_key):
                high = mid
            else:
                low = mid + 1

        first_index = low
        if first_index > 0 and self.client.can_read_object(files[first_index - 1].remote_key):
            raise ProviderError(
                "Massive historical read access was non-monotonic at the detected boundary; "
                "ATLAS will not infer an entitlement cutoff"
            )
        return files[first_index], first_index, len(files)
