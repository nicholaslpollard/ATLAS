# Pre-Phase33 Alpha Gate — SEC XBRL PIT Source / Chronology / Identity Audit

**Status: OPEN — source-only PIT audit. Feasibility is accepted. No alpha hypothesis is frozen, no market outcome is authorized, protected returns remain unread, and no trading authority is granted.**

## Accepted entry evidence

The prior SEC XBRL source census ran on target-machine head `5a8c15f95417390d0d64ff240977adfb38a20c45` and returned `FEASIBILITY_PASS` under frozen feasibility fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Accepted source-only result:

- source inventory unique CIKs: **4,400**;
- deterministic sample: **200**;
- successful Company Facts documents: **200**;
- failed Company Facts documents: **0**;
- accrual-history-ready issuers: **170**;
- profitability-history-ready issuers: **92**;
- group history-ready counts: assets **174**, net income **180**, operating cash flow **180**, revenue **136**, gross profit **78**, cost of revenue **97**;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- provider reads/writes: **200 / 0**;
- broker reads/writes, orders, PAPER, LIVE, automation: **0**.

Accepted feasibility evidence fingerprint over the frozen result fields:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

This evidence authorizes only this source/chronology/identity audit. It does not authorize an alpha hypothesis or any performance read.

## Why this audit is required

SEC Company Facts is a current aggregate across filings, not itself a historical point-in-time database snapshot. The SEC documents that Company Facts aggregates standardized facts from submissions and that the submissions API supplies filing history metadata. ATLAS must therefore reconstruct historical availability by exact accession and official SEC acceptance time rather than treating the current aggregate as if every row had always been known.

The audit proves that ATLAS can:

1. preserve the exact accession that supplied each fact;
2. reconcile that accession to an original SEC `10-Q` or `10-K` record;
3. obtain authoritative SEC `acceptanceDateTime` without guessing publication time;
4. map the filing to the first XNYS session open strictly after acceptance;
5. preserve later comparative/restated values as later accession versions instead of overwriting earlier history;
6. fail closed on contradictory values inside one accession/context;
7. map issuer CIK to a point-in-time tradable security without collapsing multiple securities from one issuer.

## Frozen audit contract

Contract:

`alpha-gate-xbrl-pit-audit-v1-source-only-accession-versioned-no-market-outcomes`

Audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

Mechanism:

`PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`

Source fact window remains `2016-01-01..2026-08-11`.

### Deterministic issuer sample

Exactly **40** issuers are selected from the accepted feasibility-ready population. Eligibility is source-only: the issuer must have passed accrual-history readiness or profitability-history readiness in the accepted feasibility report.

Selection order is ascending:

`SHA256(zero_padded_cik + ':' + audit_contract)`

No return, price, event label, Phase32 candidate, or later audit result enters issuer selection.

### Deterministic accession sample

For each audit issuer, ATLAS independently extracts exact Company Facts rows for the allowed fundamental tags and exact original forms `10-Q` and `10-K` only. Amendment forms such as `10-Q/A` and `10-K/A` are excluded.

Clean accessions are ordered by Company Facts `filed` date and accession number. Up to **5** accessions per issuer are selected at evenly spaced deterministic positions including the earliest and latest accession. This intentionally probes the historical span rather than only recent filings.

### Authoritative filing chronology

Company Facts supplies the fact/accession association. Official SEC submissions metadata supplies filing identity and `acceptanceDateTime`.

The audit uses the already accepted SEC EDGAR HTTPS/fair-access/retry/cache seam and permits only SEC-declared submissions root/shard JSON. The Phase32 8-K helper remains unchanged; the XBRL audit adds a bounded original-form metadata client that accepts only exact `10-Q` and `10-K`.

For every audited filing:

- CIK must match exactly;
- accession must match exactly;
- Company Facts `filed` date must equal SEC submissions `filingDate`;
- Company Facts form must equal SEC submissions form;
- form must be exact original `10-Q` or `10-K`;
- SEC acceptance time must be parseable and timezone-aware.

Decision session rule:

`FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE`

No market return is read to establish that session.

### Fact versioning / restatement rule

ATLAS never collapses facts across accessions.

Frozen rule:

`EXACT_ACCESSION_VERSIONED_NEVER_OVERWRITE_ACROSS_ACCESSIONS`

A later original filing may repeat or revise a fact for an earlier economic period. Both versions remain attached to their exact accession and filing chronology. A future PIT feature builder may use only versions whose acceptance time was already public at the decision time.

Within one accession, the semantic context key is:

`tag + unit + start + end + fy + fp + frame`

Exact duplicate rows are harmless and counted. Two distinct values for the same semantic context inside the same accession are not guessed away; they trigger the frozen fail-closed conflict gate.

### Point-in-time issuer-to-instrument identity

Massive `/v3/reference/tickers` is queried with exact:

- `cik`;
- point-in-time `date` equal to the reconstructed decision session;
- `market=stocks`;
- both active and inactive states.

The accepted identity contract remains:

`instrument-identity-v4-no-issuer-level-medium-collapse`

Only STRONG or MEDIUM security-level identity is eligible. CIK alone never becomes a security identifier. If zero eligible instruments exist, mapping fails closed. If multiple unique eligible instruments exist for one issuer/date, mapping is ambiguous and fails closed. ATLAS does not arbitrarily pick a share class.

## Frozen source-only gates

The audit passes only if all are true:

- audit issuer sample = exactly **40**;
- successful Company Facts documents >= **36**;
- selected clean original 10-Q/10-K filings >= **180**;
- exact SEC filing metadata reconciliations >= **170**;
- acceptance-time decision sessions reconstructed >= **170**;
- unambiguous PIT instrument mappings >= **120**;
- issuers with at least 3 unambiguous audited mappings >= **30**;
- same-accession semantic-context conflicts <= **0**.

These thresholds are frozen before the target audit is run. They are source/chronology/identity sufficiency gates, not return-performance thresholds.

## Explicitly forbidden

This audit may not read or derive:

- stock returns;
- SPY returns;
- options outcomes;
- future closes;
- target labels;
- the Phase32 protected returns;
- any performance-ranked alpha hypothesis.

It may not perform provider writes, broker reads/writes, orders, PAPER submissions, LIVE actions, scheduler/automation mutations, or automatic broker failover.

Alpha hypotheses remain **not frozen** during this audit.

## Acceptance semantics

`AUDIT_PASS` means only that ATLAS has demonstrated a viable source-only PIT reconstruction path for this fundamental mechanism. It authorizes the next scientific work package: freeze a finite hypothesis family plus outcomes, costs, chronology, dependence, multiplicity, sample/concentration gates, winner/finalist rules, and protected-evidence policy before any governed market outcome is opened.

`AUDIT_FAIL` is valid evidence. The failure must be diagnosed at the source/chronology/identity layer; the frozen thresholds or ambiguity rules may not be weakened after seeing the result.

## Target-machine runner

`scripts/run_alpha_gate_xbrl_pit_audit.py`

The runner is resumable from atomic local Company Facts, SEC submissions, and Massive CIK/date reference caches. A rerun may therefore require fewer live reads without changing the audit population or gates.
