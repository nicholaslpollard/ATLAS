from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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

    def feature_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "features" / timeframe.value / f"year={trading_date.year:04d}" / f"month={trading_date.month:02d}" / f"date={trading_date}" / "part-000.parquet"

    def feature_manifest_file(self, timeframe: Timeframe, trading_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "features" / timeframe.value / f"{trading_date.year:04d}" / f"{trading_date}.json"

    def feature_current_state_file(self, timeframe: Timeframe) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "features" / "_state" / timeframe.value / "current.json.gz"

    def feature_monthly_state_file(self, timeframe: Timeframe, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "features" / "_state" / timeframe.value / "monthly" / f"{as_of_date.year:04d}" / f"{as_of_date}.json.gz"

    def feature_benchmark_report(self, generated_at_utc: datetime) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        stamp = generated_at_utc.strftime("%Y-%m-%dT%H%M%SZ")
        return root / "features" / "_benchmarks" / f"{generated_at_utc.year:04d}" / f"{generated_at_utc.date()}" / f"{stamp}.json"

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

    def universe_reference_inventory_report(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "universe" / "reference_inventory" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def universe_snapshot_file(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "universe" / "snapshots" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / "part-000.parquet"

    def universe_exclusion_file(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "universe" / "exclusions" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / "part-000.parquet"

    def universe_snapshot_manifest(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "universe" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def discovery_input_inventory_report(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "discovery" / "input_inventory" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def discovery_snapshot_file(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "discovery" / "snapshots" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / "part-000.parquet"

    def discovery_snapshot_manifest(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "discovery" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def discovery_score_file(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "discovery" / "scores" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / "part-000.parquet"

    def discovery_score_manifest(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "discovery_scores" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def discovery_state_file(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "discovery" / "states" / f"year={as_of_date.year:04d}" / f"date={as_of_date}" / "part-000.parquet"

    def discovery_state_manifest(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "discovery_states" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def regime_input_inventory_report(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "regimes" / "input_inventory" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def regime_classification_probe_report(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "regimes" / "classification_probe" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

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

    def authoritative_ticker_intervals_file(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "reference" / "instruments" / "authoritative_ticker_intervals.parquet"

    def reference_snapshot_glob(self) -> str:
        root = self.settings.resolved_path(self.settings.data.paths.canonical)
        return (root / "reference" / "massive" / "tickers" / "date=*" / "*.parquet").as_posix()

    def live_state_file(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.live)
        return root / "market_state" / "current.json"

    def live_journal_file(self, session_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.live)
        return root / "journal" / "massive" / "stocks" / f"{session_date.year:04d}" / f"{session_date}.jsonl"

    def live_reconciliation_report(self, session_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.live)
        return root / "reconciliation" / f"{session_date.year:04d}" / f"{session_date}.json"

    def live_benchmark_report(self, generated_at_utc: datetime) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.live)
        stamp = generated_at_utc.strftime("%Y-%m-%dT%H%M%SZ")
        return root / "benchmarks" / f"{generated_at_utc.year:04d}" / f"{generated_at_utc.date()}" / f"{stamp}.json"

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
