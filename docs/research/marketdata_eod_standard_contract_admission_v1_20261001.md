# MarketData EOD standard-contract admission audit V1 — 2026-10-01

## Purpose

Define the next zero-provider gate between the accepted MarketData EOD
clock/liquidity probe and any modeled five-year option account replay.

The accepted EOD probe produced 20,040 dated stock+option source rights and 8,574
rights that simultaneously had the documented EOD clock shape, positive entry/exit
quote-side size and volume, and a strictly pre-expiry later observation. That 8,574
count is **not** itself an admissible trade population because it contains future
exit information.

V1 therefore separates entry admission from later exit disposition.

## Frozen provider semantics

Retrieved 2026-10-01:

- https://www.marketdata.app/docs/api/options/chain/
- https://www.marketdata.app/education/options/non-standard-options/

MarketData documents the historical chain endpoint as EOD. Its `nonstandard`
parameter defaults to `false`, and `false` excludes non-standard contracts.
MarketData's non-standard-options documentation describes adjusted contracts created
by splits, mergers and similar corporate actions as non-standard, while the standard
equity chain uses the ordinary 100-share contract model.

The accepted ATLAS physical-chain receipts used exactly `date`, `expiration` and
`strike`; they did not request `nonstandard=true`. The original bridge also required
the selected OCC root to equal the accepted underlying ticker.

V1 rechecks those exact receipt/body bytes and the selected OCC membership. A selected
right that still binds to that default standard-filter chain is labeled
`provider_standard_chain_classification=true`.

## Authority boundary

That classification permits one thing only: a **provider-standard 100-share modeled
multiplier assumption** for a separately labeled EOD scenario.

It does not claim:

- independent OCC deliverable/multiplier proof;
- historical publication/retrieval availability at the snapshot instant;
- an executable historical fill;
- authoritative historical option or account P&L;
- PAPER or LIVE eligibility.

A later independent OCC/corporate-action gate may supersede the modeled multiplier
assumption. Until then, any replay using it must remain explicitly modeled.

## Causal entry gate

Entry readiness may use only evidence available at the entry snapshot:

- selected contract came from the verified default standard-filter historical chain;
- entry option/underlying snapshot is provider-documented same-row EOD;
- entry snapshot is exactly 16:00 ET;
- entry quote is two-sided;
- displayed ask size is at least one contract; and
- reported entry-day volume is positive.

No field from the future exit snapshot is allowed to affect admission.

## Later exit gate

Only after an admitted position reaches its later observation may V1 evaluate:

- same-row EOD snapshot shape;
- exact 16:00 ET timestamp;
- two-sided quote;
- positive displayed bid size;
- positive reported volume; and
- later session strictly before expiration.

An entry may therefore be causal-entry-ready while the later exit remains
unqualified. Such a position must not be silently dropped from a future replay.

## Next step

Run the V1 audit against the immutable
`multiyear_marketdata_eod_clock_liquidity_probe_v1` artifact. Its output will provide:

- provider-standard selected rights;
- causal entry-ready modeled source rights;
- later exit-ready rights;
- rights satisfying both; and
- year-level counts.

If the causal entry-ready population is substantial, the next engineering gate is a
separately versioned historical EOD scenario adapter that preserves unresolved exits
as explicit account states rather than filtering them away.
