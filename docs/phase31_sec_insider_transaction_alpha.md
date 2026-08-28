# Phase 31 — SEC Form-4 Insider-Transaction Alpha

**Status:** ACTIVE — FEASIBILITY / PROVENANCE ONLY. No Phase31 market outcomes have been read. No Phase31 alpha hypotheses are frozen yet.

**Source foundation:** Phase30 merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e` (`ACCEPTED_NEGATIVE`) with zero protected return reads and the master holdout unconsumed.

## Plain-English phase start

ATLAS has tested five different modern alpha mechanisms and none earned support. Phase31 deliberately changes the information source again.

Corporate insiders—officers, directors, and certain large owners—must publicly report changes in beneficial ownership on SEC Form 4. An insider who spends personal capital buying shares may be revealing information or conviction that is not fully captured by our existing price, cross-stock, relative-value, or news-arrival signals. Insider sales are more ambiguous because they can happen for diversification, taxes, compensation, or preplanned 10b5-1 programs, so purchases and sales must not be assumed symmetric.

Phase31 will test whether structured, publicly filed insider transactions contain robust future-return information **after the filing is publicly available** and after realistic trading costs. The phase is allowed to fail. We will not tune it into a positive result.

The first work package is only feasibility. It proves that the actual Massive Stocks Starter credential can retrieve enough historical Form-4 data with trustworthy provenance and useful fields. It reads no future returns.

## 1. Entry condition

Phase30 must be accepted negative with:

- selection survivors `[]`;
- winners `[]`;
- finalists `[]`;
- supported candidates `[]`;
- protected candidate rows read `0`;
- protected return rows read `0`;
- holdout consumed `False`;
- independent negative reconstruction PASS.

Satisfied by Phase30 PR #34 / merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e`.

## 2. Information mechanism

Lead source:

`MassiveRESTClient -> GET /stocks/filings/vX/form-4`

Current Massive documentation describes Form 4 as an early-access/beta endpoint included in all Stocks plans and updated daily. The configured user subscription is **Stocks Starter**. Phase31 does not assume the Financials & Ratios Expansion, a Massive Options plan, paid partner data, or stock trade/quote entitlements unavailable on Starter.

Relevant structured fields include:

- `accession_number`;
- `form_type`;
- `filing_date`;
- `date_of_original_submission`;
- `issuer_cik` / `issuer_name`;
- `owner_cik` / `owner_name`;
- exact provider-native `tickers` array;
- `record_type`;
- `transaction_code`;
- `transaction_date`;
- `transaction_acquired_disposed`;
- `transaction_shares`;
- `transaction_price_per_share`;
- `transaction_value`;
- `shares_owned_following_transaction`;
- `direct_or_indirect`;
- `security_type` / `security_title`;
- `is_officer`, `officer_title`, `is_director`, `is_ten_percent_owner`;
- `aff_10b5_one`;
- `transaction_timeliness`;
- `filing_url` and source footnotes/remarks as provenance.

These fields are not automatically alpha-authorized merely because the API returns them. The feasibility stage measures coverage and semantics first.

## 3. Point-in-time chronology rule before performance

Massive Form 4 exposes `filing_date` as a calendar date, not an exact SEC acceptance timestamp.

Therefore the default conservative Phase31 timing rule is:

> A filing may first affect an ATLAS signal on the first XNYS session whose session date is **strictly later** than the Form 4 `filing_date`.

This eliminates same-day ambiguity. A filing submitted before the opening bell and a filing submitted after the closing bell receive the same conservative treatment: both become usable the next trading session.

A later pre-performance feasibility step may replace this rule only if exact SEC acceptance timestamps are proven authoritative, reproducible, and historically available from original SEC evidence. That decision must occur before any Phase31 outcome read and become part of the frozen scientific fingerprint.

Never use `transaction_date`, `period_of_report`, or `deemed_execution_date` as the public-availability timestamp. Those dates describe the underlying transaction/event, which can precede public filing by days.

## 4. Why Form 4 before short interest / other regulatory data

Form 4 is the first regulatory mechanism because:

- it reports economically meaningful insider ownership decisions;
- purchase/sale transaction codes are explicit;
- filing date is explicit;
- accession number and SEC source URL provide auditable provenance;
- there is a large historical research literature motivating purchases as potentially informative;
- data should be frequent enough to support a broad cross-sectional study.

Short interest is deferred because its `settlement_date` is not the public release date. Treating settlement date as decision time would create lookahead. 13-F is also viable later but has quarterly cadence and statutory reporting lag. 8-K disclosures remain a separate future event mechanism if Form 4 fails; Phase31 will not silently expand into 8-K after seeing results.

## 5. Feasibility contract — no performance

The initial feasibility stage must prove:

1. actual authenticated read-only access on the configured Massive credential;
2. nonempty historical coverage near the ATLAS research boundary and recent boundaries;
3. deterministic pagination on `/stocks/filings/vX/form-4`;
4. original Form 4 (`form_type=4`) data can be retrieved without relying on amendments;
5. accession number, filing date, issuer CIK, owner CIK, provider-native ticker association, and record type are present at useful rates;
6. transaction rows expose usable transaction-code populations, especially `P` and `S`;
7. availability/completeness can be measured for transaction value, shares, price, ownership following transaction, role flags, security type, 10b5-1 flag, and timeliness;
8. filing-to-transaction lag can be measured without using market outcomes;
9. immutable raw evidence can be persisted and replayed with SHA-256 lineage;
10. provider pagination URLs remain on the Massive host;
11. target future-return rows read remain exactly zero;
12. protected candidate/return reads remain exactly zero;
13. broker/order/PAPER/LIVE/automation authority remains zero.

### Frozen feasibility probe windows

These windows are frozen only for the feasibility gate and contain no performance information:

- `research_boundary`: `2021-08-16` through `2021-08-20`;
- `mid_history`: `2023-08-14` through `2023-08-18`;
- `development_boundary`: `2026-05-04` through `2026-05-08`;
- `protected_boundary`: `2026-08-07` through `2026-08-11`.

The purpose is to prove historical depth and modern schema/population coverage across time. These are not the final Phase31 development/protected split dates.

### Feasibility query contract

- endpoint: `/stocks/filings/vX/form-4`;
- `form_type=4` only;
- `filing_date.gte/lte` exact probe bounds;
- sort `filing_date.asc`;
- page limit `10000`;
- read-only GET only;
- preserve provider-native ticker text/case exactly;
- preserve full raw result objects as immutable provenance;
- no ticker aliases/remapping during feasibility;
- no market-data joins;
- no future returns.

## 6. Scientific contract after feasibility

The Phase31 hypothesis library is intentionally **not frozen yet**. Freezing before field/population feasibility would encourage arbitrary thresholds or unusable features.

If feasibility passes, the next internal work package must freeze a finite study before performance. It will decide, before any return read:

- original-filing handling and amendment exclusion;
- exact public-availability/session rule;
- eligible transaction/security/role types;
- purchase versus sale treatment;
- aggregation of multiple rows per accession/owner/issuer;
- handling of 10b5-1 plans, late filings, derivatives, grants/exercises, gifts, trusts, and indirect ownership;
- candidate signal transforms such as transaction value, ownership change, multi-insider clustering, or role weighting;
- whether hypotheses are deterministic or learned;
- outcome horizon(s) consistent with the economic mechanism;
- development/internal/protected chronology and purge/embargo;
- realistic costs;
- sample/concentration minimums;
- dependence-aware bootstrap/inference;
- global multiplicity family;
- year/regime/liquidity robustness;
- winner/finalist limits;
- independent blindness/reconstruction;
- finalist-only protected confirmation.

No rule may be selected because it produced a favorable return in an exploratory outcome read.

## 7. Research motivation only

Phase31 is motivated by—not validated by—existing findings that:

- insider purchases are generally more informative than sales;
- insider activity can predict cross-sectional returns beyond simple contrarian effects;
- officers/directors can be more informative than broad insider categories;
- discretionary/open-market activity may be more informative than compensation/exercise-related ownership changes.

Literature is hypothesis motivation, not ATLAS evidence. Modern ATLAS acceptance still requires its own frozen, PIT-safe, after-cost, dependence-aware validation.

## 8. Protected-evidence boundary

Master protected outcome window remains:

`2026-05-12` through `2026-08-11`

It is still outcome-unopened after Phases26–30.

During Phase31 feasibility:

- reading Form-4 metadata with filing dates inside the protected calendar window is allowed because it contains no ATLAS market outcomes;
- joining those records to protected prices/returns is forbidden;
- protected candidate performance is forbidden;
- protected return reads are forbidden;
- no protected confirmation plan exists until a later frozen scientific contract and finalist set justify one.

## 9. Authority

During the active feasibility stage:

- Massive Form-4 provider reads: **BOUNDED / ALLOWED**;
- local immutable provider evidence writes: **ALLOWED**;
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

## 10. Acceptance logic

Feasibility PASS does **not** accept Phase31 and does not grant alpha support. It only authorizes the next internal step: scientific-policy freeze and predictor construction.

A later full Phase31 positive closeout requires at least one candidate to pass every frozen selection, internal, protected, robustness, multiplicity, concentration, independent-validation, and anti-workaround requirement.

A legitimate zero-finalist result is `ACCEPTED_NEGATIVE`. It does not unlock Phase32.
