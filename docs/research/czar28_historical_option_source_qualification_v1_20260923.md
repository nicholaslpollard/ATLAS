# Czar28 Historical Option Source Qualification V1 — 2026-09-23

## Status

**IMPLEMENTED / WORKSTATION EVIDENCE PENDING**

This package qualifies Czar28/PublicOptions as a candidate read-only historical
US-equity-option source. It does not make Czar28 authoritative, does not open
strategy outcomes, and grants no PAPER/LIVE or order authority.

## Why this package exists

Historical Option Reference V7 proved scientifically useful but operationally
impractical on the current Massive Basic entitlement. The resumed V7 provider phase
had 149 provider-pending monthly partitions. After roughly 1.5–2 hours it had issued
477 provider request starts at the enforced 5 requests/minute account budget while
all five in-flight monthly partitions were still incomplete.

That evidence does not invalidate V7. The preserved V7 raw data, receipts, conflict
diagnostics, resolver rules and quarantine evidence remain valid. It does show that
a full broad-reference crawl through the current Massive Basic REST entitlement is
not the preferred acquisition route for the stock-aligned historical option research
problem.

Czar28 currently documents:

- US equity options under /v1;
- 12+ years of history and about 5.2k tickers;
- /options/chain, /options/quote/eod, /options/quote/intraday, and /options/trades;
- a Free plan with 1,000 requests/month, all endpoints, 60 requests/minute and
  burst 20;
- response headers exposing monthly quota/remaining/reset; and
- per-logical-request idempotency keys that can safely replay a cached request
  within 24 hours without consuming another monthly request.

Provider documentation reviewed for this package:
https://czar28.com/docs
https://czar28.com/pricing

These are provider claims to qualify, not accepted ATLAS source facts.

## Frozen V1 probe design

The qualification deliberately exercises essentially the entire free monthly quota,
but every request must produce useful evidence.

The primary historical-depth matrix is 30 durable US option roots across a June
standard monthly expiration in every year from 2016 through 2026:

SPY, QQQ, IWM, DIA, AAPL, MSFT, AMZN, GOOG, GOOGL, NVDA, AMD, INTC, IBM, ORCL,
CSCO, JPM, BAC, GS, XOM, CVX, WMT, COST, HD, MCD, KO, PEP, JNJ, PFE, DIS, BA.

That is 330 chain probes.

From each non-empty chain ATLAS deterministically selects the median listed strike
for calls and puts. This is a structural representative only; it is not described as
ATM or delta-equivalent. V1 then spends up to 520 requests on 90-day EOD lifecycle
windows for those contracts.

Up to 50 successful EOD contracts receive a one-day 1-minute RTH intraday-quote
probe and up to 50 receive a one-day trade-print probe. Twenty-five chain probes and
25 EOD probes are intentionally repeated with distinct logical probe IDs to measure
exact response stability.

If those declared stages leave unused quota, ATLAS spends it first on additional
representative EOD contracts and then on March/September standard-monthly chain
probes. It does not burn quota on random/no-op requests.

## Quota and credential safety

The workstation credential name is exactly CZAR_API_KEY.

The value is read from the ignored root .env through the existing ATLAS settings
loader. The secret is never written to raw responses, receipts or reports.

The V1 runner has two explicit authorization gates:

- --authorize-provider-reads
- --consume-free-quota

It has a hard local maximum of 1,000 provider calls per run and refuses a local rate
above 55 requests/minute. Provider X-RateLimit-* headers are recorded. If the
provider reports zero remaining quota, the runner stops. HTTP 429 also stops the run.

Each logical probe gets a stable idempotency key and is persisted immediately as a
compressed raw-response envelope plus a hash-bound COMPLETE receipt. A restart
reuses locally verified completed probes without another provider request. This is
important because free quota is evidence and must not be wasted after interruption.

## Evidence opened by V1

V1 may measure:

- whether expired chains really exist from 2016 through 2026;
- breadth across durable equities and ETFs;
- contract identity and strike/right representation;
- EOD OHLC/closing bid/ask/volume presence;
- one-day intraday bid/ask/size presence;
- one-day trade-print presence;
- HTTP missingness/error behavior;
- provider quota/rate-limit behavior; and
- repeated-response stability.

It does **not** yet validate Czar28 prices against another provider. A successful V1
run therefore makes Czar28 a qualified candidate only. Cross-provider overlap
validation remains required before historical option prices can become an ATLAS
historical market-data authority.

The documented Czar28 EOD schema does not include open interest. OI remains a
separately versioned future overlay study using a source that actually provides
point-in-time historical OI.

## Authorized workstation command

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\qualify_czar28_historical_options_v1.py --authorize-provider-reads --consume-free-quota
~~~

Do not start a second copy while one qualification process is active. The runner is
resumable and quota-aware; restart the identical command only after the first process
has stopped.

## First workstation attempt and transport repair

The first target-workstation execution returned
`DIAGNOSTIC_COMPLETE_WITH_LIMITATIONS` after exactly one logical provider call.
The first frozen probe was SPY / 2016-06-17 chain discovery and Czar28 returned HTTP
502 with `upstream_error`. No rate-limit headers, chain rows, EOD rows, intraday
rows or trade rows were returned, so the run provides no evidence for or against
historical coverage.

Czar28's current API documentation explicitly states that 5xx responses are not
cached and that transient failures are safe to retry using the same idempotency key.
The provider transport has therefore been repaired without changing the frozen V1
scientific contract: HTTP 500/502/503/504 and URL transport failures receive bounded
exponential-backoff retries, the logical idempotency key is unchanged across retry
attempts, HTTP 429 remains an immediate quota stop, and exhausted retries still fail
closed. Reports now distinguish logical qualification calls from physical HTTP
attempts. The first failed run remains preserved evidence rather than being rewritten.

## Connectivity preflight and live observability

After two consecutive first-probe failures on SPY 2016-06-17, ATLAS no longer starts
the full 1,000-call qualification blindly. A separately versioned operational
preflight checks, in order:

1. /options/health;
2. SPY 2026-10-16 current monthly chain;
3. SPY 2025-06-20 recent expired monthly chain; and
4. SPY 2016-06-17 deep historical monthly chain.

Each probe has at most three transport attempts. If health/current access fails, the
preflight stops before the broad qualification. If current and recent history pass
but 2016 fails, the result is explicitly DEEP_HISTORY_UNAVAILABLE rather than a
generic provider failure. The preflight creates no historical-data or trading
authority and does not change the frozen qualification fingerprint.

The broad qualification now prints phase transitions and a heartbeat every 10 new
logical calls containing logical/physical request counts, observed remaining quota,
current probe, rows returned, and elapsed time. Recovered multi-attempt requests are
printed immediately. Failed retry attempts are included in the physical HTTP count.

