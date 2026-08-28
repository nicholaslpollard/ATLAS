# Phase 31 — SEC Form-4 Insider-Transaction Alpha

**Status:** ACTIVE — ROOT CAUSE CLASSIFIED / SOURCE-QUALITY REPAIR FROZEN / LOCAL REPLAY PENDING. The original raw-feed feasibility target remains **NOT ACCEPTED** historical evidence. No Phase31 market outcomes have been read. No Phase31 alpha hypotheses are frozen yet.

**Source foundation:** Phase30 merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e` (`ACCEPTED_NEGATIVE`) with zero protected return reads and the master holdout unconsumed.

**Continuity records:**
- `docs/phase31_form4_feasibility_incident.md`
- `docs/phase31_form4_source_quality_repair.md`

## Plain-English phase start

ATLAS has tested five materially different modern alpha mechanisms and none earned support. Phase31 changes the information source again.

Corporate insiders—officers, directors, and certain large owners—must publicly report beneficial-ownership changes on SEC Form 4. Insider purchases may convey information or conviction not captured by existing price, cross-stock, relative-value, or news-arrival signals. Insider sales are more ambiguous because they can reflect diversification, taxes, compensation, or preplanned Rule 10b5-1 programs.

Phase31 will test whether structured, publicly filed insider transactions contain robust future-return information **after the filing is public** and after realistic trading costs. The phase is allowed to fail. Nothing will be tuned into a positive result.

The current work is still pre-performance source feasibility. Market outcomes remain forbidden until the source-quality repair passes and a finite scientific policy is frozen.

## 1. Entry condition

Phase30 accepted negative with zero selection survivors/winners/finalists/support, zero protected candidate/return reads, holdout unconsumed, and independent negative reconstruction PASS. Satisfied by Phase30 PR #34 / merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e`.

## 2. Information mechanism and entitlement boundary

Lead source:

`MassiveRESTClient -> GET /stocks/filings/vX/form-4`

Current planning subscription: **Stocks Starter**.

The Form-4 endpoint is early-access/beta and must be revalidated if schema, field semantics, or entitlement behavior changes. Phase31 does not assume Financials & Ratios Expansion, a Massive Options plan, paid partner data, or unavailable stock trade/quote entitlements.

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

The initial feasibility stage was frozen to prove authenticated read-only access, nonempty historical coverage, deterministic pagination, original Form 4 (`form_type=4`) retrieval, useful identity/ticker/transaction fields, purchase (`P`) and sale (`S`) populations, field completeness, filing-to-transaction chronology, immutable replayable raw evidence, zero market outcomes, zero protected performance, and zero broker/order/PAPER/LIVE authority.

### Frozen probe windows

- `research_boundary`: `2021-08-16` through `2021-08-20`
- `mid_history`: `2023-08-14` through `2023-08-18`
- `development_boundary`: `2026-05-04` through `2026-05-08`
- `protected_boundary`: `2026-08-07` through `2026-08-11`

These are feasibility windows only, not the eventual development/protected study split.

### Frozen query contract

- endpoint `/stocks/filings/vX/form-4`
- `form_type=4` only
- exact `filing_date.gte/lte` bounds
- sort `filing_date.asc`
- page limit `10000`
- read-only GET
- provider-native ticker text/case preserved exactly
- full raw result objects retained as immutable provenance
- no ticker aliases/remapping
- no market-data joins
- no future returns.

## 5A. First real target evidence — FAILED / permanently preserved

Target:

- branch `phase-31-sec-insider-transaction-alpha`
- exact head `b59a64938eb84c0c1e7df3aaea390cc437326f94`
- feasibility fingerprint `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`.

Result:

`FEASIBILITY_FAIL`

Sole failed check:

`transaction_dates_do_not_postdate_filings`

The check computes `filing_date - transaction_date`; a negative value means the provider says a transaction occurred after the filing.

Locked conclusions:

- authenticated Form-4 retrieval occurred and raw evidence was persisted;
- this was not an entitlement failure;
- the provider adapter maps `filing_date` and `transaction_date` directly;
- the chronology invariant remains intact;
- the failed report remains failed;
- no field swaps, date clamping, silent row deletion, or tolerance change is allowed;
- alpha hypotheses remain unfrozen;
- target market outcomes read = 0;
- protected candidate rows read = 0;
- protected return rows read = 0;
- protected holdout remains unconsumed;
- no trading authority was created.

## 5B. Frozen-evidence root-cause diagnostic — COMPLETE

Diagnostic implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

Target-machine result:

- status `DIAGNOSTIC_COMPLETE`
- Pass True
- 36,854 transaction rows with both dates
- 33,510 transaction-before-filing
- 3,343 same-day
- 1 transaction-after-filing
- violating rows/accessions/issuers/owners = 1 / 1 / 1 / 1
- provider calls = 0
- target/protected market outcomes = 0
- broker/order/PAPER/LIVE activity = 0.

Violating source row:

- accession `0000950170-23-043337`
- ticker `WISH`
- filing date `2023-08-17`
- period of report `2023-08-15`
- transaction date `2023-09-15`
- transaction after filing by 29 calendar days
- transaction code `M`
- derivative `Restricted Stock Unit`
- acquired `A`
- direct ownership `D`
- Rule 10b5-1 false
- transaction timeliness `O`
- Chief Product Officer
- 496 shares.

Violation artifact SHA256:

`3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`

## 5C. Root cause — Massive beta source-association/data-quality defect

Massive's current Form-4 documentation defines:

- `filing_date` as the date submitted to the SEC;
- `transaction_date` as the transaction date;
- `transaction_timeliness=O` as **on time**, `L` as late;
- Form 4 as a filing following reportable insider transactions.

The ATLAS adapter copies those raw fields directly. Therefore a transaction dated 2023-09-15 cannot be an on-time transaction row belonging to a filing submitted 2023-08-17 under the provider's documented semantics.

The endpoint is early-access/beta. The root cause is classified as a **Massive beta source-association/data-quality defect**, not an ATLAS parser bug and not a legitimate future-dated Form-4 category.

The descriptive facts `WISH`, `M`, derivative/RSU, officer, and 496 shares do not participate in the repair rule.

ATLAS does not infer a corrected accession for the row.

## 5D. Frozen source-quality repair — before any market outcome

Policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Generic treatment:

1. Preserve all raw provider rows and SHAs unchanged.
2. Any transaction row with `transaction_date > filing_date` is a chronology-invalid source row.
3. A chronology-invalid row contaminates its entire `accession_number`.
4. Quarantine every row belonging to that accession from the alpha-authoritative source corpus.
5. If a chronology-invalid row lacks an accession, fail closed.
6. Never clamp dates, swap fields, infer a replacement filing, or mutate raw evidence.
7. The authoritative corpus must have zero post-filing transaction dates.
8. Provider-native ticker strings/case remain unchanged.
9. The classifier cannot use ticker, transaction code, security type, role, price, return, profitability, or any market outcome.

There is no "one bad row" tolerance. The policy handles any number of impossible accessions identically.

Provider-free target replay:

`scripts/run_phase31_form4_source_quality_repair.py`

The replay must verify the original failed report, raw evidence SHAs, completed diagnostic, and diagnostic violation artifact SHA. It writes separate derived authoritative and quarantine artifacts.

A `SOURCE_QUALITY_REPAIR_PASS` means Form-4 source evidence is usable only behind this fail-closed source-quality boundary. It does **not** rewrite the original failure, accept Phase31, grant alpha support, or authorize market outcomes before the scientific contract is frozen.

See `docs/phase31_form4_source_quality_repair.md`.

## 6. Scientific contract after source-quality repair

The Phase31 hypothesis library is intentionally **not frozen yet**.

If the source-quality repair passes, the next internal package must freeze, before any return read:

- original/amendment handling;
- exact eligible transaction/security/role types;
- purchase-vs-sale treatment;
- multi-row/accession aggregation;
- 10b5-1, late, derivative, grant, exercise, gift, trust, indirect ownership handling;
- finite candidate signal transforms;
- deterministic-vs-learned method;
- outcome horizon(s);
- development/internal/protected chronology;
- purge/embargo;
- costs;
- sample/concentration minimums;
- dependence-aware inference;
- global multiplicity family;
- robustness gates;
- winner/finalist limits;
- independent reconstruction;
- finalist-only protected confirmation.

No rule may be selected because it produced a favorable return in exploratory performance.

## 7. Protected-evidence boundary

Master protected outcome window:

`2026-05-12` through `2026-08-11`

It remains outcome-unopened after Phases26–30 and all current Phase31 feasibility/diagnostic/repair design work.

Reading Form-4 metadata whose filing dates fall inside the protected calendar window is allowed because it contains no ATLAS market outcomes. Joining those records to protected prices/returns, candidate performance, or return labels is forbidden until a later frozen finalist-only plan authorizes it.

## 8. Authority

During the active source-quality repair stage:

- existing local immutable Form-4 evidence reads: **ALLOWED**
- provider-free source-quality replay: **ALLOWED**
- bounded new Massive reads: **NOT REQUIRED FOR THE CURRENT REPAIR**
- local derived quarantine/authoritative artifacts: **ALLOWED**
- target market-outcome reads: **0 / FORBIDDEN**
- protected candidate reads: **0 / FORBIDDEN**
- protected return reads: **0 / FORBIDDEN**
- provider writes: **0**
- broker reads: **0**
- broker writes: **0**
- order writes: **0**
- PAPER submits: **0**
- LIVE writes: **0**
- automation writes: **0**
- automatic broker failover: **DISABLED**
- frontend trading authority: **NONE**.

## 9. Acceptance logic

A source-quality repair PASS does not accept Phase31. It authorizes only the finite scientific-policy freeze.

A full positive Phase31 closeout requires at least one candidate to pass every subsequently frozen selection, internal, protected, robustness, multiplicity, concentration, independent-validation, and anti-workaround requirement.

A legitimate zero-finalist result is `ACCEPTED_NEGATIVE`. It does not unlock Phase32.

Phase32 remains blocked until at least one alpha architecture has accepted historical analytical `SUPPORTED` authority.
