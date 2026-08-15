from datetime import date
from pathlib import Path

from packages.core.enums import DataProvider, DatasetType
from packages.schemas.ingestion import IngestionPlanItem, ProviderFileDescriptor


def test_source_id_is_deterministic():
    descriptor = ProviderFileDescriptor(
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        trading_date=date(2026, 8, 14),
        remote_key="us_stocks_sip/minute_aggs_v1/2026/08/2026-08-14.csv.gz",
    )
    same = ProviderFileDescriptor(**descriptor.model_dump())
    assert descriptor.source_id == same.source_id
    assert descriptor.source_id.startswith("src_")


def test_plan_id_is_deterministic():
    descriptor = ProviderFileDescriptor(
        provider=DataProvider.MASSIVE,
        dataset=DatasetType.STOCK_DAILY_AGGREGATES,
        trading_date=date(2026, 8, 14),
        remote_key="daily",
    )
    item = IngestionPlanItem(descriptor=descriptor, local_path=Path("data/file.csv.gz"), reason="missing")
    assert item.plan_id == IngestionPlanItem(**item.model_dump()).plan_id
