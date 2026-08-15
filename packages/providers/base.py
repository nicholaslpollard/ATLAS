from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from packages.core.enums import DatasetType
from packages.schemas.ingestion import ProviderFileDescriptor


class FlatFileProvider(Protocol):
    def list_files(self, dataset: DatasetType, start_date: date, end_date: date) -> list[ProviderFileDescriptor]: ...

    def iter_object_chunks(self, remote_key: str, chunk_size: int) -> Iterable[bytes]: ...
