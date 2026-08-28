# Phase 31 — SEC Form-4 Insider-Transaction Alpha

**Status:** ACTIVE — FEASIBILITY REPAIR / ROOT-CAUSE ONLY. The first real target feasibility run is **NOT ACCEPTED**. No Phase31 market outcomes have been read. No Phase31 alpha hypotheses are frozen yet.

**Source foundation:** Phase30 merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e` (`ACCEPTED_NEGATIVE`) with zero protected return reads and the master holdout unconsumed.

**Open continuity record:** `docs/phase31_form4_feasibility_incident.md`.

## Plain-English phase start

ATLAS has tested five materially different modern alpha mechanisms and none earned support. Phase31 changes the information source again.

Corporate insiders—officers, directors, and certain large owners—must publicly report beneficial-ownership changes on SEC Form 4. Insider purchases may convey information or conviction not captured by existing price, cross-stock, relative-value, or news-arrival signals. Insider sales are more ambiguous because they can reflect diversification, taxes, compensation, or preplanned Rule 10b5-1 programs.

Phase31 will test whether structured, publicly filed insider transactions contain robust future-return information **after the filing is public** and after realistic trading costs. The phase is allowed to fail. Nothing will be tuned into a positive result.

The current work remains feasibility only. Market outcomes are forbidden until feasibility passes and a finite scientific policy is frozen.

## 1. Entry condition

Phase30 accepted negative with zero selection survivors/winners/finalists/support, zero protected candidate/return reads, holdout unconsumed, and independent negative reconstruction PASS. Satisfied by Phase30 PR #34 / merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e`.

## 2. Information mechanism and entitlement boundary

Lead source:

`MassiveRESTClient -> GET /stocks/filings/vX/form-4`

Current planning subscription: **Stocks Starter**.

The Form-4 endpoint is treated as early-access/beta and must be revalidated if schema, field semantics, or entitlement behavior changes. Phase31 does not assume Financials & Ratios Expansion, a Massive Options plan, paid partner data, or stock trade/quote entitlements unavailable to Starter.

Relevant structured fields include accession number, filing date, original-submission date, issuer/owner CIK, exact provider-native ticker associations, record type, transaction code/date, acquired/disposed flag, shares/price/value, post-transaction ownership, direct/indirect ownership, security type/title, officer/director/10% owner roles, Rule 10b5-1 flag, timeliness, filing URL, footnotes, and remarks.

Returned fields are not automatically alpha-authorized. Feasibility must establish chronology, completeness, provenance, and semantics first.

## 3. Point-in-time chronology rule before performance

Massive exposes Form-4 `filing_date` as a calendar date rather than an exact SEC acceptance timestamp.

Therefore the frozen conservative timing rule remains:

> A filing may first affect an ATLAS signal on the **first XNYS session** whose session date is **strictly later** than the Form-4 `filing_date`.

Frozen constant:

`NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`

This eliminates same-day timing ambiguity. Exact SEC acceptance timestamps may replace this rule only if authoritative, reproducible historical timestamps are proven in a separate non-performance step before any Phase31 outcome read.

Never use `transaction_date`, `period_of_report`, or `deemed_execution_date` as the public-availability timestamp. Those fields describe the transaction/event, not when the filing became public.

## 4. Why Form 4 is the lead regulatory mechanism

Form 4 is first because it reports economically meaningful insider ownership decisions with explicit transaction codes, filing dates, accession/source provenance, role flags, and frequent cross-sectional events. Research literature motivates testing purchases as potentially more informative than sales, but literature grants no ATLAS authority.

Short interest is deferred because settlement date is not automatically public-release time. 13-F remains possible later but is quarterly and delayed. 8-K remains a separate mechanism and may not be silently added after seeing Form-4 results.

## 5. Frozen initial feasibility contract — no performance

The feasibility stage must prove actual authenticated read-only access, nonempty historical coverage, deterministic pagination, original Form 4 (`form_type=4`) retrieval, useful identity/ticker/transaction fields, purchase (`P`) and sale (`S`) populations, field completeness, filing-to-transaction lag semantics, immutable replayable raw evidence, same-host pagination, zero market outcomes, zero protected performance, and zero broker/order/PAPER/LIVE authority.

### Frozen probe windows

- `research_boundary`: `2021-08-16` through `2021-08-20`;
- `mid_history`: `2023-08-14` through `2023-08-18`;
- `development_boundary`: `2026-05-04` through `2026-05-08`;
- `protected_boundary`: `2026-08-07` through `2026-08-11`.

These are feasibility windows only, not the eventual development/protected study split.

### Frozen query contract

- endpoint `/stocks/filings/vX/form-4`;
- `form_type=4` only;
- exact `filing_date.gte/lte` bounds;
- sort `filing_date.asc`;
- page limit `10000`;
- read-only GET;
- provider-native ticker text/case preserved exactly;
- full raw result objects retained as immutable provenance;
- no ticker aliases/remapping;
- no market-data joins;
- no future returns.

## 5A. First real target evidence — FAILED / NOT ACCEPTED

The user executed the frozen feasibility package locally on:

- branch `phase-31-sec-insider-transaction-alpha`;
- exact head `b59a64938eb84c0c1e7df3aaea390cc437326f94`;
- feasibility fingerprint `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`.

Result:

`FEASIBILITY_FAIL`

Failed check:

`transaction_dates_do_not_postdate_filings`

The check computes `filing_date - transaction_date`; a negative value means a returned transaction row says `transaction_date > filing_date`.

Important conclusions already locked:

- authenticated Form-4 retrieval occurred and immutable raw evidence was persisted, so this is not presently classified as a Stocks Starter entitlement failure;
- the provider adapter maps `filing_date` and `transaction_date` directly;
- the chronology invariant remains intact;
- no fields will be swapped, dates clamped, rows silently discarded, or check weakened to manufacture PASS;
- alpha hypotheses remain unfrozen;
- target market outcomes read = 0;
- protected candidate rows read = 0;
- protected return rows read = 0;
- protected holdout remains unconsumed;
- no trading authority was created.

See `docs/phase31_form4_feasibility_incident.md`.

## 5B. Frozen-evidence root-cause diagnostic

Before any new provider call, Phase31 now diagnoses the exact immutable JSONL written by the failed target:

`scripts/diagnose_phase31_form4_lag.py`

The diagnostic verifies every evidence SHA against the failed feasibility report and then reports the violating population by window, transaction code, security type, acquired/disposed flag, direct/indirect ownership, Rule 10b5-1 flag, timeliness, insider role, future gap days, accession, date pair, and provider-native ticker. It emits deterministic public-filing samples for root-cause inspection.

Diagnostic authority is strictly:

- local frozen provider evidence reads: allowed;
- provider calls: 0;
- target outcome reads: 0;
- protected candidate reads: 0;
- protected return reads: 0;
- broker/order/PAPER/LIVE writes: 0.

After diagnostics, the only acceptable classifications are:

1. ATLAS parser/mapping bug — repair mapping, keep gate;
2. authoritatively legitimate Form-4 semantic category — document authoritative semantics and freeze category-aware handling before performance;
3. Massive beta data defect — define a fail-closed, provenance-preserving quality rule only if defensible and frozen before performance;
4. unresolved ambiguity — feasibility remains failed.

Performance may not be consulted to choose the treatment.

## 6. Scientific contract after feasibility

The Phase31 hypothesis library is intentionally **not frozen yet**. If feasibility is eventually accepted, the next internal package must freeze, before any return read: original/amendment handling, public-availability/session rule, eligible transaction/security/role types, purchase-vs-sale treatment, multi-row/accession aggregation, 10b5-1/late/derivative/grant/exercise/gift/trust/indirect ownership handling, finite candidate signal transforms, deterministic-vs-learned method, outcome horizon(s), development/internal/protected chronology, purge/embargo, costs, sample/concentration minimums, dependence-aware inference, global multiplicity family, robustness gates, winner/finalist limits, independent reconstruction, and finalist-only protected confirmation.

No rule may be selected because it produced a favorable return in exploratory performance.

## 7. Protected-evidence boundary

Master protected outcome window remains:

`2026-05-12` through `2026-08-11`

It remains outcome-unopened after Phases26–30 and the current Phase31 feasibility work.

Reading Form-4 metadata whose filing dates fall inside the protected calendar window is allowed because it contains no ATLAS market outcomes. Joining those records to protected prices/returns, candidate performance, or return labels is forbidden until a later frozen finalist-only plan authorizes it.

## 8. Authority

During the active feasibility repair stage:

- existing local immutable Form-4 evidence reads: **ALLOWED**;
- bounded Massive Form-4 provider reads: **ONLY WHEN EXPLICITLY REQUIRED BY A LATER FROZEN FEASIBILITY REPAIR**;
- local provider/derived diagnostic writes: **ALLOWED**;
- target market-outcome reads: **0 / FORBIDDEN**;
- protected candidate reads: **0 / FORBIDDEN**;
- protected return reads: **0 / FORBIDDEN**;
- provider writes: **0**;
- broker reads: **0**;
- broker writes: **0**;
- order writes: **0**;
- PAPER submits: **0**;
- LIVE writes: **0**;
- automation writes: **0**;
- automatic broker failover: **DISABLED**;
- frontend trading authority: **NONE**.

## 9. Acceptance logic

A repaired feasibility PASS would not accept Phase31 and would not grant alpha support. It would only authorize scientific-policy freeze and later predictor construction.

A full positive Phase31 closeout requires at least one candidate to pass every subsequently frozen selection, internal, protected, robustness, multiplicity, concentration, independent-validation, and anti-workaround requirement.

A legitimate zero-finalist result is `ACCEPTED_NEGATIVE`. It does not unlock Phase32.
