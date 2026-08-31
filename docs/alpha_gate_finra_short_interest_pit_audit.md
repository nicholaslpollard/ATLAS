# ATLAS Pre-Phase33 FINRA Short-Interest PIT Source Audit

**State:** frozen source/chronology/identity audit; market outcomes remain forbidden.

The accepted source-feasibility target is exact head:

`104e1c6ca44a85a0a166ea24c0318d34f3c3bbb6`

Its frozen feasibility fingerprint is:

`cc80a87f020a4dece88430d20aa62e13d4dcd898656d60d53dea49b3ef975bc4`

The accepted target-machine census was `FEASIBILITY_PASS`: 12/12 files, six years, 244,979 total rows, 137,575 exchange-listed rows, 20,248 unique exchange-listed symbols, 2,328 revision-flagged rows, 514 stock-split-flagged rows, zero target/protected outcomes, and zero external mutation authority.

## Frozen PIT audit

Contract:

`alpha-gate-finra-short-interest-pit-audit-v1-publication-revision-split-active-common-stock-no-market-outcomes`

Fingerprint:

`ffdb7389ceae73f31a3781a79a8d825338102b9084cb30dd03bf21f6bf003846`

Mechanism remains:

`PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING`

No signal direction, threshold, ranking, performance horizon, or finalist rule is defined here.

## Publication chronology

Official FINRA sources establish:

- firms report short interest twice monthly under Rule 4560;
- reports are due on the second business day after the settlement date;
- consolidated data is provided for publication on the **7th business day after settlement**;
- FINRA Developer documentation states Consolidated Short Interest is available via the dataset by **4:40 PM ET** on the publication date.

Because 4:40 PM ET is after the regular U.S. equity close, ATLAS may not use the publication-date session. The frozen decision session is the **first XNYS regular-session open strictly after the publication date**.

The XNYS 7-session calculation is pinned against official 2026 FINRA schedule anchors:

- 2026-03-31 -> 2026-04-10
- 2026-06-30 -> 2026-07-10
- 2026-07-31 -> 2026-08-11
- 2026-12-31 -> 2027-01-12

Official references:

- `https://www.finra.org/filing-reporting/regulatory-filing-systems/short-interest`
- `https://www.finra.org/finra-data/browse-catalog/equity-short-interest`
- `https://developer.finra.org/docs`

## Revision and split handling

FINRA states that when corrections are made a Revision Flag appears and **only the most recent data is made available**. A present-day historical download therefore cannot reconstruct the original value or the time at which the correction became public.

Frozen rule: **every nonblank revision-flagged row is excluded** from predictor eligibility. ATLAS will not infer the original value or revision timestamp.

A nonblank stock-split flag is also excluded from predictor eligibility. This avoids comparing split-affected current/previous share quantities or adjusted volume without a separately preregistered corporate-action normalization contract.

## Security identity

FINRA's reporting instructions require the symbol and primary exchange/market code to be valid **as of the designated settlement date**. Exchange-listed codes are frozen as:

- `A` -> NYSE -> `XNYS`
- `B` -> NYSE American -> `XASE`
- `E` -> NYSE Arca -> `ARCX`
- `H` -> Cboe BZX -> `BATS`
- `R` -> Nasdaq -> `XNAS`

FINRA short-interest reports can contain common shares, preferred shares, warrants, units, or ADRs, so exchange-listed status alone is not sufficient.

For every immutable exchange-listed row in the 12 frozen files, ATLAS requires:

1. exact FINRA symbol;
2. expected primary exchange;
3. Massive `active=true`, `type=CS` at the settlement date;
4. Massive `active=true`, `type=CS` at the leakage-safe decision date;
5. exactly one qualifying instrument at both dates;
6. the same STRONG/MEDIUM ATLAS instrument identity at both dates.

Anything else fails closed for that row.

## Frozen acceptance gates

- all 12 source files reacquired successfully;
- accepted feasibility report exact counts reconcile before source reads;
- official publication anchors reconcile exactly;
- duplicate FINRA `(symbol, exchange)` source rows: **0**;
- immutable exchange-listed rows after revision/split exclusions: **>=100,000**;
- PIT-eligible active-common-stock rows: **>=60,000**;
- unique PIT instruments: **>=5,000**;
- files with at least 2,500 PIT-eligible rows: **>=10 of 12**.

These thresholds were frozen before the PIT target read.

## Authority boundary

During this audit:

- alpha hypotheses frozen: **false**;
- market/performance outcomes: **0 / forbidden**;
- protected return rows: **0 / forbidden**;
- protected holdout consumed: **false**;
- FINRA and Massive reference reads: **allowed**;
- provider writes: **0**;
- broker reads/writes: **0 / 0**;
- orders/PAPER/LIVE/automation: **0 / 0 / 0 / 0**;
- Phase33 authority: **false**.

A `PIT_AUDIT_PASS` authorizes only the next preregistration step. It is not evidence of alpha.
