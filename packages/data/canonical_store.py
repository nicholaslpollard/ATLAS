from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths


class CanonicalStore:
    """Path-level facade for trusted provider-fact Parquet partitions."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.paths = MarketDataPaths(settings)

    def session_path(self, timeframe: Timeframe, trading_date: date) -> Path:
        if timeframe not in {Timeframe.MINUTE_1, Timeframe.DAY_1}:
            raise ValueError("CanonicalStore only contains 1m and 1d provider facts")
        return self.paths.canonical_file(timeframe, trading_date)

    def exists(self, timeframe: Timeframe, trading_date: date) -> bool:
        return self.session_path(timeframe, trading_date).exists()
