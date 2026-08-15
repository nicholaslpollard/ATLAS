from datetime import date

from packages.core.enums import DataProvider, DatasetType, IngestionStatus
from packages.ingestion.manifest import DirectoryManifestStore
from packages.schemas.ingestion import IngestionManifestRecord


def test_manifest_round_trip(tmp_path):
    store = DirectoryManifestStore(tmp_path)
    record = IngestionManifestRecord(
        source_id="src_test123",
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        trading_date=date(2026, 8, 14),
        remote_key="x/2026-08-14.csv.gz",
        local_path=tmp_path / "2026-08-14.csv.gz",
        status=IngestionStatus.PLANNED,
    )
    store.put(record)
    loaded = store.get(record.source_id)
    assert loaded is not None
    assert loaded.remote_key == record.remote_key
