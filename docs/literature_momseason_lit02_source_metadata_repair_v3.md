# LIT-02 source metadata repair v3

Authority: **EXPLORATORY / NON-AUTHORITATIVE**

Repair-v3 is a source-feasibility package only. It does not authorize economic testing, Phase33, PAPER, LIVE, broker access, order writes, production behavior, or merge to main.

## Accepted base evidence

Repair-v3 starts only from the accepted exact-target-machine repair-v2 result and cached residual diagnostic:

- repair-v2 exact target-machine head: `b51857461f7034591b32079ad126ea9c7ffa7310`
- repair-v2 classification fingerprint: `6d11081f7acf39783a9c6b2fde8119a1f19f9b8b3b87be0ab3fac59a8381faa2`
- repair-v2 report fingerprint: `dca474d2d88c09f904c33e33659fbb88e4cdadcecd9d40666971b4482a1c657e`
- repair-v2 residual diagnostic exact target-machine head: `a303510e6fce1aa40040404eac93ae3b46fd31cd`
- repair-v2 residual diagnostic fingerprint: `90ed1f6ca7b433567d6a063f8ebead9c3789181f659c9175bb592ea8fe70b091`
- accepted cases: 199
- accepted repair-v2 resolved: 96
- accepted repair-v2 unresolved: 103
- accepted repair-v2 source coverage: 48.24%
- economic outcome values read: 0
- new price/return reads: 0
- protected return rows read: 0
- protected holdout consumed: False

The existing `development/l2/m/` and `development/l2/m2/` evidence remains immutable. Repair-v3 writes only to `development/l2/m3/`.

## Why another source repair is justified

The accepted residual diagnostic shows that the unresolved population still contains structured official-source gaps rather than an economic result:

- terminal effective date unresolved: 79 cases
- Massive ticker-event source absent: 71 cases
- no Composite FIGI: 25 cases
- terminal transaction context unresolved: 25 cases
- no admissible official SEC evidence under repair-v2: 15 cases
- multiple terminal cash values: 10 cases
- successor identity required: 4 cases

Most importantly, the cached parser evidence contains hundreds of terminal candidates with explicit cash terms but no admissible executed-event date under the repair-v2 current-report source set. That creates a source-only reason to test a narrowly defined additional class of official SEC transaction-result filings.

## Repair-v3 contract

Contract:

`lit02-source-metadata-repair-v3-official-sec-final-transaction-amendments-no-prices`

Repair-v3 does **not** change the frozen LIT-02 economic return paths. It changes only which official SEC filing classes may be searched for the already-required executed transaction facts.

### Added official SEC filing classes

Only these forms are added:

- `SC TO-T/A` — amended third-party tender-offer statements, which may contain final offer results and completed back-end merger facts.
- `SC 13E3/A` — amended Rule 13e-3 transaction statements, whose final amendments may report completion of a going-private transaction.

An added-form filing is not sufficient merely because it exists. The unchanged CI-certified contextual parser must still find an explicit executed transaction or explicit ticker-change fact with an effective/closing date on or before the frozen endpoint.

For a terminal cash path, the same explicit executed-event context must support the per-share cash consideration. Stock and mixed paths retain the same successor identity requirements.

### Explicitly excluded forms

Repair-v3 does not use these as terminal-return authority:

- `SC TO-C`
- non-amended `SC TO-T`
- `SC TO-I` / `SC TO-I/A`
- non-amended `SC 13E3`
- `PREM14A` / `DEFM14A`
- `S-4` / `S-4/A`
- `F-4` / `F-4/A`
- `424B3`
- `425`
- `25-NSE`
- `15-12B` / `15-12G`

These exclusions are intentional. A proposed merger term, registration/proxy statement, preliminary tender communication, final tender result without a completed terminal transaction, or exchange delisting notice does not by itself prove the frozen terminal return path.

In particular, Form 25 is not treated as merger completion authority because securities can be delisted for listing-rule failures while the issuer/security continues elsewhere.

## Frozen source-expansion mechanics

Repair-v3 freezes before target-machine acquisition:

- 199 total cases
- 96 accepted repair-v2 resolved cases reused immutably
- only 103 accepted repair-v2 unresolved cases eligible for retry
- official SEC source only for the added filing classes
- fixed 370-day lookback
- existing 10-day filing-forward allowance
- maximum 32 added-form candidate filings per CIK/endpoint lookup
- unchanged repair-v2 CI-certified parser:
  `lit02-source-metadata-repair-v2-parser-certified-context-forward-window-v2`
- same latest-admissible-effective-event conflict handling
- same ticker/successor identity verification
- same 100% source-coverage requirement
- zero economic outcome reads
- zero market-price/return reads
- zero protected reads
- zero broker/order/PAPER/LIVE writes
- no ticker-specific exceptions

The source-expansion fingerprint is generated deterministically from this contract and printed before acquisition.

## Scientific interpretation

Repair-v3 may only answer whether the frozen missing-source population can be made source-complete under the accepted official-source hierarchy.

It cannot establish positive or negative MomSeason alpha.

If exact-head repair-v3 reaches 100% source coverage, a **new fresh/non-reused LIT-02 economic-development design must still be frozen before any economic outcome read**.

If exact-head repair-v3 remains below 100%, economic testing remains blocked. At that point LIT-02 should close as source-infeasible unless a separate, general, outcome-independent source mechanism is defined and frozen before any further provider read. The 100% gate must not be lowered.
