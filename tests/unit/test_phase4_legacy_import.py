from __future__ import annotations

import csv
import gzip
from datetime import UTC, date, datetime
from pathlib import Path

from packages.core.enums import DatasetType, IngestionStatus
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.ingestion.legacy_import import LegacyFlatFileImporter
from packages.ingestion.manifest import DirectoryManifestStore

ROOT = Path(__file__).resolve().parents[2]


def write_provider_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ticker", "volume", "open", "close", "high", "low", "window_start", "transactions"])
        writer.writerow(["AAPL", 100, 10, 11, 12, 9, int(datetime(2026, 8, 14, tzinfo=UTC).timestamp() * 1e9), 25])


def test_legacy_import_registers_valid_existing_massive_file(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path / "atlas"
    source_root = tmp_path / "legacy_daily"
    source = source_root / "2026" / "2026-08-14.csv.gz"
    write_provider_file(source)

    result = LegacyFlatFileImporter(settings).import_tree(source_root, DatasetType.STOCK_DAILY_AGGREGATES)
    assert result.imported_files == 1
    destination = MarketDataPaths(settings).provider_file(DatasetType.STOCK_DAILY_AGGREGATES, date(2026, 8, 14))
    assert destination.is_file()

    records = DirectoryManifestStore(settings.resolved_path(settings.data.paths.manifests) / "ingestion").list_records()
    assert len(records) == 1
    assert records[0].status == IngestionStatus.COMPLETE
    assert records[0].sha256
