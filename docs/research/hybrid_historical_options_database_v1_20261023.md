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

## V1 operator acceptance: completed 2026-10-23

The operator ran the non-network preview followed by an explicit catalog
registration. The original source hash and raw receipts passed, resulting
in **840 observed quote records across 120 distinct option contracts**.
Catalog file: `data/options/hybrid/coverage_catalog_v1.duckdb`;
source fingerprint:
`606ee2f25dcbaa2c017c04cd2c703d8e6784cc9c7d8ccb807319ed7455415f90`.
Registration reported `catalog_inserted=True`,
`exact_source_present=True`, `simulator_ready=False` and
**zero ThetaData/broker requests**. The original source is not promoted
to full historical-coverage evidence by this registration.

## V2: Offline exact-query missing-source planner

A separate provider-free planner
`packages/data/hybrid_options_gap_planner_v1.py` and operator CLI
`scripts/plan_hybrid_options_source_gaps_v1.py` now compare explicitly
declared option-history-quote needs against V1 DuckDB `source_units`.
Inputs are bounded to **64 individual requirement uses** with a strict
source-query schema: underlying, trade date, expiration wildcard, right,
1h/1m/1s interval, observation-window start/end, max DTE and strike range,
plus named strategy and intended use.

The planner deduplicates **identical provider queries across different
strategies**, but will not infer that hourly observations satisfy minute
entry/exit history, or that SPY data satisfies QQQ, or that one date supplies
a different year. A known source is reported as
`EXACT_SOURCE_OBSERVED_UNQUALIFIED`, **never simulator-ready**;
unrecorded demands become `MISSING_EXACT_LOCAL_SOURCE`, meaning the
local catalog lacks this precise source, not that the provider lacks it.
No automated provider request or accepted acquisition worklist is created.
The V1 catalog remains unchanged.

After a tested green merge, run provider-free:

    .\.venv\Scripts\python.exe -m scripts.plan_hybrid_options_source_gaps_v1 --demo

The built-in demo has **five strategy uses of four distinct quote queries**:
two uses of the exact saved SPY 2025-06-09 1h quote source,
one SPY minute-management requirement, one QQQ hourly requirement
on the same day, and one older SPY hourly requirement.
Given the operator's previously registered V1 source, expect one
`EXACT_SOURCE_OBSERVED_UNQUALIFIED` query with 840 observed rows,
three `MISSING_EXACT_LOCAL_SOURCE` query identities and zero
simulation-ready source sets. Paste full terminal output.

The CLI also supports `--requirements FILE` with JSON:

    {
      "contract": "atlas-hybrid-options-source-requirement-batch-v1",
      "requests": [{
        "strategy_key": "MY_SPY_RESEARCH",
        "purpose": "discovery",
        "query": {
          "symbol": "SPY", "date_et": "2025-06-09",
          "expiration": "*", "right": "both", "interval": "1h",
          "start_time": "09:30:00", "end_time": "16:00:00",
          "max_dte": 45, "strike_range": 2
        }
      }]
    }

No existing quote source is modified or re-opened. Only catalog metadata is
read, and no downloaded price bars, option quotes, source receipts, protected
outcomes, broker APIs, market-data methods or simulator positions are opened.
The next separately versioned milestone is more general source registration,
lossless compressed storage and precisely qualified coverage/readiness.

## V2 operator acceptance: completed 2026-10-23

The exact-query planner was executed against the registered V1 catalog.
It reported `requirements=5`, `unique_queries=4`,
`deduplicated_uses=1`, `local_source_diagnostics=1`,
`missing_exact_local_sources=3`, and `simulator_ready=0`.
The SPY 2025-06-09 1h CALL+PUT source matched 840 observed rows.
The separate SPY 1m management, QQQ hourly and 2018 SPY hourly scopes
were absent from the **local** catalog; provider availability has not
been inferred. No new API requests or file downloads occurred.

## V3: Immutable compressed source archive (one exact source)

A provider-free archive module
`packages/data/hybrid_options_lossless_archive_v1.py` and operator
entrypoint `scripts/archive_hybrid_options_hourly_source_v1.py`
use the already registered source ID
`606ee2f25dcbaa2c017c04cd2c703d8e6784cc9c7d8ccb807319ed7455415f90`.
The default mode only previews a lossless gzip-9 mtime0 compressed
representation and verifies the original source, receipt and catalog.
Pass `--write-archive` to write the compressed bytes **once** to the
D:-bound `data/options/hybrid/source_archive_v1` directory with
a separate SHA-256 and source-identity receipt. Writes are immutable,
original evidence remains intact, and a repeat call verifies the
existing archived bytes without re-creating them.

The original canonical JSON is retained, so the first pilot does
**not** reclaim disk space. It measures actual bytes-at-rest and proves
round-trip integrity, which are prerequisites for later introducing
compressed originals for newly acquired datasets. Its archive is
a source-data cache, not verified complete historical coverage or
executable quote data. Gaps from V2 remain gaps.

Following green CI and merge, preview without writing:

    .\.venv\Scripts\python.exe -m scripts.archive_hybrid_options_hourly_source_v1

If preview reports the 840-row registered SPY source and round-trip
proof, use an explicit write flag to create the immutable pilot
copy:

    .\.venv\Scripts\python.exe -m scripts.archive_hybrid_options_hourly_source_v1 --write-archive

Both modes make **zero** ThetaData, broker, outcome or simulation calls.
The write mode checks 40 GiB free headroom and refuses inconsistent
source/receipt pairs or an altered catalog. Existing source files,
strategies and protected outcome evidence are unchanged. No broader
acquisition or archive migration is authorized by this milestone.
