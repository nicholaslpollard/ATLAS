# Historical Option Reference V3 ACHI underlying-identity failure — 2026-09-21

## Scope

This immutable incident record preserves the first target-workstation execution of
Historical Option Reference V3 after acceptance of contract fingerprint
`7a9dab85c57bbc6cd93dee2472a9244d86e8c1776f986cd97036b9963bc4c48e`.

V3 authority remained structural reference acquisition only. Historical contract
availability, dynamic deliverables, market prices, predictor generation, strategy
outcome access, PAPER and LIVE authority were all false.

## Accepted preflight observations

- reference as-of date: `2026-09-19`
- active hard end: `2032-01-01` exclusive
- monthly partitions: 212
- workers / maximum in flight: 5 / 5
- verified V2/V1 raw reuse: enabled
- hard-end boundary probe: PASS
- known AAL V2 conflict resolver probe: PASS
- AAL selected current raw payload primary exchange: `BATO`
- AAL historical resolver date: `2014-06-20`

## Reuse inventory and local rebuild

V3 inventory at run start:
- verified V3 reusable: 0
- verified V2 raw reusable: 63
- verified V1 raw reusable: 0
- provider pending: 149

All 63 verified V2 raw partitions were re-normalized locally under V3 before the
reported provider failure. No verified raw source bytes were duplicated.

At the end of that rebuild phase:
- option-reference usage: approximately 0.198 GiB
- reported disk free: approximately 116.40 GiB

## Fail-closed provider observation

Provider acquisition failed in:
- partition: `expired-2014-06`
- ticker: `O:ACHI140621C00001000`
- conflict class: unversioned same-ticker rows
- differing field reported by V3: `underlying_ticker`

V3's only frozen same-rank fallback permits
`primary_exchange`-only differences. The resolver therefore correctly refused to
choose between the ACHI rows. No V3 completion claim is made.

Because bounded scheduling allows at most five provider partitions in flight, a
future successor must re-inventory receipts before resumption rather than assume
that zero or all provider work persisted.

## Provider-documentation implications

Massive's public option-reference documentation defines:
- `as_of` as a point-in-time contract-reference selector;
- `underlying_ticker` as the ticker the option contract relates to;
- `additional_underlyings` as additional underlyings or deliverables;
- `correction` as the contract correction number.

Massive separately documents that adjusted option series may coexist and are not
merged, and that stock ticker changes/acquisitions retain their historical published
symbols rather than being automatically stitched together.

Those semantics do not justify treating an `underlying_ticker` disagreement as
interchangeable with the previously accepted AAL primary-exchange conflict.

## Frozen next step

A read-only diagnostic is frozen as
`atlas-historical-option-reference-v3-underlying-identity-conflict-diagnostic-v1`
under fingerprint
`aaf0a8e52fdd56521fe000dc1ead04059115d2639b18eb29fad03b8fe76eaec1`.

The diagnostic:
1. repeats current option structural-list requests without an underlying filter;
2. repeats pre-expiration structural-list requests without an underlying filter;
3. repeats exact Contract Overview requests at both dates;
4. records all current/historical `underlying_ticker` values, payload hashes and
   field differences;
5. performs supplemental point-in-time stock-reference lookups for every discovered
   underlying symbol when the account permits them;
6. records Stocks-plan 403/404 limitations instead of treating them as option-source
   evidence; and
7. grants no conflict-resolution or bulk-acquisition authority.

Any V4/successor rule must be frozen separately from completed diagnostic evidence.
