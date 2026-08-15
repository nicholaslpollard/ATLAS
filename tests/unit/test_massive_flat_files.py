from __future__ import annotations

from datetime import date, datetime, timezone

from packages.core.enums import DatasetType
from packages.core.settings import load_settings
from packages.providers.massive.flat_files import MassiveFlatFileProvider


class FakeListClient:
    def list_objects(self, prefix):
        if prefix.endswith("2026/08/"):
            return iter([
                {"Key": "us_stocks_sip/day_aggs_v1/2026/08/2026-08-13.csv.gz", "Size": 100, "ETag": '"abc"', "LastModified": datetime(2026, 8, 14, 15, 0, tzinfo=timezone.utc)},
                {"Key": "us_stocks_sip/day_aggs_v1/2026/08/2026-08-14.csv.gz", "Size": 101, "ETag": '"def"', "LastModified": datetime(2026, 8, 15, 15, 0, tzinfo=timezone.utc)},
            ])
        return iter([])


def test_massive_inventory_parses_actual_objects(tmp_path):
    settings = load_settings(environment="development")
    provider = MassiveFlatFileProvider(settings, client=FakeListClient())
    files = provider.list_files(DatasetType.STOCK_DAILY_AGGREGATES, date(2026, 8, 13), date(2026, 8, 14))
    assert [f.trading_date for f in files] == [date(2026, 8, 13), date(2026, 8, 14)]
    assert files[0].expected_size_bytes == 100
    assert files[0].etag == "abc"
