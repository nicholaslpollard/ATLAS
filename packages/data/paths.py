from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from packages.core.enums import DatasetType, Timeframe
from packages.core.settings import AtlasSettings


@dataclass(frozen=True, slots=True)
class MarketDataPaths:
    settings: AtlasSettings

    def provider_file(self, dataset: DatasetType, trading_date: date) -> Path:
        cfg = self.settings.massive.flat_files.datasets[dataset.value]
        root = self.settings.resolved_path(self.settings.data.paths.provider)
        return root / cfg.local_subdir / f"{trading_date.year:04d}" / f"{trading_date}.csv.gz"

    def staging_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.staging)
        return root / "market" / timeframe.value / f"{trading_date.year:04d}" / f"{trading_date.month:02d}" / f"{trading_date}.parquet"

    def canonical_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.canonical)
        if timeframe == Timeframe.DAY_1:
            return root / "stocks" / timeframe.value / f"year={trading_date.year:04d}" / f"date={trading_date}" / "part-000.parquet"
        return root / "stocks" / timeframe.value / f"year={trading_date.year:04d}" / f"month={trading_date.month:02d}" / f"date={trading_date}" / "part-000.parquet"

    def derived_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "bars" / timeframe.value / f"year={trading_date.year:04d}" / f"month={trading_date.month:02d}" / f"date={trading_date}" / "part-000.parquet"

    def quality_report(self, timeframe: Timeframe, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "quality" / timeframe.value / f"{trading_date.year:04d}" / f"{trading_date}.json"

    def quarantine_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "quality" / "quarantine" / timeframe.value / f"{trading_date.year:04d}" / f"{trading_date}.parquet"

    def symbol_quarantine_registry(self, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "quality" / "symbol_quarantine" / f"{trading_date.year:04d}" / f"{trading_date}.json"

    def reference_snapshot_file(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.canonical)
        return root / "reference" / "massive" / "tickers" / f"date={as_of_date}" / "part-000.parquet"

    def reference_snapshot_manifest(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "reference" / "massive_tickers" / f"{as_of_date}.json"

    def ticker_events_file(self, instrument_id: str) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.canonical)
        return root / "corporate_actions" / "massive" / "ticker_events" / f"instrument_id={instrument_id}" / "part-000.parquet"

    def ticker_events_manifest(self, instrument_id: str) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "reference" / "massive_ticker_events" / f"{instrument_id}.json"

    def ticker_events_glob(self) -> str:
        root = self.settings.resolved_path(self.settings.data.paths.canonical)
        return (root / "corporate_actions" / "massive" / "ticker_events" / "instrument_id=*" / "*.parquet").as_posix()

    def instrument_registry_file(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "reference" / "instruments" / "registry.parquet"

    def ticker_observations_file(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "reference" / "instruments" / "ticker_observations.parquet"

    def ticker_event_observations_file(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "reference" / "instruments" / "ticker_event_observations.parquet"

    def reference_snapshot_glob(self) -> str:
        root = self.settings.resolved_path(self.settings.data.paths.canonical)
        return (root / "reference" / "massive" / "tickers" / "date=*" / "*.parquet").as_posix()

    def materialization_manifest_dir(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "materialization"

    def duckdb_file(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.duckdb)
        return root / "atlas.duckdb"

    def glob_for_timeframe(self, timeframe: Timeframe) -> str:
        if timeframe in {Timeframe.MINUTE_1, Timeframe.DAY_1}:
            root = self.settings.resolved_path(self.settings.data.paths.canonical) / "stocks" / timeframe.value
        else:
            root = self.settings.resolved_path(self.settings.data.paths.derived) / "bars" / timeframe.value
        return (root / "**" / "*.parquet").as_posix()
