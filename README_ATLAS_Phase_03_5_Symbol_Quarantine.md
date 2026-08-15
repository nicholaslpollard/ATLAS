# ATLAS Phase 03.5 — Provider Symbol Conflict Quarantine

## What the August 14 real-data test found

The Massive daily file contained two materially different rows for each of:

- BCPC
- TPC

The minute file also contained two incompatible price regimes under each ticker.

This is not an exact duplicate and ATLAS must not choose first/last/high-volume
as the winner without authoritative reconciliation.

## Phase 03.5 policy

1. Exact duplicate provider rows:
   - remove deterministically;
   - retain a quality warning;
   - do not quarantine the symbol.

2. Conflicting daily rows for the same canonical ticker/date key:
   - quarantine the entire symbol for that session;
   - preserve every quarantined row in Parquet;
   - record the conflict and samples in a JSON registry;
   - materialize all clean symbols normally;
   - mark session quality WARNING rather than INVALID.

3. Minute data:
   - reads the same session symbol-quarantine registry;
   - removes all quarantined ticker rows before canonical/derived bars are built;
   - preserves those minute rows in quarantine Parquet;
   - downstream research/trading never sees contaminated bars.

4. Dependency tracking:
   - minute materialization fingerprints the quarantine registry;
   - if a later provider correction changes the quarantine set, the minute
     session rebuilds even if its own source-file hash did not change.

No row is arbitrarily selected as the true BCPC/TPC observation.

## New artifacts

```text
data/derived/quality/
├── quarantine/
│   ├── 1d/YYYY/YYYY-MM-DD.parquet
│   └── 1m/YYYY/YYYY-MM-DD.parquet
└── symbol_quarantine/
    └── YYYY/YYYY-MM-DD.json
```

Use:

```powershell
.\.venv\Scripts\python.exe scripts\show_symbol_quarantine.py --date 2026-08-14
```

to inspect a session registry.

## Apply

Extract this ZIP directly into the existing ATLAS root.

No new dependency is required.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected on the user's machine:

```text
42 passed
```

Then retry the August 14 materialization:

```powershell
.\.venv\Scripts\python.exe scripts\materialize_market_data.py `
  --start 2026-08-14 `
  --end 2026-08-14 `
  --dataset both
```

Expected behavior:
- daily: MATERIALIZED, quality WARNING, BCPC/TPC quarantined
- minute: MATERIALIZED, quality WARNING, BCPC/TPC quarantined
- 15m/1h/4h derived bars built only from clean minute symbols
