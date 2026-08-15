from datetime import date
from pathlib import Path

from packages.core.enums import DatasetType, Timeframe
from packages.core.settings import load_settings
from packages.data.historical_audit import HistoricalLakeAuditor
from packages.data.paths import MarketDataPaths

ROOT = Path(__file__).resolve().parents[2]


def test_audit_tracks_each_layer_independently(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    paths = MarketDataPaths(settings)
    d = date(2026, 8, 14)

    for path in (
        paths.provider_file(DatasetType.STOCK_DAILY_AGGREGATES, d),
        paths.canonical_file(Timeframe.DAY_1, d),
        paths.derived_file(Timeframe.MINUTE_15, d),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")

    report = HistoricalLakeAuditor(settings).audit(d, d)
    assert len(report.exchange_sessions) == 1
    assert report.provider["1d"].present_sessions == 1
    assert report.provider["1m"].present_sessions == 0
    assert report.canonical["1d"].present_sessions == 1
    assert report.canonical["1m"].present_sessions == 0
    assert report.derived["15m"].present_sessions == 1
    assert report.derived["1h"].present_sessions == 0
