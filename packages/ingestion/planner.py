from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.core.enums import DataProvider, DatasetType
from packages.core.market_calendar import MarketCalendar, get_market_calendar
from packages.core.settings import AtlasSettings
from packages.schemas.ingestion import IngestionPlan, IngestionPlanItem, ProviderFileDescriptor
from packages.providers.base import FlatFileProvider

from .idempotency import existing_file_is_complete
from .manifest import DirectoryManifestStore


class IngestionPlanner:
    def __init__(
        self,
        settings: AtlasSettings,
        provider: FlatFileProvider,
        manifest: DirectoryManifestStore,
        *,
        market_calendar: MarketCalendar | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.manifest = manifest
        self.calendar = market_calendar or get_market_calendar(settings.data.calendar.exchange)

    def local_path_for(self, descriptor: ProviderFileDescriptor) -> Path:
        cfg = self.settings.massive.flat_files.datasets[descriptor.dataset.value]
        provider_root = self.settings.resolved_path(self.settings.data.paths.provider)
        return provider_root / cfg.local_subdir / f"{descriptor.trading_date.year:04d}" / f"{descriptor.trading_date.isoformat()}.csv.gz"

    def plan(
        self,
        dataset: DatasetType,
        start_date: date,
        end_date: date,
        *,
        verify_existing_hashes: bool = False,
    ) -> IngestionPlan:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")

        descriptors = self.provider.list_files(dataset, start_date, end_date)
        by_date = {item.trading_date: item for item in descriptors}
        expected_sessions = self.calendar.sessions_in_range(start_date, end_date)
        available_sessions = sorted(by_date)
        unavailable = [session for session in expected_sessions if session not in by_date]

        items: list[IngestionPlanItem] = []
        complete = 0
        for descriptor in descriptors:
            local_path = self.local_path_for(descriptor)
            record = self.manifest.get(descriptor.source_id)
            if existing_file_is_complete(
                descriptor,
                local_path,
                record,
                verify_hash=verify_existing_hashes,
            ):
                complete += 1
                continue

            reason = "missing local file"
            if local_path.exists() and record is None:
                reason = "untracked local file requires validation"
            elif record is not None:
                reason = f"manifest status requires work: {record.status.value}/{record.validation_status.value}"

            items.append(IngestionPlanItem(descriptor=descriptor, local_path=local_path, reason=reason))

        return IngestionPlan(
            provider=DataProvider.MASSIVE,
            dataset=dataset,
            start_date=start_date,
            end_date=end_date,
            expected_sessions=expected_sessions,
            available_remote_sessions=available_sessions,
            unavailable_remote_sessions=unavailable,
            items=items,
            already_complete=complete,
        )
