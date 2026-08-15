from __future__ import annotations

from pathlib import Path


def sql_string(value: str | Path) -> str:
    """Return a safely quoted DuckDB string literal."""
    text = str(value).replace("\\", "/").replace("'", "''")
    return f"'{text}'"


def sql_bool(value: bool) -> str:
    return "TRUE" if value else "FALSE"
