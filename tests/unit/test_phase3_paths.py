from datetime import date
from pathlib import Path

from packages.core.enums import DatasetType, Timeframe
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths


def test_phase3_session_partition_paths(tmp_path, monkeypatch):
    # Load the repository config, then relocate all runtime roots under tmp_path.
    settings = load_settings()
    settings.project_root = tmp_path
    paths = MarketDataPaths(settings)
    d = date(2026, 8, 14)
    assert paths.canonical_file(Timeframe.MINUTE_1, d).as_posix().endswith(
        "data/canonical/stocks/1m/year=2026/month=08/date=2026-08-14/part-000.parquet"
    )
    assert paths.canonical_file(Timeframe.DAY_1, d).as_posix().endswith(
        "data/canonical/stocks/1d/year=2026/date=2026-08-14/part-000.parquet"
    )
    assert paths.derived_file(Timeframe.HOUR_1, d).as_posix().endswith(
        "data/derived/bars/1h/year=2026/month=08/date=2026-08-14/part-000.parquet"
    )
