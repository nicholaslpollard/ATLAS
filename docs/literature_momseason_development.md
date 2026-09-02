# LIT-01 Frozen Development Evaluation

**Branch:** `literature-anchored-alpha-exploration`  
**Authority:** exploratory / non-authoritative  
**Accepted research-freeze fingerprint:** `745ff247ecf9404f19aaf67450fdaf08fcec525e3a62c781f30a91662a901cfb`

## Purpose

This package is the first LIT-01 stage permitted to read development target returns. It is hard-bound to the accepted pre-outcome research freeze and cannot request a target endpoint on or after the protected-window start of `2026-05-12`.

The primary experiment remains exactly the externally specified two-hypothesis Heston-Sadka/OpenSourceAP family:

- `momseason_short_year1`
- `momseason_years2_5`

No hypothesis may be dropped after outcomes are observed.

## Frozen holdings construction

For each of the 56 development target months from `2021-09` through `2026-04`:

1. Reconstruct each hypothesis from accepted Alpaca `adjustment=all` lag endpoints and ATLAS stable PIT identity.
2. For the years-2-through-5 signal, average all available valid annual lags, with at least one valid lag required, matching the already accepted native-source contract.
3. Sort the complete native predictor cross-section by predictor value ascending, then stable `instrument_id` as a deterministic exact-tie rule.
4. Use `floor(N * 0.10)` names in each leg.
5. Long the highest predictor decile and short the lowest predictor decile.
6. Equal weight every holding within its leg.
7. Persist the holdings and target-endpoint plan fingerprints before any target return is evaluated.

Future target availability is never used to select or remove a holding.

## Development target source

Only the prior-month and target-month adjusted month-end closes needed by the frozen holdings are requested.

- provider: Alpaca
- timeframe: `1Day`
- adjustment: `all`
- feed: `sip`
- `asof`: endpoint session
- maximum allowed target endpoint: `2026-04-30`
- protected target reads: forbidden

Exact raw provider responses and invalid-symbol evidence remain in the isolated LIT-01 provider namespace.

If any frozen holding lacks a complete source-grounded target return, the development source is classified incomplete. Missing/delisted holdings are not silently deleted and are not assigned zero or last-price returns.

### Pre-outcome target-identity repair

The first target-machine invocation on exact head `49a5debe0b39d30ee7e4375b307a4e4d95332222` stopped during `build_plan()` before target acquisition with:

`ambiguous PIT ticker for development target endpoint: 2021-10-29 ins_b8e04037690e12c4013e8c02`

Because `run()` builds and fingerprints the holdings/target plan before calling target acquisition, that failure exposed no development return and consumed no protected evidence.

The first repair added the retained ATLAS source hierarchy: unique active PIT alias first, then a unique retained Massive authoritative ticker-validity interval. Exact-head Ubuntu and Windows tests passed, but the next target-machine invocation on `1927160afcec970946d1f4110e75a2c3ff84b1a8` again stopped pre-outcome and revealed the concrete simultaneous aliases:

`aliases=['VMW', 'VMWw']`

This second failure is not an ordinary unresolved ticker change. Under NYSE/CTA symbol convention, a lowercase trailing `w` is the compact form of the `WI` (When Issued) suffix. Therefore `VMWw` is the When-Issued line paired with regular `VMW`, rather than a basis for choosing between two unrelated security identities.

The repair remains intentionally narrow and source-semantic. Target alias resolution is now:

1. prefer a unique active strong/medium PIT alias at the endpoint;
2. if multiple active safe aliases remain, prefer a unique retained Massive authoritative ticker-validity interval covering that stable instrument and endpoint;
3. if no authoritative interval resolves the active set, permit only the exact case-sensitive two-alias pattern `{BASE, BASEw}` and retain `BASE` as the regular line;
4. if only inactive safe aliases exist, a unique authoritative interval may disambiguate them;
5. where a historical endpoint snapshot is unavailable, authoritative interval evidence is preferred before the already-existing formation-ticker fallback;
6. no alphabetical choice, data-availability choice, volume choice, price choice, return-based choice, or identity merge is permitted.

The When-Issued rule does not generalize to uppercase `W`, arbitrary suffixes, three-or-more-alias sets, or any other multi-alias shape. Those cases still fail closed.

None of these repairs changes the accepted research freeze, hypothesis family, native population, predictor formula, ranking, portfolio weights, turnover costs, inference, protected policy, or production authority.

## Portfolio returns and costs

The independent inferential unit is one calendar-month long-short portfolio return, not an individual stock row.

Gross monthly spread:

`EW(top decile target return) - EW(bottom decile target return)`

One-way turnover for each leg is `0.5 * sum(abs(w_t - w_{t-1}))`; the first development month has turnover 1.0 from cash for each leg.

Costs use the retained ATLAS convention:

- primary: 10 bps per unit of one-way turnover per leg
- stress: 25 bps per unit of one-way turnover per leg

## Frozen inference

For each fixed hypothesis:

- 56 monthly observations
- one-sided positive direction
- 2,000-replicate circular block bootstrap
- 12-month blocks
- 90% one-sided lower confidence bound
- Holm-Bonferroni correction across both fixed hypotheses at family alpha 0.05

A hypothesis becomes an internal development finalist only if all four checks pass:

1. primary after-cost mean > 0
2. 90% bootstrap lower confidence bound > 0
3. one-sided bootstrap p-value rejects after Holm correction
4. 25-bps-per-leg turnover-stress mean > 0

Both hypotheses are always reported. Four chronological folds and month-of-year slices are diagnostics, not adaptive selection gates.

## Protected and production authority

Development success does not consume or authorize use of the current protected window. The current window has only 2 complete months versus the frozen requirement of 12.

If a development finalist emerges, ATLAS must reserve a new prospective protected window with at least 12 complete target calendar months before any protected confirmation.

This experimental package grants no Phase33, mainline, PAPER, LIVE, broker, order, or automatic adoption authority.
