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

## Accepted workstation evidence — mid-morning and midday

Two target-workstation runs completed on 2026-09-23 under the same frozen contract,
same 13,412-symbol broad population, same 12,066-symbol Phase 7 subset, same 20-cycle
schedule and same provider endpoint.

### Mid-morning run

- evidence fingerprint:
  `46c6c01f9756867b7a5b075bcc34f632c9706fe35fc8e26ce670f719a0a515d2`;
- completed: 20/20 broad + 20/20 retries / 40 provider reads;
- wall time: 581.5 seconds;
- broad coverage: 12,775 / 13,412 = 95.251% on every cycle;
- persistent missing: 637;
- ever missing: 637;
- missing recovered by +10-second retries: 0;
- total freshness recoveries across retries: 12,377;
- mean broad quote-age <=30-second count: 5,805.2;
- mean broad <=30-second / <=100-bps diagnostic usable count: 5,598.4;
- mean broad unresolved count: 7,607.15;
- broad quote-timestamp advancement:
  - 30s: 51.277%;
  - 60s: 60.648%;
  - 120s: 68.253%;
  - 300s: 77.363%.

### Midday run

- evidence fingerprint:
  `009d26b8d3aacca316fd7f128c6e17555912fae3fe9009f6acbe26cfcce9efb5`;
- completed: 20/20 broad + 20/20 retries / 40 provider reads;
- wall time: 581.5 seconds;
- broad coverage: 12,775 / 13,412 = 95.251% on every cycle;
- persistent missing: 637;
- ever missing: 637;
- missing recovered by +10-second retries: 0;
- total freshness recoveries across retries: 10,903;
- mean broad quote-age <=30-second count: 4,768.6;
- mean broad <=30-second / <=100-bps diagnostic usable count: 4,660.6;
- mean broad unresolved count: 8,643.4;
- broad quote-timestamp advancement:
  - 30s: 43.345%;
  - 60s: 52.756%;
  - 120s: 61.174%;
  - 300s: 70.581%.

### Cross-regime findings opened

The 637-symbol raw-return gap is now observed as an invariant across forty broad
snapshots spanning two different regular-session regimes. The exact missing count
never changed and neither a later broad pass nor any +10-second unresolved retry
recovered a missing symbol. V1 therefore treats the raw missing set as a
provider-coverage/identity problem to diagnose separately, not evidence that faster
whole-universe polling is useful.

Freshness is regime-sensitive. Relative to mid-morning, midday averaged 1,036.6 fewer
symbols with quote age <=30 seconds (-17.86%), 937.8 fewer diagnostic-usable symbols
(-16.75%), and 1,036.25 more unresolved broad rows (+13.62%). The +10-second retry
cohort was correspondingly larger at midday, while total freshness recoveries fell
from 12,377 to 10,903.

The broad quote-advance curves also shifted lower at every measured cadence. Midday
was lower than mid-morning by approximately 7.93 percentage points at 30 seconds,
7.89 points at 60 seconds, 7.08 points at 120 seconds and 6.78 points at 300 seconds.

These results are strong enough to reject a model in which one fixed raw-return
coverage snapshot or one time-of-day freshness snapshot is representative of the
whole regular session. They are not yet sufficient to freeze 30/60/120/300-second
production cadence.

### Current disposition

- persistent missing-symbol handling: **separate identity/provider-coverage problem**;
- +10-second unresolved retry: **useful for freshness, not missing-symbol recovery**;
- 30-second full-universe polling: **not justified by current evidence**;
- 120-second broad refresh: **plausible candidate only, not frozen**;
- final regular-session cadence decision: **OPEN** pending the planned power-hour /
  near-close observation under the identical V1 contract;
- Strategy Evidence Register: unchanged;
- PAPER/LIVE/provider-policy authority: unchanged.

