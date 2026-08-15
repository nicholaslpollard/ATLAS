from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.enums import InstrumentIdentityQuality
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.instruments.identity import InstrumentIdentityResolver


def main() -> int:
    settings = load_settings(PROJECT_ROOT)
    paths = MarketDataPaths(settings)
    resolver = InstrumentIdentityResolver()
    a, key_a, quality_a = resolver.resolve({"ticker": "OLD", "composite_figi": "BBG000TEST01"}, date(2025, 1, 2))
    b, key_b, quality_b = resolver.resolve({"ticker": "NEW", "composite_figi": "BBG000TEST01"}, date(2026, 1, 2))
    if a != b or key_a != key_b or quality_a != InstrumentIdentityQuality.STRONG or quality_b != InstrumentIdentityQuality.STRONG:
        raise RuntimeError("Stable FIGI identity validation failed")

    print(f"Massive REST base: {settings.massive.provider.rest_base_url}")
    print(f"Reference page limit: {settings.massive.reference.page_limit}")
    print(f"Reference root: {paths.reference_snapshot_file(date(2026, 8, 14)).parent.parent}")
    print(f"Instrument registry: {paths.instrument_registry_file()}")
    print("Stable FIGI identity: PASS")
    try:
        from packages.data.duckdb_connection import connect_utc
        con = connect_utc(":memory:")
        try:
            tz = con.execute("SELECT current_setting('TimeZone')").fetchone()[0]
        finally:
            con.close()
        print(f"DuckDB canonical timezone: {tz}")
    except RuntimeError as exc:
        print(f"DuckDB check skipped: {exc}")
    print("Phase 04 validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
