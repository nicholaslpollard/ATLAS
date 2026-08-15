# Phase 04 — Instrument Identity and Historical Lake Build

Phase 04 adds the identity and orchestration layer required before ATLAS rebuilds
multiple years of historical market data.

## 1. Instrument identity is not ticker identity

A ticker is a point-in-time label. ATLAS assigns a deterministic `instrument_id`
using the strongest provider identifier available in this order:

1. Massive Composite FIGI — strong
2. Massive Share Class FIGI — strong
3. CIK + primary exchange + security type — medium
4. ticker + snapshot date — fallback and deliberately *not* merged across dates

This prevents a symbol rename or later ticker reuse from silently joining unrelated
market histories.

Reference observations are stored under:

```text
data/canonical/reference/massive/tickers/date=YYYY-MM-DD/part-000.parquet
```

The derived identity views are:

```text
data/derived/reference/instruments/registry.parquet
data/derived/reference/instruments/ticker_observations.parquet
```

`ticker_observations.parquet` records observed date ranges. Those are observation
bounds, not claimed legal/effective ticker-change dates. Massive's experimental
Ticker Events endpoint can later provide explicit change events where needed.

## 2. Massive reference API security

ATLAS authenticates Massive REST requests with:

```http
Authorization: Bearer <MASSIVE_API_KEY>
```

The API key is never appended to request URLs. Pagination URLs are sanitized to
remove any `apiKey` parameter before use and are rejected if they change host.

## 3. Point-in-time reference snapshots

Use:

```powershell
.\.venv\Scripts\python.exe scripts\sync_instrument_reference.py --date 2026-08-14
```

ATLAS requests both active and inactive stock reference populations for that date,
creates stable instrument identities, writes the canonical snapshot, and rebuilds
the aggregate identity registry. Re-running the same command skips an existing
snapshot unless `--force` is supplied.

Resolve a symbol against a snapshot with:

```powershell
.\.venv\Scripts\python.exe scripts\query_instrument_registry.py --ticker AAPL --date 2026-08-14
```

## 4. Legacy Massive source-file import

The legacy Chart Monitor derived Parquet files are not trusted as ATLAS canonical
history. Original Massive `.csv.gz` source files *are* useful and can be imported
without downloading them again.

Example daily import:

```powershell
.\.venv\Scripts\python.exe scripts\import_legacy_massive_files.py `
  --source "D:\OldChartMonitor\data\raw\day_aggs" `
  --dataset day
```

Minute import:

```powershell
.\.venv\Scripts\python.exe scripts\import_legacy_massive_files.py `
  --source "D:\OldChartMonitor\data\raw\minute_aggs" `
  --dataset minute
```

Every candidate file is gzip/CSV/schema validated before promotion. Valid imports
are registered in the Phase 2 ingestion manifest so later sync planning recognizes
them as complete. Existing ATLAS files are never replaced by different content
unless `--replace-existing` is explicit.

## 5. Historical lake audit

A fast existence/coverage audit:

```powershell
.\.venv\Scripts\python.exe scripts\audit_historical_lake.py `
  --start 2021-01-04 `
  --end 2026-08-14 `
  --json-out research\reports\historical_lake_audit.json
```

Add `--deep-validate` only when a full gzip CRC/schema pass is wanted. Deep
validation reads every provider file and is intentionally more expensive.

The report independently measures:

- provider daily coverage
- provider minute coverage
- canonical 1d coverage
- canonical 1m coverage
- derived 15m, 1h, and 4h coverage
- quarantine sessions/symbols
- tracked disk bytes

## 6. Resumable historical build

Materialize whatever provider files are already available:

```powershell
.\.venv\Scripts\python.exe scripts\build_historical_lake.py `
  --start 2021-01-04 `
  --end 2026-08-14
```

Download missing provider files first, then materialize:

```powershell
.\.venv\Scripts\python.exe scripts\build_historical_lake.py `
  --start 2021-01-04 `
  --end 2026-08-14 `
  --download-missing
```

Daily data is materialized before minute data for each session so Phase 3 symbol
quarantine propagates to 1m/15m/1h/4h data. The Phase 2 and Phase 3 manifests remain
the authoritative idempotency records; the historical build checkpoint records
range-level progress. Restarting the same range therefore skips completed work.

For an initial performance test, use a safety cap:

```powershell
.\.venv\Scripts\python.exe scripts\build_historical_lake.py `
  --start 2026-08-03 `
  --end 2026-08-14 `
  --max-sessions 3
```

## 7. Provider conflicts remain quarantined

Reference identity does not magically resolve ambiguous flat-file rows because
Massive aggregate flat files contain ticker text but no FIGI. If the same ticker
contains incompatible price histories in one source session, ATLAS continues the
Phase 3 policy: quarantine the entire ambiguous ticker/session and never guess a
winner.
