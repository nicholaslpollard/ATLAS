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
snapshot unless the reference transformation contract changes or `--force` is
supplied.

Resolve a symbol against a snapshot with:

```powershell
.\.venv\Scripts\python.exe scripts\query_instrument_registry.py --ticker AAPL --date 2026-08-14
```

### Provider ticker case is significant

Massive follows SIP ticker formatting and uses a lowercase `p` in preferred-share
symbols. ATLAS therefore preserves ticker case exactly apart from surrounding
whitespace. For example, `TPC` and `TpC` are separate securities, as are `BCPC`
and `BCpC`.

Canonical market bars, reference snapshots, ticker fallback identities, registry
lookups, quarantine records, and DuckDB symbol queries all use this exact
provider-native symbol contract. User-facing search can later offer aliases or
case-insensitive suggestions, but those conveniences must never alter canonical
identity or joins.

## 4. Historical source policy — fresh ATLAS download

The official ATLAS historical-build path is a fresh download from Massive. Legacy
Chart Monitor raw and derived data are not inputs to the normal ATLAS build.

This gives every historical ATLAS source object one provenance chain:

```text
Massive remote inventory
  -> exact missing-file plan
  -> atomic download
  -> gzip/schema validation
  -> SHA-256 + ingestion manifest
  -> canonical normalization
  -> quality gate
  -> session-aware derived bars
```

The legacy importer remains in the repository only as an optional disaster-
recovery utility. It should not be used for a normal clean build.

Before a large backfill, inspect the exact Massive inventory and download size
without writing files:

```powershell
.\.venv\Scripts\python.exe scripts\sync_missing_massive_data.py `
  --dataset daily `
  --start 2021-01-04 `
  --end 2026-08-14 `
  --dry-run
```

```powershell
.\.venv\Scripts\python.exe scripts\sync_missing_massive_data.py `
  --dataset minute `
  --start 2021-01-04 `
  --end 2026-08-14 `
  --dry-run
```

The dry-run reports exchange sessions, remote availability, files already complete,
planned downloads, provider-reported bytes, and free space on the drive containing
ATLAS. Raw download size is only part of the final footprint because canonical 1m
and derived 15m/1h/4h Parquet are also retained.

## 5. Optional legacy recovery import

`scripts/import_legacy_massive_files.py` can validate and register existing Massive
`.csv.gz` files if a future recovery situation makes that useful. It is not part of
the clean ATLAS migration plan and should not be run unless explicitly chosen.

## 6. Historical lake audit

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

## 7. Resumable historical build

Download missing provider files from Massive and materialize them:

```powershell
.\.venv\Scripts\python.exe scripts\build_historical_lake.py `
  --start 2021-01-04 `
  --end 2026-08-14 `
  --download-missing
```

The Phase 2 ingestion manifest and Phase 3 materialization manifest are authoritative
for idempotency. A stopped or failed build is restarted with the same command;
current units are skipped and only missing/stale work is retried.

Daily data is materialized before minute data for each session so any genuine
exact-symbol quarantine propagates to 1m/15m/1h/4h data. The historical-build
checkpoint records range-level progress but does not replace the per-file manifests.

For an initial performance/safety test, use a session cap:

```powershell
.\.venv\Scripts\python.exe scripts\build_historical_lake.py `
  --start 2026-08-03 `
  --end 2026-08-14 `
  --download-missing `
  --max-sessions 3
```

## 8. Session-envelope facts remain canonical

ATLAS retains provider minute observations even when they fall outside the modeled
04:00–20:00 ET trading envelope. Those rows are labeled `closed`, generate a
non-blocking quality warning, and are excluded from 15m/1h/4h derived trading bars.
A minute whose `window_start` is exactly 20:00 ET is therefore canonical provider
data but is not an after-hours trading bar.

## 9. Genuine exact-symbol conflicts remain quarantined

The August 14 BCPC/TPC anomaly exposed an ATLAS normalization bug rather than a
Massive duplicate: uppercasing provider tickers had collapsed `BCpC` into `BCPC`
and `TpC` into `TPC`. That is now fixed by preserving provider-native case.

Quarantine still applies when two materially different rows share the same exact
case-sensitive provider symbol and canonical bar key. Because Massive aggregate
flat files contain ticker text but no FIGI, ATLAS still refuses to guess a winner
for a genuine exact-symbol conflict.
