# ATLAS Hybrid Historical Options Database — V1 coverage catalog

Status: **SOURCE-ONLY CATALOG IMPLEMENTED; ACQUISITION AND SIMULATOR INTEGRATION NOT IMPLEMENTED.**
Date: 2026-10-23.

## Objective and constraints

The long-term goal is a reusable local historical option research library spanning
up to ten years and expanding across the full eligible research universe as
strategies need historical option quotes, bars, contract metadata, volume,
open interest, Greeks, implied volatility and intraday exit evidence.
The 815-symbol 09:35 CALL source demand and the 411-week SPY CALL+PUT
options-native study remain independent.

The operator measured D: **228.74 GiB free** and **1.86 GiB existing options
files** on 2026-10-23. Preserve the D:-bound data/options namespace and
existing 120 GiB candidate-options quota, 190 GiB total secondary acquisition
budget, 40 GiB free-space warning and 25 GiB minimum free-space guard.
No fallback writes to the C: stock/runtime volume.

The economic target is 30–60 days of ThetaData Standard acquisition, with
*older, harder-to-substitute* history and high-reuse surfaces prioritized first.
Feasibility for a broad ten-year universe is **not yet measured**.
Later incremental acquisition may use cheaper sources only when field coverage,
timestamp semantics, data precision and source identity satisfy the precise
simulation need.

## Latest retained hourly source

The operator ran exactly one hourly SPY source canary on 2025-06-09,
both rights, 09:30–16:00 ET, max_dte=45, strike_range=2. The response
contained **840 rows**, **zero out-of-range-DTE rows**, 201,148
SDK-normalized JSON bytes and 12,121 gzip-9 estimated bytes.
It was retained under:

    data/options/provider_qualification/thetadata_hourly_spy_v1/
      b8646235fede47d8/904e871723e54ad88a2de5a71d92abbd/

The original response and receipts are on the user's workstation; only terminal
output has been supplied in chat. The source remains DIAGNOSTIC_NO_PROMOTION.
The separate at-time 2025-06-09 source remains rejected: 144 of 264 quotes
exceeded its requested expiration range. Do not conflate the two endpoints.

## V1 provider-free implementation

- The module packages/data/hybrid_options_coverage_catalog_v1.py explicitly
  verifies **one selected original hourly summary.json** along with its
  original attempt record, original source receipt, full SHA-256 raw body,
  canonical JSON representation, report fingerprint, reported row count,
  observed contract/timestamp keys and independently measured gzip length.
- The operator entrypoint scripts/index_hybrid_options_coverage_v1.py defaults
  to **read-only verification**. The optional flag --write-catalog registers
  the exact source, idempotently, in a DuckDB file on D:
  data/options/hybrid/coverage_catalog_v1.duckdb.
- The source_units table records query, source SHA, receipt, status and
  query-completeness flags. observed_quote_keys stores the observed
  underlying, expiration, strike, CALL/PUT and time identity. Only pointers
  and bounded identity metadata are indexed. No original raw bytes are copied.
- Registration refuses modified receipts, invalid identities, duplicates
  or altered raw data. Re-running verified registration does not create
  duplicate rows.
- source_present=True means **an observed source is locally indexed**,
  not that its full query window is complete. source_status remains
  RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED; query_coverage_proven and
  simulator_ready remain **False**.
- The catalog is NOT an acquisition scheduler, historical quote acceptance
  gate, option fill, economic return model, or LIVE/PAPER simulator. It makes
  **zero market-data or broker calls** and reads no protected outcomes.

## V1 local workstation handoff

After the versioned PR is green and merged, pull main and run a
provider-free *preview*:

    .\.venv\Scripts\python.exe -m scripts.index_hybrid_options_coverage_v1 --summary "data/options/provider_qualification/thetadata_hourly_spy_v1/b8646235fede47d8/904e871723e54ad88a2de5a71d92abbd/summary.json"

If the exact 840-row source validates, run the same command with
--write-catalog to register without another paid request. Paste full
terminal output. This is a new catalog file, not a rewrite of sources.

## Future implementation stages

1. Qualify hourly source completeness and timestamp semantics separately
   from merely observing rows. Never infer a 09:35 executable quote from 1h.
2. Extend the registry to independently accepted legacy EOD, at-time,
   quote, open-interest, volume and contract metadata sources while
   preserving original acceptance and PIT boundaries.
3. Write immutable losslessly compressed archives with SHA receipts and
   compact Parquet query projections. The current 12,121-byte gzip value
   is **a measurement, not actual compressed-at-rest storage**.
4. Build a missing-data requirement planner for each frozen strategy:
   universe, as-of decision, data type, symbol/date/contract, window,
   observation resolution, DTE, holding path, and accepted source priority.
5. Add an explicitly authorized, quota-aware, resumable acquisition
   coordinator with durable attempt records, deduplication and no silent
   retry of unknown provider outcomes.
6. Require frozen complete source manifests before running backtests;
   keep simulation as a separate, reproducible local stage.
7. Measure historical population coverage, compressed disk growth,
   vendor throughput and cache reuse across independent research windows.

## Lower-cost incremental alternatives

- Alpaca Basic: free indicative options feed, options history since February
  2024. An indicative price is not interchangeable with historical OPRA NBBO
  for strict execution research.
- Massive Options Basic: $0/month advertised, two years history,
  five API calls/minute, EOD/reference/minute aggregate features; no
  comparable historical bid/ask quote feed at this tier.
- ThetaData Value: documented 2020-forward historical quote/OHLC/open-interest
  access with lower granularity than Standard; later budget and actual
  remaining gaps will determine viability.
- Every replacement source must retain provider identity and separate
  acceptance status rather than silently inheriting ThetaData source claims.
