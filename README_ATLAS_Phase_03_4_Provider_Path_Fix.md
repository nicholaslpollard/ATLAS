# ATLAS Phase 03.4 — Provider Path Contract Fix

## Problem

Phase 2 downloads Massive files to:

```text
data/provider/massive/flat_files/day_aggs/YYYY/YYYY-MM-DD.csv.gz
data/provider/massive/flat_files/minute_aggs/YYYY/YYYY-MM-DD.csv.gz
```

The Massive dataset configuration already stores the relative subdirectory as:

```text
massive/flat_files/day_aggs
massive/flat_files/minute_aggs
```

Phase 3's `MarketDataPaths.provider_file()` incorrectly prepended
`massive/flat_files` a second time. It therefore searched for:

```text
data/provider/massive/flat_files/massive/flat_files/...
```

and reported:

```text
No local provider files matched the requested range/datasets.
```

even though the Phase 2 files existed in the correct location.

## Fix

`packages/data/paths.py` now uses the same provider-root + `local_subdir`
contract as the Phase 2 ingestion planner.

A regression test was added to assert the exact expected daily and minute
paths and to explicitly reject a duplicated `massive/flat_files` segment.

## Apply

Extract into the existing ATLAS root and overwrite the included files.

No dependency reinstall is required.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Because one new regression test is added, expected result is now:

```text
38 passed
```

Then retry:

```powershell
.\.venv\Scripts\python.exe scripts\materialize_market_data.py `
  --start 2026-08-14 `
  --end 2026-08-14 `
  --dataset both
```
