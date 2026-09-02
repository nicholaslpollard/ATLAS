# ATLAS Phase 03 — Canonical Storage + Session-Aware Aggregation

Phase 03 turns validated Massive daily/minute flat files into ATLAS-owned
canonical and derived Parquet history.

## Install the new dependency

From the ATLAS root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e .
```

## Validate code/dependencies

```powershell
.\.venv\Scripts\python.exe scripts\validate_foundation.py
.\.venv\Scripts\python.exe scripts\validate_phase3.py
.\.venv\Scripts\python.exe -m pytest -q
```

With DuckDB installed, the Phase 03 package contains 37 collected tests.

## First real-data materialization

You already downloaded both Massive datasets for 2026-08-14. Process only that
session first:

```powershell
.\.venv\Scripts\python.exe scripts\materialize_market_data.py `
  --start 2026-08-14 `
  --end 2026-08-14 `
  --dataset both
```

Run the exact command again. Both source datasets should report
`SKIPPED (already current)`.

## Validate canonical data

```powershell
.\.venv\Scripts\python.exe scripts\validate_canonical_data.py --date 2026-08-14 --timeframe 1m
.\.venv\Scripts\python.exe scripts\validate_canonical_data.py --date 2026-08-14 --timeframe 1d
```

## Reconcile daily vs minute

```powershell
.\.venv\Scripts\python.exe scripts\reconcile_daily_minute.py --date 2026-08-14
```

This is diagnostic; mismatches are reported rather than automatically declared
corruption.

## Query an example ticker

```powershell
.\.venv\Scripts\python.exe scripts\query_market_data.py --symbol AAPL --timeframe 1h --segment regular --limit 20
```

## Important

Do not bulk-download/rebuild the entire five-year archive until the 2026-08-14
real-data Phase 03 test has passed on the development computer.
