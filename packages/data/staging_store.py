from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths


class NormalizedStagingStore:
    def __init__(self, settings: AtlasSettings) -> None:
        self.paths = MarketDataPaths(settings)

    def session_path(self, timeframe: Timeframe, trading_date: date) -> Path:
        return self.paths.staging_file(timeframe, trading_date)
