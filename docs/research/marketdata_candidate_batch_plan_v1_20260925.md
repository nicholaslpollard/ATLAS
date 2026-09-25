# MarketData Candidate-First Chain Batch Planner V1 — 2026-09-25

## Status

**OFFLINE PLANNER IMPLEMENTED / NO PROVIDER ACQUISITION OR OPTION-P&L AUTHORITY**

Contract: `atlas-marketdata-candidate-chain-batch-plan-v1`.

The first step after source-semantics closeout is a small, testable planning
surface that turns a stock-opportunity manifest into bounded shared historical
chain requests **without making any API calls**. This is not a simulator.

## Input and PIT requirement

The JSON manifest has purpose `SOURCE_ACQUISITION_ONLY` and an
`opportunities` array. Every row must have exactly:

- `opportunity_id`: unique stable identity;
- `ticker`: uppercase canonical underlying;
- `snapshot_date`: historical EOD chain as-of date;
- `decision_at_utc`: timezone-aware UTC decision timestamp;
- `raw_underlying_price`: price already known from the stock opportunity;
- `underlying_price_basis`: literal `RAW_AS_TRADED`;
- `expiration`: known candidate expiration date;
- `side`: `call` or `put`;
- `stock_source_sha256`: the real hash of the accepted source artifact.

The decision date in America/New_York must be strictly **after** the chain
snapshot date. This conservative V1 avoids same-day EOD lookahead by design.
The snapshot must not be in the future and expiration must be 7–75 calendar
days after it. The stock source SHA-256 and raw price basis are mandatory.
The caller must prove that the supplied price was known by decision time;
the planner does not invent it from a later provider `underlyingPrice`.

## Batching and cost model

Each opportunity receives a bounded strike interval of +/-8% around its
PIT stock price, rounded outward to cents. The planner groups by
`ticker + snapshot_date + expiration`, then merges overlapping windows
only if their combined width is <=25% of the smallest PIT stock price.
Calls and puts can share the same chain request because the endpoint can
return both sides; selection by requested side is a later local step.
The output is ordered and fingerprinted independently of input order.

For example, **50 similar-price SPY opportunities on the same snapshot
and expiration can produce one shared historical chain request** rather
than 50 redundant requests. Different underlyings, sessions, expirations
or disjoint price windows correctly remain separate requests.

The documented MarketData historical-chain credit basis is one credit per
1,000 returned option symbols, not automatically one credit per HTTP
request. V1 reports a **nominal one-credit-per-group estimate** if each response returns
1–1,000 billable symbols. It is not a guaranteed lower or upper bound: free
examples and responses above 1,000 symbols may change actual charges. The
provider's observed rate-limit headers remain authoritative. No unbounded all-expiration chain is planned.

Source documentation:
- https://www.marketdata.app/docs/api/options/chain/
- https://www.marketdata.app/docs/api/options/quotes/

Historical single-contract quote-series REST calls are **not** magically
batched by passing many symbols to the same URL. The future executor must
compare (a) shared historical chain snapshots across each EOD date with
(b) selected-contract quote-series paths using real credit/row forecasts.
Concurrency accelerates independent requests but does not reduce charged
credits.

## CLI

With a real accepted stock-opportunity manifest:

~~~powershell
.\.venv\Scripts\python.exe scripts\plan_marketdata_candidate_batches_v1.py --opportunities "PATH_TO_ACCEPTED_OPPORTUNITIES.json"
~~~

By default, the small plan is written to the configured project-visible
`data/options/manifests/marketdata_candidate_batch_plan_v1.json`. When
external storage is activated, that path is physically on the external
NVMe. An explicit `--output` path can be supplied.

This command is **offline** and needs no provider key or license activation.
It does not fetch or create historical option quotes, select an executable
contract or touch the stock database. Input for live research must originate
from accepted stock artifacts, not fabricated sample rows.

## Execution gate not yet built

The later separately accepted executor must:

1. assert the external secondary-data root and capacity are ready;
2. verify current paid entitlement and retention policy;
3. require explicit provider-read authorization on the user's one
   authorized workstation/IP, never CI;
4. estimate budget before each request, cap concurrency below 50, inspect
   provider credit headers and fail closed on rate/credit failures;
5. persist raw responses and SHA-256 receipts atomically with deduplicated
   request identity and verified restart/reuse;
6. reject unexpected oversized chains before treating them as a valid cache;
7. locally filter to input opportunity's side/PIT strike/expiry, refusing
   nonstandard/unqualified contract economics;
8. retrieve only needed selected-contract EOD quote horizons;
9. preserve D-1-settled OI and EOD-D quote/volume availability separately;
10. keep zero-volume last out of execution price and keep bid/ask as
    observed quote context rather than validated fills.

The optional future historical simulator must freeze an EOD-only timing
model. No intraday STOP/TARGET path can be reconstructed from EOD.

## Source and research authority

The passing 2026-09-25 sparse activity check and earlier positive-volume
price calibration are separately documented. Neither grants historical
execution-price, option-P&L, predictor/strategy, PAPER, LIVE, broker/order,
promotion or confluence authority.

The Strategy Evidence Register is intentionally unchanged. The core
ATLAS installation and Alpaca SIP V2 stock database remain internal.
