# Tradier Whole-Universe Cadence Diagnostic V1 — 2026-09-23

## Status

**IMPLEMENTED / TARGET-WORKSTATION MARKET-HOURS EVIDENCE PENDING**

Contract:

`atlas-tradier-whole-universe-cadence-diagnostic-v1`

This package is a read-only market-data diagnostic. It creates no provider-policy,
strategy, PAPER, LIVE, broker, order, promotion or confluence authority.

## Why this diagnostic exists

The accepted 2026-09-22 Tradier evidence established that one production POST quote
request can return a broad current population quickly, but it did not establish a safe
or useful recurrent refresh cadence.

The surviving Alpaca SIP V2 current asset snapshot contained 13,412 active, tradable
US-equity symbols. A single full-universe Tradier request returned 12,775 unique
symbols (95.251%) in about two seconds. The exact same 12,775-symbol set was returned
under tested 1,000/2,000/5,000/full batching, ruling out request-size truncation as the
main explanation for the raw coverage gap.

A separate near-close snapshot at approximately 15:58:44 America/New_York showed that
row presence was not equivalent to current actionable evidence:

- only 55.33% of returned rows had quote age <=30 seconds;
- only 43.74% had trade age <=30 seconds;
- the median quote age was about 19.6 seconds;
- the median trade age was about 65.7 seconds; and
- stale/thin rows were concentrated in lower-liquidity and specialized securities.

That evidence was captured near the close and cannot establish a whole-session cadence.
The same research record explicitly called for open, mid-morning, midday and
power-hour/near-close observations before any freshness/liquidity policy is frozen.

The present V1 package targets the missing **mid-morning repeated-snapshot** evidence.

## Frozen V1 schedule

The default diagnostic runs for about ten minutes:

- 20 broad snapshots;
- broad snapshots start every 30 seconds;
- after each broad snapshot, the diagnostic waits until +10 seconds and requests only
  unresolved symbols from the local Phase 7 discovery universe when it is available;
  otherwise it falls back to the unresolved broad population;
- at most 40 read-only Tradier provider calls are made;
- the production quote endpoint is `POST /v1/markets/quotes`;
- no account, order or broker endpoint is used.

The 30-second base sampling interval allows the final report to inspect observed
30/60/120/300-second cadence views by subsampling the same run. These are descriptive
views only. The run does not select or authorize a production cadence.

## Population

The broad source is the existing local:

`data/v2_build/alpaca_sip_v2/canonical/identity/assets_snapshot.parquet`

The diagnostic requires the snapshot itself to prove:

- active status;
- tradable status; and
- US-equity asset class.

V1 is pinned to the exact 2026-09-22 comparison source: asset snapshot SHA-256\n`43a5645d4366e7f7294e14f60596c5e753db6158c394a62262fdd283bbab151a` and exactly\n13,412 active/tradable/us-equity symbols. A changed file hash or population count fails\nclosed before any provider call.\n
When a local Phase 7 discovery-eligible universe snapshot is also available, its
quality/coverage is measured as a subset of the same broad response. That does not
consume an additional provider request and does not alter either universe contract.

## Per-row diagnostic normalization

Tradier quote/trade timestamps are normalized independently.

Non-positive timestamps are **missing/unknown**; they are never converted to epoch-age
extremes. The diagnostic preserves:

- bid timestamp;
- ask timestamp;
- trade timestamp;
- quote age based on the older bid/ask side;
- trade age;
- positive uncrossed bid/ask geometry;
- spread in basis points;
- session volume; and
- average volume.

A provider timestamp more than two seconds in the future relative to capture is
recorded as a chronology anomaly rather than silently clamped.

## Diagnostic unresolved cohort

The +10-second retry cohort is intentionally broader than a production eligibility
rule. A first-pass symbol enters the retry cohort when it is:

- missing;
- returned with invalid bid/ask geometry;
- returned with unknown quote freshness;
- returned with quote age >30 seconds; or
- returned with a future-timestamp anomaly.

The 30-second threshold is inherited only as a sensitivity boundary from the prior
near-close diagnostic. It is **not** accepted production policy.

Wide spreads alone do not cause retry membership because a wide but fresh quote is
primarily a liquidity/executability issue rather than evidence that the transport
needs another immediate poll.

## What each retry measures

For every +10-second unresolved-only retry, V1 records:

- missing symbols that become present;
- unresolved symbols that become fresh/valid;
- symbols with a newer bid/ask timestamp;
- symbols still unresolved after retry;
- provider latency;
- response bytes; and
- returned rate-limit headers.

This directly tests whether a second targeted pass adds useful information or merely
repeats the same missing/stale state.

## Whole-run evidence

The final report preserves:

- all broad/retry request metadata;
- all returned rows as gzip JSON;
- per-snapshot SHA-256 receipts;
- broad coverage and missing-set fingerprints;
- persistent-missing intersection across all broad cycles;
- ever-missing union across all broad cycles;
- quote-age sensitivity at 5/15/30/60 seconds;
- trade-age sensitivity at 5/30/60/120 seconds;
- spread distribution;
- average-volume sensitivity;
- optional Phase 7 subset quality;
- retry-recovery counts; and
- descriptive 30/60/120/300-second quote-advance and missing-recovery views.

The diagnostic deliberately does not choose a final polling cadence, retry budget,
liquidity threshold or freshness gate from one mid-morning run.

## Live tracker

The workstation output prints every broad and retry pass, including:

- cycle number;
- requested/returned symbols;
- coverage;
- quote<=30-second count;
- diagnostic <=30-second / <=100-bps usable count;
- missing count;
- unresolved count;
- provider latency;
- provider rate-limit availability;
- missing recovery;
- freshness recovery;
- newer quote timestamps; and
- still-unresolved count.

This makes a long market-hours run observable without opening the raw artifacts.

## Workstation command

Run during a normal XNYS regular session with the production Tradier key configured:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\diagnose_tradier_whole_universe_cadence_v1.py --authorize-provider-reads --run-live-cadence-diagnostic
~~~

The run is expected to last approximately ten minutes. Do not start a second copy
while the first process is active.

## Authority boundary

This is source/transport engineering evidence only.

It does not:

- change the accepted Tradier -> Alpaca -> Webull target routing;
- grant Tradier current-data authority;
- freeze a polling cadence;
- freeze freshness or spread eligibility;
- authorize broad streaming;
- alter strategy evidence;
- read a brokerage account;
- create or modify an order;
- authorize PAPER or LIVE trading; or
- change the Strategy Evidence Register.
