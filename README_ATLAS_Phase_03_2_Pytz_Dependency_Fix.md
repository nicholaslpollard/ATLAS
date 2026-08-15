# ATLAS Phase 03.2 — DuckDB `pytz` Dependency Fix

## Problem

Phase 03 successfully materialized Parquet, but DuckDB's Python timestamp
conversion attempted to import `pytz` while reading timezone-aware timestamps
from Parquet. Because `pytz` was not included in ATLAS's dependency lock, two
integration tests failed with:

```text
ModuleNotFoundError: No module named 'pytz'
```

## Fix

This patch:

- adds `pytz==2026.2` to `requirements.lock`
- adds `pytz>=2026.2,<2027` to `pyproject.toml`
- updates `scripts/validate_phase3.py` to verify `pytz` is installed

## Apply

Extract directly into the existing ATLAS root and overwrite the three files.

Then run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe scripts\validate_phase3.py
.\.venv\Scripts\python.exe -m pytest -q
```

Expected result on the user's system:

```text
37 passed
```
