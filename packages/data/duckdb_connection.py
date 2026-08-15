from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


def connect_utc(database: str | Path = ':memory:', **kwargs: Any):
    """Create a DuckDB connection with ATLAS canonical timezone semantics.

    ATLAS stores market timestamps as absolute instants and names canonical
    timestamp columns ``*_utc``. DuckDB's TIMESTAMPTZ values are rendered and
    binned using the connection TimeZone setting, which may otherwise inherit
    the host machine's local timezone. Every ATLAS-owned connection therefore
    uses UTC explicitly.
    """
    if duckdb is None:
        raise RuntimeError('duckdb is required for Phase 3. Run: pip install -r requirements.lock')
    con = duckdb.connect(str(database), **kwargs)
    con.execute("SET TimeZone='UTC'")
    return con
