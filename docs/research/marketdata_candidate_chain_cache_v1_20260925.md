# MarketData Candidate Chain Cache V1 — 2026-09-25

## Status and source contract

**IMPLEMENTED SOURCE-ACQUISITION ADAPTER / NOT A SIMULATOR / FIRST WORKSTATION RUN PENDING.**

Contract: atlas-marketdata-candidate-chain-cache-v1.

This package consumes the output of the accepted offline candidate-batch planner,
reconstructs the entire plan from its source bindings and refuses any changed
fingerprint, widened query, extra source field, altered underlying/strike window,
future EOD lookahead, or duplicate opportunity identity. The input must originate
from *accepted stock opportunities*, not fabricated qualification-only cases.

The optional live stage re-hashes explicit on-disk stock source files supplied
with --stock-source-file and requires their exact SHA-256 values to cover every
source binding in the plan. That physical match does **not** independently
prove that the files' scientific scope or DEVELOPMENT authority was accepted:
the upstream source/manifest gate remains mandatory.

## Provider and safety boundaries

The default CLI action is a read-only local **preview**, with
--max-new-requests=0, no credential needed, no provider call and no cache writes.
For live source-only reads, all of the following are mandatory:

- --authorize-provider-reads;
- --confirm-paid-starter and --confirm-private-internal-use;
- --max-new-requests from 1 to 10;
- one or more --stock-source-file paths matching exact plan source SHAs;
- paid-plan access on the operator's single permitted workstation/IP;
- existing primary C: research budget, or a READY external secondary-data root.

The executor reuses the batch plan's bounded ticker/date/expiry/explicit-strike
requests. It makes **no** whole-universe option request, same-day selection, quote
history request, data redistribution, provider write, broker read or order action.
The current authenticated MarketData client preserves exact HTTP body bytes
behind a maximum response-size gate (8 MiB here). The cache stores immutable
body bytes with SHA-256 and separately fingerprinted receipts under:

data/options/candidate_cache/chains/marketdata_v1/<2-character-id-prefix>/<request-id>.json
data/options/candidate_cache/chains/marketdata_v1/<2-character-id-prefix>/<request-id>.receipt.json

The existing project-relative namespace remains stable when external storage
is bound through Windows junctions. Every completed reuse verifies the bytes,
request identity, endpoint, query params, provider schema, row count and
receipt fingerprint. Partial, changed, damaged or quarantined pairs fail closed;
the executor never silently overwrites an observed source.

Before every new provider request the existing research-storage policy reserves
the maximum raw response size against category and total budget and minimum free
space. The adapter accepts only HTTP 200/203, exact JSON body equality, a
nonempty <=1,000-row chain with required identity fields, and valid
X-Api-Ratelimit-Consumed/Remaining headers. Empty/oversized/schema/credit-header
anomalies are retained as QUARANTINED exact-raw evidence and stop the run.
Subsequent reads stop if last observed remaining credits are below 200.
The first request cannot guarantee provider billing and remains operator-gated;
actual provider response headers, not the nominal one-credit-per-group plan,
control subsequent reads. 429 and authorization errors never become cache hits.

No background worker or unbounded retry is introduced. Requests are sequential:
batch deduplication reduces redundant API use, whereas concurrency cannot reduce
per-contract quote history charges. Complete receipts survive interruption and
are verified on restart. A successful bounded run writes a status report under
data/options/manifests. Runtime progress/status is not scientific authority.

## Operator command, once actual accepted stock inputs exist

First produce a real accepted stock-opportunity manifest (the **offline**
planner has a separate command in its own research document). Then preview
without spending credits:

~~~powershell
.\.venv\Scripts\python.exe scripts\run_marketdata_candidate_chain_cache_v1.py --plan "PATH_TO_ACCEPTED_CHAIN_PLAN.json"
~~~

The provider-read command remains a later operator gate. It requires explicit
accepted source-file paths in addition to all listed authorization flags.
Do not use a fabricated sample or choose a later adjusted stock price to
construct the manifest. Do not run it merely because the source-capability
screenshot is positive; confirm the current license/account/IP and disk first.

## Accepted provider observations and limit of authority

The paid Starter qualification is recorded in
docs/research/marketdata_paid_starter_acceptance_v1_20260925.md.
The privately retained dashboard screenshot is hash-bound in
docs/research/marketdata_starter_dashboard_evidence_20260925.md: real-time
OPRA options are NOT entitled. This EOD-only chain adapter does not use OPRA
real-time access.

The sparse V2 activity test established zero/positive-volume semantics only.
Even a COMPLETE historical chain cache does **not** select an executable
contract, validate corporate-action deliverables, justify the prior-session
OI/close timing of a historical trade, validate a zero-volume last, fetch
selected-contract EOD quote horizons, establish bid/ask fill/slippage costs,
infer an intraday option path, or calculate option P&L. A separate frozen
contract-selection and quote-horizon adapter plus independent EOD execution
model and PIT news/option joins must precede recurrent simulator integration.

Strategy Evidence Register intentionally unchanged. Historical price/execution
authority, strategy/selector/promotion authority, PAPER, LIVE, confluence and
broker/order authority remain false.


## Durable tracking, restart and efficiency contract (before first workstation run)

Every authorized invocation receives a unique UTC run ID and an atomic
checkpoint at these two locations:

- latest plan report: data/options/manifests/marketdata_candidate_chain_cache_v1_<plan-prefix>.json
- per-invocation location: data/options/manifests/marketdata_candidate_chain_cache_v1/<full-plan-SHA>/runs/<run-ID>.json

The per-run JSON is updated atomically at initialization, before each paid
request, after each response or failure, at each credit/storage block, and
at finalization. Free cache hits checkpoint every ten rather than on every
row to reduce filesystem churn. A zero-provider-read PREVIEW performs no
manifest writes and skips the full research-directory quota census; a
configured external cache path still must pass its binding guard.

The cumulative status records the plan/source fingerprints, exact run ID,
timestamps, current status, requests planned/processed/completed/pending,
verified cache hits and bytes, new exact-raw bytes, quarantined responses,
provider **attempts** (including uncertain failures), provider-reported
credits consumed/remaining, unknown-credit flags, initial/latest storage
headroom and category quotas, elapsed seconds, observed throughput and a
clearly approximate ETA. It never records credentials or raw response bodies
in a public file. Per-request body hashes and statuses are retained in the
run JSON, while raw provider bytes remain in the private cache.

Immediately before a potentially billable call, an exclusive, fsynced
request-identity attempt JSON is created beside the cache body. Its existence
without a verified COMPLETE receipt blocks automatic reuse/re-request after
timeout, interruption or process death. **No blind retry** or invented
zero-credit assertion is allowed for an ambiguous response. The original
attempt must be reconciled with provider usage and local receipts by the
operator. One exclusive plan lock prevents two concurrent processes from
acquiring the same plan; a hard crash may leave a stale lock for deliberate
inspection. Ordinary failure releases the lock but retains all per-request
attempt markers and source bytes.

The executor validates complete receipt/body pairs on restart, reuses them
without spending credits, and checks that provider chain rows actually
match the requested underlying, expiration, strike envelope, option-side
schema and unique contract IDs. Bad provider arrays and mismatched rows are
preserved as exact-raw QUARANTINED evidence, never promoted. Success is
not option price/execution authority.

Efficiency is **bounded and auditable**, not maximal raw throughput:
shared chain batching eliminates redundant requests, at most ten new calls
are allowed per invocation, new calls are serial to preserve credit-state
decisions, max_attempts=1 prevents automatic duplicate charges, response
bodies are capped at eight MiB, source SHA verification occurs once per
invocation and complete cache receipts are reused. The existing research
budget is rechecked before each new call. Explicit blocked states include
PARTIAL_CREDIT_FLOOR and PARTIAL_STORAGE_BLOCKED. A PARTIAL_RESUMABLE run
may be invoked again under explicit authority after the operator reviews
the latest checkpoint; unresolved attempt or quarantine is never
automatically retried.
