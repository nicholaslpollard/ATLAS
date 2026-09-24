# MarketData x Massive Sparse-Activity Confirmation V1 — 2026-09-24

## Status

**SPARSE_ACTIVITY_CONFIRMATION_FAILED / FROZEN / NOT TO BE RERUN AS V1**

Contract:

`atlas-marketdata-massive-sparse-activity-confirmation-v1`

This is a targeted confirmation experiment created after the frozen V2 result. It
does not rerun V2, replace any V2 anchor, relax V2's sparse-case requirement, or
reinterpret V2 as a pass.

## Evidence basis

V2 run `20260924T023405Z` /
`7461146a5c3f3f021384fea54cdfae1c4f62b509ed64f55f8a61b1b0d8d13dad`
failed only because its complete six-anchor sample contained zero sparse sessions.

The 53 positive-volume V2 comparisons were unusually coherent:

- 6/6 anchors passed all anchor-level criteria;
- exact MarketData-last / Massive-close match rate: 100%;
- MarketData-last inside Massive low/high: 100%;
- aggregate median relative price difference: 0%;
- aggregate median relative volume difference: 0%;
- maximum observed relative volume difference: about 0.30%.

Earlier DIA diagnostic evidence already showed five MarketData zero-volume sessions
with no Massive daily or minute aggregate and four positive-volume sessions with
both surfaces present. That case was too small and previously observed to satisfy
V2's requirement for an independent sparse case.

The missing evidence is therefore narrow: **independent sparse-session activity
concordance**.

## Frozen targeted sample

All roots and dates are new to prior MarketData x Massive cross-provider tests.

| Order | Root | Anchor date |
| ---: | --- | --- |
| 1 | RSP | 2025-10-06 |
| 2 | MDY | 2025-11-03 |
| 3 | IJR | 2025-12-01 |
| 4 | IEF | 2026-01-12 |
| 5 | LQD | 2026-02-09 |
| 6 | XBI | 2026-03-09 |
| 7 | KRE | 2026-04-06 |
| 8 | XRT | 2026-05-04 |
| 9 | XHB | 2026-06-15 |
| 10 | EEM | 2026-07-13 |
| 11 | FXI | 2026-08-24 |
| 12 | EWJ | 2026-09-08 |

No anchor is skipped because it looks too liquid or too sparse after observation.
All twelve are required.

## Frozen sparse-contract selector

Each anchor requests a historical call chain with:

- DTE target: 30;
- strike limit: 20;
- side: call.

Selection uses **only** the returned contract's strike, underlying price and symbol:

1. keep calls with finite positive strike and underlying price;
2. keep only out-of-the-money calls with strike > underlying price;
3. maximize strike / underlying-price ratio;
4. break exact ratio ties lexicographically by OCC option symbol.

The quote-series `volume`, `last`, later path, and Massive data are not consulted
when choosing the contract.

This intentionally stresses low-activity contracts. It is a source-semantics stress
test, not a simulator contract-selection rule.

## Provider procedure

For each of 12 anchors:

1. one MarketData historical chain read;
2. deterministic farthest-OTM call selection;
3. one MarketData selected-contract quote series covering 10 calendar days;
4. one exact-contract Massive unadjusted 1Day aggregate request for the same window.

Expected provider reads:

- MarketData: 24;
- Massive: 12;
- writes: 0.

Every raw response is persisted with a SHA-256 receipt.

## Session classification

Every MarketData quote-series session is classified; none are discarded after
observation.

- finite MarketData `volume == 0` is concordant only when Massive has **no** daily
  aggregate bar for that session;
- finite MarketData `volume > 0` is concordant only when Massive **does** have a
  daily aggregate bar;
- invalid or negative MarketData volume fails;
- a Massive daily date absent from the MarketData series fails.

No price threshold is evaluated in this experiment. A zero-volume MarketData
`last` remains uninterpreted.

## Binding pass thresholds

All must pass:

- exactly 12 completed anchors;
- at least 5 MarketData quote rows for every anchor;
- at least 10 zero-volume MarketData sessions in total;
- zero-volume sessions must occur across at least 3 distinct anchors;
- at least 20 positive-volume control sessions in total;
- positive-volume controls must occur across at least 3 distinct anchors;
- activity concordance rate = 100%;
- zero `ZERO_VOLUME_WITH_MASSIVE_BAR` mismatches;
- zero `POSITIVE_VOLUME_MISSING_MASSIVE_BAR` mismatches;
- zero invalid-volume sessions;
- zero extra Massive dates.

The thresholds, ordered anchors and selector are frozen before any provider read.

## Workstation result — 2026-09-24

Accepted V1 sparse-confirmation evidence:

- run id: `20260924T033435Z`;
- evidence fingerprint:
  `d7ce4d184d175b6f60233f2a4470e8e4e67a27691ac8a45a082b805b9e3cce6d`;
- status: `SPARSE_ACTIVITY_CONFIRMATION_FAILED`;
- terminal error: none;
- total MarketData sessions: 105;
- zero-volume sessions: 87 across 12 anchors;
- positive-volume sessions: 18 across 6 anchors;
- activity concordance: 100%;
- zero zero-volume/Massive-present mismatches;
- zero positive-volume/Massive-missing mismatches;
- zero invalid-volume sessions;
- zero extra Massive dates;
- MarketData credits consumed: 24;
- last observed MarketData credits remaining: 9,950.

The activity relationship itself was exact on every observed session. The only failed
preregistered check was `minimum_total_positive_volume_sessions`: V1 required at
least 20 positive-volume controls and observed 18.

V1 therefore remains a real failed confirmation. The positive-control floor is not
reduced from 20 to 18, the 12 anchors are not replaced, and V1 is not rerun with a
different selector.

This failure is interpreted as a **design-support shortfall**, not a contradiction of
the activity hypothesis. The farthest-OTM selector successfully generated abundant
sparse cases but generated two fewer positive controls than the frozen minimum.

A separately versioned V2 now uses a new disjoint sample and a prospectively frozen
third-farthest-OTM selector while retaining the exact same support thresholds and
100% concordance requirement.

Follow-up:
`docs/research/marketdata_massive_sparse_activity_v2_20260924.md`.

## Pass meaning

A pass confirms only that the tested MarketData positive/zero-volume session activity
state agrees with Massive trade-derived daily aggregate presence/absence under a
deliberately sparse, independently sampled option set.

A pass does **not** by itself grant:

- validation of MarketData `last` on zero-volume sessions;
- positive-volume price authority;
- historical bid/ask authority;
- intraday option paths;
- execution/slippage authority;
- simulator option P&L authority;
- strategy/PAPER/LIVE/broker/order/promotion/confluence authority.

If this sparse confirmation passes, the next package may preregister a deterministic
synthesis of the frozen V2 positive-volume evidence plus this independent sparse
evidence. It may not relabel V2 itself as passed.

## Fail-closed rules

- no anchor replacement after observation;
- no selector change after provider reads begin;
- no reduction of sparse-support thresholds after observation;
- no rerun to choose a favorable result;
- all observed sessions count;
- any provider or malformed-data error prevents a pass;
- V1 and V2 remain immutable failed validations regardless of this result.
