# Accepted Stock Candidate Export V1 for MarketData — 2026-09-25

## Status

**SOURCE-ONLY EXPORT IMPLEMENTED / FIRST WORKSTATION DIAGNOSTIC COMPLETE / MERGE GATE PENDING.**
Contract: atlas-marketdata-accepted-stock-candidate-export-v1.

The prior chain planner and gated source cache are now connected to accepted
recurrent-successor stock evidence without inventing example opportunities.
The exporter calls the existing accepted successor conditioning/selected-replay
loader and hash-verifies its exact normalized DEVELOPMENT source receipts.
It opens **no** protected consumed-master or future-blind data, makes no
provider or broker call, and does not grant strategy, option-price or PAPER/LIVE
authority.

## Frozen first cohort

Default: calendar year **2025**, exactly the one lowest SHA-256-scored
eligible opportunity in each month with at least one qualifying case
(12 rows at most). The score hashes a fixed V1 salt and exact pre-existing
opportunity identifier. It is deterministic, independent of input row order,
news, options and realized trade outcome. The source population is the
already accepted walk-forward selected, comparable, daily LONG stock cases
with canonical tickers admissible under the frozen chain planner's literal
symbol grammar; no provider-native symbol is guessed or rewritten.
SHORT funding, minute-entry options and new strategy selection are not
invented. The user can explicitly choose 1..3 rows/month and a year in
2022..2025. A signal whose next executable entry falls in another year is
excluded. The 2026 native-daily partitions remain prohibited for this V1
until a separately accepted, protected-safe raw source adapter exists.

Each selected row first binds its accepted instrument/session through the
split-adjusted research view solely for identity and independent raw-close
reconciliation. The OPEN in that research view is **not** an as-traded price.
The exporter instead verifies the corresponding accepted V2 native acquisition
plan, native acceptance fingerprint, exact unit checkpoint, canonical raw daily
unit SHA-256 and provider-native source identity, then reads the exact raw
as-traded next-session OPEN. The raw native same-session CLOSE must equal the
research view's `unadjusted_close`, and every selected pair must be present.
Only pre-2026 native daily units are eligible; no protected or future daily
partition may be opened. The source entry-open timestamp is the accepted XNYS
regular open; candidate planning decision is fixed five minutes later
to avoid treating an opening print as known before its occurrence.
The chain snapshot is the *prior signal session* EOD, never the same
decision-session close. The option request expiration is a bounded
exchange-session-adjusted monthly expiration 28..60 calendar days after
the snapshot; it is a **candidate query**, not provider-proven contract
availability or final option selection. Side is CALL for LONG underlying
exposure. The existing planner derives the +/-8% explicit strike interval
only from the known raw stock entry-open price, not EOD-D provider
underlyingPrice or moneyness.

## Immutable outputs and exact physical source binding

The exporter first writes a small JSON stock-evidence bundle containing
only selected IDs, raw open prices, dates, frozen selection rule, accepted
conditioning lineage and accepted raw-daily manifest fingerprints. The
exact SHA-256 of that on-disk bundle is assigned to each source binding in
the opportunity manifest. The existing batch planner builds the chain
plan from that manifest, and the gated chain cache can physically verify
this same bundle via --stock-source-file before an actual provider request.

All three artifacts use a deterministic cohort ID and reject conflicting
existing bytes. The bundle lives under data/research/evidence/marketdata_candidate_stock_v1 and the
opportunity/chain plans under data/options/manifests, so an activated
external-storage binding relocates only eligible secondary outputs.
The accepted stock corpus and ATLAS installation stay internal.

The bundle SHA verifies bytes of the exported selection, while source
acceptance relies on upstream hash-validated conditioning, research-daily and
independently SHA-verified native raw unit receipts. Same-entry-date raw-close
information is used only as a **source integrity cross-check after raw OPEN has
been acquired from immutable accepted native data**, never as a price-derivation
or strike-selection input. It is not proof of historical option pricing or an independent
provider entitlement query.

## First workstation command and observed source-only result

This command is local, offline and can be run outside market hours:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\export_marketdata_accepted_stock_candidates_v1.py --year 2025 --per-month 1 --duckdb-threads 4
~~~

It may take time to verify the 546 accepted normalized source partitions
and reconstruct accepted source context; it does not redo the Dynamic Exit
V1 experiment or call a market-data provider. Keep the printed
stock-source-file and plan-file paths; the next command is the dry-run
chain-cache preview using --plan. No live acquisition is implied.



## First workstation evidence — 2026-09-25

The operator executed this V1 source-only export on combined PR #230
workstation commit \`6292b9de6cd74e2c46dbb467df56648fd304b396\`,
default \`--year 2025 --per-month 1 --duckdb-threads 4\`. The operator
reported:

- status: \`EXPORTED_SOURCE_ONLY\`; cohort identity: \`d6c924cf5006d295\`;
- 546/546 normalized source parts SHA-verified, 4,685 comparable selected
  opportunities and 113 distinct training cells loaded;
- 12 daily LONG stock cases from 12 different 2025 months, independently
  sampled without inspecting future outcomes, news or option outcomes;
- 12 separately SHA-verified native raw source units and 12 distinct bounded
  historical EOD chain requests (zero duplicate calls to eliminate);
- 21 durably recorded stages, elapsed time 23.6 seconds, zero provider reads,
  zero broker reads/writes and zero option P&L authority;
- source evidence bundle SHA-256:
  \`e7d90ce3162475ecbfc442d35e0ffbca18fca38434e658b0ee8bd7633021362e\`;
- chain plan fingerprint:
  \`a830ab16e6ebce9b509ec88efad8b6c8e08e2951db8682aa8d5e34ffc96886e1\`;
- run ID: \`20260925T233304045068Z-3830a7a5\`.

Logical local artifact paths (workstation-resident, not GitHub files):
\`data/research/evidence/marketdata_candidate_stock_v1/d6c924cf5006d295.json\`,
\`data/options/manifests/marketdata_stock_opportunities_v1_d6c924cf5006d295.json\`,
\`data/options/manifests/marketdata_candidate_batch_plan_v1_d6c924cf5006d295.json\`,
\`data/options/manifests/md_stock_runs/20260925T233304045068Z-3830a7a5.json\`.

The observed tickers by source month were SRRK, TSLA, OLLI, FSLY, TEM,
DAKT, BANF, AGIO, ATRC, LNT, AMGN and ISRG. This is a bounded provider
availability cohort, not a performance-selected portfolio and not yet
a set of verified, historically available or executable option contracts.

This is an operator-supplied terminal observation. It has not been
independently reconstructed from the private source/plan files in GitHub.
## 2026-09-26 continuation — source plan preview

PR #230 subsequently merged after ten passing GitHub workflows. Following
the verified migration of secondary research paths to the internal Samsung
860 EVO at D:/ATLAS_DATA, the operator ran the exact saved chain plan with
max-new-requests zero. The output reported PREVIEW, EXTERNAL_SECONDARY,
12 planned opportunities, 12 distinct shared chains, 12 pending, zero
verified existing receipts, zero new complete receipts, zero provider
reads and zero observed credits consumed. The plan fingerprint was
unchanged; preview report fingerprint:
c83f7464dbdccd5dc7c1242e926cc5598d16a79f1e38bf5130bee714befc9538.
A zero-read preview intentionally does not re-hash physical stock source
files; the live acquisition gate requires an exact stock-source-file SHA
match as an independent step. This is operator-reported evidence, not
independent GitHub artifact reconstruction. No chain acquisition or
strategy authority is opened by this preview.

## Authority boundary

This is source selection/planning only. It deliberately does not use
post-entry outcomes for cohort selection, claim the selected opportunities
represent winning strategies, verify the chosen option exists, select a
contract, validate prior-day OI, derive IV/Greeks, treat last/bid/ask as
executable fills, download quote histories, infer intraday option
STOP/TARGET paths, or integrate news/options into recurrent account P&L.
Those require new preregistered packages. The earlier negative exit
evidence and consumed protected master remain unchanged.


## Durable source-export run tracking and efficiency

Each invocation writes a separate atomic local run report at
data/options/manifests/md_stock_runs/<run-ID>.json.
Its status is updated before the expensive accepted source load, after source
verification, after outcome-blind cohort selection, before native-raw loading,
after **each** separately hash-verified native raw unit, after the raw-price
lineage gate, when the chain plan is ready, when all three artifacts are
persisted, and on COMPLETE or FAILED_REVIEW_REQUIRED/INTERRUPTED. It contains
a run ID, timestamped stage times, a durable 45-second heartbeat during long
source loading/verification, selected-case/unit/group counts, source and plan hashes,
immutable output paths and the exception **type** when failed; it does not
record credentials, provider data or a failure's raw message. CLI progress
also reports elapsed seconds, the verified native-unit count and shared-chain
request savings.

The scientific stock bundle and chain-plan fingerprints do **not** include
nondeterministic runtime measurements. Rerunning the identical accepted input
creates a new progress report but checks/reuses byte-identical existing
outputs without overwriting conflicting artifacts. Native units are
deduplicated by exact unit ID before reading. The cohort is capped at three
eligible daily LONG cases per month, and shared-chain batching is performed
once per cohort; the accepted selected-source loader uses the caller's
explicit 1..8 DuckDB thread budget (default four). Native unit hash
verification and development/PIT boundaries are mandatory and are never
short-circuited merely to improve throughput. Source export makes **zero**
market-data requests, so it is safe outside market hours.
