from __future__ import annotations

from datetime import date

from packages.core.enums import DatasetType
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.materializer import MarketDataMaterializer, MaterializationResult


class MaterializationService:
    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.materializer = MarketDataMaterializer(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)

    def run_range(
        self,
        start_date: date,
        end_date: date,
        datasets: list[DatasetType],
        *,
        force: bool = False,
        max_sessions: int | None = None,
    ) -> list[MaterializationResult]:
        sessions = self.calendar.sessions_in_range(start_date, end_date)
        if max_sessions is not None:
            sessions = sessions[:max_sessions]
        results: list[MaterializationResult] = []
        for trading_date in sessions:
            for dataset in datasets:
                source = self.materializer.paths.provider_file(dataset, trading_date)
                if not source.exists():
                    continue
                results.append(self.materializer.materialize(dataset, trading_date, force=force))
        return results
