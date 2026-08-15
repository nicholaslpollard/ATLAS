from datetime import date
from pathlib import Path

from packages.core.enums import DatasetType, MaterializationStatus
from packages.data.materialization_manifest import MaterializationManifestStore
from packages.schemas.materialization import MaterializationRecord


def test_materialization_manifest_round_trip(tmp_path):
    store = MaterializationManifestStore(tmp_path)
    record = MaterializationRecord(
        source_id="src_abc",
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        trading_date=date(2026, 8, 14),
        source_path=Path("provider.csv.gz"),
        status=MaterializationStatus.COMPLETE,
        source_rows=10,
        canonical_rows=10,
    )
    store.put(record)
    loaded = store.get("src_abc")
    assert loaded is not None
    assert loaded.status == MaterializationStatus.COMPLETE
    assert loaded.canonical_rows == 10
