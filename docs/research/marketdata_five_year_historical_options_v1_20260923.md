# MarketData.app Five-Year Historical Options Qualification V1 — 2026-09-23

## Status

**STARTER-TRIAL CAPABILITY QUALIFIED / PAID-STARTER FIVE-YEAR QUALIFICATION PASSED**

Contract:

`atlas-marketdata-five-year-historical-options-v1`

This package is intended to unblock historical option-economics simulation without
waiting for ten-year source perfection.

## Provider role

MarketData.app Starter is the primary paid challenger for a rolling five-year
historical option layer.

Current documented Starter terms:

- $30 month-to-month;
- 10,000 API credits per day;
- five years of historical data;
- historical option chains;
- historical single-contract EOD quote series;
- 15-minute delayed current options on the paid Starter plan.

The trial/free tiers do not prove the paid five-year entitlement: they are limited to
one year of history for general tickers. The current Starter Trial additionally grants
full historical access for AAPL specifically. ATLAS therefore uses the free trial as a
bounded capability probe before any purchase:

- AAPL 2021-10-01 proves the same deep historical chain/quote mechanics near the
  five-year boundary using the trial's documented AAPL exception;
- SPY 2026-03-02, MSFT 2026-05-01, NVDA 2026-07-01 and QQQ 2026-09-01 prove the same
  schema/OI/quote-path behavior across multiple underlyings inside the trial's general
  one-year history window.

A successful trial run can de-risk endpoint behavior, schema, OI, raw persistence and
candidate-first economics at zero subscription cost. It **cannot** establish broad
five-year entitlement for non-AAPL symbols. The paid six-anchor qualification remains
the final five-year entitlement gate if ATLAS proceeds with Starter.

The target-workstation Starter Trial run completed successfully on 2026-09-23 under
run id `20260923T203419Z` and evidence fingerprint
`facd9289fc56279a14294c442f8a1f256388cfd152662be1bc06f600d1bf914a`.
All five chains and quote series were non-empty; OI, usable bid/ask geometry and all
required schema checks passed; historical Greeks/IV were present and null; no
terminal error occurred. The run consumed 8 observed API credits and ended with
9,992 remaining. Broad five-year entitlement remains explicitly unproven.

Accepted evidence:
`docs/research/marketdata_starter_trial_acceptance_v1_20260923.md`.

The operator subsequently activated the paid Starter plan and executed the
**first paid six-anchor qualification** successfully on 2026-09-25. Run
`20260925T182731Z` / evidence fingerprint
`f7a0c78e6812e59bf1b7efd243ce9c66c0325aa7241fd5a46868b3fc2224747a`
returned `QUALIFIED_FOR_FIVE_YEAR_EOD_ECONOMICS_CHALLENGER`. The six anchors
returned 96 chain rows and 50 selected-contract quote rows in aggregate;
all required checks passed, including sampled 2021-10-01 SPY access independent
of the earlier trial-only AAPL historical exception. Observed provider consumption
was 10 credits and last reported remaining was 9,990, with no terminal error.
This satisfies the bounded paid entitlement qualification, not exhaustive provider
coverage or historical executable-price/simulator authority.

Accepted paid run:
`docs/research/marketdata_paid_starter_acceptance_v1_20260925.md`.

The first independent overlap calibration is now complete under run id
`20260923T205206Z` / evidence fingerprint
`b10d6d8eb2f3bfcb9fa9dad5623d1eb56297bec5222922b2b8f2302fe5324f3a`.
All four 2026 contracts produced full date overlap: 31 overlapping sessions total,
77.419355% exact MarketData-last / Massive-close matches, zero aggregate median
absolute last-close difference, and 100% of MarketData historical last values inside
Massive's independent daily low/high range. Aggregate median relative volume
difference was 0.065284%; the maximum observed session relative volume difference was
14.213836%. No terminal error occurred.

That calibration does not itself grant price authority. Its purpose was to learn the
cross-vendor semantics before freezing a decision rule.

The next gate is now the **preregistered disjoint validation** in
`docs/research/marketdata_massive_disjoint_validation_v1_20260923.md`. Its untouched
sample is IWM 2026-02-02, AMZN 2026-04-01, META 2026-06-01 and DIA 2026-08-03.
Binding thresholds were frozen before any of those provider reads. A pass may validate
only MarketData historical EOD last/volume semantics; bid/ask, intraday, execution,
simulator, strategy, PAPER and LIVE authority remain closed.


## API-credit and transport controls confirmed from provider documentation

The provider documentation supplied on 2026-09-23 adds the following frozen
operational facts:

- Starter and Starter Trial use a daily API-credit window; Starter is 10,000
  credits/day;
- the daily usage counter resets at **09:30 America/New_York**, not midnight;
- all plans permit at most 50 concurrent requests;
- successful HTTP 200 and 203 responses consume credits; error responses do not;
- the response headers `X-Api-Ratelimit-Limit`,
  `X-Api-Ratelimit-Remaining`, `X-Api-Ratelimit-Reset`, and
  `X-Api-Ratelimit-Consumed` are the runtime budget authority;
- a single request may overdraw the remaining balance, so future bulk acquisition
  must estimate request cost before dispatch rather than relying only on
  `remaining > 0`;
- trial AAPL stock/options are documented free examples and may consume zero credits;
- Starter Trial does not support `mode=cached`;
- authentication uses a Bearer token in the Authorization header and ATLAS must never
  place the token in a query string;
- HTTP 203 is a normal cached success and must be treated identically to HTTP 200.

The V1 qualification is deliberately sequential, so it cannot approach the
50-concurrent-request ceiling. It now records the provider rate-limit snapshot for
every chain and quote response and reports observed credits consumed and the last
observed remaining balance. HTTP 429 is fail-closed in this qualification rather than
blindly retried because a sequential run cannot legitimately create the documented
concurrency condition.

The future candidate-first acquisition adapter must enforce a local concurrency cap
strictly below 50, honor the provider reset header, and budget estimated credits
before each request.


## Account/IP and redistribution boundary

The supplied MarketData documentation imposes two non-data constraints that ATLAS
must preserve:

- one MarketData account may connect from only one public IP address at a time;
  switching back and forth between IPs inside a five-minute window can trigger a
  temporary block;
- self-service plans are licensed for personal/internal consumption and do not
  authorize redistributing MarketData-derived market data to outside users through a
  public website, application, or shared dashboard.

During research acquisition, the MarketData token is therefore workstation-only.
GitHub Actions and other cloud runners must not perform authenticated provider reads,
and another machine must not use the same account concurrently. Browser observability
may display MarketData-derived state only inside the user's private/local ATLAS
surface under the self-service license. Any future public or multi-user exposure is a
separate licensing gate before implementation.

These constraints do not affect local historical simulation authority; they govern
provider access and data presentation.

## Historical economics available

Historical chain and quote rows can expose:

- OCC option symbol;
- expiration;
- side;
- strike;
- first-traded date;
- DTE;
- bid / ask / sizes;
- midpoint;
- last;
- volume;
- open interest;
- underlying price;
- updated timestamp;
- in-the-money state; and
- intrinsic / extrinsic value.

Historical IV and Greeks are not stored and are expected to be null. Derived
IV/Greeks, if later needed, must be a separately versioned derived layer and may not
be mistaken for provider-observed historical Greeks.


## EOD-only boundary and anti-lookahead rule

MarketData's historical options surfaces are end-of-day snapshots. That creates a
hard distinction between **source qualification** and **faithful strategy replay**.

The V1 qualifier deliberately uses `dte=30`, `strikeLimit=8` and the provider's
historical `underlyingPrice` only to choose one deterministic contract whose quote
history can prove that chain -> OCC symbol -> historical quote-series plumbing works.
That selected contract is **qualification-only**. It is not an accepted historical
contract-selection rule.

For a historical date D:

- `dte` is relative to D and may be used to choose a known expiration horizon;
- chain/quote bid, ask, mid, last, volume and `underlyingPrice` are EOD-D values;
- `strikeLimit` is a moneyness convenience based on the provider's option-chain
  snapshot and therefore must not define an intraday-D contract universe;
- OI remains the D-1-settled value available before D opens.

A future PIT simulator adapter must derive strike bounds/target strike from the
**ATLAS opportunity-time underlying price**, then query explicit strike/range filters
that do not depend on the provider's later EOD-D moneyness. The provider EOD
`underlyingPrice` may be retained for reconciliation but may not replace the
opportunity-time price.

MarketData alone cannot reconstruct an option's next-open price or intraday quote
path. Therefore it cannot, by itself, support a faithful option replay of an
underlying strategy whose entry or STOP/TARGET logic occurs at the open or intraday.
A later simulation must either:

1. preregister an explicitly EOD option-economics experiment whose decisions occur
   only after the corresponding EOD fields are available; or
2. combine the five-year EOD/OI layer with a separately qualified intraday historical
   option source.

No interpolation from EOD bid/ask/last into an intraday option path is authorized.

## Point-in-time semantics

For a historical date D:

- open interest is the figure settled from D-1 and available before D opens;
- bid/ask/mid/last/underlyingPrice and volume are end-of-day D observations;
- full-session D volume is therefore look-ahead for an intraday-D decision.

ATLAS must preserve those semantics in any simulator adapter. OI may be used for a
decision on D. Full-session D volume may only affect decisions whose cutoff is after
D's close or later.

## Corporate actions

The provider documents historical option data as as-traded and not adjusted for
splits, dividends or other corporate actions.

Therefore:

- raw provider prices are preserved exactly;
- the provider's historical `underlyingPrice` is retained with each option row;
- ATLAS must not silently combine as-traded option strikes with a stock series whose
  corporate-action adjustment basis is incompatible;
- adjusted/non-standard/corporate-action-sensitive cases remain fail-closed or
  quarantined until a separately accepted resolver proves the economics.

Massive Historical Option Reference V7 remains preserved for structural anomaly and
deliverable research, but it is no longer required to finish before five-year
economics qualification can proceed.

## Cost-aware acquisition design

Historical chain queries are documented at one API credit per 1,000 option symbols
returned. Historical single-contract quote requests are documented at one credit per
1,000 quote rows.

ATLAS will therefore use a candidate-first design rather than download the whole
option market:

1. take a stock strategy opportunity already known to ATLAS;
2. query the historical option chain only at the opportunity's PIT date;
3. restrict DTE and strike range before download;
4. choose candidate call/put contracts under a frozen selection rule;
5. request a short historical EOD series only for selected contracts over the
   intended holding horizon;
6. retain OI, bid/ask and underlying price with the same PIT record;
7. preserve raw response + SHA-256 receipt;
8. quarantine inconsistent/corporate-action-sensitive cases.

This design is materially more efficient than the Massive structural reference
rebuild that was throttled to five REST calls per minute.

## Qualification anchors

V1 uses six low-cost anchor probes spanning the rolling five-year entitlement:

- SPY — 2021-10-01;
- AAPL — 2022-10-03;
- MSFT — 2023-10-02;
- NVDA — 2024-10-01;
- QQQ — 2025-10-01;
- SPY — 2026-09-01.

Each anchor requests a historical chain near 30 DTE with only eight strikes, chooses
one deterministic qualification-only call using the provider's EOD underlying price,
and requests a ten-day historical quote series for that exact contract. This choice
exists only to prove endpoint linkage and may not be reused as a PIT simulator
contract-selection rule.

The run records:

- raw JSON responses;
- SHA-256 receipts;
- required schema presence;
- chain and quote row counts;
- non-null OI counts;
- historical-Greeks-null behavior; and
- proof that the oldest 2021-10-01 anchor is available.

## Acceptance meaning

A status of
`QUALIFIED_FOR_FIVE_YEAR_EOD_ECONOMICS_CHALLENGER`
means only that MarketData.app has passed the bounded five-year source/schema/OI
qualification.

It does **not** yet create:

- simulator historical-price authority;
- strategy evidence;
- an accepted option selection rule;
- an accepted execution/slippage model;
- PAPER/LIVE authority; or
- broker/order authority.

Cross-provider overlap validation and a separately frozen simulator integration
remain required.

## Workstation credential

The provider uses Bearer authentication. Keep the token only in the local `.env`:

~~~text
MARKETDATA_TOKEN=<token>
~~~

Never place the token in source control or command-line URLs.

## Workstation commands

For the 30-day Starter Trial, run the bounded capability probe first:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\qualify_marketdata_five_year_options_v1.py --authorize-provider-reads --starter-trial
~~~

This uses only the documented deep-AAPL exception plus general-ticker dates inside the
trial's one-year history limit. It does not intentionally issue a known-to-fail
out-of-entitlement request for another ticker.

The paid Starter qualification command was executed successfully on its first
workstation run (2026-09-25) and must not be rerun for result selection:

~~~powershell
git checkout main; git pull
.\.venv\Scripts\python.exe scripts\qualify_marketdata_five_year_options_v1.py --authorize-provider-reads
~~~

The next engineering package is the candidate-first five-year acquisition adapter.
No whole-market bulk download is authorized by V1.
