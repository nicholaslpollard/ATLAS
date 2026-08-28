# Phase 31 Form-4 Feasibility Incident — Chronology Invariant

**Status:** ROOT CAUSE CLASSIFIED / SOURCE-QUALITY REPAIR TARGET PASS / SCIENTIFIC CONTRACT FROZEN. Phase31 itself is not accepted.

This record preserves the first real Phase31 feasibility failure and its resolution path without rewriting the failed raw-source gate.

## Original failed target

- branch `phase-31-sec-insider-transaction-alpha`
- exact head `b59a64938eb84c0c1e7df3aaea390cc437326f94`
- feasibility fingerprint `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`
- endpoint `/stocks/filings/vX/form-4`
- result `FEASIBILITY_FAIL`
- sole failed check `transaction_dates_do_not_postdate_filings`
- target/protected outcomes 0
- trading authority 0.

The chronology invariant computes `filing_date - transaction_date` and requires no negative result. The chronology invariant remains intact.

## Diagnostic

Implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

Diagnostic violation artifact SHA256: `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`

Target diagnostic:

- 36,854 transaction rows with both dates
- before filing 33,510
- same day 3,343
- after filing 1
- one violating accession / issuer / owner
- accession `0000950170-23-043337`
- ticker WISH
- filing `2023-08-17`
- returned transaction `2023-09-15`
- 29-day impossible gap
- code M / derivative RSU / acquired A / direct D / 10b5-1 false / timeliness O
- violation SHA `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`
- provider calls 0
- market outcomes 0
- broker/order/PAPER/LIVE 0.

## Root cause

**Massive early-access/beta source-association/data-quality defect.**

Massive documents `filing_date` as date submitted to the SEC, `transaction_date` as the transaction date, and timeliness `O` as on-time. ATLAS copies those provider fields directly. The row is therefore internally impossible under the provider's documented semantics.

This is not an ATLAS parser bug, entitlement failure, or a legitimate future-dated Form-4 category. ATLAS does not fabricate a corrected accession.

## Frozen repair

Policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Rules:

- preserve raw rows unchanged;
- any transaction with `transaction_date > filing_date` contaminates its entire accession;
- quarantine the whole accession from alpha authority;
- missing accession on a violating row fails closed;
- no date correction or inferred reassignment;
- no ticker/code/security/role/performance special-case;
- authoritative source must contain zero chronology-invalid rows.

There is **no** "one bad row is acceptable" tolerance.

## Repair target PASS

Implementation head:

`03dcd371e79554cc9e52a1bb4ed3b642a067ca4b`

Exact target result:

- raw 45,921
- violation seeds 1
- contaminated accessions 1
- quarantined accession rows 6
- authoritative rows 45,915
- quarantine SHA `586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb`
- target/protected outcomes 0
- scientific-policy freeze authorized True
- Phase32 entry False.

The original `FEASIBILITY_FAIL` still stands as raw-provider provenance. The repair PASS establishes a stricter alpha-source layer rather than validating the bad row.

## Scientific continuation

The finite Phase31 scientific contract was frozen after the repair PASS and before any market-outcome read.

Scientific policy fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

See `docs/phase31_scientific_contract.md`.

Next target: full historical Form-4 acquisition and exact overlap reconciliation. No performance work begins until that source gate and predictor-only gate pass.