from __future__ import annotations

import time
from datetime import date

from apps.market_ingestion.flat_file_service import FlatFileIngestionService
from packages.core.enums import DatasetType
from packages.core.exceptions import ProviderAccessDeniedError
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.materializer import MarketDataMaterializer
from packages.ingestion.checkpoint import CheckpointStore
from packages.schemas.history import HistoricalBuildResult


class HistoricalBuildService:
    """Resumable orchestration for historical download + Phase 3 materialization."""

    DATASETS = (DatasetType.STOCK_DAILY_AGGREGATES, DatasetType.STOCK_MINUTE_AGGREGATES)

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        ingestion: FlatFileIngestionService | None = None,
        materializer: MarketDataMaterializer | None = None,
    ) -> None:
        self.settings = settings
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.ingestion = ingestion
        self.materializer = materializer
        self.checkpoints = CheckpointStore(settings.resolved_path(settings.data.paths.checkpoints) / "historical_build")

    def run(
        self,
        start_date: date,
        end_date: date,
        *,
        download_missing: bool = False,
        materialize: bool = True,
        max_download_files: int | None = None,
        max_sessions: int | None = None,
        continue_on_error: bool = True,
    ) -> HistoricalBuildResult:
        if end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        started = time.perf_counter()
        requested_sessions = self.calendar.sessions_in_range(start_date, end_date)
        sessions = list(requested_sessions)
        inaccessible_sessions = 0

        ingestion: FlatFileIngestionService | None = None
        if download_missing and sessions:
            ingestion = self.ingestion or FlatFileIngestionService(self.settings)
            provider = getattr(ingestion, "provider", None)
            first_readable = getattr(provider, "first_readable_file", None)
            if callable(first_readable):
                first_dates: list[date] = []
                for dataset in self.DATASETS:
                    first, _inaccessible_listed, listed = first_readable(dataset, start_date, end_date)
                    if listed and first is None:
                        raise ProviderAccessDeniedError(
                            f"Massive lists {listed} {dataset.value} files in {start_date}..{end_date}, "
                            "but none are readable under the current S3 subscription"
                        )
                    if first is not None:
                        first_dates.append(first.trading_date)
                if first_dates:
                    # Build only the intersection that is readable for every required
                    # source dataset. Existing local files can still be materialized by
                    # running without --download-missing.
                    entitlement_start = max(first_dates)
                    inaccessible_sessions = sum(1 for session in sessions if session < entitlement_start)
                    sessions = [session for session in sessions if session >= entitlement_start]

        if max_sessions is not None:
            sessions = sessions[:max_sessions]

        if sessions:
            effective_start, effective_end = sessions[0], sessions[-1]
        else:
            effective_start = None
            effective_end = None

        daily_planned = 0
        minute_planned = 0
        if download_missing and sessions and ingestion is not None and effective_start is not None and effective_end is not None:
            for dataset in self.DATASETS:
                plan = ingestion.plan(dataset, effective_start, effective_end)
                if dataset == DatasetType.STOCK_DAILY_AGGREGATES:
                    daily_planned = plan.planned_count
                else:
                    minute_planned = plan.planned_count
                if plan.planned_count:
                    ingestion.sync(dataset, effective_start, effective_end, max_files=max_download_files)

        materialized_count = 0
        skipped_count = 0
        failures: dict[str, str] = {}
        if materialize and sessions and effective_start is not None and effective_end is not None:
            materializer = self.materializer or MarketDataMaterializer(self.settings)
            checkpoint_id = f"history_{effective_start}_{effective_end}"
            completed_sessions = 0
            for trading_date in sessions:
                session_failed = False
                # Daily must run first so symbol quarantine propagates to minute.
                for dataset in self.DATASETS:
                    source = materializer.paths.provider_file(dataset, trading_date)
                    if not source.exists():
                        continue
                    try:
                        result = materializer.materialize(dataset, trading_date)
                        if result.skipped:
                            skipped_count += 1
                        else:
                            materialized_count += 1
                    except Exception as exc:
                        key = f"{trading_date}:{dataset.value}"
                        failures[key] = f"{type(exc).__name__}: {exc}"
                        session_failed = True
                        if not continue_on_error:
                            raise
                completed_sessions += 1
                self.checkpoints.advance(
                    checkpoint_id,
                    stage="historical_materialization",
                    source_id=None,
                    cursor=trading_date.isoformat(),
                    completed_units=completed_sessions,
                    total_units=len(sessions),
                )
                if session_failed and not continue_on_error:
                    break

        return HistoricalBuildResult(
            start_date=start_date,
            end_date=end_date,
            effective_start_date=effective_start,
            effective_end_date=effective_end,
            sessions_requested=len(requested_sessions),
            sessions_processed=len(sessions),
            inaccessible_sessions_skipped=inaccessible_sessions,
            daily_downloads_planned=daily_planned,
            minute_downloads_planned=minute_planned,
            materialized_sessions=materialized_count,
            skipped_materializations=skipped_count,
            failures=failures,
            elapsed_seconds=time.perf_counter() - started,
        )
