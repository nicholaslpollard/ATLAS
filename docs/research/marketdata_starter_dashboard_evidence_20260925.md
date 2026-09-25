# MarketData.app Starter dashboard evidence — 2026-09-25

## Provenance and retention

The operator supplied a screenshot of the authenticated MarketData.app account
dashboard on 2026-09-25. Its exact original PNG is retained **privately** in the
operator's ChatGPT Library at
`/ATLAS/Evidence/marketdata-starter-entitlements-2026-09-25.png`, not in this
public GitHub repository. This pathname is a human-facing custody reference,
not a machine-accessible ATLAS input or evidence authority.

Original image SHA-256:
`1357a70a9c154f9171eac1ec976abaa647834d613a6f88b8129e4e3f266775bd`.

The screenshot itself is operator-supplied dashboard evidence, not a credentialed
API probe performed by this documentation package. No API key, account identifier,
payment information or confidential market data is committed.

## Exact dashboard observations

| Dashboard item | Displayed state |
| --- | --- |
| Subscription | Starter, active |
| Account verification | Verified / good standing |
| IEX — Real-Time Stock Data | Entitled |
| UTP — Consolidated Candles | Entitled |
| OPRA — Real-Time Options Data | **Not Entitled**; dashboard shows Trader plan or above |
| API usage | 34 / 10,000 credits |

The displayed 34 used credits reconcile with the separate observed 10-credit
paid-Starter historical-option qualification and 24-credit Sparse-Activity V2
confirmation. This is consistency evidence, not proof of additional consumption
or that the displayed daily quota has not changed since the screenshot.

## Scope and implications for ATLAS

The screenshot independently supports the operator's observed paid Starter
account state, IEX/UTP labels and OPRA **real-time** restriction. It does not
prove an OPRA subscription, real-time consolidated stock NBBO, tradability,
quote freshness, order/fill economics, or historical options price authority.

Historical five-year EOD option chains/quotes/OI were previously demonstrated
by a separate authenticated *workstation* qualification with immutable
hash-bound receipts, as recorded in
`docs/research/marketdata_paid_starter_acceptance_v1_20260925.md`.
Lack of real-time OPRA entitlement must **not** be misinterpreted as failure of
that sampled historical EOD qualification; conversely, that qualification
cannot unlock real-time options feeds.

The current acquisition/cache path therefore remains EOD-only, private/internal,
and explicitly read-authorized on the single authorized workstation/IP.
The dashboard is not a substitute for runtime provider entitlement responses,
credit headers, provider terms or license checks. No public market-data
redistribution is authorized. No historical executable option price, strategy,
simulator P&L, PAPER or LIVE authority is created.

The private image is deliberately not copied into the public repository. This
text record and image hash allow the retained original to be checked later.
