from __future__ import annotations

import re
from datetime import date
from pathlib import PurePosixPath

from packages.core.enums import DataProvider, DatasetType
from packages.core.exceptions import ConfigurationError
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
