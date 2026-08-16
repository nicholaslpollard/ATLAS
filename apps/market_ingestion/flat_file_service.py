from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone

from packages.core.enums import DatasetType, IngestionStatus, ValidationStatus
from packages.core.settings import AtlasSettings
from packages.ingestion.checkpoint import CheckpointStore
from packages.ingestion.downloader import AtomicDownloader
from packages.ingestion.manifest import DirectoryManifestStore
from packages.ingestion.planner import IngestionPlanner
from packages.ingestion.staging import FlatFileValidator
from packages.providers.massive.flat_files import MassiveFlatFileProvider
from packages.schemas.ingestion import IngestionManifestRecord, IngestionPlan


ProgressCallback = Callable[[str, int, int, date], None]


class FlatFileIngestionService:
    def __init__(
        self,
        settings: AtlasSettings,
        *,
        provider: MassiveFlatFileProvider | None = None,
        manifest: DirectoryManifestStore | None = None,
        checkpoints: CheckpointStore | None = None,
        downloader: AtomicDownloader | None = None,
        validator: FlatFileValidator | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider or MassiveFlatFileProvider(settings)
        manifest_root = settings.resolved_path(settings.data.paths.manifests) / "ingestion"
        checkpoint_root = settings.resolved_path(settings.data.paths.checkpoints) / "ingestion"
        self.manifest = manifest or DirectoryManifestStore(manifest_root)
        self.checkpoints = checkpoints or CheckpointStore(checkpoint_root)
        cfg = settings.massive.flat_files
        self.downloader = downloader or AtomicDownloader(
            self.provider.client,
            chunk_size=cfg.chunk_size_bytes,
            max_attempts=cfg.max_attempts,
            initial_retry_seconds=cfg.initial_retry_seconds,
            max_retry_seconds=cfg.max_retry_seconds,
        )
        self.validator = validator or FlatFileValidator(
            validate_gzip_crc=cfg.validate_gzip_crc,
            count_rows=cfg.count_rows_during_validation,
        )
        self.planner = IngestionPlanner(settings, self.provider, self.manifest)

    def plan(self, dataset: DatasetType, start_date: date, end_date: date, *, verify_existing_hashes: bool = False) -> IngestionPlan:
        return self.planner.plan(dataset, start_date, end_date, verify_existing_hashes=verify_existing_hashes)

    def sync(
        self,
        dataset: DatasetType,
        start_date: date,
        end_date: date,
        *,
        max_files: int | None = None,
        verify_existing_hashes: bool = False,
        stop_after_completed: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestionPlan:
        plan = self.plan(dataset, start_date, end_date, verify_existing_hashes=verify_existing_hashes)
        items = plan.items[:max_files] if max_files is not None else plan.items
        checkpoint_id = f"massive_{dataset.value}_{start_date.isoformat()}_{end_date.isoformat()}"
        completed = 0

        for item in items:
            descriptor = item.descriptor
            record = self.manifest.get(descriptor.source_id) or IngestionManifestRecord(
                source_id=descriptor.source_id,
                provider=descriptor.provider,
                dataset=descriptor.dataset,
                trading_date=descriptor.trading_date,
                remote_key=descriptor.remote_key,
                local_path=item.local_path,
                etag=descriptor.etag,
            )
            try:
                record.status = IngestionStatus.DOWNLOADING
                record.attempt_count += 1
                record.last_error = None
                self.manifest.put(record)

                result = self.downloader.download(item)
                now = datetime.now(timezone.utc)
                record.status = IngestionStatus.DOWNLOADED
                record.size_bytes = result.size_bytes
                record.sha256 = result.sha256
                record.downloaded_at_utc = now
                self.manifest.put(record)

                record.status = IngestionStatus.VALIDATING
                self.manifest.put(record)
                validation = self.validator.validate(
                    result.local_path,
                    expected_columns=self.provider.expected_columns(dataset),
                    expected_size_bytes=descriptor.expected_size_bytes,
                    expected_sha256=result.sha256,
                )
                record.validation_status = validation.status
                record.validated_at_utc = datetime.now(timezone.utc)
                if validation.is_valid:
                    record.status = IngestionStatus.COMPLETE
                    record.processed_at_utc = record.validated_at_utc
                    record.last_error = None
                else:
                    record.status = IngestionStatus.FAILED
                    record.last_error = "; ".join(validation.errors)
                self.manifest.put(record)

                if not validation.is_valid:
                    # Keep the invalid file for forensic inspection. The next plan
                    # will correctly schedule it for replacement rather than treat
                    # it as complete.
                    raise ValueError(f"Downloaded file failed validation: {item.local_path.name}")

                completed += 1
                self.checkpoints.advance(
                    checkpoint_id,
                    stage="flat_file_sync",
                    source_id=descriptor.source_id,
                    cursor=descriptor.trading_date.isoformat(),
                    completed_units=completed,
                    total_units=len(items),
                )
                if progress_callback is not None:
                    progress_callback(f"download:{dataset.value}", completed, len(items), descriptor.trading_date)
                if stop_after_completed is not None and completed >= stop_after_completed:
                    raise RuntimeError("simulated ingestion interruption")
            except RuntimeError as exc:
                if str(exc) == "simulated ingestion interruption":
                    raise
                record.status = IngestionStatus.FAILED
                record.last_error = type(exc).__name__
                self.manifest.put(record)
                raise
            except Exception as exc:
                record.status = IngestionStatus.FAILED
                record.last_error = f"{type(exc).__name__}: {exc}"
                self.manifest.put(record)
                raise

        return plan
