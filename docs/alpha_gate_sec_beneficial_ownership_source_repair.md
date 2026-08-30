# ATLAS Pre-Phase33 SEC Schedule 13D/13G Beneficial-Ownership Targeted Source Repair V2

**State: V1 TARGET RESULT PRESERVED `NOT ACCEPTED`; TARGETED SOURCE REPAIR V2 FROZEN BEFORE RERUN. Alpha hypotheses remain unfrozen, market outcomes remain forbidden, protected evidence remains unread, and Phase33 remains blocked.**

## Parent v1 gate and preserved failure

Parent source-only feasibility contract:

`alpha-gate-sec-beneficial-ownership-feasibility-v1-schedule13d13g-source-only-no-market-outcomes`

Parent feasibility fingerprint:

`f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`

Target-machine v1 head:

`37194556012bc6df3f5e5579f2dacdcb5bed738b`

The first real source run is permanently preserved as **`NOT ACCEPTED`**. It stopped before submission sampling or any market outcome read with:

`conflicting SEC master-index metadata for accession 0001193125-16-687002`

Observed v1 index progress at termination:

- expected quarterly indexes: **43**;
- successful quarterly indexes: **9**;
- failed quarterly indexes: **34**;
- eligible master-index rows accumulated before the fail-closed accession check: **49,349**;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- provider/broker/order/PAPER/LIVE/automation mutations: **0**.

The v1 result is not rewritten as a pass and its frozen fingerprint remains historical evidence.

## Diagnosed root causes

### 1. SEC quarterly-index transport bound was incorrectly shared with complete submissions

The read-only SEC archive client used one **20,000,000-byte** maximum for both complete submissions and quarterly `master.idx` files. That bound is below the size of many official quarterly indexes in the frozen source window. Examples from the SEC directory listings include approximately:

- 2024 Q4 `master.idx`: **24,983 KB**;
- 2025 Q1 `master.idx`: **29,594 KB**;
- 2026 Q1 `master.idx`: **32,282 KB**.

This directly explains the large sequence of quarterly-index read failures in v1. The owning-layer repair separates bounded response limits:

- quarterly `master.idx`: **64,000,000 bytes**;
- complete submission `.txt`: **20,000,000 bytes**.

The SEC host/path allowlist, declared fair-access identity, retry policy, sequential request behavior, and read-only authority remain unchanged.

### 2. V1 incorrectly treated the master-index CIK as the subject-company security identity

The SEC master index provides an indexed entity CIK plus the exact archive filename. For EDGAR submissions, the accession number can reflect the login CIK used to submit a filing, and a Schedule 13D/13G complete-submission header separately identifies `SUBJECT COMPANY` and `FILED BY` entities.

Therefore a single filing/accession can legitimately have index/archive entity associations that are not the security issuer represented by `SUBJECT COMPANY`. V1 incorrectly required differing master-index rows for one accession to be identical and also compared the parsed subject-company CIK to the master-index CIK.

The v2 repair separates those roles:

- **master-index CIK** = preserved index/archive entity provenance;
- **SEC complete-submission `SUBJECT COMPANY` CIK** = authoritative issuer/security identity;
- Massive PIT identity lookup = exact authoritative subject CIK + decision date + `active=true` + `type=CS`.

No current ticker, arbitrary issuer alias, or reporting-person CIK is substituted for the authoritative subject-company CIK.

## Frozen targeted repair contract

Repair contract:

`alpha-gate-sec-beneficial-ownership-source-repair-v2-master-index-role-bounded-index-size-no-market-outcomes`

Frozen repair fingerprint:

`78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c`

Mechanism remains:

`PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`

This is a **source-only owning-layer repair**, not a new alpha hypothesis, performance retune, or threshold relaxation.

## Duplicate-accession rule

V2 groups discovery by accession. Multiple master-index entity associations for one accession are allowed only when the filing-level semantics agree exactly on:

- conformed form type;
- filing date;
- legacy/structured era;
- normalized form class;
- stratum.

When those filing semantics agree, ATLAS deterministically retains one canonical index/archive row for the exact accession. If any of those filing semantics conflict, the accession still fails closed.

The number of collapsed duplicate accession/index associations is recorded as a diagnostic in the v2 report.

## Unchanged source population and numeric gates

The source window remains **2016-01-01..2026-08-11** and the structured-data compliance boundary remains **2024-12-18**.

The deterministic sample remains **200 filings = 25 filings in each of eight era × form-class strata** using the same accession + parent feasibility contract hash ranking. No market information participates in sample selection.

All numeric thresholds are retained:

- all **43** quarterly SEC master indexes must be successfully read;
- each of eight strata must contain at least **50** discovered eligible filings;
- sample exactly **25 per stratum / 200 total**;
- complete-submission parse success >= **190**;
- accession reconciliation >= **190**;
- form reconciliation >= **190**;
- filing-date reconciliation >= **190**;
- authoritative SEC-header `SUBJECT COMPANY` CIK extraction >= **185**;
- acceptance-time decision sessions reconstructed >= **190**;
- unique authoritative subject CIKs >= **140**;
- structured-era `primary_doc.xml` markers >= **90**;
- legacy-era CUSIP markers >= **90**;
- unambiguous PIT active common-stock mappings >= **130**;
- parsed filings per individual stratum >= **22**.

The v1 numeric value **185** is not reduced. Its source-semantic definition is corrected before rerun from the invalid `subject CIK == master-index CIK` assumption to successful extraction of the authoritative `SUBJECT COMPANY` CIK from the official complete-submission header.

The count of cases where subject CIK happens to equal master-index CIK remains a diagnostic only because SEC entity roles do not require equality.

## Chronology and security identity

For every parsed sample filing:

1. exact accession, form, and filed-as-of date must reconcile to the selected master-index filing record;
2. `SUBJECT COMPANY` CIK is extracted from the official complete-submission header;
3. `<ACCEPTANCE-DATETIME>` is reconstructed;
4. decision session is the first XNYS regular-session open strictly after acceptance;
5. Massive is queried with exact subject CIK + decision date, `active=true`, `type=CS`;
6. only STRONG or MEDIUM security-level identity is eligible;
7. exactly one unique common-stock instrument is required; zero or multiple eligible instruments fail mapping.

The accepted identity contract remains:

`instrument-identity-v4-no-issuer-level-medium-collapse`

## Scientific and authority boundary

Alpha hypotheses remain **not frozen**. V2 reads:

- zero stock forward returns;
- zero SPY forward returns;
- zero target labels;
- zero protected returns.

Provider mutations, broker reads/writes, order writes, PAPER submissions, LIVE writes, automation writes, and automatic broker failover remain disabled.

A v2 `FEASIBILITY_PASS` can authorize only the next complete scientific freeze. It cannot create `SUPPORTED` alpha or satisfy Phase33 entry.

A v2 `FEASIBILITY_FAIL` must be preserved and root-caused under the same repaired source contract. None of the retained numeric gates may be lowered after the rerun.

## Output

V2 writes its source-only report to:

`data/derived/strategy_evaluation/pre_phase33/beneficial_ownership_feasibility_v2/source_audit.json`

Raw provider evidence continues to reuse the v1 source cache under:

`data/provider/pre_phase33_beneficial_ownership/v1`

Reusing raw source bytes does not reuse any performance evidence; v1 opened no market outcomes.

## Downstream boundary

Historical supported modern alpha remains **0**. Phase33 Signal-to-Trade Construction remains blocked. The master protected window `2026-05-12..2026-08-11` remains unconsumed. LIVE and automatic broker failover remain disabled.
