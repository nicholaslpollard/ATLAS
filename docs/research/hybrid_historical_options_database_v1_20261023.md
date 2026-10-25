# ATLAS Hybrid Historical Options Database — V1 coverage catalog

Status: **V6 VERIFIED COMPRESSED SOURCE STORE WORKSTATION-ACCEPTED; V7 OFFLINE REQUEST QUEUE UNDER CI REVIEW; PAID ACQUISITION AND SIMULATOR INTEGRATION NOT IMPLEMENTED.**
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

## V3 operator acceptance and V4 compressed historical-source retrieval

Operator V3 acceptance (2026-10-23): preview and explicit compressed-archive
creation both completed successfully; source original **201,148 bytes**,
gzip-9 **12,121 bytes**, **93.97%** size reduction, **840 rows**,
`lossless_verified=True`, `archive_inserted=True`,
`simulator_ready=False`, **zero provider requests**.
The archive lives at the content-addressed file
`data/options/hybrid/source_archive_v1/0a/`
`0af1ad27857cbb1da8fdf51d272a1bd644e972f0d1b49bef29015b8192d91c21.json.gz`
with a separate immutable receipt at the same SHA stem.
The original canonical JSON is still stored, so this pilot does not
reclaim its original disk bytes.

V4 adds `packages/data/hybrid_options_archive_reader_v1.py`, a
source-only local compressed quote retrieval interface, and
`scripts/read_hybrid_options_archive_v1.py`, an operator audit CLI.
The reader fetches the exact catalog source identity and expected
observation keys, verifies the immutable archive SHA receipt, performs
**bounded** gzip decompression, checks the original canonical-body
SHA-256 and byte length, and cross-checks each quote's underlying,
expiration, strike, CALL/PUT and observed timestamp with its existing
indexed ordinal. It does **not reopen the original uncompressed quote
file** and cannot silently download missing data.

After green CI and merge, verify the actual compressed read:

    .\.venv\Scripts\python.exe -m scripts.read_hybrid_options_archive_v1

Expected on the accepted SPY source: **840 archived quotes**, **120
distinct contracts**, original byte length 201,148, compressed byte
length 12,121, diagnostic source status and `simulator_ready=False`.
The CLI reports observed clock bounds and CALL/PUT counts, not trade
performance or executable prices. Any missing/corrupted archive,
receipt, changed query status or key inconsistency fails closed.
This step makes no new ThetaData/broker requests, source writes or
strategy simulations.

The next major milestone is **generalizing verified source registration
beyond the single frozen SPY source**, along with using this reader for
compressed-at-ingestion source storage in an explicitly authorized,
storage/rate-bounded acquisition pipeline. Do not mistake V4 archive
retrieval for complete hourly sessions, minute-level exits, OI, Greeks
or simulator-ready historical fills.


## V5: Verified compressed-source simulation preflight (2026-10-24)

A separate provider-free preparation module,
packages/data/hybrid_options_simulation_preflight_v1.py, composes the
exact V2 requirement/gap planner and V4 immutable archive reader. Its CLI,
scripts/preflight_hybrid_options_simulator_v1.py, accepts the same explicit
bounded JSON requirement batch as V2 (or --demo) and reports all deduplicated
requests, verified original/archive hashes, observed quote counts, historical
local gaps, source status and simulation readiness.

The preflight reads each reused archived source at most once and rechecks
original bytes, receipt identity and catalog observation keys. Existing raw
uncompressed sources are not opened. Missing or corrupted archives are an
integrity failure and never silently become a new provider download.
V5 caps distinct archived sources verified per run at eight to bound memory
and decompression work.

The V1 source-only catalog is intentionally unchanged: the verified 840-row
hourly source remains diagnostic and cannot be used as a qualified 09:35
entry, complete holding/exit history, account simulation, or PAPER/LIVE
authority. The result has simulator_run_permitted=False,
frozen_simulation_dataset_created=False and explicit local missing-query
statuses. --require-ready exits nonzero when input readiness is unqualified;
there is no readiness override or V5 source-promotion path.

After green CI and merge, operator may run two independent offline checks
against the existing D:-bound catalog/archive:

    .\.venv\Scripts\python.exe -m scripts.read_hybrid_options_archive_v1
    .\.venv\Scripts\python.exe -m scripts.preflight_hybrid_options_simulator_v1 --demo

The second command should show 5 requirement uses, 4 distinct queries,
1 reverified original source archive, 3 missing local exact queries,
0 simulation-ready queries, 0 provider/broker requests and 0 simulations.
CI runs synthetic fixtures, not the workstation D: evidence. The future
acquisition coordinator must be explicitly budgeted/authorized and complete
sources independently qualified and bound into frozen replay inputs before
any historical strategy evaluation. Passed preflight is an integrity
diagnostic, not profit or simulator acceptance.


## V6: Generalized, compression-at-ingestion quote source store (2026-10-24; in testing)

A separate versioned source-store implementation can now index **different
underlyings, dates, rights and quote resolutions (1h / 1m / 1s)** in
`data/options/hybrid/source_store_v2.duckdb`, with immutable
content-verified gzip in `data/options/hybrid/source_archive_v2`.
This is source infrastructure, *not* new provider entitlement, actual
multi-symbol source acquisition, complete query coverage, executable quotes or
simulation authority. Existing V1-V5 DuckDB and archive receipts are unchanged.

Each registration validates a strict exact-session query, the original
SDK-normalized byte representation, complete source rows, underlying and
contract identities, aware timestamps, book schema, sizes and original
provenance. Observations outside DTE/clock bounds, crossed books and duplicate
identities are counted as **retained diagnostics**, not dropped. The original
request parameters and hashes bind archive and index. Even good diagnostics
are explicitly `RAW_VERIFIED_DIAGNOSTIC_UNQUALIFIED`,
`query_coverage_proven=False`, `simulator_ready=False`; importantly,
quote interval timestamps are **not assumed to be decision-time usable**.

For a controlled offline proof, V6 can independently verify the existing
V4 compressed SPY source, preview its generalized representation, then
separately import it into the V6 store **without a provider call**. This
creates one additional small compressed representation and index while
preserving the verified V4 original/archive. No historical options data is
silently deleted, and the first V6 import does not replace V4.
The command is provider-free by default:

    .\.venv\Scripts\python.exe -m scripts.index_hybrid_options_general_source_v2

After green PR CI/merge and successful preview, explicit one-source import:

    .\.venv\Scripts\python.exe -m scripts.index_hybrid_options_general_source_v2 --import-verified-v4

A repeated import verifies the existing bytes and is idempotent. Existing
same-query distinct source bodies are a conflict, never overwritten. Incomplete
archive/receipt pairs, modified compressed bytes, catalogue/row-identity drift,
and unqualified storage bindings fail closed without acquisition fallback.
The V6 source-store quota is capped at 120 GiB and also checks the 40 GiB
free-space reserve. Before broad acquisition, the coordinator must account
for *all* other candidate-cache usage against the shared quota; the V6
substore cap alone does not demonstrate total quota availability.

The next engineering stage is a frozen, precisely bounded missing-data
acquisition and catalog-reconciliation coordinator: enumerate exact requests
first, skip verified V6/V4 source identities, preserve ambiguous attempts,
and require explicit paid authorization before opening ThetaData. A separate
historical execution-source qualification gate and frozen complete paths
remain prerequisites for simulation. V5 continues to report the existing
V4 source as unqualified; generalized V6 source storage does not grant V5
simulator authority.


## V6 operator acceptance and V7 offline acquisition-reservation coordinator

Operator-provided V6 workstation acceptance (2026-10-24, America/New_York):
68/68 selected hybrid regression tests passed. The V6 one-source preview was
read-only. Explicit import preserved original V4 evidence and created the
second, generalized archive and DuckDB index for SPY 2025-06-09, 840 quote
observations / 120 observed contracts / zero requested-DTE violations /
zero duplicate observation keys, with exact gzip size 12,121 bytes and
restored canonical-body size 201,148 bytes. V5 simulator preflight still
found one diagnostic query and three local missing exact queries, with no
simulator authority. No provider, broker or simulation calls occurred.

V7 is a **bounded, offline-only precursor**, not an automated paid-data
ingester. The implementation is
\`packages/data/hybrid_options_acquisition_reservations_v1.py\` and
\`scripts/plan_hybrid_options_offline_acquisition_v1.py\`.
Given a V2-style, explicit JSON request batch (at most 64 uses),
it re-verifies exact query identities against both V4 archived receipts and
V6 generalized quote-source catalog, checks SHA/body hashes, individual
observation evidence and unchanged negative simulation authority,
and counts a mirrored V4/V6 observation as **one available query**.
A damaged indexed source fails closed instead of becoming new provider work.
The 5-use demo is intentionally *not* the 10-year acquisition manifest.

For newly missing queries, V7 requires an exact supported method:
ThetaData isolated worker \`option_history_hourly_quote_surface\` can represent
regular 09:30–16:00 ET full-session 1h CALL/PUT requests with
\`1 <= max_dte <= 75\` and \`0 <= strike_range <= 8\`.
All other intervals and windows are **blocked until a corresponding adapter
is implemented and tested**. Oldest sessions are considered first, without
consulting performance. The preview has no filesystem writes:

    .\\.venv\\Scripts\\python.exe -m scripts.plan_hybrid_options_offline_acquisition_v1 --demo

After inspection, the operator may separately issue \`--reserve\`, which
creates immutable, SHA-fingerprinted \`RESERVED_NO_PROVIDER_CALL\` receipts.
These are planning claims, not attempted calls or provider availability
evidence. Repeated calls recheck the original receipt and do not create
duplicates. An altered or ambiguous receipt is a hard stop.

Default worst-case disk reservation is 128 MiB per distinct eligible query,
up to a 512 MiB single-batch ceiling. V7 reuses the ATLAS secondary-storage
snapshot (min/warning free space and overall research budget), measures
uncategorized \`data/options/hybrid\` alongside the existing
\`options_candidate_cache\`, conservatively applies their *joint* 120 GiB
limit, and verifies/deducts **all** pending reservation receipts, including
prior batches, before allocating additional space. The ledger scan stops at
4096 receipts; it does not silently assume extra capacity. A reservation is
not a guarantee actual source storage will fit: later execution must
reinspect real disk headroom, source limits, query completeness, and the
provider attempt state independently.

The next version must implement separately authorized call attempts with
single-attempt receipts, durable unresolved outcomes, no automatic retry after
possible delivery, and integration with the generalized gzip-at-ingestion
store; later, minute/second history and separately verified holding/exit
quotes must be qualified before simulation. No broker, strategies, holdings
or protected outcomes are read by V7.
