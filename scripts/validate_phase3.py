from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths


def main() -> int:
    try:
        import duckdb
    except ImportError:
        print("Phase 03 validation: FAIL")
        print("duckdb is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.lock")
        return 2

    try:
        import pytz  # noqa: F401 - DuckDB timezone conversion requires it at runtime
    except ImportError:
        print("Phase 03 validation: FAIL")
        print("pytz is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.lock")
        return 2

    settings = load_settings(PROJECT_ROOT)
    paths = MarketDataPaths(settings)
    with tempfile.TemporaryDirectory(prefix="atlas_phase3_") as td:
        parquet = Path(td) / "smoke.parquet"
        con = connect_utc(":memory:")
        try:
            con.execute(f"COPY (SELECT 1 AS x) TO '{parquet.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
            value = con.execute(f"SELECT x FROM read_parquet('{parquet.as_posix()}')").fetchone()[0]
            timezone = con.execute("SELECT current_setting('TimeZone')").fetchone()[0]
        finally:
            con.close()
        if value != 1:
            print("Phase 03 validation: FAIL (Parquet round trip)")
            return 2
        if str(timezone).upper() not in {"UTC", "ETC/UTC"}:
            print(f"Phase 03 validation: FAIL (DuckDB TimeZone={timezone}, expected UTC)")
            return 2

    print(f"DuckDB: {duckdb.__version__}")
    print(f"Canonical root: {settings.resolved_path(settings.data.paths.canonical)}")
    print(f"Derived root: {settings.resolved_path(settings.data.paths.derived)}")
    print(f"DuckDB file: {paths.duckdb_file()}")
    print("DuckDB canonical timezone: UTC")
    print("Parquet read/write smoke test: PASS")
    print("Phase 03 validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
