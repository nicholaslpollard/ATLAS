# ATLAS Pre-Phase33 SEC Schedule 13D/13G Beneficial-Ownership Source Feasibility

**State: FROZEN SOURCE-ONLY FEASIBILITY GATE; TARGET SOURCE RESULT NOT YET READ. Alpha hypotheses are not frozen, market outcomes are forbidden, protected evidence remains unread, and Phase33 remains blocked.**

## Purpose

The preceding SEC XBRL fundamental-quality/accrual mechanism closed `ACCEPTED_NEGATIVE`. ATLAS therefore moves to a materially different information mechanism rather than retuning the failed family.

This gate asks only whether official SEC Schedule 13D/13G beneficial-ownership disclosures can support a trustworthy point-in-time historical research population with authoritative filing chronology and security-level identity. It does **not** test returns, select a trading direction, rank candidate hypotheses by performance, or grant strategy/trading authority.

Mechanism:

`PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`

Feasibility contract:

`alpha-gate-sec-beneficial-ownership-feasibility-v1-schedule13d13g-source-only-no-market-outcomes`

Frozen feasibility fingerprint:

`f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`

Source lineage begins only after accepted SEC XBRL closeout merge:

`083c0a5742b161cf4b7c04d5bf0246f3057f6c19`

## Scientific boundary

Alpha hypotheses are **not frozen** at this gate. The source audit reads zero market outcomes, zero stock/SPY forward returns, zero target labels, and zero protected returns. The master protected window `2026-05-12..2026-08-11` remains unconsumed.

A `FEASIBILITY_PASS` authorizes only a later scientific freeze. It does not create historical `SUPPORTED` alpha and does not satisfy Phase33 entry.

A `FEASIBILITY_FAIL` is preserved as evidence. Its frozen source gates may not be reduced after seeing the target result.

## Authoritative sources

### SEC discovery

Official SEC quarterly master indexes:

`www.sec.gov/Archives/edgar/full-index/YYYY/QTR#/master.idx`

Frozen source window: **2016-01-01..2026-08-11**. The gate reads exactly 43 quarterly index files, from 2016 Q1 through 2026 Q3, and discards filings after the source cutoff.

The master index supplies CIK, company name, form type, filing date, and the exact complete-submission archive filename. ATLAS does not infer or guess archive artifacts.

### SEC complete submissions

For the frozen sample, ATLAS reads the official complete submission `.txt` file identified by the master index. From the SEC header it reconstructs:

- exact accession number;
- exact conformed submission type;
- filed-as-of date;
- `<ACCEPTANCE-DATETIME>`;
- `SUBJECT COMPANY` CIK and name.

The subject-company CIK, not the reporting-person/filer CIK, is the issuer identity that must reconcile to the quarterly master index.

### PIT security identity

The decision timestamp is converted to the first XNYS regular-session open **strictly after** SEC acceptance. ATLAS then queries the accepted Massive reference seam using exact subject CIK + decision date with `active=true` and `type=CS`.

The existing identity contract remains:

`instrument-identity-v4-no-issuer-level-medium-collapse`

Only STRONG or MEDIUM security-level identity is eligible. Exactly one unique common-stock instrument is required. Zero eligible securities fail mapping; multiple eligible common-stock instruments are ambiguous and fail closed. No arbitrary share-class choice, ticker-only continuity, current-universe backprojection, or alias substitution is permitted.

## Form and era coverage

Accepted historical form aliases:

- `SC 13D`
- `SC 13D/A`
- `SC 13G`
- `SC 13G/A`
- `SCHEDULE 13D`
- `SCHEDULE 13D/A`
- `SCHEDULE 13G`
- `SCHEDULE 13G/A`

These normalize to four source classes:

- `13D_INITIAL`
- `13D_AMENDMENT`
- `13G_INITIAL`
- `13G_AMENDMENT`

The SEC structured-data compliance boundary is frozen at **2024-12-18**. Filings before that date are `legacy`; filings on or after it are `structured`.

The source sample is stratified across all eight combinations of era × normalized form class. ATLAS deterministically selects **25 filings in each of eight strata**, for exactly 200 sampled filings, using SHA-256 rank of accession + frozen feasibility contract. No market information participates in sample selection.

## Frozen feasibility gates

These thresholds were frozen before the target source run:

- all **43** quarterly SEC master indexes must be successfully read;
- each of the eight strata must contain at least **50** discovered eligible filings;
- sample must be exactly **25 per stratum / 200 total**;
- complete-submission parse success >= **190**;
- accession reconciliation >= **190**;
- form reconciliation >= **190**;
- filing-date reconciliation >= **190**;
- subject-company CIK reconciliation >= **185**;
- acceptance-time decision sessions reconstructed >= **190**;
- unique reconciled subject CIKs >= **140**;
- structured-era `primary_doc.xml` markers >= **90** of 100 sampled structured filings;
- legacy-era CUSIP markers >= **90** of 100 sampled legacy filings;
- unambiguous PIT active common-stock mappings >= **130**;
- parsed filings per individual stratum >= **22** of 25.

`Item 4` and “date of event which requires filing” markers are source diagnostics only at feasibility. They are not alpha labels and are not pass/fail thresholds.

## Authority and mutation boundary

Allowed:

- official SEC archive reads required by this source census;
- Massive exact CIK/date common-stock reference reads;
- deterministic local source caches and the derived source-only report.

Forbidden:

- market price/return reads or target labels;
- protected performance reads;
- provider mutations;
- broker reads or writes;
- order writes;
- PAPER submission;
- LIVE writes;
- automation writes;
- automatic broker failover.

The feasibility runner has no threshold, sample-size, direction, horizon, or strategy override arguments.

## Output

The source-only report is written to:

`data/derived/strategy_evaluation/pre_phase33/beneficial_ownership_feasibility_v1/source_audit.json`

Provider evidence is cached under:

`data/provider/pre_phase33_beneficial_ownership/v1`

The report records source counts, stratum coverage, exact SEC reconciliation, acceptance-time chronology, structured/legacy diagnostics, PIT identity outcomes, source/cache read counts, and explicit zero outcome/trading authority.

## Result semantics

### `FEASIBILITY_PASS`

Only source/chronology/identity feasibility has passed. The next coherent work package must freeze, before any market outcomes, a finite Schedule 13D/13G hypothesis family plus exact ownership/purpose semantics, chronology, outcomes, costs, dependence treatment, multiplicity, sample/concentration/robustness gates, winner/finalist rules, and protected-evidence policy.

### `FEASIBILITY_FAIL`

Preserve the failure and diagnose its owning source layer. Do not reduce the frozen 43 / 50 / 200 / 190 / 185 / 140 / 90 / 90 / 130 / 22 gates after observing the result. Provider/parser defects may be repaired while retaining the same frozen scientific gate when scientifically valid; genuine source insufficiency requires a new preregistered mechanism/source decision.

## Downstream boundary

Historical supported modern alpha remains **0**. Phase33 Signal-to-Trade Construction remains blocked. LIVE remains disabled and automatic broker failover remains disabled.
