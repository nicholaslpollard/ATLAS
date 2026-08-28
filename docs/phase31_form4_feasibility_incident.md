# Phase 31 Form-4 Feasibility Incident — Chronology Invariant

**Status:** ROOT CAUSE CLASSIFIED. SOURCE-QUALITY REPAIR FROZEN. LOCAL FROZEN-EVIDENCE REPLAY PENDING. Phase31 itself is **NOT ACCEPTED**.

This document preserves the first real Phase31 feasibility failure, the completed root-cause diagnosis, and the approved non-performance repair boundary. It is not an alpha-policy result and grants no trading authority.

## Failed target evidence

- Branch: `phase-31-sec-insider-transaction-alpha`
- Exact target head: `b59a64938eb84c0c1e7df3aaea390cc437326f94`
- Frozen feasibility fingerprint: `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`
- Massive plan: **Stocks Starter**
- Endpoint: accepted read-only `MassiveRESTClient -> /stocks/filings/vX/form-4`
- Endpoint status: early-access/beta
- Target result: `FEASIBILITY_FAIL`
- Sole failed check: `transaction_dates_do_not_postdate_filings`
- Alpha hypotheses frozen: **False**
- Phase31 market outcomes read: **0**
- Protected candidate rows read: **0**
- Protected return rows read: **0**
- Protected holdout consumed: **False**
- Broker/order/PAPER/LIVE authority: **NONE**

Authenticated Form-4 retrieval succeeded and immutable provider evidence was written before the check failed. This was therefore not an entitlement failure.

## Chronology invariant

For each transaction row with both dates:

`lag_calendar_days = filing_date - transaction_date`

The original feasibility requires no negative lag. A negative lag means the provider row says the transaction happened after the filing.

The chronology invariant remains intact. The original failed report remains permanent provenance and is not rewritten to PASS.

## Frozen-evidence diagnostic result

Diagnostic implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

The target machine ran:

`scripts/diagnose_phase31_form4_lag.py`

Result:

- status: `DIAGNOSTIC_COMPLETE`
- pass: True
- transaction rows with filing + transaction dates: **36,854**
- transaction before filing: **33,510**
- transaction same day as filing: **3,343**
- transaction after filing: **1**
- violating rows/accessions/issuers/owners: **1 / 1 / 1 / 1**
- violation window: `mid_history`
- provider calls: **0**
- target/protected market outcomes read: **0**
- broker/order/PAPER/LIVE activity: **0**

The violating row:

- accession `0000950170-23-043337`
- ticker `WISH`
- issuer CIK `0001822250`
- owner CIK `0001967530`
- officer title `Chief Product Officer`
- filing date `2023-08-17`
- period of report `2023-08-15`
- returned transaction date `2023-09-15`
- transaction after filing by **29 calendar days**
- transaction code `M`
- `Restricted Stock Unit`
- security type derivative
- acquired `A`
- direct ownership `D`
- 10b5-1 false
- transaction timeliness `O`
- 496 shares
- transaction price/value 0.

Violation artifact SHA256:

`3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`

## Root-cause classification

**Classification: Massive early-access/beta source-association/data-quality defect.**

Evidence:

1. Massive documents Form-4 `filing_date` as the date submitted to the SEC.
2. Massive documents `transaction_date` as the date of the transaction.
3. Massive documents `transaction_timeliness=O` as **on time**.
4. Massive states Form 4 is filed after reportable insider transactions.
5. ATLAS maps these raw provider fields directly and does not swap or synthesize them.
6. A provider transaction date of 2023-09-15 attached to an accession filed 2023-08-17 is therefore internally impossible under the provider's documented semantics.
7. The endpoint is explicitly early-access/beta.
8. ContextLogic's public filing index independently shows the suspect accession as an August 17, 2023 Form 4 and later Form-4 filings on September 19, 2023.

This is **not** classified as:

- an ATLAS parser/mapping defect;
- an entitlement problem;
- a legitimate category that permits future transaction dates;
- a reason to weaken the chronology rule.

The diagnostic attributes `M`, derivative/RSU, officer, and WISH only as descriptive facts. The repair does not special-case any of them.

Public references:

- `https://massive.com/docs/rest/stocks/filings/form-4`
- `https://wish.gcs-web.com/financial-information/sec-filings/`

ATLAS does not infer which later accession should own the September event. No corrected row is fabricated.

## Frozen repair

Dedicated contract:

`docs/phase31_form4_source_quality_repair.md`

Policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

General rule:

- preserve raw provider rows unchanged;
- detect any transaction where `transaction_date > filing_date`;
- quarantine the **entire accession** containing such a row;
- fail closed if a violating row lacks accession identity;
- never clamp dates, swap fields, or infer replacement accessions;
- require zero chronology-invalid rows in the authoritative corpus;
- preserve provider-native ticker strings/case;
- make the decision without ticker, code, security type, role, price, returns, or profitability.

There is **no** "one bad row is acceptable" tolerance. The source-quality classifier handles any number of impossible accessions identically.

## Why this is not gate weakening

The original feasibility result stays failed.

The repair creates a stricter distinction between:

- **raw provider evidence** — immutable audit provenance, which may contain beta-provider defects; and
- **alpha-authoritative source evidence** — only rows surviving deterministic fail-closed source-quality rules.

The original raw-source chronology gate correctly discovered the provider defect. The new repair does not make the raw row valid. It prevents that contaminated accession from becoming authoritative.

This decision was made before any Phase31 market outcome or alpha hypothesis was read/frozen.

## Exact next action

Run the provider-free replay:

`scripts/run_phase31_form4_source_quality_repair.py`

It must verify the exact failed report, exact raw evidence SHAs, completed diagnostic, and exact violation artifact SHA. It then writes separate derived authoritative/quarantine artifacts.

A PASS authorizes only the next **scientific-policy freeze**. It does not:

- accept Phase31;
- grant alpha support;
- authorize performance reads before the scientific contract is frozen;
- consume protected returns;
- unlock Phase32;
- enable PAPER/LIVE.

If the repair fails, Phase31 remains in feasibility repair and the source-quality rule is not weakened.

## Continuity order

Future ATLAS chats should read:

1. `docs/roadmap.md`
2. `docs/current_status.md`
3. `docs/phase31_sec_insider_transaction_alpha.md`
4. this incident record
5. `docs/phase31_form4_source_quality_repair.md`
6. accepted code/validator/CI evidence.

`docs/roadmap.md` remains structurally correct. Phase31 remains the active alpha gate and Phase32 remains blocked.
