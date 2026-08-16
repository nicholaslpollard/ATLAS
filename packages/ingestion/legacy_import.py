from __future__ import annotations

import hashlib
import os
import re
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.enums import DataProvider, DatasetType, IngestionStatus, ValidationStatus
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.ingestion.manifest import DirectoryManifestStore
from packages.ingestion.staging import FlatFileValidator
from packages.schemas.history import LegacyImportResult
from packages.schemas.ingestion import IngestionManifestRecord, ProviderFileDescriptor

_DATE_RE = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})\.csv\.gz$")


class LegacyFlatFileImporter:
    """Import existing Massive flat files into ATLAS without re-downloading them."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        cfg = settings.massive.flat_files
        self.validator = FlatFileValidator(validate_gzip_crc=cfg.validate_gzip_crc, count_rows=False)
        self.manifest = DirectoryManifestStore(settings.resolved_path(settings.data.paths.manifests) / "ingestion")

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(4 * 1024 * 1024):
                h.update(chunk)
        return h.hexdigest()

    def _descriptor(self, dataset: DatasetType, trading_date: date) -> ProviderFileDescriptor:
        cfg = self.settings.massive.flat_files.datasets[dataset.value]
        return ProviderFileDescriptor(
            provider=DataProvider.MASSIVE,
            dataset=dataset,
            trading_date=trading_date,
            remote_key=f"{cfg.prefix}/{trading_date.year:04d}/{trading_date.month:02d}/{trading_date}.csv.gz",
        )

    def import_tree(
        self,
        source_root: Path,
        dataset: DatasetType,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        replace_existing: bool = False,
        max_files: int | None = None,
    ) -> LegacyImportResult:
        if dataset not in {DatasetType.STOCK_DAILY_AGGREGATES, DatasetType.STOCK_MINUTE_AGGREGATES}:
            raise ValueError("Legacy importer only accepts Massive daily or minute stock aggregates")
        root = Path(source_root).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Legacy source directory does not exist: {root}")

        discovered: list[tuple[date, Path]] = []
        for path in sorted(root.rglob("*.csv.gz")):
            match = _DATE_RE.search(path.name)
            if not match:
                continue
            trading_date = date.fromisoformat(match.group("date"))
            if start_date and trading_date < start_date:
                continue
            if end_date and trading_date > end_date:
                continue
            discovered.append((trading_date, path))
        if max_files is not None:
            discovered = discovered[:max_files]

        expected_columns = list(self.settings.massive.flat_files.datasets[dataset.value].expected_columns)
        imported = 0
        skipped = 0
        invalid = 0
        imported_dates: list[date] = []
        invalid_paths: list[Path] = []

        for trading_date, source in discovered:
            validation = self.validator.validate(source, expected_columns=expected_columns)
            if not validation.is_valid:
                invalid += 1
                invalid_paths.append(source)
                continue

            destination = self.paths.provider_file(dataset, trading_date)
            source_sha = validation.sha256 or self._sha256(source)
            should_copy = True
            if destination.exists():
                destination_sha = self._sha256(destination)
                if destination_sha == source_sha:
                    should_copy = False
                    skipped += 1
                elif not replace_existing:
                    skipped += 1
                    continue

            if should_copy:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temp = destination.with_name(destination.name + f".{os.getpid()}.importing")
                temp.unlink(missing_ok=True)
                shutil.copy2(source, temp)
                os.replace(temp, destination)
                imported += 1
                imported_dates.append(trading_date)

            descriptor = self._descriptor(dataset, trading_date)
            now = datetime.now(UTC)
            self.manifest.put(
                IngestionManifestRecord(
                    source_id=descriptor.source_id,
                    provider=DataProvider.MASSIVE,
                    dataset=dataset,
                    trading_date=trading_date,
                    remote_key=descriptor.remote_key,
                    local_path=destination,
                    status=IngestionStatus.COMPLETE,
                    validation_status=ValidationStatus.VALID,
                    size_bytes=destination.stat().st_size,
                    sha256=source_sha,
                    attempt_count=0,
                    downloaded_at_utc=now,
                    validated_at_utc=now,
                    processed_at_utc=now,
                )
            )

        return LegacyImportResult(
            dataset=dataset,
            discovered_files=len(discovered),
            imported_files=imported,
            skipped_files=skipped,
            invalid_files=invalid,
            imported_dates=imported_dates,
            invalid_paths=invalid_paths,
        )
