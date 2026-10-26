# ATLAS Hybrid Historical Options Database — V1 coverage catalog

Status: **V15 SOURCE-LINKED CAUSAL SPY QUOTE RESEARCH ACCEPTED (39 TESTS; 436 EXPERIMENTAL CALL/PUT PAIRS, 393 PASSING EXPLORATORY 60S SPREAD SCREEN). V16 MERGED PR #382, POST-MERGE CI GREEN; FIRST WORKSTATION --RUN BLOCKED IN OFFLINE PREFLIGHT BY MIXED-BRANCH GLOBAL-PRIORITY CHECK (30/30 TESTS PASSED). CORRECTION ADDS REALISTIC PRIORITY-GAP REGRESSION; PROVIDER CALLS=0 IN FAILED RUN; SIMULATOR REMAINS BLOCKED.**
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

After inspection, the operator may separately issue \`--reserve\` only with a frozen \`--requirements FILE\` batch (\`--demo --reserve\` is rejected), which
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


## V7 operator acceptance and V8 one-attempt provider interface (2026-10-24 ET)

The operator completed V7 acceptance with 85/85 targeted hybrid tests.
V7 recognized 5 uses / 4 unique exact queries and deduplicated 1 use.
The same SPY 1h 2025-06-09 local source is independently verified in
V4 and V6 but counts as only 1 existing query. Of three exact gaps,
2018 SPY 1h and 2025 QQQ 1h were eligible for offline reservation; 2025
SPY 1m was adapter-blocked. The preview created **zero reservations** and
made **zero provider, broker or simulator calls**. Free D: headroom was
228.73 GiB; conservatively safe additional storage was 119.70 GiB,
existing candidate-cache use 0.298 GiB, hybrid subtree 0.00273 GiB.
These figures are measured policy-constrained capacity, not a ten-year
dataset size projection.

V8 installs a single-request, **explicitly gated** provider interface.
Preview is always free of provider calls:

    .\.venv\Scripts\python.exe -m scripts.run_hybrid_options_single_provider_attempt_v1 --demo

A future paid execution requires *all* of: a non-demo frozen
\`--requirements FILE\`, explicit 64-hex \`--query-id\`, an already
indexed exact V7 \`RESERVED_NO_PROVIDER_CALL\` receipt, current headroom,
verified local source absence, matching hourly adapter, plus
\`--authorize-paid-single-hourly-request\` and
\`--acknowledge-no-retry-after-ambiguous-attempt\`. No paid execution is
performed by PR tests or by the operator acceptance preview.

The controller writes a content-addressed immutable
\`POSSIBLY_DISPATCHED_NO_RETRY\` marker under
\`data/options/hybrid/provider_attempts_v1\` BEFORE the isolated SDK
request. If the process crashes between marker and provider call, the
marker conservatively blocks retry until a separately reviewed manual
reconciliation. If the provider returns, V8 verifies the canonical
ThetaData response envelope, delegates direct gzip-at-ingestion indexing
to V6, and records an immutable terminal receipt; explicit empty/no-data
and ambiguous timeout/storage failures remain diagnostic. No terminal
state grants full coverage, causal replay, fills, strategies or
simulator readiness. There is no bulk loop or automatic retry in V8.

The next stage after independent V8 workstation acceptance is
preparing an actual 10-year priority-sorted acquisition manifest
from the two existing frozen research demand branches, with exact
provider adapter scope and storage budgets. Real paid requests require
a separately explicit command after the batch is frozen and reviewed.


## V8 workstation acceptance and V9 historical source-demand inventory (2026-10-24 ET)

V8 operator acceptance passed all 100 selected V1–V8 regression tests
in 16.46 seconds. The existing V6 gzip source was independently recovered:
840 SPY quote observations, status OBSERVED_ONLY, simulator_ready=False.
The V7 demo recovered 5 uses/4 unique exact request scopes, of which one
SPY source is already verified under both V4 and V6, two other hourly
queries were offline reservation candidates, and one SPY minute query
was blocked by missing exact adapter. No reservations were written and
no provider or broker calls, outcomes or simulations occurred.
D: free: 228.73 GiB; conservative safe additional capacity 119.70 GiB;
candidate cache 0.298 GiB and hybrid subtree 0.00273 GiB. V8 reported
the SPY 2018 and QQQ 2025 queries as NOT RESERVED, and blocked both the
existing hourly SPY local source and the unimplemented SPY minute adapter.

V9 addresses a distinct and material gap: V8's **full-session 1h quote
history** does not represent the original research entry clocks.
The two existing source plans demand:
- Weekly SPY options-native 10:00 ET CALL+PUT at-time quote surfaces,
  generated from the frozen 2018–2025 calendar specification.
- The separately frozen 9,455 underlying/date CALL candidate
  surfaces at **09:35 ET** during 2021–2025, DTE <=75,
  with wildcard expirations and no preselected strike range.

They both require \`/v3/option/at_time/quote\`, not V8's 1h historical
quote adapter. V9 preserves original endpoint and params, lineage
fingerprint, CALL/PUT choice, decision time, max DTE, strike range and
case source identity, and freezes qualification anchors separately from
chronological remainder. Every entry explicitly states that its
corresponding at-time adapter has NOT yet been qualified for acquisition.
A 1h SPY archive therefore neither fills nor satisfies a 09:35 or
10:00 at-time data gap.

A provider-free, read-only pilot preview is:

    .\.venv\Scripts\python.exe -m scripts.plan_hybrid_options_frozen_research_demand_v1

The full two-branch preview additionally needs the operator's original,
independently frozen source-plan file on D::

    .\.venv\Scripts\python.exe -m scripts.plan_hybrid_options_frozen_research_demand_v1 --candidate-plan data/options/manifests/thetadata_candidate_surface_source_plan_v1_<FINGERPRINT16>.json

No 9,455-row source plan is embedded in Git; the workstation-owned immutable
plan is validated against its exact 64-character content fingerprint,
frozen contract and all source row identities. The explicit optional
\`--write-manifest\` flag (available only with the full candidate plan)
creates an immutable bounded source-demand JSON file on D:; it does NOT
create reservations, make provider calls, qualify at-time quotes, or
run a simulator. This frozen inventory is *research-selected demand*
spanning 2018–2025, NOT ten years of all contracts for every security.
Broader universe and management data requirements must be separately
designed and measured.

V9 workstation acceptance should exercise the weekly-only preview first,
then validate the actual frozen 9,455-query source plan. The next stage is
building a separate explicitly gated ThetaData at-time adapter, resolving
the old 264-row out-of-DTE diagnostic without changing the scientific
contract, and independently validating observed 09:35/10:00 timestamps
before any actual paid broad acquisition.


## V9 operator acceptance and V10 exact SDK source gate (2026-10-25 ET)

Operator V9 workstation checks: 113/113 V1–V9 hybrid tests. The independent
frozen SPY pilot produced 411 weekly CALL+PUT requests at 10:00 ET,
2018–2025; the original externally persisted source-plan receipt
independently verified 9,455 underlying/date CALL 09:35 requests,
2021–2025, with 15 multiyear qualification anchors. Combined 9,866
unique at-time queries retained full original request identities. The
combined read-only manifest fingerprint was
\`138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63\`.
V8's exact hourly quote demo remained unreserved/no-call and the V5
simulator gate continued to block. No provider calls, reservations,
simulations or source writes were made.

V10 is the *offline exact at-time SDK mapping and saved-source admission
diagnostic*, implemented in:
- \`packages/data/hybrid_options_at_time_source_gate_v1.py\`
- \`scripts/inspect_hybrid_options_at_time_source_gate_v1.py\`
- \`tests/test_hybrid_options_at_time_source_gate_v1.py\`

It maps a precise, V9-fingerprinted provider query to the pinned
\`option_at_time_quote_surface\` wrapper without actually invoking
the wrapper, SDK client or provider. Full original quote responses
supplied to the pure validator are checked for immutable body/SHA
equivalence, pinned SDK provenance, required fields, exact CALL/PUT and
root, nonexpired dates and requested maximum DTE, historical Eastern
clock causality, duplicate contracts, valid prices, sizes and quote
conditions. A row beyond requested DTE quarantines the *entire*
response, retaining all original observations. It never silently
projects a 45-DTE subset or represents filtered quotes as actual
provider-requested data.

Preview with zero provider calls, reading the frozen weekly calendar only:

    .\.venv\Scripts\python.exe -m scripts.inspect_hybrid_options_at_time_source_gate_v1

Explicit offline replay of the **already-retained** 2025-06-09
10:00 SPY failed canary:

    .\.venv\Scripts\python.exe -m scripts.inspect_hybrid_options_at_time_source_gate_v1 --replay-retained-spy

Replay first independently verifies the original retained canary's
summary, query receipt and SHA/body through the existing audit module,
then matches its frozen original quote query to the precise SPY V9
entry. It checks all source rows; historically the canary returned
264 original quotes, of which 120 were within requested max_dte=45 and
144 exceeded it. No provider call, fallback, source rewrite, simulated
fill or new qualification authority is possible.

The direct ThetaData Python SDK 1.0.12 method's \`max_dte\`
forwarding remains **not proved** by the original static audit. V10
does not claim to determine whether SDK or server caused the prior
over-DTE rows. Actual at-time paid source acquisition remains separately
gated and unimplemented. The next stage must avoid duplicative
calls; any future one-request qualification should use new immutable
pre-dispatch attempt evidence, exact method semantics and independent
storage/resource checks, never bulk-autorizations or retroactive source
promotions.


## V10 operator source replay and V11 guarded 2021 qualification (2026-10-25 ET)

User verified the exact original retained 2025-06-09 SPY at-time
10:00 ET source under V10: complete unchanged SDK body SHA-256
\`cbe1b2d9a48b6812448a6b0a2f394fab21a9ca04dec550e67558a33b155e8ecf\`,
264 rows; 120 within requested max_dte=45 and 144 beyond.
V10 status correctly \`QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION\`;
no provider call or price promotion occurred. The accepted V9 demand
manifest was immutably written to
\`data/options/manifests/hybrid_exact_at_time_research_demand_v1_138234eb2276409a.json\`;
its full fingerprint remained
\`138234eb2276409ae641f6e40d7f6eb3c779502ffb5459b612e0dbc439cb4b63\`.
9,866 exact at-time quote scopes and all scientific clocks/rights remain
in the file. The V5 simulator gate remained blocked and no provider,
broker, reserve, trade or outcome access occurred.

V11 (under CI review) adds a **single-attempt only**, globally capped
2021 candidate-qualification interface, not a bulk source acquisition
campaign. It requires re-validation of both complete original frozen
plans, strict at-time SDK mapping, a 2021 09:35 CALL qualification anchor
and existing research D: storage headroom. It never re-requests the
known rejected 2025 SPY canary.

Operator preview is ZERO-CALL:

    .\.venv\Scripts\python.exe -m scripts.qualify_one_hybrid_at_time_option_source_v1

Use an explicitly supplied \`--manifest\` and \`--candidate-plan\` only
when the existing canonical names differ. Its default exact paths refer
to the already accepted V9 full manifest and accepted source-plan receipt.

Actual paid execution (not authorized by CI/acceptance) additionally
requires the exact full \`--query-id\`, and ALL of the independent flags:
\`--authorize-one-paid-qualification-call\`,
\`--acknowledge-sdk-max-dte-unproven\`, and
\`--acknowledge-permanent-no-automatic-retry\`. The controlling method
writes an immutable global once-only receipt *before any provider call*;
after ambiguous timeout/process crash it blocks **all** other V11
requests. A returned nonempty source is stored in its entirety in one
lossless gzip-9 archive on the external options storage, with
cryptographic readback. The original full source is never silently
projected to 45/75 DTE, and all V10 diagnostics remain non-executable.
No V6/strategy/holdout/simulator/PAPER/LIVE authority is granted.
Actual source-semantic proof, completeness and data throughput are
still needed before authorizing historical acquisition of 9,866 scopes.


## V11 paid AAL 2021 call and V12 user-authorized unattended operation (2026-10-25 ET)

The user ran the V11 AAL single at-time source call. The input was
the existing frozen 2021-11-30 AAL 09:35 ET CALL max_dte=75 no-strike-range
request ID
\`15ac1c4ac389a5b4893530b954f40bc6ed4ee7d4614e1c606aa53a8a920eafe4\`.
The provider/worker call returned a nonempty SDK-normalized original
source that was successfully stored as complete lossless gzip; the V10
gate classified it as \`SOURCE_ARCHIVED_QUARANTINED_DTE\` /
\`QUARANTINED_OUT_OF_SCOPE_DTE_NO_PROJECTION\` because some expiration
dates exceeded the requested 75 calendar days. No source promotion or
simulator access was granted. V11's immutable global once-only marker
and terminal proof were created: DO NOT rerun V11 paid flags or overwrite
these records. User explicitly instructed ATLAS to eliminate interactive
per-call authorizations and to allow continued provider data requests.

V12 preserves exact original V9 source demand and removes *per-call
authorization friction* in favor of a normal provider-acquisition command.
Read-only original-AAL receipt+gzip re-audit:
\`python -m scripts.run_hybrid_options_unattended_campaign_v1\`.
The module rechecks the original V9 full manifest and 9,455 source plan,
V11 immutable marker/terminal receipts, the AAL source SHA and lossless
gzip restore, computes DTE bucket counts and then previews the remaining
9,866-source queue. Known existing AAL 2021 and saved SPY 2025 at-time
source queries are skipped; they are never requested again.

A subsequent \`--run\` starts provider acquisition with no consent flags,
typing prompts, or fixed lifetime request count. Optional \`--max-calls N\`
controls a single work session; omission means all remaining requests in
the pinned frozen scope. Each individual query saves an immutable
pre-dispatch marker (even on timeout/forced process interruption) and a
terminal receipt, so resuming never resubmits the same query after
an ambiguous result. Nonempty quotes are stored as deterministic gzip-9
in the query-keyed V12 D: archive root and verified by SHA-256 and
bounded decompression. Source schema/DTE issues are recorded as
non-executable diagnostics, not silently filtered executable sources.
The runner rechecks D: free-space and joint options research quota before
every new query, and stops on transport/storage failures.

The provider documentation states max_dte should apply an inclusive
calendar-day DTE limit; both saved historical canaries returned rows
outside it. This may be an SDK-forwarding or server-side problem.
V12 **does not claim to have fixed** that issue; it captures original
source material for independent investigation. Query count 9,866 is
the frozen *selected decision-time entry research* scope, not a complete
ten-year all-symbol all-contract 1h local options database or management
exit data.


## First unattended V12 SPY batch and V13 full original-source census (2026-10-25)

The workstation's initial fully unattended 10-provider-call batch completed
without prompts, retries, interruptions or provider/SDK errors. V12 wrote
10 immutable original compressed source archives and 10 terminal receipts;
**all 10** original quote sources returned some expirations beyond their
frozen max_dte=45 days. The 2021 AAL qualification source remained separate
and unchanged. A read-only V12 queue replay verified 9,854 remaining exact
research queries, zero ambiguous deliveries, 10 new V12 source IDs archived,
two historical sources excluded from re-acquisition and safe additional
119.700 GiB on the D: research storage at the last inspection.

The AAL original source replay fix was operator accepted: 16 regression
tests passed, 464 unchanged quote rows, 238 with 0–75 DTE, 226 with
>75 DTE, 16 expirations, 113,899 original bytes, 9,345 compressed
bytes, SHA256
\`6ff575bde70b7eaec3ab95854f99cf47d868517ed0d437982fb78677348b1a59\`.

V13 adds read-only independent research diagnostics. Default command:

    .\.venv\Scripts\python.exe -m scripts.audit_hybrid_options_saved_scope_quality_v1

The tool derives per-archived-request and aggregate counts of observations
within/outside their exact frozen DTE limits, invalid fields or future
quote timestamps, un-crossed positive two-sided NBBO quotes, oldest quote
age, expiration buckets, raw and losslessly compressed bytes. Each original
source is cryptographically replayed against existing immutable receipts;
no local filtered source is written, no SDK client or provider call made
and no quote is advanced to strategy/simulator authority.

ThetaData's published v3 docs for both REST and Python at-time option
quotes describe \`max_dte\` as an inclusive calendar-day expiration cap.
Saved 2025 SPY, 2021 AAL and 10 SPY archived returns violate that
description. These observations are evidence of parameter-scope
nonconformance, NOT proof of a specific SDK or server defect. Subsequent
work should compare actual in-scope quote quality and evaluate an
independently versioned locally scoped diagnostic view retaining the
complete provider original; it must not replace originals or claim full
chain coverage. Bulk collection may continue later without per-call
authorizations, but should not be run blind without the scope census.


## V13 operator result and V14 locally derived source-index-only view (2026-10-25)

The operator's full V13 quality replay independently verified 10 original
SPY 10:00 ET both-right sources after 20 targeted tests passed. All original
response cryptographic hashes matched and every one of 2,744 original quotes
had required causal timestamp, valid identity/expiration and quote fields.
Zero invalid rows; all 2,744 had positive two-sided displayed sizes.
1,336 observations were within requested 0–45 calendar-day DTE,
1,408 were beyond it. No provider call was made by V13.
Source-original 675,058 JSON bytes were retained as 53,961 deterministic
gzip bytes (92.01% compression savings). Individual source oldest quote
staleness never exceeded 32 seconds. The ten source responses remain
diagnostic only. V12's frozen 9,866-request queue has two previously
saved external source queries, ten newly archived and 9,854 not attempted;
the historical AAL source remains 464 rows with 238 in-range and 226
over-range under the independent V11 acquisition path.

V14 generates a *derived, locally scoped original-row reference index*,
never falsely representing it as a ThetaData source file or a complete
historical option chain. Each immutable index stores only positions
into the verified complete original V12 canonical JSON response,
the original source body and gzip SHA, frozen V9 query identity,
original V12 terminal fingerprint, requested date/clock/right/max DTE,
exact included/excluded row counts, explicit diagnostic status and
simulator/PAPER/LIVE non-admissibility.

Offline read-only preview:

    .\.venv\Scripts\python.exe -m scripts.build_hybrid_options_derived_dte_index_v1

Explicit source-index-only D: write (no provider/broker calls):

    .\.venv\Scripts\python.exe -m scripts.build_hybrid_options_derived_dte_index_v1 --write-indexes

A repeated write verifies matching immutable sidecar bytes, never replaces
an existing file. Any new index fingerprint for the same original query
identity is treated as conflicting source semantics, and the operation
fails closed. Incomplete or invalid source quotes remain unindexable.
Do not substitute index-selected rows for the original provider result
or claim provider-side max_dte correctness, complete executable chains,
strategy validation, held-out result integrity or simulator readiness.


## V14 operator accepted and V15 read-only causal quote observation adapter (2026-10-25)

The operator completed V14 workstation acceptance with 28/28 relevant
unit tests, read-only index preview, local index write and repeat
immutable verification. The original sources were independently
rechecked against the accepted V9 frozen 9,866-request source plan.
Ten D:-bound source-linked index JSONs were written, totaling **26,167
bytes**. They point to **1,336 original in-0..45-DTE observations**
inside the ten V12 historical SPY CALL+PUT option quote archives, leaving
**1,408 original over-DTE observations** unindexed. The repeat write
verified all ten original sidecars and created **zero** new ones.
No old archive was edited, no new provider requests were made, and
**9,854 exact frozen query scopes remain unattempted**.

V15 connects this trustworthy positional evidence to a bounded in-memory
original-quote research reader and separate observed-chain diagnostic.
Every read revalidates exact V9 query, V12 original source SHA and
immutable terminal receipt, complete original JSON/gzip, and byte-identical
V14 local index fingerprint. It materializes exactly the indexed original
quote dictionaries in RAM, retaining original bid, ask, sizes, quote
conditions, timestamps, expiry, strike and option right. Nothing is
persisted as new pricing data. It assesses **observed** CALL/PUT
expiry-strike pairs at the historical decision clock, counts optional
14–45-DTE research-window observations, compares original displayed
bid/ask spread to mid against a 15% quality threshold and timestamp age
against a 60-second window. Those parameter checks are diagnostics only;
matching option pairs are not proof of a complete provider-native
options universe or valid executable fills. No entry/exit simulator or
strategy outcome data is read.

Use:

    .\.venv\Scripts\python.exe -m scripts.audit_hybrid_options_source_linked_research_v1

No ThetaData, broker calls, user prompts, source writes, source promotion,
protected outcomes, simulations or historical strategy decisions occur.
Outstanding dependencies include point-in-time underlying spot, original
chain completeness, historical OI and the issuer dividend publication
evidence needed by expiration-specific valuation; none are replaced or
inferred by the V15 quote diagnostics.


## V15 operator acceptance and larger V16 integrated acquisition/simulator-readiness cycle

The operator passed 39 V12–V15 targeted tests. The existing 10
V12 SPY 10:00 original at-time archived sources replayed to 2,744 original
quote observations, 1,336 0–45 DTE source-linked row references.
The V15 exploratory 14–45 DTE read found 872 observed quote rows and
436 same-expiration/same-strike CALL+PUT pairs, of which 393 satisfied
the V15 <=60s freshness and <=15% spread-to-mid observation screen.
These are not trades, complete option chains, underlying forecasts,
broker fills or simulator-ready input.

The user's priority is now fewer partial small engineering cycles and
faster collection during the active $80/month ThetaData Options Standard
subscription. V16 groups an enlarged SPY acquisition workflow, automatic
existing V14 sidecar indexing and native simulator-readiness assessment
into a single CI acceptance and workstation operation.

- V12 provider runner gains a strict \`allowed_origin\` gate and periodic
  provider-call progress summary; original immutable receipt semantics,
  SHA hashes and deduplication remain unchanged. It cannot accidentally
  proceed from the SPY pilot into the 9,455 unrelated 09:35 CALL sources.
- \`python -m scripts.run_spy_pilot_integrated_acquisition_v1\` defaults
  to provider-free coverage inspection. An \`--run\` execution collects
  all still-unattempted original SPY weekly 10:00 both-right entry
  quotes, with no interactive confirmations and optional \`--max-calls\`
  to bound a single session. It then verifies/creates SHA-linked original
  positional sidecars using the existing V14 contract.
- A separately callable read-only
  \`python -m scripts.review_spy_native_pilot_accelerated_readiness_v1\`
  audits exact 411 weekly source identities, distinguishes saved,
  failed, missing and independently retained 2025 SPY observations,
  applies the native frozen 30–45 DTE and 30s quote-age diagnostics,
  and plans original 10:00 both-right quote requests for all five
  following XNYS sessions after each weekly entry. Exact duplicate
  session requests are deduplicated; no exit quote acquisition/option
  fills are invented by the planner.
- Neither V16 script executes backtests, enables the V5 hybrid hourly
  simulator, substitutes V15 diagnostic pair counts for historical
  option fill authority, reads protected performance outcomes nor
  silently ignores missing PIT underlying spot, prior 20 economic
  returns, OI publication, contract deliverability, rates/dividends,
  IV/Greeks, executable order latency or account fees/lifecycle.
  Those independent prerequisites still block the frozen straddle
  simulator and are surfaced in the readiness report.


## V16 workstation no-provider preflight compatibility correction (2026-10-25)

The first integrated V16 `--run --progress-every 25` passed its 30 targeted workstation regression tests but stopped before entering the V12 downloader. The V16 SPY-only census incorrectly expected `priority=1..411`, whereas V9's immutable full 9,866-request manifest assigns globally unique priorities across both the 411 weekly SPY and 9,455 separate 09:35 CALL campaigns, with qualification anchors interleaved. This was a reader validation defect, not evidence of a ThetaData provider or source-receipt failure. The fix preserves the exact V9 priorities and original immutable source records, rejects duplicates/out-of-bounds values, and reports safe fixed exception codes and preflight/acquisition/index/readiness phase. Tests model the global priority gaps; no historical returns, provider calls, broker actions, source rewrites or simulations are performed by the correction. The paid SPY entry acquisition remains operator-pending.


## V17 bounded provider concurrency (development, not acquired evidence)

The existing ThetaData Standard subscription documents four account-wide concurrent requests. V17 adds an opt-in `--workers 4` to each original V12 and SPY-specific V16 acquisition CLI. Each network worker has its own existing thread-local isolated ThetaData Python-library subprocess. A single coordinator owns receipt and full-original gzip/SHA archiving so concurrent calls cannot independently write shared indexes or corrupt saved source identities. The same original 9,866 exact V9 manifest and V12 immutable start/terminal receipt contract apply; changes to the frozen query clock/right/DTE are prohibited.

Concurrency is capped at 4 outstanding requests, and shared safe storage is rechecked with a per-pending-response capacity reservation. A run-scoped `--max-calls` applies to all threads total, not per worker. Provider failure prevents more dispatch; already in-flight requests are still finalized, and a prior ambiguous ID is never silently redownloaded. Defaults remain sequential and any concurrent workload from *another* program must be excluded before using all four slots. No live provider calls or speed measurements were made in implementing this parallel option; the simulator continues to reject these diagnostic-only sources until separate source/PIT/execution qualification.


## 2026-10-26 full 400-SPY entry campaign and source-only geometry issue

The operator reported corrected V16 tests **44/44**, offline source/exit preflight success, and actual **400/400 new** historical SPY 10:00 both-right provider archive completions. All 400 were marked original out-of-requested-DTE diagnostics, none invalid; 410 V12 sources now have 410 immutable V14 positional index sidecars (400 created this run), referencing **53,652 original <=45-DTE rows**. The 2025-06-09 legacy SPY diagnostic remains outside the V12 archive count. The final in-memory source-linked 30–45-DTE research review blocked on `HybridSourceLinkedReaderError`, after acquisition and source index writing; no other ThetaData calls are necessary to investigate. Earlier read-only coverage before this run: 10 V12 indexed clocks, 328 native 30–45 DTE rows, 164 observed paired strikes, 145 passing 30s/15% research-only screens, 27 wide rows. The 410-clock post-run counts are not known yet.

Candidate mismatch: original V10/V13 quote/archive checks accept nonnegative zero-sided prices/sizes as observations but V15 incorrectly raises `NON_DISPLAYED_QUALIFIED_ROW` on research geometry. The V15 correction retains such original observations and adds `research_window_non_displayed_rows` without treating them as two-sided/liquid, altering historical original source, or certifying fills. A positive crossed market, duplicated contract, causal violation, or source-index integrity drift still stops. V16 now supplies source date/immutable query fingerprint and fixed reader code in its own error, when the failing exception is `HybridSourceLinkedReaderError`. No cause is asserted as certain until the operator's **provider-free** `run_spy_pilot_integrated_acquisition_v1` default readiness census passes or exposes a new exact failure. 411 SPY originals, the separate 9,455 CALL campaign, and 1,570 additional unique exit-review scopes remain distinct.

