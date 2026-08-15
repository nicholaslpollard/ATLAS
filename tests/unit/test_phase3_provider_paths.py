from datetime import date

from packages.core.enums import DatasetType
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths


def test_phase3_provider_paths_match_phase2_download_layout(tmp_path):
    settings = load_settings()
    settings.project_root = tmp_path
    paths = MarketDataPaths(settings)
    d = date(2026, 8, 14)

    day = paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d)
    minute = paths.provider_file(DatasetType.STOCK_MINUTE_AGGREGATES, d)

    assert day == tmp_path / "data" / "provider" / "massive" / "flat_files" / "day_aggs" / "2026" / "2026-08-14.csv.gz"
    assert minute == tmp_path / "data" / "provider" / "massive" / "flat_files" / "minute_aggs" / "2026" / "2026-08-14.csv.gz"
    assert "massive/flat_files/massive/flat_files" not in day.as_posix()
    assert "massive/flat_files/massive/flat_files" not in minute.as_posix()
