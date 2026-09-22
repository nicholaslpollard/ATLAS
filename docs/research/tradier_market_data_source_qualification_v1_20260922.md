# Tradier production market-data source qualification V1 — 2026-09-22

## Purpose

Tradier is now available to the operator through a production Brokerage API token
stored locally in `TRADIER_API_KEY`.

ATLAS does not change its live/current provider policy merely because credentials are
available. Tradier must first pass explicit source qualification against the target
workstation and ATLAS universe.

This package freezes only the first qualification stage:

`atlas-tradier-production-market-data-source-qualification-v1`

It is a read-only production market-data diagnostic. It has no account-read, order,
broker-mutation, PAPER, LIVE, promotion, confluence or current-provider-policy
authority.

## Provider facts frozen for this diagnostic

Official Tradier documentation reviewed on 2026-09-22 states:

- production Brokerage API equity market data is real-time;
- production Brokerage API options market data is real-time;
- the production feed is consolidated from U.S. exchanges;
- sandbox market data is delayed approximately 15 minutes;
- production `/markets` resources are limited to 120 requests per minute per
  access token;
- POST `/v1/markets/quotes` is intended for larger symbol lists;
- Tradier does not publish a hard maximum symbol count for that POST quote request;
- market-data streaming permits one market-data stream session at a time;
- the provider documents streaming from one symbol through more than several hundred
  symbols, but does not publish a hard symbol limit; and
- the provider explicitly discourages abusive/exchange-wide stream requests.

Documentation references:

- `https://docs.tradier.com/docs/market-data`
- `https://docs.tradier.com/docs/rate-limiting`
- `https://docs.tradier.com/reference/brokerage-api-markets-post-quotes`
- `https://docs.tradier.com/docs/streaming-data`
- `https://docs.tradier.com/reference/websocket-market-data-streaming`

These are provider claims. ATLAS still measures actual entitlement, coverage, latency,
cardinality and transport behavior independently.

## Credential boundary

The production token is read only from the environment variable:

`TRADIER_API_KEY`

The token is placed only in the HTTPS Authorization header. It is never included in
request URLs, logs, reports, persisted payload metadata, object representations or
source-control files.

The repository's `.env.example` contains only the empty variable name. Real values
remain in the ignored local `.env`.

## V1 REST qualification

The target endpoint is:

`POST https://api.tradier.com/v1/markets/quotes`

The default staged request sizes are:

1. 1 symbol
2. 10 symbols
3. 100 symbols
4. 250 symbols
5. 500 symbols
6. 1,000 symbols

When explicit symbols are not supplied, the runner loads the latest local Phase 7
universe snapshot, retains only `discovery_eligible=true` tickers and samples it
deterministically. SPY, QQQ, AAPL, MSFT and NVDA are retained as liquid anchors when
present; the remaining sample is stable hash-ordered so repeated runs use the same
population.

For every completed stage the diagnostic records:

- requested and returned unique-symbol cardinality;
- coverage fraction;
- missing symbols, capped in the display/report for readability;
- unexpected symbols;
- duplicate symbol rows;
- provider/request wall latency;
- response bytes;
- provider payload fingerprint;
- non-null field counts; and
- returned `X-Ratelimit-*` headers.

Actual quote prices are **not** persisted by this V1 diagnostic. The provider response
is reduced to coverage/schema/performance evidence and a cryptographic payload
fingerprint.

The runner stops after the first provider/request failure instead of repeatedly
submitting larger requests after a boundary has already been found.

Reports are written beneath ignored local state:

`data/research/provider_qualification/tradier/rest/`

## Interpretation boundary

A successful REST V1 run proves only observed production REST access, practical batch
behavior and returned quote coverage for the sampled ATLAS symbols.

It does **not** prove:

- that Tradier should replace Alpaca or Webull in the operating provider chain;
- streaming capacity or recovery behavior;
- full-universe refresh timing;
- options-chain economics;
- historical source suitability;
- broker execution quality;
- account/order API safety; or
- PAPER/LIVE authority.

Streaming must be qualified separately after the REST evidence is reviewed. That later
contract should use a bounded candidate-style symbol set consistent with Tradier's
published streaming guidance rather than attempting an exchange-wide subscription.

Only after REST, streaming, timestamp/freshness and cross-provider feed-quality
evidence are accepted may ATLAS consider a new version of the live/current provider
policy.
