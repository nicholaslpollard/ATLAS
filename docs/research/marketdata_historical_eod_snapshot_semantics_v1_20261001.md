# MarketData historical option EOD snapshot semantics V1 — 2026-10-01

## Purpose

Freeze the external documentation interpretation used by ATLAS when auditing the
already-acquired MarketData historical option quote bodies. This is a source-semantics
contract only. It does not modify original receipts, does not contact MarketData, and
does not create historical fills, option cash P&L, account P&L, PAPER authority or LIVE
authority.

## External documentation reviewed

Retrieved 2026-10-01:

- https://www.marketdata.app/docs/api/options/quotes/
- https://www.marketdata.app/docs/api/dates-and-times/
- https://www.marketdata.app/docs/api/options/chain/

The current Option Quotes documentation identifies `updated` as the date/time of the
quote snapshot. It defines `underlyingPrice` as the last underlying-security price at
the time of that quote, `askSize` and `bidSize` as displayed contract counts at the
respective quote sides, and `volume` as contracts negotiated during the trading day
at the time of the quote. For historical option requests, the documentation states
that bid, ask, mid, last, underlyingPrice and volume are as of the row's `updated`
timestamp and describes the historical snapshot as end-of-day / 16:00 ET. Historical
Greeks and IV are not stored.

The frozen interpretation is fingerprinted in
`packages/data/multiyear_marketdata_eod_clock_liquidity_probe_v1.py`.
Any material provider-documentation change requires a new version rather than silently
changing this V1 interpretation.

## What this newly permits ATLAS to test

The raw accepted quote bodies were preserved byte-for-byte and SHA-bound in their
original receipts. The original quote classifier already required
`underlyingPrice`, while prior derived timelines intentionally projected only bid,
ask, volume state and `updated`.

V1 therefore reopens only a receipt-verified physical body and, for the exact entry
and later observations already frozen in the historical execution-proof demand,
projects:

- option bid / ask;
- bidSize / askSize when present;
- reported volume;
- underlyingPrice from the same response row;
- the exact `updated` timestamp; and
- whether the later source observation is strictly before OCC expiration.

This can quantify a provider-documented same-row stock/option snapshot-clock
**source-shape candidate**. It can also quantify whether a one-contract conservative
entry-at-ask / exit-at-bid scenario has positive displayed size and positive reported
volume at both marks, and whether a forced exit before expiration avoids exercise /
assignment handling for that candidate.

## What this does not prove

The historical response was retrieved retrospectively. Provider documentation of a
snapshot timestamp is not, by itself, independent evidence that the historical row
was publicly retrievable through this provider at that exact instant. Therefore V1
keeps all of the following false:

- independent option publication/retrieval availability verified;
- matched executable stock/option clock verified;
- point-in-time deliverable/multiplier verified;
- historical trade admitted;
- historical account P&L authority.

It also does not reinterpret an EOD snapshot as the original 09:35 decision/fill.
The existing 09:35 strategy chronology remains unchanged.

## 2026-10-01 source-acquisition closeout that motivates this probe

The accepted October 1 reset-day run ended with:

- 13,511 complete demand-cache exact histories;
- 2,235 reused accepted 2022 histories;
- zero exact quote gaps;
- 1,602 original exact identities outside the current floor, all covered by the
  current clipped recovery overlay;
- of those recovery histories, 487 reused a previously verified covering body and
  1,115 used the new current-floor recovery source;
- 17,348 physical histories decoded in the final source refresh;
- 20,040 case/right rows with dated option and stock source pairs;
- 7,297 cumulative observed MarketData credits consumed;
- 2,703 credits remaining in the last observed provider header; and
- zero historical executable option trades.

Those remaining credits are not an unfinished exact-history backlog. The 1,602
original-plan pending identities are represented by complete clipped recovery bodies.
Additional provider spend should be justified by new source demand, not by attempting
to refill an unavailable original prefix or repeat accepted histories.

## Next gate

Run the V1 probe against the exact
`multiyear_historical_execution_proof_demand_v1` artifact from the accepted October
1 source refresh. The result will show how many of the 20,040 dated rights already
have the EOD snapshot/liquidity/pre-expiry source shape and how many retain a field or
policy gap.

No execution gate is promoted by the probe. The result is used to decide which
independent evidence acquisition is worth doing next, with deliverable/multiplier and
publication/retrieval availability remaining explicit blockers.
