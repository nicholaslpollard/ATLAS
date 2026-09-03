# ATLAS Phase 03.3 — DuckDB UTC Canonical-Time Fix

## What the local failure proved

DuckDB returned:

`2026-08-14 09:30:00 America/New_York`

while the test expected the `.hour` field to be `13`.

Those are the same instant:

`2026-08-14 09:30 EDT == 2026-08-14 13:30 UTC`

ATLAS's canonical contract is UTC. DuckDB `TIMESTAMPTZ` values represent an
instant, but DuckDB renders/bins them according to the connection's `TimeZone`
setting. On the user's Eastern-time Windows machine that setting caused the
Python datetime to be returned as 09:30 EDT.

## Fix

Phase 03.3 adds a single ATLAS DuckDB connection factory that always executes:

```sql
SET TimeZone='UTC';
```

All ATLAS-owned DuckDB connections now use it, including:

- provider normalization
- canonical materialization
- session aggregation
- quality validation
- daily/minute reconciliation
- analytical repository/query layer
- Phase 03 validation

The integration tests also compare timezone-aware timestamps as UTC instants
rather than assuming the host machine's display zone.

## Apply

Extract this ZIP into the existing ATLAS root and overwrite the included files.

No dependency reinstall is required.

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_phase3.py
.\.venv\Scripts\python.exe -m pytest -q
```

Expected:

```text
DuckDB canonical timezone: UTC
Phase 03 validation: PASS
37 passed
```
