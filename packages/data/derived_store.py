from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths


class DerivedStore:
    """Path-level facade for materialized bars derived from canonical 1m data."""

    MATERIALIZED = {Timeframe.MINUTE_15, Timeframe.HOUR_1, Timeframe.HOUR_4}

    def __init__(self, settings: AtlasSettings) -> None:
        self.paths = MarketDataPaths(settings)

    def session_path(self, timeframe: Timeframe, trading_date: date) -> Path:
        if timeframe not in self.MATERIALIZED:
            raise ValueError(f"Timeframe is not a materialized derived bar: {timeframe}")
        return self.paths.derived_file(timeframe, trading_date)

    def exists(self, timeframe: Timeframe, trading_date: date) -> bool:
        return self.session_path(timeframe, trading_date).exists()
