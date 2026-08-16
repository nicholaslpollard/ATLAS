from datetime import date
from pathlib import Path

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths

ROOT = Path(__file__).resolve().parents[2]


def test_phase4_reference_paths_are_under_canonical_and_derived(tmp_path):
    settings = load_settings(ROOT, "development")
    settings.project_root = tmp_path
    paths = MarketDataPaths(settings)
    d = date(2026, 8, 14)
    assert paths.reference_snapshot_file(d) == tmp_path / "data/canonical/reference/massive/tickers/date=2026-08-14/part-000.parquet"
    assert paths.instrument_registry_file() == tmp_path / "data/derived/reference/instruments/registry.parquet"
    assert paths.ticker_observations_file() == tmp_path / "data/derived/reference/instruments/ticker_observations.parquet"
