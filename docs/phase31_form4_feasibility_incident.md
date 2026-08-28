# Phase 31 Form-4 Feasibility Incident — Chronology Invariant

**Status:** OPEN ROOT-CAUSE INVESTIGATION. Phase31 feasibility is **NOT ACCEPTED**.

This document is the continuity record for the first real Phase31 target-machine feasibility run. It is not a scientific-policy change and grants no alpha/trading authority.

## Failed target evidence

- Branch: `phase-31-sec-insider-transaction-alpha`
- Exact target head: `b59a64938eb84c0c1e7df3aaea390cc437326f94`
- Frozen feasibility fingerprint: `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`
- Declared/actual planning entitlement: Massive **Stocks Starter**
- Endpoint: accepted read-only `MassiveRESTClient -> /stocks/filings/vX/form-4`
- Endpoint status: Massive early-access/beta
- Target result: `FEASIBILITY_FAIL`
- Failed check: `transaction_dates_do_not_postdate_filings`
- User-visible failure: `Phase31 Form-4 feasibility failed: transaction_dates_do_not_postdate_filings`
- Alpha hypotheses frozen: **False**
- Phase31 market outcomes read: **0**
- protected candidate rows read: **0**
- protected return rows read: **0**
- protected holdout consumed: **False**
- broker/order/PAPER/LIVE authority: **NONE**

The run reached authenticated Form-4 data retrieval and persisted immutable raw evidence before the chronology acceptance check failed. Therefore this is **not currently classified as a Stocks Starter entitlement failure**. It is a returned-data chronology/semantics quality failure until root cause is proven.

## The invariant that failed

For each Form-4 transaction row with both dates, feasibility computes:

`lag_calendar_days = filing_date - transaction_date`

The frozen feasibility check requires no row to have a negative lag. A negative lag means the provider row says `transaction_date > filing_date`.

The chronology invariant remains intact. It has **not** been weakened, reinterpreted, or removed to obtain PASS.

Massive documents `filing_date` as the date the filing was submitted to the SEC and `transaction_date` as the transaction date. The Phase31 provider adapter maps those provider fields directly. There is currently no accepted basis to swap or redefine them.

## Root-cause plan

The failed target already persisted immutable provider JSONL for all four frozen probe windows. The next step therefore does **not** call Massive again. `scripts/diagnose_phase31_form4_lag.py` reads those exact local evidence files, verifies every SHA against the failed feasibility report, and reports:

- transaction-before-filing / same-day / transaction-after-filing counts;
- violating rows, accessions, issuers, and owners;
- violation counts by probe window;
- transaction codes;
- derivative/non-derivative security type;
- acquired/disposed values;
- direct/indirect ownership;
- Rule 10b5-1 flags;
- timeliness flags;
- insider role combinations;
- exact future-gap-day distribution;
- filing-date -> transaction-date pairs;
- provider-native ticker counts;
- deterministic samples with accession/source provenance when available.

The diagnostic reads **no market outcomes**, performs **zero provider calls**, and has **zero broker/order/PAPER/LIVE authority**.

## Classification after diagnostic

Only evidence may determine the repair:

1. **ATLAS parser/mapping bug** — fix the mapping, retain the chronology gate, rerun feasibility.
2. **Authoritatively legitimate Form-4 semantic category** — document the governing SEC/provider semantics and freeze a category-aware handling rule before any performance read.
3. **Massive beta data defect** — define a fail-closed, provenance-preserving data-quality treatment only if defensible and frozen before performance; never silently coerce dates.
4. **Unresolved/ambiguous** — feasibility remains failed and Phase31 does not advance.

No performance result may be inspected to choose among these treatments.

## Documentation/continuity rule

Future ATLAS chats must read, in order:

1. `docs/roadmap.md`
2. `docs/current_status.md`
3. `docs/phase31_sec_insider_transaction_alpha.md`
4. this incident record while it remains open
5. accepted code/validator/CI evidence.

`docs/roadmap.md` remains structurally correct: Phase31 is still the active alpha gate and Phase32 remains blocked. This incident does not alter the remaining phase sequence.
