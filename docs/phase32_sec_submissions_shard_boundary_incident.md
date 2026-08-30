# Phase32 SEC Submissions Shard-Boundary Incident

Status: **CORRECTION IMPLEMENTED / TARGET-MACHINE VALIDATION REQUIRED / NO MARKET OUTCOMES OPENED**

## Incident

After the independently diagnosed crash-cache corruption was repaired and the full Phase32 local cache parse surface passed, the resumable full-history predictor/source acquisition progressed to `27,225 / 36,309` filing entities and stopped before any market-outcome read at:

`SEC submissions metadata does not cover requested accession/date: 0001564708-23-000471 / 2023-10-05`

The failing filing is a News Corp original 8-K under CIK `0001564708`.

## Read-only root-cause evidence

Local Massive source evidence contains the exact filing:

- accession: `0001564708-23-000471`;
- issuer CIK: `0001564708`;
- filing date: `2023-10-05`;
- original form: `8-K`;
- index ticker: `NWS`;
- semantic tickers: `NWS`, `NWSA`;
- frozen semantic family: `capital_and_financing/shareholder_returns/share_repurchase_program`.

Official SEC root metadata at `data.sec.gov/submissions/CIK0001564708.json` showed:

- exact accession absent from `filings.recent`;
- `filings.recent` date span beginning `2023-10-06`;
- one SEC-declared historical shard, `CIK0001564708-submissions-001.json`;
- root-declared shard range ending `2023-10-04`.

The requested filing date therefore fell in a one-calendar-day gap between the root's declared historical-shard end and recent-file start.

A bounded read-only diagnostic then inspected only the SEC-declared nearest shard. The shard itself reported an actual row span through `2023-10-05` and contained the exact target accession:

- accession: `0001564708-23-000471`;
- filing date: `2023-10-05`;
- acceptanceDateTime: `2023-10-04T22:16:27.000Z`;
- form: `8-K`;
- items: `8.01,9.01`;
- primary document: `nws-20231004.htm`.

Diagnostic disposition:

`EXACT_ACCESSION_PRESENT_IN_NEAREST_SEC_DECLARED_SHARD_DESPITE_RANGE_GAP`

This proves a root/shard boundary-metadata mismatch: the SEC root's `filingFrom` / `filingTo` summary can understate the actual content boundary of an SEC-declared submissions shard by one calendar day.

## Root cause

The ATLAS `SECEDGARClient.filing_metadata()` implementation treated the root-declared `filingFrom..filingTo` range as a hard precondition for reading a historical shard. That is stricter than the observed official SEC data semantics and can reject an exact authoritative filing that is present in a SEC-declared shard at a one-day rollover boundary.

This is a source-reconciliation implementation defect, not a hypothesis, identity-v4, performance, provider-ticker, or protected-evidence defect.

## Corrected bounded rule

Contract:

`phase32-sec-submissions-declared-shard-rollover-boundary-v1`

The corrected SEC submissions lookup preserves the accepted architecture and adds only the empirically demonstrated boundary case:

1. `filings.recent` exact-accession lookup remains first.
2. If historical lookup is required, SEC-declared shards whose root metadata covers the requested filing date remain primary.
3. Only when **no** SEC-declared shard covers the requested date, an SEC-declared shard exactly **one calendar day** from that date may be inspected as a rollover-boundary candidate.
4. ATLAS never guesses a shard URL; every candidate name must come from the official root `filings.files` list and pass the existing shard-name validation.
5. The existing hard maximum of **two** shard reads per lookup remains unchanged.
6. More-distant shards remain ineligible.
7. If any date-covering shard exists, adjacent fallback is suppressed even if the covering shard does not contain the accession; that case remains fail-closed for separate diagnosis.
8. A returned row must still match the exact requested accession, exact requested filing date, and original form `8-K`.
9. Issuer CIK continues to be bound to the exact SEC company-submissions root used for the lookup.

The correction therefore changes shard-selection semantics only; it does not loosen filing identity.

## Regression requirements

Focused regressions must prove:

- the observed one-day rollover gap succeeds only through an SEC-declared shard containing the exact accession/date/original 8-K;
- a gap greater than one day remains fail-closed;
- a matching accession with the wrong filing date remains fail-closed;
- an adjacent shard cannot substitute when a date-covering shard exists;
- the two-shard hard bound remains enforced;
- amended/non-original forms remain rejected.

Validator:

`scripts/validate_phase32_sec_shard_boundary.py`

Unit regression:

`tests/unit/test_phase32_sec_shard_boundary.py`

## Scientific and authority boundary

This correction changes no Phase32 scientific policy. The frozen fingerprint remains:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

No hypothesis, direction, chronology, cost, outcome definition, sample gate, multiplicity control, identity-v4 rule, winner/finalist rule, or protected-evidence boundary changes.

Stock, SPY, options, development-return, and protected-return rows remain unread. Broker reads/writes, orders, PAPER, and LIVE remain zero/disabled.

Only after focused tests and validators pass may the source-only acquisition resume from its existing atomic caches. A source-acquisition PASS still requires the separately planned independent local source/predictor acceptance gate before any development return is opened.
